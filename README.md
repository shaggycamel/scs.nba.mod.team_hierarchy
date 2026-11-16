# team-hierarchy

Point-in-time NBA depth charts: rank every rostered player, assign the five
position slots, estimate who is available, and predict who absorbs an absent
teammate's minutes and usage.

Extracted from the `nba_adhoc` team-hierarchy branch at commit
`afcfd67` (`heir-mod`). The source branch is archived in that repository as tag
`archive/heir-mod-2026-11-07`.

`pipeline.daily_hierarchy(date)` is the entry point. Every model inside it is
fitted only on games before the date it is asked about.

## The layers

| module | does | key output |
| --- | --- | --- |
| `data.py` | loads box scores, normalises the free-text DNP reason | `presence` |
| `roster.py` | rebuilds the rows the box score omits | roster-complete panel |
| `state.py` | 111 pre-game features from prior games only | trailing form |
| `position.py` | G/F/C learned, then split into five positions | `position`, `position_depth` |
| `availability.py` | calibrated probability the player takes the floor | `p_play` |
| `absorption.py` | who inherits an absent teammate's minutes and usage | `expected_minutes`, `expected_usage` |

Each module opens with the measurements behind its design decisions, including
the ones that argued against the obvious choice. `scripts/eval_*.py` reproduce
the figures below.

### Why there is a panel

The box score only carries rows for players a team listed that night, so an
absent player usually leaves no trace: **92.7% of players the injury report
lists as Out have no box-score row at all** (34,189 of 36,894 player-dates). A
model asked who absorbs an absent teammate's minutes cannot see the absence in
that data.

`roster.py` reconstructs those rows from a membership interval per
(season, team, player), bounded by dated evidence, and takes the panel from
516,941 to 608,143 rows. It also fixes a quieter problem: a player who vanishes
for three months would otherwise keep a stale trailing average.

## Results

Walk-forward throughout — each validation season is predicted by models trained
only on seasons that finished before it. Simple baselines first.

**Position**, share of starters assigned the right G/F/C slot:

| method | accuracy |
| --- | --- |
| majority class | 0.4000 |
| slot the player has started at most often before | 0.8529 |
| profile only | 0.8437 |
| profile + start history | 0.8804 |
| + matching the lineup to the 2G/2F/1C skeleton | **0.9504** |

The constraint supplies most of the gain. This assumes the five starters are
known; it measures slotting a lineup, not predicting who starts.

**Availability**, whether the player takes the floor:

| model | log loss | Brier | AUC | ECE |
| --- | --- | --- | --- | --- |
| base rate | 0.6708 | 0.2389 | 0.5000 | 0.0111 |
| report status only | 0.4144 | 0.1336 | 0.8030 | 0.0549 |
| recent playing record only | 0.3787 | 0.1172 | 0.9018 | 0.0102 |
| both | 0.2548 | 0.0800 | 0.9555 | 0.0206 |
| both + isotonic calibration | 0.2581 | 0.0805 | 0.9544 | **0.0115** |

Injury earns its place — a third off the log loss. But the report alone is
worse than the recent record alone: it is a strong complement, not a
substitute.

**Minutes**, for players who played:

| model | MAE | RMSE | R² |
| --- | --- | --- | --- |
| season mean | 5.348 | 7.042 | 0.5430 |
| trailing mean | 5.163 | 6.753 | 0.5798 |
| mechanical minute-budget allocation | 5.352 | 7.100 | 0.5361 |
| model, own form only | 5.052 | 6.535 | 0.6067 |
| model, own form + absorption | **4.762** | **6.158** | **0.6510** |

Absorption is worth 0.044 of R² overall and 0.101 on the quartile with the most
minutes in doubt, where the model reaches 0.491 against 0.390 for own form
alone. The mechanical allocation matches a trailing mean overall, then collapses
to R² 0.199 exactly where absences are largest.

Composed end to end, `expected_minutes` reaches **R² 0.787, MAE 4.0 minutes**
against actual minutes across every roster row, absentees counted as zero.

## The usage head

Layer 4's usage regression was the one head that never cleared its own bar: R²
0.3421 against 0.3310 for a trailing mean, with the same MAE to three decimals.
`team_hierarchy.usage` replaces it with a dedicated head and leaves the original
columns in place so the two can be compared live.

