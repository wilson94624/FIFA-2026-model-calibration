from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from datetime import date
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model.elo_rebuilder import MatchInput, parse_match_date, parse_match_rows, rebuild_elo_history
from src.tuning.elo_benchmark_report import CALIBRATED_MODEL, STANDARD_MODEL
from src.tuning.evaluation import evaluate_rebuilt_elo_rows
from src.tuning.tune_goal_diff_multiplier import goal_diff_multiplier
from src.tuning.tune_k_factor import read_match_rows
from src.tuning.universe_benchmark import read_team_universe, team_allowed

TRAIN_START = date(1872, 1, 1)
TRAIN_END = date(2023, 12, 31)
VALIDATION_START = date(2024, 1, 1)
UNIVERSE = "fifa_historical"

REPORT_COLUMNS = [
    "model",
    "train_matches",
    "validation_matches",
    "accuracy",
    "log_loss",
    "brier_score",
    "train_accuracy",
    "train_log_loss",
    "train_brier_score",
    "final_team_count",
    "elo_std",
    "elo_min",
    "elo_max",
    "norway_rank",
    "norway_final_elo",
]


def filter_matches_for_universe(
    matches: list[MatchInput],
    team_universe: dict[str, dict[str, str]],
    universe: str = UNIVERSE,
) -> list[MatchInput]:
    return [
        match
        for match in matches
        if team_allowed(match.home_team, universe, team_universe)
        and team_allowed(match.away_team, universe, team_universe)
    ]


def rebuild_for_model(matches: list[MatchInput], model: dict[str, str | float]) -> list[dict[str, Any]]:
    variant = str(model["goal_diff_variant"])
    goal_diff_fn = None if variant == "none" else goal_diff_multiplier(variant)
    return rebuild_elo_history(
        matches,
        k_factor=float(model["k_factor"]),
        goal_diff_multiplier_fn=goal_diff_fn,
        model_version=str(model["name"]),
    )


