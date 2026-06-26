# Injury Data Source Audit Report

This report audits whether Injury / Availability and Dynamic Team PQS have enough time-safe, reproducible data to move from shadow analysis into benchmark or validation.

Scope:

- No formal Predictor code was modified.
- No model formula was modified.
- No Injury / Availability or Dynamic Team PQS tuning was performed.
- No web scraping or live data collection was performed.
- This is a data-source feasibility audit only.

## Executive Summary

The Calibration Lab is not yet ready for Injury / Availability or Dynamic Team PQS tuning or historical validation.

Current data can support a limited 2026-style shadow benchmark because the lab has:

- A frozen `teams_db` snapshot.
- Player-level ratings.
- Team-name mapping.
- A PQS shadow framework that can mark missing data and enforce basic time-safety checks.

Current data cannot support rigorous injury-aware validation because the lab does not yet have:

- Match-level unavailable players.
- `reported_at` timestamps for each injury or availability record.
- Prediction timestamps for the evaluated fixtures.
- Period-correct squads and player ratings for historical matches.
- Pre-match roster / expected starter context.
- Reliable player identity mapping between external injury feeds and `player_id`.

Recommended path:

```text
A. Conservative route: 2026 World Cup shadow-only
```

This is the safest next step. It avoids claims of predictive improvement and measures only xG / WDL / score-matrix drift under time-safe availability inputs.

## 1. FIFA Predictor 4.0 Injury Data Source Audit

The archived product logic shows that FIFA Predictor 4.0 already supports unavailable-player inputs.

### Local Code Paths Found

Relevant files:

- `archive/product_legacy/engine.py`
- `archive/product_legacy/player_level_simulator.py`
- `archive/product_legacy/models.py`

Observed product behavior:

- `engine.py` reads:

```text
stats["unavailable_players"]
```

- The expected structure is roughly:

```text
unavailable_players = {
  "home": [...],
  "away": [...]
}
```

- `active_pqs()` excludes unavailable players from the active player pool.
- Remaining players are sorted by `efficiency_score`.
- The top 11 active players become the implied starters.
- Offensive PQS is computed from active FW/MF players.
- Defensive PQS is computed from active DF/GK players.
- Bench PQS is computed from remaining active players.
- Fatigue can further reduce attack and defense PQS.

This means the original product logic already treats injury / unavailable data as an active-roster modifier.

### Whether It Appears To Come From FotMob

The archived lab copy does not include a complete upstream FotMob ingestion pipeline. The local code references a generic `stats` payload and reads `stats["unavailable_players"]`, but the current repository does not preserve enough evidence to prove that every unavailable-player record came from FotMob.

Feasibility assessment:

| Question | Audit Result |
| --- | --- |
| Does product logic read unavailable players? | Yes. |
| Is the source definitely FotMob in the Calibration Lab copy? | Not proven from local files. |
| Is the unavailable-player payload preserved historically? | Not in current lab data. |
| Is there a `reported_at` timestamp per unavailable player? | Not found. |
| Is there a `fetched_at` timestamp in legacy DB models? | Yes, source-level records include `fetched_at`, but not per unavailable-player event. |
| Is there a `prediction_timestamp` tied to each prediction input? | Not available in current processed lab data. |
| Can this support historical validation by itself? | No. |

### Time-Safety Gap

`archive/product_legacy/models.py` contains source metadata such as:

```text
source
fetched_at
version
confidence
```

This is useful but insufficient for rigorous injury validation.

For time-safe injury-aware benchmarking, the lab needs:

```text
reported_at <= prediction_timestamp <= kickoff
```

Current archived product logic can consume unavailable players, but the lab cannot prove when each unavailable-player fact became known.

### Current-Event vs Historical Support

The existing product path appears most suitable for current or future tournaments where data can be fetched and frozen before predictions.

It is not currently sufficient for historical validation because:

- Historical payloads are not present.
- Per-player availability timestamps are not present.
- Source snapshots are not versioned by match.
- Player ratings are not period-correct for older matches.

Conclusion:

```text
FIFA Predictor 4.0 injury logic is usable as a shadow input path,
but the current lab does not have a reproducible historical injury archive.
```

## 2. Existing Calibration Lab Data

### `teams_db_snapshot.csv`

Current processed file:

```text
data/processed/teams_db_snapshot.csv
```

Observed size:

```text
48 team rows + header
```

Available fields:

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
- `notes`

