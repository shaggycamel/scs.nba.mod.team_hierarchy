# Headline accuracy

`usg_pct` conditional on playing, 5+ minutes, expanding-window folds. `usage_events` use the hierarchy's predicted minutes; the `true min` columns hand the same rate the realised minutes.

| fold | n | mean usg | MAE | RMSE | R2 | corr | ±3pp | ±5pp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024-25 | 22728 | 0.185 | 0.0429 | 0.0557 | 0.4741 | 0.689 | 44.0% | 66.7% |
| 2025-26 | 23803 | 0.185 | 0.0430 | 0.0555 | 0.4764 | 0.691 | 43.7% | 66.0% |
| 2026-27 | 3563 | 0.182 | 0.0435 | 0.0567 | 0.4589 | 0.678 | 43.9% | 66.0% |

| fold | baseline MAE | baseline R2 | events MAE | events R2 | events MAE (true min) | events R2 (true min) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024-25 | 0.0447 | 0.4313 | 3.183 | 0.6717 | 2.439 | 0.8036 |
| 2025-26 | 0.0451 | 0.4287 | 3.164 | 0.6569 | 2.441 | 0.7930 |
| 2026-27 | 0.0473 | 0.3737 | 3.201 | 0.6523 | 2.412 | 0.7989 |
