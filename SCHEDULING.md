# Scheduling the team-hierarchy job

Status: the daily job is scheduled through `nba/mod/_runner` on the NUC and
executes on the Jetson.

## Schedule row

`util.update_schedule` carries:

```text
job_family          model
schema              mod
table_name          team_hierarchy
associated_function scs.nba.mod.team_hierarchy
cadence             intraday
schema_sequence     NULL
function_sequence   NULL
pause               FALSE
```

Injury carries `function_sequence = 1`; hierarchy is NULL so the runner's
`NULLS LAST` ordering puts it after injury. The hierarchy job reads
`mod.injury_game_availability_base`, so the order is a data dependency, not a
preference.

The runner derives the repo directory from the last dotted segment
(`team_hierarchy`) and runs its root `__main__.py`.

## Execution

Two model runs a day, both after the database `intraday` refresh that writes
`nba.get_team_injuries` (16:00 and 22:00 UTC):

```cron
15 16 * * *  $NBA_JOBS/mod/_runner/cron.sh intraday >> $NBA_JOBS/mod/_runner/cron.log 2>&1
15 22 * * *  $NBA_JOBS/mod/_runner/cron.sh intraday >> $NBA_JOBS/mod/_runner/cron.log 2>&1
```

Do not add the 03:45 or 07:00 slots: the 13:00 database `daily` run is the only
writer of box scores, so those runs would carry two-night-old form.

The job fails if `nba.get_team_injuries` has not succeeded within two hours, if
the box-score task is more than 30 hours old, or if the availability table has
no rows. The runner SSHes to the Jetson and runs, from
`/home/oli/shaggy_camel_sports/nba/mod/team_hierarchy`:

```bash
uv run --frozen --group data python __main__.py
```

The job writes `{"row_count": n}` to `SCS_RESULT_FILE`; the runner writes
`process start`, `team_hierarchy.job` and `process end` to `util.update_log`.

## Model bundle

The production models are frozen at the end of 2025-26 and copied to the
Jetson; the daily job never refits on 2026-27.

```bash
uv run --group data python scripts/fit_model.py --through-season 2025-26
scp artifacts/team_hierarchy/model.pkl artifacts/team_hierarchy/model.json \
  jetson:/home/oli/shaggy_camel_sports/nba/mod/team_hierarchy/artifacts/team_hierarchy/
```

Refit after the 2026-27 season ends, then scp again.

## Backfill

Completed 2026-27 slates plus today:

```bash
uv run --group data python scripts/backfill.py \
  --season 2026-27 --end 2026-11-07
```

It uses the same 2025-26 bundle for every date and writes to
`mod.team_hierarchy_base`; the public `mod.team_hierarchy_vw` is applied by
`nba/mod/_runner` after the job.

## Verification

```bash
cd /home/oli/shaggy_camel_sports/nba/mod/_runner
./cron.sh --list
./cron.sh daily --dry-run
./cron.sh --task team_hierarchy
```

Then check `util.update_log` for `source = 'scs.nba.mod.team_hierarchy'` and
`mod.team_hierarchy_vw` for the target `game_date`.
