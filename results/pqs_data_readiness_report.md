# PQS Data Readiness Report

This report evaluates whether the Calibration Lab can build a reproducible PQS benchmark and defines the first data schema needed for a PQS shadow benchmark.

Status:

- PQS calibration is **not** complete.
- The current lab can support a PQS shadow benchmark or limited modern-period benchmark only after period-correct data are supplied.
- No formal Predictor code, `src/model/pqs.py`, or model formula was modified.

## Recommended Schema Files

### `data/schema/teams_db_snapshot_schema.csv`

Purpose: one frozen team-level snapshot for the team database used by PQS benchmarks.

| Field | Required | Purpose |
| --- | --- | --- |
| `snapshot_id` | yes | Stable identifier for a frozen teams_db snapshot. |
| `snapshot_date` | yes | Date when ratings and roster data are valid or frozen. |
| `team_key` | yes | Canonical join key across all PQS files. |
| `team_name` | yes | Human-readable teams_db team name. |
| `has_data` | yes | Whether player-level data are available. |
| `starting_pqs` | yes | Fallback or precomputed starting XI PQS. |
| `bench_pqs` | yes | Fallback or precomputed bench quality. |
| `fifa_points` | no | Optional product-side rating input; not a replacement for calibrated Elo. |
| `style` | no | Optional tactical style for future shadow analysis. |
| `source` | yes | Snapshot source or export process. |
| `notes` | no | Coverage caveats. |

### `data/schema/player_ratings_schema.csv`

Purpose: player-level ratings inside a timestamped snapshot.

| Field | Required | Purpose |
| --- | --- | --- |
| `snapshot_id` | yes | Joins player record to a frozen team snapshot. |
| `snapshot_date` | yes | Date ratings are valid. |
| `team_key` | yes | Canonical team key. |
| `player_id` | yes | Stable player identifier. |
| `player_name` | yes | Display name and fallback matching field. |
| `position` | yes | Used to split offensive and defensive PQS. |
| `overall` | no | Optional raw player overall rating. |
| `efficiency_score` | yes | Primary PQS quality input. |
| `rating_source` | yes | Rating provenance. |
| `rating_timestamp` | yes | Extraction or publication timestamp. |
| `is_in_squad_pool` | no | Whether player belongs to tournament squad pool. |
| `notes` | no | Known caveats. |

### `data/schema/match_roster_schema.csv`

Purpose: match-level roster, starting XI, and bench availability.

| Field | Required | Purpose |
| --- | --- | --- |
| `match_id` | yes | Join key to fixture or historical match. |
| `match_date` | yes | Used for time-safe snapshot selection. |
| `team_key` | yes | Canonical team key. |
| `player_id` | yes | Stable player identifier. |
| `player_name` | yes | Display name for diagnostics. |
| `roster_status` | yes | `starting_xi`, `bench`, `squad`, or `not_in_squad`. |
| `position` | yes | Required for attack/defense PQS split. |
| `source` | yes | Roster or lineup source. |
| `lineup_confirmed` | no | Confirmed lineup vs projected squad. |
| `notes` | no | Coverage caveats or late changes. |

### `data/schema/unavailable_players_schema.csv`

Purpose: match-level unavailable players for injury, suspension, and other absences.

| Field | Required | Purpose |
| --- | --- | --- |
| `match_id` | yes | Join key to match. |
| `match_date` | yes | Verifies absence data timing. |
| `team_key` | yes | Canonical team key. |
| `player_id` | no | Stable player identifier when available. |
| `player_name` | yes | Name used for active roster exclusion. |
| `unavailable_reason` | yes | Injury, suspension, illness, personal, not selected, or unknown. |
| `status_confidence` | no | Confirmed, probable, or uncertain. |
| `reported_at` | yes | Timestamp proving information existed before prediction. |
| `source` | yes | Availability source. |
| `notes` | no | Additional context. |

### `data/schema/fatigue_state_schema.csv`

Purpose: pre-match fatigue state used by PQS shadow benchmarks.

