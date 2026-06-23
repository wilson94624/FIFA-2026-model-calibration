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

from src.model.expected_goals import MIN_XG
from src.model.metrics import brier_score, multiclass_log_loss
from src.model.poisson import outcome_probabilities, score_matrix
from src.tuning.evaluation import actual_label
from src.tuning.neutral_xg_benchmark import (
    ASYMMETRIC_XG,
    CALIBRATED_ELO_V3,
    asymmetric_xg,
    rebuild_calibrated_v3,
)
from src.tuning.time_split_validation import filter_matches_for_universe
from src.tuning.tune_k_factor import read_match_rows
from src.tuning.universe_benchmark import read_team_universe
from src.model.elo_rebuilder import parse_match_rows

TARGET_TOURNAMENTS = ("FIFA World Cup", "UEFA Euro")
BASE_VALUES = (1.10, 1.20, 1.30, 1.40, 1.50)
C1_VALUES = (0.50, 0.75, 1.00, 1.25, 1.50)
SCALE_VALUES = (350.0, 400.0, 450.0, 500.0, 550.0)

REPORT_COLUMNS = [
    "base",
    "c1",
    "scale",
    "matches",
    "goal_mae",
    "team_a_goal_mae",
    "team_b_goal_mae",
    "total_goals_mae",
    "goal_difference_mae",
    "poisson_log_loss",
    "brier_score",
    "predicted_avg_team_a_goals",
    "predicted_avg_team_b_goals",
    "predicted_avg_total_goals",
    "actual_avg_team_a_goals",
    "actual_avg_team_b_goals",
    "actual_avg_total_goals",
    "predicted_minus_actual_total_goals",
]


def is_target_neutral_row(row: dict[str, Any]) -> bool:
    return (
        str(row["tournament"]) in TARGET_TOURNAMENTS
        and str(row.get("neutral", "")).strip().upper() == "TRUE"
    )


def neutral_symmetric_xg(
    team_a_elo: float,
    team_b_elo: float,
    base: float,
    c1: float,
    scale: float,
) -> tuple[float, float]:
    elo_diff = team_a_elo - team_b_elo
    adjustment = c1 * elo_diff / scale
    return max(MIN_XG, base + adjustment), max(MIN_XG, base - adjustment)


