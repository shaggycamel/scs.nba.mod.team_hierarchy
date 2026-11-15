"""The usage head: next-game usage rate and volume, with the team budget enforced.

Layer 4's original usage regression is the one head in this bundle that never
cleared its own bar. Its evaluation put it at R2 0.3421 against 0.3310 for a
trailing mean, with identical mean absolute error to three decimals, and the
module docstring in `absorption` says so. This replaces it.

Three things make the difference, and none of them is a new algorithm:

* **Trailing state at several horizons.** Last-5 and last-20 means, a
  season-to-date mean, and the trend between the short and long windows. A
  single EWMA lags a role change; the pair does not.
* **Usage events as a second target.** `usg_pct` is a share and its error is
  mostly irreducible; `FGA + 0.44 FTA + TOV` per minute is the quantity that
  multiplies into a projection.
* **The team budget.** Minutes-weighted team usage is 0.1935 with a standard
  deviation of 0.003 across team-games, because a team spends one usage budget
  per possession. Predicting players independently ignores that, so their errors
  do not cancel. Rescaling each team-game back to the budget was worth a full
  point of R2 in the research repo.

The blend is deliberate. Ridge and LightGBM make different mistakes -- the
linear model cannot see interactions, the trees cannot extrapolate -- and their
average beat both on all three evaluation folds.
"""

from __future__ import annotations

import numpy as np
import polars as pl

FT_FACTOR = 0.44
TEAM_USAGE_BUDGET = 0.1935
BLEND_WEIGHT = 0.5
RIDGE_ALPHA = 3.0

# The horizon set. Short windows catch a role change, long windows carry the
# level, and the trend between them is the difference the eye would use.
WINDOWS = (5, 10, 20)

# Features computed here rather than by `state.py`. Everything else the head
# uses already exists on the layer-4 frame.
TRAILING_FEATURES = (
    "usg_pct_last5",
    "usg_pct_last10",
    "usg_pct_last20",
    "usg_pct_season",
    "min_last5",
    "min_last10",
    "events_per_min_last10",
    "usage_events_last10",
    "usage_events_season",
    "start_rate_last10",
    "usg_trend",
    "min_trend",
)

RATE_TARGET = "usg_pct"
EVENTS_TARGET = "events_per_min"


def add_events(df: pl.DataFrame) -> pl.DataFrame:
    """The numerator of the usage formula, per game and per minute."""
    out = df.with_columns(
        usage_events=pl.col("fga") + FT_FACTOR * pl.col("fta") + pl.col("tov")
    )
    return out.with_columns(
        events_per_min=pl.when(pl.col("min") > 0)
        .then(pl.col("usage_events") / pl.col("min"))
        .otherwise(None)
    )


