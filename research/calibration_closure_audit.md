# Calibration Closure Audit

Status: research-only closure audit.

This document summarizes the current state of the FIFA-2026-model-calibration lab and decides whether the calibration phase can close.

Constraints honored:

- No new model was added.
- No calibration was re-run.
- No predictions were generated.
- No FIFA Predictor 4.0 code was modified.
- No formal model formula was modified.
- No data files were modified.
- No git operation was performed.

## 1. Research Inventory

### Primary Research Documents

| Document | Research Topic | Core Conclusion | Impacts Formal Model? | Useful For 4.0 / 5.0? |
| --- | --- | --- | --- | --- |
| `README.md` | English project summary and roadmap | Current recommended World Cup candidate is calibrated Elo v3 + neutral xG + rho 0.05 + gamma 0.08, with Raw PQS and Domination disabled. | Documentation only | Yes, integration reference |
| `README_zh.md` | Chinese project summary and roadmap | Same as English README, with clearer research motivation and phase narrative. | Documentation only | Yes, communication / planning |
| `research/00-overview.md` | Calibration Lab purpose | The lab exists to test which intuitive football features actually improve probability calibration. | No direct formula change | Yes, product philosophy |
| `research/01-elo-calibration.md` | Elo calibration | Elo calibration is complete enough for the current candidate; recommended Elo candidate uses K=80 and goal-difference shrinkage alpha=0.10. | Yes, candidate parameter basis | Yes, 4.0 candidate / 5.0 baseline |
| `research/02-xg-calibration.md` | Elo-to-xG calibration | xG calibration is the largest improvement layer; World Cup mode should use neutral xG with base=1.35, c1=1.30, scale=600. | Yes, candidate parameter basis | Yes, 4.0 candidate / 5.0 baseline |
| `research/03-dixon-coles-gamma.md` | Dixon-Coles rho and Bivariate Poisson gamma | rho=0.05 and gamma=0.08 provide small but consistent calibration improvement. | Yes, candidate parameter basis | Yes, final World Cup candidate |
| `research/04-pqs-shadow-study.md` | Raw PQS shadow benchmark | Raw PQS overlaps Elo strongly and should not become a main team-strength feature. | No formal model change | Yes, defines PQS limits |
| `research/05-domination-layer-study.md` | Domination branch benchmark | Domination hurts LogLoss/Brier and only slightly helps Top-3/Top-5 correct score; keep disabled. | Yes, negative decision | Yes, remove / disable guidance |
| `research/06-score-tail-calibration.md` | Score-tail and margin-tail research | GD>=3 is underpredicted, but global tail correction is unstable across splits. | No formal model change | Yes, diagnostics only |
| `research/07-poisson-distribution-research.md` | Poisson limits and MAX_GOALS diagnostics | MAX_GOALS truncation is not the main issue; keep Poisson baseline while researching distribution shape. | No formal model change | Yes, benchmark guardrails |
| `research/08-injury-aware-pqs-design.md` | Injury / Availability design | Injury / availability may provide new signal, but requires time-safe data and must begin as Information Layer and Shadow Mode. | No formal model change | Yes, 5.0 research |
| `research/09-future-work.md` | Future research priorities | Best future value is new information, not another strength amplifier. Prioritize Dynamic Team PQS, host advantage, fatigue/style data readiness, and distribution monitoring. | No direct change | Yes, 5.0 roadmap |
| `research/10-score-distribution-and-model-limits.md` | Score distribution and model limits | Correct score is intrinsically high variance; do not overfit global model to rare 5-0 / 7-1 cases. | No formal model change | Yes, product framing |
| `research/frozen_prediction_availability_audit.md` | Frozen prediction availability | The lab lacks a core frozen prediction dataset for absence signal calibration. | No formal model change | Yes, data platform requirement |

### Result Reports And Supporting Artifacts