Supports:

- Team-level static PQS baseline.
- Bench-depth proxy through `bench_pqs`.
- Frozen 2026-style squad snapshot.
- Reproducible team key joins.

Does not support:

- Match-level injury status.
- Match-specific roster.
- Historical squads.
- Per-player expected role.
- Availability timing.

### `player_ratings.csv`

Current processed file:

```text
data/processed/player_ratings.csv
```

Observed size:

```text
1248 player rows + header
```

Available fields:

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
- `notes`

Supports:

- Player-level quality.
- Position-aware missing-player impact.
- Stable player IDs generated from teams_db.
- Rating timestamp checks.

Does not support:

- Injury or suspension status.
- Match-level starter expectation.
- Minutes expectation.
- Historical player form.
- Historical national-team roster membership.
- Replacement hierarchy beyond a rough same-position ranking.

### `team_name_mapping.csv`

Current processed file:

```text
data/processed/team_name_mapping.csv
```

Observed size:

```text
106 mapping rows + header
```

Supports:

- Mapping teams_db names to fixture or international-results aliases.
- Basic time-safe joins when `valid_from` / `valid_to` are populated.

Does not fully support:

- Historical national-name ambiguity unless validity windows are maintained.
- Player identity mapping from external injury sources.

### Existing Injury / Roster Schemas

Current schema files exist:

```text
data/schema/unavailable_players_schema.csv
data/schema/match_roster_schema.csv
data/schema/fatigue_state_schema.csv
```

Current `unavailable_players_schema.csv` header:

```text
match_id,match_date,team_key,player_id,player_name,unavailable_reason,status_confidence,reported_at,source,notes
```

This is a good start, but injury-aware MVP should add:

- `prediction_timestamp`
- `position`
- `expected_role`
- `availability_status`

Current lab readiness:

| Capability | Status |
| --- | --- |
| Static 2026 PQS shadow drift | Ready. |
| Injury-aware shadow with manually supplied unavailable players | Nearly ready. |
| Historical injury validation | Not ready. |
| PQS tuning | Not ready. |
| Production claim | Not supported. |

## 3. External Injury Data Source Possibilities

This section is feasibility analysis only. No website was scraped or queried beyond general source research.

### Kaggle Football Injury Datasets

Likely profile:

- Public datasets may exist for football injuries, but many are club-focused, league-focused, or medical-event focused.
- Coverage of national-team international fixtures is uncertain.
- Timestamps are often publication dates, season dates, or scraped record dates, not necessarily pre-match `reported_at`.

Assessment:

| Criterion | Feasibility |
| --- | --- |
| National team coverage | Low to uncertain. |
| Match-level availability | Usually weak. |
| Timestamp suitable for look-ahead control | Often weak. |
| Injury reason | Often available. |
| Expected starter / lineup | Usually missing. |
| Player ID mapping to teams_db | Manual or fuzzy. |
| Suitable for training / validation | High risk unless dataset is carefully verified. |
| Suitable for shadow QA | Possible if records are modern and source timing is clear. |

Conclusion:

Kaggle-style injury datasets should not be assumed usable for Injury / Availability or Dynamic Team PQS validation until manually inspected for national-team match coverage and pre-match timestamps.

### Transfermarkt Injury History / Public Mirrors

Likely profile:

- Transfermarkt-style injury history is often player-centered and club-centered.
- It can contain injury type, start date, end date, missed matches, or absence periods.
- Some public mirrors or research datasets may exist, but licensing and scraping terms are a major concern.

Assessment:

| Criterion | Feasibility |
| --- | --- |
| National team coverage | Partial at best. |
| Match-level availability | Can be inferred from injury intervals, but not direct. |
| Timestamp suitable for look-ahead control | Usually problematic unless source versioning exists. |
| Injury reason | Often available. |
| Expected starter / lineup | Missing. |
| Player ID mapping to teams_db | Hard; requires player-name disambiguation. |
| Suitable for historical validation | Possible only with strict source, license, and timestamp controls. |
| Suitable for shadow QA | Possible for manual samples. |

Club-to-national mapping risk:

- A club injury interval may imply a player was unavailable for a national-team match, but this is not always true.
- International call-up decisions, fitness recovery, travel, and federation reporting differ from club injury records.
- National-team absences may be tactical, selection-based, administrative, or personal rather than injury.

Conclusion:

Transfermarkt-style injury history is the most plausible aggressive historical route, but it is legally and methodologically high risk unless obtained from a clearly licensed downloadable dataset with stable timestamps and player identifiers.

### FotMob Current Match Payload

Likely profile:

- Useful for current or upcoming fixtures.
- May include lineups, unavailable players, and match details depending on match availability.
- Current payloads are more useful for shadow mode than for historical validation unless fetched and archived before prediction.

Assessment:

| Criterion | Feasibility |
| --- | --- |
| National team coverage | Potentially good for major tournaments. |
| Match-level availability | Potentially good for current fixtures. |
| Timestamp suitable for look-ahead control | Only if the lab records `fetched_at` and prediction timestamp. |
| Injury reason | Variable. |
| Expected starter / lineup | Confirmed lineup may be available close to kickoff; projected lineup uncertain. |
| Player ID mapping to teams_db | Requires mapping layer. |
| Suitable for training / validation | Not historical unless archived. |
| Suitable for 2026 shadow QA | Yes, if fetched and frozen before each prediction. |

Conclusion:

2026 FotMob-style data is best treated as shadow-mode input. It can support QA and drift analysis during the tournament, but not pre-tournament calibration unless historical payload archives exist.

### Public Lineup Datasets

Likely profile:

- Lineup datasets may exist for club football and major competitions.
- International tournament lineup history can be found in some public sources, but availability timestamps are usually absent.

Assessment:

| Criterion | Feasibility |
| --- | --- |
| National team coverage | Medium for major tournaments. |
| Match-level availability | Lineups yes; injuries no. |
| Timestamp suitable for look-ahead control | Weak unless source is archived pre-match. |
| Injury reason | Usually missing. |
| Expected starter / lineup | Confirmed post-match lineups available; pre-match projected lineups rare. |
| Player ID mapping to teams_db | Hard but possible. |
| Suitable for validation | Risky if using confirmed lineups as if pre-match. |
| Suitable for post-hoc diagnostics | Yes. |

Conclusion:

Lineups help diagnose replacement quality and starters, but confirmed lineups alone can introduce look-ahead bias if used before they would have been available.

### Manual / Semi-Automated 2024-2026 Sample

Likely profile:

- Human-curated injury and availability reports for selected matches.
- Can include source URL, publication time, expected role, confidence, and notes.
- Better time-safety than generic public injury histories if curated carefully.

Assessment:

| Criterion | Feasibility |
| --- | --- |
| National team coverage | Can target exactly the desired tournaments. |
| Match-level availability | Yes, if manually recorded. |
| Timestamp suitable for look-ahead control | Yes, if required. |
| Injury reason | Yes. |
| Expected starter / lineup | Can be manually annotated. |
| Player ID mapping to teams_db | Manual but manageable. |
| Suitable for tuning | Only after enough matches. |
| Suitable for shadow QA | Good. |

Conclusion:

This is the most reliable route for a limited modern-period benchmark, but it requires disciplined data entry and audit trails.

## 4. Data Source Evaluation Matrix

| Source | National Team | Match-Level Availability | Timestamp | Injury Reason | Expected Starter / Lineup | Player Mapping | Look-Ahead Safe | Best Use |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Current teams_db snapshot | Yes, 2026-style teams | No | Snapshot only | No | No | Native | Partial | Static shadow baseline |
| Current player_ratings | Yes, 2026-style teams | No | Rating timestamp | No | No | Native | Partial | Player-quality impact basis |
| Product `stats.unavailable_players` | Potentially yes | Yes if payload exists | Not proven per player | Variable | No | Name-based | Weak unless archived | Future/current shadow input |
| FotMob current payload | Potentially yes | Potentially yes | Safe only if fetched/frozen | Variable | Sometimes lineup | Requires mapping | Yes if archived before prediction | 2026 shadow mode |
| Kaggle injury datasets | Uncertain | Usually weak | Often weak | Often yes | Usually no | Hard | High risk | Exploratory only |
| Transfermarkt-style history | Partial | Interval-based inference | Usually weak | Often yes | No | Hard | High risk | Aggressive research path |
| Public lineup datasets | Medium for major tournaments | Lineup yes, injury no | Usually post-match | No | Confirmed lineup | Hard | Risky | Diagnostics |
| Manual 2024-2026 sample | Targeted | Yes | Yes if enforced | Yes | Can annotate | Manual | Strong if audited | Limited benchmark / QA |

## 5. Key Judgments