def add_usage_state(df: pl.DataFrame) -> pl.DataFrame:
    """Trailing usage state as of the previous game each row describes.

    Computed on the played subframe and attached with an exact-or-previous
    as-of join, so a DNP never advances a window and never enters one. That
    distinction is not cosmetic: the panel is mostly DNP rows, and building the
    windows on the full frame moved R2 from 0.32 to 0.11 when it was measured.

    One sentinel row per player is appended a day after his last game. Without
    it the join is off by one: the state a player carries into game j is stored
    on row j, and a serving row after his final game has no row to match. It
    matters -- the off-by-one cost 0.006 of MAE when it was measured.
    """
    if "usage_events" not in df.columns:
        df = add_events(df)

    played = df.filter(pl.col("min") > 0).sort("player_id", "game_date", "game_id")
    played = played.with_columns(
        started=pl.col("start_position").is_in(["G", "F", "C"]).cast(pl.Float64)
    )

    # The sentinel carries no statistics: it exists so the state after the last
    # played game has a date to live on. Built from the player's last row so the
    # schema matches exactly.
    sentinel = (
        played.group_by("player_id", maintain_order=True)
        .agg(pl.all().sort_by("game_date").last())
        .with_columns(
            game_date=pl.col("game_date") + pl.duration(days=1),
            usg_pct=pl.lit(None, dtype=pl.Float64),
            min=pl.lit(None, dtype=pl.Float64),
            usage_events=pl.lit(None, dtype=pl.Float64),
            events_per_min=pl.lit(None, dtype=pl.Float64),
            started=pl.lit(None, dtype=pl.Float64),
            season=pl.lit(None, dtype=pl.String),
        )
        .select(played.columns)
    )
    work = pl.concat([played, sentinel], how="vertical").sort("player_id", "game_date")

    exprs: list[pl.Expr] = []
    for col in ("usg_pct", "min", "usage_events", "events_per_min"):
        prior = pl.col(col).shift(1)
        for w in WINDOWS:
            exprs.append(
                prior.rolling_mean(w, min_samples=3).over("player_id").alias(f"{col}_last{w}")
            )
        exprs.append(
            (
                prior.cum_sum().over(["player_id", "season"])
                / prior.cum_count().over(["player_id", "season"])
            ).alias(f"{col}_season")
        )
    exprs += [
        pl.col("started")
        .shift(1)
        .rolling_mean(10, min_samples=3)
        .over("player_id")
        .alias("start_rate_last10"),
        pl.col("usg_pct").shift(1).rolling_mean(5, min_samples=3).over("player_id").alias("_u5"),
        pl.col("min").shift(1).rolling_mean(5, min_samples=3).over("player_id").alias("_m5"),
    ]
    work = work.with_columns(exprs).with_columns(
        usg_trend=pl.col("_u5") - pl.col("usg_pct_last20"),
        min_trend=pl.col("_m5") - pl.col("min_last20"),
    )

    features = work.select("player_id", "game_date", *TRAILING_FEATURES)
    # A player appears twice on one date only across a trade; the panel already
    # keeps the row he played, so the keys are unique in practice.
    features = features.unique(subset=["player_id", "game_date"], keep="last").sort(
        "player_id", "game_date"
    )
    return df.sort("player_id", "game_date").join_asof(
        features,
        on="game_date",
        by="player_id",
        strategy="backward",
        allow_exact_matches=True,
    )


def _design(frame: pl.DataFrame, features: list[str]) -> np.ndarray:
    return frame.select(features).to_numpy()


def fit(train: pl.DataFrame, features: list[str]) -> dict:
    """Fit both targets on the same feature list. Returns a plain dict."""
    import lightgbm as lgb
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    x = _design(train, features)
    head: dict = {"features": list(features)}
    for name, target in (("rate", RATE_TARGET), ("events", EVENTS_TARGET)):
        y = train[target].to_numpy()
        head[f"{name}_ridge"] = make_pipeline(
            SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=RIDGE_ALPHA)
        ).fit(x, y)
        head[f"{name}_gbm"] = lgb.LGBMRegressor(
            n_estimators=400,
            learning_rate=0.03,
            num_leaves=31,
            min_child_samples=50,
            subsample=0.8,
            subsample_freq=1,
            colsample_bytree=0.8,
            random_state=0,
            verbose=-1,
        ).fit(x, y)
    return head


def predict(head: dict, frame: pl.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Blended rate and events-per-minute predictions."""
    x = _design(frame, head["features"])

    def blend(name: str) -> np.ndarray:
        return BLEND_WEIGHT * head[f"{name}_ridge"].predict(
            x
        ) + (1 - BLEND_WEIGHT) * head[f"{name}_gbm"].predict(x)

    return blend("rate"), blend("events")


def normalise_team_budget(
    frame: pl.DataFrame, pred: np.ndarray, minutes_col: str = "minutes_if_plays"
) -> np.ndarray:
    """Rescale so a team-game's minutes-weighted usage meets the budget.

    Weights are expected minutes on the floor. A team-game with no expected
    minutes is left alone rather than divided by zero.
    """
    scored = frame.with_columns(pred=pl.Series(pred, dtype=pl.Float64))
    weight = (pl.col("p_play") * pl.col(minutes_col)).clip(lower_bound=0.0)
    totals = (
        scored.with_columns(weight=weight)
        .group_by(["game_id", "team_id"])
        .agg(
            (pl.col("weight") * pl.col("pred")).sum().alias("_num"),
            pl.col("weight").sum().alias("_den"),
        )
    )
    scored = scored.join(totals, on=["game_id", "team_id"], how="left").with_columns(
        scale=pl.when((pl.col("_den") > 0) & (pl.col("_num") > 0))
        .then((TEAM_USAGE_BUDGET * pl.col("_den")) / pl.col("_num"))
        .otherwise(1.0)
    )
    return (scored["pred"] * scored["scale"]).clip(lower_bound=0.0, upper_bound=0.6).to_numpy()
