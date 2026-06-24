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

from src.model.expected_goals import MIN_XG
from src.model.metrics import accuracy, brier_score, multiclass_log_loss
from src.model.poisson import GAMMA, outcome_probabilities, score_matrix
from src.tuning.evaluation import actual_label
from src.tuning.final_worldcup_model_benchmark import matrix_expected_total_goals
from src.tuning.tune_dixon_coles_rho import CALIBRATED_XG_WORLDCUP_V1, top_scoreline
from src.tuning.worldcup_xg_parameter_search import load_target_rows, neutral_symmetric_xg

RHO = 0.05
NORMAL_WEIGHTS = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5)
DOMINATION_THRESHOLD = 250.0
DOMINATION_BOOST_PER_ELO = 0.0018
DOMINATION_PENALTY_PER_ELO = 0.0005

REPORT_COLUMNS = [
    "normal_weight",
    "domination_weight",
    "matches",
    "accuracy",
    "log_loss",
    "brier_score",
    "correct_score_top1_accuracy",
    "goal_difference_mae",
    "total_goals_mae",
    "predicted_avg_total_goals",
    "actual_avg_total_goals",
    "predicted_draw_probability",
    "actual_draw_rate",
    "draw_probability_calibration_error",
    "affected_matches",
    "avg_abs_elo_diff",
    "avg_abs_xg_shift",
]


def normal_worldcup_xg(team_a_elo: float, team_b_elo: float) -> tuple[float, float]:
    return neutral_symmetric_xg(
        team_a_elo,
        team_b_elo,
        base=float(CALIBRATED_XG_WORLDCUP_V1["base"]),
        c1=float(CALIBRATED_XG_WORLDCUP_V1["c1"]),
        scale=float(CALIBRATED_XG_WORLDCUP_V1["scale"]),
    )


def domination_xg(
    normal_team_a_xg: float,
    normal_team_b_xg: float,
    team_a_elo: float,
    team_b_elo: float,
) -> tuple[float, float]:
    team_a_xg = normal_team_a_xg
    team_b_xg = normal_team_b_xg
    elo_diff = team_a_elo - team_b_elo

    if elo_diff > DOMINATION_THRESHOLD:
        excess = elo_diff - DOMINATION_THRESHOLD
        team_a_xg += excess * DOMINATION_BOOST_PER_ELO
        team_b_xg -= excess * DOMINATION_PENALTY_PER_ELO
    elif elo_diff < -DOMINATION_THRESHOLD:
        excess = -elo_diff - DOMINATION_THRESHOLD
        team_b_xg += excess * DOMINATION_BOOST_PER_ELO
        team_a_xg -= excess * DOMINATION_PENALTY_PER_ELO

    return max(MIN_XG, team_a_xg), max(MIN_XG, team_b_xg)


def blend_xg(
    normal_team_a_xg: float,
    normal_team_b_xg: float,
    domination_team_a_xg: float,
    domination_team_b_xg: float,
    normal_weight: float,
) -> tuple[float, float]:
    domination_weight = 1.0 - normal_weight
    return (
        max(MIN_XG, normal_weight * normal_team_a_xg + domination_weight * domination_team_a_xg),
        max(MIN_XG, normal_weight * normal_team_b_xg + domination_weight * domination_team_b_xg),
    )


def score_probability_delta(
    first: list[dict[str, float | int]],
    second: list[dict[str, float | int]],
) -> float:
    return sum(
        abs(float(first_cell["probability"]) - float(second_cell["probability"]))
        for first_cell, second_cell in zip(first, second, strict=True)
    ) / len(first)


