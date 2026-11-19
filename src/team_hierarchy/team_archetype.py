"""Team-level archetype summary: distribution plus the hierarchy inside it.

One row per team-game-archetype. The shares answer "what is this team made of"
for the expected starters (rolling `start_rate_5`), the men who actually
started, and the players expected to be available. The top-three columns answer
"who owns this style right now" without collapsing the player to a hard label.
"""

from __future__ import annotations

import polars as pl

from .similarity import RESPONSIBILITY_PREFIX, responsibility_columns

KEYS = ("game_date", "game_id", "team_id", "archetype")
BASE = ("season", "team_abbreviation", "player_id", "player_name")


def team_archetype_summary(frame: pl.DataFrame) -> pl.DataFrame:
    """Distribution and depth for every team-game-archetype.

    `frame` must carry one row per roster player per team game, the
    responsibility columns, `start_rate_5`, `started` and `play_rate_5`.
    """
    columns = responsibility_columns(frame)
    if not columns:
        raise ValueError("frame carries no archetype_<n> columns")
    required = {
        "game_date",
        "game_id",
        "team_id",
        "season",
        "team_abbreviation",
        "player_id",
        "player_name",
        "start_rate_5",
        "started",
        "play_rate_5",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"frame is missing: {sorted(missing)}")
    k = len(columns)

    long = (
        frame.select(
            *BASE,
            "game_date",
            "game_id",
            "team_id",
            "start_rate_5",
            "started",
            "play_rate_5",
            *columns,
        )
        .unpivot(
            index=[
                *BASE,
                "game_date",
                "game_id",
                "team_id",
                "start_rate_5",
                "started",
                "play_rate_5",
            ],
            on=columns,
        )
        .with_columns(
            archetype=pl.col("variable").str.replace(RESPONSIBILITY_PREFIX, "").cast(pl.Int32),
            responsibility=pl.col("value").fill_null(0.0),
            w_expected=pl.col("start_rate_5").fill_null(0.0),
            w_actual=pl.col("started").cast(pl.Float64),
            w_available=pl.col("start_rate_5").fill_null(0.0)
            * pl.col("play_rate_5").fill_null(0.0),
        )
        .drop("variable", "value")
        .with_columns(score=pl.col("w_expected") * pl.col("responsibility"))
        .sort([*KEYS, "player_id"])
    )

    shares = (
        long.group_by(*KEYS, "season", "team_abbreviation")
        .agg(
            pl.len().cast(pl.Int32).alias("roster_size"),
            pl.col("w_expected").sum().alias("expected_starter_weight"),
            pl.when(pl.col("w_expected").sum() > 0)
            .then(
                (pl.col("w_expected") * pl.col("responsibility")).sum() / pl.col("w_expected").sum()
            )
            .otherwise(1.0 / k)
            .alias("expected_share"),
            pl.when(pl.col("w_actual").sum() > 0)
            .then((pl.col("w_actual") * pl.col("responsibility")).sum() / pl.col("w_actual").sum())
            .otherwise(1.0 / k)
            .alias("actual_starter_share"),
            pl.when(pl.col("w_available").sum() > 0)
            .then(
                (pl.col("w_available") * pl.col("responsibility")).sum()
                / pl.col("w_available").sum()
            )
            .otherwise(1.0 / k)
            .alias("available_share"),
        )
        .with_columns(
            expected_dominant=pl.col("expected_share")
            == pl.col("expected_share").max().over(["game_date", "game_id", "team_id"]),
            actual_dominant=pl.col("actual_starter_share")
            == pl.col("actual_starter_share").max().over(["game_date", "game_id", "team_id"]),
        )
    )

    ranked = long.with_columns(
        rank_in_archetype=pl.col("score")
        .rank("ordinal", descending=True)
        .over(["game_date", "game_id", "team_id", "archetype"])
        .cast(pl.Int32)
    )
    top = []
    for rank in (1, 2, 3):
        selected = ranked.filter(pl.col("rank_in_archetype") == rank).select(
            *KEYS,
            pl.col("player_id").alias(f"top_{rank}_player_id"),
            pl.col("player_name").alias(f"top_{rank}_player_name"),
            pl.col("score").alias(f"top_{rank}_score"),
        )
        top.append(selected)

    out = shares
    for selected in top:
        out = out.join(selected, on=list(KEYS), how="left")
    return out.sort([*KEYS])
