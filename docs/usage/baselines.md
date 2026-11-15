# Usage baselines

Prior-games-only trailing statistics on expanding-window season folds. `usg_pct` is a fraction; `usage_events` is FGA + 0.44 FTA + TOV.

## 2024-25 - usg_pct, all played (25025 rows)

| model | n | MAE | RMSE | R2 |
| --- | ---: | ---: | ---: | ---: |
| EWMA-3 | 24673 | 0.0509 | 0.0700 | 0.3201 |
| last 10 games | 24673 | 0.0510 | 0.0700 | 0.3213 |
| last 20 games | 24452 | 0.0500 | 0.0684 | 0.3454 |
| season to date | 24461 | 0.0514 | 0.0719 | 0.2857 |

## 2024-25 - usg_pct, 5+ minutes (23030 rows)

| model | n | MAE | RMSE | R2 |
| --- | ---: | ---: | ---: | ---: |
| EWMA-3 | 22831 | 0.0452 | 0.0587 | 0.4162 |
| last 10 games | 22831 | 0.0454 | 0.0588 | 0.4143 |
| last 20 games | 22692 | 0.0447 | 0.0579 | 0.4314 |
| season to date | 22601 | 0.0455 | 0.0595 | 0.3999 |

## 2024-25 - usage events, 5+ minutes (23030 rows)

| model | n | MAE | RMSE | R2 |
| --- | ---: | ---: | ---: | ---: |
| EWMA-3 events | 22831 | 3.2980 | 4.3128 | 0.6469 |
| last 10 events | 22831 | 3.3683 | 4.3948 | 0.6334 |
| last 20 events | 22692 | 3.3802 | 4.4220 | 0.6294 |
| rate x predicted minutes | 22831 | 3.3751 | 4.3995 | 0.6326 |
| rate x actual minutes | 22831 | 2.6019 | 3.4172 | 0.7783 |

## 2025-26 - usg_pct, all played (26088 rows)

| model | n | MAE | RMSE | R2 |
| --- | ---: | ---: | ---: | ---: |
| EWMA-3 | 25760 | 0.0505 | 0.0689 | 0.3263 |
| last 10 games | 25760 | 0.0506 | 0.0688 | 0.3271 |
| last 20 games | 25538 | 0.0499 | 0.0676 | 0.3486 |
| season to date | 25506 | 0.0509 | 0.0696 | 0.3133 |

## 2025-26 - usg_pct, 5+ minutes (24152 rows)

| model | n | MAE | RMSE | R2 |
| --- | ---: | ---: | ---: | ---: |
| EWMA-3 | 23946 | 0.0455 | 0.0588 | 0.4121 |
| last 10 games | 23946 | 0.0456 | 0.0589 | 0.4101 |
| last 20 games | 23796 | 0.0451 | 0.0580 | 0.4288 |
| season to date | 23684 | 0.0457 | 0.0593 | 0.4021 |

## 2025-26 - usage events, 5+ minutes (24152 rows)

| model | n | MAE | RMSE | R2 |
| --- | ---: | ---: | ---: | ---: |
| EWMA-3 events | 23946 | 3.3250 | 4.3648 | 0.6173 |
| last 10 events | 23946 | 3.3873 | 4.4496 | 0.6023 |
| last 20 events | 23796 | 3.4297 | 4.4977 | 0.5944 |
| rate x predicted minutes | 23946 | 3.3962 | 4.4560 | 0.6012 |
| rate x actual minutes | 23946 | 2.6070 | 3.4473 | 0.7613 |

## 2026-27 - usg_pct, all played (4179 rows)

| model | n | MAE | RMSE | R2 |
| --- | ---: | ---: | ---: | ---: |
| EWMA-3 | 4022 | 0.0523 | 0.0710 | 0.2895 |
| last 10 games | 4022 | 0.0527 | 0.0710 | 0.2898 |
| last 20 games | 3937 | 0.0524 | 0.0705 | 0.2967 |
| season to date | 3712 | 0.0547 | 0.0764 | 0.1642 |

## 2026-27 - usg_pct, 5+ minutes (3829 rows)

| model | n | MAE | RMSE | R2 |
| --- | ---: | ---: | ---: | ---: |
| EWMA-3 | 3727 | 0.0470 | 0.0610 | 0.3730 |
| last 10 games | 3727 | 0.0474 | 0.0613 | 0.3662 |
| last 20 games | 3658 | 0.0472 | 0.0608 | 0.3733 |
| season to date | 3443 | 0.0488 | 0.0645 | 0.2931 |

## 2026-27 - usage events, 5+ minutes (3829 rows)

| model | n | MAE | RMSE | R2 |
| --- | ---: | ---: | ---: | ---: |
| EWMA-3 events | 3727 | 3.3809 | 4.3709 | 0.6220 |
| last 10 events | 3727 | 3.4784 | 4.4870 | 0.6016 |
| last 20 events | 3658 | 3.5988 | 4.6164 | 0.5772 |
| rate x predicted minutes | 3727 | 3.4819 | 4.4813 | 0.6026 |
| rate x actual minutes | 3727 | 2.6004 | 3.4183 | 0.7688 |