def evaluate_weight(rows: list[dict[str, Any]], normal_weight: float) -> dict[str, Any]:
    if not rows:
        raise ValueError("at least one neutral World Cup/Euro row is required")

    labels: list[str] = []
    probabilities: list[dict[str, float]] = []
    correct_score_hits = 0
    goal_difference_errors: list[float] = []
    total_goal_errors: list[float] = []
    predicted_total_goals: list[float] = []
    actual_total_goals: list[int] = []
    predicted_draw_probs: list[float] = []
    actual_draws = 0
    abs_elo_diffs: list[float] = []
    abs_xg_shifts: list[float] = []
    affected_matches = 0

    for row in rows:
        team_a_elo = float(row["home_pre_match_elo"])
        team_b_elo = float(row["away_pre_match_elo"])
        team_a_score = int(row["home_score"])
        team_b_score = int(row["away_score"])

        normal_a, normal_b = normal_worldcup_xg(team_a_elo, team_b_elo)
        domination_a, domination_b = domination_xg(normal_a, normal_b, team_a_elo, team_b_elo)
        team_a_xg, team_b_xg = blend_xg(normal_a, normal_b, domination_a, domination_b, normal_weight)

        matrix = score_matrix(team_a_xg, team_b_xg, gamma=GAMMA, rho=RHO)
        outcome_probs = outcome_probabilities(matrix)
        label = actual_label(team_a_score, team_b_score)

        labels.append(label)
        probabilities.append(outcome_probs)
        if top_scoreline(matrix) == (team_a_score, team_b_score):
            correct_score_hits += 1
        if team_a_score == team_b_score:
            actual_draws += 1

        goal_difference_errors.append(abs((team_a_xg - team_b_xg) - (team_a_score - team_b_score)))
        total_goal_errors.append(abs((team_a_xg + team_b_xg) - (team_a_score + team_b_score)))
        predicted_total_goals.append(matrix_expected_total_goals(matrix))
        actual_total_goals.append(team_a_score + team_b_score)
        predicted_draw_probs.append(outcome_probs["draw"])
        elo_diff = abs(team_a_elo - team_b_elo)
        abs_elo_diffs.append(elo_diff)
        xg_shift = abs(team_a_xg - normal_a) + abs(team_b_xg - normal_b)
        abs_xg_shifts.append(xg_shift)
        if elo_diff > DOMINATION_THRESHOLD:
            affected_matches += 1

    match_count = len(rows)
    predicted_draw_probability = statistics.mean(predicted_draw_probs)
    actual_draw_rate = actual_draws / match_count
    return {
        "normal_weight": normal_weight,
        "domination_weight": 1.0 - normal_weight,
        "matches": match_count,
        "accuracy": accuracy(labels, probabilities),
        "log_loss": multiclass_log_loss(labels, probabilities),
        "brier_score": brier_score(labels, probabilities),
        "correct_score_top1_accuracy": correct_score_hits / match_count,
        "goal_difference_mae": statistics.mean(goal_difference_errors),
        "total_goals_mae": statistics.mean(total_goal_errors),
        "predicted_avg_total_goals": statistics.mean(predicted_total_goals),
        "actual_avg_total_goals": statistics.mean(actual_total_goals),
        "predicted_draw_probability": predicted_draw_probability,
        "actual_draw_rate": actual_draw_rate,
        "draw_probability_calibration_error": abs(predicted_draw_probability - actual_draw_rate),
        "affected_matches": affected_matches,
        "avg_abs_elo_diff": statistics.mean(abs_elo_diffs),
        "avg_abs_xg_shift": statistics.mean(abs_xg_shifts),
    }


def evaluate_subset(rows: list[dict[str, Any]], normal_weight: float, subset_name: str) -> dict[str, Any]:
    metrics = evaluate_weight(rows, normal_weight)
    return {"subset": subset_name, **metrics}


def match_effect_rows(rows: list[dict[str, Any]], normal_weight: float) -> list[dict[str, Any]]:
    effects: list[dict[str, Any]] = []
    for row in rows:
        team_a_elo = float(row["home_pre_match_elo"])
        team_b_elo = float(row["away_pre_match_elo"])
        normal_a, normal_b = normal_worldcup_xg(team_a_elo, team_b_elo)
        domination_a, domination_b = domination_xg(normal_a, normal_b, team_a_elo, team_b_elo)
        blended_a, blended_b = blend_xg(normal_a, normal_b, domination_a, domination_b, normal_weight)

        normal_matrix = score_matrix(normal_a, normal_b, gamma=GAMMA, rho=RHO)
        blended_matrix = score_matrix(blended_a, blended_b, gamma=GAMMA, rho=RHO)
        normal_probs = outcome_probabilities(normal_matrix)
        blended_probs = outcome_probabilities(blended_matrix)
        win_key = "home" if team_a_elo >= team_b_elo else "away"
        stronger_team = str(row["home_team"] if team_a_elo >= team_b_elo else row["away_team"])
        weaker_team = str(row["away_team"] if team_a_elo >= team_b_elo else row["home_team"])

        effects.append(
            {
                "date": row["date"],
                "tournament": row["tournament"],
                "team_a": row["home_team"],
                "team_b": row["away_team"],
                "score": f"{row['home_score']}-{row['away_score']}",
                "elo_diff": team_a_elo - team_b_elo,
                "abs_elo_diff": abs(team_a_elo - team_b_elo),
                "stronger_team": stronger_team,
                "weaker_team": weaker_team,
                "normal_team_a_xg": normal_a,
                "normal_team_b_xg": normal_b,
                "domination_team_a_xg": domination_a,
                "domination_team_b_xg": domination_b,
                "blended_team_a_xg": blended_a,
                "blended_team_b_xg": blended_b,
                "team_a_xg_delta": blended_a - normal_a,
                "team_b_xg_delta": blended_b - normal_b,
                "stronger_win_prob_delta": blended_probs[win_key] - normal_probs[win_key],
                "draw_prob_delta": blended_probs["draw"] - normal_probs["draw"],
                "score_matrix_mean_abs_delta": score_probability_delta(normal_matrix, blended_matrix),
                "xg_shift": abs(blended_a - normal_a) + abs(blended_b - normal_b),
            }
        )
    return sorted(
        effects,
        key=lambda effect: (
            abs(float(effect["stronger_win_prob_delta"])),
            abs(float(effect["xg_shift"])),
        ),
        reverse=True,
    )


