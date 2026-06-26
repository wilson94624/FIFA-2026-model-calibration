# Frozen Prediction Availability Audit

Status: research-only data availability audit.

This audit checks whether the Calibration Lab currently contains a historical frozen prediction dataset that can support an `Absence Signal Calibration Benchmark`.

No model was created, no calibration was run, no new predictions were generated, and no FIFA Predictor 4.0 files were modified.

## Executive Conclusion

The Calibration Lab does **not** currently contain the core frozen prediction dataset needed for injury / absence signal calibration.

Current assets contain:

- Actual historical match results.
- Rebuilt Elo features.
- Several benchmark summary outputs.
- One ELO-only post-hoc prediction output.
- One PQS shadow drift output.
- Static team and player PQS snapshots.

Current assets do **not** contain a complete dataset with all three required components:

```text
Frozen Predictions
+
Actual Results
+
Absence Features
```

Final readiness classification:

```text
C. Missing core Frozen Prediction Dataset
```

The most important missing asset is a match-level frozen prediction table with `prediction_timestamp`, W/D/L probabilities, actual result linkage, and absence features captured before prediction time.

## 1. Search Scope

The audit searched the Calibration Lab repository for:

- `prediction`
- `predictions`
- `backtest`
- `benchmark`
- `simulation`
- `evaluation`
- `snapshot`
- `absence`
- `injury`
- `unavailable`
- `frozen`
- `residual`
- CSV / JSON / parquet / database-style files

No parquet, SQLite, DB, pickle, or feather prediction stores were found in the Calibration Lab repository.

## 2. Candidate Prediction Assets

### Match-Level Or Prediction-Like Files

| File | Path | Format | Rows | What It Contains | Key Limitation |
| --- | --- | ---: | ---: | --- | --- |
| ELO baseline predictions | `results/elo_baseline_predictions.csv` | CSV | 49,449 | Post-hoc ELO-only probabilities and actual labels | No `match_id`, no `match_date`, no `prediction_timestamp`, not frozen |
| PQS shadow benchmark | `results/pqs_shadow_benchmark.csv` | CSV | 220 | 44 matches x 5 PQS weights; xG and W/D/L drift | Shadow drift only; no actual result fields in file; no absence data; not frozen |
| PQS shadow benchmark | `results/pqs_shadow_benchmark.json` | JSON | 220 rows | Same PQS shadow rows plus metadata | Inputs show `unavailable_players: null`; fixture source points to `/tmp/...`, not a repository asset |
| PQS shadow QA | `results/pqs_shadow_qa_report.json` | JSON | 6 | Hand-reviewed largest PQS drift matches | QA subset only, not a prediction dataset |
| Elo-to-xG benchmark samples | `results/elo_to_xg_benchmark.json` | JSON | 3 x 20 sample predictions | Small sample predictions for three Elo sources | Sample only; not complete; not frozen |
| Score-tail missed blowout diagnostics | `results/score_tail_calibration_report.json` | JSON | 186 top-3 misses, 177 top-5 misses | Diagnostic match slices with actual score and scoreline probabilities | Diagnostic subset only; no full W/D/L prediction table |

### Actual-Result And Feature Assets

| File | Path | Format | Rows | What It Contains | Prediction Status |
| --- | --- | ---: | ---: | --- | --- |
| Rebuilt match/Elo history | `data/processed/matches_with_elo.csv` | CSV | 49,449 | `match_id`, date, teams, scores, standard Elo features | Actual-result feature table, not predictions |
| Team snapshot | `data/processed/teams_db_snapshot.csv` | CSV | 48 | Static 2026-style team PQS snapshot | Team snapshot only |
| Player ratings | `data/processed/player_ratings.csv` | CSV | 1,248 | Static 2026-style player ratings | Player ratings only |
| Team name mapping | `data/processed/team_name_mapping.csv` | CSV | 106 | Team-key mapping | Mapping only |
| Team universe | `data/processed/team_universe.csv` | CSV | 336 | FIFA / historical / excluded team universe | Filter metadata only |

### Aggregate Benchmark Outputs

