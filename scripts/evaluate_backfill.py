"""Evaluate the 2026-27 backfill against actual box scores.

Prints availability, minutes and usage accuracy for completed games only.
No files are written.

Usage:
    TEAM_HIERARCHY_DATA=data/daily uv run --group data python \
        scripts/evaluate_backfill.py --season 2026-27
"""

from __future__ import annotations

import argparse
import os
from itertools import pairwise
from pathlib import Path

import numpy as np
import polars as pl
import scs_hub


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--db-con", default="cockroach-read")
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(os.environ.get("TEAM_HIERARCHY_DATA", "data/daily")),
    )
    return parser.parse_args()


def ece(p: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    total = len(p)
    out = 0.0
    for lo, hi in pairwise(edges):
        m = (p >= lo) & (p < hi if hi < 1 else p <= hi)
        if m.any():
            out += abs(p[m].mean() - y[m].mean()) * m.sum() / total
    return float(out)


def main() -> None:
    args = parse_args()
    data = Path(args.data).expanduser().resolve()
    box = pl.read_parquet(
        data / "nba" / "player_box_score.parquet",
        columns=["game_id", "team_id", "player_id", "min", "usg_pct"],
    )
    schedule = pl.read_parquet(
        data / "nba" / "league_game_schedule.parquet",
        columns=["game_id", "season"],
    )
    season_games = schedule.filter(pl.col("season") == args.season)["game_id"].unique().to_list()
    box = box.filter(pl.col("game_id").is_in(season_games)).with_columns(
        pl.col("min").cast(pl.Float64),
        pl.col("usg_pct").cast(pl.Float64),
        (pl.col("min").fill_null(0) > 0).alias("played"),
        pl.col("min").fill_null(0).alias("actual_min"),
    )
    completed = box["game_id"].unique().to_list()

    hub = scs_hub.SportsHub(db_con=args.db_con)
    pred = hub.db.read(
        f"""
        SELECT game_date, game_id, team_id, player_id, p_play,
               minutes_if_plays, expected_minutes, expected_usage
        FROM mod.team_hierarchy
        WHERE game_date >= DATE '2026-10-01' AND game_id IN ({",".join(map(str, completed))})
        """
    )
    if pred.is_empty():
        raise SystemExit("no completed predictions to evaluate")

    joined = pred.join(
        box.select("game_id", "team_id", "player_id", "played", "actual_min", "usg_pct"),
        on=["game_id", "team_id", "player_id"],
        how="left",
    ).with_columns(
        pl.col("played").fill_null(False),
        pl.col("actual_min").fill_null(0.0),
        pl.col("usg_pct").fill_null(0.0),
    )

    p = joined["p_play"].to_numpy()
    y = joined["played"].to_numpy().astype(int)
    brier = float(np.mean((p - y) ** 2))
    logloss = float(
        -np.mean(y * np.log(np.clip(p, 1e-12, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-12, 1)))
    )
    from sklearn.metrics import roc_auc_score

    auc = float(roc_auc_score(y, p)) if y.min() != y.max() else float("nan")

    played = joined.filter(pl.col("played"))
    min_played = played["actual_min"].to_numpy()
    min_pred = played["minutes_if_plays"].to_numpy()
    exp_all = joined["expected_minutes"].to_numpy()
    act_all = joined["actual_min"].to_numpy()
    usg_act = played["usg_pct"].to_numpy()
    usg_pred = played["expected_usage"].to_numpy()

    def mae(a, b):
        return float(np.mean(np.abs(a - b)))

    def rmse(a, b):
        return float(np.sqrt(np.mean((a - b) ** 2)))

    def r2(a, b):
        return float(1 - np.sum((a - b) ** 2) / np.sum((b - b.mean()) ** 2))

    print(
        f"season {args.season}: {joined.height:,} predictions, "
        f"{joined['game_id'].n_unique()} completed games, "
        f"{joined['game_date'].n_unique()} dates"
    )
    print(f"availability base rate {y.mean():.3f}")
    print()
    print(f"{'availability':<22} {'Brier':>8} {'log loss':>9} {'AUC':>7} {'ECE':>7}")
    print(f"{'p_play':<22} {brier:8.4f} {logloss:9.4f} {auc:7.4f} {ece(p, y):7.4f}")
    print()
    print(f"{'minutes':<22} {'MAE':>8} {'RMSE':>8} {'R2':>8}")
    print(
        f"{'minutes_if_plays':<22} {mae(min_pred, min_played):8.3f} "
        f"{rmse(min_pred, min_played):8.3f} {r2(min_pred, min_played):8.3f}"
    )
    print(
        f"{'expected_minutes':<22} {mae(exp_all, act_all):8.3f} "
        f"{rmse(exp_all, act_all):8.3f} {r2(exp_all, act_all):8.3f}"
    )
    print(f"  (n={played.height:,} played rows for the conditional minutes)")
    print()
    print(f"{'usage, played rows':<22} {'MAE':>8} {'RMSE':>8} {'R2':>8}")
    print(
        f"{'expected_usage':<22} {mae(usg_pred, usg_act):8.4f} "
        f"{rmse(usg_pred, usg_act):8.4f} {r2(usg_pred, usg_act):8.4f}"
    )
    print()

    per_date = (
        joined.group_by("game_date")
        .agg(
            pl.len().alias("rows"),
            pl.col("played").sum().alias("played"),
            (pl.col("p_play").mean()).alias("mean_p"),
            ((pl.col("p_play") - pl.col("played")) ** 2).mean().alias("brier"),
            (pl.col("minutes_if_plays") - pl.col("actual_min")).abs().mean().alias("min_mae"),
        )
        .sort("game_date")
    )
    print("by date:")
    print(per_date)


if __name__ == "__main__":
    main()
