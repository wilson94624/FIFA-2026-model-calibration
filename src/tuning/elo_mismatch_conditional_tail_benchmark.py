from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from datetime import date
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
from src.tuning.margin_tail_modeling_research import (
    favorite_tail_boost,
    favorite_win_by_three_probability,
    gd_tail_redistribution,
    matrix_kl_divergence,
    matrix_mad,
)
from src.tuning.score_tail_calibration_report import RHO, total_goals_probability, worldcup_xg
from src.tuning.worldcup_xg_parameter_search import load_target_rows

THRESHOLDS = (200, 250, 300, 350, 400)
ALPHAS = (0.04, 0.06, 0.08, 0.10, 0.12)

REPORT_COLUMNS = [
    "split",
    "variant",
    "method",
    "threshold",
    "alpha",
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
    "score_matrix_kl_drift",
    "score_matrix_mad_drift",
    "affected_match_count",
    "affected_match_rate",
]


def parse_match_date(row: dict[str, Any]) -> date:
    value = row["date"]
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def abs_elo_diff(row: dict[str, Any]) -> float:
    return abs(float(row["home_pre_match_elo"]) - float(row["away_pre_match_elo"]))


def build_variant_configs() -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = [
        {
            "variant": "baseline",
            "method": "baseline",
            "threshold": None,
            "alpha": None,
        }
    ]
    for threshold in THRESHOLDS:
        for alpha in ALPHAS:
            configs.append(
                {
                    "variant": f"conditional_gd_tail_threshold_{threshold}_alpha_{alpha:.2f}",
                    "method": "conditional_gd_tail_redistribution",
                    "threshold": threshold,
                    "alpha": alpha,
                }
            )
    for threshold in THRESHOLDS:
        for alpha in ALPHAS:
            configs.append(
                {
                    "variant": f"conditional_favorite_tail_threshold_{threshold}_alpha_{alpha:.2f}",
                    "method": "conditional_favorite_tail_boost",
                    "threshold": threshold,
                    "alpha": alpha,
                }
            )
    return configs


def split_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "all_pooled": rows,
        "fifa_world_cup_only": [
            row for row in rows if str(row["tournament"]) == "FIFA World Cup"
        ],
        "uefa_euro_only": [row for row in rows if str(row["tournament"]) == "UEFA Euro"],
        "world_cup_modern_1990_plus": [
            row
            for row in rows
            if str(row["tournament"]) == "FIFA World Cup"
            and parse_match_date(row) >= date(1990, 1, 1)
        ],
        "world_cup_recent_2000_plus": [
            row
            for row in rows
            if str(row["tournament"]) == "FIFA World Cup"
            and parse_match_date(row) >= date(2000, 1, 1)
        ],
        "high_mismatch_abs_elo_diff_300_plus": [
            row for row in rows if abs_elo_diff(row) >= 300.0
        ],
        "balanced_abs_elo_diff_lt_200": [
            row for row in rows if abs_elo_diff(row) < 200.0
        ],
    }


def analyze_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    analyzed: list[dict[str, Any]] = []
    for row in rows:
        home_elo = float(row["home_pre_match_elo"])
        away_elo = float(row["away_pre_match_elo"])
        home_xg, away_xg = worldcup_xg(home_elo, away_elo)
        home_score = int(row["home_score"])
        away_score = int(row["away_score"])
        home_is_favorite = home_elo >= away_elo
        favorite_score = home_score if home_is_favorite else away_score
        underdog_score = away_score if home_is_favorite else home_score
        analyzed.append(
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
                "abs_elo_diff": abs(home_elo - away_elo),
                "actual_favorite_win_by_3_plus": favorite_score - underdog_score >= 3,
            }
        )
    return analyzed


def should_apply(row: dict[str, Any], config: dict[str, Any]) -> bool:
    if config["method"] == "baseline":
        return False
    return float(row["abs_elo_diff"]) >= float(config["threshold"])


def apply_candidate(
    baseline_matrix: list[dict[str, float | int]],
    row: dict[str, Any],
    config: dict[str, Any],
) -> tuple[list[dict[str, float | int]], bool]:
    if not should_apply(row, config):
        return baseline_matrix, False
    alpha = float(config["alpha"])
    if config["method"] == "conditional_gd_tail_redistribution":
        return gd_tail_redistribution(baseline_matrix, alpha), True
    if config["method"] == "conditional_favorite_tail_boost":
        return favorite_tail_boost(baseline_matrix, alpha, bool(row["home_is_favorite"])), True
    raise ValueError(f"unknown method {config['method']!r}")


