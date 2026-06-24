from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model.poisson import GAMMA, score_matrix
from src.tuning.domination_layer_benchmark import (
    NORMAL_WEIGHTS,
    RHO,
    blend_xg,
    build_domination_layer_benchmark,
    domination_xg,
    normal_worldcup_xg,
)
from src.tuning.tune_dixon_coles_rho import top_scoreline
from src.tuning.worldcup_xg_parameter_search import load_target_rows

REPORT_COLUMNS = [
    "normal_weight",
    "domination_weight",
    "matches",
    "correct_score_top1_accuracy",
    "correct_score_top3_accuracy",
    "correct_score_top5_accuracy",
    "goal_difference_exact_accuracy",
    "goal_difference_plus_minus_1_accuracy",
    "blowout_detection_accuracy",
    "actual_blowout_rate",
    "predicted_blowout_probability",
    "top3_probability_coverage",
    "top5_probability_coverage",
    "high_margin_matches",
    "high_margin_correct_score_top3_accuracy",
    "high_margin_correct_score_top5_accuracy",
    "high_margin_goal_difference_exact_accuracy",
    "high_margin_goal_difference_plus_minus_1_accuracy",
    "high_margin_predicted_blowout_probability",
]


def top_scorelines(
    matrix: list[dict[str, float | int]],
    count: int,
) -> list[tuple[int, int, float]]:
    sorted_cells = sorted(matrix, key=lambda cell: float(cell["probability"]), reverse=True)
    return [
        (int(cell["home"]), int(cell["away"]), float(cell["probability"]))
        for cell in sorted_cells[:count]
    ]


def goal_difference_probabilities(matrix: list[dict[str, float | int]]) -> dict[int, float]:
    probabilities: dict[int, float] = {}
    for cell in matrix:
        goal_difference = int(cell["home"]) - int(cell["away"])
        probabilities[goal_difference] = probabilities.get(goal_difference, 0.0) + float(cell["probability"])
    return probabilities


def predicted_goal_difference(matrix: list[dict[str, float | int]]) -> int:
    probabilities = goal_difference_probabilities(matrix)
    return max(probabilities, key=lambda goal_difference: probabilities[goal_difference])


def blowout_probability(matrix: list[dict[str, float | int]]) -> float:
    return sum(
        float(cell["probability"])
        for cell in matrix
        if abs(int(cell["home"]) - int(cell["away"])) >= 3
    )


