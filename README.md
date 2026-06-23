# FIFA-2026-model-calibration

This repository is the FIFA Predictor 4.0 model calibration lab. It is a research
workspace for testing model assumptions, probability calibration, and tuning
experiments. It is not the production API, frontend, database layer, or
deployment package.

# Calibration Progress

Completed research phases:

- Rebuilt a reproducible Elo history from `international_results`.
- Tuned Elo K-factor candidates and selected stronger calibrated candidates for validation.
- Researched home advantage as an Elo-point adjustment while keeping it disabled for the current World Cup-oriented candidate.
- Researched tournament weight effects and kept tournament weight disabled after conservative grid validation.
- Researched goal-difference multipliers and introduced shrinkage to reduce Elo scale expansion.
- Built a team universe filter for FIFA-only and FIFA + historical national team calibration.
- Ran time split validation with training through 2023 and validation from 2024 onward.
- Ran tournament split validation across major international competitions.
- Built an Elo-to-xG benchmark to evaluate how Elo sources convert into expected goals and downstream W/D/L probabilities.

# Current Best Candidate

Current candidate:

```text
calibrated_elo_v3_candidate
```

Parameters:

- `K = 80`
- `goal_diff_shrinkage_alpha = 0.10`
- `home_advantage = 0`
- `tournament_weight = 1`
- PQS disabled

Status:

- Better calibration than standard Elo.
- More stable rating scale than `calibrated_elo_v2_candidate`.
- Not yet promoted to the production default.

# Research Roadmap

Completed:

- Elo rebuild
- Elo calibration
- Validation framework

In progress:

- Elo-to-xG calibration

Planned:

- Poisson calibration
- Dixon-Coles calibration
- PQS integration
- FIFA Predictor integration

Pipeline:

```text
international_results
    ↓
Elo Rebuild
    ↓
Elo Calibration
    ↓
xG Calibration
    ↓
Poisson
    ↓
Dixon-Coles
    ↓
PQS
    ↓
FIFA Predictor
```

## Phase-One Baseline

The current executable baseline is intentionally narrow:

- ELO-only expected goals
- Bivariate Poisson score matrix
- Dixon-Coles low-score correction
- Accuracy, multiclass LogLoss, and Brier Score

The baseline uses only these CSV columns:

```text
home_team,away_team,home_score,away_score,home_pre_match_elo,away_pre_match_elo
```

It does not update ELO ratings while reading the CSV. Each row must already
include the pre-match ELO values to evaluate.

Fixed model constants:

- `c1 = 0.75`
- `GAMMA = 0.08`
- `RHO = -0.05`
- `MAX_GOALS = 5`

## Usage

Create a historical matches CSV with the required schema, then run:

```bash
python scripts/run_elo_baseline.py \
  --input data/raw/historical_matches.csv \
  --output results/elo_baseline_predictions.csv
```

The output CSV includes expected goals, home/draw/away probabilities, predicted
label, and actual label. The command prints:

```text
matches: N
accuracy: ...
log_loss: ...
brier_score: ...
```

A header-only schema template is available at:

```text
data/schema/historical_matches_schema.csv
```

No fake historical match data is included.

## Repository Layout

```text
data/
  raw/
  processed/
  external/
  schema/
src/
  model/
    elo.py
    pqs.py
    expected_goals.py
    poisson.py
    metrics.py
  tuning/
  utils/
scripts/
results/
notebooks/
archive/product_legacy/
tests/
```

## Preserved Legacy Logic

The calibration modules preserve the useful model core from FIFA Predictor 4.0:

- ELO expected score and ELO update helper
- ELO-to-Expected-Goals formula
- Bivariate Poisson score probability formula
- Dixon-Coles correction
- Score-matrix normalization
- Score-matrix aggregation into home/draw/away probabilities
- Legacy PQS active-roster logic isolated for future research

## Isolated Product Dependencies

The original product-coupled files are archived under `archive/product_legacy/`.
They are not imported by the phase-one baseline.

Isolated product dependencies include:

- SQLAlchemy database models
- backend/FastAPI import paths
- frontend JSON paths
- `.env` loading
- Gemini/LLM analysis and external API calls
- tournament bracket and knockout simulation
- Monte Carlo champion probability outputs
- automatic frontend JSON writes

## Next Data Needed

To run meaningful calibration experiments, prepare historical match data with:

- team names
- final score
- pre-match ELO for both teams
- match date
- competition or tournament name
- neutral-site or host indicator

Future extensions can add player/PQS snapshots, injuries, rest days, travel,
market odds, and tournament context, but these are intentionally excluded from
the phase-one ELO-only baseline.
