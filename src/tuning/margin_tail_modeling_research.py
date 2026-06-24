from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model.metrics import accuracy, brier_score, multiclass_log_loss
from src.model.poisson import GAMMA, outcome_probabilities, score_matrix
from src.tuning.domination_layer_extended_benchmark import (
    blowout_probability,
    predicted_goal_difference,
    top_scorelines,
)
from src.tuning.evaluation import actual_label
from src.tuning.score_distribution_diagnostics import predicted_favorite_margin_bucket
from src.tuning.score_tail_calibration_report import (
    RHO,
    bucket_for_probability,
    favorite_win_by_three_probability,
    total_goals_probability,
    worldcup_xg,
)
from src.tuning.worldcup_xg_parameter_search import load_target_rows

ALPHAS = (0.05, 0.10, 0.15)
REPORT_COLUMNS = [
    "variant",
    "method",
    "alpha",
    "condition",
    "max_goals",
    "matches",
    "accuracy",
    "log_loss",
    "brier_score",
    "correct_score_top1_accuracy",
    "correct_score_top3_accuracy",
    "correct_score_top5_accuracy",
    "goal_difference_exact_accuracy",
    "goal_difference_plus_minus_1_accuracy",
    "actual_gd_3_plus_rate",
    "predicted_gd_3_plus_probability",
    "gd_3_plus_calibration_error",
    "actual_favorite_win_by_3_plus_rate",
    "predicted_favorite_win_by_3_plus_probability",
    "favorite_win_by_3_plus_calibration_error",
    "actual_total_goals_4_plus_rate",
    "predicted_total_goals_4_plus_probability",
    "total_goals_4_plus_calibration_error",
    "blowout_bucket_weighted_abs_error",
    "score_matrix_kl_drift",
    "score_matrix_mad_drift",
]


ScoreCell = dict[str, float | int]


def normalize_matrix(matrix: list[ScoreCell]) -> list[ScoreCell]:
    total = sum(float(cell["probability"]) for cell in matrix) or 1.0
    return [
        {
            "home": int(cell["home"]),
            "away": int(cell["away"]),
            "probability": max(0.0, float(cell["probability"])) / total,
        }
        for cell in matrix
    ]


def matrix_to_map(matrix: list[ScoreCell]) -> dict[tuple[int, int], float]:
    return {
        (int(cell["home"]), int(cell["away"])): float(cell["probability"])
        for cell in matrix
    }


def map_to_matrix(probabilities: dict[tuple[int, int], float]) -> list[ScoreCell]:
    return [
        {"home": home, "away": away, "probability": probability}
        for (home, away), probability in sorted(probabilities.items())
    ]


def transfer_probability(
    probabilities: dict[tuple[int, int], float],
    source: tuple[int, int],
    target: tuple[int, int],
    amount: float,
) -> None:
    if amount <= 0.0:
        return
    available = probabilities.get(source, 0.0)
    moved = min(available, amount)
    probabilities[source] = available - moved
    probabilities[target] = probabilities.get(target, 0.0) + moved


def gd_tail_redistribution(matrix: list[ScoreCell], alpha: float) -> list[ScoreCell]:
    probabilities = matrix_to_map(matrix)
    max_goals = max(max(home, away) for home, away in probabilities)
    for home, away in list(probabilities):
        goal_difference = home - away
        if abs(goal_difference) != 2:
            continue
        amount = probabilities[(home, away)] * alpha
        if goal_difference > 0:
            target = (home + 1, away) if home + 1 <= max_goals else (home, max(0, away - 1))
        else:
            target = (home, away + 1) if away + 1 <= max_goals else (max(0, home - 1), away)
        if abs(target[0] - target[1]) >= 3:
            transfer_probability(probabilities, (home, away), target, amount)
    return normalize_matrix(map_to_matrix(probabilities))


def favorite_tail_boost(
    matrix: list[ScoreCell],
    alpha: float,
    home_is_favorite: bool,
) -> list[ScoreCell]:
    probabilities = matrix_to_map(matrix)
    max_goals = max(max(home, away) for home, away in probabilities)
    for home, away in list(probabilities):
        bucket = predicted_favorite_margin_bucket(home, away, home_is_favorite)
        if bucket != "favorite_win_by_2":
            continue
        amount = probabilities[(home, away)] * alpha
        if home_is_favorite:
            target = (home + 1, away) if home + 1 <= max_goals else (home, max(0, away - 1))
        else:
            target = (home, away + 1) if away + 1 <= max_goals else (max(0, home - 1), away)
        if predicted_favorite_margin_bucket(target[0], target[1], home_is_favorite) == "favorite_win_by_3_plus":
            transfer_probability(probabilities, (home, away), target, amount)
    return normalize_matrix(map_to_matrix(probabilities))


