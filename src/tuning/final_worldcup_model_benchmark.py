from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model.elo_rebuilder import MatchInput, parse_match_rows, rebuild_elo_history
from src.model.metrics import accuracy, brier_score, multiclass_log_loss
from src.model.poisson import GAMMA, outcome_probabilities, score_matrix
from src.tuning.evaluation import actual_label
from src.tuning.neutral_xg_benchmark import ASYMMETRIC_XG, CALIBRATED_ELO_V3, asymmetric_xg
from src.tuning.time_split_validation import filter_matches_for_universe
from src.tuning.tune_dixon_coles_rho import (
    CALIBRATED_XG_WORLDCUP_V1,
    LOW_SCORELINES,
    score_probability,
    top_scoreline,
)
from src.tuning.tune_gd_shrinkage import gd_shrinkage_multiplier
from src.tuning.tune_k_factor import read_match_rows
from src.tuning.universe_benchmark import read_team_universe
from src.tuning.worldcup_xg_parameter_search import TARGET_TOURNAMENTS, neutral_symmetric_xg

STANDARD_ELO = {
    "model": "standard_elo_v1",
    "k_factor": 20.0,
    "goal_diff_shrinkage_alpha": None,
}

MODEL_CONFIGS = [
    {
        "model": "baseline_current",
        "elo": "standard_elo_v1",
        "xg": "current_asymmetric_formula",
        "rho": -0.05,
        "gamma": GAMMA,
    },
    {
        "model": "elo_only_calibrated",
        "elo": "calibrated_elo_v3_candidate",
        "xg": "current_asymmetric_formula",
        "rho": -0.05,
        "gamma": GAMMA,
    },
    {
        "model": "elo_xg_calibrated",
        "elo": "calibrated_elo_v3_candidate",
        "xg": "calibrated_xg_worldcup_v1_candidate",
        "rho": -0.05,
        "gamma": GAMMA,
    },
    {
        "model": "full_calibrated_worldcup_candidate",
        "elo": "calibrated_elo_v3_candidate",
        "xg": "calibrated_xg_worldcup_v1_candidate",
        "rho": 0.05,
        "gamma": GAMMA,
    },
]

REPORT_COLUMNS = [
    "model",
    "matches",
    "accuracy",
    "log_loss",
    "brier_score",
    "correct_score_top1_accuracy",
    "predicted_draw_probability",
    "actual_draw_rate",
    "predicted_low_score_probability",
    "actual_low_score_rate",
    "predicted_avg_total_goals",
    "actual_avg_total_goals",
]

XgFn = Callable[[float, float], tuple[float, float]]


def is_target_row(row: dict[str, Any]) -> bool:
    return (
        str(row["tournament"]) in TARGET_TOURNAMENTS
        and str(row.get("neutral", "")).strip().upper() == "TRUE"
    )


def rebuild_standard(matches: list[MatchInput]) -> list[dict[str, Any]]:
    return rebuild_elo_history(
        matches,
        k_factor=float(STANDARD_ELO["k_factor"]),
        model_version=str(STANDARD_ELO["model"]),
    )


def rebuild_calibrated_v3(matches: list[MatchInput]) -> list[dict[str, Any]]:
    return rebuild_elo_history(
        matches,
        k_factor=float(CALIBRATED_ELO_V3["k_factor"]),
        goal_diff_multiplier_fn=gd_shrinkage_multiplier(
            float(CALIBRATED_ELO_V3["goal_diff_shrinkage_alpha"])
        ),
        model_version=str(CALIBRATED_ELO_V3["model"]),
    )


def calibrated_worldcup_xg(team_a_elo: float, team_b_elo: float) -> tuple[float, float]:
    return neutral_symmetric_xg(
        team_a_elo,
        team_b_elo,
        base=float(CALIBRATED_XG_WORLDCUP_V1["base"]),
        c1=float(CALIBRATED_XG_WORLDCUP_V1["c1"]),
        scale=float(CALIBRATED_XG_WORLDCUP_V1["scale"]),
    )


def matrix_expected_total_goals(matrix: list[dict[str, float | int]]) -> float:
    return sum((int(cell["home"]) + int(cell["away"])) * float(cell["probability"]) for cell in matrix)


