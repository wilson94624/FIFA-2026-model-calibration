# Elo Mismatch Conditional Tail Benchmark

Research-only benchmark. Formal Predictor formulas and production defaults remain unchanged.

## Split Summary

| Split | Matches | Best GD>=3 | GD Error Delta | Top-3 Delta | MAD Drift | Affected Rate |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| all_pooled | 1170 | conditional_gd_tail_threshold_200_alpha_0.12 | 0.006849 | -0.002564 | 0.000381 | 0.241880 |
| fifa_world_cup_only | 881 | conditional_gd_tail_threshold_200_alpha_0.12 | 0.007469 | -0.001135 | 0.000415 | 0.263337 |
| uefa_euro_only | 289 | baseline | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| world_cup_modern_1990_plus | 536 | conditional_favorite_tail_threshold_250_alpha_0.12 | 0.004327 | 0.001866 | 0.000249 | 0.166045 |
| world_cup_recent_2000_plus | 386 | baseline | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| high_mismatch_abs_elo_diff_300_plus | 87 | baseline | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| balanced_abs_elo_diff_lt_200 | 887 | baseline | 0.000000 | 0.000000 | 0.000000 | 0.000000 |

## Recommendation

- Conditional tail more stable than global: `True`
- Improves high mismatch subset: `False`
- Hurts balanced subset: `False`
- Has 2026 group-stage research value: `True`
- Keep formal model baseline unchanged: `True`
