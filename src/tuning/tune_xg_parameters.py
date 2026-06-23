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

BASE_HOME_VALUES = (1.0, 1.1, 1.2, 1.3, 1.4, 1.5)
BASE_AWAY_VALUES = (1.0, 1.1, 1.2, 1.3, 1.4)
C1_VALUES = (0.50, 0.75, 1.00, 1.25, 1.50)
CALIBRATED_ELO_V3 = {
    "model": "calibrated_elo_v3_candidate",
    "k_factor": 80.0,
    "goal_diff_shrinkage_alpha": 0.10,
}

REPORT_COLUMNS = [
    "base_home",
    "base_away",
    "c1",
    "matches",
    "home_goal_mae",
    "away_goal_mae",
    "total_goals_mae",
    "goal_difference_mae",
    "poisson_log_loss",
    "brier_score",
    "predicted_avg_home_goals",
    "predicted_avg_away_goals",
    "predicted_avg_total_goals",
    "actual_avg_home_goals",
    "actual_avg_away_goals",
    "actual_avg_total_goals",
    "predicted_minus_actual_total_goals",
]


def rebuild_calibrated_v3(matches: list[MatchInput]) -> list[dict[str, Any]]:
    return rebuild_elo_history(
        matches,
        k_factor=float(CALIBRATED_ELO_V3["k_factor"]),
        goal_diff_multiplier_fn=gd_shrinkage_multiplier(
            float(CALIBRATED_ELO_V3["goal_diff_shrinkage_alpha"])
        ),
        model_version=str(CALIBRATED_ELO_V3["model"]),
    )


