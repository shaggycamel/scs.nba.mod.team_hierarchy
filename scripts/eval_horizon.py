"""Does the injury curve beat the hierarchy's state-only availability?

For each run date, predict the next week's games with the panel cut at the run
date -- the information a real pre-game run has -- and compare the hierarchy's
own probability with the composed one. Restricting the panel is the whole point:
without `panel_through`, the serving state sees games played between the run and
the game, which flatters both models and hides the horizon problem.

The availability file comes from the injury repo:

    INJURY_DURATION_DATA=data/full uv run python \
        scripts/21_backfill_availability.py --season 2026-27

Then:

    uv run --group data python scripts/eval_horizon.py \
        --availability ../injury_duration/artifacts/availability_2026_27.parquet \
        --runs 2026-11-02,2026-11-05,2026-11-08,2026-11-11
"""

from __future__ import annotations

import argparse
import os
from datetime import date, timedelta
from pathlib import Path

import polars as pl

from team_hierarchy import source
from team_hierarchy.persist import load
from team_hierarchy.pipeline import daily_hierarchy

KEY = ["game_id", "player_id"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--availability", type=Path, required=True)
    parser.add_argument(
        "--runs",
        required=True,
        help="comma-separated run dates (the panel is cut at each)",
    )
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--db-con", default="jetson-read")
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("artifacts/team_hierarchy/model.pkl"),
    )
    return parser.parse_args()


def _slates(season: str) -> tuple[pl.DataFrame, pl.DataFrame]:
    box = source.read_player_games().select("game_id", "player_id", "min")
    schedule = source.read_schedule().select("game_id", "game_date", "season", "season_type")
    regular = schedule.filter(
        (pl.col("season") == season) & (pl.col("season_type") == "Regular Season")
    )
    return box, regular


def _brier(col: str) -> pl.Expr:
    return ((pl.col(col) - pl.col("played").cast(pl.Float64)) ** 2).mean()


def main() -> None:
    args = parse_args()
    os.environ["TEAM_HIERARCHY_DB_CON"] = args.db_con
    bundle = load(args.model)
    availability = pl.read_parquet(args.availability)
    box, schedule = _slates(args.season)
    slates = sorted(schedule["game_date"].unique().to_list())

    rows: list[pl.DataFrame] = []
    for run in (date.fromisoformat(x) for x in args.runs.split(",")):
        window = [g for g in slates if run < g <= run + timedelta(days=args.days)]
        av = availability.filter(pl.col("prediction_date") == run)
        for game in window:
            if schedule.filter(pl.col("game_date") == game).join(box, on="game_id").is_empty():
                continue
            base = daily_hierarchy(game, bundle=bundle, include_report=False, panel_through=run)
            new = daily_hierarchy(
                game,
                bundle=bundle,
                include_report=False,
                panel_through=run,
                availability=av,
            )
            rows.append(
                base.select(*KEY, "p_play", "expected_minutes")
                .join(
                    new.select(
                        *KEY,
                        pl.col("p_play").alias("p_play_new"),
                        pl.col("p_play_injury"),
                        pl.col("p_play_source"),
                        pl.col("expected_minutes").alias("expected_minutes_new"),
                    ),
                    on=KEY,
                )
                .with_columns(
                    pl.lit(run).alias("run_date"),
                    pl.lit(game).alias("game_date"),
                )
            )
        print(f"{run}: {len(rows)} slates so far", flush=True)

    if not rows:
        raise SystemExit("no matched games; check the run dates and snapshot")

    actual = box.select(*KEY, pl.col("min").fill_null(0.0).alias("minutes")).with_columns(
        (pl.col("minutes") > 0).alias("played")
    )
    data = (
        pl.concat(rows)
        .join(actual, on=KEY, how="left")
        .with_columns(pl.col("played").fill_null(False), pl.col("minutes").fill_null(0.0))
        .with_columns(
            (pl.col("game_date") - pl.col("run_date")).dt.total_days().alias("days_ahead")
        )
    )
    changed = data.filter(pl.col("p_play_source") == "injury")

    def show(df: pl.DataFrame, label: str) -> None:
        print(
            f"\n{label}: n={df.height} base_rate={df['played'].mean():.3f} "
            f"hier_mean={df['p_play'].mean():.3f} injury_mean={df['p_play_new'].mean():.3f}"
        )
        print(
            df.select(
                _brier("p_play").round(4).alias("brier_state_only"),
                _brier("p_play_new").round(4).alias("brier_composed"),
                ((pl.col("expected_minutes") - pl.col("minutes")).abs().mean())
                .round(3)
                .alias("minutes_mae_before"),
                ((pl.col("expected_minutes_new") - pl.col("minutes")).abs().mean())
                .round(3)
                .alias("minutes_mae_after"),
            )
        )

    show(data, "all rows")
    for lo, hi in [(1, 2), (3, 5), (6, 7)]:
        show(
            data.filter((pl.col("days_ahead") >= lo) & (pl.col("days_ahead") <= hi)),
            f"{lo}-{hi} days ahead",
        )
    show(changed, "rows the injury curve changed")


if __name__ == "__main__":
    main()