| 5+ minutes, walk-forward | trailing mean | layer 4 usage | usage head + budget |
| --- | ---: | ---: | ---: |
| 2024-25 MAE / R² | 0.0448 / 0.428 | 0.0443 / 0.440 | **0.0430 / 0.471** |
| 2025-26 | 0.0452 / 0.425 | 0.0441 / 0.450 | **0.0431 / 0.474** |
| 2026-27 | 0.0476 / 0.368 | 0.0454 / 0.422 | **0.0438 / 0.452** |

Ratios are on the rows the trailing baseline can also speak to. Usage events
(`FGA + 0.44 FTA + TOV`) come out at 3.16-3.18 MAE and R² 0.66-0.67, against
3.37-3.47 and 0.60-0.63 for the trailing event count.

Three things do the work: trailing state at several horizons (last 5 and last
20, plus the trend between them), a second target in events per minute, and the
team budget — minutes-weighted team usage is 0.1935 with an SD of 0.003 across
team-games, and rescaling each team-game to it corrects the errors an
independent per-player model cannot cancel.

Everything that was tested and rejected — four archetype formulations, standings
and incentives, shrinkage, extra trees — is recorded in
[`docs/usage/`](docs/usage/), with the reports it came from. The negative
results are the expensive part; do not re-test them blind.

The state windows are built on the played subframe and attached with an as-of
join plus one sentinel row per player a day after his last game. Without the
sentinel the join is off by one game and costs 0.006 of MAE; `tests/test_usage.py`
pins the correct behaviour against a direct computation.

Published as `expected_usage_model` (rate, budget-normalised) and
`expected_usage_events` (events with `minutes_if_plays`). Both are null until the
bundle is refitted: the head is stored in `HierarchyBundle.usage_head`, and a
bundle pickled before it existed simply omits the columns.

```bash
TEAM_HIERARCHY_DATA=data/daily uv run python scripts/fit_model.py --through-season 2025-26
```

## What is weak

- **Usage barely beats a trailing mean** (R² 0.3421 against 0.3310, identical
  MAE to three decimals). Build on minutes and availability, not usage rate.
- **The five-position split is soft.** G/F/C holds 97.1% game to game; PG/SG and
  SF/PF are a convention with no source labels, hold 87.5%, and a quarter of the
  split decisions rest on an arbitrarily small gap.
- **Layers 3 and 4 start in 2021-22**, where the injury report begins. Layers 1
  and 2 use all of 2009-10 onward.
- **2021-22's report is not comparable to later seasons** — 4.9% coverage
  against ~30% since, and an "Out" still played 8.2% of the time. Status-cut
  statistics should exclude it.
- A waived-and-re-signed player can read as one long absence;
  `absence_run_full` flags implausible runs (0.65% are over 60 games).

## Horizon availability

The daily job scores every unplayed slate in the next seven days. For a date
whose report has not been published, the hierarchy's state-only `p_play` is
badly overconfident: across 2026-27 rosters it averages 0.63 on rows where the
actual play rate is 0.19. The injury model's per-game survival fills those
dates instead (report wins whenever one exists).

Sampled check on 2026-27 with the panel cut at each run date
(`scripts/eval_horizon.py`, runs 2026-11-05 and 2026-11-11):

| days ahead | n | play rate | state-only Brier | composed Brier | minutes MAE before → after |
| --- | ---: | ---: | ---: | ---: | ---: |
| all | 2,618 | 0.581 | 0.196 | 0.161 | 6.70 → 5.87 |
| 1-2 | 1,118 | 0.560 | 0.188 | 0.150 | 6.45 → 5.54 |
| 3-5 | 1,011 | 0.580 | 0.207 | 0.178 | 6.78 → 6.08 |
| 6-7 | 489 | 0.632 | 0.191 | 0.151 | 7.13 → 6.23 |
| rows the curve changed | 379 | 0.190 | 0.373 | 0.127 | 9.45 → 4.13 |

The composed probability still runs a little high (0.69-0.71 against 0.58-0.63),
but the minutes allocation moves with it. The panel cutoff is the whole point:
without it the serving state sees games played between the run and the target,
which flatters the state-only model and hides the problem.

Reproduce:

```bash
# injury repo: the historical curve for the season
INJURY_DURATION_DATA=data/full uv run python scripts/21_backfill_availability.py \
  --season 2026-27

# hierarchy repo
TEAM_HIERARCHY_DATA=data/daily uv run python scripts/eval_horizon.py \
  --availability ../injury_duration/artifacts/availability_2026_27.parquet \
  --runs 2026-11-05,2026-11-11
```

This is a sampled check, not the full walk-forward. The seasonal refit is where
it becomes a full-season test.

## Leakage and reproducibility

