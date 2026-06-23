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

from src.model.expected_goals import MIN_XG
from src.model.metrics import accuracy, brier_score, multiclass_log_loss
from src.model.poisson import GAMMA, outcome_probabilities, score_matrix
from src.tuning.evaluation import actual_label
from src.tuning.worldcup_xg_parameter_search import CALIBRATED_ELO_V3, TARGET_TOURNAMENTS, load_target_rows
from src.tuning.worldcup_xg_parameter_search import neutral_symmetric_xg

RHO_VALUES = (-0.20, -0.15, -0.10, -0.05, 0.00, 0.05, 0.10)

CALIBRATED_XG_WORLDCUP_V1 = {
    "mode": "neutral",
    "base": 1.35,
    "c1": 1.30,
    "scale": 600.0,
    "min_xg": MIN_XG,
}

LOW_SCORELINES = ((0, 0), (1, 0), (0, 1), (1, 1))

REPORT_COLUMNS = [
    "rho",
    "matches",
    "accuracy",
    "log_loss",
    "brier_score",
    "correct_score_top1_accuracy",
    "actual_low_score_match_rate",
    "predicted_low_score_probability",
    "actual_0_0_rate",
    "predicted_0_0_probability",
    "actual_1_0_rate",
    "predicted_1_0_probability",
    "actual_0_1_rate",
    "predicted_0_1_probability",
    "actual_1_1_rate",
    "predicted_1_1_probability",
]


def score_probability(matrix: list[dict[str, float | int]], home_goals: int, away_goals: int) -> float:
    for cell in matrix:
        if int(cell["home"]) == home_goals and int(cell["away"]) == away_goals:
            return float(cell["probability"])
    return 0.0


def top_scoreline(matrix: list[dict[str, float | int]]) -> tuple[int, int]:
    best = max(matrix, key=lambda cell: float(cell["probability"]))
    return int(best["home"]), int(best["away"])


def evaluate_rho(rows: list[dict[str, Any]], rho: float) -> dict[str, Any]:
    if not rows:
        raise ValueError("at least one neutral World Cup/Euro row is required")

    y_true: list[str] = []
    y_prob: list[dict[str, float]] = []
    correct_score_hits = 0
    actual_low_score_hits = 0
    predicted_low_score_probs: list[float] = []
    actual_scoreline_hits = {scoreline: 0 for scoreline in LOW_SCORELINES}
    predicted_scoreline_probs = {scoreline: [] for scoreline in LOW_SCORELINES}

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
        matrix = score_matrix(home_xg, away_xg, gamma=GAMMA, rho=rho)
        outcome_probs = outcome_probabilities(matrix)
        label = actual_label(home_score, away_score)
        predicted_scoreline = top_scoreline(matrix)

        y_true.append(label)
        y_prob.append(outcome_probs)
        if predicted_scoreline == (home_score, away_score):
            correct_score_hits += 1
        if (home_score, away_score) in LOW_SCORELINES:
            actual_low_score_hits += 1
        predicted_low_score_probs.append(
            sum(score_probability(matrix, home, away) for home, away in LOW_SCORELINES)
        )
        for scoreline in LOW_SCORELINES:
            if (home_score, away_score) == scoreline:
                actual_scoreline_hits[scoreline] += 1
            predicted_scoreline_probs[scoreline].append(score_probability(matrix, *scoreline))

    match_count = len(rows)
    output = {
        "rho": rho,
        "matches": match_count,
        "accuracy": accuracy(y_true, y_prob),
        "log_loss": multiclass_log_loss(y_true, y_prob),
        "brier_score": brier_score(y_true, y_prob),
        "correct_score_top1_accuracy": correct_score_hits / match_count,
        "actual_low_score_match_rate": actual_low_score_hits / match_count,
        "predicted_low_score_probability": sum(predicted_low_score_probs) / match_count,
    }
    for home, away in LOW_SCORELINES:
        key = f"{home}_{away}"
        output[f"actual_{key}_rate"] = actual_scoreline_hits[(home, away)] / match_count
        output[f"predicted_{key}_probability"] = (
            sum(predicted_scoreline_probs[(home, away)]) / match_count
        )
    return output


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    best_accuracy = max(rows, key=lambda row: float(row["accuracy"]))
    best_log_loss = min(rows, key=lambda row: float(row["log_loss"]))
    best_brier = min(rows, key=lambda row: float(row["brier_score"]))
    best_correct_score = max(rows, key=lambda row: float(row["correct_score_top1_accuracy"]))
    current_rho = next(row for row in rows if float(row["rho"]) == -0.05)
    zero_rho = next(row for row in rows if float(row["rho"]) == 0.0)
    return {
        "best_accuracy": best_accuracy,
        "best_log_loss": best_log_loss,
        "best_brier_score": best_brier,
        "best_correct_score_top1_accuracy": best_correct_score,
        "current_rho_minus_0_05": current_rho,
        "rho_0_00": zero_rho,
        "best_log_loss_vs_current_rho": {
            "log_loss_delta": float(current_rho["log_loss"]) - float(best_log_loss["log_loss"]),
            "brier_delta": float(current_rho["brier_score"]) - float(best_log_loss["brier_score"]),
            "accuracy_delta": float(best_log_loss["accuracy"]) - float(current_rho["accuracy"]),
            "is_better_log_loss": float(best_log_loss["log_loss"]) < float(current_rho["log_loss"]),
            "is_better_brier": float(best_log_loss["brier_score"]) < float(current_rho["brier_score"]),
        },
        "rho_0_00_vs_current_rho": {
            "log_loss_delta": float(current_rho["log_loss"]) - float(zero_rho["log_loss"]),
            "brier_delta": float(current_rho["brier_score"]) - float(zero_rho["brier_score"]),
            "accuracy_delta": float(zero_rho["accuracy"]) - float(current_rho["accuracy"]),
            "is_better_log_loss": float(zero_rho["log_loss"]) < float(current_rho["log_loss"]),
            "is_better_brier": float(zero_rho["brier_score"]) < float(current_rho["brier_score"]),
        },
        "recommended_calibrated_dc_worldcup_v1_candidate": {
            "rho": best_log_loss["rho"],
            "selection_metric": "wdl_log_loss",
        },
    }


