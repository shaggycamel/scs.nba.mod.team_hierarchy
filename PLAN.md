# Team Hierarchy — Production Checklist

Status: 2026-11-07. The model, frozen bundle, daily job and Cockroach output
are working. The 2026-27 season is out-of-sample.

## Done

- Persisted bundle for position, availability + isotonic calibration, minutes
  and usage models.
- Bundle trained only through 2025-26; metadata records the cutoff, feature
  lists, package versions and git commit.
- `load()` refuses a library-version mismatch.
- Daily job loads the bundle; it does not refit.
- `__main__.py` / `scripts/job.py` for `scs.nba.mod.runner`.
- Publish to `mod.team_hierarchy_base`, keyed by
  `(game_date, game_id, team_id, player_id)`; the public
  `mod.team_hierarchy_vw` is applied from `nba/database`.
- `model_cutoff` and `model_version` written per row.
- Backfill for completed 2026-27 slates plus today (5,674 rows, 18 dates).
- Daily runner row and NUC cron entry.
- `SCHEDULING.md`, `README` production sections.
- 60 tests, ruff clean.

## Remaining (beyond the player_archetypes standard)

- CI with a synthetic fast suite; the real-data tests remain local.
- Monitoring/alert thresholds for row-count and empty-slate anomalies.
- Current-season/incremental fetch instead of the full 595k-row refresh.
- Seasonal refit reminder and bundle rollback runbook.

## Seasonal refit

After the 2026-27 season ends:

```bash
TEAM_HIERARCHY_DATA=data/daily uv run python scripts/fit_model.py \
  --through-season 2026-27
scp artifacts/team_hierarchy/model.pkl artifacts/team_hierarchy/model.json \
  jetson:/home/oli/shaggy_camel_sports/nba/mod/team_hierarchy/artifacts/team_hierarchy/
```

Do not refit mid-season; the point of the frozen bundle is that 2026-27 stays
out-of-sample.
