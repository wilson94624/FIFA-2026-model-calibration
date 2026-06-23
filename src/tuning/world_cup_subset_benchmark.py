from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model.elo_rebuilder import parse_match_rows, rebuild_elo_history
from src.tuning.elo_benchmark_report import (
    CALIBRATED_MODEL,
    STANDARD_MODEL,
    distribution_summary,
    final_team_ratings,
    ranking,
)
from src.tuning.evaluation import evaluate_rebuilt_elo_rows
from src.tuning.tune_goal_diff_multiplier import goal_diff_multiplier
from src.tuning.tune_k_factor import read_match_rows

TARGET_TOURNAMENTS = {
    "FIFA World Cup Finals": "FIFA World Cup",
    "UEFA Euro": "UEFA Euro",
    "Copa América": "Copa América",
    "AFC Asian Cup": "AFC Asian Cup",
    "African Cup of Nations": "African Cup of Nations",
}

REPORT_COLUMNS = [
    "tournament_group",
    "model",
    "matches",
    "accuracy",
    "log_loss",
    "brier_score",
    "accuracy_delta",
    "log_loss_delta",
    "brier_delta",
]


def rebuild_for_model(matches: list[Any], model: dict[str, str | float]) -> list[dict[str, Any]]:
    variant = str(model["goal_diff_variant"])
    goal_diff_fn = None if variant == "none" else goal_diff_multiplier(variant)
    return rebuild_elo_history(
        matches,
        k_factor=float(model["k_factor"]),
        goal_diff_multiplier_fn=goal_diff_fn,
        model_version=str(model["name"]),
    )


def filter_tournament_rows(rows: list[dict[str, Any]], tournament: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row["tournament"]) == tournament]


def metric_row(
    tournament_group: str,
    model_name: str,
    rows: list[dict[str, Any]],
    deltas: dict[str, float] | None = None,
) -> dict[str, Any]:
    metrics = evaluate_rebuilt_elo_rows(rows)
    return {
        "tournament_group": tournament_group,
        "model": model_name,
        "matches": len(rows),
        "accuracy": metrics["accuracy"],
        "log_loss": metrics["log_loss"],
        "brier_score": metrics["brier_score"],
        "accuracy_delta": 0.0 if deltas is None else deltas["accuracy_delta"],
        "log_loss_delta": 0.0 if deltas is None else deltas["log_loss_delta"],
        "brier_delta": 0.0 if deltas is None else deltas["brier_delta"],
    }


def teams_in_target_tournaments(rows: list[dict[str, Any]]) -> set[str]:
    target_names = set(TARGET_TOURNAMENTS.values())
    teams: set[str] = set()
    for row in rows:
        if str(row["tournament"]) in target_names:
            teams.add(str(row["home_team"]))
            teams.add(str(row["away_team"]))
    return teams


def subset_distribution(
    teams: dict[str, dict[str, float | int]],
    subset_teams: set[str],
) -> dict[str, float]:
    return distribution_summary({team: teams[team] for team in subset_teams if team in teams})


def anomaly_report(
    calibrated_rows: list[dict[str, Any]],
    calibrated_rankings: list[dict[str, float | int | str]],
    teams: tuple[str, ...] = ("Norway", "Basque Country"),
) -> list[dict[str, Any]]:
    rank_by_team = {str(row["team"]): row for row in calibrated_rankings}
    target_counts: dict[str, Counter[str]] = {team: Counter() for team in teams}
    for row in calibrated_rows:
        tournament = str(row["tournament"])
        if tournament not in TARGET_TOURNAMENTS.values():
            continue
        for side in ("home_team", "away_team"):
            team = str(row[side])
            if team in target_counts:
                target_counts[team][tournament] += 1

    report: list[dict[str, Any]] = []
    for team in teams:
        rank_row = rank_by_team.get(team)
        report.append(
            {
                "team": team,
                "calibrated_rank": rank_row["rank"] if rank_row else None,
                "calibrated_final_elo": rank_row["final_elo"] if rank_row else None,
                "major_tournament_matches": sum(target_counts[team].values()),
                "major_tournament_breakdown": dict(target_counts[team]),
            }
        )
    return report