def search_dixon_coles_rho(
    input_path: Path,
    team_universe_path: Path,
    rho_values: tuple[float, ...] = RHO_VALUES,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target_rows, source_summary = load_target_rows(input_path, team_universe_path)
    rows = [evaluate_rho(target_rows, rho) for rho in rho_values]
    payload = {
        "elo_source": CALIBRATED_ELO_V3,
        "xg_source": {
            "name": "calibrated_xg_worldcup_v1_candidate",
            **CALIBRATED_XG_WORLDCUP_V1,
        },
        "poisson": {
            "bivariate_shared_goal_gamma": GAMMA,
            "gamma_tuned": False,
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
        "search_space": {"rho": list(rho_values)},
        "formal_model_formulas_unchanged": True,
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
    parser = argparse.ArgumentParser(description="Search Dixon-Coles rho for neutral World Cup/Euro xG.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/dixon_coles_rho_search.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/dixon_coles_rho_search.json"),
    )
    parser.add_argument("--rho", action="append", help="Candidate Dixon-Coles rho value.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = search_dixon_coles_rho(
        args.input,
        args.team_universe,
        rho_values=_parse_float_tuple(args.rho, RHO_VALUES),
    )
    write_outputs(rows, payload, args.output_csv, args.output_json)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    print(f"evaluated_rho_values: {len(rows)}")
    print("rho accuracy log_loss brier_score correct_score_top1_accuracy")
    for row in rows:
        print(
            f"{float(row['rho']):.2f} "
            f"{float(row['accuracy']):.6f} "
            f"{float(row['log_loss']):.6f} "
            f"{float(row['brier_score']):.6f} "
            f"{float(row['correct_score_top1_accuracy']):.6f}"
        )
    best = payload["summary"]["best_log_loss"]
    print(
        "best_log_loss: "
        f"rho={float(best['rho']):.2f}, "
        f"log_loss={float(best['log_loss']):.6f}, "
        f"brier_score={float(best['brier_score']):.6f}"
    )


if __name__ == "__main__":
    main()
