"""How similar is a player's style to the teammates whose minutes are vacated?

The archetype responsibilities are probability vectors, so two players can be
compared without collapsing either to a label. The feature this module builds
is the note's allocation term:

    sum over teammates j of
        (1 - p_play_j) * E[minutes_j | plays] * similarity(i, j)

The vector for a player is the latest assignment strictly before the target
game. A player who is out has no assignment for that game, so an exact join
would silently drop exactly the teammates the feature is about.
"""

from __future__ import annotations

import polars as pl

RESPONSIBILITY_PREFIX = "archetype_"
KEYS = ("game_id", "team_id", "player_id")
STYLE_FEATURE = "expected_vacated_minutes_similar_style"


def responsibility_columns(frame: pl.DataFrame) -> list[str]:
    columns = [
        column
        for column in frame.columns
        if column.startswith(RESPONSIBILITY_PREFIX)
        and column.removeprefix(RESPONSIBILITY_PREFIX).isdigit()
    ]
    return sorted(columns, key=lambda column: int(column.removeprefix(RESPONSIBILITY_PREFIX)))


def _normalise(assignments: pl.DataFrame, columns: list[str]) -> pl.DataFrame:
    """One vector per player-game, scaled to sum to one."""
    total = pl.sum_horizontal(columns)
    out = (
        assignments.select("player_id", "game_date", *columns)
        .drop_nulls(["player_id", "game_date", *columns])
        .with_columns(_total=total)
        .filter(pl.col("_total") > 0)
        .with_columns([(pl.col(column) / pl.col("_total")).alias(column) for column in columns])
        .drop("_total")
    )
    return out.unique(subset=["player_id", "game_date"], keep="last")


def _similarity_expr(columns: list[str], metric: str) -> pl.Expr:
    if metric == "cosine":
        dot = pl.sum_horizontal(pl.col(c) * pl.col(f"{c}_j") for c in columns)
        norm_i = pl.sum_horizontal(pl.col(c) ** 2 for c in columns).sqrt()
        norm_j = pl.sum_horizontal(pl.col(f"{c}_j") ** 2 for c in columns).sqrt()
        return (dot / (norm_i * norm_j)).clip(0.0, 1.0).fill_null(0.0)
    if metric == "bhattacharyya":
        return (
            pl.sum_horizontal((pl.col(c) * pl.col(f"{c}_j")).sqrt() for c in columns)
            .clip(0.0, 1.0)
            .fill_null(0.0)
        )
    raise ValueError(f"unknown similarity metric: {metric!r}")


def attach_style_similarity(
    scored: pl.DataFrame,
    assignments: pl.DataFrame,
    metric: str = "bhattacharyya",
) -> pl.DataFrame:
    """Attach the expected vacated minutes from similarly styled teammates.

    `scored` must carry one row per roster player per team game, including
    absent players, with `p_play` and `ewm_min_played_8`. `assignments` is the
    responsibility table with `player_id`, `game_date` and `archetype_<n>`
    columns. Vectors are joined as of the game date, never on `game_id`.
    """
    columns = responsibility_columns(assignments)
    if not columns:
        raise ValueError("assignments carry no archetype_<n> columns")
    required = {"game_id", "team_id", "player_id", "game_date", "p_play", "ewm_min_played_8"}
    missing = required - set(scored.columns)
    if missing:
        raise ValueError(f"scored frame is missing: {sorted(missing)}")

    uniform = 1.0 / len(columns)
    vectors = _normalise(assignments, columns)

    left = scored.select(*KEYS, "game_date", "p_play", "ewm_min_played_8").sort(
        ["player_id", "game_date"]
    )
    if vectors.height:
        latest = left.join_asof(
            vectors.sort(["player_id", "game_date"]),
            on="game_date",
            by="player_id",
            strategy="backward",
            allow_exact_matches=False,
        )
    else:
        latest = left.with_columns([pl.lit(None, dtype=pl.Float64).alias(c) for c in columns])
    latest = latest.with_columns(
        [pl.col(c).fill_null(uniform).alias(c) for c in columns]
    ).with_columns(_weight=(1.0 - pl.col("p_play")) * pl.col("ewm_min_played_8").fill_null(0.0))

    left_side = latest.select(*KEYS, "_weight", *columns)
    right_side = latest.select(
        "game_id",
        "team_id",
        pl.col("player_id").alias("player_id_j"),
        pl.col("_weight").alias("_weight_j"),
        *[pl.col(c).alias(f"{c}_j") for c in columns],
    )
    contributions = (
        left_side.join(right_side, on=["game_id", "team_id"], how="inner")
        .filter(pl.col("player_id") != pl.col("player_id_j"))
        .with_columns(_contribution=_similarity_expr(columns, metric) * pl.col("_weight_j"))
        .group_by(*KEYS)
        .agg(pl.col("_contribution").sum().alias(STYLE_FEATURE))
    )
    return scored.join(contributions, on=list(KEYS), how="left").with_columns(
        pl.col(STYLE_FEATURE).fill_null(0.0)
    )