def evaluate_model_rows(
    model_name: str,
    rows: list[dict[str, Any]],
    xg_fn: XgFn,
    rho: float,
    gamma: float,
) -> dict[str, Any]:
    if not rows:
        raise ValueError(f"at least one target row is required for {model_name!r}")

    y_true: list[str] = []
    y_prob: list[dict[str, float]] = []
    correct_score_hits = 0
    actual_draw_hits = 0
    actual_low_score_hits = 0
    predicted_draw_probs: list[float] = []
    predicted_low_score_probs: list[float] = []
    predicted_total_goals: list[float] = []
    actual_total_goals: list[int] = []

    for row in rows:
        home_score = int(row["home_score"])
        away_score = int(row["away_score"])
        home_xg, away_xg = xg_fn(
            float(row["home_pre_match_elo"]),
            float(row["away_pre_match_elo"]),
        )
        matrix = score_matrix(home_xg, away_xg, gamma=gamma, rho=rho)
        outcome_probs = outcome_probabilities(matrix)
        label = actual_label(home_score, away_score)

        y_true.append(label)
        y_prob.append(outcome_probs)
        if top_scoreline(matrix) == (home_score, away_score):
            correct_score_hits += 1
        if home_score == away_score:
            actual_draw_hits += 1
        if (home_score, away_score) in LOW_SCORELINES:
            actual_low_score_hits += 1

        predicted_draw_probs.append(outcome_probs["draw"])
        predicted_low_score_probs.append(
            sum(score_probability(matrix, home, away) for home, away in LOW_SCORELINES)
        )
        predicted_total_goals.append(matrix_expected_total_goals(matrix))
        actual_total_goals.append(home_score + away_score)

    match_count = len(rows)
    return {
        "model": model_name,
        "matches": match_count,
        "accuracy": accuracy(y_true, y_prob),
        "log_loss": multiclass_log_loss(y_true, y_prob),
        "brier_score": brier_score(y_true, y_prob),
        "correct_score_top1_accuracy": correct_score_hits / match_count,
        "predicted_draw_probability": sum(predicted_draw_probs) / match_count,
        "actual_draw_rate": actual_draw_hits / match_count,
        "predicted_low_score_probability": sum(predicted_low_score_probs) / match_count,
        "actual_low_score_rate": actual_low_score_hits / match_count,
        "predicted_avg_total_goals": sum(predicted_total_goals) / match_count,
        "actual_avg_total_goals": sum(actual_total_goals) / match_count,
    }