These files contain aggregate metrics, search rows, or research summaries. They are useful research artifacts, but they are not match-level frozen prediction datasets.

| File | Format | Rows | Notes |
| --- | ---: | ---: | --- |
| `results/k_factor_results.csv` / `.json` | CSV / JSON | 7 | K-factor tuning metrics |
| `results/home_advantage_results.csv` / `.json` | CSV / JSON | 7 | Home-advantage metrics |
| `results/tournament_weight_grid_results.csv` / `.json` | CSV / JSON | 48 | Tournament-weight grid metrics |
| `results/goal_diff_multiplier_results.csv` / `.json` | CSV / JSON | 4 | Goal-difference multiplier metrics |
| `results/gd_shrinkage_results.csv` / `.json` | CSV / JSON | 5 | Goal-difference shrinkage metrics |
| `results/time_split_validation.csv` / `.json` | CSV / JSON | 2 | Train/validation aggregate metrics |
| `results/time_split_shrinkage_validation.csv` / `.json` | CSV / JSON | 8 | Shrinkage validation aggregate metrics |
| `results/tournament_split_v3_validation.csv` / `.json` | CSV / JSON | 15 | Tournament split aggregate metrics |
| `results/world_cup_subset_benchmark.csv` / `.json` | CSV / JSON | 10 | Major tournament aggregate metrics |
| `results/universe_benchmark.csv` / `.json` | CSV / JSON | 6 | Universe aggregate metrics |
| `results/elo_benchmark_report.csv` / `.json` | CSV / JSON | 2 / summary | Elo benchmark summary |
| `results/elo_to_xg_benchmark.csv` / `.json` | CSV / JSON | 3 / samples | xG benchmark metrics plus 20-row samples per model |
| `results/neutral_xg_benchmark.csv` / `.json` | CSV / JSON | 12 | Neutral xG aggregate metrics |
| `results/worldcup_xg_parameter_search.csv` / `.json` | CSV / JSON | 125 | xG search metrics |
| `results/worldcup_xg_fine_search.csv` / `.json` | CSV / JSON | 60 | xG fine-search metrics |
| `results/worldcup_euro_xg_split_validation.csv` / `.json` | CSV / JSON | 6 | xG split aggregate metrics |
| `results/dixon_coles_rho_search.csv` / `.json` | CSV / JSON | 7 | Rho search metrics |
| `results/bivariate_gamma_search.csv` / `.json` | CSV / JSON | 8 | Gamma search metrics |
| `results/final_worldcup_model_benchmark.csv` / `.json` | CSV / JSON | 4 | Final model aggregate metrics |
| `results/domination_layer_benchmark.csv` / `.json` | CSV / JSON | 6 | Domination aggregate metrics |
| `results/domination_layer_extended_benchmark.csv` / `.json` | CSV / JSON | 6 | Extended score metrics |
| `results/margin_tail_modeling_research.csv` / `.json` | CSV / JSON | 12 | Margin-tail aggregate metrics |
| `results/margin_tail_fine_search.csv` / `.json` | CSV / JSON | 60 | Margin-tail split metrics |
| `results/elo_mismatch_conditional_tail_benchmark.csv` / `.json` | CSV / JSON | 357 | Conditional tail benchmark metrics |
| `results/negative_binomial_feasibility_benchmark.csv` / `.json` | CSV / JSON | 266 | Negative Binomial benchmark metrics |

None of these aggregate benchmark outputs records a complete match-level frozen prediction history with prediction timestamp and absence features.

## 3. Required Prediction Fields Audit

Required fields for Absence Signal Calibration:

```text
match_id
match_date
home_team
away_team
home_win_prob
draw_prob
away_win_prob
```

### `results/elo_baseline_predictions.csv`

Actual fields:

```text
home_team
away_team
home_score
away_score
home_pre_match_elo
away_pre_match_elo
home_xg
away_xg
prob_home
prob_draw
prob_away
predicted_label
actual_label
```

Field mapping:

| Required Field | Available? | Actual Field |
| --- | --- | --- |
| `match_id` | No | Missing |
| `match_date` | No | Missing |
| `home_team` | Yes | `home_team` |
| `away_team` | Yes | `away_team` |
| `home_win_prob` | Yes | `prob_home` |
| `draw_prob` | Yes | `prob_draw` |
| `away_win_prob` | Yes | `prob_away` |