def split_rows(
    rows: list[dict[str, Any]],
    train_start: date = TRAIN_START,
    train_end: date = TRAIN_END,
    validation_start: date = VALIDATION_START,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    for row in rows:
        match_date = parse_match_date(str(row["date"]))
        if train_start <= match_date <= train_end:
            train_rows.append(row)
        elif match_date >= validation_start:
            validation_rows.append(row)
    return train_rows, validation_rows


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


def distribution(teams: dict[str, dict[str, float | int]]) -> dict[str, float]:
    ratings = [float(values["final_elo"]) for values in teams.values()]
    if not ratings:
        raise ValueError("cannot summarize empty final team ratings")
    return {
        "final_team_count": float(len(ratings)),
        "elo_mean": statistics.mean(ratings),
        "elo_median": statistics.median(ratings),
        "elo_std": statistics.pstdev(ratings),
        "elo_min": min(ratings),
        "elo_max": max(ratings),
    }


def norway_summary(rankings: list[dict[str, float | int | str]]) -> dict[str, float | int | None]:
    for row in rankings:
        if row["team"] == "Norway":
            return {
                "rank": int(row["rank"]),
                "final_elo": float(row["final_elo"]),
                "matches": int(row["matches"]),
            }
    return {"rank": None, "final_elo": None, "matches": None}


def metric_payload(rows: list[dict[str, Any]]) -> dict[str, float]:
    return evaluate_rebuilt_elo_rows(rows)


def model_report_row(
    model_name: str,
    train_rows: list[dict[str, Any]],
    validation_rows: list[dict[str, Any]],
    full_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    train_metrics = metric_payload(train_rows)
    validation_metrics = metric_payload(validation_rows)
    teams = final_team_ratings(full_rows)
    dist = distribution(teams)
    ranks = ranking(teams)
    norway = norway_summary(ranks)
    row = {
        "model": model_name,
        "train_matches": len(train_rows),
        "validation_matches": len(validation_rows),
        "accuracy": validation_metrics["accuracy"],
        "log_loss": validation_metrics["log_loss"],
        "brier_score": validation_metrics["brier_score"],
        "train_accuracy": train_metrics["accuracy"],
        "train_log_loss": train_metrics["log_loss"],
        "train_brier_score": train_metrics["brier_score"],
        "final_team_count": dist["final_team_count"],
        "elo_std": dist["elo_std"],
        "elo_min": dist["elo_min"],
        "elo_max": dist["elo_max"],
        "norway_rank": norway["rank"],
        "norway_final_elo": norway["final_elo"],
    }
    payload = {
        "train_matches": len(train_rows),
        "validation_matches": len(validation_rows),
        "train_metrics": train_metrics,
        "validation_metrics": validation_metrics,
        "final_distribution": dist,
        "norway": norway,
        "top20": ranks[:20],
    }
    return row, payload


def build_time_split_validation(
    input_path: Path,
    team_universe_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = read_match_rows(input_path)
    matches = parse_match_rows(source_rows, skip_unplayed=True)
    team_universe = read_team_universe(team_universe_path)
    universe_matches = filter_matches_for_universe(matches, team_universe)
    if not universe_matches:
        raise ValueError("no matches remain after FIFA+historical universe filtering")

    model_configs = (STANDARD_MODEL, CALIBRATED_MODEL)
    report_rows: list[dict[str, Any]] = []
    model_payloads: dict[str, Any] = {}
    for model in model_configs:
        rebuilt = rebuild_for_model(universe_matches, model)
        train_rows, validation_rows = split_rows(rebuilt)
        if not train_rows:
            raise ValueError(f"{model['name']} has no train rows")
        if not validation_rows:
            raise ValueError(f"{model['name']} has no validation rows")
        row, model_payload = model_report_row(
            str(model["name"]),
            train_rows,
            validation_rows,
            rebuilt,
        )
        report_rows.append(row)
        model_payloads[str(model["name"])] = {
            "config": model,
            **model_payload,
        }

    standard_row = next(row for row in report_rows if row["model"] == STANDARD_MODEL["name"])
    calibrated_row = next(row for row in report_rows if row["model"] == CALIBRATED_MODEL["name"])
    deltas = {
        "accuracy_delta": float(calibrated_row["accuracy"]) - float(standard_row["accuracy"]),
        "log_loss_delta": float(standard_row["log_loss"]) - float(calibrated_row["log_loss"]),
        "brier_delta": float(standard_row["brier_score"]) - float(calibrated_row["brier_score"]),
        "elo_std_delta": float(calibrated_row["elo_std"]) - float(standard_row["elo_std"]),
        "elo_max_delta": float(calibrated_row["elo_max"]) - float(standard_row["elo_max"]),
        "elo_min_delta": float(calibrated_row["elo_min"]) - float(standard_row["elo_min"]),
    }

    calibrated_norway_rank = calibrated_row["norway_rank"]
    calibrated_elo_max = float(calibrated_row["elo_max"])
    calibrated_elo_min = float(calibrated_row["elo_min"])
    payload = {
        "split": {
            "train_start": TRAIN_START.isoformat(),
            "train_end": TRAIN_END.isoformat(),
            "validation_start": VALIDATION_START.isoformat(),
        },
        "universe": {
            "name": UNIVERSE,
            "label": "FIFA + historical national teams",
            "source_matches": len(matches),
            "universe_matches": len(universe_matches),
        },
        "rows": report_rows,
        "models": model_payloads,
        "validation_improvement": deltas,
        "analysis": {
            "calibrated_validation_better_than_standard": {
                "accuracy": deltas["accuracy_delta"] > 0,
                "log_loss": deltas["log_loss_delta"] > 0,
                "brier_score": deltas["brier_delta"] > 0,
            },
            "norway_still_high": (
                calibrated_norway_rank is not None and int(calibrated_norway_rank) <= 10
            ),
            "elo_scale_still_expanded": calibrated_elo_max > 2200 or calibrated_elo_min < 800,
            "recommendation": {
                "verdict": "B",
                "label": "do_not_promote_v2_without_shrinkage",
                "reason": (
                    "time-split validation must improve validation LogLoss/Brier without preserving "
                    "the extreme final Elo scale before this candidate becomes a FIFA Predictor default"
                ),
            },
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
    parser = argparse.ArgumentParser(description="Run FIFA+historical time-split Elo validation.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/time_split_validation.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/time_split_validation.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = build_time_split_validation(args.input, args.team_universe)
    write_outputs(rows, payload, args.output_csv, args.output_json)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    for row in rows:
        print(
            f"{row['model']} train_matches={row['train_matches']} "
            f"validation_matches={row['validation_matches']} "
            f"accuracy={float(row['accuracy']):.6f} "
            f"log_loss={float(row['log_loss']):.6f} "
            f"brier_score={float(row['brier_score']):.6f} "
            f"elo_min={float(row['elo_min']):.3f} "
            f"elo_max={float(row['elo_max']):.3f} "
            f"norway_rank={row['norway_rank']}"
        )
    improvement = payload["validation_improvement"]
    print(
        "validation_delta "
        f"accuracy={improvement['accuracy_delta']:.6f} "
        f"log_loss={improvement['log_loss_delta']:.6f} "
        f"brier={improvement['brier_delta']:.6f}"
    )


if __name__ == "__main__":
    main()
