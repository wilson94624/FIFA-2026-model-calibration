from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.tuning.worldcup_xg_parameter_search import (
    ASYMMETRIC_XG,
    CALIBRATED_ELO_V3,
    TARGET_TOURNAMENTS,
    evaluate_rows,
    load_target_rows,
)

NEUTRAL_WORLDCUP_XG_V1 = {
    "formula": "neutral_xg_worldcup_v1_candidate",
    "base": 1.50,
    "c1": 1.25,
    "scale": 550.0,
}
SPLITS = {
    "FIFA World Cup neutral": "FIFA World Cup",
    "UEFA Euro neutral": "UEFA Euro",
    "World Cup + Euro neutral": None,
}

REPORT_COLUMNS = [
    "split",
    "formula",
    "matches",
    "goal_mae",
    "team_a_goal_mae",
    "team_b_goal_mae",
    "total_goals_mae",
    "goal_difference_mae",
    "poisson_log_loss",
    "brier_score",
    "predicted_avg_total_goals",
    "actual_avg_total_goals",
    "predicted_avg_home_or_team_a_goals",
    "predicted_avg_away_or_team_b_goals",
    "actual_avg_home_or_team_a_goals",
    "actual_avg_away_or_team_b_goals",
    "predicted_minus_actual_total_goals",
]


def rows_for_split(rows: list[dict[str, Any]], tournament: str | None) -> list[dict[str, Any]]:
    if tournament is None:
        return rows
    return [row for row in rows if str(row["tournament"]) == tournament]


def metric_row(split: str, formula: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "split": split,
        "formula": formula,
        "matches": metrics["matches"],
        "goal_mae": metrics["goal_mae"],
        "team_a_goal_mae": metrics["team_a_goal_mae"],
        "team_b_goal_mae": metrics["team_b_goal_mae"],
        "total_goals_mae": metrics["total_goals_mae"],
        "goal_difference_mae": metrics["goal_difference_mae"],
        "poisson_log_loss": metrics["poisson_log_loss"],
        "brier_score": metrics["brier_score"],
        "predicted_avg_total_goals": metrics["predicted_avg_total_goals"],
        "actual_avg_total_goals": metrics["actual_avg_total_goals"],
        "predicted_avg_home_or_team_a_goals": metrics["predicted_avg_team_a_goals"],
        "predicted_avg_away_or_team_b_goals": metrics["predicted_avg_team_b_goals"],
        "actual_avg_home_or_team_a_goals": metrics["actual_avg_team_a_goals"],
        "actual_avg_away_or_team_b_goals": metrics["actual_avg_team_b_goals"],
        "predicted_minus_actual_total_goals": metrics["predicted_minus_actual_total_goals"],
    }


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_split: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_split.setdefault(str(row["split"]), {})[str(row["formula"])] = row

    comparisons: dict[str, Any] = {}
    for split, formulas in by_split.items():
        asymmetric = formulas["current_asymmetric_xg"]
        neutral = formulas["neutral_xg_worldcup_v1_candidate"]
        comparisons[split] = {
            "log_loss_delta": float(asymmetric["poisson_log_loss"]) - float(neutral["poisson_log_loss"]),
            "brier_delta": float(asymmetric["brier_score"]) - float(neutral["brier_score"]),
            "goal_difference_mae_delta": float(asymmetric["goal_difference_mae"])
            - float(neutral["goal_difference_mae"]),
            "total_goals_mae_delta": float(asymmetric["total_goals_mae"])
            - float(neutral["total_goals_mae"]),
            "neutral_better_log_loss": float(neutral["poisson_log_loss"])
            < float(asymmetric["poisson_log_loss"]),
            "neutral_better_brier": float(neutral["brier_score"]) < float(asymmetric["brier_score"]),
            "neutral_predicted_total_minus_actual": float(neutral["predicted_minus_actual_total_goals"]),
            "asymmetric_predicted_total_minus_actual": float(
                asymmetric["predicted_minus_actual_total_goals"]
            ),
        }

    pooled = comparisons["World Cup + Euro neutral"]
    return {
        "comparisons": comparisons,
        "neutral_better_on_all_splits": {
            "log_loss": all(item["neutral_better_log_loss"] for item in comparisons.values()),
            "brier_score": all(item["neutral_better_brier"] for item in comparisons.values()),
        },
        "pooled_recommendation": {
            "formula": (
                "neutral_xg_worldcup_v1_candidate"
                if pooled["neutral_better_log_loss"] and pooled["neutral_better_brier"]
                else "current_asymmetric_xg"
            ),
            "selection_metric": "poisson_log_loss_and_brier_score",
        },
    }


def build_worldcup_euro_xg_split_validation(
    input_path: Path,
    team_universe_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target_rows, source_summary = load_target_rows(input_path, team_universe_path)
    report_rows: list[dict[str, Any]] = []

    for split, tournament in SPLITS.items():
        split_rows = rows_for_split(target_rows, tournament)
        if not split_rows:
            raise ValueError(f"no rows found for split {split!r}")
        asymmetric_metrics = evaluate_rows(split_rows, use_asymmetric=True)
        neutral_metrics = evaluate_rows(split_rows, xg_config=NEUTRAL_WORLDCUP_XG_V1)
        report_rows.append(metric_row(split, "current_asymmetric_xg", asymmetric_metrics))
        report_rows.append(
            metric_row(split, "neutral_xg_worldcup_v1_candidate", neutral_metrics)
        )

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
        "formulas": {
            "current_asymmetric_xg": ASYMMETRIC_XG,
            "neutral_xg_worldcup_v1_candidate": NEUTRAL_WORLDCUP_XG_V1,
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
    parser = argparse.ArgumentParser(description="Validate World Cup/Euro neutral xG splits.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/worldcup_euro_xg_split_validation.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/worldcup_euro_xg_split_validation.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = build_worldcup_euro_xg_split_validation(args.input, args.team_universe)
    write_outputs(rows, payload, args.output_csv, args.output_json)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    for row in rows:
        print(
            f"{row['split']} | {row['formula']} | "
            f"matches={row['matches']} "
            f"log_loss={float(row['poisson_log_loss']):.6f} "
            f"brier={float(row['brier_score']):.6f} "
            f"total_mae={float(row['total_goals_mae']):.6f} "
            f"pred_total={float(row['predicted_avg_total_goals']):.6f}"
        )
    print(f"pooled_recommendation: {payload['summary']['pooled_recommendation']['formula']}")


if __name__ == "__main__":
    main()
