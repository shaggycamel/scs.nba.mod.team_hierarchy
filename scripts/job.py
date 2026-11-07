"""Run the daily team-hierarchy job and publish it.

Called by `scs.nba.mod.runner` through `__main__.py`, or manually:

    uv run --group data python __main__.py --date 2026-11-07

Sequence:
  1. refresh the full hierarchy snapshot from Cockroach
  2. fit the point-in-time hierarchy for the target date
  3. write the depth chart and publish it to mod.team_hierarchy
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parent.parent
SOURCE = "scs.nba.mod.team_hierarchy"
TASK = "team_hierarchy.job"


def current_season(day: date) -> str:
    year = day.year if day.month >= 7 else day.year - 1
    return f"{year}-{str(year + 1)[-2:]}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date", type=date.fromisoformat,
        default=datetime.now(UTC).date(),
        help="slate date (default: today in UTC)",
    )
    parser.add_argument("--season", default=None)
    parser.add_argument("--cadence", default=os.environ.get("SCS_CADENCE", "daily"))
    parser.add_argument("--db-con", default="cockroach-write")
    parser.add_argument("--source", default=os.environ.get("UPDATE_LOG_SOURCE", SOURCE))
    parser.add_argument("--skip-fetch", action="store_true")
    return parser.parse_args(argv)


def run(name: str, argv: list[str], *, env: dict[str, str] | None = None) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {name}", flush=True)
    subprocess.run([sys.executable, *argv], cwd=ROOT, env=env, check=True)


def parse_kickoff() -> datetime:
    raw = os.environ.get("UPDATE_LOG_KICKOFF")
    if raw:
        try:
            value = datetime.fromisoformat(raw)
        except ValueError:
            pass
        else:
            return value if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime.now(UTC)


def log_run(kickoff: datetime, cadence: str, source: str, success: bool,
            error: str | None, row_count: int | None, db_con: str) -> None:
    import scs_hub

    hub = scs_hub.SportsHub(db_con=db_con)
    hub.db.write(
        pl.DataFrame(
            {
                "source": source,
                "job_kickoff": kickoff,
                "cadence": cadence,
                "task": TASK,
                "task_time": datetime.now(UTC),
                "success": success,
                "error_message": error,
                "row_count": row_count,
            },
            schema_overrides={"row_count": pl.Int64},
        ),
        "update_log",
        "util",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    kickoff = parse_kickoff()
    result_file = os.environ.get("SCS_RESULT_FILE")
    season = args.season or current_season(args.date)
    data_dir = ROOT / "data/daily"
    output = ROOT / f"artifacts/team_hierarchy_{args.date}.parquet"

    error = None
    rows = None
    try:
        if not args.skip_fetch:
            run("fetch", [
                "scripts/00_fetch.py", "--through", season,
                "--out", str(data_dir), "--db-con", args.db_con,
            ])

        os.environ["TEAM_HIERARCHY_DATA"] = str(data_dir)
        from team_hierarchy.pipeline import daily_hierarchy

        served = daily_hierarchy(args.date)
        rows = served.height
        if served.is_empty():
            print(f"{args.date}: no fixtures; nothing to publish")
        else:
            out = served.select(
                "game_date", "game_id", "team_id", "player_id", "season",
                "team_abbreviation", "opponent", "home", "player_name",
                "position", pl.col("position_depth").cast(pl.Int64),
                pl.col("height_cm").cast(pl.Int64),
                pl.col("report_status"),
                pl.col("p_play").cast(pl.Float64),
                pl.col("minutes_if_plays").cast(pl.Float64),
                pl.col("expected_minutes").cast(pl.Float64),
                pl.col("expected_usage").cast(pl.Float64),
                pl.col("depth_rank").cast(pl.Int64),
                pl.col("available_rank").cast(pl.Int64),
                pl.col("rank_improvement").cast(pl.Int64),
                pl.col("expected_vacated_minutes").cast(pl.Float64),
                pl.col("expected_vacated_minutes_same_position").cast(pl.Float64),
            ).with_columns(pl.lit(datetime.now(UTC)).alias("generated_at"))
            output.parent.mkdir(parents=True, exist_ok=True)
            out.write_parquet(output)
            run("publish", [
                "scripts/publish.py", "--input", str(output),
                "--db-con", args.db_con,
            ])
    except Exception as exc:  # noqa: BLE001 - the runner needs one failure row
        error = f"{type(exc).__name__}: {exc}"
        print(f"failed: {error}", file=sys.stderr, flush=True)

    if result_file:
        Path(result_file).write_text(
            json.dumps({"row_count": rows if error is None else 0}) + "\n"
        )
    else:
        log_run(kickoff, args.cadence, args.source, error is None, error, rows, args.db_con)
    return 0 if error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
