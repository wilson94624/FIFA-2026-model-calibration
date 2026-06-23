from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model.metrics import accuracy, brier_score, multiclass_log_loss
from src.model.poisson import outcome_probabilities, score_matrix
from src.tuning.evaluation import actual_label
from src.tuning.tune_dixon_coles_rho import (
    CALIBRATED_XG_WORLDCUP_V1,
    LOW_SCORELINES,
    score_probability,
    top_scoreline,
)
from src.tuning.worldcup_xg_parameter_search import CALIBRATED_ELO_V3, TARGET_TOURNAMENTS, load_target_rows
from src.tuning.worldcup_xg_parameter_search import neutral_symmetric_xg

GAMMA_VALUES = (0.00, 0.03, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20)
FIXED_RHO = 0.05

REPORT_COLUMNS = [
    "gamma",
    "matches",
    "accuracy",
    "log_loss",
    "brier_score",
    "correct_score_top1_accuracy",
    "actual_draw_rate",
    "predicted_draw_probability",
    "actual_low_score_rate",
    "predicted_low_score_probability",
    "actual_0_0_rate",
    "predicted_0_0_probability",
    "actual_1_1_rate",
    "predicted_1_1_probability",
    "predicted_avg_total_goals",
    "actual_avg_total_goals",
]


def matrix_expected_total_goals(matrix: list[dict[str, float | int]]) -> float:
    return sum((int(cell["home"]) + int(cell["away"])) * float(cell["probability"]) for cell in matrix)


def evaluate_gamma(rows: list[dict[str, Any]], gamma: float) -> dict[str, Any]:
    if not rows:
        raise ValueError("at least one neutral World Cup/Euro row is required")

    y_true: list[str] = []
    y_prob: list[dict[str, float]] = []
    correct_score_hits = 0
    actual_draw_hits = 0
    actual_low_score_hits = 0
    predicted_draw_probs: list[float] = []
    predicted_low_score_probs: list[float] = []
    predicted_total_goals: list[float] = []
    actual_total_goals: list[int] = []
    actual_0_0_hits = 0
    actual_1_1_hits = 0
    predicted_0_0_probs: list[float] = []
    predicted_1_1_probs: list[float] = []

    for row in rows:
        home_score = int(row["home_score"])
        away_score = int(row["away_score"])
        home_elo = float(row["home_pre_match_elo"])
        away_elo = float(row["away_pre_match_elo"])
        home_xg, away_xg = neutral_symmetric_xg(
            home_elo,
            away_elo,
            base=float(CALIBRATED_XG_WORLDCUP_V1["base"]),
            c1=float(CALIBRATED_XG_WORLDCUP_V1["c1"]),
            scale=float(CALIBRATED_XG_WORLDCUP_V1["scale"]),
        )
        matrix = score_matrix(home_xg, away_xg, gamma=gamma, rho=FIXED_RHO)
        outcome_probs = outcome_probabilities(matrix)
        label = actual_label(home_score, away_score)
        predicted_scoreline = top_scoreline(matrix)

        y_true.append(label)
        y_prob.append(outcome_probs)
        if predicted_scoreline == (home_score, away_score):
            correct_score_hits += 1
        if home_score == away_score:
            actual_draw_hits += 1
        if (home_score, away_score) in LOW_SCORELINES:
            actual_low_score_hits += 1
        if (home_score, away_score) == (0, 0):
            actual_0_0_hits += 1
        if (home_score, away_score) == (1, 1):
            actual_1_1_hits += 1

        predicted_draw_probs.append(outcome_probs["draw"])
        predicted_low_score_probs.append(
            sum(score_probability(matrix, home, away) for home, away in LOW_SCORELINES)
        )
        predicted_0_0_probs.append(score_probability(matrix, 0, 0))
        predicted_1_1_probs.append(score_probability(matrix, 1, 1))
        predicted_total_goals.append(matrix_expected_total_goals(matrix))
        actual_total_goals.append(home_score + away_score)

    match_count = len(rows)
    return {
        "gamma": gamma,
        "matches": match_count,
        "accuracy": accuracy(y_true, y_prob),
        "log_loss": multiclass_log_loss(y_true, y_prob),
        "brier_score": brier_score(y_true, y_prob),
        "correct_score_top1_accuracy": correct_score_hits / match_count,
        "actual_draw_rate": actual_draw_hits / match_count,
        "predicted_draw_probability": sum(predicted_draw_probs) / match_count,
        "actual_low_score_rate": actual_low_score_hits / match_count,
        "predicted_low_score_probability": sum(predicted_low_score_probs) / match_count,
        "actual_0_0_rate": actual_0_0_hits / match_count,
        "predicted_0_0_probability": sum(predicted_0_0_probs) / match_count,
        "actual_1_1_rate": actual_1_1_hits / match_count,
        "predicted_1_1_probability": sum(predicted_1_1_probs) / match_count,
        "predicted_avg_total_goals": sum(predicted_total_goals) / match_count,
        "actual_avg_total_goals": sum(actual_total_goals) / match_count,
    }


