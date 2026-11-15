"""Evaluate the usage head: rate, events, and what the budget adds.

Walk-forward: each season is scored by models fitted only on seasons before it,
and the minutes model is refitted the same way because the head's event target
and the budget weights both need a minutes prediction that was never in its own
training data.

Reported against the three things that could make it unnecessary: a trailing
mean, layer 4's original usage regression, and the same head with the budget
correction switched off.
"""

from __future__ import annotations

import polars as pl

from team_hierarchy import usage
from team_hierarchy.absorption import (
    ABSORPTION_FEATURES,
    MINUTES_TARGET,
    OWN_FEATURES,
    USAGE_TARGET,
    fit_regressor,
    predict,
    regression_score,
)
from team_hierarchy.pipeline import layer4_frame

TEST_SEASONS = ["2024-25", "2025-26", "2026-27"]
MIN_MINUTES = 5.0


def report(title: str, rows: list[dict]) -> pl.DataFrame:
    res = pl.DataFrame(rows)
    print(f"\n=== {title} ===")
    print(
        res.select(
            "season",
            "model",
            pl.col("mae").round(4),
            pl.col("rmse").round(4),
            pl.col("r2").round(4),
        ).to_pandas().to_string(index=False)
    )
    return res


def main() -> None:
    data = layer4_frame()
    data = usage.add_usage_state(data)
    features = list(OWN_FEATURES + ABSORPTION_FEATURES)
    usage_features = features + list(usage.TRAILING_FEATURES)

    rate_rows: list[dict] = []
    event_rows: list[dict] = []
    for season in TEST_SEASONS:
        train = data.filter((pl.col("season") < season) & pl.col("played"))
        test = data.filter((pl.col("season") == season) & (pl.col("min") >= MIN_MINUTES))
        if not train.height or not test.height:
            continue

        minutes_model = fit_regressor(train, features, MINUTES_TARGET)
        legacy = fit_regressor(train, features, USAGE_TARGET)
        head = usage.fit(train, usage_features)

        scored = predict(minutes_model, test, features, "minutes_if_plays")
        scored = scored.with_columns(
            legacy_usage=predict(legacy, scored, features, "legacy_usage")["legacy_usage"],
            trailing=pl.col("usg_pct_last20").fill_null(pl.col("usg_pct_season")),
        )
        rate, events = usage.predict(head, scored)
        scored = scored.with_columns(pred=pl.Series(rate, dtype=pl.Float64))
        normalised = usage.normalise_team_budget(scored, rate)
        scored = scored.with_columns(pred_budget=pl.Series(normalised))
        scored = scored.with_columns(
            events_model=pl.Series(events).clip(0.0) * pl.col("minutes_if_plays"),
        )
        # Score every model on the rows the trailing baselines can speak to, so
        # the comparison is like-for-like rather than flattering the models with
        # the cold starts only they can handle.
        scored = scored.filter(
            pl.col("trailing").is_not_null() & pl.col("usage_events_last10").is_not_null()
        )

        actual = scored["usg_pct"].to_numpy()
        for name, col in (
            ("trailing mean", "trailing"),
            ("layer 4 usage", "legacy_usage"),
            ("usage head", "pred"),
            ("usage head + budget", "pred_budget"),
        ):
            s = regression_score(scored[col].to_numpy(), actual)
            rate_rows.append({"season": season, "model": name, **s})

        actual_events = (
            scored["fga"] + usage.FT_FACTOR * scored["fta"] + scored["tov"]
        ).to_numpy()
        for name, col in (
            ("trailing events", "usage_events_last10"),
            ("usage head events", "events_model"),
        ):
            s = regression_score(scored[col].to_numpy(), actual_events)
            event_rows.append({"season": season, "model": name, **s})

    report("usage rate, 5+ minutes", rate_rows)
    report("usage events, 5+ minutes", event_rows)


if __name__ == "__main__":
    main()
