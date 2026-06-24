from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model.metrics import accuracy, brier_score, multiclass_log_loss
from src.model.poisson import GAMMA, poisson_pmf, score_matrix
from src.tuning.domination_layer_extended_benchmark import (
    blowout_probability,
    predicted_goal_difference,
    top_scorelines,
)
from src.tuning.evaluation import actual_label
from src.tuning.score_tail_calibration_report import (
    RHO,
    scoreline_key,
    total_goals_probability,
    worldcup_xg,
)
from src.tuning.worldcup_xg_parameter_search import load_target_rows

MAX_GOALS_VALUES = (5, 6, 7, 8, 10)
GD_BUCKETS = ("GD=0", "GD=1", "GD=2", "GD>=3")
FAVORITE_BUCKETS = (
    "favorite_win_by_1",
    "favorite_win_by_2",
    "favorite_win_by_3_plus",
)


def raw_grid_mass(
    home_rate: float,
    away_rate: float,
    max_goals: int,
    gamma: float = GAMMA,
    rho: float = RHO,
) -> float:
    """Diagnostic unnormalized finite-grid mass using the current bivariate/DC shape."""
    shared = max(0.0, min(gamma, home_rate - 0.01, away_rate - 0.01))
    home_independent = home_rate - shared
    away_independent = away_rate - shared

    home_pmfs = [poisson_pmf(k, home_independent) for k in range(max_goals + 1)]
    away_pmfs = [poisson_pmf(k, away_independent) for k in range(max_goals + 1)]
    shared_pmfs = [poisson_pmf(k, shared) for k in range(max_goals + 1)]

    total = 0.0
    for home_goals in range(max_goals + 1):
        for away_goals in range(max_goals + 1):
            probability = 0.0
            for common in range(min(home_goals, away_goals) + 1):
                probability += (
                    home_pmfs[home_goals - common]
                    * away_pmfs[away_goals - common]
                    * shared_pmfs[common]
                )

            if home_goals == 0 and away_goals == 0:
                probability *= 1.0 - rho * home_rate * away_rate
            elif home_goals == 1 and away_goals == 1:
                probability *= 1.0 - rho
            elif home_goals == 1 and away_goals == 0:
                probability *= 1.0 + rho * away_rate
            elif home_goals == 0 and away_goals == 1:
                probability *= 1.0 + rho * home_rate

            total += max(0.0, probability)
    return total


def missing_tail_mass(home_rate: float, away_rate: float, max_goals: int) -> float:
    return max(0.0, 1.0 - raw_grid_mass(home_rate, away_rate, max_goals))


def scoreline_in_top_n(
    matrix: list[dict[str, float | int]],
    actual_home: int,
    actual_away: int,
    count: int,
) -> bool:
    return any(
        home == actual_home and away == actual_away
        for home, away, _ in top_scorelines(matrix, count)
    )


def analyze_row(row: dict[str, Any]) -> dict[str, Any]:
    home_elo = float(row["home_pre_match_elo"])
    away_elo = float(row["away_pre_match_elo"])
    home_xg, away_xg = worldcup_xg(home_elo, away_elo)
    home_score = int(row["home_score"])
    away_score = int(row["away_score"])
    return {
        "row": row,
        "home_xg": home_xg,
        "away_xg": away_xg,
        "home_score": home_score,
        "away_score": away_score,
        "actual_label": actual_label(home_score, away_score),
        "actual_abs_gd": abs(home_score - away_score),
        "actual_total_goals": home_score + away_score,
        "home_is_favorite": home_elo >= away_elo,
        "elo_diff": home_elo - away_elo,
    }