### Is 2026 FotMob Injury Data Shadow-Only?

Yes, unless the lab can archive payloads before prediction and later compare outcomes with a pre-declared evaluation protocol.

For 2026:

- It can support shadow mode.
- It can support pre-match QA.
- It can support drift reports.
- It should not be used to claim calibration until enough time-safe match records accumulate.

### Can Kaggle / Transfermarkt Injury History Support Historical Validation?

Possibly, but not by default.

It can support historical validation only if all of the following are true:

- Data license permits research use.
- National-team match coverage is sufficient.
- Injury intervals can be mapped to match dates.
- Player identity can be mapped to `player_id`.
- Source timestamps or data-version timestamps prevent look-ahead leakage.
- The dataset distinguishes injury from non-selection.
- The benchmark excludes matches with ambiguous availability.

Without those conditions, it is safer to use such data for qualitative diagnostics only.

### Can Club Injuries Map To National-Team Availability?

Only cautiously.

Club injury history can be useful when:

- Injury interval clearly overlaps a national-team match.
- The player was in the relevant national-team pool.
- The absence reason aligns with external national-team reporting.
- The player was expected to be relevant for that match.

Club injury data is not enough when:

- A player is not called up for tactical reasons.
- The player recovered before the international match.
- The player was unavailable to club but available to country, or vice versa.
- Injury dates are approximate.
- The source does not timestamp when information was known.

Conclusion:

Club injury mapping should be treated as a high-risk proxy, not a primary validation source.

### How Many Matches Are Needed For Tuning?

For Injury / Availability and Dynamic Team PQS, the effective sample size is not total matches. It is:

```text
matches with meaningful time-safe injury signal
```

A useful tuning set should contain enough matches with:

- Missing expected starters.
- Missing high-impact attackers.
- Missing defensive anchors or goalkeepers.
- Multiple unavailable players.
- Comparable no-injury controls.
- Balanced team-strength contexts.

Rough guidance:

| Use Case | Minimum Useful Sample |
| --- | --- |
| Shadow QA only | 10-30 matches with good sources. |
| Limited modern-period benchmark | 75-150 matches, with enough injury-positive cases. |
| First cautious parameter tuning | 200+ matches, ideally across tournaments and team strengths. |
| Robust model promotion | Several hundred time-safe matches with clear injury-negative controls. |

### Is 44 Matches Enough?

No for tuning.

44 matches can be enough for:

- Shadow drift reporting.
- Manual QA.
- Sanity checks.
- Case studies.
- Identifying failure modes.

44 matches is not enough for:

- Selecting a reliable injury weight.
- Measuring small LogLoss / Brier improvements.
- Separating injury signal from Elo, xG, matchup strength, and tournament noise.
- Validating rare events such as goalkeeper injuries or multiple-starter absences.

If only 44 matches exist, recommended use:

- Freeze the model before matches.
- Produce shadow predictions.
- Compare deltas, not claims.
- Build a case library.
- Use results to decide whether a larger dataset is worth collecting.

## 6. Route Options

### A. Conservative Route: 2026 World Cup Shadow-Only

Description:

- Use current `teams_db_snapshot.csv`, `player_ratings.csv`, and `team_name_mapping.csv`.
- Add time-safe unavailable-player rows during the 2026 World Cup.
- Archive `fetched_at`, `reported_at`, `prediction_timestamp`, and source notes.
- Run baseline vs Injury / Availability Dynamic Team PQS shadow reports.
- Do not tune.
- Do not claim predictive improvement.

Pros:

- Lowest look-ahead risk.
- Directly relevant to FIFA Predictor.
- Does not require risky historical injury scraping.
- Easy to QA manually.

Cons:

- Too few matches for tuning.
- Cannot prove generalizable performance.
- Requires disciplined pre-match data capture.

Recommendation:

```text
Use this route first.
```

### B. Middle Route: 2024-2026 Manual / Semi-Automated Injury Sample

Description:

- Curate injury / unavailable-player data for selected major tournaments and qualifiers.
- Require source URL or source note.
- Require `reported_at`.
- Add expected role and position.
- Map players to `player_id`.
- Evaluate only matches with time-safe records.

Pros:

- More useful than 2026-only shadow.
- Can build a limited benchmark.
- Better data quality than broad public scraped history.

Cons:

- Labor-intensive.
- Still may be too small for tuning.
- Manual role labels can introduce subjectivity.

