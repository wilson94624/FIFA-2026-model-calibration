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

from src.model.expected_goals import MIN_XG
from src.tuning.worldcup_xg_parameter_search import (
    ASYMMETRIC_XG,
    CALIBRATED_ELO_V3,
    TARGET_TOURNAMENTS,
    evaluate_rows,
    load_target_rows,
)

BASE_VALUES = (1.35, 1.40, 1.45, 1.50)
C1_VALUES = (1.00, 1.10, 1.20, 1.25, 1.30)
SCALE_VALUES = (500.0, 550.0, 600.0)

SPLITS = {
    "world_cup": "FIFA World Cup",
    "euro": "UEFA Euro",
    "pooled": None,
}

REPORT_COLUMNS = [
    "base",
    "c1",
    "scale",
    "world_cup_matches",
    "euro_matches",
    "pooled_matches",
    "world_cup_log_loss",
    "euro_log_loss",
    "pooled_log_loss",
    "world_cup_brier_score",
    "euro_brier_score",
    "pooled_brier_score",
    "world_cup_goal_difference_mae",
    "euro_goal_difference_mae",
    "pooled_goal_difference_mae",
    "world_cup_predicted_avg_total_goals",
    "euro_predicted_avg_total_goals",
    "pooled_predicted_avg_total_goals",
    "world_cup_actual_avg_total_goals",
    "euro_actual_avg_total_goals",
    "pooled_actual_avg_total_goals",
    "world_cup_total_goal_error",
    "euro_total_goal_error",
    "pooled_total_goal_error",
    "world_cup_abs_total_goal_error",
    "euro_abs_total_goal_error",
    "pooled_abs_total_goal_error",
]


def rows_for_tournament(rows: list[dict[str, Any]], tournament: str | None) -> list[dict[str, Any]]:
    if tournament is None:
        return rows
    return [row for row in rows if str(row["tournament"]) == tournament]


def flatten_metrics(prefix: str, metrics: dict[str, Any]) -> dict[str, Any]:
    total_error = float(metrics["predicted_minus_actual_total_goals"])
    return {
        f"{prefix}_matches": metrics["matches"],
        f"{prefix}_log_loss": metrics["poisson_log_loss"],
        f"{prefix}_brier_score": metrics["brier_score"],
        f"{prefix}_goal_difference_mae": metrics["goal_difference_mae"],
        f"{prefix}_predicted_avg_total_goals": metrics["predicted_avg_total_goals"],
        f"{prefix}_actual_avg_total_goals": metrics["actual_avg_total_goals"],
        f"{prefix}_total_goal_error": total_error,
        f"{prefix}_abs_total_goal_error": abs(total_error),
    }


def evaluate_config_by_split(
    target_rows: list[dict[str, Any]],
    config: dict[str, float],
) -> dict[str, Any]:
    row: dict[str, Any] = {**config}
    for prefix, tournament in SPLITS.items():
        split_rows = rows_for_tournament(target_rows, tournament)
        if not split_rows:
            raise ValueError(f"no rows found for split {prefix!r}")
        row.update(flatten_metrics(prefix, evaluate_rows(split_rows, xg_config=config)))
    return row


def build_asymmetric_baseline(target_rows: list[dict[str, Any]]) -> dict[str, Any]:
    row: dict[str, Any] = {"formula": "current_asymmetric_xg", **ASYMMETRIC_XG}
    for prefix, tournament in SPLITS.items():
        split_rows = rows_for_tournament(target_rows, tournament)
        if not split_rows:
            raise ValueError(f"no rows found for split {prefix!r}")
        row.update(flatten_metrics(prefix, evaluate_rows(split_rows, use_asymmetric=True)))
    return row


