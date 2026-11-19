"""Run the daily team-hierarchy job and publish it.

Called by `scs.nba.mod.runner` through `__main__.py`, or manually:

    uv run --group data python __main__.py --date 2026-11-07

Sequence:
  1. refresh the full hierarchy snapshot
  2. score every unplayed slate in the next `--days` window
  3. write the depth chart to mod.team_hierarchy_base

Availability is the report when one exists for the game date; otherwise the
injury-duration curve fills it (see `_apply_availability`).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
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
        "--date",
        type=date.fromisoformat,
        default=None,
        help="score one slate instead of the horizon",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="calendar days of unplayed slates to score (default: 7)",
    )
    parser.add_argument("--season", default=None)
    parser.add_argument("--cadence", default=os.environ.get("SCS_CADENCE", "intraday"))
    parser.add_argument("--db-con", default="jetson-write")
    parser.add_argument("--source", default=os.environ.get("UPDATE_LOG_SOURCE", SOURCE))
    parser.add_argument(
        "--skip-freshness",
        action="store_true",
        help="skip the injury/box-score freshness gates (manual backfills)",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("artifacts/team_hierarchy/model.pkl"),
    )
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


def log_run(
    kickoff: datetime,
    cadence: str,
    source: str,
    success: bool,
    error: str | None,
    row_count: int | None,
    db_con: str,
) -> None:
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


def horizon_dates(schedule: pl.DataFrame, season: str, start: date, days: int) -> list[date]:
    """Slates in the window whose results have not been ingested.

    A date freezes once any result arrives, so a partially played slate is
    never rewritten and its first pre-game rows survive.
    """
    window = schedule.filter(
        (pl.col("season") == season)
        & (pl.col("season_type") == "Regular Season")
        & (pl.col("game_date") >= start)
        & (pl.col("game_date") <= start + timedelta(days=days - 1))
    )
    if window.is_empty():
        return []
    return (
        window.group_by("game_date")
        .agg(pl.col("team_winner").is_null().all().alias("unplayed"))
        .filter("unplayed")
        .sort("game_date")["game_date"]
        .to_list()
    )


def require_fresh(hub, task: str, max_age_minutes: int, label: str) -> None:
    """Fail when an upstream task has not written recently."""
    last = hub.db.read(
        f"SELECT max(task_time) AS t FROM util.update_log WHERE task = '{task}' AND success"
    ).item()
    if last is None:
        raise RuntimeError(f"no successful {label} update in util.update_log")
    age = datetime.now(UTC) - last
    if age > timedelta(minutes=max_age_minutes):
        raise RuntimeError(
            f"{label} data is {age} old; expected an update within {max_age_minutes} minutes"
        )


def load_availability(hub, max_age_minutes: int = 180) -> pl.DataFrame:
    """The latest per-game injury curve, or a loud failure.

    Falling back to the hierarchy's own state-only probability would publish
    the overconfident numbers this table exists to replace.
    """
    try:
        frame = hub.db.read(
            """
            SELECT prediction_date, player_id, game_date, p_available, generated_at
            FROM mod.injury_game_availability_base
            WHERE prediction_date = (
                SELECT max(prediction_date) FROM mod.injury_game_availability_base
            )
            """
        )
    except Exception as exc:
        raise RuntimeError(
            "mod.injury_game_availability_base is unavailable; run "
            "scs.nba.mod.injury_duration first"
        ) from exc
    if frame.is_empty():
        raise RuntimeError(
            "mod.injury_game_availability_base has no rows; run scs.nba.mod.injury_duration first"
        )
    newest = frame["generated_at"].max()
    if newest is not None and datetime.now(UTC) - newest > timedelta(minutes=max_age_minutes):
        raise RuntimeError(
            "mod.injury_game_availability_base is "
            f"{datetime.now(UTC) - newest} old; the injury job has not run"
        )
    return frame.select("prediction_date", "player_id", "game_date", "p_available")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    kickoff = parse_kickoff()
    result_file = os.environ.get("SCS_RESULT_FILE")
    today = datetime.now(UTC).date()
    season = args.season or current_season(args.date or today)

    error = None
    rows = None
    try:
        # The loaders read the public views; this selects the credentials
        # section before the first connection is opened.
        os.environ["TEAM_HIERARCHY_DB_CON"] = args.db_con
        from team_hierarchy import source
        from team_hierarchy.persist import load
        from team_hierarchy.pipeline import daily_hierarchy

        schedule = source.read_schedule()
        dates = (
            [args.date]
            if args.date is not None
            else horizon_dates(schedule, season, today, args.days)
        )
        if not dates:
            print(f"no unplayed fixtures in the next {args.days} days; nothing to publish")
            served = pl.DataFrame()
        else:
            import scs_hub

            hub = scs_hub.SportsHub(db_con=args.db_con)
            if not args.skip_freshness:
                require_fresh(hub, "nba.get_team_injuries", 120, "injury report")
                require_fresh(hub, "nba.get_player_box_score", 30 * 60, "box score")
            availability = load_availability(hub)

            model_path = args.model if args.model.is_absolute() else ROOT / args.model
            if not model_path.exists():
                raise FileNotFoundError(f"missing model bundle: {model_path}")
            bundle = load(model_path)
            frames = [
                frame
                for frame in (
                    daily_hierarchy(day, bundle=bundle, availability=availability) for day in dates
                )
                if not frame.is_empty()
            ]
            served = pl.concat(frames) if frames else pl.DataFrame()
            if served.is_empty():
                raise RuntimeError(f"no hierarchy rows for {dates}")
            missing = sorted(set(dates) - set(served["game_date"].unique().to_list()))
            if missing:
                raise RuntimeError(f"no hierarchy rows for scheduled dates: {missing}")

        rows = served.height
        if served.is_empty():
            print(f"{today}: no fixtures; nothing to publish")
        else:
            output = ROOT / (
                f"artifacts/team_hierarchy_{args.date}.parquet"
                if args.date is not None
                else f"artifacts/team_hierarchy_{today}_{args.days}d.parquet"
            )
            optional = [
                pl.col(c).cast(pl.Float64)
                for c in ("expected_usage_model", "expected_usage_events")
                if c in served.columns
            ]
            out = served.select(
                "game_date",
                "game_id",
                "team_id",
                "player_id",
                "season",
                "team_abbreviation",
                "opponent",
                "home",
                "player_name",
                "position",
                pl.col("position_depth").cast(pl.Int64),
                pl.col("height_cm").cast(pl.Int64),
                pl.col("report_status"),
                pl.col("p_play").cast(pl.Float64),
                pl.col("p_play_injury").cast(pl.Float64),
                pl.col("p_play_source"),
                pl.col("minutes_if_plays").cast(pl.Float64),
                pl.col("expected_minutes").cast(pl.Float64),
                pl.col("expected_usage").cast(pl.Float64),
                pl.col("depth_rank").cast(pl.Int64),
                pl.col("available_rank").cast(pl.Int64),
                pl.col("rank_improvement").cast(pl.Int64),
                pl.col("expected_vacated_minutes").cast(pl.Float64),
                pl.col("expected_vacated_minutes_same_position").cast(pl.Float64),
                *optional,
            ).with_columns(
                pl.lit(bundle.metadata["trained_through"]).alias("model_cutoff"),
                pl.lit(bundle.metadata["created_at"]).alias("model_version"),
                pl.lit(datetime.now(UTC)).alias("generated_at"),
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            out.write_parquet(output)
            run(
                "publish",
                [
                    "scripts/publish.py",
                    "--input",
                    str(output),
                    "--db-con",
                    args.db_con,
                ],
            )
    except Exception as exc:  # noqa: BLE001 - the runner needs one failure row
        error = f"{type(exc).__name__}: {exc}"
        print(f"failed: {error}", file=sys.stderr, flush=True)

    if result_file:
        Path(result_file).write_text(json.dumps({"row_count": rows if error is None else 0}) + "\n")
    else:
        log_run(kickoff, args.cadence, args.source, error is None, error, rows, args.db_con)
    return 0 if error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
