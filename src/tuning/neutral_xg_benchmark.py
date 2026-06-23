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
from src.model.expected_goals import MIN_XG, elo_only_expected_goals
from src.model.metrics import brier_score, multiclass_log_loss
from src.model.poisson import outcome_probabilities, score_matrix
from src.tuning.evaluation import actual_label
from src.tuning.time_split_validation import filter_matches_for_universe
from src.tuning.tune_gd_shrinkage import gd_shrinkage_multiplier
from src.tuning.tune_k_factor import read_match_rows
from src.tuning.universe_benchmark import read_team_universe

TOURNAMENT_GROUPS = {
    "FIFA World Cup": "FIFA World Cup",
    "UEFA Euro": "UEFA Euro",
    "Copa América": "Copa América",
    "AFC Asian Cup": "AFC Asian Cup",
    "African Cup of Nations": "African Cup of Nations",
}
ALL_MAJOR_GROUP = "All Major Tournaments"

CALIBRATED_ELO_V3 = {
    "model": "calibrated_elo_v3_candidate",
    "k_factor": 80.0,
    "goal_diff_shrinkage_alpha": 0.10,
}
ASYMMETRIC_XG = {
    "formula": "current_asymmetric",
    "base_home": 1.50,
    "base_away": 1.10,
    "c1": 1.00,
    "scale": 450.0,
    "min_xg": MIN_XG,
}
SYMMETRIC_XG = {
    "formula": "neutral_symmetric",
    "base": 1.30,
    "c1": 1.00,
    "scale": 450.0,
    "min_xg": MIN_XG,
}

REPORT_COLUMNS = [
    "tournament_group",
    "formula",
    "matches",
    "neutral_matches",
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


def asymmetric_xg(home_elo: float, away_elo: float) -> tuple[float, float]:
    return elo_only_expected_goals(
        home_elo,
        away_elo,
        c1=float(ASYMMETRIC_XG["c1"]),
        base_home=float(ASYMMETRIC_XG["base_home"]),
        base_away=float(ASYMMETRIC_XG["base_away"]),
        min_xg=float(ASYMMETRIC_XG["min_xg"]),
    )


def symmetric_xg(team_a_elo: float, team_b_elo: float) -> tuple[float, float]:
    elo_diff = team_a_elo - team_b_elo
    adjustment = float(SYMMETRIC_XG["c1"]) * elo_diff / float(SYMMETRIC_XG["scale"])
    base = float(SYMMETRIC_XG["base"])
    min_xg = float(SYMMETRIC_XG["min_xg"])
    return max(min_xg, base + adjustment), max(min_xg, base - adjustment)


def filter_tournament_rows(rows: list[dict[str, Any]], tournament: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row["tournament"]) == tournament]


def is_neutral(row: dict[str, Any]) -> bool:
    return str(row.get("neutral", "")).strip().upper() == "TRUE"