def load_rebuilt_target_rows(
    input_path: Path,
    team_universe_path: Path,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    source_rows = read_match_rows(input_path)
    matches = parse_match_rows(source_rows, skip_unplayed=True)
    team_universe = read_team_universe(team_universe_path)
    universe_matches = filter_matches_for_universe(matches, team_universe)
    if not universe_matches:
        raise ValueError("no matches remain after FIFA+historical universe filtering")

    rebuilt_by_elo = {
        "standard_elo_v1": rebuild_standard(universe_matches),
        "calibrated_elo_v3_candidate": rebuild_calibrated_v3(universe_matches),
    }
    target_by_elo = {
        name: [row for row in rows if is_target_row(row)]
        for name, rows in rebuilt_by_elo.items()
    }
    for name, rows in target_by_elo.items():
        if not rows:
            raise ValueError(f"no target rows found for {name}")
    return target_by_elo, {
        "source_matches": len(matches),
        "universe_matches": len(universe_matches),
        "target_matches": len(next(iter(target_by_elo.values()))),
    }


def xg_function(name: str) -> XgFn:
    if name == "current_asymmetric_formula":
        return asymmetric_xg
    if name == "calibrated_xg_worldcup_v1_candidate":
        return calibrated_worldcup_xg
    raise ValueError(f"unknown xG formula {name!r}")


def metric_deltas(reference: dict[str, Any], candidate: dict[str, Any]) -> dict[str, float]:
    return {
        "accuracy_delta": float(candidate["accuracy"]) - float(reference["accuracy"]),
        "log_loss_delta": float(reference["log_loss"]) - float(candidate["log_loss"]),
        "brier_delta": float(reference["brier_score"]) - float(candidate["brier_score"]),
        "correct_score_top1_accuracy_delta": float(candidate["correct_score_top1_accuracy"])
        - float(reference["correct_score_top1_accuracy"]),
    }


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_model = {str(row["model"]): row for row in rows}
    baseline = by_model["baseline_current"]
    elo_only = by_model["elo_only_calibrated"]
    elo_xg = by_model["elo_xg_calibrated"]
    full = by_model["full_calibrated_worldcup_candidate"]
    layer_contributions = {
        "elo": metric_deltas(baseline, elo_only),
        "xg": metric_deltas(elo_only, elo_xg),
        "dc": metric_deltas(elo_xg, full),
    }
    largest_log_loss_layer = max(
        layer_contributions,
        key=lambda layer: float(layer_contributions[layer]["log_loss_delta"]),
    )
    largest_brier_layer = max(
        layer_contributions,
        key=lambda layer: float(layer_contributions[layer]["brier_delta"]),
    )
    return {
        "baseline_current_to_full_calibrated": metric_deltas(baseline, full),
        "layer_contributions": layer_contributions,
        "largest_contribution": {
            "by_log_loss": largest_log_loss_layer,
            "by_brier_score": largest_brier_layer,
        },
        "best_accuracy": max(rows, key=lambda row: float(row["accuracy"])),
        "best_log_loss": min(rows, key=lambda row: float(row["log_loss"])),
        "best_brier_score": min(rows, key=lambda row: float(row["brier_score"])),
        "best_correct_score_top1_accuracy": max(
            rows,
            key=lambda row: float(row["correct_score_top1_accuracy"]),
        ),
        "recommendation": {
            "create_final_worldcup_model_v1_candidate": (
                float(full["log_loss"]) < float(baseline["log_loss"])
                and float(full["brier_score"]) < float(baseline["brier_score"])
            ),
            "shadow_mode_ready": (
                float(full["log_loss"]) < float(baseline["log_loss"])
                and float(full["brier_score"]) < float(baseline["brier_score"])
            ),
            "candidate": {
                "elo": "calibrated_elo_v3_candidate",
                "xg": "calibrated_xg_worldcup_v1_candidate",
                "rho": 0.05,
                "gamma": GAMMA,
            },
        },
    }


def build_final_worldcup_model_benchmark(
    input_path: Path,
    team_universe_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target_by_elo, source_summary = load_rebuilt_target_rows(input_path, team_universe_path)
    rows: list[dict[str, Any]] = []
    for config in MODEL_CONFIGS:
        model_rows = target_by_elo[str(config["elo"])]
        rows.append(
            evaluate_model_rows(
                str(config["model"]),
                model_rows,
                xg_function(str(config["xg"])),
                rho=float(config["rho"]),
                gamma=float(config["gamma"]),
            )
        )

    payload = {
        "universe": {
            "name": "fifa_historical",
            "label": "FIFA + historical national teams",
            **source_summary,
        },
        "target": {
            "tournaments": list(TARGET_TOURNAMENTS),
            "neutral_only": True,
        },
        "model_configs": MODEL_CONFIGS,
        "elo_configs": {
            "standard_elo_v1": STANDARD_ELO,
            "calibrated_elo_v3_candidate": CALIBRATED_ELO_V3,
        },
        "xg_configs": {
            "current_asymmetric_formula": ASYMMETRIC_XG,
            "calibrated_xg_worldcup_v1_candidate": CALIBRATED_XG_WORLDCUP_V1,
        },
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build final World Cup neutral model benchmark.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/final_worldcup_model_benchmark.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/final_worldcup_model_benchmark.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = build_final_worldcup_model_benchmark(args.input, args.team_universe)
    write_outputs(rows, payload, args.output_csv, args.output_json)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    print("model accuracy log_loss brier_score correct_score_top1_accuracy")
    for row in rows:
        print(
            f"{row['model']} "
            f"{float(row['accuracy']):.6f} "
            f"{float(row['log_loss']):.6f} "
            f"{float(row['brier_score']):.6f} "
            f"{float(row['correct_score_top1_accuracy']):.6f}"
        )
    summary = payload["summary"]
    print(
        "baseline_to_full: "
        f"accuracy_delta={float(summary['baseline_current_to_full_calibrated']['accuracy_delta']):.6f} "
        f"log_loss_delta={float(summary['baseline_current_to_full_calibrated']['log_loss_delta']):.6f} "
        f"brier_delta={float(summary['baseline_current_to_full_calibrated']['brier_delta']):.6f}"
    )
    print(f"largest_log_loss_contribution: {summary['largest_contribution']['by_log_loss']}")


if __name__ == "__main__":
    main()