def evaluate_max_goals(rows: list[dict[str, Any]], max_goals: int) -> dict[str, Any]:
    start = time.perf_counter()
    labels: list[str] = []
    probabilities: list[dict[str, float]] = []
    top1_hits = 0
    top3_hits = 0
    top5_hits = 0
    gd_3_plus_probs: list[float] = []
    total_4_plus_probs: list[float] = []
    missing_masses: list[float] = []

    for row in rows:
        matrix = score_matrix(
            row["home_xg"],
            row["away_xg"],
            max_goals=max_goals,
            gamma=GAMMA,
            rho=RHO,
        )
        labels.append(row["actual_label"])
        from src.model.poisson import outcome_probabilities

        probabilities.append(outcome_probabilities(matrix))
        if scoreline_in_top_n(matrix, row["home_score"], row["away_score"], 1):
            top1_hits += 1
        if scoreline_in_top_n(matrix, row["home_score"], row["away_score"], 3):
            top3_hits += 1
        if scoreline_in_top_n(matrix, row["home_score"], row["away_score"], 5):
            top5_hits += 1
        gd_3_plus_probs.append(blowout_probability(matrix))
        total_4_plus_probs.append(total_goals_probability(matrix, 4))
        missing_masses.append(missing_tail_mass(row["home_xg"], row["away_xg"], max_goals))

    elapsed = time.perf_counter() - start
    match_count = len(rows)
    return {
        "max_goals": max_goals,
        "matches": match_count,
        "log_loss": multiclass_log_loss(labels, probabilities),
        "brier_score": brier_score(labels, probabilities),
        "accuracy": accuracy(labels, probabilities),
        "correct_score_top1_accuracy": top1_hits / match_count,
        "correct_score_top3_accuracy": top3_hits / match_count,
        "correct_score_top5_accuracy": top5_hits / match_count,
        "predicted_gd_3_plus_probability": statistics.mean(gd_3_plus_probs),
        "predicted_total_goals_4_plus_probability": statistics.mean(total_4_plus_probs),
        "average_missing_tail_mass": statistics.mean(missing_masses),
        "max_missing_tail_mass": max(missing_masses),
        "runtime_seconds": elapsed,
        "runtime_ms_per_match": elapsed * 1000.0 / match_count,
    }


def score_grid_truncation_analysis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    match_count = len(rows)
    by_either_team = {}
    for threshold in (6, 7, 8):
        matches = [
            row
            for row in rows
            if max(int(row["home_score"]), int(row["away_score"])) >= threshold
        ]
        by_either_team[f"{threshold}_plus_goals_by_either_team"] = {
            "matches": len(matches),
            "rate": len(matches) / match_count,
        }

    exact_score_outside_max_5 = [
        row
        for row in rows
        if int(row["home_score"]) > 5 or int(row["away_score"]) > 5
    ]
    return {
        **by_either_team,
        "exact_score_outside_current_max_goals_5": {
            "matches": len(exact_score_outside_max_5),
            "rate": len(exact_score_outside_max_5) / match_count,
            "examples": [
                {
                    "date": row["row"]["date"],
                    "match": f"{row['row']['home_team']} vs {row['row']['away_team']}",
                    "score": scoreline_key(row["home_score"], row["away_score"]),
                    "tournament": row["row"]["tournament"],
                }
                for row in exact_score_outside_max_5[:20]
            ],
        },
        "impact_note": (
            "MAX_GOALS=5 makes exact-score hits impossible for any match where either team scores 6+."
        ),
    }


def poisson_shape_analysis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    target_scorelines = (
        (2, 2),
        (3, 1),
        (1, 3),
        (2, 1),
        (1, 2),
        (4, 0),
        (0, 4),
        (5, 0),
        (0, 5),
        (4, 1),
        (1, 4),
    )
    actual_counter = Counter(scoreline_key(row["home_score"], row["away_score"]) for row in rows)
    predicted_totals = Counter()
    for row in rows:
        matrix = score_matrix(row["home_xg"], row["away_xg"], max_goals=5, gamma=GAMMA, rho=RHO)
        for home, away in target_scorelines:
            key = scoreline_key(home, away)
            for cell in matrix:
                if int(cell["home"]) == home and int(cell["away"]) == away:
                    predicted_totals[key] += float(cell["probability"])
                    break

    match_count = len(rows)
    rows_out = [
        {
            "scoreline": scoreline_key(home, away),
            "actual_frequency": actual_counter[scoreline_key(home, away)] / match_count,
            "predicted_probability": predicted_totals[scoreline_key(home, away)] / match_count,
            "actual_minus_predicted": (actual_counter[scoreline_key(home, away)] / match_count)
            - (predicted_totals[scoreline_key(home, away)] / match_count),
        }
        for home, away in target_scorelines
    ]
    concentrated_keys = {"2-2", "3-1", "1-3", "2-1", "1-2"}
    tail_keys = {"4-0", "0-4", "5-0", "0-5", "4-1", "1-4"}
    return {
        "scoreline_comparison": rows_out,
        "concentrated_scoreline_predicted_probability": sum(
            row["predicted_probability"] for row in rows_out if row["scoreline"] in concentrated_keys
        ),
        "concentrated_scoreline_actual_frequency": sum(
            row["actual_frequency"] for row in rows_out if row["scoreline"] in concentrated_keys
        ),
        "tail_scoreline_predicted_probability": sum(
            row["predicted_probability"] for row in rows_out if row["scoreline"] in tail_keys
        ),
        "tail_scoreline_actual_frequency": sum(
            row["actual_frequency"] for row in rows_out if row["scoreline"] in tail_keys
        ),
    }


