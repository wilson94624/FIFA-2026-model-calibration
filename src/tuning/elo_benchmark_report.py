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

from src.model.elo_rebuilder import parse_match_rows, rebuild_elo_history
from src.tuning.evaluation import evaluate_rebuilt_elo_rows
from src.tuning.tune_goal_diff_multiplier import goal_diff_multiplier
from src.tuning.tune_k_factor import read_match_rows

REPORT_COLUMNS = [
    "model",
    "accuracy",
    "log_loss",
    "brier_score",
    "accuracy_delta",
    "log_loss_delta",
    "brier_delta",
]

STANDARD_MODEL = {
    "name": "standard_elo_v1",
    "k_factor": 20.0,
    "goal_diff_variant": "none",
}

CALIBRATED_MODEL = {
    "name": "calibrated_elo_v2_candidate",
    "k_factor": 80.0,
    "goal_diff_variant": "log_margin",
}


def final_team_ratings(rows: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    teams: dict[str, dict[str, float | int]] = {}
    for row in rows:
        teams[str(row["home_team"])] = {
            "final_elo": float(row["home_post_match_elo"]),
            "matches": int(row["home_matches_after"]),
        }
        teams[str(row["away_team"])] = {
            "final_elo": float(row["away_post_match_elo"]),
            "matches": int(row["away_matches_after"]),
        }
    return teams


def ranking(teams: dict[str, dict[str, float | int]]) -> list[dict[str, float | int | str]]:
    return [
        {"rank": index, "team": team, "final_elo": values["final_elo"], "matches": values["matches"]}
        for index, (team, values) in enumerate(
            sorted(teams.items(), key=lambda item: float(item[1]["final_elo"]), reverse=True),
            start=1,
        )
    ]


def team_rating_deltas(
    standard: dict[str, dict[str, float | int]],
    calibrated: dict[str, dict[str, float | int]],
    limit: int = 20,
) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for team in sorted(set(standard) & set(calibrated)):
        standard_elo = float(standard[team]["final_elo"])
        calibrated_elo = float(calibrated[team]["final_elo"])
        rows.append(
            {
                "team": team,
                "standard_final_elo": standard_elo,
                "calibrated_final_elo": calibrated_elo,
                "elo_delta": calibrated_elo - standard_elo,
                "abs_elo_delta": abs(calibrated_elo - standard_elo),
                "matches": int(calibrated[team]["matches"]),
            }
        )
    return sorted(rows, key=lambda row: float(row["abs_elo_delta"]), reverse=True)[:limit]


def top20_ranking_comparison(
    standard_ranking: list[dict[str, float | int | str]],
    calibrated_ranking: list[dict[str, float | int | str]],
) -> list[dict[str, float | int | str | None]]:
    standard_by_team = {str(row["team"]): row for row in standard_ranking}
    calibrated_by_team = {str(row["team"]): row for row in calibrated_ranking}
    teams = {
        str(row["team"]) for row in standard_ranking[:20]
    } | {str(row["team"]) for row in calibrated_ranking[:20]}

    rows: list[dict[str, float | int | str | None]] = []
    for team in teams:
        standard_row = standard_by_team.get(team)
        calibrated_row = calibrated_by_team.get(team)
        standard_rank = int(standard_row["rank"]) if standard_row else None
        calibrated_rank = int(calibrated_row["rank"]) if calibrated_row else None
        rows.append(
            {
                "team": team,
                "standard_rank": standard_rank,
                "calibrated_rank": calibrated_rank,
                "rank_delta": (
                    standard_rank - calibrated_rank
                    if standard_rank is not None and calibrated_rank is not None
                    else None
                ),
                "standard_final_elo": float(standard_row["final_elo"]) if standard_row else None,
                "calibrated_final_elo": float(calibrated_row["final_elo"]) if calibrated_row else None,
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            int(row["calibrated_rank"]) if row["calibrated_rank"] is not None else 9999,
            int(row["standard_rank"]) if row["standard_rank"] is not None else 9999,
        ),
    )


def distribution_summary(teams: dict[str, dict[str, float | int]]) -> dict[str, float]:
    ratings = [float(values["final_elo"]) for values in teams.values()]
    return {
        "team_count": float(len(ratings)),
        "mean": statistics.mean(ratings),
        "median": statistics.median(ratings),
        "std": statistics.pstdev(ratings),
        "min": min(ratings),
        "max": max(ratings),
    }


def extreme_teams(
    teams: dict[str, dict[str, float | int]],
    low_threshold: float = 1000.0,
    high_threshold: float = 2200.0,
) -> dict[str, list[dict[str, float | int | str]]]:
    low = [
        {"team": team, "final_elo": values["final_elo"], "matches": values["matches"]}
        for team, values in teams.items()
        if float(values["final_elo"]) < low_threshold
    ]
    high = [
        {"team": team, "final_elo": values["final_elo"], "matches": values["matches"]}
        for team, values in teams.items()
        if float(values["final_elo"]) > high_threshold
    ]
    return {
        "below_1000": sorted(low, key=lambda row: float(row["final_elo"])),
        "above_2200": sorted(high, key=lambda row: float(row["final_elo"]), reverse=True),
    }


def evaluate_model(matches: list[Any], model: dict[str, str | float]) -> dict[str, Any]:
    variant = str(model["goal_diff_variant"])
    goal_diff_fn = None if variant == "none" else goal_diff_multiplier(variant)
    rebuilt_rows = rebuild_elo_history(
        matches,
        k_factor=float(model["k_factor"]),
        goal_diff_multiplier_fn=goal_diff_fn,
        model_version=str(model["name"]),
    )
    metrics = evaluate_rebuilt_elo_rows(rebuilt_rows)
    teams = final_team_ratings(rebuilt_rows)
    return {
        "config": model,
        "rows": rebuilt_rows,
        "metrics": metrics,
        "teams": teams,
        "ranking": ranking(teams),
        "distribution": distribution_summary(teams),
        "extreme_teams": extreme_teams(teams),
    }


def build_benchmark_report(input_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = read_match_rows(input_path)
    matches = parse_match_rows(source_rows, skip_unplayed=True)
    if not matches:
        raise ValueError(f"{input_path} contains no completed match rows")

    standard = evaluate_model(matches, STANDARD_MODEL)
    calibrated = evaluate_model(matches, CALIBRATED_MODEL)

    standard_metrics = standard["metrics"]
    calibrated_metrics = calibrated["metrics"]
    deltas = {
        "accuracy_delta": calibrated_metrics["accuracy"] - standard_metrics["accuracy"],
        "log_loss_delta": standard_metrics["log_loss"] - calibrated_metrics["log_loss"],
        "brier_delta": standard_metrics["brier_score"] - calibrated_metrics["brier_score"],
    }

    report_rows = [
        {
            "model": STANDARD_MODEL["name"],
            **standard_metrics,
            "accuracy_delta": 0.0,
            "log_loss_delta": 0.0,
            "brier_delta": 0.0,
        },
        {
            "model": CALIBRATED_MODEL["name"],
            **calibrated_metrics,
            **deltas,
        },
    ]

    payload = {
        "models": {
            "standard_elo_v1": {
                "config": standard["config"],
                "metrics": standard_metrics,
                "distribution": standard["distribution"],
                "extreme_teams": standard["extreme_teams"],
            },
            "calibrated_elo_v2_candidate": {
                "config": calibrated["config"],
                "metrics": calibrated_metrics,
                "distribution": calibrated["distribution"],
                "extreme_teams": calibrated["extreme_teams"],
            },
        },
        "improvement": deltas,
        "largest_team_elo_changes": team_rating_deltas(standard["teams"], calibrated["teams"]),
        "top20_ranking_comparison": top20_ranking_comparison(
            standard["ranking"], calibrated["ranking"]
        ),
        "recommendation": {
            "promote_to_calibrated_elo_v2": (
                deltas["log_loss_delta"] > 0 and deltas["brier_delta"] > 0
            ),
            "keep_parameters": {
                "k_factor": 80.0,
                "goal_diff_multiplier": "log_margin",
                "tournament_weight": 1.0,
                "home_advantage": 0.0,
            },
            "retire_parameters": {
                "k_factor": 20.0,
                "goal_diff_multiplier": "none",
            },
        },
    }
    return report_rows, payload


def write_report_outputs(
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
    parser = argparse.ArgumentParser(description="Build Elo benchmark report.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/matches_with_elo.csv"),
        help="Input processed matches CSV. Only date/team/score columns are used for rebuild.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/elo_benchmark_report.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/elo_benchmark_report.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = build_benchmark_report(args.input)
    write_report_outputs(rows, payload, args.output_csv, args.output_json)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    for row in rows:
        print(
            f"{row['model']} "
            f"accuracy={float(row['accuracy']):.6f} "
            f"log_loss={float(row['log_loss']):.6f} "
            f"brier_score={float(row['brier_score']):.6f}"
        )
    print(
        "improvement "
        f"accuracy_delta={payload['improvement']['accuracy_delta']:.6f} "
        f"log_loss_delta={payload['improvement']['log_loss_delta']:.6f} "
        f"brier_delta={payload['improvement']['brier_delta']:.6f}"
    )


if __name__ == "__main__":
    main()
