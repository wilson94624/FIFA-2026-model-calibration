# FIFA 2026 Model Calibration Lab

English | [繁體中文](README_zh.md)

This repository is the research documentation and calibration workspace for the
FIFA Predictor World Cup model. It is not the production API, frontend,
database, deployment package, or a new modeling phase.

Calibration Lab v1.0 is now closed. The final closure audit decision is:

```text
A. Close calibration and move into 4.0 / 5.0 integration planning.
```

The purpose of this lab was not to prove that every football idea improves the
model. It was to test which ideas survive calibration, which ideas should stay
out, and which ideas belong in the next research phase.

> Calibration is not about proving every idea works.
> It is about discovering which ideas deserve to become part of the model.

## What This Project Does

The lab takes a football prediction model apart into testable layers:

- Rebuild team strength from international results.
- Calibrate Elo and expected goals.
- Evaluate score-distribution assumptions.
- Test intuitive add-ons such as Raw PQS, Domination, and Score Tail Correction.
- Separate validated model components from research-only ideas.
- Define what should move into FIFA Predictor 4.0 and what belongs to FIFA Predictor 5.0.

The calibration target is a World Cup-oriented neutral-match model, evaluated
primarily on FIFA World Cup and UEFA Euro neutral-site matches.

## Final Model Candidate

The current formal model candidate is:

```text
final_worldcup_model_v1_candidate
```

Retained components:

| Layer | Final Setting |
| --- | --- |
| Elo | `calibrated_elo_v3_candidate` |
| Elo K factor | `K = 80` |
| Goal-difference shrinkage | `alpha = 0.10` |
| World Cup xG | Neutral xG |
| xG parameters | `base = 1.35`, `c1 = 1.30`, `scale = 600` |
| Home advantage | Disabled in Neutral World Cup Mode |
| Tournament weight | Disabled, `tournament_weight = 1` |
| Score distribution | Bivariate Poisson |
| Dixon-Coles | `rho = 0.05` |
| Gamma | `gamma = 0.08` |

Excluded from the formal model:

| Idea | Final Decision |
| --- | --- |
| Raw PQS as team strength | Not adopted |
| Domination Layer | Not adopted |
| Global Tail Correction | Not adopted |
| Conditional Tail Correction | Not adopted |
| Negative Binomial replacement | Not adopted |
| Fixed injury coefficient | Not adopted |
| Fatigue coefficient | Deferred |
| Style coefficient | Deferred |

## Final Benchmark

Final World Cup benchmark scope:

- FIFA World Cup + UEFA Euro
- Neutral-site matches only
- FIFA + historical national team universe

| Model | Accuracy | LogLoss | Brier |
| --- | ---: | ---: | ---: |
| `baseline_current` | 0.485470 | 1.022132 | 0.611690 |
| `full_calibrated_worldcup_candidate` | 0.532479 | 0.993752 | 0.590615 |

Improvement from `baseline_current`:

- Accuracy: `+0.047009`
- LogLoss: `+0.028380`
- Brier: `+0.021075`

The biggest verified improvement came from xG calibration. Elo calibration also
helped. Dixon-Coles and Gamma were retained because they gave small, consistent
calibration improvements. The rejected layers were rejected because they did not
improve the primary probability metrics reliably enough.

## Research Method

The lab follows a simple rule:

```text
Do not add a model layer just because it sounds right in football terms.
```

Each candidate idea was checked against some combination of:

- Accuracy
- Multiclass LogLoss
- Brier Score
- Top-1 / Top-3 / Top-5 correct score
- Goal-difference calibration
- Draw and low-score calibration
- Time split validation
- Tournament split validation
- Modern-era and recent-era stability
- Data-readiness and look-ahead-bias audits

The lab treats negative results as real research output. A rejected feature can
be just as useful as an adopted feature if it prevents the formal model from
double-counting signal or overfitting rare scorelines.

## Completed Research

| Topic | Outcome | Where To Read |
| --- | --- | --- |
| Calibration overview | Explains why the lab exists and what it learned | [research/00-overview.md](research/00-overview.md) |
| Elo calibration | Adopt `calibrated_elo_v3_candidate` with `K = 80` and `alpha = 0.10` | [research/01-elo-calibration.md](research/01-elo-calibration.md) |
| xG calibration | Adopt neutral World Cup xG with `base = 1.35`, `c1 = 1.30`, `scale = 600` | [research/02-xg-calibration.md](research/02-xg-calibration.md) |
| Dixon-Coles / Gamma | Retain `rho = 0.05` and `gamma = 0.08` | [research/03-dixon-coles-gamma.md](research/03-dixon-coles-gamma.md) |
| Raw PQS | Do not use as main team-strength feature | [research/04-pqs-shadow-study.md](research/04-pqs-shadow-study.md) |
| Domination Layer | Do not adopt; hurts primary calibration metrics | [research/05-domination-layer-study.md](research/05-domination-layer-study.md) |
| Score Tail Correction | Do not adopt global or conditional correction | [research/06-score-tail-calibration.md](research/06-score-tail-calibration.md) |
| Poisson limits | Keep Bivariate Poisson; do not replace with Negative Binomial | [research/07-poisson-distribution-research.md](research/07-poisson-distribution-research.md) |
| Injury / Availability | Use as Information Layer and future Shadow Mode, not a fixed coefficient | [research/08-injury-aware-pqs-design.md](research/08-injury-aware-pqs-design.md) |
| Future work | Move Dynamic Team PQS to FIFA Predictor 5.0 research | [research/09-future-work.md](research/09-future-work.md) |
| Score distribution limits | Correct score remains high variance; avoid overfitting rare blowouts | [research/10-score-distribution-and-model-limits.md](research/10-score-distribution-and-model-limits.md) |
| Closure audit | Formal close decision for Calibration Lab v1.0 | [research/calibration_closure_audit.md](research/calibration_closure_audit.md) |