def evaluate_extended_weight(rows: list[dict[str, Any]], normal_weight: float) -> dict[str, Any]:
    if not rows:
        raise ValueError("at least one neutral World Cup/Euro row is required")

    top1_hits = 0
    top3_hits = 0
    top5_hits = 0
    gd_exact_hits = 0
    gd_pm1_hits = 0
    blowout_detection_hits = 0
    actual_blowout_hits = 0
    predicted_blowout_probs: list[float] = []
    top3_probability_coverages: list[float] = []
    top5_probability_coverages: list[float] = []

    high_margin_top3_hits = 0
    high_margin_top5_hits = 0
    high_margin_gd_exact_hits = 0
    high_margin_gd_pm1_hits = 0
    high_margin_predicted_blowout_probs: list[float] = []

    for row in rows:
        team_a_elo = float(row["home_pre_match_elo"])
        team_b_elo = float(row["away_pre_match_elo"])
        team_a_score = int(row["home_score"])
        team_b_score = int(row["away_score"])
        actual_scoreline = (team_a_score, team_b_score)
        actual_goal_difference = team_a_score - team_b_score
        actual_is_blowout = abs(actual_goal_difference) >= 3

        normal_a, normal_b = normal_worldcup_xg(team_a_elo, team_b_elo)
        domination_a, domination_b = domination_xg(normal_a, normal_b, team_a_elo, team_b_elo)
        team_a_xg, team_b_xg = blend_xg(normal_a, normal_b, domination_a, domination_b, normal_weight)
        matrix = score_matrix(team_a_xg, team_b_xg, gamma=GAMMA, rho=RHO)

        top3 = top_scorelines(matrix, 3)
        top5 = top_scorelines(matrix, 5)
        predicted_gd = predicted_goal_difference(matrix)
        predicted_blowout_prob = blowout_probability(matrix)
        predicted_is_blowout = predicted_blowout_prob >= 0.5

        if top_scoreline(matrix) == actual_scoreline:
            top1_hits += 1
        if any((home, away) == actual_scoreline for home, away, _ in top3):
            top3_hits += 1
        if any((home, away) == actual_scoreline for home, away, _ in top5):
            top5_hits += 1
        if predicted_gd == actual_goal_difference:
            gd_exact_hits += 1
        if abs(predicted_gd - actual_goal_difference) <= 1:
            gd_pm1_hits += 1
        if predicted_is_blowout == actual_is_blowout:
            blowout_detection_hits += 1
        if actual_is_blowout:
            actual_blowout_hits += 1
            if any((home, away) == actual_scoreline for home, away, _ in top3):
                high_margin_top3_hits += 1
            if any((home, away) == actual_scoreline for home, away, _ in top5):
                high_margin_top5_hits += 1
            if predicted_gd == actual_goal_difference:
                high_margin_gd_exact_hits += 1
            if abs(predicted_gd - actual_goal_difference) <= 1:
                high_margin_gd_pm1_hits += 1
            high_margin_predicted_blowout_probs.append(predicted_blowout_prob)

        predicted_blowout_probs.append(predicted_blowout_prob)
        top3_probability_coverages.append(sum(probability for _, _, probability in top3))
        top5_probability_coverages.append(sum(probability for _, _, probability in top5))

    match_count = len(rows)
    high_margin_count = actual_blowout_hits
    return {
        "normal_weight": normal_weight,
        "domination_weight": 1.0 - normal_weight,
        "matches": match_count,
        "correct_score_top1_accuracy": top1_hits / match_count,
        "correct_score_top3_accuracy": top3_hits / match_count,
        "correct_score_top5_accuracy": top5_hits / match_count,
        "goal_difference_exact_accuracy": gd_exact_hits / match_count,
        "goal_difference_plus_minus_1_accuracy": gd_pm1_hits / match_count,
        "blowout_detection_accuracy": blowout_detection_hits / match_count,
        "actual_blowout_rate": actual_blowout_hits / match_count,
        "predicted_blowout_probability": statistics.mean(predicted_blowout_probs),
        "top3_probability_coverage": statistics.mean(top3_probability_coverages),
        "top5_probability_coverage": statistics.mean(top5_probability_coverages),
        "high_margin_matches": high_margin_count,
        "high_margin_correct_score_top3_accuracy": (
            high_margin_top3_hits / high_margin_count if high_margin_count else 0.0
        ),
        "high_margin_correct_score_top5_accuracy": (
            high_margin_top5_hits / high_margin_count if high_margin_count else 0.0
        ),
        "high_margin_goal_difference_exact_accuracy": (
            high_margin_gd_exact_hits / high_margin_count if high_margin_count else 0.0
        ),
        "high_margin_goal_difference_plus_minus_1_accuracy": (
            high_margin_gd_pm1_hits / high_margin_count if high_margin_count else 0.0
        ),
        "high_margin_predicted_blowout_probability": (
            statistics.mean(high_margin_predicted_blowout_probs) if high_margin_predicted_blowout_probs else 0.0
        ),
    }


