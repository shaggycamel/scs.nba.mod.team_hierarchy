"""How similar is a player's style to the teammates whose minutes are vacated?

The archetype responsibilities are probability vectors, so two players can be
compared without collapsing either to a label. The feature this module builds
is the note's allocation term:

    sum over teammates j of
        (1 - p_play_j) * E[minutes_j | plays] * similarity(i, j)

The vector for a player is the latest assignment strictly before the target
game. A player who is out has no assignment for that game, so an exact join
would silently drop exactly the teammates the feature is about.

The starter-weighted variant multiplies the teammate term by `start_rate_5`, the
rolling share of team games he started. It is a soft version of "traditional
starting five": an injured starter fades as he misses games, a promoted backup
rises, and no lineup is hard-coded.
"""

from __future__ import annotations

import polars as pl

RESPONSIBILITY_PREFIX = "archetype_"
KEYS = ("game_id", "team_id", "player_id")
TEAM_KEYS = ("game_date", "game_id", "team_id")
STYLE_FEATURE = "expected_vacated_minutes_similar_style"
STARTER_STYLE_FEATURE = "expected_vacated_minutes_starter_style"
STARTER_WEIGHT = "start_rate_5"


def responsibility_columns(frame: pl.DataFrame) -> list[str]:
    columns = [
        column
        for column in frame.columns
        if column.startswith(RESPONSIBILITY_PREFIX)
        and column.removeprefix(RESPONSIBILITY_PREFIX).isdigit()
    ]
    return sorted(columns, key=lambda column: int(column.removeprefix(RESPONSIBILITY_PREFIX)))


def _normalise(assignments: pl.DataFrame, columns: list[str], keep_season: bool) -> pl.DataFrame:
    """One vector per player-game, scaled to sum to one."""
    total = pl.sum_horizontal(columns)
    keys = ["player_id", "season", "game_date"] if keep_season else ["player_id", "game_date"]
    out = (
        assignments.select(*keys, *columns)
        .drop_nulls([*keys, *columns])
        .with_columns(_total=total)
        .filter(pl.col("_total") > 0)
        .with_columns([(pl.col(column) / pl.col("_total")).alias(column) for column in columns])
        .drop("_total")
    )
    return out.unique(subset=keys, keep="last")


def attach_responsibilities(
    scored: pl.DataFrame,
    assignments: pl.DataFrame,
) -> pl.DataFrame:
    """Attach each player's latest responsibility vector before the game.

    Missing vectors fall back to the uniform distribution, so every roster row
    has a usable representation. The join is on `game_date`, never `game_id`.
    """
    columns = responsibility_columns(assignments)
    if not columns:
        raise ValueError("assignments carry no archetype_<n> columns")
    required = {"game_id", "team_id", "player_id", "game_date"}
    missing = required - set(scored.columns)
    if missing:
        raise ValueError(f"scored frame is missing: {sorted(missing)}")

    uniform = 1.0 / len(columns)
    # Cluster ids are only comparable within one seasonal fit. If both frames
    # carry `season`, keep the as-of join inside it so a 2024-25 fallback cannot
    # be compared with a 2025-26 vector.
    keep_season = "season" in scored.columns and "season" in assignments.columns
    by = ["player_id", "season"] if keep_season else "player_id"
    vectors = _normalise(assignments, columns, keep_season)
    select = [*KEYS, "season", "game_date"] if keep_season else [*KEYS, "game_date"]
    sort_keys = [*by, "game_date"] if keep_season else ["player_id", "game_date"]
    left = scored.select(*select).sort(sort_keys)
    if vectors.height:
        latest = left.join_asof(
            vectors.sort(sort_keys),
            on="game_date",
            by=by,
            strategy="backward",
            allow_exact_matches=False,
        )
    else:
        latest = left.with_columns([pl.lit(None, dtype=pl.Float64).alias(c) for c in columns])
    latest = latest.with_columns([pl.col(c).fill_null(uniform).alias(c) for c in columns]).select(
        *KEYS, *columns
    )
    return scored.join(latest, on=list(KEYS), how="left").with_columns(
        [pl.col(c).fill_null(uniform) for c in columns]
    )


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
    starter_weight: str = STARTER_WEIGHT,
) -> pl.DataFrame:
    """Attach the style-similarity vacancy features.

    `scored` must carry one row per roster player per team game, including
    absent players, with `p_play` and `ewm_min_played_8`. The starter-weighted
    column also needs `starter_weight` (default `start_rate_5`).
    """
    required = {"game_id", "team_id", "player_id", "game_date", "p_play", "ewm_min_played_8"}
    missing = required - set(scored.columns)
    if missing:
        raise ValueError(f"scored frame is missing: {sorted(missing)}")
    if starter_weight not in scored.columns:
        raise ValueError(f"scored frame is missing starter weight: {starter_weight}")

    frame = attach_responsibilities(scored, assignments)
    columns = responsibility_columns(frame)
    left = frame.select(
        *KEYS,
        "p_play",
        "ewm_min_played_8",
        pl.col(starter_weight).fill_null(0.0).alias("_starter"),
        *columns,
    ).with_columns(_weight=(1.0 - pl.col("p_play")) * pl.col("ewm_min_played_8").fill_null(0.0))

    left_side = left.select(*KEYS, "_weight", "_starter", *columns)
    right_side = left.select(
        "game_id",
        "team_id",
        pl.col("player_id").alias("player_id_j"),
        pl.col("_weight").alias("_weight_j"),
        pl.col("_starter").alias("_starter_j"),
        *[pl.col(c).alias(f"{c}_j") for c in columns],
    )
    contributions = (
        left_side.join(right_side, on=["game_id", "team_id"], how="inner")
        .filter(pl.col("player_id") != pl.col("player_id_j"))
        .with_columns(
            _similarity=_similarity_expr(columns, metric),
            _all=pl.col("_weight_j"),
            _starter_weight=pl.col("_weight_j") * pl.col("_starter_j"),
        )
        .with_columns(
            _contribution=pl.col("_similarity") * pl.col("_all"),
            _starter_contribution=pl.col("_similarity") * pl.col("_starter_weight"),
        )
        .group_by(*KEYS)
        .agg(
            pl.col("_contribution").sum().alias(STYLE_FEATURE),
            pl.col("_starter_contribution").sum().alias(STARTER_STYLE_FEATURE),
        )
    )
    return scored.join(contributions, on=list(KEYS), how="left").with_columns(
        pl.col(STYLE_FEATURE).fill_null(0.0),
        pl.col(STARTER_STYLE_FEATURE).fill_null(0.0),
    )


