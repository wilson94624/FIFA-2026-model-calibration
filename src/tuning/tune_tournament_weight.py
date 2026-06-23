from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model.elo_rebuilder import MODEL_VERSION, parse_match_rows, rebuild_elo_history
from src.tuning.evaluation import evaluate_rebuilt_elo_rows
from src.tuning.tournament_taxonomy import (
    TOURNAMENT_CATEGORIES,
    category_counts,
    tournament_category,
    weight_for_tournament,
)
from src.tuning.tune_k_factor import read_match_rows

FIXED_K_FACTOR = 80.0
DEFAULT_WEIGHTS = {
    "Friendly": 1.0,
    "Qualifier": 1.5,
    "Nations League": 1.25,
    "Continental Finals": 2.0,
    "World Cup Finals": 2.5,
    "Other": 1.0,
}

GRID_OUTPUT_COLUMNS = [
    "qualifier_weight",
    "continental_finals_weight",
    "world_cup_finals_weight",
    "accuracy",
    "log_loss",
    "brier_score",
]

DEFAULT_QUALIFIER_GRID = (1.0, 1.25, 1.5)
DEFAULT_CONTINENTAL_FINALS_GRID = (1.0, 1.25, 1.5, 2.0)
DEFAULT_WORLD_CUP_FINALS_GRID = (1.0, 1.25, 1.5, 2.0)


def tournament_frequency(rows: list[dict[str, str]], limit: int = 50) -> list[dict[str, Any]]:
    counts = Counter(row.get("tournament", "") for row in rows)
    return [
        {
            "tournament": tournament,
            "matches": count,
            "category": tournament_category(tournament),
        }
        for tournament, count in counts.most_common(limit)
    ]


def evaluate_tournament_weights(
    input_path: Path,
    weights: dict[str, float] | None = None,
    k_factor: float = FIXED_K_FACTOR,
) -> dict[str, Any]:
    selected_weights = dict(DEFAULT_WEIGHTS if weights is None else weights)
    source_rows = read_match_rows(input_path)
    matches = parse_match_rows(source_rows, skip_unplayed=True)
    if not matches:
        raise ValueError(f"{input_path} contains no completed match rows")

    rebuilt_rows = rebuild_elo_history(
        matches,
        k_factor=k_factor,
        tournament_weight_fn=lambda tournament: weight_for_tournament(tournament, selected_weights),
        model_version=f"{MODEL_VERSION}_k_{k_factor:g}_tournament_weight",
    )
    metrics = evaluate_rebuilt_elo_rows(rebuilt_rows)
    return {
        "fixed_k_factor": k_factor,
        "weights": selected_weights,
        "metrics": metrics,
        "category_counts": category_counts(match.tournament for match in matches),
        "top_tournaments": tournament_frequency(source_rows),
    }


def run_tournament_weight_grid(
    input_path: Path,
    qualifier_weights: tuple[float, ...] = DEFAULT_QUALIFIER_GRID,
    continental_finals_weights: tuple[float, ...] = DEFAULT_CONTINENTAL_FINALS_GRID,
    world_cup_finals_weights: tuple[float, ...] = DEFAULT_WORLD_CUP_FINALS_GRID,
    k_factor: float = FIXED_K_FACTOR,
) -> list[dict[str, float]]:
    source_rows = read_match_rows(input_path)
    matches = parse_match_rows(source_rows, skip_unplayed=True)
    if not matches:
        raise ValueError(f"{input_path} contains no completed match rows")

    rows: list[dict[str, float]] = []
    for qualifier, continental, world_cup in itertools.product(
        qualifier_weights,
        continental_finals_weights,
        world_cup_finals_weights,
    ):
        weights = {
            "Friendly": 1.0,
            "Qualifier": qualifier,
            "Nations League": 1.0,
            "Continental Finals": continental,
            "World Cup Finals": world_cup,
            "Other": 1.0,
        }
        rebuilt_rows = rebuild_elo_history(
            matches,
            k_factor=k_factor,
            tournament_weight_fn=lambda tournament, weight_map=weights: weight_for_tournament(
                tournament, weight_map
            ),
            model_version=f"{MODEL_VERSION}_k_{k_factor:g}_tournament_weight_grid",
        )
        metrics = evaluate_rebuilt_elo_rows(rebuilt_rows)
        rows.append(
            {
                "qualifier_weight": float(qualifier),
                "continental_finals_weight": float(continental),
                "world_cup_finals_weight": float(world_cup),
                "accuracy": metrics["accuracy"],
                "log_loss": metrics["log_loss"],
                "brier_score": metrics["brier_score"],
            }
        )
    return rows


def grid_summary(rows: list[dict[str, float]], limit: int = 10) -> dict[str, list[dict[str, float]]]:
    if not rows:
        raise ValueError("at least one grid row is required")
    return {
        "top_log_loss": sorted(rows, key=lambda row: row["log_loss"])[:limit],
        "top_brier_score": sorted(rows, key=lambda row: row["brier_score"])[:limit],
        "top_accuracy": sorted(rows, key=lambda row: row["accuracy"], reverse=True)[:limit],
    }


def write_grid_outputs(
    rows: list[dict[str, float]],
    csv_path: Path,
    json_path: Path,
    k_factor: float = FIXED_K_FACTOR,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=GRID_OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    payload: dict[str, Any] = {
        "fixed_k_factor": k_factor,
        "fixed_weights": {
            "Friendly": 1.0,
            "Nations League": 1.0,
            "Other": 1.0,
        },
        "results": rows,
        "summary": grid_summary(rows),
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_weights(values: list[str] | None) -> dict[str, float]:
    weights = dict(DEFAULT_WEIGHTS)
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"invalid weight {value!r}; expected Category=value")
        category, raw_weight = value.split("=", 1)
        category = category.strip()
        if category not in TOURNAMENT_CATEGORIES:
            raise ValueError(f"unknown category {category!r}; expected one of {TOURNAMENT_CATEGORIES}")
        weights[category] = float(raw_weight)
    return weights


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate one tournament-weight Elo configuration.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/matches_with_elo.csv"),
        help="Input processed matches CSV. Only date/team/score/tournament columns are used for rebuild.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/tournament_weight_results.json"),
        help="Output JSON path for taxonomy, weights, and metrics.",
    )
    parser.add_argument("--k-factor", type=float, default=FIXED_K_FACTOR)
    parser.add_argument(
        "--weight",
        action="append",
        help="Override category weight, e.g. 'Qualifier=1.5'. Repeat for multiple categories.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = evaluate_tournament_weights(
        args.input,
        weights=parse_weights(args.weight),
        k_factor=args.k_factor,
    )
    write_json(args.output_json, payload)

    print(f"output_json: {args.output_json}")
    print(f"fixed_k_factor: {payload['fixed_k_factor']:g}")
    print("weights:")
    for category in TOURNAMENT_CATEGORIES:
        print(f"  {category}: {payload['weights'][category]:g}")
    print("category_counts:")
    for category, count in payload["category_counts"].items():
        print(f"  {category}: {count}")
    print("metrics:")
    for name, value in payload["metrics"].items():
        print(f"  {name}: {value:.6f}")


if __name__ == "__main__":
    main()
