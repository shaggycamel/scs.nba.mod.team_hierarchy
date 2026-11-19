"""Load the player-game spine: one row per (game, team, player) on the roster.

The NBA box score already carries a row for every player who dressed *or* was
listed and did not play, so the spine doubles as a roster record: a DNP row is
evidence the player was with the team that night, which is exactly what the
availability and absorption layers need.
"""

from __future__ import annotations

import polars as pl

from . import source
from .config import SEASON_TYPES

# Absence reasons, normalised from the free-text `comment` field. Only the
# coach/injury split is load-bearing for the hierarchy: a coach's decision is a
# demotion signal, an injury is not.
# A total order over panel rows, shared by every layer. All four columns are
# needed: a player traded between two teams that then play each other appears
# twice for that one game -- Kobe Bufkin, ATL to PHI, who met PHI on 2025-03-10
# -- so (player, date, game) alone leaves ties. Polars' sort is not stable, so a
# tie means row order, and therefore every `.over("player_id")` window and every
# `rank("ordinal")` downstream, changes between runs. 43 such pairs exist in the
# panel and they were enough to make the pipeline non-reproducible.
ROW_KEY = ("player_id", "game_date", "game_id", "team_id")


def canonical_sort(df: pl.DataFrame, key: tuple[str, ...] = ROW_KEY) -> pl.DataFrame:
    """Sort into a reproducible total order, by whichever key columns exist."""
    return df.sort([c for c in key if c in df.columns])


STATUS_PLAYED = "PLAYED"
STATUS_COACH = "DNP_COACH"
STATUS_INJURY = "DNP_INJURY"
STATUS_SUSPENSION = "DNP_SUSPENSION"
STATUS_REST = "DNP_REST"
STATUS_AWAY = "DNP_AWAY"
STATUS_OTHER = "DNP_OTHER"

_INJURY_WORDS = (
    "INJUR|ILLNESS|ILL|SORE|SPRAIN|STRAIN|SURGER|SURGERY|REHAB|RECONDITION"
    "|CONCUSSION|PROTOCOL|FRACTUR|TORN|TEAR|TENDIN|BRUISE|CONTUSION|DISLOCAT"
    "|MICRODISCECTOMY|ACHILLES|HAMSTRING|GROIN|ANKLE|KNEE|SHOULDER|WRIST"
    "|THUMB|FINGER|BACK|HIP|CALF|QUAD|FOOT|TOE|HAND|ELBOW|NECK|RIB|ADDUCTOR"
)
_AWAY_WORDS = "G LEAGUE|GLEAGUE|ASSIGN|NOT WITH TEAM|PERSONAL|TRADE|RETURN TO"


def _absence_status() -> pl.Expr:
    """Classify why a player did not play, from the box score comment."""
    norm = pl.col("comment").fill_null("").str.to_uppercase().str.replace_all(r"[_\-]", " ")
    return (
        pl.when(pl.col("played"))
        .then(pl.lit(STATUS_PLAYED))
        # Keyword match first: it is more reliable than the DNP/DND/NWT prefix,
        # which is inconsistent across seasons.
        .when(norm.str.contains("COACH"))
        .then(pl.lit(STATUS_COACH))
        .when(norm.str.contains(_INJURY_WORDS))
        .then(pl.lit(STATUS_INJURY))
        .when(norm.str.contains("SUSPEN"))
        .then(pl.lit(STATUS_SUSPENSION))
        .when(norm.str.contains("REST"))
        .then(pl.lit(STATUS_REST))
        .when(norm.str.contains(_AWAY_WORDS))
        .then(pl.lit(STATUS_AWAY))
        # Fall back on the prefix: DND means "did not dress", which is an
        # injury far more often than not.
        .when(norm.str.starts_with("DND"))
        .then(pl.lit(STATUS_INJURY))
        .when(norm.str.starts_with("NWT"))
        .then(pl.lit(STATUS_AWAY))
        .otherwise(pl.lit(STATUS_OTHER))
    )


def _safe_div(num: str, den: str) -> pl.Expr:
    """Divide, yielding null rather than inf/NaN when the denominator is 0."""
    return pl.when(pl.col(den) > 0).then(pl.col(num) / pl.col(den)).otherwise(None)


def _per36(stat: str) -> pl.Expr:
    return pl.when(pl.col("min") > 0).then(pl.col(stat) / pl.col("min") * 36).otherwise(None)


