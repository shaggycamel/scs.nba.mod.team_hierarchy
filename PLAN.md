# Team Hierarchy — Production Checklist

Status: 2026-11-16. The model, frozen bundle, daily job and Jetson output are
working. The 2026-27 season is out-of-sample.

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
- Seven-day horizon over unplayed slates, with a partially played date frozen.
- Availability precedence: report, then the injury curve, then state-only;
  `p_play_source` and `p_play_injury` record which one produced the row.
- `mod.game_day_vw` joins the horizon, the latest injury spell and the
  archetype profile for the day-of contract.
- `scripts/eval_horizon.py` compares the composed curve with state-only at the
  same information set; the sampled 2026-27 check is in the README.
- `SCHEDULING.md`, `README` production sections.
- 71 tests, ruff clean.

## Remaining (beyond the player_archetypes standard)

- CI with a synthetic fast suite; the real-data tests remain local.
- Monitoring/alert thresholds for row-count and empty-slate anomalies.
- Cache the panel across the two intraday runs; it still rebuilds the full
  history from the views each time.
- Seasonal refit reminder and bundle rollback runbook.
- Run `eval_horizon.py` over the full 2026-27 season at the next refit; the
  current check samples two run dates.

## Seasonal refit

After the 2026-27 season ends:

```bash
uv run --group data python scripts/fit_model.py --through-season 2026-27
scp artifacts/team_hierarchy/model.pkl artifacts/team_hierarchy/model.json \
  jetson:/home/oli/shaggy_camel_sports/nba/mod/team_hierarchy/artifacts/team_hierarchy/
```

Do not refit mid-season; the point of the frozen bundle is that 2026-27 stays
out-of-sample.
