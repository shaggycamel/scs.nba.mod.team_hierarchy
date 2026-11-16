"""The report-vs-injury precedence for availability.

The rule: a report for the game date wins; the injury-duration curve fills only
report-less dates; otherwise the hierarchy's own state-only probability stands.
"""

from __future__ import annotations

from datetime import date

import polars as pl

from team_hierarchy.config import SERVING_GAME_ID
from team_hierarchy.pipeline import _apply_availability


def _serving() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "player_id": [1, 2, 3, 4],
            "game_date": [date(2026, 11, 16)] * 4,
            "game_id": [SERVING_GAME_ID] * 3 + [123],
            "report_status": ["Out", None, None, None],
            "p_play": [0.9, 0.85, 0.8, 0.7],
        }
    )


def _availability() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "prediction_date": [date(2026, 11, 15)] * 3,
            "player_id": [1, 2, 4],
            "game_date": [date(2026, 11, 16)] * 3,
            "p_available": [0.01, 0.05, 0.02],
        }
    )


def test_report_wins_and_injury_fills_only_the_gap() -> None:
    out = _apply_availability(_serving(), _availability())

    assert out["p_play"].to_list() == [0.9, 0.05, 0.8, 0.7]
    assert out["p_play_source"].to_list() == ["report", "injury", "state", "state"]
    assert out["p_play_injury"].to_list() == [0.01, 0.05, None, None]


def test_without_an_injury_frame_the_state_probability_stands() -> None:
    out = _apply_availability(_serving(), None)

    assert out["p_play"].to_list() == [0.9, 0.85, 0.8, 0.7]
    assert out["p_play_source"].to_list() == ["report", "state", "state", "state"]
    # The column exists either way, so the published schema is stable.
    assert out["p_play_injury"].null_count() == 4


def test_the_latest_prediction_wins_when_two_spells_overlap() -> None:
    availability = pl.concat(
        [
            _availability().filter(pl.col("player_id") == 2),
            _availability()
            .filter(pl.col("player_id") == 2)
            .with_columns(
                pl.lit(date(2026, 11, 16)).alias("prediction_date"),
                pl.lit(0.42).alias("p_available"),
            ),
        ]
    )

    out = _apply_availability(_serving(), availability)

    assert out.filter(pl.col("player_id") == 2)["p_play"].item() == 0.42


def test_a_published_report_blocks_the_injury_override() -> None:
    # The report exists for the date, so an unlisted player is the report's
    # statement that he is available -- not a gap for the curve to fill.
    out = _apply_availability(_serving(), _availability(), allow_injury=False)

    assert out["p_play"].to_list() == [0.9, 0.85, 0.8, 0.7]
    assert out["p_play_source"].to_list() == ["report", "report", "report", "state"]
    # The curve is still exposed as context.
    assert out["p_play_injury"].to_list() == [0.01, 0.05, None, None]