def evaluate_variant(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    labels: list[str] = []
    probabilities: list[dict[str, float]] = []
    top1_hits = 0
    top3_hits = 0
    top5_hits = 0
    gd_exact_hits = 0
    gd_pm1_hits = 0
    actual_gd_3_plus: list[bool] = []
    predicted_gd_3_plus: list[float] = []
    actual_favorite_3_plus: list[bool] = []
    predicted_favorite_3_plus: list[float] = []
    actual_total_4_plus: list[bool] = []
    predicted_total_4_plus: list[float] = []
    kl_drifts: list[float] = []
    mad_drifts: list[float] = []
    affected_count = 0

    for row in rows:
        baseline_matrix = score_matrix(row["home_xg"], row["away_xg"], gamma=GAMMA, rho=RHO)
        candidate_matrix, affected = apply_candidate(baseline_matrix, row, config)
        affected_count += 1 if affected else 0
        outcome_probs = outcome_probabilities(candidate_matrix)
        predicted_gd = predicted_goal_difference(candidate_matrix)

        labels.append(str(row["label"]))
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
        if predicted_gd == int(row["actual_goal_difference"]):
            gd_exact_hits += 1
        if abs(predicted_gd - int(row["actual_goal_difference"])) <= 1:
            gd_pm1_hits += 1

        actual_gd_3_plus.append(bool(row["actual_abs_goal_difference"] >= 3))
        predicted_gd_3_plus.append(blowout_probability(candidate_matrix))
        actual_favorite_3_plus.append(bool(row["actual_favorite_win_by_3_plus"]))
        predicted_favorite_3_plus.append(
            favorite_win_by_three_probability(candidate_matrix, bool(row["home_is_favorite"]))
        )
        actual_total_4_plus.append(bool(row["actual_total_goals"] >= 4))
        predicted_total_4_plus.append(total_goals_probability(candidate_matrix, 4))
        kl_drifts.append(matrix_kl_divergence(baseline_matrix, candidate_matrix))
        mad_drifts.append(matrix_mad(baseline_matrix, candidate_matrix))

    match_count = len(rows)
    actual_gd_rate = sum(actual_gd_3_plus) / match_count
    predicted_gd_probability = statistics.mean(predicted_gd_3_plus)
    actual_favorite_rate = sum(actual_favorite_3_plus) / match_count
    predicted_favorite_probability = statistics.mean(predicted_favorite_3_plus)
    actual_total_rate = sum(actual_total_4_plus) / match_count
    predicted_total_probability = statistics.mean(predicted_total_4_plus)
    return {
        "variant": config["variant"],
        "method": config["method"],
        "threshold": config["threshold"],
        "alpha": config["alpha"],
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
        "favorite_win_by_3_plus_calibration_error": abs(actual_favorite_rate - predicted_favorite_probability),
        "actual_total_goals_4_plus_rate": actual_total_rate,
        "predicted_total_goals_4_plus_probability": predicted_total_probability,
        "total_goals_4_plus_calibration_error": abs(actual_total_rate - predicted_total_probability),
        "score_matrix_kl_drift": statistics.mean(kl_drifts),
        "score_matrix_mad_drift": statistics.mean(mad_drifts),
        "affected_match_count": affected_count,
        "affected_match_rate": affected_count / match_count,
    }


def evaluate_split(
    split_name: str,
    rows: list[dict[str, Any]],
    configs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not rows:
        raise ValueError(f"split {split_name!r} has no rows")
    analyzed = analyze_rows(rows)
    return [{"split": split_name, **evaluate_variant(analyzed, config)} for config in configs]


def summarize_split(rows: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = next(row for row in rows if row["variant"] == "baseline")
    candidates = [row for row in rows if row["variant"] != "baseline"]
    best_gd = min(rows, key=lambda row: float(row["gd_3_plus_calibration_error"]))
    best_favorite = min(rows, key=lambda row: float(row["favorite_win_by_3_plus_calibration_error"]))
    best_top3 = max(rows, key=lambda row: float(row["correct_score_top3_accuracy"]))
    best_top5 = max(rows, key=lambda row: float(row["correct_score_top5_accuracy"]))
    best_conservative = min(
        candidates,
        key=lambda row: (
            float(row["gd_3_plus_calibration_error"]),
            float(row["score_matrix_mad_drift"]),
        ),
    )
    return {
        "baseline": baseline,
        "best_gd_3_plus_calibration": best_gd,
        "best_favorite_win_by_3_plus_calibration": best_favorite,
        "best_correct_score_top3": best_top3,
        "best_correct_score_top5": best_top5,
        "best_non_baseline_by_gd_then_drift": best_conservative,
        "best_gd_vs_baseline": {
            "gd_error_delta": float(baseline["gd_3_plus_calibration_error"])
            - float(best_gd["gd_3_plus_calibration_error"]),
            "favorite_error_delta": float(baseline["favorite_win_by_3_plus_calibration_error"])
            - float(best_gd["favorite_win_by_3_plus_calibration_error"]),
            "top3_delta": float(best_gd["correct_score_top3_accuracy"])
            - float(baseline["correct_score_top3_accuracy"]),
            "top5_delta": float(best_gd["correct_score_top5_accuracy"])
            - float(baseline["correct_score_top5_accuracy"]),
            "log_loss_delta": float(baseline["log_loss"]) - float(best_gd["log_loss"]),
            "brier_delta": float(baseline["brier_score"]) - float(best_gd["brier_score"]),
            "mad_drift": float(best_gd["score_matrix_mad_drift"]),
            "affected_match_rate": float(best_gd["affected_match_rate"]),
        },
    }


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_split: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_split.setdefault(str(row["split"]), []).append(row)
    split_summaries = {
        split: summarize_split(split_rows_) for split, split_rows_ in by_split.items()
    }
    high = split_summaries.get("high_mismatch_abs_elo_diff_300_plus")
    balanced = split_summaries.get("balanced_abs_elo_diff_lt_200")
    world_cup_modern = split_summaries.get("world_cup_modern_1990_plus")
    world_cup_recent = split_summaries.get("world_cup_recent_2000_plus")
    return {
        "split_summaries": split_summaries,
        "best_variants_by_split": {
            split: summary["best_gd_3_plus_calibration"]["variant"]
            for split, summary in split_summaries.items()
        },
        "recommendation": {
            "conditional_tail_more_stable_than_global": (
                balanced is not None
                and float(balanced["best_gd_vs_baseline"]["affected_match_rate"]) == 0.0
            ),
            "improves_high_mismatch_subset": (
                high is not None and float(high["best_gd_vs_baseline"]["gd_error_delta"]) > 0.0
            ),
            "hurts_balanced_subset": (
                balanced is not None
                and (
                float(balanced["best_gd_vs_baseline"]["gd_error_delta"]) < 0.0
                or float(balanced["best_gd_vs_baseline"]["top3_delta"]) < 0.0
                )
            ),
            "modern_world_cup_supports_correction": float(
                world_cup_modern["best_gd_vs_baseline"]["gd_error_delta"]
            )
            > 0.0 if world_cup_modern is not None else False,
            "recent_world_cup_supports_correction": float(
                world_cup_recent["best_gd_vs_baseline"]["gd_error_delta"]
            )
            > 0.0 if world_cup_recent is not None else False,
            "has_2026_group_stage_research_value": True,
            "continue_research": True,
            "keep_formal_model_baseline_unchanged": True,
        },
    }


def build_elo_mismatch_conditional_tail_benchmark(
    input_path: Path,
    team_universe_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target_rows, source_summary = load_target_rows(input_path, team_universe_path)
    splits = split_rows(target_rows)
    configs = build_variant_configs()
    rows: list[dict[str, Any]] = []
    for split_name, split_rows_ in splits.items():
        if not split_rows_:
            continue
        rows.extend(evaluate_split(split_name, split_rows_, configs))
    payload = {
        "benchmark": "elo_mismatch_conditional_tail_benchmark",
        "dataset": {
            "label": "FIFA World Cup + UEFA Euro neutral matches",
            "universe": "FIFA + historical national teams",
            **source_summary,
        },
        "model_context": {
            "baseline": "final_worldcup_model_v1_candidate",
            "formal_model_formulas_unchanged": True,
            "production_default_unchanged": True,
            "research_benchmark_layer_only": True,
        },
        "search_space": {
            "thresholds": list(THRESHOLDS),
            "alphas": list(ALPHAS),
            "methods": ["conditional_gd_tail_redistribution", "conditional_favorite_tail_boost"],
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
    lines = [
        "# Elo Mismatch Conditional Tail Benchmark",
        "",
        "Research-only benchmark. Formal Predictor formulas and production defaults remain unchanged.",
        "",
        "## Split Summary",
        "",
        "| Split | Matches | Best GD>=3 | GD Error Delta | Top-3 Delta | MAD Drift | Affected Rate |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for split, split_summary in summary["split_summaries"].items():
        best = split_summary["best_gd_3_plus_calibration"]
        delta = split_summary["best_gd_vs_baseline"]
        lines.append(
            f"| {split} | {best['matches']} | {best['variant']} | "
            f"{delta['gd_error_delta']:.6f} | {delta['top3_delta']:.6f} | "
            f"{delta['mad_drift']:.6f} | {delta['affected_match_rate']:.6f} |"
        )
    rec = summary["recommendation"]
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"- Conditional tail more stable than global: `{rec['conditional_tail_more_stable_than_global']}`",
            f"- Improves high mismatch subset: `{rec['improves_high_mismatch_subset']}`",
            f"- Hurts balanced subset: `{rec['hurts_balanced_subset']}`",
            f"- Has 2026 group-stage research value: `{rec['has_2026_group_stage_research_value']}`",
            f"- Keep formal model baseline unchanged: `{rec['keep_formal_model_baseline_unchanged']}`",
        ]
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
    parser = argparse.ArgumentParser(description="Run Elo mismatch conditional tail benchmark.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/elo_mismatch_conditional_tail_benchmark.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/elo_mismatch_conditional_tail_benchmark.json"),
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("results/elo_mismatch_conditional_tail_benchmark.md"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = build_elo_mismatch_conditional_tail_benchmark(args.input, args.team_universe)
    write_outputs(rows, payload, args.output_csv, args.output_json, args.output_md)
    rec = payload["summary"]["recommendation"]
    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    print(f"output_md: {args.output_md}")
    print(f"improves_high_mismatch_subset: {rec['improves_high_mismatch_subset']}")
    print(f"hurts_balanced_subset: {rec['hurts_balanced_subset']}")
    print(f"keep_formal_model_baseline_unchanged: {rec['keep_formal_model_baseline_unchanged']}")


if __name__ == "__main__":
    main()
