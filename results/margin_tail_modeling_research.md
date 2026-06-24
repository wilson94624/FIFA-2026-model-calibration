# Margin Tail Modeling Research

Research-only benchmark. Formal Predictor formulas and production defaults remain unchanged.

## Summary

- Best GD>=3 calibration: `favorite_tail_boost_alpha_0.15`
- Best Top-3 correct score: `gd_tail_redistribution_alpha_0.10`
- Best Top-5 correct score: `gd_tail_redistribution_alpha_0.10`
- Most conservative non-baseline: `conditional_blowout_calibration_favorite_win_prob>=0.75`
- Keep formal baseline unchanged: `True`

## Results

| Variant | LogLoss | Brier | Top-3 | Top-5 | GD>=3 Error | Fav 3+ Error | KL Drift | MAD Drift |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 0.993752 | 0.590615 | 0.335897 | 0.484615 | 0.026471 | 0.027706 | 0.000000 | 0.000000 |
| max_goals_10_only | 0.993687 | 0.590486 | 0.335897 | 0.484615 | 0.019142 | 0.021135 | 0.009174 | 0.000151 |
| gd_tail_redistribution_alpha_0.05 | 0.993752 | 0.590615 | 0.338462 | 0.485470 | 0.015433 | 0.019831 | 0.000924 | 0.000613 |
| gd_tail_redistribution_alpha_0.10 | 0.993752 | 0.590615 | 0.339316 | 0.487179 | 0.004395 | 0.011955 | 0.003545 | 0.001226 |
| gd_tail_redistribution_alpha_0.15 | 0.993752 | 0.590615 | 0.334188 | 0.487179 | 0.006643 | 0.004080 | 0.007717 | 0.001840 |
| favorite_tail_boost_alpha_0.05 | 0.993752 | 0.590615 | 0.338462 | 0.485470 | 0.018596 | 0.019831 | 0.000602 | 0.000438 |
| favorite_tail_boost_alpha_0.10 | 0.993752 | 0.590615 | 0.339316 | 0.487179 | 0.010721 | 0.011955 | 0.002334 | 0.000875 |
| favorite_tail_boost_alpha_0.15 | 0.993752 | 0.590615 | 0.334188 | 0.487179 | 0.002846 | 0.004080 | 0.005124 | 0.001313 |
| conditional_blowout_calibration_favorite_win_prob>=0.65 | 0.993752 | 0.590615 | 0.334188 | 0.484615 | 0.023887 | 0.025121 | 0.000330 | 0.000144 |
| conditional_blowout_calibration_favorite_win_prob>=0.75 | 0.993752 | 0.590615 | 0.335897 | 0.484615 | 0.025615 | 0.026849 | 0.000102 | 0.000048 |
| conditional_blowout_calibration_xg_diff>=1.0 | 0.993752 | 0.590615 | 0.334188 | 0.484615 | 0.022738 | 0.023972 | 0.000488 | 0.000207 |
| conditional_blowout_calibration_xg_diff>=1.5 | 0.993752 | 0.590615 | 0.335897 | 0.484615 | 0.025417 | 0.026651 | 0.000128 | 0.000059 |
