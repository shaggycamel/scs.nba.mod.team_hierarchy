from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from team_hierarchy.similarity import STYLE_FEATURE, attach_style_similarity


def assignments() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "player_id": [1, 1, 1, 2],
            "game_date": [
                date(2024, 1, 1),
                date(2024, 1, 5),
                date(2024, 1, 10),
                date(2024, 1, 1),
            ],
            "archetype_0": [1.0, 0.0, 0.5, 1.0],
            "archetype_1": [0.0, 1.0, 0.5, 0.0],
        }
    )


def scored(games: list[tuple[int, date]]) -> pl.DataFrame:
    rows = []
    for game_id, game_date in games:
        rows.extend(
            [
                {
                    "game_id": game_id,
                    "team_id": 10,
                    "player_id": 1,
                    "game_date": game_date,
                    "p_play": 0.5,
                    "ewm_min_played_8": 30.0,
                },
                {
                    "game_id": game_id,
                    "team_id": 10,
                    "player_id": 2,
                    "game_date": game_date,
                    "p_play": 0.5,
                    "ewm_min_played_8": 20.0,
                },
            ]
        )
    return pl.DataFrame(rows)


def feature(frame: pl.DataFrame, game_id: int, player_id: int) -> float:
    row = frame.filter((pl.col("game_id") == game_id) & (pl.col("player_id") == player_id))[
        STYLE_FEATURE
    ]
    return float(row.item())


def test_vector_is_the_latest_assignment_strictly_before_the_game():
    games = [
        (1, date(2024, 1, 5)),  # uses 1/1: [1, 0]
        (2, date(2024, 1, 6)),  # uses 1/5: [0, 1]
        (3, date(2024, 1, 11)),  # uses 1/10: [0.5, 0.5]
    ]
    out = attach_style_similarity(scored(games), assignments())

    # player 1 against player 2's [1, 0], weight 10.
    assert feature(out, 1, 1) == pytest.approx(10.0)
    assert feature(out, 2, 1) == pytest.approx(0.0)
    assert feature(out, 3, 1) == pytest.approx(10.0 * (0.5**0.5))


def test_cosine_matches_the_same_pairing():
    out = attach_style_similarity(scored([(3, date(2024, 1, 11))]), assignments(), "cosine")
    # [0.5, 0.5] against [1, 0]: dot 0.5 / (sqrt(0.5) * 1)
    assert feature(out, 3, 1) == pytest.approx(10.0 * (0.5**0.5))


def test_missing_vector_falls_back_to_uniform():
    only_one = assignments().filter(pl.col("player_id") == 1)
    out = attach_style_similarity(scored([(1, date(2024, 1, 5))]), only_one)
    # player 1 [1, 0] against uniform [0.5, 0.5]
    assert feature(out, 1, 1) == pytest.approx(10.0 * (0.5**0.5))


def test_a_player_with_no_teammates_gets_zero():
    one_player = scored([(1, date(2024, 1, 5))]).filter(pl.col("player_id") == 1)
    out = attach_style_similarity(one_player, assignments())
    assert feature(out, 1, 1) == 0.0


def test_opponents_do_not_contribute():
    frame = scored([(1, date(2024, 1, 5))]).with_columns(
        pl.when(pl.col("player_id") == 2)
        .then(pl.lit(20))
        .otherwise(pl.col("team_id"))
        .alias("team_id")
    )
    out = attach_style_similarity(frame, assignments())
    assert feature(out, 1, 1) == 0.0
