# Score Tail Calibration Report

Dataset: FIFA World Cup + UEFA Euro neutral matches, FIFA + historical national team universe.

Model: `final_worldcup_model_v1_candidate`, domination disabled / 100% normal xG.

## Tail Calibration

- Actual GD >= 3 rate: `0.164103`
- Predicted GD >= 3 probability: `0.137631`
- Actual total goals >= 4 rate: `0.282051`
- Predicted total goals >= 4 probability: `0.281544`
- Actual favorite wins by 3+ rate: `0.140171`
- Predicted favorite wins by 3+ probability: `0.112465`
- Actual avg total goals: `2.725641`
- Predicted avg total goals: `2.657145`

## Missed Blowouts

- Actual blowout matches: `192`
- Missed Top-3 count: `186`
- Missed Top-5 count: `177`

## Calibration Buckets

| Predicted GD>=3 bucket | Matches | Predicted Avg | Actual Rate | Actual - Predicted |
| --- | ---: | ---: | ---: | ---: |
| 0-5% | 0 | 0.000000 | 0.000000 | 0.000000 |
| 5-10% | 0 | 0.000000 | 0.000000 | 0.000000 |
| 10-20% | 1081 | 0.127722 | 0.160037 | 0.032315 |
| 20-30% | 69 | 0.231760 | 0.217391 | -0.014369 |
| 30%+ | 20 | 0.348495 | 0.200000 | -0.148495 |

## Diagnostic Conclusions

- Systematically underestimates blowouts: `True`
- Systematically underestimates high-total-goals matches: `False`
- Recommended next step: Research fat-tail score distribution diagnostics before changing formulas.

Exact 4-0 / 5-0 style scorelines are sparse and high variance, so individual missed scorelines should be interpreted through aggregate tail calibration rather than treated as standalone proof that a new amplifier is needed.