def team_mix(frame: pl.DataFrame) -> pl.DataFrame:
    """Per team-game style distribution, weighted by rolling starter status.

    `frame` must be the output of `attach_responsibilities` and carry
    `start_rate_5` and `p_play`. Roster mix weights by starts; available mix
    additionally weights by the probability of playing.
    """
    columns = responsibility_columns(frame)
    if not columns:
        raise ValueError("frame carries no archetype_<n> columns")
    k = len(columns)
    weight = pl.col(STARTER_WEIGHT).fill_null(0.0)
    available = weight * pl.col("p_play").fill_null(0.0)
    aggs = []
    for i, column in enumerate(columns):
        total = weight.sum()
        available_total = available.sum()
        aggs.append(
            pl.when(total > 0)
            .then((weight * pl.col(column)).sum() / total)
            .otherwise(1.0 / k)
            .alias(f"roster_mix_{i}")
        )
        aggs.append(
            pl.when(available_total > 0)
            .then((available * pl.col(column)).sum() / available_total)
            .otherwise(1.0 / k)
            .alias(f"available_mix_{i}")
        )
    out = frame.group_by(*TEAM_KEYS).agg(*aggs, pl.len().alias("roster_size"))
    roster = [f"roster_mix_{i}" for i in range(k)]
    available_cols = [f"available_mix_{i}" for i in range(k)]
    return out.with_columns(
        roster_dominant=pl.concat_list(roster).list.arg_max().cast(pl.Int32),
        available_dominant=pl.concat_list(available_cols).list.arg_max().cast(pl.Int32),
        roster_entropy=pl.concat_list(roster)
        .list.eval(-(pl.element() * (pl.element() + 1e-12).log()) / pl.lit(k).log())
        .list.sum(),
        available_entropy=pl.concat_list(available_cols)
        .list.eval(-(pl.element() * (pl.element() + 1e-12).log()) / pl.lit(k).log())
        .list.sum(),
    )


def archetype_depth(frame: pl.DataFrame) -> pl.DataFrame:
    """Long player-archetype hierarchy: who currently owns each style.

    `frame` must be the output of `attach_responsibilities`. A player's score
    in an archetype is his rolling starter weight times his responsibility for
    that style; the rank is within `(game_date, game_id, team_id, archetype)`.
    """
    columns = responsibility_columns(frame)
    if not columns:
        raise ValueError("frame carries no archetype_<n> columns")
    keep = ["game_date", "game_id", "team_id", "player_id", "player_name", "p_play"]
    keep = [c for c in keep if c in frame.columns]
    long = (
        frame.select(*keep, STARTER_WEIGHT, "ewm_min_played_8", *columns)
        .unpivot(index=keep + [STARTER_WEIGHT, "ewm_min_played_8"], on=columns)
        .with_columns(
            archetype=pl.col("variable").str.replace(RESPONSIBILITY_PREFIX, "").cast(pl.Int32)
        )
        .drop("variable")
        .rename({"value": "responsibility"})
        .with_columns(
            starter_weight=pl.col(STARTER_WEIGHT).fill_null(0.0),
            responsibility=pl.col("responsibility").fill_null(0.0),
        )
        .with_columns(score=pl.col("starter_weight") * pl.col("responsibility"))
    )
    return long.with_columns(
        rank_in_archetype=pl.col("score")
        .rank("ordinal", descending=True)
        .over(["game_date", "game_id", "team_id", "archetype"])
        .cast(pl.Int32)
    ).sort(["game_date", "game_id", "team_id", "archetype", "rank_in_archetype"])
