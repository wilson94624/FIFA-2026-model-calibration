from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model.poisson import GAMMA, score_matrix
from src.tuning.domination_layer_extended_benchmark import (
    blowout_probability,
    top_scorelines,
)
from src.tuning.final_worldcup_model_benchmark import matrix_expected_total_goals
from src.tuning.tune_dixon_coles_rho import CALIBRATED_XG_WORLDCUP_V1, score_probability
from src.tuning.worldcup_xg_parameter_search import load_target_rows, neutral_symmetric_xg

RHO = 0.05
TAIL_SCORELINES = (
    (4, 0),
    (5, 0),
    (6, 0),
    (4, 1),
    (5, 1),
    (0, 4),
    (0, 5),
    (0, 6),
    (1, 4),
    (1, 5),
)
GD_BUCKETS = (
    ("0-5%", 0.00, 0.05),
    ("5-10%", 0.05, 0.10),
    ("10-20%", 0.10, 0.20),
    ("20-30%", 0.20, 0.30),
    ("30%+", 0.30, float("inf")),
)


def worldcup_xg(team_a_elo: float, team_b_elo: float) -> tuple[float, float]:
    return neutral_symmetric_xg(
        team_a_elo,
        team_b_elo,
        base=float(CALIBRATED_XG_WORLDCUP_V1["base"]),
        c1=float(CALIBRATED_XG_WORLDCUP_V1["c1"]),
        scale=float(CALIBRATED_XG_WORLDCUP_V1["scale"]),
    )


def scoreline_key(home_goals: int, away_goals: int) -> str:
    return f"{home_goals}-{away_goals}"


def scoreline_probability_map(matrix: list[dict[str, float | int]]) -> dict[str, float]:
    return {
        scoreline_key(int(cell["home"]), int(cell["away"])): float(cell["probability"])
        for cell in matrix
    }


def total_goals_probability(matrix: list[dict[str, float | int]], threshold: int) -> float:
    return sum(
        float(cell["probability"])
        for cell in matrix
        if int(cell["home"]) + int(cell["away"]) >= threshold
    )


def favorite_win_by_three_probability(
    matrix: list[dict[str, float | int]],
    team_a_is_favorite: bool,
) -> float:
    total = 0.0
    for cell in matrix:
        home_goals = int(cell["home"])
        away_goals = int(cell["away"])
        probability = float(cell["probability"])
        if team_a_is_favorite and home_goals - away_goals >= 3:
            total += probability
        elif not team_a_is_favorite and away_goals - home_goals >= 3:
            total += probability
    return total


def bucket_for_probability(probability: float) -> str:
    for label, lower, upper in GD_BUCKETS:
        if lower <= probability < upper:
            return label
    return GD_BUCKETS[-1][0]


def format_top_scorelines(scorelines: list[tuple[int, int, float]]) -> list[dict[str, Any]]:
    return [
        {"scoreline": scoreline_key(home, away), "probability": probability}
        for home, away, probability in scorelines
    ]


def analyze_match(row: dict[str, Any]) -> dict[str, Any]:
    team_a_elo = float(row["home_pre_match_elo"])
    team_b_elo = float(row["away_pre_match_elo"])
    team_a_xg, team_b_xg = worldcup_xg(team_a_elo, team_b_elo)
    matrix = score_matrix(team_a_xg, team_b_xg, gamma=GAMMA, rho=RHO)
    team_a_score = int(row["home_score"])
    team_b_score = int(row["away_score"])
    actual_goal_difference = team_a_score - team_b_score
    team_a_is_favorite = team_a_elo >= team_b_elo
    favorite_score = team_a_score if team_a_is_favorite else team_b_score
    underdog_score = team_b_score if team_a_is_favorite else team_a_score

    return {
        "row": row,
        "team_a_xg": team_a_xg,
        "team_b_xg": team_b_xg,
        "matrix": matrix,
        "actual_scoreline": scoreline_key(team_a_score, team_b_score),
        "actual_goal_difference": actual_goal_difference,
        "actual_abs_goal_difference": abs(actual_goal_difference),
        "actual_total_goals": team_a_score + team_b_score,
        "team_a_is_favorite": team_a_is_favorite,
        "actual_favorite_wins_by_3_plus": favorite_score - underdog_score >= 3,
        "predicted_gd_3_plus_probability": blowout_probability(matrix),
        "predicted_total_goals_4_plus_probability": total_goals_probability(matrix, 4),
        "predicted_favorite_wins_by_3_plus_probability": favorite_win_by_three_probability(
            matrix,
            team_a_is_favorite,
        ),
        "predicted_total_goals": matrix_expected_total_goals(matrix),
        "probability_map": scoreline_probability_map(matrix),
        "top3": top_scorelines(matrix, 3),
        "top5": top_scorelines(matrix, 5),
    }


