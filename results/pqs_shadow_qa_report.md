# PQS Shadow QA Report
This report manually reviews the largest `pqs_weight=0.30` drift cases. It does not claim PQS calibration or predictive improvement.
## Context
- PQS vs Elo Pearson correlation: approximately `0.75`
- Sign agreement: approximately `84%`
- PQS creates material xG / WDL / score-matrix drift, but strongly overlaps Elo.
## Largest Drift Matches
### France vs Iraq
- Baseline xG: `2.192096 - 0.507904`
- PQS-adjusted xG: `2.382096 - 0.307237`
- xG delta: `+0.190000` / `-0.200667`
- Baseline W/D/L: `0.767944` / `0.164414` / `0.067642`
- PQS W/D/L: `0.844382` / `0.126706` / `0.028912`
- W/D/L delta: `+0.076438` / `-0.037708` / `-0.038730`
- Score matrix MAD: `0.007521`
- Boosted: `France`; Penalized: `Iraq`
- Football intuition: `reasonable_direction_but_high_double_counting_risk`
- Double-counting Elo risk: `high`
- Human review: `yes`
- Note: France receiving a boost and Iraq a penalty fits broad squad-quality intuition, but France is already heavily favored by Elo, so this looks like a likely double-counting case.
### Brazil vs Haiti
- Baseline xG: `2.274391 - 0.425609`
- PQS-adjusted xG: `2.456891 - 0.262038`
- xG delta: `+0.182500` / `-0.163571`
- Baseline W/D/L: `0.801229` / `0.14875` / `0.05002`
- PQS W/D/L: `0.863538` / `0.11509` / `0.021373`
- W/D/L delta: `+0.062308` / `-0.033661` / `-0.028648`
- Score matrix MAD: `0.006525`
- Boosted: `Brazil`; Penalized: `Haiti`
- Football intuition: `reasonable_direction_but_high_double_counting_risk`
- Double-counting Elo risk: `high`
- Human review: `yes`
- Note: Brazil boost versus Haiti penalty is intuitive, but the matchup is already structurally captured by Elo; PQS mostly amplifies an existing mismatch.
### Jordan vs Algeria
- Baseline xG: `0.896985 - 1.803015`
- PQS-adjusted xG: `0.719843 - 1.955792`
- xG delta: `-0.177143` / `+0.152778`
- Baseline W/D/L: `0.182227` / `0.226844` / `0.590929`
- PQS W/D/L: `0.125885` / `0.204216` / `0.669899`
- W/D/L delta: `-0.056342` / `-0.022628` / `+0.078969`
- Score matrix MAD: `0.005052`
- Boosted: `Algeria`; Penalized: `Jordan`
- Football intuition: `reasonable_direction`
- Double-counting Elo risk: `medium`
- Human review: `yes`
- Note: Algeria boost and Jordan penalty are plausible from squad-quality priors. Review needed because the drift is large and may over-penalize Jordan.
### Austria vs Jordan
- Baseline xG: `1.799367 - 0.900633`
- PQS-adjusted xG: `1.948367 - 0.726823`
- xG delta: `+0.149000` / `-0.173810`
- Baseline W/D/L: `0.589167` / `0.227296` / `0.183537`
- PQS W/D/L: `0.666559` / `0.205375` / `0.128066`
- W/D/L delta: `+0.077392` / `-0.021921` / `-0.055471`
- Score matrix MAD: `0.004939`
- Boosted: `Austria`; Penalized: `Jordan`
- Football intuition: `reasonable_direction`
- Double-counting Elo risk: `medium`
- Human review: `yes`
- Note: Austria boost and Jordan penalty are plausible, but Jordan appears repeatedly among largest penalties, suggesting a cap or injury-only rule may be safer.
### Belgium vs Iran
- Baseline xG: `1.643823 - 1.056177`
- PQS-adjusted xG: `1.832573 - 0.885224`
- xG delta: `+0.188750` / `-0.170952`
- Baseline W/D/L: `0.513382` / `0.24355` / `0.243068`
- PQS W/D/L: `0.600557` / `0.223509` / `0.175935`
- W/D/L delta: `+0.087175` / `-0.020042` / `-0.067133`
- Score matrix MAD: `0.00493`
- Boosted: `Belgium`; Penalized: `Iran`
- Football intuition: `plausible_but_potentially_excessive`
- Double-counting Elo risk: `high`
- Human review: `yes`
- Note: Belgium boost is plausible from player pool quality, but Iran penalty may be too broad without injury/availability evidence.
### Uzbekistan vs Colombia
- Baseline xG: `0.856332 - 1.843668`
- PQS-adjusted xG: `0.701332 - 2.01224`
- xG delta: `-0.155000` / `+0.168571`
- Baseline W/D/L: `0.167906` / `0.221605` / `0.610489`
- PQS W/D/L: `0.117087` / `0.197041` / `0.685871`
- W/D/L delta: `-0.050819` / `-0.024563` / `+0.075382`
- Score matrix MAD: `0.004673`
- Boosted: `Colombia`; Penalized: `Uzbekistan`
- Football intuition: `reasonable_direction`
- Double-counting Elo risk: `medium`
- Human review: `yes`
- Note: Colombia boost and Uzbekistan penalty align with squad-value intuition, but should be reviewed because PQS is likely acting as another team-strength proxy.
## Strongest Boost Teams
| Team | Matches | Avg xG Δ | Starting PQS | Bench PQS | Avg Overall | Stars |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Belgium | 2 | +0.177083 | 0.337273 | 0.284000 | 80.654 | 0 |
| Colombia | 1 | +0.168571 | 0.297273 | 0.258667 | 77.500 | 0 |
| Spain | 2 | +0.142381 | 0.364545 | 0.334667 | 84.731 | 0 |
| Germany | 2 | +0.136500 | 0.357273 | 0.320000 | 83.577 | 0 |
| France | 2 | +0.130000 | 0.367273 | 0.333333 | 84.769 | 0 |
| Brazil | 2 | +0.116500 | 0.363636 | 0.317333 | 83.692 | 0 |

## Strongest Penalty Teams
| Team | Matches | Avg xG Δ | Starting PQS | Bench PQS | Avg Overall | Stars |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Jordan | 2 | -0.175476 | 0.127273 | 0.070000 | 59.423 | 0 |
| Iraq | 2 | -0.156167 | 0.166364 | 0.042667 | 59.500 | 0 |
| Uzbekistan | 1 | -0.155000 | 0.134545 | 0.065333 | 59.462 | 0 |
| Haiti | 2 | -0.124286 | 0.192727 | 0.042667 | 60.615 | 0 |
| South Africa | 2 | -0.109107 | 0.181818 | 0.046667 | 60.385 | 0 |
| Iran | 2 | -0.096786 | 0.164545 | 0.088667 | 62.077 | 0 |

## QA Conclusions
- Reasonable drift cases: `Jordan vs Algeria`, `Austria vs Jordan`, `Uzbekistan vs Colombia`.
- Suspicious / likely double-counting cases: `France vs Iraq`, `Brazil vs Haiti`, `Belgium vs Iran`.
- `pqs_weight=0.30` should be treated as too aggressive for raw squad-quality adjustment.
- Future research should cap raw PQS lower, likely around `0.10-0.20`, unless injury/availability evidence justifies larger movement.
- The preferred future direction is injury-only or availability-aware PQS adjustment, not raw PQS as a main model feature.
- It is reasonable to begin designing injury / unavailable-player simulation, but not to claim PQS calibration.
