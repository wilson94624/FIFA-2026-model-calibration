from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model.elo_rebuilder import MatchInput, parse_match_rows, rebuild_elo_history
from src.tuning.elo_benchmark_report import CALIBRATED_MODEL, STANDARD_MODEL
from src.tuning.evaluation import evaluate_rebuilt_elo_rows
from src.tuning.time_split_validation import (
    distribution,
    filter_matches_for_universe,
    final_team_ratings,
    ranking,
    split_rows,
)
from src.tuning.tune_gd_shrinkage import gd_shrinkage_multiplier
from src.tuning.tune_k_factor import read_match_rows
from src.tuning.universe_benchmark import read_team_universe

SHRINKAGE_ALPHAS = (0.10, 0.20, 0.25, 0.30, 0.40, 0.50)
TRACKED_TEAMS = ("Argentina", "Spain", "France", "Norway", "Brazil")
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
    *(
        {
            "model": f"calibrated_elo_v3_shrinkage_alpha_{alpha:g}",
            "k_factor": 80.0,
            "gd_variant": "log_margin_shrinkage",
            "alpha": alpha,
        }
        for alpha in SHRINKAGE_ALPHAS
    ),
)

REPORT_COLUMNS = [
    "model",
    "k_factor",
    "gd_variant",
    "alpha",
    "train_matches",
    "validation_matches",
    "accuracy",
    "log_loss",
    "brier_score",
    "elo_min",
    "elo_max",
    "elo_std",
    "norway_rank",
    "norway_elo",
    "argentina_elo",
    "spain_elo",
    "france_elo",
    "brazil_elo",
    "log_loss_improvement_vs_standard",
    "brier_improvement_vs_standard",
    "log_loss_retention_vs_v2",
    "brier_retention_vs_v2",
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


def tracked_team_values(
    rank_rows: list[dict[str, float | int | str]],
) -> dict[str, dict[str, float | int | None]]:
    by_team = {str(row["team"]): row for row in rank_rows}
    result: dict[str, dict[str, float | int | None]] = {}
    for team in TRACKED_TEAMS:
        row = by_team.get(team)
        result[team] = {
            "rank": int(row["rank"]) if row else None,
            "final_elo": float(row["final_elo"]) if row else None,
            "matches": int(row["matches"]) if row else None,
        }
    return result


def row_for_config(
    config: dict[str, Any],
    rebuilt_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    train_rows, validation_rows = split_rows(rebuilt_rows)
    if not train_rows:
        raise ValueError(f"{config['model']} has no train rows")
    if not validation_rows:
        raise ValueError(f"{config['model']} has no validation rows")

    metrics = evaluate_rebuilt_elo_rows(validation_rows)
    teams = final_team_ratings(rebuilt_rows)
    dist = distribution(teams)
    rank_rows = ranking(teams)
    tracked = tracked_team_values(rank_rows)

    row = {
        "model": config["model"],
        "k_factor": config["k_factor"],
        "gd_variant": config["gd_variant"],
        "alpha": "" if config["alpha"] is None else config["alpha"],
        "train_matches": len(train_rows),
        "validation_matches": len(validation_rows),
        "accuracy": metrics["accuracy"],
        "log_loss": metrics["log_loss"],
        "brier_score": metrics["brier_score"],
        "elo_min": dist["elo_min"],
        "elo_max": dist["elo_max"],
        "elo_std": dist["elo_std"],
        "norway_rank": tracked["Norway"]["rank"],
        "norway_elo": tracked["Norway"]["final_elo"],
        "argentina_elo": tracked["Argentina"]["final_elo"],
        "spain_elo": tracked["Spain"]["final_elo"],
        "france_elo": tracked["France"]["final_elo"],
        "brazil_elo": tracked["Brazil"]["final_elo"],
    }
    payload = {
        "config": config,
        "train_matches": len(train_rows),
        "validation_matches": len(validation_rows),
        "validation_metrics": metrics,
        "final_distribution": dist,
        "tracked_teams": tracked,
        "top20": rank_rows[:20],
    }
    return row, payload


def add_improvement_columns(rows: list[dict[str, Any]]) -> None:
    standard = next(row for row in rows if row["model"] == STANDARD_MODEL["name"])
    calibrated_v2 = next(row for row in rows if row["model"] == CALIBRATED_MODEL["name"])
    v2_log_loss_gain = float(standard["log_loss"]) - float(calibrated_v2["log_loss"])
    v2_brier_gain = float(standard["brier_score"]) - float(calibrated_v2["brier_score"])

    for row in rows:
        log_loss_gain = float(standard["log_loss"]) - float(row["log_loss"])
        brier_gain = float(standard["brier_score"]) - float(row["brier_score"])
        row["log_loss_improvement_vs_standard"] = log_loss_gain
        row["brier_improvement_vs_standard"] = brier_gain
        row["log_loss_retention_vs_v2"] = log_loss_gain / v2_log_loss_gain if v2_log_loss_gain else 0.0
        row["brier_retention_vs_v2"] = brier_gain / v2_brier_gain if v2_brier_gain else 0.0


def build_recommendation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    standard = next(row for row in rows if row["model"] == STANDARD_MODEL["name"])
    calibrated_v2 = next(row for row in rows if row["model"] == CALIBRATED_MODEL["name"])
    shrinkage_rows = [row for row in rows if str(row["gd_variant"]) == "log_margin_shrinkage"]

    best_log_loss = min(rows, key=lambda row: float(row["log_loss"]))
    best_brier = min(rows, key=lambda row: float(row["brier_score"]))
    scale_reasonable = min(
        shrinkage_rows,
        key=lambda row: (
            float(row["elo_max"]) - float(row["elo_min"]),
            float(row["elo_std"]),
        ),
    )
    retained_70 = [
        row
        for row in shrinkage_rows
        if float(row["log_loss_retention_vs_v2"]) >= 0.70
        and float(row["brier_retention_vs_v2"]) >= 0.70
    ]
    recommended = min(
        retained_70,
        key=lambda row: (
            float(row["elo_max"]) - float(row["elo_min"]),
            float(row["elo_std"]),
            float(row["log_loss"]),
        ),
    ) if retained_70 else best_log_loss

    return {
        "standard": standard,
        "calibrated_v2": calibrated_v2,
        "best_log_loss": best_log_loss,
        "best_brier_score": best_brier,
        "most_reasonable_shrinkage_scale": scale_reasonable,
        "alphas_retaining_at_least_70_percent_v2_log_loss_and_brier_gain": retained_70,
        "recommended_calibrated_elo_v3_candidate": {
            "model": recommended["model"],
            "alpha": recommended["alpha"],
            "reason": (
                "smallest Elo range/std among shrinkage candidates retaining at least 70% "
                "of v2 LogLoss and Brier gains"
                if retained_70
                else "no shrinkage candidate retained 70% of both v2 gains; fallback to best LogLoss"
            ),
        },
        "can_start_fifa_predictor_integration_planning": bool(retained_70),
        "integration_caution": (
            "planning can start around the recommended v3 candidate, but final default promotion "
            "should wait for tournament-split checks and scale policy approval"
        ),
    }


def build_time_split_shrinkage_validation(
    input_path: Path,
    team_universe_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = read_match_rows(input_path)
    matches = parse_match_rows(source_rows, skip_unplayed=True)
    team_universe = read_team_universe(team_universe_path)
    universe_matches = filter_matches_for_universe(matches, team_universe)
    if not universe_matches:
        raise ValueError("no matches remain after FIFA+historical universe filtering")

    report_rows: list[dict[str, Any]] = []
    model_payloads: dict[str, Any] = {}
    for config in MODEL_CONFIGS:
        rebuilt = rebuild_for_config(universe_matches, config)
        row, model_payload = row_for_config(config, rebuilt)
        report_rows.append(row)
        model_payloads[str(config["model"])] = model_payload

    add_improvement_columns(report_rows)
    payload = {
        "universe": {
            "name": "fifa_historical",
            "label": "FIFA + historical national teams",
            "source_matches": len(matches),
            "universe_matches": len(universe_matches),
        },
        "fixed_settings": {
            "home_advantage": 0.0,
            "tournament_weight": 1.0,
            "pqs": "disabled",
        },
        "formula": "1 + alpha * (log(goal_diff + 1) - 1); draws use 1.0",
        "rows": report_rows,
        "models": model_payloads,
        "summary": build_recommendation(report_rows),
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
    parser = argparse.ArgumentParser(description="Run time-split validation for GD shrinkage candidates.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/time_split_shrinkage_validation.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/time_split_shrinkage_validation.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = build_time_split_shrinkage_validation(args.input, args.team_universe)
    write_outputs(rows, payload, args.output_csv, args.output_json)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    print("model accuracy log_loss brier_score elo_min elo_max elo_std norway_rank")
    for row in rows:
        print(
            f"{row['model']} "
            f"{float(row['accuracy']):.6f} "
            f"{float(row['log_loss']):.6f} "
            f"{float(row['brier_score']):.6f} "
            f"{float(row['elo_min']):.3f} "
            f"{float(row['elo_max']):.3f} "
            f"{float(row['elo_std']):.3f} "
            f"{row['norway_rank']}"
        )
    recommendation = payload["summary"]["recommended_calibrated_elo_v3_candidate"]
    print(f"recommended_model: {recommendation['model']}")
    print(f"recommended_alpha: {recommendation['alpha']}")


if __name__ == "__main__":
    main()