def load_schedule() -> pl.DataFrame:
    """One row per game: date, season and season type.

    The view holds one row per *team* per game; the three columns we keep are
    identical across a game's two rows, which is asserted here rather than
    assumed.
    """
    sched = source.read_schedule().select(
        pl.col("game_id").cast(pl.Int64), "game_date", "season", "season_type"
    )
    per_game = sched.group_by("game_id").agg(
        pl.col("game_date").n_unique().alias("n_date"),
        pl.col("season").n_unique().alias("n_season"),
        pl.col("season_type").n_unique().alias("n_type"),
    )
    conflicting = per_game.filter(
        (pl.col("n_date") > 1) | (pl.col("n_season") > 1) | (pl.col("n_type") > 1)
    )
    if conflicting.height:
        raise ValueError(
            f"{conflicting.height} game_ids disagree on date/season/season_type "
            "across their two schedule rows"
        )
    return sched.unique(subset=["game_id"], keep="first")


def load_team_roster(season: str | None = None) -> pl.DataFrame:
    """The dated season roster, used to correct serving membership."""
    return (
        source.read_team_roster(season)
        .select(
            "season",
            pl.col("team_id").cast(pl.Int64),
            "team_slug",
            pl.col("player_id").cast(pl.Int64),
            "player_name",
            "entry_date",
            "exit_date",
        )
        .with_columns(pl.col("team_slug").alias("team_abbreviation"))
    )


def load_fixtures(
    season_types: tuple[str, ...] = SEASON_TYPES,
) -> pl.DataFrame:
    """One row per team per scheduled game: who they play, where, and when.

    The panel is built from box scores, which only exist once a game has been
    played, so it cannot say whether a team has a fixture on a given date. That
    makes this the only source that can stop a daily run inventing a game for a
    team that is not playing.
    """
    teams = source.read_teams().select(pl.col("team_id").cast(pl.Int64), "team_slug")
    sched = source.read_schedule()
    if season_types:
        sched = sched.filter(pl.col("season_type").is_in(season_types))
    return (
        sched.join(teams, left_on="team", right_on="team_slug", how="inner")
        .select(
            "team_id",
            pl.col("game_id").cast(pl.Int64),
            "game_date",
            "season",
            pl.col("opponent"),
            pl.col("home"),
            pl.col("matchup"),
        )
        .unique(subset=["team_id", "game_id"], keep="first")
    )


def load_player_games(
    season_types: tuple[str, ...] = SEASON_TYPES,
) -> pl.DataFrame:
    """The player-game spine, sorted for windowed feature computation.

    Sorted by (player_id, game_date, game_id) so that `.over("player_id")`
    windows see each player's games in chronological order.
    """
    pg = source.read_player_games()
    if season_types:
        pg = pg.filter(pl.col("season_type").is_in(season_types))
    # The public view is roster-complete: it emits a row for every roster player
    # on every team game. The hierarchy's own panel reconstructs the missing
    # rows, so it starts from the box-score spine (`in_box_score`) and keeps the
    # view's extra rows out of the training frame.
    pg = pg.filter(pl.col("in_box_score"))

    pg = pg.with_columns(
        pl.col("game_id").cast(pl.Int64),
        pl.col("team_id").cast(pl.Int64),
        pl.col("player_id").cast(pl.Int64),
        played=pl.col("min").fill_null(0) > 0,
        started=pl.col("start_position").is_in(["G", "F", "C"]).fill_null(False),
    ).with_columns(
        status=_absence_status(),
        fg3_rate=_safe_div("fg3_a", "fga"),
        ftr=_safe_div("fta", "fga"),
        fga36=_per36("fga"),
        ast36=_per36("ast"),
        reb36=_per36("reb"),
        blk36=_per36("blk"),
        stl36=_per36("stl"),
        tov36=_per36("tov"),
    )
    # Rate stats are meaningless on a DNP row; null them so the played-only
    # EWMAs in state.py skip the row instead of averaging in a zero.
    rate_cols = [
        "usg_pct",
        "ast_pct",
        "reb_pct",
        "oreb_pct",
        "dreb_pct",
        "ts_pct",
    ]
    pg = pg.with_columns(
        [pl.when(pl.col("played")).then(pl.col(c)).otherwise(None).alias(c) for c in rate_cols]
    )
    return canonical_sort(pg)
