from __future__ import annotations

import argparse
import csv
import json
import math
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
    favorite_win_by_three_probability,
    matrix_mad,
)
from src.tuning.score_tail_calibration_report import RHO, total_goals_probability, worldcup_xg
from src.tuning.worldcup_xg_parameter_search import load_target_rows

SIZE_VALUES = (2, 3, 5, 8, 12, 20)
DRAW_FACTORS = (0.90, 0.95, 1.00, 1.05, 1.10)
MAX_GOALS = 5

REPORT_COLUMNS = [
    "split",
    "variant",
    "family",
    "size_r",
    "draw_factor",
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
    "actual_draw_rate",
    "predicted_draw_probability",
    "draw_calibration_error",
    "score_matrix_mad_drift",
]

ScoreCell = dict[str, float | int]


def negative_binomial_pmf(k: int, mean: float, size_r: float) -> float:
    if k < 0:
        return 0.0
    if mean <= 0:
        raise ValueError("mean must be positive")
    if size_r <= 0:
        raise ValueError("size_r must be positive")
    p = size_r / (size_r + mean)
    log_coeff = math.lgamma(k + size_r) - math.lgamma(size_r) - math.lgamma(k + 1)
    return math.exp(log_coeff + size_r * math.log(p) + k * math.log1p(-p))


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


def independent_negative_binomial_matrix(
    home_mean: float,
    away_mean: float,
    size_r: float,
    max_goals: int = MAX_GOALS,
    draw_factor: float = 1.0,
) -> list[ScoreCell]:
    home_probs = [negative_binomial_pmf(k, home_mean, size_r) for k in range(max_goals + 1)]
    away_probs = [negative_binomial_pmf(k, away_mean, size_r) for k in range(max_goals + 1)]
    matrix: list[ScoreCell] = []
    for home_goals in range(max_goals + 1):
        for away_goals in range(max_goals + 1):
            probability = home_probs[home_goals] * away_probs[away_goals]
            if home_goals == away_goals:
                probability *= draw_factor
            matrix.append({"home": home_goals, "away": away_goals, "probability": probability})
    return normalize_matrix(matrix)


def parse_match_date(row: dict[str, Any]) -> date:
    value = row["date"]
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def abs_elo_diff(row: dict[str, Any]) -> float:
    return abs(float(row["home_pre_match_elo"]) - float(row["away_pre_match_elo"]))


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


def build_variant_configs() -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = [
        {
            "variant": "baseline_bivariate_poisson",
            "family": "bivariate_poisson",
            "size_r": None,
            "draw_factor": None,
            "max_goals": 5,
        },
        {
            "variant": "baseline_bivariate_poisson_max_goals_10",
            "family": "bivariate_poisson",
            "size_r": None,
            "draw_factor": None,
            "max_goals": 10,
        },
    ]
    for size_r in SIZE_VALUES:
        configs.append(
            {
                "variant": f"independent_negative_binomial_r_{size_r}",
                "family": "independent_negative_binomial",
                "size_r": size_r,
                "draw_factor": 1.0,
                "max_goals": 5,
            }
        )
    for size_r in SIZE_VALUES:
        for draw_factor in DRAW_FACTORS:
            configs.append(
                {
                    "variant": f"negative_binomial_r_{size_r}_draw_{draw_factor:.2f}",
                    "family": "negative_binomial_with_draw_adjustment",
                    "size_r": size_r,
                    "draw_factor": draw_factor,
                    "max_goals": 5,
                }
            )
    return configs


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
                "actual_favorite_win_by_3_plus": favorite_score - underdog_score >= 3,
            }
        )
    return analyzed