def actual_scoreline_distribution(matches: list[dict[str, Any]]) -> dict[str, Any]:
    counter = Counter(match["actual_scoreline"] for match in matches)
    match_count = len(matches)
    return {
        "top_20": [
            {
                "scoreline": scoreline,
                "matches": count,
                "actual_frequency": count / match_count,
            }
            for scoreline, count in counter.most_common(20)
        ],
        "gd_3_plus": {
            "matches": sum(1 for match in matches if match["actual_abs_goal_difference"] >= 3),
            "rate": sum(1 for match in matches if match["actual_abs_goal_difference"] >= 3) / match_count,
        },
        "total_goals_4_plus": {
            "matches": sum(1 for match in matches if match["actual_total_goals"] >= 4),
            "rate": sum(1 for match in matches if match["actual_total_goals"] >= 4) / match_count,
        },
        "tail_scorelines": [
            {
                "scoreline": scoreline_key(home, away),
                "matches": counter[scoreline_key(home, away)],
                "actual_frequency": counter[scoreline_key(home, away)] / match_count,
            }
            for home, away in TAIL_SCORELINES
        ],
    }


def predicted_scoreline_distribution(matches: list[dict[str, Any]]) -> dict[str, Any]:
    probability_totals: defaultdict[str, float] = defaultdict(float)
    actual_counter = Counter(match["actual_scoreline"] for match in matches)
    match_count = len(matches)
    for match in matches:
        for scoreline, probability in match["probability_map"].items():
            probability_totals[scoreline] += probability

    predicted_rows = [
        {
            "scoreline": scoreline,
            "predicted_probability": probability / match_count,
            "actual_frequency": actual_counter[scoreline] / match_count,
            "actual_matches": actual_counter[scoreline],
            "actual_minus_predicted": (actual_counter[scoreline] / match_count)
            - (probability / match_count),
        }
        for scoreline, probability in probability_totals.items()
    ]
    predicted_rows.sort(key=lambda row: float(row["predicted_probability"]), reverse=True)

    comparison_scorelines = {
        row["scoreline"] for row in predicted_rows[:20]
    } | {row["scoreline"] for row in actual_scoreline_distribution(matches)["top_20"]}
    comparison_scorelines |= {scoreline_key(home, away) for home, away in TAIL_SCORELINES}
    comparison_rows = [
        row for row in predicted_rows if row["scoreline"] in comparison_scorelines
    ]
    comparison_rows.sort(key=lambda row: abs(float(row["actual_minus_predicted"])), reverse=True)
    return {
        "top_20_predicted_scorelines": predicted_rows[:20],
        "actual_vs_predicted_comparison": comparison_rows,
    }


