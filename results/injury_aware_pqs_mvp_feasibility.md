# Injury / Availability Dynamic Team PQS MVP Feasibility Study

This report is a research-only feasibility study for a future Injury / Availability layer and Dynamic Team PQS path. It does not modify the formal Predictor, does not tune PQS, and does not promote any injury / availability method to production.

## Executive Summary

Raw PQS should not be used as a main team-strength feature because prior shadow work found strong overlap with Elo:

- PQS vs Elo Pearson correlation: approximately `0.75`
- Sign agreement: approximately `84%`
- Raw PQS creates meaningful xG / WDL / score-matrix drift
- Raw PQS cannot currently be claimed to improve predictions

The most promising future role is narrower:

```text
PQS -> injury / availability correction layer
```

That means PQS should estimate how much a team is weakened relative to its own expected full-strength state, not how strong the team is globally. Elo and calibrated xG should remain the primary team-strength backbone.

## 1. What Existing `teams_db.json` Can Provide

The current converted `teams_db` snapshot already supports a useful static player-quality baseline:

- `snapshot_id`
- `snapshot_date`
- `team_key`
- `team_name`
- `has_data`
- `starting_pqs`
- `bench_pqs`
- `fifa_points`
- `style`
- `source`

Useful injury-aware signals:

- Team-level fallback quality through `starting_pqs`
- Team-level replacement depth through `bench_pqs`
- Team identity through stable `team_key`
- Tactical metadata through `style`, useful for QA but not required for MVP
- Snapshot provenance, which helps keep the benchmark reproducible

Limitations:

- It is a static snapshot, currently suitable for a 2026 World Cup shadow benchmark.
- It is not a match-specific injury report.
- It does not tell which players were expected starters for a specific fixture.
- It cannot safely evaluate older matches unless a period-correct snapshot exists.

## 2. What `player_ratings.csv` Can Provide

The current `player_ratings.csv` provides:

- `snapshot_id`
- `snapshot_date`
- `team_key`
- `player_id`
- `player_name`
- `position`
- `overall`
- `efficiency_score`
- `rating_source`
- `rating_timestamp`
- `is_in_squad_pool`

Useful injury-aware signals:

- Player-level quality through `efficiency_score`
- Position grouping through `position`
- Stable identity through `player_id`
- Rating timestamp for time-safety checks
- Squad-pool membership for 2026-style shadow scenarios

Most likely new signal beyond Elo:

- Absence of a high-efficiency player who was expected to play
- Replacement quality gap at the same position
- Goalkeeper-specific unavailability
- Thin bench depth when multiple starters are missing

Limitations:

- It does not say a player is injured, suspended, doubtful, or unavailable.
- It does not say whether the player was expected to start.
- It does not contain minutes expectation.
- It does not provide match-specific replacement hierarchy.

## 3. Current Injury-aware Critical Data Gaps

The current Calibration Lab is missing the key match-level inputs required to make Injury / Availability and Dynamic Team PQS reliable:

- Match-level unavailable players
- `reported_at` timestamp for every unavailable-player record
- Injury / suspension / illness reason
- Confidence level, such as confirmed vs doubtful
- Match-level roster or expected squad
- Starting XI or projected starters
- Bench / replacement options by position
- Goalkeeper starter and backup identification
- Match prediction timestamp
- Source provenance for each availability claim

Without these, the lab can produce drift simulations, but not credible injury-aware validation.

## 4. Minimum `unavailable_players` Schema

Recommended MVP schema:

```text
match_id
match_date
prediction_timestamp
team_key
player_id
player_name
position
expected_role
unavailable_reason
availability_status
status_confidence
reported_at
source
notes
```

Field purpose:

| Field | Required | Purpose |
| --- | --- | --- |
| `match_id` | yes | Join to fixture or match row. |
| `match_date` | yes | Basic temporal validation. |
| `prediction_timestamp` | yes | Defines what information was knowable. |
| `team_key` | yes | Join to team snapshot and player ratings. |
| `player_id` | strongly recommended | Stable match to player ratings. |
| `player_name` | yes | Human-readable fallback if player_id is unavailable. |
| `position` | yes | Needed for attack / defense / goalkeeper impact. |
| `expected_role` | yes for MVP | `starter`, `rotation`, `bench`, `squad`, or `unknown`. |
| `unavailable_reason` | yes | Injury, suspension, illness, personal, not selected, unknown. |
| `availability_status` | yes | Out, doubtful, questionable, available, unknown. |
| `status_confidence` | yes | Confirmed, probable, uncertain. |
| `reported_at` | yes | Prevents look-ahead bias. |
| `source` | yes | Source URL, feed, manual research, or internal note. |
| `notes` | no | Context, injury type, ambiguity. |