def build_summary(rows: list[dict[str, Any]], target_rows: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = next(row for row in rows if float(row["normal_weight"]) == 1.0)
    current = next(row for row in rows if float(row["normal_weight"]) == 0.7)
    best_accuracy = max(rows, key=lambda row: float(row["accuracy"]))
    best_log_loss = min(rows, key=lambda row: float(row["log_loss"]))
    best_brier = min(rows, key=lambda row: float(row["brier_score"]))
    best_correct_score = max(rows, key=lambda row: float(row["correct_score_top1_accuracy"]))
    best_goal_diff = min(rows, key=lambda row: float(row["goal_difference_mae"]))
    best_total_goals = min(rows, key=lambda row: float(row["total_goals_mae"]))
    best_draw_calibration = min(rows, key=lambda row: float(row["draw_probability_calibration_error"]))

    affected_rows = [
        row
        for row in target_rows
        if abs(float(row["home_pre_match_elo"]) - float(row["away_pre_match_elo"])) > DOMINATION_THRESHOLD
    ]
    unaffected_rows = [
        row
        for row in target_rows
        if abs(float(row["home_pre_match_elo"]) - float(row["away_pre_match_elo"])) <= DOMINATION_THRESHOLD
    ]
    subset_rows = []
    if affected_rows:
        subset_rows.extend(
            [
                evaluate_subset(affected_rows, 1.0, "affected_elo_diff_gt_250"),
                evaluate_subset(affected_rows, 0.7, "affected_elo_diff_gt_250"),
            ]
        )
    if unaffected_rows:
        subset_rows.extend(
            [
                evaluate_subset(unaffected_rows, 1.0, "unaffected_elo_diff_lte_250"),
                evaluate_subset(unaffected_rows, 0.7, "unaffected_elo_diff_lte_250"),
            ]
        )

    current_effects = match_effect_rows(target_rows, 0.7)
    current_vs_baseline = {
        "accuracy_delta": float(current["accuracy"]) - float(baseline["accuracy"]),
        "log_loss_delta": float(baseline["log_loss"]) - float(current["log_loss"]),
        "brier_delta": float(baseline["brier_score"]) - float(current["brier_score"]),
        "correct_score_top1_accuracy_delta": float(current["correct_score_top1_accuracy"])
        - float(baseline["correct_score_top1_accuracy"]),
        "goal_difference_mae_delta": float(baseline["goal_difference_mae"])
        - float(current["goal_difference_mae"]),
        "total_goals_mae_delta": float(baseline["total_goals_mae"]) - float(current["total_goals_mae"]),
    }

    over_amplification_flags = {
        "current_increases_predicted_avg_total_goals": float(current["predicted_avg_total_goals"])
        > float(baseline["predicted_avg_total_goals"]),
        "current_worse_log_loss_than_baseline": float(current["log_loss"]) > float(baseline["log_loss"]),
        "current_worse_brier_than_baseline": float(current["brier_score"])
        > float(baseline["brier_score"]),
        "current_worse_goal_difference_mae_than_baseline": float(current["goal_difference_mae"])
        > float(baseline["goal_difference_mae"]),
    }
    return {
        "best_accuracy": best_accuracy,
        "best_log_loss": best_log_loss,
        "best_brier_score": best_brier,
        "best_correct_score_top1_accuracy": best_correct_score,
        "best_goal_difference_mae": best_goal_diff,
        "best_total_goals_mae": best_total_goals,
        "best_draw_probability_calibration": best_draw_calibration,
        "current_70_30": current,
        "baseline_100_normal": baseline,
        "current_70_30_vs_100_normal": current_vs_baseline,
        "subset_comparison_100_normal_vs_70_30": subset_rows,
        "largest_affected_matches_at_70_30": current_effects[:20],
        "over_amplification_flags": over_amplification_flags,
        "recommendation": {
            "current_70_30_is_best_log_loss": float(current["normal_weight"])
            == float(best_log_loss["normal_weight"]),
            "domination_layer_improves_log_loss": float(best_log_loss["log_loss"]) < float(baseline["log_loss"]),
            "domination_layer_improves_brier": float(best_brier["brier_score"])
            < float(baseline["brier_score"]),
            "retain_domination_layer_for_worldcup_candidate": (
                float(best_log_loss["log_loss"]) < float(baseline["log_loss"])
                and float(best_brier["brier_score"]) < float(baseline["brier_score"])
            ),
            "selection_metric": "log_loss",
        },
    }


def build_domination_layer_benchmark(
    input_path: Path,
    team_universe_path: Path,
    normal_weights: tuple[float, ...] = NORMAL_WEIGHTS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target_rows, source_summary = load_target_rows(input_path, team_universe_path)
    rows = [evaluate_weight(target_rows, normal_weight) for normal_weight in normal_weights]
    payload = {
        "benchmark": "domination_layer_benchmark",
        "dataset": {
            "label": "FIFA World Cup + UEFA Euro neutral matches",
            "universe": "FIFA + historical national teams",
            **source_summary,
        },
        "model_context": {
            "normal_xg": {
                "name": "calibrated_xg_worldcup_v1_candidate",
                **CALIBRATED_XG_WORLDCUP_V1,
            },
            "domination_layer": {
                "threshold_elo_diff": DOMINATION_THRESHOLD,
                "favorite_boost_per_excess_elo": DOMINATION_BOOST_PER_ELO,
                "underdog_penalty_per_excess_elo": DOMINATION_PENALTY_PER_ELO,
                "min_xg_floor": MIN_XG,
            },
            "dixon_coles_rho": RHO,
            "bivariate_poisson_gamma": GAMMA,
        },
        "search_space": {
            "normal_weight": list(normal_weights),
            "domination_weight": [1.0 - weight for weight in normal_weights],
        },
        "formal_model_formulas_unchanged": True,
        "rows": rows,
        "summary": build_summary(rows, target_rows),
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
    parser = argparse.ArgumentParser(description="Benchmark production-style domination xG layer.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/domination_layer_benchmark.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/domination_layer_benchmark.json"),
    )
    parser.add_argument("--normal-weight", action="append", help="Candidate normal xG blend weight.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    normal_weights = _parse_float_tuple(args.normal_weight, NORMAL_WEIGHTS)
    rows, payload = build_domination_layer_benchmark(args.input, args.team_universe, normal_weights)
    write_outputs(rows, payload, args.output_csv, args.output_json)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    print("normal_weight domination_weight accuracy log_loss brier_score correct_score_top1 goal_diff_mae")
    for row in rows:
        print(
            f"{float(row['normal_weight']):.2f} "
            f"{float(row['domination_weight']):.2f} "
            f"{float(row['accuracy']):.6f} "
            f"{float(row['log_loss']):.6f} "
            f"{float(row['brier_score']):.6f} "
            f"{float(row['correct_score_top1_accuracy']):.6f} "
            f"{float(row['goal_difference_mae']):.6f}"
        )

    summary = payload["summary"]
    current_delta = summary["current_70_30_vs_100_normal"]
    print(
        "current_70_30_vs_100_normal: "
        f"accuracy_delta={float(current_delta['accuracy_delta']):.6f} "
        f"log_loss_delta={float(current_delta['log_loss_delta']):.6f} "
        f"brier_delta={float(current_delta['brier_delta']):.6f}"
    )
    print(f"best_log_loss_normal_weight: {summary['best_log_loss']['normal_weight']}")
    print(
        "retain_domination_layer_for_worldcup_candidate: "
        f"{summary['recommendation']['retain_domination_layer_for_worldcup_candidate']}"
    )


if __name__ == "__main__":
    main()
