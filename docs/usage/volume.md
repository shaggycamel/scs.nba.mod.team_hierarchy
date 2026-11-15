# Usage events

FGA + 0.44 FTA + TOV. Conditional rows are 5+ minutes; marginal rows are every roster row with absentees as zero.

| fold | model | n | MAE | RMSE | R2 |
| --- | --- | ---: | ---: | ---: | ---: |
| 2024-25 | trailing events | 22851 | 3.298 | 4.313 | 0.6469 |
| 2024-25 | trailing rate x h_minutes | 22851 | 3.282 | 4.271 | 0.6538 |
| 2024-25 | model rate x h_minutes | 23030 | 3.179 | 4.147 | 0.6732 |
| 2024-25 | model rate x actual minutes | 23030 | 2.453 | 3.224 | 0.8025 |
| 2024-25 | marginal: trailing | 24705 | 3.329 | 4.443 | 0.6481 |
| 2024-25 | marginal: model | 24705 | 3.253 | 4.361 | 0.6610 |
| 2025-26 | trailing events | 23951 | 3.326 | 4.366 | 0.6170 |
| 2025-26 | trailing rate x h_minutes | 23951 | 3.263 | 4.265 | 0.6345 |
| 2025-26 | model rate x h_minutes | 24152 | 3.160 | 4.124 | 0.6580 |
| 2025-26 | model rate x actual minutes | 24152 | 2.453 | 3.219 | 0.7916 |
| 2025-26 | marginal: trailing | 25768 | 3.266 | 4.350 | 0.6431 |
| 2025-26 | marginal: model | 25768 | 3.198 | 4.254 | 0.6586 |
| 2026-27 | trailing events | 3632 | 3.374 | 4.364 | 0.6246 |
| 2026-27 | trailing rate x h_minutes | 3632 | 3.270 | 4.241 | 0.6455 |
| 2026-27 | model rate x h_minutes | 3734 | 3.206 | 4.209 | 0.6524 |
| 2026-27 | model rate x actual minutes | 3734 | 2.435 | 3.224 | 0.7961 |
| 2026-27 | marginal: trailing | 3917 | 3.249 | 4.257 | 0.6629 |
| 2026-27 | marginal: model | 3917 | 3.175 | 4.175 | 0.6757 |