def tail_calibration(matches: list[dict[str, Any]]) -> dict[str, Any]:
    match_count = len(matches)
    actual_gd_3_plus = [match["actual_abs_goal_difference"] >= 3 for match in matches]
    actual_total_4_plus = [match["actual_total_goals"] >= 4 for match in matches]
    actual_favorite_3_plus = [match["actual_favorite_wins_by_3_plus"] for match in matches]
    return {
        "actual_gd_3_plus_rate": sum(actual_gd_3_plus) / match_count,
        "predicted_gd_3_plus_probability": statistics.mean(
            match["predicted_gd_3_plus_probability"] for match in matches
        ),
        "gd_3_plus_actual_minus_predicted": (sum(actual_gd_3_plus) / match_count)
        - statistics.mean(match["predicted_gd_3_plus_probability"] for match in matches),
        "actual_total_goals_4_plus_rate": sum(actual_total_4_plus) / match_count,
        "predicted_total_goals_4_plus_probability": statistics.mean(
            match["predicted_total_goals_4_plus_probability"] for match in matches
        ),
        "total_goals_4_plus_actual_minus_predicted": (sum(actual_total_4_plus) / match_count)
        - statistics.mean(match["predicted_total_goals_4_plus_probability"] for match in matches),
        "actual_favorite_wins_by_3_plus_rate": sum(actual_favorite_3_plus) / match_count,
        "predicted_favorite_wins_by_3_plus_probability": statistics.mean(
            match["predicted_favorite_wins_by_3_plus_probability"] for match in matches
        ),
        "favorite_wins_by_3_plus_actual_minus_predicted": (sum(actual_favorite_3_plus) / match_count)
        - statistics.mean(match["predicted_favorite_wins_by_3_plus_probability"] for match in matches),
        "actual_avg_total_goals": statistics.mean(match["actual_total_goals"] for match in matches),
        "predicted_avg_total_goals": statistics.mean(match["predicted_total_goals"] for match in matches),
    }


def missed_blowout_analysis(matches: list[dict[str, Any]]) -> dict[str, Any]:
    missed_top3: list[dict[str, Any]] = []
    missed_top5: list[dict[str, Any]] = []
    actual_blowouts = [match for match in matches if match["actual_abs_goal_difference"] >= 3]
    for match in actual_blowouts:
        row = match["row"]
        actual_pair = tuple(int(value) for value in match["actual_scoreline"].split("-"))
        in_top3 = any((home, away) == actual_pair for home, away, _ in match["top3"])
        in_top5 = any((home, away) == actual_pair for home, away, _ in match["top5"])
        output = {
            "match": f"{row['home_team']} vs {row['away_team']}",
            "date": row["date"],
            "tournament": row["tournament"],
            "actual_score": match["actual_scoreline"],
            "actual_goal_difference": match["actual_goal_difference"],
            "model_top_5_scorelines": format_top_scorelines(match["top5"]),
            "probability_assigned_to_actual_scoreline": score_probability(
                match["matrix"],
                actual_pair[0],
                actual_pair[1],
            ),
            "predicted_gd_3_plus_probability": match["predicted_gd_3_plus_probability"],
            "predicted_total_goals_4_plus_probability": match["predicted_total_goals_4_plus_probability"],
            "elo_diff": float(row["home_pre_match_elo"]) - float(row["away_pre_match_elo"]),
            "team_a_xg": match["team_a_xg"],
            "team_b_xg": match["team_b_xg"],
        }
        if not in_top3:
            missed_top3.append(output)
        if not in_top5:
            missed_top5.append(output)

    missed_top3.sort(
        key=lambda row: (
            abs(float(row["actual_goal_difference"])),
            float(row["predicted_gd_3_plus_probability"]),
        ),
        reverse=True,
    )
    missed_top5.sort(
        key=lambda row: (
            abs(float(row["actual_goal_difference"])),
            float(row["predicted_gd_3_plus_probability"]),
        ),
        reverse=True,
    )
    return {
        "actual_blowout_matches": len(actual_blowouts),
        "missed_top3_count": len(missed_top3),
        "missed_top5_count": len(missed_top5),
        "missed_top3_rate_among_blowouts": len(missed_top3) / len(actual_blowouts)
        if actual_blowouts
        else 0.0,
        "missed_top5_rate_among_blowouts": len(missed_top5) / len(actual_blowouts)
        if actual_blowouts
        else 0.0,
        "missed_top3_matches": missed_top3,
        "missed_top5_matches": missed_top5,
    }