| Files | Research Topic | Core Conclusion | Impacts Formal Model? | Useful For 4.0 / 5.0? |
| --- | --- | --- | --- | --- |
| `results/elo_benchmark_report.*`, `results/time_split_validation.*`, `results/time_split_shrinkage_validation.*`, `results/tournament_split_v3_validation.*` | Elo benchmark and validation | Calibrated Elo improves LogLoss/Brier; v3 shrinkage is the practical candidate because v2 expands Elo scale too much. | Yes, candidate basis | Yes |
| `results/k_factor_results.*`, `results/goal_diff_multiplier_results.*`, `results/gd_shrinkage_results.*`, `results/home_advantage_results.*`, `results/tournament_weight_grid_results.*` | Elo parameter studies | K=80 and shrinkage are useful; tournament weights did not improve; home advantage helps general international data but is disabled for neutral World Cup mode. | Yes, mostly negative / constrained decisions | Yes |
| `results/elo_to_xg_benchmark.*`, `results/xg_parameter_search.*`, `results/neutral_xg_benchmark.*`, `results/worldcup_xg_parameter_search.*`, `results/worldcup_xg_fine_search.*`, `results/worldcup_euro_xg_split_validation.*` | xG calibration | Neutral World Cup xG is preferred for World Cup / Euro neutral matches. | Yes, candidate basis | Yes |
| `results/dixon_coles_rho_search.*`, `results/bivariate_gamma_search.*` | Low-score and shared-goal calibration | rho=0.05 and gamma=0.08 are retained; improvements are small. | Yes, candidate basis | Yes |
| `results/final_worldcup_model_benchmark.*` | Final World Cup benchmark | Full candidate improves over baseline_current: Accuracy +0.047009, LogLoss +0.028380, Brier +0.021075. | Yes, final candidate evidence | Yes |
| `results/pqs_data_readiness_report.*`, `results/pqs_shadow_benchmark.*`, `results/pqs_shadow_qa_report.*` | PQS readiness, shadow drift, QA | Raw PQS is shadow-only; correlation with Elo is about 0.75 and sign agreement about 84%; future use should be injury / availability correction. | No formal model change | Yes, 5.0 PQS architecture |
| `results/injury_aware_pqs_mvp_feasibility.md`, `results/injury_data_source_audit.md` | Injury / Availability feasibility and data audit | Current data is not enough for historical injury calibration; 2026 Shadow Mode is feasible if availability data is captured time-safely. | No formal model change | Yes, 5.0 data planning |
| `results/domination_layer_benchmark.*`, `results/domination_layer_extended_benchmark.*` | Domination benchmark | 100% normal xG is best for LogLoss/Brier/GD MAE; domination gains in Top-3/Top-5 are too tiny to justify formal inclusion. | Yes, negative decision | Yes |
| `results/score_tail_calibration_report.*`, `results/score_distribution_diagnostics.*`, `results/large_margin_frequency_report.*` | Score-tail diagnostics | Total goals tail is calibrated reasonably; GD>=3 is underpredicted; large margins cluster in mismatch / early World Cup contexts. | No formal model change | Yes, diagnostics |
| `results/margin_tail_modeling_research.*`, `results/margin_tail_fine_search.*`, `results/elo_mismatch_conditional_tail_benchmark.*` | Margin-tail correction research | Global and conditional tail corrections are not stable enough across splits; keep baseline unchanged. | No formal model change | Yes, avoid overfitting |
| `results/negative_binomial_feasibility_benchmark.*` | Negative Binomial feasibility | NB helps some high-mismatch cases but worsens pooled LogLoss/Brier and Top-3; keep Bivariate Poisson baseline. | No formal model change | Yes, future research only |
| `results/fifa_team_filter_analysis.json`, `results/team_universe_report.json`, `results/universe_benchmark.*` | Team universe filtering | FIFA + historical national teams universe is the recommended calibration universe. | Yes, dataset policy | Yes |

### Not Found As Standalone Documents In This Repo

The prompt mentions completed work around Injury Information Layer, Dynamic Team PQS v5 design, and FIFA Predictor v5 product architecture. In the current Calibration Lab repository, no standalone files with those exact names were found. Their supporting evidence is present indirectly through:

- `research/08-injury-aware-pqs-design.md`
- `results/injury_aware_pqs_mvp_feasibility.md`
- `results/injury_data_source_audit.md`
- `research/frozen_prediction_availability_audit.md`
- `research/09-future-work.md`

Therefore this audit treats those as 5.0 planning directions supported by the Calibration Lab, not as already calibrated model components.

## 2. ELO Conclusion

Elo calibration can be considered complete for the current calibration phase.

Evidence:

- `standard_elo_v1` is a clean baseline, but it is weaker on probability calibration.
- K-factor tuning found much better calibration around K=80.
- Full log-margin goal-difference updates improved metrics but expanded the Elo scale too aggressively.
- Shrinkage alpha=0.10 gives a better tradeoff between calibration gain and rating scale stability.
- Tournament weighting did not beat the no-weight baseline.
- General home advantage helped all-international data, but is not included in neutral World Cup mode.

Recommended current Elo candidate:

```text
calibrated_elo_v3_candidate
K = 80
goal_diff_shrinkage_alpha = 0.10
home_advantage = 0 for neutral World Cup mode
tournament_weight = 1
```

Product readiness:

- Can enter 4.0 as a candidate or shadow/stable parameter set for World Cup mode.
- Can serve as the 5.0 baseline for future model versioning.
- Should not reopen calibration unless new dataset splits, host-advantage scope, or uncertainty modeling are introduced.