def matrix_kl_divergence(baseline: list[ScoreCell], candidate: list[ScoreCell]) -> float:
    baseline_map = matrix_to_map(baseline)
    candidate_map = matrix_to_map(candidate)
    keys = set(baseline_map) | set(candidate_map)
    eps = 1e-15
    total = 0.0
    for key in keys:
        p = max(eps, baseline_map.get(key, 0.0))
        q = max(eps, candidate_map.get(key, 0.0))
        total += p * math.log(p / q)
    return total


def matrix_mad(baseline: list[ScoreCell], candidate: list[ScoreCell]) -> float:
    baseline_map = matrix_to_map(baseline)
    candidate_map = matrix_to_map(candidate)
    keys = set(baseline_map) | set(candidate_map)
    return sum(abs(baseline_map.get(key, 0.0) - candidate_map.get(key, 0.0)) for key in keys) / len(keys)


def condition_is_active(
    condition: str,
    baseline_matrix: list[ScoreCell],
    home_xg: float,
    away_xg: float,
    home_is_favorite: bool,
) -> bool:
    outcome_probs = outcome_probabilities(baseline_matrix)
    favorite_win_probability = outcome_probs["home"] if home_is_favorite else outcome_probs["away"]
    xg_diff = abs(home_xg - away_xg)
    if condition == "favorite_win_prob>=0.65":
        return favorite_win_probability >= 0.65
    if condition == "favorite_win_prob>=0.75":
        return favorite_win_probability >= 0.75
    if condition == "xg_diff>=1.0":
        return xg_diff >= 1.0
    if condition == "xg_diff>=1.5":
        return xg_diff >= 1.5
    raise ValueError(f"unknown condition {condition!r}")


def build_variant_configs() -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = [
        {
            "variant": "baseline",
            "method": "baseline",
            "alpha": None,
            "condition": "none",
            "max_goals": 5,
        },
        {
            "variant": "max_goals_10_only",
            "method": "max_goals_10_only",
            "alpha": None,
            "condition": "none",
            "max_goals": 10,
        },
    ]
    for alpha in ALPHAS:
        configs.append(
            {
                "variant": f"gd_tail_redistribution_alpha_{alpha:.2f}",
                "method": "gd_tail_redistribution",
                "alpha": alpha,
                "condition": "none",
                "max_goals": 5,
            }
        )
    for alpha in ALPHAS:
        configs.append(
            {
                "variant": f"favorite_tail_boost_alpha_{alpha:.2f}",
                "method": "favorite_tail_boost",
                "alpha": alpha,
                "condition": "none",
                "max_goals": 5,
            }
        )
    for condition in (
        "favorite_win_prob>=0.65",
        "favorite_win_prob>=0.75",
        "xg_diff>=1.0",
        "xg_diff>=1.5",
    ):
        configs.append(
            {
                "variant": f"conditional_blowout_calibration_{condition}",
                "method": "conditional_blowout_calibration",
                "alpha": 0.10,
                "condition": condition,
                "max_goals": 5,
            }
        )
    return configs


def apply_variant(
    baseline_matrix: list[ScoreCell],
    config: dict[str, Any],
    home_xg: float,
    away_xg: float,
    home_is_favorite: bool,
) -> list[ScoreCell]:
    method = str(config["method"])
    alpha = float(config["alpha"] or 0.0)
    if method == "baseline":
        return baseline_matrix
    if method == "max_goals_10_only":
        return score_matrix(home_xg, away_xg, max_goals=10, gamma=GAMMA, rho=RHO)
    if method == "gd_tail_redistribution":
        return gd_tail_redistribution(baseline_matrix, alpha)
    if method == "favorite_tail_boost":
        return favorite_tail_boost(baseline_matrix, alpha, home_is_favorite)
    if method == "conditional_blowout_calibration":
        if condition_is_active(str(config["condition"]), baseline_matrix, home_xg, away_xg, home_is_favorite):
            return favorite_tail_boost(baseline_matrix, alpha, home_is_favorite)
        return baseline_matrix
    raise ValueError(f"unknown method {method!r}")