def evaluate_rows(
    rows: list[dict[str, Any]],
    tournament_group: str,
    formula_name: str,
    xg_fn: Callable[[float, float], tuple[float, float]],
) -> dict[str, Any]:
    if not rows:
        raise ValueError(f"at least one row is required for {tournament_group!r}")

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
        team_a_xg, team_b_xg = xg_fn(
            float(row["home_pre_match_elo"]),
            float(row["away_pre_match_elo"]),
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

    predicted_avg_a = statistics.mean(predicted_a)
    predicted_avg_b = statistics.mean(predicted_b)
    actual_avg_a = statistics.mean(actual_a)
    actual_avg_b = statistics.mean(actual_b)
    return {
        "tournament_group": tournament_group,
        "formula": formula_name,
        "matches": len(rows),
        "neutral_matches": sum(1 for row in rows if is_neutral(row)),
        "team_a_goal_mae": statistics.mean(team_a_errors),
        "team_b_goal_mae": statistics.mean(team_b_errors),
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
    }


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_group: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_group.setdefault(str(row["tournament_group"]), {})[str(row["formula"])] = row

    comparisons: dict[str, Any] = {}
    for group, formulas in by_group.items():
        asymmetric = formulas["current_asymmetric"]
        symmetric = formulas["neutral_symmetric"]
        comparisons[group] = {
            "symmetric_minus_asymmetric_log_loss": float(symmetric["poisson_log_loss"])
            - float(asymmetric["poisson_log_loss"]),
            "symmetric_minus_asymmetric_brier": float(symmetric["brier_score"])
            - float(asymmetric["brier_score"]),
            "symmetric_minus_asymmetric_total_goals_mae": float(symmetric["total_goals_mae"])
            - float(asymmetric["total_goals_mae"]),
            "symmetric_better_log_loss": float(symmetric["poisson_log_loss"])
            < float(asymmetric["poisson_log_loss"]),
            "symmetric_better_brier": float(symmetric["brier_score"]) < float(asymmetric["brier_score"]),
            "symmetric_better_total_goals_mae": float(symmetric["total_goals_mae"])
            < float(asymmetric["total_goals_mae"]),
        }

    all_major = by_group[ALL_MAJOR_GROUP]
    recommendation_formula = min(
        all_major.values(),
        key=lambda row: float(row["poisson_log_loss"]),
    )
    return {
        "formula_comparisons": comparisons,
        "best_all_major_poisson_log_loss": recommendation_formula,
        "best_all_major_brier_score": min(
            all_major.values(),
            key=lambda row: float(row["brier_score"]),
        ),
        "best_all_major_total_goals_mae": min(
            all_major.values(),
            key=lambda row: float(row["total_goals_mae"]),
        ),
        "recommended_worldcup_xg_direction": {
            "formula": recommendation_formula["formula"],
            "selection_metric": "poisson_log_loss",
            "reason": (
                "This benchmark compares the all-match asymmetric xG candidate against a neutral "
                "symmetric variant on major tournaments using calibrated Elo v3."
            ),
        },
    }


def build_neutral_xg_benchmark(
    input_path: Path,
    team_universe_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = read_match_rows(input_path)
    matches = parse_match_rows(source_rows, skip_unplayed=True)
    team_universe = read_team_universe(team_universe_path)
    universe_matches = filter_matches_for_universe(matches, team_universe)
    if not universe_matches:
        raise ValueError("no matches remain after FIFA+historical universe filtering")
    rebuilt_rows = rebuild_calibrated_v3(universe_matches)

    major_rows: list[dict[str, Any]] = []
    report_rows: list[dict[str, Any]] = []
    formula_fns = {
        "current_asymmetric": asymmetric_xg,
        "neutral_symmetric": symmetric_xg,
    }

    for group, tournament in TOURNAMENT_GROUPS.items():
        tournament_rows = filter_tournament_rows(rebuilt_rows, tournament)
        if not tournament_rows:
            raise ValueError(f"no rows for tournament group {group!r}")
        major_rows.extend(tournament_rows)
        for formula_name, xg_fn in formula_fns.items():
            report_rows.append(evaluate_rows(tournament_rows, group, formula_name, xg_fn))

    for formula_name, xg_fn in formula_fns.items():
        report_rows.append(evaluate_rows(major_rows, ALL_MAJOR_GROUP, formula_name, xg_fn))

    payload = {
        "elo_source": CALIBRATED_ELO_V3,
        "universe": {
            "name": "fifa_historical",
            "label": "FIFA + historical national teams",
            "source_matches": len(matches),
            "universe_matches": len(universe_matches),
        },
        "tournament_groups": TOURNAMENT_GROUPS,
        "formulas": {
            "current_asymmetric": ASYMMETRIC_XG,
            "neutral_symmetric": SYMMETRIC_XG,
        },
        "formal_model_formulas_unchanged": True,
        "rows": report_rows,
        "summary": build_summary(report_rows),
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
    parser = argparse.ArgumentParser(description="Benchmark asymmetric versus neutral xG on major tournaments.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/neutral_xg_benchmark.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/neutral_xg_benchmark.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = build_neutral_xg_benchmark(args.input, args.team_universe)
    write_outputs(rows, payload, args.output_csv, args.output_json)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    for row in rows:
        print(
            f"{row['tournament_group']} | {row['formula']} | "
            f"matches={row['matches']} "
            f"log_loss={float(row['poisson_log_loss']):.6f} "
            f"brier={float(row['brier_score']):.6f} "
            f"total_mae={float(row['total_goals_mae']):.6f} "
            f"pred_total={float(row['predicted_avg_total_goals']):.6f}"
        )
    print(
        "recommended_worldcup_xg_direction: "
        f"{payload['summary']['recommended_worldcup_xg_direction']['formula']}"
    )


if __name__ == "__main__":
    main()
