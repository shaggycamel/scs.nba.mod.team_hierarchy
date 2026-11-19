from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from team_hierarchy.team_archetype import team_archetype_summary


def frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "season": ["2025-26", "2025-26"],
            "team_abbreviation": ["BOS", "BOS"],
            "player_id": [1, 2],
            "player_name": ["Starter", "Backup"],
            "game_date": [date(2026, 1, 1), date(2026, 1, 1)],
            "game_id": [10, 10],
            "team_id": [2, 2],
            "start_rate_5": [1.0, 1.0],
            "started": [True, False],
            "play_rate_5": [1.0, 1.0],
            "archetype_0": [1.0, 0.0],
            "archetype_1": [0.0, 1.0],
        }
    )


def test_shares_sum_to_one_per_team_game():
    out = team_archetype_summary(frame())
    expected = out.group_by("game_id", "team_id").agg(
        pl.col("expected_share").sum(),
        pl.col("actual_starter_share").sum(),
        pl.col("available_share").sum(),
    )
    assert expected["expected_share"].item() == pytest.approx(1.0)
    assert expected["actual_starter_share"].item() == pytest.approx(1.0)
    assert expected["available_share"].item() == pytest.approx(1.0)


def test_hierarchy_follows_the_style_mass():
    out = team_archetype_summary(frame()).sort("archetype")
    creator = out.filter(pl.col("archetype") == 0)
    connector = out.filter(pl.col("archetype") == 1)
    assert creator["top_1_player_id"].item() == 1
    assert connector["top_1_player_id"].item() == 2


def test_actual_starter_share_is_separate_from_the_expectation():
    out = team_archetype_summary(frame()).sort("archetype")
    creator = out.filter(pl.col("archetype") == 0)
    connector = out.filter(pl.col("archetype") == 1)
    assert creator["expected_share"].item() == pytest.approx(0.5)
    assert creator["actual_starter_share"].item() == pytest.approx(1.0)
    assert connector["actual_starter_share"].item() == pytest.approx(0.0)