def evaluate_xg_parameters(
    rows: list[dict[str, Any]],
    base_home: float,
    base_away: float,
    c1: float,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("at least one rebuilt Elo row is required")

    home_errors: list[float] = []
    away_errors: list[float] = []
    total_errors: list[float] = []
    goal_diff_errors: list[float] = []
    predicted_home: list[float] = []
    predicted_away: list[float] = []
    actual_home: list[int] = []
    actual_away: list[int] = []
    labels: list[str] = []
    probabilities: list[dict[str, float]] = []

    for row in rows:
        home_score = int(row["home_score"])
        away_score = int(row["away_score"])
        home_xg, away_xg = elo_only_expected_goals(
            float(row["home_pre_match_elo"]),
            float(row["away_pre_match_elo"]),
            c1=c1,
            base_home=base_home,
            base_away=base_away,
            min_xg=MIN_XG,
        )
        outcome_probs = outcome_probabilities(score_matrix(home_xg, away_xg))

        home_errors.append(abs(home_xg - home_score))
        away_errors.append(abs(away_xg - away_score))
        total_errors.append(abs((home_xg + away_xg) - (home_score + away_score)))
        goal_diff_errors.append(abs((home_xg - away_xg) - (home_score - away_score)))
        predicted_home.append(home_xg)
        predicted_away.append(away_xg)
        actual_home.append(home_score)
        actual_away.append(away_score)
        labels.append(actual_label(home_score, away_score))
        probabilities.append(outcome_probs)

    predicted_avg_home = statistics.mean(predicted_home)
    predicted_avg_away = statistics.mean(predicted_away)
    actual_avg_home = statistics.mean(actual_home)
    actual_avg_away = statistics.mean(actual_away)
    predicted_avg_total = predicted_avg_home + predicted_avg_away
    actual_avg_total = actual_avg_home + actual_avg_away

    return {
        "base_home": base_home,
        "base_away": base_away,
        "c1": c1,
        "matches": len(rows),
        "home_goal_mae": statistics.mean(home_errors),
        "away_goal_mae": statistics.mean(away_errors),
        "total_goals_mae": statistics.mean(total_errors),
        "goal_difference_mae": statistics.mean(goal_diff_errors),
        "poisson_log_loss": multiclass_log_loss(labels, probabilities),
        "brier_score": brier_score(labels, probabilities),
        "predicted_avg_home_goals": predicted_avg_home,
        "predicted_avg_away_goals": predicted_avg_away,
        "predicted_avg_total_goals": predicted_avg_total,
        "actual_avg_home_goals": actual_avg_home,
        "actual_avg_away_goals": actual_avg_away,
        "actual_avg_total_goals": actual_avg_total,
        "predicted_minus_actual_total_goals": predicted_avg_total - actual_avg_total,
    }


def load_rebuilt_calibrated_v3_rows(
    input_path: Path,
    team_universe_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = read_match_rows(input_path)
    matches = parse_match_rows(source_rows, skip_unplayed=True)
    team_universe = read_team_universe(team_universe_path)
    universe_matches = filter_matches_for_universe(matches, team_universe)
    if not universe_matches:
        raise ValueError("no matches remain after FIFA+historical universe filtering")
    return rebuild_calibrated_v3(universe_matches), {
        "source_matches": len(matches),
        "universe_matches": len(universe_matches),
    }


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    current = next(
        row
        for row in rows
        if float(row["base_home"]) == BASE_HOME_XG
        and float(row["base_away"]) == BASE_AWAY_XG
        and float(row["c1"]) == C1
    )
    best_log_loss = min(rows, key=lambda row: float(row["poisson_log_loss"]))
    best_brier = min(rows, key=lambda row: float(row["brier_score"]))
    best_total_mae = min(rows, key=lambda row: float(row["total_goals_mae"]))
    best_total_avg_match = min(
        rows,
        key=lambda row: abs(float(row["predicted_minus_actual_total_goals"])),
    )
    return {
        "current_formula": current,
        "best_home_goal_mae": min(rows, key=lambda row: float(row["home_goal_mae"])),
        "best_away_goal_mae": min(rows, key=lambda row: float(row["away_goal_mae"])),
        "best_total_goals_mae": best_total_mae,
        "best_goal_difference_mae": min(
            rows,
            key=lambda row: float(row["goal_difference_mae"]),
        ),
        "best_poisson_log_loss": best_log_loss,
        "best_brier_score": best_brier,
        "closest_predicted_total_goals_to_history": best_total_avg_match,
        "recommended_calibrated_xg_v1_candidate": {
            "base_home": best_log_loss["base_home"],
            "base_away": best_log_loss["base_away"],
            "c1": best_log_loss["c1"],
            "selection_metric": "poisson_log_loss",
            "reason": (
                "Poisson W/D/L LogLoss is the primary probability-calibration metric; "
                "Brier Score and goal MAE should be reviewed as secondary checks."
            ),
        },
    }


def tune_xg_parameters(
    input_path: Path,
    team_universe_path: Path,
    base_home_values: tuple[float, ...] = BASE_HOME_VALUES,
    base_away_values: tuple[float, ...] = BASE_AWAY_VALUES,
    c1_values: tuple[float, ...] = C1_VALUES,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rebuilt_rows, source_summary = load_rebuilt_calibrated_v3_rows(input_path, team_universe_path)

    rows: list[dict[str, Any]] = []
    for base_home in base_home_values:
        for base_away in base_away_values:
            for c1 in c1_values:
                rows.append(evaluate_xg_parameters(rebuilt_rows, base_home, base_away, c1))

    payload = {
        "elo_source": CALIBRATED_ELO_V3,
        "universe": {
            "name": "fifa_historical",
            "label": "FIFA + historical national teams",
            **source_summary,
        },
        "search_space": {
            "base_home": list(base_home_values),
            "base_away": list(base_away_values),
            "c1": list(c1_values),
            "min_xg": MIN_XG,
        },
        "formal_formula_unchanged": True,
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


def _parse_float_tuple(values: list[str] | None, default: tuple[float, ...]) -> tuple[float, ...]:
    if not values:
        return default
    return tuple(float(value) for value in values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tune Elo-to-xG formula parameters.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/xg_parameter_search.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/xg_parameter_search.json"),
    )
    parser.add_argument("--base-home", action="append", help="Candidate base_home value.")
    parser.add_argument("--base-away", action="append", help="Candidate base_away value.")
    parser.add_argument("--c1", action="append", help="Candidate c1 value.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = tune_xg_parameters(
        args.input,
        args.team_universe,
        base_home_values=_parse_float_tuple(args.base_home, BASE_HOME_VALUES),
        base_away_values=_parse_float_tuple(args.base_away, BASE_AWAY_VALUES),
        c1_values=_parse_float_tuple(args.c1, C1_VALUES),
    )
    write_outputs(rows, payload, args.output_csv, args.output_json)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    print(f"evaluated_parameter_sets: {len(rows)}")
    for key in ("best_poisson_log_loss", "best_brier_score", "best_total_goals_mae"):
        row = payload["summary"][key]
        print(
            f"{key}: base_home={float(row['base_home']):.2f} "
            f"base_away={float(row['base_away']):.2f} "
            f"c1={float(row['c1']):.2f} "
            f"log_loss={float(row['poisson_log_loss']):.6f} "
            f"brier={float(row['brier_score']):.6f} "
            f"total_mae={float(row['total_goals_mae']):.6f} "
            f"pred_total={float(row['predicted_avg_total_goals']):.6f}"
        )


if __name__ == "__main__":
    main()
