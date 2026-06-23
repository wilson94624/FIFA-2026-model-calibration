from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model.elo_rebuilder import MatchInput, parse_match_rows, rebuild_elo_history
from src.model.expected_goals import BASE_AWAY_XG, BASE_HOME_XG, C1, MIN_XG, elo_only_expected_goals
from src.model.metrics import brier_score, multiclass_log_loss
from src.model.poisson import outcome_probabilities, score_matrix
from src.tuning.evaluation import actual_label
from src.tuning.time_split_validation import filter_matches_for_universe
from src.tuning.tune_gd_shrinkage import gd_shrinkage_multiplier
from src.tuning.tune_k_factor import read_match_rows
from src.tuning.universe_benchmark import read_team_universe

MODEL_CONFIGS = (
    {
        "model": "standard_elo_v1",
        "k_factor": 20.0,
        "gd_variant": "none",
        "alpha": None,
    },
    {
        "model": "calibrated_elo_v2_candidate",
        "k_factor": 80.0,
        "gd_variant": "log_margin",
        "alpha": 1.0,
    },
    {
        "model": "calibrated_elo_v3_candidate",
        "k_factor": 80.0,
        "gd_variant": "log_margin_shrinkage",
        "alpha": 0.10,
    },
)

REPORT_COLUMNS = [
    "model",
    "matches",
    "home_goal_mae",
    "away_goal_mae",
    "total_goals_mae",
    "goal_difference_mae",
    "poisson_log_loss",
    "brier_score",
    "mean_predicted_home_xg",
    "mean_predicted_away_xg",
    "mean_actual_home_goals",
    "mean_actual_away_goals",
]


def multiplier_for_config(config: dict[str, Any]) -> Callable[[int, int], float] | None:
    if config["gd_variant"] == "none":
        return None
    alpha = config["alpha"]
    if alpha is None:
        return None
    return gd_shrinkage_multiplier(float(alpha))