For a guided reading order, start with [research/README.md](research/README.md).
For the short v1.0 narrative summary, read
[research/final_summary.md](research/final_summary.md).

## What Was Adopted

### Calibrated Elo

Elo calibration is complete for this phase. The model uses
`calibrated_elo_v3_candidate`, with `K = 80` and goal-difference shrinkage
`alpha = 0.10`.

Tournament weight was tested and not adopted. Home advantage remains disabled in
Neutral World Cup Mode because the final candidate is built around neutral-site
World Cup and Euro matches.

### Neutral xG

World Cup mode uses a neutral xG formula. This avoids treating dataset ordering
as a real home/away advantage when the match is played at a neutral site.

The retained xG candidate is:

```text
base = 1.35
c1 = 1.30
scale = 600
min_xg = 0.20
```

### Dixon-Coles And Gamma

Dixon-Coles `rho = 0.05` and Bivariate Poisson `gamma = 0.08` remain in the
model. Their contribution is small, but stable enough to keep.

## What Was Rejected

### Raw PQS

Raw PQS was originally expected to improve team-strength estimation. The shadow
study found that it overlaps strongly with Elo:

- PQS vs Elo Pearson correlation: approximately `0.75`
- Sign agreement: approximately `84%`

That makes Raw PQS risky as a direct team-strength feature. It often amplifies a
strength difference that Elo and xG already know.

Final decision:

```text
Raw PQS is not adopted as a formal team-strength layer.
```

### Domination Layer

Domination produced tiny improvements in some correct-score ranking metrics, but
it worsened the primary model-calibration metrics. It is not part of the formal
candidate.

### Score Tail Correction

The lab confirmed that GD>=3 is underpredicted, but global and conditional tail
corrections were not stable across splits. The model keeps diagnostics but does
not alter the formal score formula.

### Negative Binomial

Negative Binomial has research value for high-mismatch subsets, but it worsened
pooled LogLoss, Brier, and Top-3 in the feasibility benchmark. Bivariate Poisson
remains the formal score-distribution baseline.

### Injury Coefficient

The lab does not support a fixed injury coefficient. Injury and availability are
useful as information, but the current repository does not have the time-safe,
match-level absence data needed for calibration.

## Dynamic Team PQS And FIFA Predictor 5.0

Dynamic Team PQS is not part of Calibration Lab v1.0. It is the main research
direction for FIFA Predictor 5.0.

The important shift is this:

```text
Raw PQS asks: how strong is this team?
Dynamic Team PQS asks: how different is this team today from its expected state?
```

That second question is more promising because it can use information that Elo
does not fully capture:

- injuries
- suspensions
- unavailable players
- expected starters
- bench depth
- late availability shocks

The required path is:

```text
Information Layer
-> Dynamic Team PQS
-> Shadow Mode
-> validation
-> possible formal model integration
```

It should not become a fixed coefficient until it proves predictive value with
time-safe data.

## 4.0 And 5.0 Boundary

FIFA Predictor 4.0 integration should use the validated model core:

- calibrated Elo v3
- neutral World Cup xG
- Bivariate Poisson
- Dixon-Coles `rho = 0.05`
- Gamma `0.08`
- no Raw PQS
- no Domination Layer
- no Tail Correction

FIFA Predictor 5.0 research should build the data and shadow infrastructure that
Calibration Lab could not honestly claim yet:

- Dynamic Team PQS
- Injury / Availability Information Layer
- frozen prediction archives
- model versioning and input snapshots
- host / semi-home advantage research
- fatigue data readiness
- style data readiness
- score-tail monitoring for 48-team World Cup mismatches

## Repository Layout

```text
data/
  raw/
  processed/
  external/
  schema/
src/
  model/
  tuning/
  utils/
scripts/
results/
research/
tests/
archive/product_legacy/
```

## Running The Baseline

The executable baseline is still available for research use:

```bash
python scripts/run_elo_baseline.py \
  --input data/raw/historical_matches.csv \
  --output results/elo_baseline_predictions.csv
```

This command expects a historical match CSV with pre-match Elo values already
included. It does not update Elo ratings while reading the file.

## Final Conclusion

Calibration Lab v1.0 produced a cleaner model, but more importantly, it produced
a clearer boundary around the model.

The lab proved that calibrated Elo, neutral xG, Dixon-Coles, and Gamma deserve
to be part of the current World Cup candidate. It did not prove that Raw PQS,
Domination, Tail Correction, Negative Binomial, injury coefficients, fatigue, or
style should enter the formal model.

That is the point of calibration.

> Calibration is not about proving every idea works.
> It is about discovering which ideas deserve to become part of the model.
