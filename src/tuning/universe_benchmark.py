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
from src.tuning.elo_benchmark_report import CALIBRATED_MODEL, STANDARD_MODEL
from src.tuning.evaluation import evaluate_rebuilt_elo_rows
from src.tuning.tune_goal_diff_multiplier import goal_diff_multiplier
from src.tuning.tune_k_factor import read_match_rows

UNIVERSES = ("all", "fifa_only", "fifa_historical")
REPORT_COLUMNS = [
    "universe",
    "model",
    "matches",
    "team_count",
    "accuracy",
    "log_loss",
    "brier_score",
    "mean_elo",
    "median_elo",
    "std_elo",
    "min_elo",
    "max_elo",
]


def read_team_universe(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["team"]: row for row in csv.DictReader(handle)}


def team_allowed(team: str, universe: str, team_universe: dict[str, dict[str, str]]) -> bool:
    if universe == "all":
        return True
    row = team_universe.get(team)
    if row is None:
        return False
    if universe == "fifa_only":
        return row["include_fifa_only"] == "TRUE"
    if universe == "fifa_historical":
        return row["include_fifa_historical"] == "TRUE"
    raise ValueError(f"unknown universe {universe!r}")


def filter_rows_for_universe(
    rows: list[dict[str, Any]],
    universe: str,
    team_universe: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if team_allowed(str(row["home_team"]), universe, team_universe)
        and team_allowed(str(row["away_team"]), universe, team_universe)
    ]


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


def distribution(teams: dict[str, dict[str, float | int]]) -> dict[str, float]:
    ratings = [float(values["final_elo"]) for values in teams.values()]
    if not ratings:
        raise ValueError("cannot summarize empty team set")
    return {
        "team_count": float(len(ratings)),
        "mean_elo": statistics.mean(ratings),
        "median_elo": statistics.median(ratings),
        "std_elo": statistics.pstdev(ratings),
        "min_elo": min(ratings),
        "max_elo": max(ratings),
    }


def ranking(teams: dict[str, dict[str, float | int]]) -> list[dict[str, float | int | str]]:
    return [
        {"rank": index, "team": team, "final_elo": values["final_elo"], "matches": values["matches"]}
        for index, (team, values) in enumerate(
            sorted(teams.items(), key=lambda item: float(item[1]["final_elo"]), reverse=True),
            start=1,
        )
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


def top20_comparison(
    standard_ranking: list[dict[str, float | int | str]],
    calibrated_ranking: list[dict[str, float | int | str]],
) -> list[dict[str, Any]]:
    standard_by_team = {str(row["team"]): row for row in standard_ranking}
    calibrated_by_team = {str(row["team"]): row for row in calibrated_ranking}
    teams = {str(row["team"]) for row in standard_ranking[:20]} | {
        str(row["team"]) for row in calibrated_ranking[:20]
    }
    rows: list[dict[str, Any]] = []
    for team in teams:
        standard = standard_by_team.get(team)
        calibrated = calibrated_by_team.get(team)
        rows.append(
            {
                "team": team,
                "standard_rank": standard["rank"] if standard else None,
                "calibrated_rank": calibrated["rank"] if calibrated else None,
                "standard_final_elo": standard["final_elo"] if standard else None,
                "calibrated_final_elo": calibrated["final_elo"] if calibrated else None,
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            int(row["calibrated_rank"]) if row["calibrated_rank"] is not None else 9999,
            int(row["standard_rank"]) if row["standard_rank"] is not None else 9999,
        ),
    )


def anomaly_presence(ranking_rows: list[dict[str, float | int | str]]) -> dict[str, Any]:
    by_team = {str(row["team"]): row for row in ranking_rows}
    result: dict[str, Any] = {}
    for team in ("Basque Country", "Jersey", "Norway"):
        row = by_team.get(team)
        result[team] = {
            "present": row is not None,
            "rank": row["rank"] if row else None,
            "final_elo": row["final_elo"] if row else None,
        }
    return result


def build_universe_benchmark(
    input_path: Path,
    team_universe_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = read_match_rows(input_path)
    matches = parse_match_rows(source_rows, skip_unplayed=True)
    if not matches:
        raise ValueError(f"{input_path} contains no completed match rows")
    team_universe = read_team_universe(team_universe_path)

    rebuilt = {
        STANDARD_MODEL["name"]: rebuild_for_model(matches, STANDARD_MODEL),
        CALIBRATED_MODEL["name"]: rebuild_for_model(matches, CALIBRATED_MODEL),
    }

    report_rows: list[dict[str, Any]] = []
    payload: dict[str, Any] = {"universes": {}, "rows": report_rows}
    for universe in UNIVERSES:
        universe_payload: dict[str, Any] = {"models": {}}
        rankings: dict[str, list[dict[str, float | int | str]]] = {}
        for model_name, rows in rebuilt.items():
            subset_rows = filter_rows_for_universe(rows, universe, team_universe)
            metrics = evaluate_rebuilt_elo_rows(subset_rows)
            teams = final_team_ratings(subset_rows)
            dist = distribution(teams)
            rank = ranking(teams)
            rankings[model_name] = rank
            report_row = {
                "universe": universe,
                "model": model_name,
                "matches": len(subset_rows),
                **metrics,
                **dist,
            }
            report_rows.append(report_row)
            universe_payload["models"][model_name] = {
                "matches": len(subset_rows),
                "metrics": metrics,
                "distribution": dist,
                "top20": rank[:20],
                "anomaly_presence": anomaly_presence(rank),
            }
        universe_payload["top20_ranking_comparison"] = top20_comparison(
            rankings[STANDARD_MODEL["name"]],
            rankings[CALIBRATED_MODEL["name"]],
        )
        payload["universes"][universe] = universe_payload

    payload["analysis"] = {
        "basque_country_removed_from_fifa_universes": not payload["universes"]["fifa_historical"][
            "models"
        ][CALIBRATED_MODEL["name"]]["anomaly_presence"]["Basque Country"]["present"],
        "jersey_removed_from_fifa_universes": not payload["universes"]["fifa_historical"]["models"][
            CALIBRATED_MODEL["name"]
        ]["anomaly_presence"]["Jersey"]["present"],
        "recommendation": {
            "verdict": "B",
            "label": "use_fifa_historical_universe_but_continue_shrinkage_research",
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
    parser = argparse.ArgumentParser(description="Run universe-aware Elo benchmark.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument("--output-csv", type=Path, default=Path("results/universe_benchmark.csv"))
    parser.add_argument("--output-json", type=Path, default=Path("results/universe_benchmark.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = build_universe_benchmark(args.input, args.team_universe)
    write_outputs(rows, payload, args.output_csv, args.output_json)
    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    for row in rows:
        print(
            f"{row['universe']} | {row['model']} | matches={row['matches']} "
            f"accuracy={float(row['accuracy']):.6f} "
            f"log_loss={float(row['log_loss']):.6f} "
            f"brier_score={float(row['brier_score']):.6f} "
            f"max_elo={float(row['max_elo']):.3f}"
        )


if __name__ == "__main__":
    main()