## 3. PQS Conclusion

Raw PQS should not become a main historical calibration factor.

Key findings:

- PQS and Elo overlap strongly.
- Pearson correlation is approximately 0.75.
- Sign agreement is approximately 84%.
- Raw PQS creates meaningful xG / WDL / score-matrix drift.
- Several largest-drift cases look like double-counting Elo rather than adding new information.
- `pqs_weight=0.30` is too aggressive for raw squad-quality adjustment.

Best current role:

```text
PQS -> injury / availability / depth correction layer
```

PQS is therefore better suited as a foundation for Dynamic Team PQS than as a direct model-strength coefficient.

Recommended product interpretation:

- Do not use Raw PQS in 4.0 Stable W/D/L probabilities.
- Keep PQS shadow reports and QA tools.
- Use player ratings, bench quality, and team snapshots as infrastructure for 5.0 Dynamic Team PQS.
- Require time-safe availability data before any injury-aware calibration claim.

## 4. xG / Score Model Conclusion

### xG

xG calibration has a clear enough conclusion for World Cup mode.

Recommended current xG candidate:

```text
calibrated_xg_worldcup_v1_candidate
mode = neutral
base = 1.35
c1 = 1.30
scale = 600
min_xg = 0.20
```

Why this is accepted:

- xG calibration contributed the largest LogLoss improvement in the final benchmark.
- Neutral xG avoids treating dataset ordering as a true home advantage in World Cup / Euro neutral matches.
- The candidate is stable enough for World Cup integration planning.

Remaining non-blocking research:

- Host / semi-home advantage for USA, Mexico, Canada, and geographically favorable matches.
- Era-specific goal environment.
- Style-aware xG only if reliable data becomes available.

### Poisson / Bivariate Poisson / Dixon-Coles / Gamma

Current retained score model:

```text
Neutral xG
-> Bivariate Poisson
-> Dixon-Coles rho = 0.05
-> Gamma = 0.08
-> Score matrix
```

Retain:

- Bivariate Poisson as the baseline score distribution.
- Dixon-Coles rho=0.05 as a small low-score correction.
- Gamma=0.08 as the current shared-goal component.

Do not promote:

- Domination branch.
- Global margin-tail correction.
- Elo-mismatch conditional tail correction.
- Negative Binomial replacement.

Reason:

- Domination worsened primary calibration metrics.
- Tail corrections improved some pooled tail metrics but failed split stability.
- Negative Binomial improved some high-mismatch slices but worsened pooled LogLoss/Brier and Top-3.
- Correct score remains high variance; product framing should emphasize probabilities and uncertainty, not exact-score certainty.

## 5. Injury / Availability Conclusion

Injury and availability are promising, but not ready as calibrated model coefficients.

Current data state:

- The lab has a 2026-style `teams_db_snapshot.csv`.
- The lab has `player_ratings.csv`.
- The lab has `team_name_mapping.csv`.
- The lab has schema and shadow framework support.

Missing core data:

- Match-level unavailable-player facts.
- `reported_at` timestamp per injury / availability fact.
- `prediction_timestamp` for evaluated fixtures.
- Period-correct historical squads and ratings.
- Expected starter / role context.
- Frozen predictions for absence residual calibration.

Current conclusion:

```text
Injury / availability should be an Information Layer first,
then a Dynamic Team PQS shadow input,
not a fixed global coefficient.
```

It should not enter 4.0 Stable as a calibrated coefficient. It can enter 5.0 Research as:

- Shadow-only availability capture.
- Injury-aware drift analysis.
- Dynamic Team PQS infrastructure.
- Manual QA and model explanation layer.

## 6. Fatigue / Style Conclusion

Fatigue and style should not continue as immediate calibration priorities.

### Fatigue

Why not now:

- Needs time-safe match schedules, travel/rest-day features, extra-time history, minutes, squad rotation, and bench-depth interaction.
- Existing lab does not contain a validated fatigue dataset.
- A formula without data readiness would likely become another unverified product heuristic.

Recommended status:

```text
Deferred to 5.0 Research after data readiness audit.
```

### Style

Why not now:

- Style labels are hard to define consistently.
- Current `teams_db_snapshot.csv` style metadata is static and not match-contextual.
- Style can easily become a narrative layer rather than a calibrated predictive signal.
- No benchmark currently proves style improves LogLoss/Brier.

Recommended status:

```text
Deferred. Use for explanation/UX only until a reliable style dataset exists.
```

## 7. 4.0 Stable Candidate Changes

These are safe candidates for FIFA Predictor 4.0 Stable because they either improve the World Cup model core or do not change the formal model.

### Model Candidate