def calibration_buckets(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bucketed: dict[str, list[dict[str, Any]]] = {label: [] for label, _, _ in GD_BUCKETS}
    for match in matches:
        bucketed[bucket_for_probability(match["predicted_gd_3_plus_probability"])].append(match)

    rows: list[dict[str, Any]] = []
    for label, _, _ in GD_BUCKETS:
        bucket_matches = bucketed[label]
        if bucket_matches:
            predicted_average = statistics.mean(
                match["predicted_gd_3_plus_probability"] for match in bucket_matches
            )
            actual_rate = sum(
                1 for match in bucket_matches if match["actual_abs_goal_difference"] >= 3
            ) / len(bucket_matches)
        else:
            predicted_average = 0.0
            actual_rate = 0.0
        rows.append(
            {
                "bucket": label,
                "match_count": len(bucket_matches),
                "predicted_average_probability": predicted_average,
                "actual_observed_rate": actual_rate,
                "actual_minus_predicted": actual_rate - predicted_average,
            }
        )
    return rows


def build_diagnostic_conclusions(report: dict[str, Any]) -> dict[str, Any]:
    tail = report["tail_calibration"]
    actual_gd = float(tail["actual_gd_3_plus_rate"])
    predicted_gd = float(tail["predicted_gd_3_plus_probability"])
    actual_total = float(tail["actual_total_goals_4_plus_rate"])
    predicted_total = float(tail["predicted_total_goals_4_plus_probability"])
    actual_avg_total = float(tail["actual_avg_total_goals"])
    predicted_avg_total = float(tail["predicted_avg_total_goals"])
    return {
        "systematically_underestimates_blowouts": actual_gd > predicted_gd + 0.02,
        "systematically_underestimates_high_total_goals": actual_total > predicted_total + 0.02,
        "xg_level_signal": {
            "actual_avg_total_goals": actual_avg_total,
            "predicted_avg_total_goals": predicted_avg_total,
            "predicted_minus_actual": predicted_avg_total - actual_avg_total,
            "interpretation": (
                "Predicted average total goals are below actual average total goals."
                if predicted_avg_total < actual_avg_total
                else "Predicted average total goals are not below actual average total goals."
            ),
        },
        "score_distribution_tail_signal": {
            "actual_gd_3_plus_rate": actual_gd,
            "predicted_gd_3_plus_probability": predicted_gd,
            "actual_total_goals_4_plus_rate": actual_total,
            "predicted_total_goals_4_plus_probability": predicted_total,
            "interpretation": (
                "Tail probabilities are below observed tail rates."
                if actual_gd > predicted_gd and actual_total > predicted_total
                else "Tail underprediction is not uniform across both GD and total-goals tails."
            ),
        },
        "correct_score_variance_note": (
            "Exact scorelines such as 4-0 and 5-0 are sparse and high variance. "
            "Missed individual scorelines should be interpreted through tail-rate calibration, "
            "not as standalone proof that a new amplifier is needed."
        ),
        "recommended_next_step": (
            "Research fat-tail score distribution diagnostics before changing formulas."
            if actual_gd > predicted_gd + 0.02 or actual_total > predicted_total + 0.02
            else "Do not change formulas yet; continue monitoring score-tail diagnostics."
        ),
    }


def build_score_tail_calibration_report(
    input_path: Path,
    team_universe_path: Path,
) -> dict[str, Any]:
    target_rows, source_summary = load_target_rows(input_path, team_universe_path)
    analyzed_matches = [analyze_match(row) for row in target_rows]
    report: dict[str, Any] = {
        "report": "score_tail_calibration_report",
        "dataset": {
            "label": "FIFA World Cup + UEFA Euro neutral matches",
            "universe": "FIFA + historical national teams",
            **source_summary,
        },
        "model_context": {
            "candidate": "final_worldcup_model_v1_candidate",
            "elo": "calibrated_elo_v3_candidate",
            "xg": {
                "name": "calibrated_xg_worldcup_v1_candidate",
                **CALIBRATED_XG_WORLDCUP_V1,
            },
            "dixon_coles_rho": RHO,
            "bivariate_poisson_gamma": GAMMA,
            "domination": "disabled / 100% normal",
            "formal_model_formulas_unchanged": True,
        },
        "actual_scoreline_distribution": actual_scoreline_distribution(analyzed_matches),
        "predicted_scoreline_probability_distribution": predicted_scoreline_distribution(
            analyzed_matches
        ),
        "tail_calibration": tail_calibration(analyzed_matches),
        "missed_blowout_analysis": missed_blowout_analysis(analyzed_matches),
        "calibration_buckets": calibration_buckets(analyzed_matches),
    }
    report["diagnostic_conclusions"] = build_diagnostic_conclusions(report)
    return report


def write_markdown_report(report: dict[str, Any], path: Path) -> None:
    tail = report["tail_calibration"]
    missed = report["missed_blowout_analysis"]
    conclusions = report["diagnostic_conclusions"]
    lines = [
        "# Score Tail Calibration Report",
        "",
        "Dataset: FIFA World Cup + UEFA Euro neutral matches, FIFA + historical national team universe.",
        "",
        "Model: `final_worldcup_model_v1_candidate`, domination disabled / 100% normal xG.",
        "",
        "## Tail Calibration",
        "",
        f"- Actual GD >= 3 rate: `{tail['actual_gd_3_plus_rate']:.6f}`",
        f"- Predicted GD >= 3 probability: `{tail['predicted_gd_3_plus_probability']:.6f}`",
        f"- Actual total goals >= 4 rate: `{tail['actual_total_goals_4_plus_rate']:.6f}`",
        f"- Predicted total goals >= 4 probability: `{tail['predicted_total_goals_4_plus_probability']:.6f}`",
        f"- Actual favorite wins by 3+ rate: `{tail['actual_favorite_wins_by_3_plus_rate']:.6f}`",
        f"- Predicted favorite wins by 3+ probability: `{tail['predicted_favorite_wins_by_3_plus_probability']:.6f}`",
        f"- Actual avg total goals: `{tail['actual_avg_total_goals']:.6f}`",
        f"- Predicted avg total goals: `{tail['predicted_avg_total_goals']:.6f}`",
        "",
        "## Missed Blowouts",
        "",
        f"- Actual blowout matches: `{missed['actual_blowout_matches']}`",
        f"- Missed Top-3 count: `{missed['missed_top3_count']}`",
        f"- Missed Top-5 count: `{missed['missed_top5_count']}`",
        "",
        "## Calibration Buckets",
        "",
        "| Predicted GD>=3 bucket | Matches | Predicted Avg | Actual Rate | Actual - Predicted |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for bucket in report["calibration_buckets"]:
        lines.append(
            f"| {bucket['bucket']} | {bucket['match_count']} | "
            f"{bucket['predicted_average_probability']:.6f} | "
            f"{bucket['actual_observed_rate']:.6f} | "
            f"{bucket['actual_minus_predicted']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Diagnostic Conclusions",
            "",
            f"- Systematically underestimates blowouts: `{conclusions['systematically_underestimates_blowouts']}`",
            f"- Systematically underestimates high-total-goals matches: `{conclusions['systematically_underestimates_high_total_goals']}`",
            f"- Recommended next step: {conclusions['recommended_next_step']}",
            "",
            "Exact 4-0 / 5-0 style scorelines are sparse and high variance, so individual missed scorelines should be interpreted through aggregate tail calibration rather than treated as standalone proof that a new amplifier is needed.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(report: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown_report(report, markdown_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build score-tail calibration diagnostics.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/score_tail_calibration_report.json"),
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("results/score_tail_calibration_report.md"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_score_tail_calibration_report(args.input, args.team_universe)
    write_outputs(report, args.output_json, args.output_md)

    tail = report["tail_calibration"]
    conclusions = report["diagnostic_conclusions"]
    print(f"output_json: {args.output_json}")
    print(f"output_md: {args.output_md}")
    print(f"matches: {report['dataset']['target_matches']}")
    print(
        "gd_3_plus: "
        f"actual={float(tail['actual_gd_3_plus_rate']):.6f} "
        f"predicted={float(tail['predicted_gd_3_plus_probability']):.6f}"
    )
    print(
        "total_goals_4_plus: "
        f"actual={float(tail['actual_total_goals_4_plus_rate']):.6f} "
        f"predicted={float(tail['predicted_total_goals_4_plus_probability']):.6f}"
    )
    print(
        "systematically_underestimates_blowouts: "
        f"{conclusions['systematically_underestimates_blowouts']}"
    )


if __name__ == "__main__":
    main()