def gd_bucket(abs_gd: int) -> str:
    if abs_gd == 0:
        return "GD=0"
    if abs_gd == 1:
        return "GD=1"
    if abs_gd == 2:
        return "GD=2"
    return "GD>=3"


def goal_difference_tail_analysis(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actual_counts = Counter(gd_bucket(row["actual_abs_gd"]) for row in rows)
    predicted_totals = Counter()
    for row in rows:
        matrix = score_matrix(row["home_xg"], row["away_xg"], max_goals=5, gamma=GAMMA, rho=RHO)
        for cell in matrix:
            predicted_totals[gd_bucket(abs(int(cell["home"]) - int(cell["away"])))] += float(
                cell["probability"]
            )

    match_count = len(rows)
    return [
        {
            "bucket": bucket,
            "actual_rate": actual_counts[bucket] / match_count,
            "predicted_probability": predicted_totals[bucket] / match_count,
            "actual_minus_predicted": (actual_counts[bucket] / match_count)
            - (predicted_totals[bucket] / match_count),
        }
        for bucket in GD_BUCKETS
    ]


def favorite_margin_bucket(row: dict[str, Any]) -> str | None:
    favorite_goals = row["home_score"] if row["home_is_favorite"] else row["away_score"]
    underdog_goals = row["away_score"] if row["home_is_favorite"] else row["home_score"]
    margin = favorite_goals - underdog_goals
    if margin == 1:
        return "favorite_win_by_1"
    if margin == 2:
        return "favorite_win_by_2"
    if margin >= 3:
        return "favorite_win_by_3_plus"
    return None


def predicted_favorite_margin_bucket(home: int, away: int, home_is_favorite: bool) -> str | None:
    favorite_goals = home if home_is_favorite else away
    underdog_goals = away if home_is_favorite else home
    margin = favorite_goals - underdog_goals
    if margin == 1:
        return "favorite_win_by_1"
    if margin == 2:
        return "favorite_win_by_2"
    if margin >= 3:
        return "favorite_win_by_3_plus"
    return None


def favorite_blowout_analysis(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actual_counts = Counter()
    predicted_totals = Counter()
    for row in rows:
        bucket = favorite_margin_bucket(row)
        if bucket:
            actual_counts[bucket] += 1
        matrix = score_matrix(row["home_xg"], row["away_xg"], max_goals=5, gamma=GAMMA, rho=RHO)
        for cell in matrix:
            predicted_bucket = predicted_favorite_margin_bucket(
                int(cell["home"]),
                int(cell["away"]),
                bool(row["home_is_favorite"]),
            )
            if predicted_bucket:
                predicted_totals[predicted_bucket] += float(cell["probability"])

    match_count = len(rows)
    return [
        {
            "bucket": bucket,
            "actual_rate": actual_counts[bucket] / match_count,
            "predicted_probability": predicted_totals[bucket] / match_count,
            "actual_minus_predicted": (actual_counts[bucket] / match_count)
            - (predicted_totals[bucket] / match_count),
        }
        for bucket in FAVORITE_BUCKETS
    ]


def build_conclusions(report: dict[str, Any]) -> dict[str, Any]:
    max5 = next(row for row in report["max_goals_sensitivity"] if row["max_goals"] == 5)
    max_reference = max(
        report["max_goals_sensitivity"],
        key=lambda row: int(row["max_goals"]),
    )
    gd_tail = next(row for row in report["goal_difference_tail_analysis"] if row["bucket"] == "GD>=3")
    high_total_delta = (
        max_reference["predicted_total_goals_4_plus_probability"]
        - max5["predicted_total_goals_4_plus_probability"]
    )
    gd_delta = (
        max_reference["predicted_gd_3_plus_probability"]
        - max5["predicted_gd_3_plus_probability"]
    )
    truncation_rate = report["score_grid_truncation_analysis"][
        "exact_score_outside_current_max_goals_5"
    ]["rate"]
    shape = report["poisson_shape_analysis"]
    return {
        "max_goals_should_be_raised_for_wdl_metrics": (
            float(max_reference["log_loss"]) < float(max5["log_loss"]) - 0.001
            or float(max_reference["brier_score"]) < float(max5["brier_score"]) - 0.001
        ),
        "max_goals_should_be_raised_for_exact_score_diagnostics": truncation_rate > 0.0,
        "max_goals_5_to_reference": {
            "reference_max_goals": max_reference["max_goals"],
            "gd_3_plus_probability_delta": gd_delta,
            "total_goals_4_plus_probability_delta": high_total_delta,
        },
        "primary_gd_3_plus_underestimation_cause": (
            "xG difference / score-distribution shape, not grid truncation"
            if gd_delta < 0.01 and float(gd_tail["actual_minus_predicted"]) > 0.02
            else "grid truncation may materially contribute"
        ),
        "poisson_shape_note": (
            "The model assigns more probability to concentrated 2-1/1-2/2-2/3-1/1-3 scorelines "
            "than to 4-0/5-0/4-1 style tail scorelines."
            if float(shape["concentrated_scoreline_predicted_probability"])
            > float(shape["tail_scoreline_predicted_probability"])
            else "Tail scorelines are not lower than the selected concentrated scoreline set."
        ),
        "fat_tail_distribution_research_recommended": float(gd_tail["actual_minus_predicted"]) > 0.02,
        "do_not_change_formal_model_yet": True,
    }


def build_score_distribution_diagnostics(
    input_path: Path,
    team_universe_path: Path,
    max_goals_values: tuple[int, ...] = MAX_GOALS_VALUES,
) -> dict[str, Any]:
    target_rows, source_summary = load_target_rows(input_path, team_universe_path)
    rows = [analyze_row(row) for row in target_rows]
    report: dict[str, Any] = {
        "report": "score_distribution_diagnostics",
        "dataset": {
            "label": "FIFA World Cup + UEFA Euro neutral matches",
            "universe": "FIFA + historical national teams",
            **source_summary,
        },
        "model_context": {
            "candidate": "final_worldcup_model_v1_candidate",
            "domination": "disabled / 100% normal",
            "dixon_coles_rho": RHO,
            "bivariate_poisson_gamma": GAMMA,
            "formal_model_formulas_unchanged": True,
            "diagnostic_only": True,
        },
        "max_goals_sensitivity": [
            evaluate_max_goals(rows, max_goals) for max_goals in max_goals_values
        ],
        "score_grid_truncation_analysis": score_grid_truncation_analysis(rows),
        "poisson_shape_analysis": poisson_shape_analysis(rows),
        "goal_difference_tail_analysis": goal_difference_tail_analysis(rows),
        "favorite_blowout_analysis": favorite_blowout_analysis(rows),
    }
    report["diagnostic_conclusions"] = build_conclusions(report)
    return report


def write_markdown_report(report: dict[str, Any], path: Path) -> None:
    conclusions = report["diagnostic_conclusions"]
    lines = [
        "# Score Distribution Diagnostics Report",
        "",
        "Dataset: FIFA World Cup + UEFA Euro neutral matches, FIFA + historical national team universe.",
        "",
        "Model: `final_worldcup_model_v1_candidate`, domination disabled / 100% normal xG.",
        "",
        "## MAX_GOALS Sensitivity",
        "",
        "| MAX_GOALS | LogLoss | Brier | Top-1 | Top-3 | Top-5 | GD>=3 Prob | TG>=4 Prob | Missing Tail Mass | Runtime ms/match |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report["max_goals_sensitivity"]:
        lines.append(
            f"| {row['max_goals']} | {row['log_loss']:.6f} | {row['brier_score']:.6f} | "
            f"{row['correct_score_top1_accuracy']:.6f} | {row['correct_score_top3_accuracy']:.6f} | "
            f"{row['correct_score_top5_accuracy']:.6f} | {row['predicted_gd_3_plus_probability']:.6f} | "
            f"{row['predicted_total_goals_4_plus_probability']:.6f} | "
            f"{row['average_missing_tail_mass']:.6f} | {row['runtime_ms_per_match']:.4f} |"
        )

    lines.extend(
        [
            "",
            "## Goal-Difference Tail",
            "",
            "| Bucket | Actual Rate | Predicted Probability | Actual - Predicted |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for row in report["goal_difference_tail_analysis"]:
        lines.append(
            f"| {row['bucket']} | {row['actual_rate']:.6f} | "
            f"{row['predicted_probability']:.6f} | {row['actual_minus_predicted']:.6f} |"
        )

    lines.extend(
        [
            "",
            "## Favorite Margin",
            "",
            "| Bucket | Actual Rate | Predicted Probability | Actual - Predicted |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for row in report["favorite_blowout_analysis"]:
        lines.append(
            f"| {row['bucket']} | {row['actual_rate']:.6f} | "
            f"{row['predicted_probability']:.6f} | {row['actual_minus_predicted']:.6f} |"
        )

    truncation = report["score_grid_truncation_analysis"]
    lines.extend(
        [
            "",
            "## Truncation",
            "",
            f"- 6+ goals by either team: `{truncation['6_plus_goals_by_either_team']['rate']:.6f}`",
            f"- 7+ goals by either team: `{truncation['7_plus_goals_by_either_team']['rate']:.6f}`",
            f"- 8+ goals by either team: `{truncation['8_plus_goals_by_either_team']['rate']:.6f}`",
            f"- Exact scores outside MAX_GOALS=5: `{truncation['exact_score_outside_current_max_goals_5']['rate']:.6f}`",
            "",
            "## Conclusions",
            "",
            f"- Raise MAX_GOALS for W/D/L metrics: `{conclusions['max_goals_should_be_raised_for_wdl_metrics']}`",
            f"- Raise MAX_GOALS for exact-score diagnostics: `{conclusions['max_goals_should_be_raised_for_exact_score_diagnostics']}`",
            f"- Primary GD>=3 underestimation cause: {conclusions['primary_gd_3_plus_underestimation_cause']}",
            f"- Fat-tail score distribution research recommended: `{conclusions['fat_tail_distribution_research_recommended']}`",
            f"- Formal model formulas unchanged: `{report['model_context']['formal_model_formulas_unchanged']}`",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(report: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown_report(report, markdown_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build score distribution diagnostics.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/score_distribution_diagnostics.json"),
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("results/score_distribution_diagnostics.md"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_score_distribution_diagnostics(args.input, args.team_universe)
    write_outputs(report, args.output_json, args.output_md)
    conclusions = report["diagnostic_conclusions"]
    max5 = next(row for row in report["max_goals_sensitivity"] if row["max_goals"] == 5)
    max10 = next(row for row in report["max_goals_sensitivity"] if row["max_goals"] == 10)

    print(f"output_json: {args.output_json}")
    print(f"output_md: {args.output_md}")
    print(f"matches: {report['dataset']['target_matches']}")
    print(
        "max_goals_5_to_10: "
        f"log_loss={float(max5['log_loss']):.6f}->{float(max10['log_loss']):.6f} "
        f"gd3p={float(max5['predicted_gd_3_plus_probability']):.6f}->{float(max10['predicted_gd_3_plus_probability']):.6f}"
    )
    print(f"primary_cause: {conclusions['primary_gd_3_plus_underestimation_cause']}")
    print(
        "fat_tail_score_distribution_research_recommended: "
        f"{conclusions['fat_tail_distribution_research_recommended']}"
    )


if __name__ == "__main__":
    main()
