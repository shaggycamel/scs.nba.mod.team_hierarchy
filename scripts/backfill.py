"""Backfill completed 2026-27 depth charts with the frozen model.

Only dates that have already happened (plus today) are scored. Every date uses
features from games before it and the same 2025-26 bundle, so the whole season
is out-of-sample.

Usage:
    TEAM_HIERARCHY_DATA=data/daily uv run python scripts/backfill.py \
        --season 2026-27 --end 2026-11-07
"""

from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--start", type=date.fromisoformat, default=None)
    parser.add_argument(
        "--end", type=date.fromisoformat, default=datetime.now(UTC).date()
    )
    parser.add_argument("--model", type=Path,
                        default=Path("artifacts/team_hierarchy/model.pkl"))
    parser.add_argument("--out", type=Path,
                        default=Path("artifacts/team_hierarchy_backfill.parquet"))
    parser.add_argument("--db-con", default="cockroach-write")
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    from team_hierarchy.config import DATA_DIR
    from team_hierarchy.data import load_fixtures
    from team_hierarchy.persist import load
    from team_hierarchy.pipeline import daily_hierarchy

    model_path = args.model if args.model.is_absolute() else ROOT / args.model
    bundle = load(model_path)
    schedule = load_fixtures(DATA_DIR).filter(pl.col("season") == args.season)
    dates = (
        schedule.filter(pl.col("game_date") <= args.end)["game_date"]
        .unique().sort().to_list()
    )
    if args.start:
        dates = [d for d in dates if d >= args.start]
    if args.limit:
        dates = dates[: args.limit]
    print(f"{args.season}: {len(dates)} slates through {args.end}")

    frames = []
    for i, day in enumerate(dates, 1):
        served = daily_hierarchy(day, bundle=bundle)
        if served.is_empty():
            print(f"  {day}: no fixtures")
            continue
        out = served.select(
            "game_date", "game_id", "team_id", "player_id", "season",
            "team_abbreviation", "opponent", "home", "player_name",
            "position", pl.col("position_depth").cast(pl.Int64),
            pl.col("height_cm").cast(pl.Int64), pl.col("report_status"),
            pl.col("p_play").cast(pl.Float64),
            pl.col("minutes_if_plays").cast(pl.Float64),
            pl.col("expected_minutes").cast(pl.Float64),
            pl.col("expected_usage").cast(pl.Float64),
            pl.col("depth_rank").cast(pl.Int64),
            pl.col("available_rank").cast(pl.Int64),
            pl.col("rank_improvement").cast(pl.Int64),
            pl.col("expected_vacated_minutes").cast(pl.Float64),
            pl.col("expected_vacated_minutes_same_position").cast(pl.Float64),
        ).with_columns(
            pl.lit(bundle.metadata["trained_through"]).alias("model_cutoff"),
            pl.lit(bundle.metadata["created_at"]).alias("model_version"),
            pl.lit(datetime.now(UTC)).alias("generated_at"),
        )
        frames.append(out)
        print(f"  [{i}/{len(dates)}] {day}: {out.height} rows", flush=True)

    if not frames:
        raise SystemExit("no rows generated")
    all_rows = pl.concat(frames).sort("game_date", "team_abbreviation", "position", "position_depth")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    all_rows.write_parquet(args.out)
    print(f"wrote {args.out}: {all_rows.height:,} rows, "
          f"{all_rows['game_date'].n_unique()} dates")

    import subprocess
    import sys
    subprocess.run(
        [sys.executable, "scripts/publish.py", "--input", str(args.out),
         "--db-con", args.db_con],
        cwd=ROOT, check=True,
    )


if __name__ == "__main__":
    main()
