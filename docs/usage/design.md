# Next-game usage: the design and the gate

## Status

Done: baselines, fold panels, feature ablations for history, hierarchy,
context, standings and four archetype formulations, plus the team-budget
correction, the Ridge/LightGBM blend, and the usage-events target.

Result: 3.6-6.8% MAE off the best trailing mean on the three folds, R²
0.47-0.48. Kept: hierarchy state, budget normalisation, the blend. Rejected:
archetypes (own, opponent, team-mate, interaction), standings, context,
shrinkage, extra trees. Not built: the published `mod.usage_vw` and the
scheduled job.

## Target

`usg_pct` for a player's next game, conditional on him taking the floor, from
information known before tip-off. Second target, for projections: usage events
(`FGA + 0.44 FTA + TOV`), and the marginal version once `p_play` is multiplied
in.

The rate target is hard. Three attempts on this problem landed at R² 0.33-0.42
with a trailing mean and gained only a few percent from a fitted model. Minutes
and availability carry far more predictable variance, so any model that only
scores the rate is measured on the least promising half of the problem.

## Folds

Expanding-window seasons, nothing shuffled. Features are prior-games-only and
built on the played subframe, which matters more than it sounds: the box-score
view is about half DNP rows, and building windows on the full frame moves R²
from 0.32 to 0.11 on the same rows.

Decision folds are 2024-25 and 2025-26. 2026-27 is scored but is only 25 days
old, so it is a sanity check rather than evidence.

## Feature blocks, in the order they will be tested

Each is a separate ablation, kept only if it improves the same target on both
decision folds. Blocks are ordered by expected value, not by how interesting
they are.

1. **Own history.** EWMA, last 10, last 20, season-to-date. The baseline.
2. **Rotation.** Depth rank, rank improvement, available rank, position slot —
   already computed by `team_hierarchy`.
3. **Absorption.** Expected vacated minutes and usage, from
   `mod.team_hierarchy_vw`. Prior work measured this as the largest structural
   effect for minutes and a small one for usage.
4. **Injury timing.** Report status and `p_play` from the hierarchy, plus
   `p_next_game` and expected games missed from `mod.injury_daily_forecast_vw`.
   Untested in this form: the earlier attempt only knew whether a teammate was
   out tonight, not when he comes back.
5. **Archetypes.** Not own-archetype — that has been rejected twice. The two
   untested uses are teammate composition weighted by expected minutes (who
   absorbs the usage), and a cold-start prior for players with little history.
6. **Incentives.** Standings position and playoff distance. The only block that
   replicated in prior work, and the only one describing something outside the
   player's own record.

## The gate

A block ships only if:

- conditional-rate MAE beats `mod.team_hierarchy_vw.expected_usage` on both
  decision folds by at least 2%, and
- marginal usage volume beats the composed baseline (hierarchy `p_play` ×
  `minutes_if_plays` × trailing rate), and
- the gain does not come from a single slice.

Anything smaller than the spread between folds is not evidence. The honest
expected outcome is a null result for archetypes and a small gain from
rotation and incentives.

## Cold start

The first month is where a model can actually win: in 2026-27 the season-to-date
mean falls to R² 0.164 against 0.290 for an EWMA, because ten games of prior
state do not exist yet. Any cold-start feature is evaluated on the first ten
games of each season separately, not folded into an aggregate that hides it.
