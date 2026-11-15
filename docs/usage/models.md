# Usage model vs baselines

Expanding-window folds. `usg_pct` conditional on playing, 5+ minutes. Every feature is computed from games before the row it describes.

| model | features | 2024-25 MAE | 2024-25 R2 | 2025-26 MAE | 2025-26 R2 | 2026-27 MAE | 2026-27 R2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | EWMA-3 | 0.0452 | 0.4160 | 0.0455 | 0.4122 | 0.0471 | 0.3737 |
| baseline | last 10 games | 0.0454 | 0.4138 | 0.0456 | 0.4103 | 0.0476 | 0.3662 |
| baseline | last 20 games | 0.0447 | 0.4313 | 0.0451 | 0.4287 | 0.0473 | 0.3737 |
| baseline | season to date | 0.0455 | 0.3999 | 0.0457 | 0.4021 | 0.0490 | 0.2930 |
| ridge | history | 0.0441 | 0.4468 | 0.0444 | 0.4454 | 0.0457 | 0.4071 |
| ridge+budget | history | 0.0433 | 0.4634 | 0.0434 | 0.4648 | 0.0448 | 0.4255 |
| lightgbm | history | 0.0442 | 0.4454 | 0.0444 | 0.4459 | 0.0458 | 0.4065 |
| lightgbm+budget | history | 0.0434 | 0.4619 | 0.0435 | 0.4647 | 0.0447 | 0.4272 |
| blend | history | 0.0441 | 0.4485 | 0.0443 | 0.4477 | 0.0456 | 0.4097 |
| blend+budget | history | 0.0433 | 0.4648 | 0.0434 | 0.4666 | 0.0447 | 0.4289 |
| ridge | history+context | 0.0442 | 0.4465 | 0.0444 | 0.4455 | 0.0457 | 0.4076 |
| ridge+budget | history+context | 0.0433 | 0.4629 | 0.0434 | 0.4649 | 0.0448 | 0.4255 |
| lightgbm | history+context | 0.0442 | 0.4454 | 0.0444 | 0.4460 | 0.0456 | 0.4098 |
| lightgbm+budget | history+context | 0.0434 | 0.4619 | 0.0435 | 0.4645 | 0.0445 | 0.4298 |
| blend | history+context | 0.0441 | 0.4484 | 0.0443 | 0.4478 | 0.0455 | 0.4118 |
| blend+budget | history+context | 0.0433 | 0.4647 | 0.0434 | 0.4665 | 0.0446 | 0.4303 |
| ridge | history+hierarchy | 0.0436 | 0.4580 | 0.0437 | 0.4621 | 0.0450 | 0.4249 |
| ridge+budget | history+hierarchy | 0.0431 | 0.4674 | 0.0432 | 0.4692 | 0.0443 | 0.4368 |
| lightgbm | history+hierarchy | 0.0436 | 0.4580 | 0.0437 | 0.4619 | 0.0447 | 0.4291 |
| lightgbm+budget | history+hierarchy | 0.0432 | 0.4674 | 0.0433 | 0.4698 | 0.0441 | 0.4406 |
| blend | history+hierarchy | 0.0435 | 0.4610 | 0.0436 | 0.4646 | 0.0448 | 0.4295 |
| blend+budget | history+hierarchy | 0.0431 | 0.4698 | 0.0432 | 0.4716 | 0.0441 | 0.4408 |
| ridge | history+hierarchy+context | 0.0436 | 0.4581 | 0.0436 | 0.4627 | 0.0449 | 0.4258 |
| ridge+budget | history+hierarchy+context | 0.0431 | 0.4675 | 0.0432 | 0.4696 | 0.0443 | 0.4370 |
| lightgbm | history+hierarchy+context | 0.0436 | 0.4584 | 0.0437 | 0.4624 | 0.0448 | 0.4285 |
| lightgbm+budget | history+hierarchy+context | 0.0431 | 0.4681 | 0.0432 | 0.4701 | 0.0441 | 0.4402 |
| blend | history+hierarchy+context | 0.0435 | 0.4612 | 0.0436 | 0.4651 | 0.0447 | 0.4297 |
| blend+budget | history+hierarchy+context | 0.0431 | 0.4702 | 0.0432 | 0.4719 | 0.0441 | 0.4408 |
| ridge | base+standings | 0.0436 | 0.4581 | 0.0436 | 0.4627 | 0.0449 | 0.4258 |
| ridge+budget | base+standings | 0.0431 | 0.4675 | 0.0432 | 0.4696 | 0.0443 | 0.4370 |
| lightgbm | base+standings | 0.0436 | 0.4584 | 0.0437 | 0.4624 | 0.0448 | 0.4285 |
| lightgbm+budget | base+standings | 0.0431 | 0.4681 | 0.0432 | 0.4701 | 0.0441 | 0.4402 |
| blend | base+standings | 0.0435 | 0.4612 | 0.0436 | 0.4651 | 0.0447 | 0.4297 |
| blend+budget | base+standings | 0.0431 | 0.4702 | 0.0432 | 0.4719 | 0.0441 | 0.4408 |
| ridge | base+standings+own_archetype | 0.0437 | 0.4557 | 0.0437 | 0.4621 | 0.0449 | 0.4264 |
| ridge+budget | base+standings+own_archetype | 0.0432 | 0.4657 | 0.0432 | 0.4696 | 0.0443 | 0.4375 |
| lightgbm | base+standings+own_archetype | 0.0439 | 0.4543 | 0.0438 | 0.4598 | 0.0448 | 0.4282 |
| lightgbm+budget | base+standings+own_archetype | 0.0434 | 0.4640 | 0.0433 | 0.4684 | 0.0441 | 0.4397 |
| blend | base+standings+own_archetype | 0.0436 | 0.4587 | 0.0437 | 0.4637 | 0.0447 | 0.4300 |
| blend+budget | base+standings+own_archetype | 0.0432 | 0.4678 | 0.0432 | 0.4712 | 0.0441 | 0.4408 |
| ridge | base+standings+opponent_archetype | 0.0436 | 0.4579 | 0.0437 | 0.4621 | 0.0449 | 0.4258 |
| ridge+budget | base+standings+opponent_archetype | 0.0431 | 0.4674 | 0.0432 | 0.4693 | 0.0443 | 0.4371 |
| lightgbm | base+standings+opponent_archetype | 0.0437 | 0.4562 | 0.0438 | 0.4613 | 0.0449 | 0.4258 |
| lightgbm+budget | base+standings+opponent_archetype | 0.0432 | 0.4669 | 0.0433 | 0.4698 | 0.0441 | 0.4374 |
| blend | base+standings+opponent_archetype | 0.0436 | 0.4603 | 0.0436 | 0.4644 | 0.0448 | 0.4284 |
| blend+budget | base+standings+opponent_archetype | 0.0431 | 0.4696 | 0.0432 | 0.4716 | 0.0441 | 0.4395 |
| ridge | base+all_archetype | 0.0442 | 0.4486 | 0.0441 | 0.4581 | 0.0450 | 0.4251 |
| ridge+budget | base+all_archetype | 0.0433 | 0.4651 | 0.0433 | 0.4690 | 0.0443 | 0.4378 |
| lightgbm | base+all_archetype | 0.0443 | 0.4475 | 0.0442 | 0.4549 | 0.0453 | 0.4154 |
| lightgbm+budget | base+all_archetype | 0.0434 | 0.4632 | 0.0434 | 0.4677 | 0.0443 | 0.4337 |
| blend | base+all_archetype | 0.0441 | 0.4518 | 0.0440 | 0.4599 | 0.0450 | 0.4235 |
| blend+budget | base+all_archetype | 0.0433 | 0.4667 | 0.0432 | 0.4707 | 0.0442 | 0.4380 |