def build_summary(rows: list[dict[str, Any]], asymmetric_baseline: dict[str, Any]) -> dict[str, Any]:
    best_world_cup_log_loss = min(rows, key=lambda row: float(row["world_cup_log_loss"]))
    best_euro_log_loss = min(rows, key=lambda row: float(row["euro_log_loss"]))
    best_pooled_log_loss = min(rows, key=lambda row: float(row["pooled_log_loss"]))
    best_pooled_brier = min(rows, key=lambda row: float(row["pooled_brier_score"]))
    best_pooled_goal_difference = min(
        rows,
        key=lambda row: float(row["pooled_goal_difference_mae"]),
    )
    best_euro_total_balance = min(rows, key=lambda row: float(row["euro_abs_total_goal_error"]))
    euro_under_030 = [row for row in rows if float(row["euro_abs_total_goal_error"]) < 0.30]
    balanced_under_030 = min(
        euro_under_030,
        key=lambda row: float(row["pooled_log_loss"]),
        default=None,
    )

    return {
        "current_asymmetric_baseline": asymmetric_baseline,
        "best_world_cup_log_loss": best_world_cup_log_loss,
        "best_euro_log_loss": best_euro_log_loss,
        "best_pooled_log_loss": best_pooled_log_loss,
        "best_pooled_brier_score": best_pooled_brier,
        "best_pooled_goal_difference_mae": best_pooled_goal_difference,
        "best_euro_total_goal_balance": best_euro_total_balance,
        "best_pooled_log_loss_with_euro_total_error_under_0_30": balanced_under_030,
        "euro_total_error_under_0_30_count": len(euro_under_030),
        "best_pooled_log_loss_vs_asymmetric": {
            "world_cup_log_loss_delta": float(asymmetric_baseline["world_cup_log_loss"])
            - float(best_pooled_log_loss["world_cup_log_loss"]),
            "euro_log_loss_delta": float(asymmetric_baseline["euro_log_loss"])
            - float(best_pooled_log_loss["euro_log_loss"]),
            "pooled_log_loss_delta": float(asymmetric_baseline["pooled_log_loss"])
            - float(best_pooled_log_loss["pooled_log_loss"]),
            "pooled_brier_delta": float(asymmetric_baseline["pooled_brier_score"])
            - float(best_pooled_log_loss["pooled_brier_score"]),
        },
        "recommended_neutral_worldcup_xg_candidate": {
            "base": best_pooled_log_loss["base"],
            "c1": best_pooled_log_loss["c1"],
            "scale": best_pooled_log_loss["scale"],
            "selection_metric": "pooled_poisson_log_loss",
        },
    }


def search_worldcup_xg_fine_parameters(
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
                rows.append(
                    evaluate_config_by_split(
                        target_rows,
                        {"base": base, "c1": c1, "scale": scale},
                    )
                )

    asymmetric_baseline = build_asymmetric_baseline(target_rows)
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
    parser = argparse.ArgumentParser(description="Fine search neutral World Cup/Euro xG parameters.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/worldcup_xg_fine_search.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/worldcup_xg_fine_search.json"),
    )
    parser.add_argument("--base", action="append", help="Candidate neutral base value.")
    parser.add_argument("--c1", action="append", help="Candidate c1 value.")
    parser.add_argument("--scale", action="append", help="Candidate Elo scale value.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = search_worldcup_xg_fine_parameters(
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
    for key in (
        "best_world_cup_log_loss",
        "best_euro_log_loss",
        "best_pooled_log_loss",
        "best_pooled_log_loss_with_euro_total_error_under_0_30",
    ):
        row = payload["summary"][key]
        if row is None:
            print(f"{key}: none")
            continue
        print(
            f"{key}: base={float(row['base']):.2f} "
            f"c1={float(row['c1']):.2f} "
            f"scale={float(row['scale']):.0f} "
            f"wc_log_loss={float(row['world_cup_log_loss']):.6f} "
            f"euro_log_loss={float(row['euro_log_loss']):.6f} "
            f"pooled_log_loss={float(row['pooled_log_loss']):.6f} "
            f"pooled_brier={float(row['pooled_brier_score']):.6f} "
            f"euro_total_error={float(row['euro_total_goal_error']):.6f}"
        )


if __name__ == "__main__":
    main()