def evaluate_rows(
    rows: list[dict[str, Any]],
    xg_config: dict[str, float] | None = None,
    use_asymmetric: bool = False,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("at least one neutral World Cup/Euro row is required")

    team_a_errors: list[float] = []
    team_b_errors: list[float] = []
    total_errors: list[float] = []
    goal_diff_errors: list[float] = []
    predicted_a: list[float] = []
    predicted_b: list[float] = []
    actual_a: list[int] = []
    actual_b: list[int] = []
    labels: list[str] = []
    probabilities: list[dict[str, float]] = []

    for row in rows:
        team_a_score = int(row["home_score"])
        team_b_score = int(row["away_score"])
        team_a_elo = float(row["home_pre_match_elo"])
        team_b_elo = float(row["away_pre_match_elo"])
        if use_asymmetric:
            team_a_xg, team_b_xg = asymmetric_xg(team_a_elo, team_b_elo)
        else:
            if xg_config is None:
                raise ValueError("xg_config is required for neutral symmetric evaluation")
            team_a_xg, team_b_xg = neutral_symmetric_xg(
                team_a_elo,
                team_b_elo,
                base=float(xg_config["base"]),
                c1=float(xg_config["c1"]),
                scale=float(xg_config["scale"]),
            )
        outcome_probs = outcome_probabilities(score_matrix(team_a_xg, team_b_xg))

        team_a_errors.append(abs(team_a_xg - team_a_score))
        team_b_errors.append(abs(team_b_xg - team_b_score))
        total_errors.append(abs((team_a_xg + team_b_xg) - (team_a_score + team_b_score)))
        goal_diff_errors.append(abs((team_a_xg - team_b_xg) - (team_a_score - team_b_score)))
        predicted_a.append(team_a_xg)
        predicted_b.append(team_b_xg)
        actual_a.append(team_a_score)
        actual_b.append(team_b_score)
        labels.append(actual_label(team_a_score, team_b_score))
        probabilities.append(outcome_probs)

    team_a_mae = statistics.mean(team_a_errors)
    team_b_mae = statistics.mean(team_b_errors)
    predicted_avg_a = statistics.mean(predicted_a)
    predicted_avg_b = statistics.mean(predicted_b)
    actual_avg_a = statistics.mean(actual_a)
    actual_avg_b = statistics.mean(actual_b)
    return {
        "matches": len(rows),
        "goal_mae": (team_a_mae + team_b_mae) / 2.0,
        "team_a_goal_mae": team_a_mae,
        "team_b_goal_mae": team_b_mae,
        "total_goals_mae": statistics.mean(total_errors),
        "goal_difference_mae": statistics.mean(goal_diff_errors),
        "poisson_log_loss": multiclass_log_loss(labels, probabilities),
        "brier_score": brier_score(labels, probabilities),
        "predicted_avg_team_a_goals": predicted_avg_a,
        "predicted_avg_team_b_goals": predicted_avg_b,
        "predicted_avg_total_goals": predicted_avg_a + predicted_avg_b,
        "actual_avg_team_a_goals": actual_avg_a,
        "actual_avg_team_b_goals": actual_avg_b,
        "actual_avg_total_goals": actual_avg_a + actual_avg_b,
        "predicted_minus_actual_total_goals": (predicted_avg_a + predicted_avg_b)
        - (actual_avg_a + actual_avg_b),
    }


def load_target_rows(input_path: Path, team_universe_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = read_match_rows(input_path)
    matches = parse_match_rows(source_rows, skip_unplayed=True)
    team_universe = read_team_universe(team_universe_path)
    universe_matches = filter_matches_for_universe(matches, team_universe)
    rebuilt_rows = rebuild_calibrated_v3(universe_matches)
    target_rows = [row for row in rebuilt_rows if is_target_neutral_row(row)]
    if not target_rows:
        raise ValueError("no neutral FIFA World Cup / UEFA Euro rows found")
    return target_rows, {
        "source_matches": len(matches),
        "universe_matches": len(universe_matches),
        "target_matches": len(target_rows),
    }


def build_summary(rows: list[dict[str, Any]], asymmetric_baseline: dict[str, Any]) -> dict[str, Any]:
    best_log_loss = min(rows, key=lambda row: float(row["poisson_log_loss"]))
    best_brier = min(rows, key=lambda row: float(row["brier_score"]))
    best_goal_mae = min(rows, key=lambda row: float(row["goal_mae"]))
    best_total_mae = min(rows, key=lambda row: float(row["total_goals_mae"]))
    closest_total = min(
        rows,
        key=lambda row: abs(float(row["predicted_minus_actual_total_goals"])),
    )
    return {
        "current_asymmetric_baseline": asymmetric_baseline,
        "best_poisson_log_loss": best_log_loss,
        "best_brier_score": best_brier,
        "best_goal_mae": best_goal_mae,
        "best_total_goals_mae": best_total_mae,
        "closest_predicted_total_goals_to_history": closest_total,
        "best_log_loss_vs_asymmetric": {
            "log_loss_delta": float(asymmetric_baseline["poisson_log_loss"])
            - float(best_log_loss["poisson_log_loss"]),
            "brier_delta": float(asymmetric_baseline["brier_score"]) - float(best_log_loss["brier_score"]),
            "is_better_log_loss": float(best_log_loss["poisson_log_loss"])
            < float(asymmetric_baseline["poisson_log_loss"]),
            "is_better_brier": float(best_log_loss["brier_score"]) < float(asymmetric_baseline["brier_score"]),
        },
        "recommended_calibrated_xg_worldcup_v1_candidate": {
            "base": best_log_loss["base"],
            "c1": best_log_loss["c1"],
            "scale": best_log_loss["scale"],
            "selection_metric": "poisson_log_loss",
        },
    }


def search_worldcup_xg_parameters(
    input_path: Path,
    team_universe_path: Path,
    base_values: tuple[float, ...] = BASE_VALUES,
    c1_values: tuple[float, ...] = C1_VALUES,
    scale_values: tuple[float, ...] = SCALE_VALUES,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target_rows, source_summary = load_target_rows(input_path, team_universe_path)
    rows: list[dict[str, Any]] = []
    for base in base_values:
        for c1 in c1_values:
            for scale in scale_values:
                config = {"base": base, "c1": c1, "scale": scale}
                rows.append({**config, **evaluate_rows(target_rows, config)})

    asymmetric_baseline = {
        "formula": "current_asymmetric",
        **ASYMMETRIC_XG,
        **evaluate_rows(target_rows, use_asymmetric=True),
    }
    payload = {
        "elo_source": CALIBRATED_ELO_V3,
        "universe": {
            "name": "fifa_historical",
            "label": "FIFA + historical national teams",
            **source_summary,
        },
        "target": {
            "tournaments": list(TARGET_TOURNAMENTS),
            "neutral_only": True,
        },
        "search_space": {
            "base": list(base_values),
            "c1": list(c1_values),
            "scale": list(scale_values),
            "min_xg": MIN_XG,
        },
        "formal_model_formulas_unchanged": True,
        "rows": rows,
        "summary": build_summary(rows, asymmetric_baseline),
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
    parser = argparse.ArgumentParser(description="Search neutral World Cup/Euro xG parameters.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/worldcup_xg_parameter_search.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/worldcup_xg_parameter_search.json"),
    )
    parser.add_argument("--base", action="append", help="Candidate neutral base value.")
    parser.add_argument("--c1", action="append", help="Candidate c1 value.")
    parser.add_argument("--scale", action="append", help="Candidate Elo scale value.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = search_worldcup_xg_parameters(
        args.input,
        args.team_universe,
        base_values=_parse_float_tuple(args.base, BASE_VALUES),
        c1_values=_parse_float_tuple(args.c1, C1_VALUES),
        scale_values=_parse_float_tuple(args.scale, SCALE_VALUES),
    )
    write_outputs(rows, payload, args.output_csv, args.output_json)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    print(f"evaluated_parameter_sets: {len(rows)}")
    for key in ("best_poisson_log_loss", "best_brier_score", "best_total_goals_mae"):
        row = payload["summary"][key]
        print(
            f"{key}: base={float(row['base']):.2f} "
            f"c1={float(row['c1']):.2f} "
            f"scale={float(row['scale']):.0f} "
            f"log_loss={float(row['poisson_log_loss']):.6f} "
            f"brier={float(row['brier_score']):.6f} "
            f"total_mae={float(row['total_goals_mae']):.6f} "
            f"pred_total={float(row['predicted_avg_total_goals']):.6f}"
        )


if __name__ == "__main__":
    main()