def analyze_rows(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in source_rows:
        home_elo = float(row["home_pre_match_elo"])
        away_elo = float(row["away_pre_match_elo"])
        home_xg, away_xg = worldcup_xg(home_elo, away_elo)
        home_score = int(row["home_score"])
        away_score = int(row["away_score"])
        home_is_favorite = home_elo >= away_elo
        favorite_score = home_score if home_is_favorite else away_score
        underdog_score = away_score if home_is_favorite else home_score
        rows.append(
            {
                "row": row,
                "home_xg": home_xg,
                "away_xg": away_xg,
                "home_score": home_score,
                "away_score": away_score,
                "label": actual_label(home_score, away_score),
                "actual_goal_difference": home_score - away_score,
                "actual_abs_goal_difference": abs(home_score - away_score),
                "actual_total_goals": home_score + away_score,
                "home_is_favorite": home_is_favorite,
                "actual_favorite_win_by_3_plus": favorite_score - underdog_score >= 3,
            }
        )
    return rows


def blowout_bucket_error(
    predicted_probabilities: list[float],
    actual_blowouts: list[bool],
) -> float:
    buckets: dict[str, list[tuple[float, bool]]] = {
        label: [] for label in ("0-5%", "5-10%", "10-20%", "20-30%", "30%+")
    }
    for probability, actual in zip(predicted_probabilities, actual_blowouts, strict=True):
        buckets[bucket_for_probability(probability)].append((probability, actual))

    total_count = len(predicted_probabilities)
    weighted_error = 0.0
    for bucket_rows in buckets.values():
        if not bucket_rows:
            continue
        predicted_avg = statistics.mean(probability for probability, _ in bucket_rows)
        actual_rate = sum(1 for _, actual in bucket_rows if actual) / len(bucket_rows)
        weighted_error += abs(actual_rate - predicted_avg) * len(bucket_rows) / total_count
    return weighted_error


def evaluate_variant(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    labels: list[str] = []
    probabilities: list[dict[str, float]] = []
    top1_hits = 0
    top3_hits = 0
    top5_hits = 0
    gd_exact_hits = 0
    gd_pm1_hits = 0
    predicted_gd_3_plus_probs: list[float] = []
    predicted_favorite_3_plus_probs: list[float] = []
    predicted_total_4_plus_probs: list[float] = []
    actual_gd_3_plus: list[bool] = []
    actual_favorite_3_plus: list[bool] = []
    actual_total_4_plus: list[bool] = []
    kl_drifts: list[float] = []
    mad_drifts: list[float] = []

    for row in rows:
        baseline_matrix = score_matrix(row["home_xg"], row["away_xg"], max_goals=5, gamma=GAMMA, rho=RHO)
        candidate_matrix = apply_variant(
            baseline_matrix,
            config,
            row["home_xg"],
            row["away_xg"],
            bool(row["home_is_favorite"]),
        )
        outcome_probs = outcome_probabilities(candidate_matrix)
        predicted_gd = predicted_goal_difference(candidate_matrix)

        labels.append(row["label"])
        probabilities.append(outcome_probs)
        if any(
            home == row["home_score"] and away == row["away_score"]
            for home, away, _ in top_scorelines(candidate_matrix, 1)
        ):
            top1_hits += 1
        if any(
            home == row["home_score"] and away == row["away_score"]
            for home, away, _ in top_scorelines(candidate_matrix, 3)
        ):
            top3_hits += 1
        if any(
            home == row["home_score"] and away == row["away_score"]
            for home, away, _ in top_scorelines(candidate_matrix, 5)
        ):
            top5_hits += 1
        if predicted_gd == row["actual_goal_difference"]:
            gd_exact_hits += 1
        if abs(predicted_gd - row["actual_goal_difference"]) <= 1:
            gd_pm1_hits += 1

        predicted_gd_3_plus_probs.append(blowout_probability(candidate_matrix))
        predicted_favorite_3_plus_probs.append(
            favorite_win_by_three_probability(candidate_matrix, bool(row["home_is_favorite"]))
        )
        predicted_total_4_plus_probs.append(total_goals_probability(candidate_matrix, 4))
        actual_gd_3_plus.append(bool(row["actual_abs_goal_difference"] >= 3))
        actual_favorite_3_plus.append(bool(row["actual_favorite_win_by_3_plus"]))
        actual_total_4_plus.append(bool(row["actual_total_goals"] >= 4))
        kl_drifts.append(matrix_kl_divergence(baseline_matrix, candidate_matrix))
        mad_drifts.append(matrix_mad(baseline_matrix, candidate_matrix))

    match_count = len(rows)
    actual_gd_rate = sum(actual_gd_3_plus) / match_count
    predicted_gd_probability = statistics.mean(predicted_gd_3_plus_probs)
    actual_favorite_rate = sum(actual_favorite_3_plus) / match_count
    predicted_favorite_probability = statistics.mean(predicted_favorite_3_plus_probs)
    actual_total_rate = sum(actual_total_4_plus) / match_count
    predicted_total_probability = statistics.mean(predicted_total_4_plus_probs)
    return {
        "variant": config["variant"],
        "method": config["method"],
        "alpha": config["alpha"],
        "condition": config["condition"],
        "max_goals": config["max_goals"],
        "matches": match_count,
        "accuracy": accuracy(labels, probabilities),
        "log_loss": multiclass_log_loss(labels, probabilities),
        "brier_score": brier_score(labels, probabilities),
        "correct_score_top1_accuracy": top1_hits / match_count,
        "correct_score_top3_accuracy": top3_hits / match_count,
        "correct_score_top5_accuracy": top5_hits / match_count,
        "goal_difference_exact_accuracy": gd_exact_hits / match_count,
        "goal_difference_plus_minus_1_accuracy": gd_pm1_hits / match_count,
        "actual_gd_3_plus_rate": actual_gd_rate,
        "predicted_gd_3_plus_probability": predicted_gd_probability,
        "gd_3_plus_calibration_error": abs(actual_gd_rate - predicted_gd_probability),
        "actual_favorite_win_by_3_plus_rate": actual_favorite_rate,
        "predicted_favorite_win_by_3_plus_probability": predicted_favorite_probability,
        "favorite_win_by_3_plus_calibration_error": abs(
            actual_favorite_rate - predicted_favorite_probability
        ),
        "actual_total_goals_4_plus_rate": actual_total_rate,
        "predicted_total_goals_4_plus_probability": predicted_total_probability,
        "total_goals_4_plus_calibration_error": abs(actual_total_rate - predicted_total_probability),
        "blowout_bucket_weighted_abs_error": blowout_bucket_error(
            predicted_gd_3_plus_probs,
            actual_gd_3_plus,
        ),
        "score_matrix_kl_drift": statistics.mean(kl_drifts),
        "score_matrix_mad_drift": statistics.mean(mad_drifts),
    }


def metric_delta(reference: dict[str, Any], candidate: dict[str, Any]) -> dict[str, float]:
    return {
        "log_loss_delta": float(reference["log_loss"]) - float(candidate["log_loss"]),
        "brier_delta": float(reference["brier_score"]) - float(candidate["brier_score"]),
        "top3_delta": float(candidate["correct_score_top3_accuracy"])
        - float(reference["correct_score_top3_accuracy"]),
        "top5_delta": float(candidate["correct_score_top5_accuracy"])
        - float(reference["correct_score_top5_accuracy"]),
        "gd_3_plus_calibration_error_delta": float(reference["gd_3_plus_calibration_error"])
        - float(candidate["gd_3_plus_calibration_error"]),
        "favorite_3_plus_calibration_error_delta": float(
            reference["favorite_win_by_3_plus_calibration_error"]
        )
        - float(candidate["favorite_win_by_3_plus_calibration_error"]),
    }


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = next(row for row in rows if row["variant"] == "baseline")
    best_gd = min(rows, key=lambda row: float(row["gd_3_plus_calibration_error"]))
    best_favorite = min(rows, key=lambda row: float(row["favorite_win_by_3_plus_calibration_error"]))
    best_top3 = max(rows, key=lambda row: float(row["correct_score_top3_accuracy"]))
    best_top5 = max(rows, key=lambda row: float(row["correct_score_top5_accuracy"]))
    best_log_loss = min(rows, key=lambda row: float(row["log_loss"]))
    best_brier = min(rows, key=lambda row: float(row["brier_score"]))
    non_baseline = [row for row in rows if row["variant"] != "baseline"]
    conservative_candidates = [
        row
        for row in non_baseline
        if float(row["score_matrix_mad_drift"]) <= 0.0005
        and float(row["log_loss"]) <= float(baseline["log_loss"]) + 0.001
        and float(row["brier_score"]) <= float(baseline["brier_score"]) + 0.001
    ]
    most_conservative = min(
        conservative_candidates or non_baseline,
        key=lambda row: (
            float(row["score_matrix_mad_drift"]),
            float(row["score_matrix_kl_drift"]),
        ),
    )
    return {
        "baseline": baseline,
        "best_gd_3_plus_calibration": best_gd,
        "best_favorite_win_by_3_plus_calibration": best_favorite,
        "best_correct_score_top3": best_top3,
        "best_correct_score_top5": best_top5,
        "best_log_loss": best_log_loss,
        "best_brier_score": best_brier,
        "most_conservative_non_baseline": most_conservative,
        "best_gd_vs_baseline": metric_delta(baseline, best_gd),
        "best_top3_vs_baseline": metric_delta(baseline, best_top3),
        "recommendation": {
            "any_method_improves_gd_3_plus_calibration": float(best_gd["gd_3_plus_calibration_error"])
            < float(baseline["gd_3_plus_calibration_error"]),
            "any_method_improves_top3": float(best_top3["correct_score_top3_accuracy"])
            > float(baseline["correct_score_top3_accuracy"]),
            "any_method_improves_top5": float(best_top5["correct_score_top5_accuracy"])
            > float(baseline["correct_score_top5_accuracy"]),
            "best_gd_hurts_log_loss": float(best_gd["log_loss"]) > float(baseline["log_loss"]),
            "best_gd_hurts_brier": float(best_gd["brier_score"]) > float(baseline["brier_score"]),
            "continue_margin_tail_research": True,
            "keep_formal_model_baseline_unchanged": True,
            "next_round_candidate": best_gd["variant"],
        },
    }


def build_margin_tail_modeling_research(
    input_path: Path,
    team_universe_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target_rows, source_summary = load_target_rows(input_path, team_universe_path)
    analyzed_rows = analyze_rows(target_rows)
    configs = build_variant_configs()
    rows = [evaluate_variant(analyzed_rows, config) for config in configs]
    payload = {
        "benchmark": "margin_tail_modeling_research",
        "dataset": {
            "label": "FIFA World Cup + UEFA Euro neutral matches",
            "universe": "FIFA + historical national teams",
            **source_summary,
        },
        "model_context": {
            "baseline": "final_worldcup_model_v1_candidate",
            "domination": "disabled / 100% normal",
            "formal_model_formulas_unchanged": True,
            "production_default_unchanged": True,
            "research_layer_only": True,
        },
        "variant_configs": configs,
        "rows": rows,
        "summary": build_summary(rows),
    }
    return rows, payload


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    summary = payload["summary"]
    rows = payload["rows"]
    lines = [
        "# Margin Tail Modeling Research",
        "",
        "Research-only benchmark. Formal Predictor formulas and production defaults remain unchanged.",
        "",
        "## Summary",
        "",
        f"- Best GD>=3 calibration: `{summary['best_gd_3_plus_calibration']['variant']}`",
        f"- Best Top-3 correct score: `{summary['best_correct_score_top3']['variant']}`",
        f"- Best Top-5 correct score: `{summary['best_correct_score_top5']['variant']}`",
        f"- Most conservative non-baseline: `{summary['most_conservative_non_baseline']['variant']}`",
        f"- Keep formal baseline unchanged: `{summary['recommendation']['keep_formal_model_baseline_unchanged']}`",
        "",
        "## Results",
        "",
        "| Variant | LogLoss | Brier | Top-3 | Top-5 | GD>=3 Error | Fav 3+ Error | KL Drift | MAD Drift |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['variant']} | {row['log_loss']:.6f} | {row['brier_score']:.6f} | "
            f"{row['correct_score_top3_accuracy']:.6f} | {row['correct_score_top5_accuracy']:.6f} | "
            f"{row['gd_3_plus_calibration_error']:.6f} | "
            f"{row['favorite_win_by_3_plus_calibration_error']:.6f} | "
            f"{row['score_matrix_kl_drift']:.6f} | {row['score_matrix_mad_drift']:.6f} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(
    rows: list[dict[str, Any]],
    payload: dict[str, Any],
    csv_path: Path,
    json_path: Path,
    markdown_path: Path,
) -> None:
    write_csv(rows, csv_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_markdown(payload, markdown_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run margin-tail modeling research benchmark.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/margin_tail_modeling_research.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/margin_tail_modeling_research.json"),
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("results/margin_tail_modeling_research.md"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = build_margin_tail_modeling_research(args.input, args.team_universe)
    write_outputs(rows, payload, args.output_csv, args.output_json, args.output_md)
    summary = payload["summary"]

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    print(f"output_md: {args.output_md}")
    print(f"best_gd_3_plus_calibration: {summary['best_gd_3_plus_calibration']['variant']}")
    print(f"best_top3: {summary['best_correct_score_top3']['variant']}")
    print(f"keep_formal_model_baseline_unchanged: {summary['recommendation']['keep_formal_model_baseline_unchanged']}")


if __name__ == "__main__":
    main()