```text
final_worldcup_model_v1_candidate
Elo = calibrated_elo_v3_candidate
xG = calibrated_xg_worldcup_v1_candidate
Dixon-Coles rho = 0.05
Bivariate Poisson gamma = 0.08
Domination = disabled
Raw PQS = disabled
Tournament weight = 1
Home advantage = disabled for neutral World Cup mode
```

Benchmark summary:

| Model | Accuracy | LogLoss | Brier |
| --- | ---: | ---: | ---: |
| baseline_current | 0.485470 | 1.022132 | 0.611690 |
| full_calibrated_worldcup_candidate | 0.532479 | 0.993752 | 0.590615 |

Improvement:

- Accuracy: +0.047009
- LogLoss: +0.028380
- Brier: +0.021075

### Non-Model Stable Candidates

- Documentation updates explaining what is and is not calibrated.
- Model version labels in prediction outputs.
- Snapshot archive for team/player inputs.
- Display-only injury / availability information with source timestamps.
- Shadow-mode comparison panels.
- QA reports for largest model deltas.
- Clear product language around uncertainty and correct-score variance.

## 8. 5.0 Research Candidate Changes

These should move into FIFA Predictor 5.0 planning, not immediate 4.0 Stable model defaults.

- Dynamic Team PQS as an availability/depth system.
- Injury Information Layer with `reported_at`, `prediction_timestamp`, source confidence, and player mapping.
- Frozen prediction archive and residual benchmark infrastructure.
- Model versioning and input snapshot hashing.
- Host / semi-home advantage benchmark for 2026 hosts.
- Fatigue data readiness and shadow benchmark.
- Style data readiness and shadow benchmark.
- Negative Binomial or alternative score distribution research for high-mismatch subsets only.
- Score-tail diagnostics for 2026 group-stage mismatch monitoring.
- Shadow Mode comparing old Predictor and calibrated World Cup mode side by side.

## 9. Abandoned / Deferred Ideas

### Not Recommended For Product Defaults

- Raw PQS as a main team-strength feature.
- Fixed global PQS weight.
- Fixed injury coefficient without time-safe validation data.
- Domination layer as a formal score-matrix component.
- Global margin-tail correction.
- Elo-mismatch conditional tail correction as production default.
- Negative Binomial replacement for Bivariate Poisson.
- Tournament weight multipliers from the tested grid.
- Style coefficient without reliable style data.
- Fatigue formula without validated rest/travel/minutes data.

### Deferred But Still Potentially Useful

- Host advantage for 2026.
- Dynamic Team PQS Shadow Mode.
- Availability/depth correction using Dynamic Team PQS.
- Score-tail monitoring for 48-team group-stage mismatches.
- Exact-score diagnostics as product explanation, not core optimization target.
- Elo uncertainty / confidence intervals.
- Era-specific score environment research.

## 10. Final Calibration Closure Decision

Decision:

```text
A. 可以收尾，進入 4.0 / 5.0 integration planning
```

Reasoning:

1. The core model layers have a clear candidate:
   - calibrated Elo v3
   - neutral World Cup xG
   - Dixon-Coles rho=0.05
   - gamma=0.08

2. The major tempting add-ons have been tested and mostly rejected:
   - Raw PQS
   - Domination
   - global tail correction
   - conditional tail correction
   - Negative Binomial replacement
   - tournament weights

3. The remaining open directions are data-product problems, not blockers for calibration closure:
   - injury / availability data capture
   - frozen prediction archive
   - Dynamic Team PQS design
   - host advantage data
   - fatigue/style data readiness

4. The lab has enough evidence to define what should enter a World Cup model candidate and what should stay out.

Final answer:

The calibration stage can formally close. The next phase should be integration planning:

- 4.0 Stable: adopt only the validated candidate core and safe non-model infrastructure.
- 5.0 Research: build Dynamic Team PQS, Injury Information Layer, frozen prediction archives, and shadow-mode evaluation.

Do not start another broad calibration loop unless a new time-safe dataset is added.

---

## Final Decision

Final decision:

```text
A. Close calibration and move into 4.0 / 5.0 integration planning.
```

Adopt for the current World Cup candidate: calibrated Elo v3, Neutral World Cup xG, Bivariate Poisson, Dixon-Coles `rho = 0.05`, and Gamma `0.08`.

Do not adopt: Raw PQS as a team-strength feature, Domination Layer, Global Tail Correction, Conditional Tail Correction, Negative Binomial replacement, Tournament Weight, fixed Injury Coefficient, Fatigue coefficient, or Style coefficient.

Future research should move to Dynamic Team PQS, Injury / Availability Information Layer, Shadow Mode, frozen prediction archives, Host Advantage, and data readiness for Fatigue and Style.