Assessment:

This is the closest file to a full match-level prediction table, but it is not sufficient for frozen absence calibration because it lacks `match_id`, `match_date`, prediction timestamp, model run timestamp, and absence features. It also appears to be a post-hoc Calibration Lab output generated from historical data, not a pre-match frozen prediction archive.

### `results/pqs_shadow_benchmark.csv`

Actual fields:

```text
match_id
team_a
team_b
pqs_weight
baseline_team_a_xg
baseline_team_b_xg
pqs_team_a_xg
pqs_team_b_xg
team_a_xg_delta
team_b_xg_delta
baseline_home_or_team_a_win_prob
pqs_home_or_team_a_win_prob
win_prob_delta
draw_prob_delta
low_score_prob_delta
score_matrix_mean_abs_delta
pqs_data_status
warnings
```

Field mapping:

| Required Field | Available? | Actual Field |
| --- | --- | --- |
| `match_id` | Yes | `match_id` |
| `match_date` | No in file | Joinable from `matches_with_elo.csv` |
| `home_team` | Partial | `team_a` |
| `away_team` | Partial | `team_b` |
| `home_win_prob` | Partial | `baseline_home_or_team_a_win_prob`, `pqs_home_or_team_a_win_prob` |
| `draw_prob` | No full probability | Only `draw_prob_delta` |
| `away_win_prob` | No | Missing |

Additional audit:

- Rows: 220
- Unique matches: 44
- PQS weights: `0.00`, `0.10`, `0.20`, `0.25`, `0.30`
- All 44 unique `match_id` values can join to `data/processed/matches_with_elo.csv`
- Joined actual-result rows exist for 44 matches
- The JSON metadata records:

```text
unavailable_players: null
match_roster: null
fatigue_state: null
fixtures: /tmp/pqs_shadow_worldcup_fixtures.csv
```

Assessment:

This is a shadow drift output, not a frozen historical prediction dataset. It does not contain real absence features. It also does not include full W/D/L probabilities needed for calibration.

### `results/elo_to_xg_benchmark.json`

Nested sample prediction fields:

```text
match_id
date
home_team
away_team
home_score
away_score
predicted_home_xg
predicted_away_xg
home_win_probability
draw_probability
away_win_probability
```

Assessment:

This file contains useful 20-row samples for each of three Elo sources. It is not a full dataset and cannot support calibration.

## 4. Actual Result Linkage Audit

### Strong Actual Result Source

`data/processed/matches_with_elo.csv` contains:

```text
match_id
date
home_team
away_team
home_score
away_score
tournament
neutral
actual_home_score
actual_away_score
```

Rows:

```text
49,449
```

This is the canonical actual-result table in the Calibration Lab.

### Can Prediction Outputs Join To Actual Results?

| Prediction-Like Asset | Direct Actual Fields? | Joinable To Actual Results? | Notes |
| --- | --- | --- | --- |
| `results/elo_baseline_predictions.csv` | Yes, scores and `actual_label` | Not cleanly; no `match_id` or date | Could attempt fuzzy join by teams + scores + order, but this is risky |
| `results/pqs_shadow_benchmark.csv` | No | Yes, by `match_id` | 44 unique matches join to `matches_with_elo.csv` |
| `results/elo_to_xg_benchmark.json` samples | Yes | Yes, sample rows include `match_id` | Sample only |
| Aggregate benchmark outputs | Aggregate actual metrics only | No match-level join | Not suitable |

## 5. Absence Feature Linkage Audit

The repository currently has schemas and static PQS data, but no populated match-level absence feature table.

Found:

```text
data/schema/unavailable_players_schema.csv
data/schema/match_roster_schema.csv
data/schema/fatigue_state_schema.csv
data/processed/teams_db_snapshot.csv
data/processed/player_ratings.csv
data/processed/team_name_mapping.csv
```

Not found:

```text
data/processed/unavailable_players.csv
data/processed/match_roster.csv
data/processed/fatigue_state.csv
data/processed/player_absence_features.csv
data/processed/match_level_absence_features.csv
results/frozen_baseline_residuals.csv
results/absence_signal_features.csv
```

Keyword search did not find repository files for:

- Transfermarkt raw injury parser output
- Player absence dataset MVP output
- National-team absence proxy benchmark output
- Match-level absence feature output
- Frozen baseline residual benchmark output

The current PQS shadow output explicitly reports no unavailable-player input:

```text
unavailable_players: null
```

Therefore:

```text
Prediction + Actual Result + Absence Features = not currently available
```

## 6. Frozen Status Evaluation

To qualify as frozen prediction data, a dataset should prove that predictions were produced before match results were known.

Minimum frozen proof fields:

```text
prediction_id
model_version
prediction_timestamp
input_snapshot_id
input_snapshot_timestamp
match_id
match_date or kickoff_time
home_team
away_team
home_win_prob
draw_prob
away_win_prob
```

Nice-to-have fields:

```text
source_commit
data_version
run_id
created_at
fetched_at
features_hash
prediction_payload_hash
```

### Asset-Level Frozen Assessment

| Asset | Frozen Status | Reason |
| --- | --- | --- |
| `results/elo_baseline_predictions.csv` | Not frozen / cannot prove frozen | No `prediction_timestamp`; generated from historical data; no input snapshot metadata |
| `results/pqs_shadow_benchmark.csv` | Not frozen / shadow output | No prediction timestamp in output; generated as research drift; no real unavailable-player input |
| `results/elo_to_xg_benchmark.json` samples | Not frozen | Benchmark sample predictions generated from historical data |
| Aggregate benchmark files | Not frozen | Store aggregate research metrics, not pre-match predictions |
| `data/processed/matches_with_elo.csv` | Not predictions | Historical results and features |

Conclusion:

No current asset can prove:

```text
Prediction was produced before the match result was known.
```

Most prediction-like assets appear to be post-hoc research outputs regenerated from historical results and calibrated features.

## 7. Data Quantity Evaluation

### Total Prediction-Like Rows

| Asset | Rows | Interpretation |
| --- | ---: | --- |
| `results/elo_baseline_predictions.csv` | 49,449 | Full post-hoc ELO-only prediction table, not frozen |
| `results/pqs_shadow_benchmark.csv` | 220 | 44 matches x 5 PQS weights, shadow drift only |
| `results/elo_to_xg_benchmark.json` sample predictions | 60 | 20 sample rows x 3 Elo sources |

### Rows With Actual Result Linkage

| Asset | Rows / Matches | Actual Result Linkage |
| --- | ---: | --- |
| `results/elo_baseline_predictions.csv` | 49,449 rows | Contains `home_score`, `away_score`, `actual_label`; lacks `match_id` and date |
| `results/pqs_shadow_benchmark.csv` | 44 unique matches | All 44 unique `match_id` values join to `matches_with_elo.csv` |
| `results/elo_to_xg_benchmark.json` samples | 60 sample rows | Contains scores and `match_id` |

### Rows With Absence Feature Linkage

| Asset | Rows / Matches | Absence Feature Linkage |
| --- | ---: | --- |
| `results/elo_baseline_predictions.csv` | 0 | No absence fields |
| `results/pqs_shadow_benchmark.csv` | 0 | `unavailable_players: null`; no real absence features |
| `results/elo_to_xg_benchmark.json` samples | 0 | No absence fields |
| `data/processed/matches_with_elo.csv` | 0 | No absence fields |

Estimated usable rows for Absence Signal Calibration:

```text
0
```

## 8. Can The Current Assets Support Absence Signal Calibration?

### Required Dataset Shape

The benchmark needs a table at this granularity:

```text
one row per frozen prediction per match
```

Minimum fields:

```text
prediction_id
prediction_timestamp
model_version
match_id
match_date
home_team
away_team
home_win_prob
draw_prob
away_win_prob
home_goals
away_goals
actual_result
absence_feature_version
home_absence_features
away_absence_features
```

Recommended explicit absence features:

```text
home_missing_starter_count
away_missing_starter_count
home_missing_star_count
away_missing_star_count
home_missing_gk
away_missing_gk
home_absence_attack_impact
away_absence_attack_impact
home_absence_defense_impact
away_absence_defense_impact
home_total_absence_impact
away_total_absence_impact
absence_reported_at_max
absence_source_count
```

### Current Readiness

| Requirement | Current Status |
| --- | --- |
| Frozen W/D/L predictions | Missing |
| Actual results | Available |
| Absence features | Missing |
| Match IDs | Available in `matches_with_elo`, missing in `elo_baseline_predictions` |
| Prediction timestamp | Missing |
| Model version per prediction | Missing in match-level prediction output |
| Input snapshot ID | Missing in match-level prediction output |
| Injury / absence timestamp | Missing |
| Period-correct player data | Missing for historical validation |

## 9. Answer To Readiness Question

### Classification

```text
C. Missing core Frozen Prediction Dataset
```

### Reason

The repository does not currently contain a historical frozen prediction table that can be joined to both:

```text
Actual Results
+
Absence Features
```

The closest assets are:

1. `results/elo_baseline_predictions.csv`
   - Has probabilities and actual results.
   - Missing `match_id`, `match_date`, frozen timestamp, model snapshot metadata, and absence features.

2. `results/pqs_shadow_benchmark.csv`
   - Has `match_id` and shadow drift.
   - Can join to actual results for 44 matches.
   - Does not contain full W/D/L probabilities.
   - Does not contain actual absence features.
   - Is not frozen.

3. `data/processed/matches_with_elo.csv`
   - Has actual results and stable match IDs.
   - Not a prediction file.

## 10. Most Critical Missing Data

The single most critical missing dataset is:

```text
frozen_predictions.csv
```

Recommended minimum schema:

```text
prediction_id
prediction_timestamp
model_version
model_family
input_snapshot_id
feature_snapshot_id
match_id
match_date
home_team
away_team
home_win_prob
draw_prob
away_win_prob
home_xg
away_xg
score_matrix_json
prediction_source
created_at
notes
```

The second most critical missing dataset is:

```text
match_level_absence_features.csv
```

Recommended minimum schema:

```text
match_id
feature_snapshot_id
feature_timestamp
home_team
away_team
home_absence_count
away_absence_count
home_missing_starter_count
away_missing_starter_count
home_missing_star_count
away_missing_star_count
home_missing_gk
away_missing_gk
home_absence_attack_impact
away_absence_attack_impact
home_absence_defense_impact
away_absence_defense_impact
home_total_absence_impact
away_total_absence_impact
max_reported_at
source_count
coverage_status
notes
```

These two datasets should then join to:

```text
data/processed/matches_with_elo.csv
```

for actual results.

## 11. Final Answer

Current state:

```text
Prediction: partial, post-hoc, not frozen
Actual Result: yes
Absence Features: no
```

Therefore the Calibration Lab does **not** yet have the combined dataset required for:

```text
Absence Signal Calibration Benchmark
```

Most critical missing data:

```text
Historical frozen match-level predictions with prediction_timestamp and model/input snapshot metadata.
```

Second critical missing data:

```text
Match-level absence features with time-safe reported_at / feature_timestamp fields.
```

Recommended next step:

Do not start calibration yet. First build a frozen prediction inventory format and decide whether the benchmark will use:

1. A future 2026 shadow-mode frozen prediction archive, or
2. A reconstructed historical baseline explicitly labeled as post-hoc and not frozen.

Only option 1 can support a strict frozen-prediction absence calibration claim.

---

## Final Decision

Final decision: the current lab cannot support absence signal calibration yet.

Adopt as a requirement for v5: a frozen prediction archive with `prediction_timestamp`, model version, input snapshot metadata, W/D/L probabilities, and actual-result linkage.

Do not adopt a fixed injury or absence coefficient from the current data. The repository has useful static PQS assets, but it does not have time-safe match-level absence features or frozen historical predictions.

Future research should start with Injury / Availability Information Layer and Shadow Mode, then use Dynamic Team PQS only after the missing frozen prediction and absence datasets exist.