def rebuild_for_config(
    matches: list[MatchInput],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    return rebuild_elo_history(
        matches,
        k_factor=float(config["k_factor"]),
        goal_diff_multiplier_fn=multiplier_for_config(config),
        model_version=str(config["model"]),
    )


def evaluate_elo_to_xg_rows(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not rows:
        raise ValueError("at least one rebuilt Elo row is required")

    home_errors: list[float] = []
    away_errors: list[float] = []
    total_errors: list[float] = []
    goal_diff_errors: list[float] = []
    home_xgs: list[float] = []
    away_xgs: list[float] = []
    actual_home_goals: list[int] = []
    actual_away_goals: list[int] = []
    labels: list[str] = []
    outcome_probs: list[dict[str, float]] = []
    predictions: list[dict[str, Any]] = []

    for row in rows:
        home_score = int(row["home_score"])
        away_score = int(row["away_score"])
        home_xg, away_xg = elo_only_expected_goals(
            float(row["home_pre_match_elo"]),
            float(row["away_pre_match_elo"]),
        )
        probabilities = outcome_probabilities(score_matrix(home_xg, away_xg))
        label = actual_label(home_score, away_score)

        home_errors.append(abs(home_xg - home_score))
        away_errors.append(abs(away_xg - away_score))
        total_errors.append(abs((home_xg + away_xg) - (home_score + away_score)))
        goal_diff_errors.append(abs((home_xg - away_xg) - (home_score - away_score)))
        home_xgs.append(home_xg)
        away_xgs.append(away_xg)
        actual_home_goals.append(home_score)
        actual_away_goals.append(away_score)
        labels.append(label)
        outcome_probs.append(probabilities)
        predictions.append(
            {
                "match_id": row["match_id"],
                "date": row["date"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "home_score": home_score,
                "away_score": away_score,
                "predicted_home_xg": home_xg,
                "predicted_away_xg": away_xg,
                "home_win_probability": probabilities["home"],
                "draw_probability": probabilities["draw"],
                "away_win_probability": probabilities["away"],
            }
        )

    metrics = {
        "matches": len(rows),
        "home_goal_mae": statistics.mean(home_errors),
        "away_goal_mae": statistics.mean(away_errors),
        "total_goals_mae": statistics.mean(total_errors),
        "goal_difference_mae": statistics.mean(goal_diff_errors),
        "poisson_log_loss": multiclass_log_loss(labels, outcome_probs),
        "brier_score": brier_score(labels, outcome_probs),
        "mean_predicted_home_xg": statistics.mean(home_xgs),
        "mean_predicted_away_xg": statistics.mean(away_xgs),
        "mean_actual_home_goals": statistics.mean(actual_home_goals),
        "mean_actual_away_goals": statistics.mean(actual_away_goals),
    }
    return metrics, predictions


def build_elo_to_xg_benchmark(
    input_path: Path,
    team_universe_path: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = read_match_rows(input_path)
    matches = parse_match_rows(source_rows, skip_unplayed=True)
    if team_universe_path is not None:
        team_universe = read_team_universe(team_universe_path)
        matches = filter_matches_for_universe(matches, team_universe)
    if not matches:
        raise ValueError("no completed matches available for Elo-to-xG benchmark")

    report_rows: list[dict[str, Any]] = []
    model_payloads: dict[str, Any] = {}
    for config in MODEL_CONFIGS:
        rebuilt_rows = rebuild_for_config(matches, config)
        metrics, predictions = evaluate_elo_to_xg_rows(rebuilt_rows)
        row = {"model": config["model"], **metrics}
        report_rows.append(row)
        model_payloads[str(config["model"])] = {
            "config": config,
            "metrics": metrics,
            "sample_predictions": predictions[:20],
        }

    summary = {
        "best_home_goal_mae": min(report_rows, key=lambda row: float(row["home_goal_mae"])),
        "best_away_goal_mae": min(report_rows, key=lambda row: float(row["away_goal_mae"])),
        "best_total_goals_mae": min(report_rows, key=lambda row: float(row["total_goals_mae"])),
        "best_goal_difference_mae": min(
            report_rows,
            key=lambda row: float(row["goal_difference_mae"]),
        ),
        "best_poisson_log_loss": min(report_rows, key=lambda row: float(row["poisson_log_loss"])),
        "best_brier_score": min(report_rows, key=lambda row: float(row["brier_score"])),
    }
    payload = {
        "expected_goals_formula": {
            "description": "home_xg=max(min_xg, base_home + c1 * (home_elo-away_elo)/450); away_xg=max(min_xg, base_away - c1 * (home_elo-away_elo)/450)",
            "c1": C1,
            "base_home": BASE_HOME_XG,
            "base_away": BASE_AWAY_XG,
            "min_xg": MIN_XG,
        },
        "universe": (
            {
                "name": "fifa_historical",
                "label": "FIFA + historical national teams",
                "source": str(team_universe_path),
            }
            if team_universe_path is not None
            else {"name": "all", "label": "All teams"}
        ),
        "rows": report_rows,
        "models": model_payloads,
        "summary": summary,
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
    parser = argparse.ArgumentParser(description="Benchmark Elo-to-xG conversion by Elo source.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
        help="Optional team universe CSV. Defaults to FIFA+historical universe.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/elo_to_xg_benchmark.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/elo_to_xg_benchmark.json"),
    )
    parser.add_argument("--all-teams", action="store_true", help="Disable team universe filtering.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    team_universe_path = None if args.all_teams else args.team_universe
    rows, payload = build_elo_to_xg_benchmark(args.input, team_universe_path)
    write_outputs(rows, payload, args.output_csv, args.output_json)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    for row in rows:
        print(
            f"{row['model']} matches={row['matches']} "
            f"home_mae={float(row['home_goal_mae']):.6f} "
            f"away_mae={float(row['away_goal_mae']):.6f} "
            f"total_mae={float(row['total_goals_mae']):.6f} "
            f"gd_mae={float(row['goal_difference_mae']):.6f} "
            f"log_loss={float(row['poisson_log_loss']):.6f} "
            f"brier={float(row['brier_score']):.6f}"
        )
    print(f"best_poisson_log_loss: {payload['summary']['best_poisson_log_loss']['model']}")
    print(f"best_brier_score: {payload['summary']['best_brier_score']['model']}")


if __name__ == "__main__":
    main()