def build_summary(
    rows: list[dict[str, Any]],
    base_benchmark_payload: dict[str, Any],
) -> dict[str, Any]:
    baseline = next(row for row in rows if float(row["normal_weight"]) == 1.0)
    current = next(row for row in rows if float(row["normal_weight"]) == 0.7)
    best_top3 = max(rows, key=lambda row: float(row["correct_score_top3_accuracy"]))
    best_top5 = max(rows, key=lambda row: float(row["correct_score_top5_accuracy"]))
    best_gd_exact = max(rows, key=lambda row: float(row["goal_difference_exact_accuracy"]))
    best_gd_pm1 = max(rows, key=lambda row: float(row["goal_difference_plus_minus_1_accuracy"]))
    best_blowout_detection = max(rows, key=lambda row: float(row["blowout_detection_accuracy"]))
    best_high_margin_top3 = max(
        rows,
        key=lambda row: float(row["high_margin_correct_score_top3_accuracy"]),
    )
    best_high_margin_top5 = max(
        rows,
        key=lambda row: float(row["high_margin_correct_score_top5_accuracy"]),
    )
    wdl_best_log_loss = base_benchmark_payload["summary"]["best_log_loss"]
    betting_candidates = {
        "top3": best_top3,
        "top5": best_top5,
        "goal_difference_exact": best_gd_exact,
        "goal_difference_plus_minus_1": best_gd_pm1,
        "blowout_detection": best_blowout_detection,
        "high_margin_top3": best_high_margin_top3,
        "high_margin_top5": best_high_margin_top5,
    }
    betting_best_weights = {
        name: candidate["normal_weight"] for name, candidate in betting_candidates.items()
    }
    return {
        "best_correct_score_top3": best_top3,
        "best_correct_score_top5": best_top5,
        "best_goal_difference_exact_accuracy": best_gd_exact,
        "best_goal_difference_plus_minus_1_accuracy": best_gd_pm1,
        "best_blowout_detection_accuracy": best_blowout_detection,
        "best_high_margin_correct_score_top3": best_high_margin_top3,
        "best_high_margin_correct_score_top5": best_high_margin_top5,
        "current_70_30": current,
        "baseline_100_normal": baseline,
        "current_70_30_vs_100_normal": {
            "correct_score_top3_delta": float(current["correct_score_top3_accuracy"])
            - float(baseline["correct_score_top3_accuracy"]),
            "correct_score_top5_delta": float(current["correct_score_top5_accuracy"])
            - float(baseline["correct_score_top5_accuracy"]),
            "goal_difference_exact_delta": float(current["goal_difference_exact_accuracy"])
            - float(baseline["goal_difference_exact_accuracy"]),
            "goal_difference_plus_minus_1_delta": float(current["goal_difference_plus_minus_1_accuracy"])
            - float(baseline["goal_difference_plus_minus_1_accuracy"]),
            "blowout_detection_delta": float(current["blowout_detection_accuracy"])
            - float(baseline["blowout_detection_accuracy"]),
            "high_margin_top3_delta": float(current["high_margin_correct_score_top3_accuracy"])
            - float(baseline["high_margin_correct_score_top3_accuracy"]),
            "high_margin_top5_delta": float(current["high_margin_correct_score_top5_accuracy"])
            - float(baseline["high_margin_correct_score_top5_accuracy"]),
        },
        "wdl_best_log_loss_weight": wdl_best_log_loss["normal_weight"],
        "betting_best_weights": betting_best_weights,
        "wdl_and_betting_best_weights_differ": any(
            float(weight) != float(wdl_best_log_loss["normal_weight"])
            for weight in betting_best_weights.values()
        ),
        "recommendation": {
            "domination_improves_top3_correct_score": float(best_top3["correct_score_top3_accuracy"])
            > float(baseline["correct_score_top3_accuracy"]),
            "domination_improves_top5_correct_score": float(best_top5["correct_score_top5_accuracy"])
            > float(baseline["correct_score_top5_accuracy"]),
            "domination_improves_blowout_detection": float(best_blowout_detection["blowout_detection_accuracy"])
            > float(baseline["blowout_detection_accuracy"]),
            "score_betting_best_weight_changed_from_wdl": any(
                float(weight) != float(wdl_best_log_loss["normal_weight"])
                for weight in betting_best_weights.values()
            ),
            "selection_note": (
                "Correct-score Top-N hit rate and Top-N probability coverage are both reported. "
                "The former checks whether the actual scoreline appears in the top-N set; the latter "
                "reports how concentrated the model's probability mass is in that top-N set."
            ),
        },
    }