def _find_gamma(rows: list[dict[str, Any]], gamma: float) -> dict[str, Any] | None:
    for row in rows:
        if abs(float(row["gamma"]) - gamma) < 1e-12:
            return row
    return None


def _delta_summary(reference: dict[str, Any] | None, candidate: dict[str, Any]) -> dict[str, Any] | None:
    if reference is None:
        return None
    return {
        "log_loss_delta": float(reference["log_loss"]) - float(candidate["log_loss"]),
        "brier_delta": float(reference["brier_score"]) - float(candidate["brier_score"]),
        "accuracy_delta": float(candidate["accuracy"]) - float(reference["accuracy"]),
        "correct_score_top1_accuracy_delta": float(candidate["correct_score_top1_accuracy"])
        - float(reference["correct_score_top1_accuracy"]),
        "is_better_log_loss": float(candidate["log_loss"]) < float(reference["log_loss"]),
        "is_better_brier": float(candidate["brier_score"]) < float(reference["brier_score"]),
    }


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    best_accuracy = max(rows, key=lambda row: float(row["accuracy"]))
    best_log_loss = min(rows, key=lambda row: float(row["log_loss"]))
    best_brier = min(rows, key=lambda row: float(row["brier_score"]))
    best_correct_score = max(rows, key=lambda row: float(row["correct_score_top1_accuracy"]))
    current_gamma = _find_gamma(rows, 0.08)
    zero_gamma = _find_gamma(rows, 0.0)
    return {
        "best_accuracy": best_accuracy,
        "best_log_loss": best_log_loss,
        "best_brier_score": best_brier,
        "best_correct_score_top1_accuracy": best_correct_score,
        "current_gamma_0_08": current_gamma,
        "gamma_0_00": zero_gamma,
        "best_log_loss_vs_current_gamma": _delta_summary(current_gamma, best_log_loss),
        "gamma_0_00_vs_current_gamma": (
            _delta_summary(current_gamma, zero_gamma) if zero_gamma is not None else None
        ),
        "recommended_calibrated_poisson_worldcup_v1_candidate": {
            "gamma": best_log_loss["gamma"],
            "rho": FIXED_RHO,
            "selection_metric": "wdl_log_loss",
        },
    }


def search_bivariate_gamma(
    input_path: Path,
    team_universe_path: Path,
    gamma_values: tuple[float, ...] = GAMMA_VALUES,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target_rows, source_summary = load_target_rows(input_path, team_universe_path)
    rows = [evaluate_gamma(target_rows, gamma) for gamma in gamma_values]
    payload = {
        "elo_source": CALIBRATED_ELO_V3,
        "xg_source": {
            "name": "calibrated_xg_worldcup_v1_candidate",
            **CALIBRATED_XG_WORLDCUP_V1,
        },
        "dixon_coles": {
            "rho": FIXED_RHO,
            "rho_tuned": False,
        },
        "universe": {
            "name": "fifa_historical",
            "label": "FIFA + historical national teams",
            **source_summary,
        },
        "target": {
            "tournaments": list(TARGET_TOURNAMENTS),
            "neutral_only": True,
        },
        "search_space": {"gamma": list(gamma_values)},
        "formal_model_formulas_unchanged": True,
        "predicted_avg_total_goals_definition": "expected total goals from normalized score matrix",
        "rows": rows,
        "summary": build_summary(rows),
    }
    return rows, payload


def write_outputs(
    rows: list[dict[str, Any]],
    payload: dict[str, Any],
    csv_path: Path,
    json_path: Path,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _parse_float_tuple(values: list[str] | None, default: tuple[float, ...]) -> tuple[float, ...]:
    if not values:
        return default
    return tuple(float(value) for value in values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search bivariate Poisson gamma for neutral World Cup/Euro xG.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/bivariate_gamma_search.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/bivariate_gamma_search.json"),
    )
    parser.add_argument("--gamma", action="append", help="Candidate bivariate shared-goal gamma value.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = search_bivariate_gamma(
        args.input,
        args.team_universe,
        gamma_values=_parse_float_tuple(args.gamma, GAMMA_VALUES),
    )
    write_outputs(rows, payload, args.output_csv, args.output_json)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    print(f"evaluated_gamma_values: {len(rows)}")
    print("gamma accuracy log_loss brier_score correct_score_top1_accuracy predicted_draw_probability")
    for row in rows:
        print(
            f"{float(row['gamma']):.2f} "
            f"{float(row['accuracy']):.6f} "
            f"{float(row['log_loss']):.6f} "
            f"{float(row['brier_score']):.6f} "
            f"{float(row['correct_score_top1_accuracy']):.6f} "
            f"{float(row['predicted_draw_probability']):.6f}"
        )
    best = payload["summary"]["best_log_loss"]
    print(
        "best_log_loss: "
        f"gamma={float(best['gamma']):.2f}, "
        f"log_loss={float(best['log_loss']):.6f}, "
        f"brier_score={float(best['brier_score']):.6f}"
    )


if __name__ == "__main__":
    main()