Recommendation:

```text
Best next route if the team wants evidence beyond shadow mode.
```

### C. Aggressive Route: Transfermarkt / Public Injury History Mapping

Description:

- Identify a legally usable public injury-history dataset.
- Map injury intervals to national-team matches.
- Map players to teams_db identities.
- Infer national-team availability.

Pros:

- Potentially larger sample.
- Could enable broader historical analysis.

Cons:

- Highest license and data-use risk.
- High player-mapping burden.
- High look-ahead risk.
- Club-to-country availability inference is noisy.
- Expected starter context remains missing.

Recommendation:

```text
Do not start here.
```

Use only after the conservative and middle routes define the schema, QA process, and expected signal.

## 7. Minimum Data Needed Before Any Benchmark Claim

Before Injury / Availability or Dynamic Team PQS can make even a limited benchmark claim, each evaluated match should have:

```text
match_id
match_date
prediction_timestamp
team_key
player_id or high-confidence player_name mapping
player position
expected_role
unavailable_reason
availability_status
status_confidence
reported_at
source
snapshot_id
snapshot_date
rating_timestamp
```

Required time-safety checks:

```text
snapshot_date <= match_date
rating_timestamp <= prediction_timestamp
reported_at <= prediction_timestamp
prediction_timestamp <= kickoff
```

Required exclusions:

- Missing `reported_at`.
- Future-dated injury report.
- No player mapping.
- No time-safe player rating.
- Injury status inferred only after the match.
- Confirmed lineup used before it was public.

## 8. What Is Available Now vs Must Be Added

Available now:

- 48-team 2026-style team snapshot.
- 1248 player ratings.
- Team-name mapping.
- Existing schemas for roster, unavailable players, fatigue.
- PQS shadow benchmark framework.
- Prior PQS drift and QA reports.

Must be added:

- Actual unavailable-player rows.
- `reported_at` for every availability fact.
- `prediction_timestamp` in fixture inputs.
- Expected role labels.
- Player mapping for external sources.
- Source provenance.
- Optional but valuable: match roster / projected XI / bench depth.

## 9. Final Recommendation

Injury / Availability and Dynamic Team PQS are not ready for tuning.

It is ready for a carefully constrained shadow-mode data collection process.

Recommended next step:

```text
Build a 2026 World Cup injury availability capture protocol.
```

Protocol requirements:

- Freeze fixture list before prediction.
- Record `prediction_timestamp`.
- Record all unavailable players known at that time.
- Record `reported_at` and source for each unavailable player.
- Map each player to `player_id`.
- Mark expected role.
- Run Injury / Availability Dynamic Team PQS only as shadow drift.
- Review the largest xG / WDL / score-matrix deltas manually.

Do not:

- Tune injury weights on 44 matches.
- Use current 2026 teams_db to evaluate 2024 matches.
- Use club injury history as national-team truth without validation.
- Claim PQS has improved prediction accuracy.
- Promote Injury / Availability Dynamic Team PQS into the formal Predictor.

## 10. Answers To Required Questions

### Available Data Sources

Usable immediately:

- `teams_db_snapshot.csv`
- `player_ratings.csv`
- `team_name_mapping.csv`
- Future manually supplied `unavailable_players.csv`
- Future pre-match FotMob-style payload archives, if stored with timestamps

Potentially usable with caution:

- Manual 2024-2026 injury sample.
- Public lineup datasets for diagnostics.
- Legally usable public injury datasets after inspection.

### Unavailable Or High-Risk Sources

High risk:

- Transfermarkt-style scraped injury history without clear license.
- Club injury intervals used as direct national-team availability.
- Kaggle injury data without national-team coverage and timestamps.
- Confirmed lineups used as pre-match projected starters.
- Any source without `reported_at` or archived `fetched_at`.

### Is There Enough Data For Tuning?

No.

Current lab data has player quality, but not injury events. Even a 44-match tournament sample would be too small for tuning. It can support shadow QA, not parameter fitting.

### Is This Shadow-Only For Now?

Yes.

The safest current status is:

```text
Injury / Availability Dynamic Team PQS Shadow Mode only
```

### Next Step

Create a time-safe data capture workflow for 2026 World Cup availability data, then run the existing PQS shadow benchmark with real unavailable-player inputs.

If more evidence is needed before 2026, build a small manually audited 2024-2026 sample, but label it as limited benchmark research rather than calibration.