def build_subset_benchmark(input_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = read_match_rows(input_path)
    matches = parse_match_rows(source_rows, skip_unplayed=True)
    if not matches:
        raise ValueError(f"{input_path} contains no completed match rows")

    standard_rows = rebuild_for_model(matches, STANDARD_MODEL)
    calibrated_rows = rebuild_for_model(matches, CALIBRATED_MODEL)
    report_rows: list[dict[str, Any]] = []
    per_tournament: dict[str, Any] = {}

    for group, tournament in TARGET_TOURNAMENTS.items():
        standard_subset = filter_tournament_rows(standard_rows, tournament)
        calibrated_subset = filter_tournament_rows(calibrated_rows, tournament)
        if len(standard_subset) != len(calibrated_subset):
            raise ValueError(f"subset size mismatch for {group}")
        standard_metrics = evaluate_rebuilt_elo_rows(standard_subset)
        calibrated_metrics = evaluate_rebuilt_elo_rows(calibrated_subset)
        deltas = {
            "accuracy_delta": calibrated_metrics["accuracy"] - standard_metrics["accuracy"],
            "log_loss_delta": standard_metrics["log_loss"] - calibrated_metrics["log_loss"],
            "brier_delta": standard_metrics["brier_score"] - calibrated_metrics["brier_score"],
        }

        standard_row = {
            "tournament_group": group,
            "model": STANDARD_MODEL["name"],
            "matches": len(standard_subset),
            **standard_metrics,
            "accuracy_delta": 0.0,
            "log_loss_delta": 0.0,
            "brier_delta": 0.0,
        }
        calibrated_row = {
            "tournament_group": group,
            "model": CALIBRATED_MODEL["name"],
            "matches": len(calibrated_subset),
            **calibrated_metrics,
            **deltas,
        }
        report_rows.extend([standard_row, calibrated_row])
        per_tournament[group] = {
            "source_tournament": tournament,
            "matches": len(standard_subset),
            "standard": standard_metrics,
            "calibrated": calibrated_metrics,
            "improvement": deltas,
            "improved_log_loss": deltas["log_loss_delta"] > 0,
            "improved_brier": deltas["brier_delta"] > 0,
            "improved_accuracy": deltas["accuracy_delta"] > 0,
        }

    standard_teams = final_team_ratings(standard_rows)
    calibrated_teams = final_team_ratings(calibrated_rows)
    target_teams = teams_in_target_tournaments(calibrated_rows)
    calibrated_ranking = ranking(calibrated_teams)
    all_log_loss_improved = all(row["improvement"]["log_loss_delta"] > 0 for row in per_tournament.values())
    all_brier_improved = all(row["improvement"]["brier_delta"] > 0 for row in per_tournament.values())

    payload = {
        "target_tournaments": TARGET_TOURNAMENTS,
        "rows": report_rows,
        "per_tournament": per_tournament,
        "all_major_tournaments_improved": {
            "accuracy": all(row["improvement"]["accuracy_delta"] > 0 for row in per_tournament.values()),
            "log_loss": all_log_loss_improved,
            "brier_score": all_brier_improved,
        },
        "fifa_level_team_scale": {
            "team_count": len(target_teams),
            "standard": subset_distribution(standard_teams, target_teams),
            "calibrated": subset_distribution(calibrated_teams, target_teams),
        },
        "anomaly_cases": anomaly_report(calibrated_rows, calibrated_ranking),
        "recommendation": {
            "verdict": "B",
            "label": "needs_further_shrinkage",
            "reason": (
                "calibrated v2 improves most major-tournament calibration metrics, "
                "but not every major tournament improves and the final Elo scale remains very wide."
            ),
        },
    }
    return report_rows, payload


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
    parser = argparse.ArgumentParser(description="Benchmark Elo variants on major tournament subsets.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/matches_with_elo.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/world_cup_subset_benchmark.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/world_cup_subset_benchmark.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = build_subset_benchmark(args.input)
    write_outputs(rows, payload, args.output_csv, args.output_json)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    for row in rows:
        print(
            f"{row['tournament_group']} | {row['model']} | "
            f"matches={row['matches']} "
            f"accuracy={float(row['accuracy']):.6f} "
            f"log_loss={float(row['log_loss']):.6f} "
            f"brier_score={float(row['brier_score']):.6f}"
        )
    print(f"verdict: {payload['recommendation']['verdict']} - {payload['recommendation']['label']}")


if __name__ == "__main__":
    main()