Every feature is computed from games strictly before the row it sits on, and
that is asserted rather than assumed. `tests/` pins the arithmetic on synthetic
cases, recomputes real players' features by brute force, and requires the daily
path and the training build to agree to 1e-9 on a historical date.

Three cautions for anyone extending this:

- `absence_run_full` is deliberately forward-looking and is a diagnostic only.
  Features use `absent_streak_prior`; a test pins the difference.
- Absence is measured from `p_play`, never from who actually played. The report
  is known before tip-off; the outcome is not.
- **Sort on `data.ROW_KEY`, via `canonical_sort`, before any window or rank.**
  Polars' sort is not stable; `(player, date, game)` is not unique when a
  traded player appears for both teams. Two tests shuffle the input and require
  identical output.

## Install

```bash
uv sync --group dev
```

## Data

The Parquet snapshot is not committed. Point `TEAM_HIERARCHY_DATA` at a
directory containing `nba/` and `util/`:

```bash
export TEAM_HIERARCHY_DATA=/path/to/nba_adhoc/data
```

The default is `data/` in the repository root. The model needs:

```
nba/injuries.parquet
nba/league_game_schedule.parquet
nba/player_box_score.parquet
nba/player_info.parquet
nba/team_roster_vw.parquet
nba/teams.parquet
util/player_id_map_vw.parquet
```

The daily run uses the dated `team_roster_vw` to correct offseason membership: a player traded in July has no game for his new team yet, so the panel alone would still put him on last season's team.

## Reproduce

```bash
uv run python scripts/depth_chart.py BOS 2025-03-05   # one team's chart
uv run python scripts/eval_position.py                # position tables
uv run python scripts/eval_availability.py            # availability tables
uv run python scripts/eval_absorption.py              # minutes/usage tables
uv run python scripts/export_charts.py 2026-04-12     # reports/ CSV, TXT, HTML
uv run pytest                                          # 60 tests
```

## Persisted model

The production bundle is frozen through 2025-26, so the whole 2026-27 season is
out-of-sample:

```bash
TEAM_HIERARCHY_DATA=data/daily uv run python scripts/fit_model.py \
  --through-season 2025-26
```

This writes `artifacts/team_hierarchy/model.pkl` and `model.json`. The daily
job loads it and never refits:

```bash
uv run python __main__.py --date 2026-11-07
```

The four fitted models (position, availability + isotonic, minutes, usage) and
their feature lists live in the bundle. `persist.load()` refuses a package
version mismatch.

## Scheduled pipeline and backfill

`__main__.py` refreshes the snapshot, loads the 2025-26 bundle and scores every
unplayed slate in the next seven days, replacing those `game_date` rows in
`mod.team_hierarchy_base` in one publish. The public `mod.team_hierarchy_vw` and
the day-of contract `mod.game_day_vw` are applied from
`nba/database/sql/views/mod/`. It is scheduled through `nba/mod/_runner` on the
NUC; see [`SCHEDULING.md`](SCHEDULING.md).

A date freezes once any result is ingested, so a partially played slate is
never rewritten. Pass `--date 2026-11-07` to score one slate instead of the
horizon.

Availability has three sources, in order:

| condition | `p_play` from | `p_play_source` |
| --- | --- | --- |
| an injury report exists for that game date | the calibrated play model | `report` |
| no report, active injury spell | `1 - surv` from `mod.injury_game_availability_base` | `injury` |
| no report, no spell | the calibrated play model | `state` |

The override runs before absorption, so an expected return also changes the
minutes his replacement can absorb. `p_play_injury` carries the curve's value
alongside the final `p_play`. The injury row is required: the job fails rather
than silently falling back to the overconfident state-only probability.

Completed 2026-27 slates plus today:

```bash
TEAM_HIERARCHY_DATA=data/daily uv run python scripts/backfill.py \
  --season 2026-27 --end 2026-11-07
```

The same frozen bundle is used for every date, and every row records
`model_cutoff` and `model_version`.

## Layout

```
src/team_hierarchy/
  data.py         # box score, schedule, injury report
  roster.py       # roster-complete panel
  state.py        # pre-game features, strictly prior games
  position.py     # G/F/C and five-slot assignment
  availability.py # calibrated p_play
  absorption.py   # minutes/usage allocation
  pipeline.py     # daily composition, out-of-fold fitting
scripts/          # depth chart, evaluations, report export
tests/            # synthetic + real-data leakage tests
reports/          # committed depth-chart artifacts for 2026-04-12
```
