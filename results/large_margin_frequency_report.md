# Large Margin Frequency and Overfitting Risk Report

Research-only data diagnostics. Formal Predictor formulas remain unchanged.

## Core Splits

| Split | Matches | GD>=3 | GD>=4 | GD>=5 | Favorite 3+ | Favorite 4+ | Avg Abs Elo Diff |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all_processed_matches | 49449 | 0.227568 | 0.121600 | 0.066614 | 0.190681 | 0.106352 | 122.01 |
| fifa_world_cup_only | 1008 | 0.181548 | 0.077381 | 0.040675 | 0.160714 | 0.070437 | 102.07 |
| uefa_euro_only | 388 | 0.121134 | 0.028351 | 0.012887 | 0.103093 | 0.025773 | 107.63 |
| modern_era_1990_plus | 32331 | 0.215459 | 0.112802 | 0.060901 | 0.187343 | 0.102193 | 131.80 |
| recent_era_2000_plus | 25387 | 0.215622 | 0.112341 | 0.060503 | 0.188758 | 0.102533 | 136.26 |

## Elo Mismatch Buckets

| Bucket | Matches | GD>=3 | GD>=4 | GD>=5 | Favorite 3+ |
| --- | ---: | ---: | ---: | ---: | ---: |
| abs_elo_diff_lt_100 | 25137 | 0.176990 | 0.085213 | 0.044635 | 0.119465 |
| abs_elo_diff_100_200 | 15099 | 0.220942 | 0.114246 | 0.059673 | 0.199881 |
| abs_elo_diff_200_300 | 6057 | 0.314512 | 0.179792 | 0.097408 | 0.305597 |
| abs_elo_diff_300_400 | 2132 | 0.445122 | 0.290807 | 0.179174 | 0.442308 |
| abs_elo_diff_400_plus | 1024 | 0.599609 | 0.426758 | 0.291992 | 0.599609 |

## World Cup Stage Proxy

international_results does not provide official stage labels; use this only as directional diagnostics.

| Proxy Stage | Matches | GD>=3 | GD>=4 | Favorite 3+ |
| --- | ---: | ---: | ---: | ---: |
| world_cup_group_stage_proxy | 705 | 0.195745 | 0.083688 | 0.175887 |
| world_cup_knockout_stage_proxy | 303 | 0.148515 | 0.062706 | 0.125413 |

## Conclusions

- Tail scorelines common enough for global model change: `False`
- Overfitting risk: `high`
- Recommended 48-team World Cup mode: conditional shadow diagnostics and separate group-stage diagnostics
- Research Poisson vs Negative Binomial: `True`
- Keep formal baseline unchanged: `True`
