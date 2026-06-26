# Negative Binomial Feasibility Benchmark

Research-only benchmark. Formal Predictor formulas and production defaults remain unchanged.

## Split Summary

| Split | Matches | Baseline LogLoss | Best NB LogLoss | Best NB | LogLoss Delta | Top-3 Delta | GD Error Delta | TG>=4 Error Delta | MAD Drift |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| all_pooled | 1170 | 0.993752 | 0.994336 | negative_binomial_r_20_draw_1.00 | -0.000583 | -0.005983 | 0.016168 | -0.002600 | 0.001837 |
| fifa_world_cup_only | 881 | 0.979603 | 0.980383 | negative_binomial_r_20_draw_0.95 | -0.000780 | -0.003405 | 0.017809 | -0.002052 | 0.001782 |
| uefa_euro_only | 289 | 1.036887 | 1.034691 | negative_binomial_r_20_draw_1.10 | 0.002196 | -0.013841 | -0.013297 | 0.003537 | 0.002281 |
| world_cup_modern_1990_plus | 536 | 0.984072 | 0.984267 | negative_binomial_r_20_draw_1.05 | -0.000195 | -0.005597 | -0.005036 | 0.003286 | 0.002059 |
| world_cup_recent_2000_plus | 386 | 0.974221 | 0.974118 | negative_binomial_r_20_draw_1.00 | 0.000103 | -0.005181 | -0.015331 | 0.002760 | 0.001843 |
| high_mismatch_abs_elo_diff_300_plus | 87 | 0.771735 | 0.753775 | negative_binomial_r_8_draw_0.90 | 0.017960 | -0.011494 | -0.005242 | -0.007018 | 0.002841 |
| balanced_abs_elo_diff_lt_200 | 887 | 1.040566 | 1.041365 | negative_binomial_r_20_draw_1.05 | -0.000798 | -0.007892 | 0.016277 | 0.002711 | 0.002037 |

## Recommendation

- NB improves pooled LogLoss: `False`
- NB improves high-mismatch LogLoss: `True`
- Continue NB research: `True`
- Keep Bivariate Poisson baseline: `True`
