# Margin Tail Fine Search and Split Validation

Research-only validation. Formal Predictor formulas and production defaults remain unchanged.

## Split Summary

| Split | Matches | Best GD>=3 | Best Top-3 | Best Top-5 | alpha=0.10 GD Error Delta | alpha=0.10 Top-3 Delta |
| --- | ---: | --- | --- | --- | ---: | ---: |
| all_pooled | 1170 | gd_tail_redistribution_alpha_0.12 | gd_tail_redistribution_alpha_0.10 | gd_tail_redistribution_alpha_0.14 | 0.022076 | 0.003419 |
| fifa_world_cup_only | 881 | gd_tail_redistribution_alpha_0.14 | baseline | gd_tail_redistribution_alpha_0.14 | 0.022126 | 0.000000 |
| uefa_euro_only | 289 | baseline | gd_tail_redistribution_alpha_0.04 | gd_tail_redistribution_alpha_0.04 | -0.021924 | 0.013841 |
| modern_era_1990_plus | 784 | baseline | gd_tail_redistribution_alpha_0.10 | gd_tail_redistribution_alpha_0.08 | -0.022115 | 0.006378 |
| recent_era_2000_plus | 597 | baseline | gd_tail_redistribution_alpha_0.10 | baseline | -0.022168 | 0.011725 |

## Recommendation

- alpha=0.10 stable for GD calibration: `False`
- Top-3 / Top-5 gains are small: `True`
- Improvement mainly early World Cup: `True`
- Continue diagnostics / monitoring: `True`
- Keep formal baseline unchanged: `True`