The current `data/schema/unavailable_players_schema.csv` is a good starting point, but MVP should add `prediction_timestamp`, `position`, `expected_role`, and `availability_status`.

## 5. Is Starting XI Necessary?

Starting XI is not strictly required for MVP, but some role estimate is required.

Minimum acceptable alternative:

```text
expected_role = starter | rotation | bench | squad | unknown
```

Why this matters:

- A missing regular starter should affect xG more than a missing deep bench player.
- A missing star who was not expected to start should not receive full starter impact.
- Without role, the model may overstate injuries to famous substitutes or understate injuries to quiet but essential starters.

MVP can start without confirmed XI if it has projected starter / rotation labels. Confirmed XI should be treated as optional and only usable if it was available before `prediction_timestamp`.

## 6. Is Bench Depth Necessary?

Bench depth is strongly recommended, but not absolutely required for the first MVP.

Without bench depth:

- Injury impact can only measure missing-player quality.
- Strong teams with deep squads may be over-penalized.
- Replacement quality is invisible.

With bench depth:

```text
net_injury_impact = missing_player_quality - replacement_player_quality
```

This is the most important way to avoid overreacting to injuries for teams like France, Brazil, Spain, Germany, or England.

MVP fallback if no explicit depth chart exists:

- Use all available players at the same position.
- Sort by `efficiency_score`.
- Treat the highest-rated non-unavailable non-starter as the replacement candidate.
- Mark output with `replacement_inferred = TRUE`.

## 7. How To Avoid Look-ahead Bias

Core rule:

```text
snapshot_date <= match_date
rating_timestamp <= prediction_timestamp
reported_at <= prediction_timestamp
```

Do not use:

- 2026 squad data to evaluate 2024 matches.
- Confirmed lineup if it was published after the prediction timestamp.
- Injury news published after kickoff.
- Player ratings updated after the tournament to evaluate earlier matches.
- Tournament performance information from later matches.

If no time-safe player snapshot or injury report exists, the match should be marked:

```text
missing_injury_data
```

and excluded from injury-aware validation claims.

## 8. Minimum Viable MVP Fields

The smallest viable Injury / Availability Dynamic Team PQS MVP requires:

### Fixture / Match List

```text
match_id
match_date
prediction_timestamp
team_a
team_b
team_a_key
team_b_key
team_a_pre_match_elo
team_b_pre_match_elo
```

### Player Ratings

```text
snapshot_id
snapshot_date
rating_timestamp
team_key
player_id
player_name
position
efficiency_score
is_in_squad_pool
```

### Unavailable Players

```text
match_id
team_key
player_id
player_name
position
expected_role
availability_status
unavailable_reason
reported_at
source
```

### Team Mapping

```text
source_team_name
source_system
team_key
teams_db_name
mapping_confidence
valid_from
valid_to
```

Optional but useful:

```text
bench_pqs
starting_pqs
projected_replacement_player_id
lineup_confirmed
status_confidence
```

## 9. What MVP Can Do

The MVP can support a shadow-only injury-aware benchmark:

- Identify unavailable players before a match.
- Estimate missing attacking, defensive, and goalkeeper quality.
- Apply conservative xG deltas on top of `final_worldcup_model_v1_candidate`.
- Compare baseline vs injury-aware xG, W/D/L probability, draw probability, and score matrix drift.
- Produce QA reports for largest injury-driven changes.
- Test whether injury reports add signal that Raw PQS did not.

Recommended MVP output:

```text
match_id
team_a
team_b
baseline_team_a_xg
baseline_team_b_xg
injury_adjusted_team_a_xg
injury_adjusted_team_b_xg
team_a_xg_delta
team_b_xg_delta
affected_players
replacement_inferred
data_quality_status
warnings
```

## 10. What MVP Cannot Do

The MVP cannot honestly claim:

