# Usage: the evidence behind the head

Provenance: built in `scs.nba.mod.usage`, a standalone research repo, and moved
here with the head it produced (`src/team_hierarchy/usage.py`). That repo has
been removed; the reports in this directory are the record, and
`scripts/eval_usage.py` reproduces the headline accuracy from this repo.

## What the head is worth

Walk-forward, `usg_pct` conditional on playing, 5+ minutes, scored in this repo
by `scripts/eval_usage.py`:

| | trailing mean | layer 4 usage | usage head + budget |
| --- | ---: | ---: | ---: |
| 2024-25 MAE / R² | 0.0448 / 0.428 | 0.0443 / 0.440 | **0.0430 / 0.471** |
| 2025-26 | 0.0452 / 0.425 | 0.0441 / 0.450 | **0.0431 / 0.474** |
| 2026-27 | 0.0476 / 0.368 | 0.0454 / 0.422 | **0.0438 / 0.452** |

Usage events: 3.16-3.18 MAE, R² 0.66-0.67, against 3.37-3.47 / 0.60-0.63 for a
trailing event count.

## What was tested and rejected

Kept because the negative results are the expensive part.

| block | verdict | evidence |
| --- | --- | --- |
| archetype responsibilities, own | rejected | `models.md`; third independent rejection |
| opponent archetype mix | rejected | `models.md` |
| team-mate archetype mix | rejected | `models.md` |
| own × opponent interaction | rejected | `models.md` |
| standings and incentives | rejected | `models.md` |
| game context (rest, trends, start rate) | neutral | `models.md` |
| shrinkage towards the trailing mean | no-op | `tuning.md` |
| ridge penalty, 0.3 to 30 | irrelevant | `tuning.md` |
| LightGBM with 900 trees | overfits | `models.md` |
| usage events as a second target | **kept** | `volume.md` |
| team-budget normalisation | **kept** | `models.md`, `volume.md` |
| ridge + LightGBM blend | **kept** | `models.md` |

The archetype mixes were populated for 76% of played rows with real variation, so
those nulls are not an availability artifact. The reading: usage rate is set by a
player's own role and by who else is available on his team, and the absorption
features already carry the second part.

## Reports

| file | contents |
| --- | --- |
| `baselines.md` | trailing means, rate and volume, three folds |
| `models.md` | every feature block × fitter × fold |
| `tuning.md` | ridge penalty and shrinkage, selected on one fold |
| `volume.md` | usage events conditional and marginal |
| `summary.md` | headline accuracy: MAE, RMSE, R², correlation, ±3pp, ±5pp |
| `design.md` | target, folds, the ablation gate, cold start |

## Caveats carried over

- Three folds, and the third is 25 days of a live season. Quote the 2024-25 and
  2025-26 numbers.
- Ranking was never measured. MAE and correlation say nothing about whether the
  model orders players better, which is what a draft board uses.
- The head inherits the availability and minutes heads' failure modes through
  `p_play` and `minutes_if_plays`, and the budget rescale will happily rescale on
  a wrong roster.
- Under three prior games the history features are null and the head leans on
  hierarchy priors. It has not been through an opening night.