def candidate_matrix(row: dict[str, Any], config: dict[str, Any]) -> list[ScoreCell]:
    if config["family"] == "bivariate_poisson":
        return score_matrix(
            row["home_xg"],
            row["away_xg"],
            max_goals=int(config["max_goals"]),
            gamma=GAMMA,
            rho=RHO,
        )
    if config["family"] in {
        "independent_negative_binomial",
        "negative_binomial_with_draw_adjustment",
    }:
        return independent_negative_binomial_matrix(
            row["home_xg"],
            row["away_xg"],
            size_r=float(config["size_r"]),
            max_goals=int(config["max_goals"]),
            draw_factor=float(config["draw_factor"]),
        )
    raise ValueError(f"unknown family {config['family']!r}")


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
    actual_draws: list[bool] = []
    predicted_draws: list[float] = []
    mad_drifts: list[float] = []

    for row in rows:
        baseline_matrix = score_matrix(row["home_xg"], row["away_xg"], gamma=GAMMA, rho=RHO)
        matrix = candidate_matrix(row, config)
        outcome_probs = outcome_probabilities(matrix)
        predicted_gd = predicted_goal_difference(matrix)

        labels.append(str(row["label"]))
        probabilities.append(outcome_probs)
        if any(
            home == row["home_score"] and away == row["away_score"]
            for home, away, _ in top_scorelines(matrix, 1)
        ):
            top1_hits += 1
        if any(
            home == row["home_score"] and away == row["away_score"]
            for home, away, _ in top_scorelines(matrix, 3)
        ):
            top3_hits += 1
        if any(
            home == row["home_score"] and away == row["away_score"]
            for home, away, _ in top_scorelines(matrix, 5)
        ):
            top5_hits += 1
        if predicted_gd == int(row["actual_goal_difference"]):
            gd_exact_hits += 1
        if abs(predicted_gd - int(row["actual_goal_difference"])) <= 1:
            gd_pm1_hits += 1

        actual_gd_3_plus.append(bool(row["actual_abs_goal_difference"] >= 3))
        predicted_gd_3_plus.append(blowout_probability(matrix))
        actual_favorite_3_plus.append(bool(row["actual_favorite_win_by_3_plus"]))
        predicted_favorite_3_plus.append(
            favorite_win_by_three_probability(matrix, bool(row["home_is_favorite"]))
        )
        actual_total_4_plus.append(bool(row["actual_total_goals"] >= 4))
        predicted_total_4_plus.append(total_goals_probability(matrix, 4))
        actual_draws.append(row["home_score"] == row["away_score"])
        predicted_draws.append(outcome_probs["draw"])
        mad_drifts.append(matrix_mad(baseline_matrix, matrix))

    match_count = len(rows)
    actual_gd_rate = sum(actual_gd_3_plus) / match_count
    predicted_gd_probability = statistics.mean(predicted_gd_3_plus)
    actual_favorite_rate = sum(actual_favorite_3_plus) / match_count
    predicted_favorite_probability = statistics.mean(predicted_favorite_3_plus)
    actual_total_rate = sum(actual_total_4_plus) / match_count
    predicted_total_probability = statistics.mean(predicted_total_4_plus)
    actual_draw_rate = sum(actual_draws) / match_count
    predicted_draw_probability = statistics.mean(predicted_draws)
    return {
        "variant": config["variant"],
        "family": config["family"],
        "size_r": config["size_r"],
        "draw_factor": config["draw_factor"],
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
        "actual_draw_rate": actual_draw_rate,
        "predicted_draw_probability": predicted_draw_probability,
        "draw_calibration_error": abs(actual_draw_rate - predicted_draw_probability),
        "score_matrix_mad_drift": statistics.mean(mad_drifts),
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
    baseline = next(row for row in rows if row["variant"] == "baseline_bivariate_poisson")
    nb_rows = [row for row in rows if str(row["family"]).startswith("negative_binomial")]
    best_nb_log_loss = min(nb_rows, key=lambda row: float(row["log_loss"]))
    best_nb_brier = min(nb_rows, key=lambda row: float(row["brier_score"]))
    best_nb_top3 = max(nb_rows, key=lambda row: float(row["correct_score_top3_accuracy"]))
    best_nb_top5 = max(nb_rows, key=lambda row: float(row["correct_score_top5_accuracy"]))
    best_nb_gd = min(nb_rows, key=lambda row: float(row["gd_3_plus_calibration_error"]))
    return {
        "baseline": baseline,
        "best_nb_log_loss": best_nb_log_loss,
        "best_nb_brier": best_nb_brier,
        "best_nb_correct_score_top3": best_nb_top3,
        "best_nb_correct_score_top5": best_nb_top5,
        "best_nb_gd_3_plus_calibration": best_nb_gd,
        "best_nb_log_loss_vs_baseline": {
            "log_loss_delta": float(baseline["log_loss"]) - float(best_nb_log_loss["log_loss"]),
            "brier_delta": float(baseline["brier_score"]) - float(best_nb_log_loss["brier_score"]),
            "top3_delta": float(best_nb_log_loss["correct_score_top3_accuracy"])
            - float(baseline["correct_score_top3_accuracy"]),
            "top5_delta": float(best_nb_log_loss["correct_score_top5_accuracy"])
            - float(baseline["correct_score_top5_accuracy"]),
            "gd_error_delta": float(baseline["gd_3_plus_calibration_error"])
            - float(best_nb_log_loss["gd_3_plus_calibration_error"]),
            "total_goals_4_plus_error_delta": float(baseline["total_goals_4_plus_calibration_error"])
            - float(best_nb_log_loss["total_goals_4_plus_calibration_error"]),
            "mad_drift": float(best_nb_log_loss["score_matrix_mad_drift"]),
        },
    }


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_split: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_split.setdefault(str(row["split"]), []).append(row)
    split_summaries = {
        split: summarize_split(split_rows_) for split, split_rows_ in by_split.items()
    }
    pooled = split_summaries["all_pooled"]
    high = split_summaries.get("high_mismatch_abs_elo_diff_300_plus")
    modern = split_summaries.get("world_cup_modern_1990_plus")
    recent = split_summaries.get("world_cup_recent_2000_plus")
    return {
        "split_summaries": split_summaries,
        "best_nb_log_loss_by_split": {
            split: summary["best_nb_log_loss"]["variant"]
            for split, summary in split_summaries.items()
        },
        "recommendation": {
            "nb_improves_pooled_log_loss": float(
                pooled["best_nb_log_loss_vs_baseline"]["log_loss_delta"]
            )
            > 0.0,
            "nb_improves_pooled_top3": float(
                pooled["best_nb_log_loss_vs_baseline"]["top3_delta"]
            )
            > 0.0,
            "nb_improves_high_mismatch_log_loss": (
                high is not None
                and float(high["best_nb_log_loss_vs_baseline"]["log_loss_delta"]) > 0.0
            ),
            "nb_useful_modern_world_cup": (
                modern is not None
                and float(modern["best_nb_log_loss_vs_baseline"]["log_loss_delta"]) > 0.0
            ),
            "nb_useful_recent_world_cup": (
                recent is not None
                and float(recent["best_nb_log_loss_vs_baseline"]["log_loss_delta"]) > 0.0
            ),
            "continue_nb_research": True,
            "keep_bivariate_poisson_baseline": True,
            "production_default_unchanged": True,
        },
    }


def build_negative_binomial_feasibility_benchmark(
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
        "benchmark": "negative_binomial_feasibility_benchmark",
        "dataset": {
            "label": "FIFA World Cup + UEFA Euro neutral matches",
            "universe": "FIFA + historical national teams",
            **source_summary,
        },
        "model_context": {
            "baseline": "final_worldcup_model_v1_candidate",
            "baseline_score_distribution": "bivariate_poisson",
            "dixon_coles_rho": RHO,
            "bivariate_poisson_gamma": GAMMA,
            "formal_model_formulas_unchanged": True,
            "production_default_unchanged": True,
            "research_benchmark_layer_only": True,
        },
        "search_space": {
            "negative_binomial_size_r": list(SIZE_VALUES),
            "draw_factor": list(DRAW_FACTORS),
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
        "# Negative Binomial Feasibility Benchmark",
        "",
        "Research-only benchmark. Formal Predictor formulas and production defaults remain unchanged.",
        "",
        "## Split Summary",
        "",
        "| Split | Matches | Baseline LogLoss | Best NB LogLoss | Best NB | LogLoss Delta | Top-3 Delta | GD Error Delta | TG>=4 Error Delta | MAD Drift |",
        "| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for split, split_summary in summary["split_summaries"].items():
        baseline = split_summary["baseline"]
        best = split_summary["best_nb_log_loss"]
        delta = split_summary["best_nb_log_loss_vs_baseline"]
        lines.append(
            f"| {split} | {baseline['matches']} | {baseline['log_loss']:.6f} | "
            f"{best['log_loss']:.6f} | {best['variant']} | "
            f"{delta['log_loss_delta']:.6f} | {delta['top3_delta']:.6f} | "
            f"{delta['gd_error_delta']:.6f} | {delta['total_goals_4_plus_error_delta']:.6f} | "
            f"{delta['mad_drift']:.6f} |"
        )
    rec = summary["recommendation"]
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"- NB improves pooled LogLoss: `{rec['nb_improves_pooled_log_loss']}`",
            f"- NB improves high-mismatch LogLoss: `{rec['nb_improves_high_mismatch_log_loss']}`",
            f"- Continue NB research: `{rec['continue_nb_research']}`",
            f"- Keep Bivariate Poisson baseline: `{rec['keep_bivariate_poisson_baseline']}`",
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
    parser = argparse.ArgumentParser(description="Run Negative Binomial feasibility benchmark.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/negative_binomial_feasibility_benchmark.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/negative_binomial_feasibility_benchmark.json"),
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("results/negative_binomial_feasibility_benchmark.md"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = build_negative_binomial_feasibility_benchmark(args.input, args.team_universe)
    write_outputs(rows, payload, args.output_csv, args.output_json, args.output_md)
    rec = payload["summary"]["recommendation"]
    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    print(f"output_md: {args.output_md}")
    print(f"nb_improves_pooled_log_loss: {rec['nb_improves_pooled_log_loss']}")
    print(f"nb_improves_high_mismatch_log_loss: {rec['nb_improves_high_mismatch_log_loss']}")
    print(f"keep_bivariate_poisson_baseline: {rec['keep_bivariate_poisson_baseline']}")


if __name__ == "__main__":
    main()