| Field | Required | Purpose |
| --- | --- | --- |
| `match_id` | yes | Join key to fixture. |
| `match_date` | yes | Match date. |
| `team_key` | yes | Canonical team key. |
| `pre_match_fatigue` | yes | Fatigue value available before the match. |
| `fatigue_method` | yes | Calculation method or disabled state. |
| `prior_matches_counted` | no | Prior matches included. |
| `extra_time_prior` | no | Prior extra-time matches included. |
| `bench_pqs_used` | no | Bench PQS used in fatigue increment. |
| `source` | yes | Data or calculation source. |
| `notes` | no | Caveats. |

### `data/schema/team_name_mapping_schema.csv`

Purpose: map FIFA / `international_results` names to teams_db keys.

| Field | Required | Purpose |
| --- | --- | --- |
| `source_team_name` | yes | Team name as it appears in match data. |
| `source_system` | yes | Name source, such as FIFA or `international_results`. |
| `team_key` | yes | Canonical teams_db key. |
| `teams_db_name` | yes | Name used in teams_db snapshot. |
| `valid_from` | no | Mapping start date. |
| `valid_to` | no | Mapping end date. |
| `mapping_confidence` | yes | Exact, alias, manual, or ambiguous. |
| `notes` | no | Name-change or ambiguity notes. |

## Minimum Viable PQS Shadow Benchmark Data

Required for a first reproducible shadow benchmark:

- `teams_db_snapshot_schema.csv`
- `player_ratings_schema.csv`
- `team_name_mapping_schema.csv`

Strongly recommended:

- `match_roster_schema.csv`
- `unavailable_players_schema.csv`

Optional for v1 shadow:

- `fatigue_state_schema.csv`

Minimum fields:

- `snapshot_id`
- `snapshot_date`
- `team_key`
- `team_name`
- `has_data`
- `starting_pqs`
- `bench_pqs`
- `player_id`
- `player_name`
- `position`
- `efficiency_score`
- `rating_source`
- `rating_timestamp`
- `source_team_name`
- `source_system`
- `teams_db_name`
- `mapping_confidence`

This is enough for a 2026 World Cup shadow benchmark, but not enough to claim PQS calibration.

## Look-Ahead Bias Risks

Do not use a 2026 squad snapshot to evaluate 2024 matches. For any evaluated match, only snapshots with:

```text
snapshot_date <= match_date
rating_timestamp <= match kickoff or prediction timestamp
reported_at <= match kickoff or prediction timestamp
```

are eligible.

Major leakage risks:

- 2026 squad data used for Euro 2024.
- Confirmed starting XI used before it would have been available.
- Injury reports published after kickoff.
- Tournament performance boosts from later matches used for earlier matches.
- Current team mappings used without historical validity windows.

If no eligible snapshot exists for a match, exclude that match from PQS validation.

## PQS As Shadow Additive Layer

Baseline:

```text
final_worldcup_model_v1_candidate without PQS
```

PQS should be added as an xG adjustment layer for shadow comparison, not as a replacement for calibrated Elo or calibrated neutral xG.

Research-only shape:

```text
team_a_xg = baseline_team_a_xg + pqs_weight * (attack_pqs_a - defense_pqs_b) / 0.3
team_b_xg = baseline_team_b_xg + pqs_weight * (attack_pqs_b - defense_pqs_a) / 0.3
```

Candidate weights:

```text
0.00, 0.10, 0.20, 0.25, 0.30
```

Required shadow outputs:

- baseline xG
- PQS-adjusted xG
- xG delta
- W/D/L probability delta
- score matrix delta
- draw probability delta
- low-score probability delta
- championship odds delta

Do not claim:

- PQS improves predictive accuracy.
- Raw PQS is calibrated.
- PQS weight is optimal.

## Recommendation

First benchmark scope:

```text
2026 World Cup shadow benchmark
```

Reason:

- It can use a period-correct 2026 pre-tournament teams_db snapshot.
- It avoids pretending that modern squads can validate historical matches.
- It supports QA comparison before production integration.

Go / no-go:

- Can start PQS benchmark framework: yes.
- Can start PQS tuning: no.
- Can claim PQS calibrated: no.

Recommended next step:

Create schema templates and a PQS shadow benchmark framework that reads frozen snapshots and reports drift versus `final_worldcup_model_v1_candidate`.
