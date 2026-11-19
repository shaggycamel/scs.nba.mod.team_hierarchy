"""Read the hierarchy inputs from the public database views.

The database is the only source. Frames are cached for the life of the process
because the pipeline asks for the same schedule, panel and report several times;
Polars frames are immutable, so sharing them is safe.
"""

from __future__ import annotations

import os
from functools import lru_cache

import polars as pl

DEFAULT_DB_CON = "jetson-read"

_DB = None


def db(db_con: str | None = None):
    """The shared read connection, created on first use."""
    global _DB
    if _DB is None or db_con is not None:
        from scs_hub import SportsHub

        section = db_con or os.environ.get("TEAM_HIERARCHY_DB_CON", DEFAULT_DB_CON)
        _DB = SportsHub(db_con=section).db
    return _DB


@lru_cache(maxsize=1)
def read_schedule() -> pl.DataFrame:
    return db().read(
        """
        SELECT
            game_id, game_date, season, season_type,
            team, opponent, home, matchup, team_winner
        FROM nba.league_game_schedule_vw
        """
    )


@lru_cache(maxsize=8)
def read_team_roster(season: str | None = None) -> pl.DataFrame:
    query = """
        SELECT
            season,
            team_id,
            team_slug,
            player_id,
            player_name,
            entry_date,
            exit_date
        FROM nba.team_roster_vw
    """
    if season is not None:
        query += f" WHERE season = '{season}'"
    return db().read(query)


@lru_cache(maxsize=1)
def read_player_games() -> pl.DataFrame:
    """The box-score spine, with the columns every layer reads."""
    return db().read(
        """
        SELECT
            game_id,
            game_date,
            season,
            season_type,
            team AS team_abbreviation,
            team_id,
            player_id,
            player_name,
            start_position,
            in_box_score,
            inj_reason AS comment,
            min,
            usg_pct,
            ast_pct,
            reb_pct,
            oreb_pct,
            dreb_pct,
            ts_pct,
            fga,
            fg3_a,
            fta,
            ast,
            reb,
            blk,
            stl,
            tov,
            poss
        FROM nba.player_box_score_vw
        """
    )


@lru_cache(maxsize=1)
def read_injuries() -> pl.DataFrame:
    return db().read(
        """
        SELECT
            season,
            season_type,
            game_date,
            game_id,
            matchup,
            team,
            team_slug,
            player_name,
            nba_id,
            status,
            reason,
            team_id
        FROM nba.injuries_vw
        """
    )


@lru_cache(maxsize=1)
def read_teams() -> pl.DataFrame:
    return db().read("SELECT team_id, team_slug FROM nba.teams_vw")


@lru_cache(maxsize=1)
def read_player_info() -> pl.DataFrame:
    return db().read(
        """
        SELECT player_id, height_cm, weight_kg
        FROM nba.player_info_vw
        """
    )


@lru_cache(maxsize=1)
def read_player_map() -> pl.DataFrame:
    return db().read(
        """
        SELECT nba_name, conformed_name, nba_id
        FROM util.player_id_map_vw
        """
    )