- Raw PQS is calibrated.
- Injury / Availability Dynamic Team PQS improves prediction accuracy.
- A global PQS weight is optimal.
- Historical validation is reliable without period-correct injury data.
- Replacement quality is accurate without roster or depth information.
- Late-breaking lineup news is safe unless timestamped before prediction.

The MVP should not:

- Replace Elo.
- Replace calibrated neutral xG.
- Use raw squad PQS as a main strength feature.
- Backfill missing injuries with assumptions.
- Treat missing injury data as full-strength certainty.

## Proposed MVP Injury Impact Logic

Research-only first version:

```text
player_absence_impact =
    role_weight
  * position_weight
  * efficiency_score
  * status_confidence_weight
```

Suggested conservative role weights:

```text
starter = 1.00
rotation = 0.60
bench = 0.25
unknown = 0.40
```

Suggested position handling:

- Forward / attacking midfielder absence: reduce own attacking xG.
- Defender / defensive midfielder absence: increase opponent xG.
- Goalkeeper absence: special case; increase opponent xG only.

Suggested caps:

```text
max_attack_xg_delta_per_team = 0.20
max_defense_xg_delta_per_team = 0.20
max_goalkeeper_xg_delta = 0.15
max_total_injury_xg_delta_per_team = 0.30
```

These caps are intentionally small because Elo and calibrated xG already capture most team strength.

## What Existing FIFA Predictor Data Can Support Today

Available today:

- 2026-style frozen `teams_db_snapshot.csv`
- `starting_pqs`
- `bench_pqs`
- `player_ratings.csv`
- `overall`
- `efficiency_score`
- `position`
- `team_name_mapping.csv`

Can support:

- 2026 World Cup shadow scenarios
- Static squad-quality drift analysis
- Simulated injury what-if reports
- Replacement-depth approximation

Cannot support yet:

- Real historical injury validation
- Real match-by-match injury-aware calibration
- Safe 2024-2026 validation unless period-correct availability reports are added
- Claims that Injury / Availability Dynamic Team PQS improves accuracy

## What Must Be Added

Required before implementation:

1. A fixture file with `prediction_timestamp`.
2. A match-level unavailable players file.
3. Time-safe `reported_at` for every unavailable-player record.
4. Expected role labels, at least `starter`, `rotation`, `bench`, `unknown`.
5. Position labels aligned with player ratings.
6. Data quality flags for uncertain or unverified reports.

Strongly recommended:

1. Projected or confirmed roster.
2. Replacement player identification.
3. Goalkeeper starter / backup flag.
4. Source URL or source note for each availability record.
5. Validity windows for team-name mapping.

## Feasibility Assessment

### Is It Worth Entering Implementation?

Yes, but only for a shadow MVP.

Recommended first implementation scope:

```text
2026 World Cup Injury / Availability Dynamic Team PQS Shadow Mode benchmark
```

Do not attempt broad historical injury-aware calibration until period-correct historical injury and roster data exist.

### MVP Estimated Workload

Estimated implementation effort:

```text
2-4 focused development days
```

Breakdown:

- Schema extension and fixture validation: `0.5 day`
- Unavailable-player ingestion and time-safety checks: `0.5-1 day`
- Injury impact calculation and caps: `1 day`
- Shadow output and QA report: `0.5-1 day`
- Tests and documentation: `0.5 day`

Data collection effort is separate and likely larger:

```text
1-3 days for manual 2026-style fixture/sample data
much longer for historical coverage
```

### Biggest Risk

The biggest risk is look-ahead bias.

Second biggest risk is over-attributing team quality to injuries when the real issue is already captured by Elo, xG, or squad depth.

### Most Likely New Signal

The most likely new signal is not raw player strength. It is:

```text
unexpected availability shock relative to expected lineup
```

Examples:

- Starting goalkeeper unavailable.
- Top attacking player unavailable.
- Multiple starters unavailable in the same unit.
- Thin bench unable to replace missing starters.
- Last-minute suspension or illness known before prediction.

This is plausibly information Elo does not fully capture.

## Recommendation

Proceed to implementation only as:

```text
Injury / Availability Dynamic Team PQS shadow MVP
```

Do not:

- Tune PQS weight yet.
- Promote Injury / Availability Dynamic Team PQS to production.
- Claim calibration.
- Use Raw PQS as a main strength feature.

The MVP should measure drift and QA plausibility first. Prediction-quality claims require a later validation dataset with period-correct, timestamped injury and roster information.
