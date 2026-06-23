from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model.elo_rebuilder import MODEL_VERSION, parse_match_rows, rebuild_elo_history
from src.tuning.evaluation import evaluate_rebuilt_elo_rows, rank_metric_rows

DEFAULT_K_FACTORS = (10.0, 15.0, 20.0, 25.0, 30.0, 40.0)
OUTPUT_COLUMNS = ["k_factor", "accuracy", "log_loss", "brier_score"]


def read_match_rows(path: Path) -> list[dict[str, str]]:
    return pd.read_csv(path, dtype=str).fillna("").to_dict(orient="records")


def tune_k_factors(
    input_path: Path,
    k_factors: tuple[float, ...] = DEFAULT_K_FACTORS,
) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    source_rows = read_match_rows(input_path)
    matches = parse_match_rows(source_rows, skip_unplayed=True)
    if not matches:
        raise ValueError(f"{input_path} contains no completed match rows")

    metric_rows: list[dict[str, float]] = []
    for k_factor in k_factors:
        rebuilt_rows = rebuild_elo_history(
            matches,
            k_factor=k_factor,
            model_version=f"{MODEL_VERSION}_k_{k_factor:g}",
        )
        metrics = evaluate_rebuilt_elo_rows(rebuilt_rows)
        metric_rows.append(
            {
                "k_factor": float(k_factor),
                "accuracy": metrics["accuracy"],
                "log_loss": metrics["log_loss"],
                "brier_score": metrics["brier_score"],
            }
        )

    frame = pd.DataFrame(metric_rows, columns=OUTPUT_COLUMNS)
    summary = rank_metric_rows(metric_rows)
    return frame, summary


def write_outputs(
    frame: pd.DataFrame,
    summary: dict[str, dict[str, float]],
    csv_path: Path,
    json_path: Path,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)
    payload: dict[str, Any] = {
        "results": frame.to_dict(orient="records"),
        "summary": summary,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_k_factors(values: list[str] | None) -> tuple[float, ...]:
    if not values:
        return DEFAULT_K_FACTORS
    parsed = tuple(float(value) for value in values)
    if not parsed:
        raise ValueError("at least one K factor is required")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tune standard Elo K factor.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/matches_with_elo.csv"),
        help="Input processed matches CSV. Only date/team/score columns are used for rebuilding.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/k_factor_results.csv"),
        help="Output CSV path for K-factor metrics.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/k_factor_results.json"),
        help="Output JSON path for visualization and ranking summary.",
    )
    parser.add_argument(
        "--k-factor",
        action="append",
        help="Candidate K factor. Repeat to pass multiple values. Defaults to 10,15,20,25,30,40.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame, summary = tune_k_factors(args.input, parse_k_factors(args.k_factor))
    write_outputs(frame, summary, args.output_csv, args.output_json)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    print(frame.to_string(index=False))
    print(
        "best_accuracy: "
        f"K={summary['best_accuracy']['k_factor']:g}, "
        f"accuracy={summary['best_accuracy']['accuracy']:.6f}"
    )
    print(
        "best_log_loss: "
        f"K={summary['best_log_loss']['k_factor']:g}, "
        f"log_loss={summary['best_log_loss']['log_loss']:.6f}"
    )
    print(
        "best_brier_score: "
        f"K={summary['best_brier_score']['k_factor']:g}, "
        f"brier_score={summary['best_brier_score']['brier_score']:.6f}"
    )


if __name__ == "__main__":
    main()
