"""Tests for the usage head: windows that do not leak, and a budget that holds."""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from team_hierarchy import usage


def _games(usg: list[float], pid: int = 7) -> pl.DataFrame:
    n = len(usg)
    return pl.DataFrame(
        {
            "season": ["2025-26"] * n,
            "player_id": [pid] * n,
            "game_id": list(range(1, n + 1)),
            "game_date": [dt.date(2025, 11, 1) + dt.timedelta(days=2 * i) for i in range(n)],
            "min": [30.0] * n,
            "usg_pct": usg,
            "fga": [10.0] * n,
            "fta": [2.0] * n,
            "tov": [1.0] * n,
            "start_position": ["G"] * n,
        }
    )


def test_events_follow_the_nba_formula():
    out = usage.add_events(_games([0.2]))
    assert out["usage_events"][0] == pytest.approx(10.0 + 0.44 * 2.0 + 1.0)
    assert out["events_per_min"][0] == pytest.approx(out["usage_events"][0] / 30.0)


def test_window_ignores_the_game_it_describes():
    out = usage.add_usage_state(_games([0.10, 0.20, 0.30, 0.40, 0.50]))
    # Game 5 is described by games 1-4. Leaking the current row gives 0.30.
    assert out["usg_pct_last5"][4] == pytest.approx(0.25)


def test_window_matches_a_direct_computation():
    """The as-of join must attach the state computed at that row, not the row before.

    Missing this by one is the bug the sentinel row exists to prevent, and it
    cost 0.006 of MAE on the 2024-25 fold when it was live.
    """
    df = _games([0.10, 0.12, 0.14, 0.16, 0.18, 0.20])
    direct = df.sort("player_id", "game_date").with_columns(
        expected=pl.col("usg_pct")
        .shift(1)
        .rolling_mean(5, min_samples=3)
        .over("player_id")
    )["expected"]
    out = usage.add_usage_state(df)
    assert out["usg_pct_last5"].to_list() == pytest.approx(direct.to_list(), nan_ok=True)


def test_row_after_the_last_game_carries_the_full_state():
    """A serving row has no game of its own; it must inherit the final state."""
    df = _games([0.10, 0.12, 0.14, 0.16, 0.18])
    serving = df.tail(1).with_columns(
        game_id=pl.lit(99, dtype=pl.Int64),
        game_date=pl.lit(dt.date(2026, 1, 1), dtype=pl.Date),
        min=pl.lit(None, dtype=pl.Float64),
        usg_pct=pl.lit(None, dtype=pl.Float64),
    )
    out = usage.add_usage_state(pl.concat([df, serving])).sort("game_id")
    # Mean of all five games, 0.14, not the mean of the first four.
    assert out["usg_pct_last5"][-1] == pytest.approx(0.14)


def test_budget_rescales_a_team_to_the_target():
    frame = pl.DataFrame(
        {
            "game_id": [1, 1, 1],
            "team_id": [10, 10, 10],
            "p_play": [1.0, 1.0, 1.0],
            "minutes_if_plays": [30.0, 20.0, 10.0],
        }
    )
    pred = [0.30, 0.20, 0.10]  # weighted mean 0.21, above the 0.1935 budget
    out = usage.normalise_team_budget(frame, pred)
    weights = [30.0, 20.0, 10.0]
    weighted = sum(w * p for w, p in zip(weights, out, strict=True)) / sum(weights)
    assert weighted == pytest.approx(usage.TEAM_USAGE_BUDGET, abs=1e-9)


def test_budget_leaves_a_team_with_no_minutes_alone():
    frame = pl.DataFrame(
        {
            "game_id": [1, 1],
            "team_id": [10, 10],
            "p_play": [0.0, 0.0],
            "minutes_if_plays": [0.0, 0.0],
        }
    )
    out = usage.normalise_team_budget(frame, [0.10, 0.20])
    assert out.tolist() == pytest.approx([0.10, 0.20])