def build_domination_layer_extended_benchmark(
    input_path: Path,
    team_universe_path: Path,
    normal_weights: tuple[float, ...] = NORMAL_WEIGHTS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target_rows, source_summary = load_target_rows(input_path, team_universe_path)
    base_rows, base_payload = build_domination_layer_benchmark(
        input_path,
        team_universe_path,
        normal_weights,
    )
    rows = [evaluate_extended_weight(target_rows, normal_weight) for normal_weight in normal_weights]
    payload = {
        "benchmark": "domination_layer_extended_benchmark",
        "dataset": {
            "label": "FIFA World Cup + UEFA Euro neutral matches",
            "universe": "FIFA + historical national teams",
            **source_summary,
        },
        "base_domination_benchmark_rows": base_rows,
        "metric_definitions": {
            "correct_score_top3_accuracy": "Actual scoreline appears in the three highest-probability scorelines.",
            "correct_score_top5_accuracy": "Actual scoreline appears in the five highest-probability scorelines.",
            "goal_difference_exact_accuracy": "Most probable aggregated goal-difference equals actual goal-difference.",
            "goal_difference_plus_minus_1_accuracy": "Most probable aggregated goal-difference is within one goal of actual goal-difference.",
            "blowout_detection_accuracy": "Binary accuracy for actual abs(goal_difference) >= 3 using predicted blowout probability >= 0.5.",
            "top3_probability_coverage": "Average probability mass assigned to the top three scorelines.",
            "top5_probability_coverage": "Average probability mass assigned to the top five scorelines.",
        },
        "search_space": {
            "normal_weight": list(normal_weights),
            "domination_weight": [1.0 - weight for weight in normal_weights],
        },
        "formal_model_formulas_unchanged": True,
        "rows": rows,
        "summary": build_summary(rows, base_payload),
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
    parser = argparse.ArgumentParser(description="Benchmark domination layer for score-betting metrics.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/domination_layer_extended_benchmark.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/domination_layer_extended_benchmark.json"),
    )
    parser.add_argument("--normal-weight", action="append", help="Candidate normal xG blend weight.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    normal_weights = _parse_float_tuple(args.normal_weight, NORMAL_WEIGHTS)
    rows, payload = build_domination_layer_extended_benchmark(args.input, args.team_universe, normal_weights)
    write_outputs(rows, payload, args.output_csv, args.output_json)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    print("normal_weight domination_weight top3 top5 gd_exact gd_pm1 blowout_detection high_margin_top3")
    for row in rows:
        print(
            f"{float(row['normal_weight']):.2f} "
            f"{float(row['domination_weight']):.2f} "
            f"{float(row['correct_score_top3_accuracy']):.6f} "
            f"{float(row['correct_score_top5_accuracy']):.6f} "
            f"{float(row['goal_difference_exact_accuracy']):.6f} "
            f"{float(row['goal_difference_plus_minus_1_accuracy']):.6f} "
            f"{float(row['blowout_detection_accuracy']):.6f} "
            f"{float(row['high_margin_correct_score_top3_accuracy']):.6f}"
        )

    summary = payload["summary"]
    print(f"best_top3_normal_weight: {summary['best_correct_score_top3']['normal_weight']}")
    print(f"best_top5_normal_weight: {summary['best_correct_score_top5']['normal_weight']}")
    print(f"best_blowout_detection_normal_weight: {summary['best_blowout_detection_accuracy']['normal_weight']}")
    print(
        "wdl_and_betting_best_weights_differ: "
        f"{summary['wdl_and_betting_best_weights_differ']}"
    )


if __name__ == "__main__":
    main()
