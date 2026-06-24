# Score Distribution Diagnostics Report

Dataset: FIFA World Cup + UEFA Euro neutral matches, FIFA + historical national team universe.

Model: `final_worldcup_model_v1_candidate`, domination disabled / 100% normal xG.

## MAX_GOALS Sensitivity

| MAX_GOALS | LogLoss | Brier | Top-1 | Top-3 | Top-5 | GD>=3 Prob | TG>=4 Prob | Missing Tail Mass | Runtime ms/match |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 0.993752 | 0.590615 | 0.127350 | 0.335897 | 0.484615 | 0.137631 | 0.281544 | 0.009431 | 0.0314 |
| 6 | 0.993691 | 0.590515 | 0.127350 | 0.335897 | 0.484615 | 0.143195 | 0.286557 | 0.002498 | 0.0415 |
| 7 | 0.993684 | 0.590491 | 0.127350 | 0.335897 | 0.484615 | 0.144581 | 0.287777 | 0.000791 | 0.0522 |
| 8 | 0.993686 | 0.590487 | 0.127350 | 0.335897 | 0.484615 | 0.144887 | 0.288048 | 0.000410 | 0.0677 |
| 10 | 0.993687 | 0.590486 | 0.127350 | 0.335897 | 0.484615 | 0.144960 | 0.288114 | 0.000318 | 0.1029 |

## Goal-Difference Tail

| Bucket | Actual Rate | Predicted Probability | Actual - Predicted |
| --- | ---: | ---: | ---: |
| GD=0 | 0.241026 | 0.236890 | 0.004136 |
| GD=1 | 0.400855 | 0.404715 | -0.003860 |
| GD=2 | 0.194017 | 0.220764 | -0.026747 |
| GD>=3 | 0.164103 | 0.137631 | 0.026471 |

## Favorite Margin

| Bucket | Actual Rate | Predicted Probability | Actual - Predicted |
| --- | ---: | ---: | ---: |
| favorite_win_by_1 | 0.250427 | 0.247150 | 0.003277 |
| favorite_win_by_2 | 0.141880 | 0.157503 | -0.015622 |
| favorite_win_by_3_plus | 0.140171 | 0.112465 | 0.027706 |

## Truncation

- 6+ goals by either team: `0.027350`
- 7+ goals by either team: `0.012821`
- 8+ goals by either team: `0.005983`
- Exact scores outside MAX_GOALS=5: `0.027350`

## Conclusions

- Raise MAX_GOALS for W/D/L metrics: `False`
- Raise MAX_GOALS for exact-score diagnostics: `True`
- Primary GD>=3 underestimation cause: xG difference / score-distribution shape, not grid truncation
- Fat-tail score distribution research recommended: `True`
- Formal model formulas unchanged: `True`
