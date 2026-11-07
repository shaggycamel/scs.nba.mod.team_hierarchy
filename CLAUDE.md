# scs.nba.mod.team_hierarchy

Point-in-time NBA team hierarchy: depth charts, availability and minutes
absorption.

## Purpose
Rank every rostered player on a team, assign the five basketball positions, and
estimate who plays and who absorbs an absent teammate's minutes and usage.
- Every feature is computed from games strictly before the row it sits on.
- `pipeline.daily_hierarchy(date)` is the serving path; it must agree with the
  training build to 1e-9 on a historical date.
- The box score omits absent players; `roster.py` reconstructs the roster
  panel from membership intervals and dated evidence.
- Availability is modelled separately from minutes. `expected_minutes` is
  exactly `p_play * minutes_if_plays`; keep that decomposition.
- Minutes is the useful target. Usage barely beats a trailing mean; do not
  claim otherwise without an ablation.
- Always compare against simple baselines (season mean, trailing mean,
  mechanical minute allocation) before claiming a model helps.
- Walk-forward validation only, never random shuffles.

## Stack
- Python only, managed with `uv`. Python version is pinned in `.python-version`.
- Add dependencies with `uv add`; run code with `uv run`. Don't use `pip`.
- Use `polars` for data analysis. Avoid `pandas` unless a library requires it.
- Sort on `data.ROW_KEY` via `canonical_sort` before any window or rank.
  Polars' sort is not stable, and `(player, date, game)` is not unique for a
  traded player.

## Data
- The Parquet snapshot is not committed. Point `TEAM_HIERARCHY_DATA` at a
  directory containing `nba/` and `util/`; the default is `data/`.
- The snapshot is produced by `data/gen.py` in `scs.nba.mod.scratch`.
- Never commit raw data exports or large files.

## Database (CockroachDB Cloud)
- Cluster: `nba-data-mgmt` (id `11af18b7-ef5e-41b2-b3b7-5db438b1d403`),
  database `nba`, schema `nba`.
- **Read-only, always.** Use only `select_query`, `list_*`,
  `get_table_schema`, `explain_query`, `show_statement` and
  `show_running_queries`.
- Never use `create_database`, `create_table`, `insert_rows`, or any DDL/DML.
  Ask the user to run writes.
- Use only schema `nba.nba`. Ignore `util`, `anl` and `fty` as feature sources;
  `util` Parquet tables in the snapshot are the id crosswalk.
- Prefer `*_vw` views where they cover the question. Check the schema before
  writing queries; add explicit `LIMIT`s on large tables.

## Secrets
- Never print, log or commit `COCKROACH_URL`, API keys or credentials.

## Git
- Work on the session branch; never push to `main`.
- Make small, focused commits with descriptive messages.
- Don't commit raw data exports or large files.
