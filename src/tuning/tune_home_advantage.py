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
from src.tuning.tune_k_factor import read_match_rows

FIXED_K_FACTOR = 80.0
DEFAULT_HOME_ADVANTAGES = (0.0, 25.0, 50.0, 75.0, 100.0, 125.0, 150.0)
OUTPUT_COLUMNS = ["home_advantage", "accuracy", "log_loss", "brier_score"]


def tune_home_advantages(
    input_path: Path,
    home_advantages: tuple[float, ...] = DEFAULT_HOME_ADVANTAGES,
    k_factor: float = FIXED_K_FACTOR,
) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    source_rows = read_match_rows(input_path)
    matches = parse_match_rows(source_rows, skip_unplayed=True)
    if not matches:
        raise ValueError(f"{input_path} contains no completed match rows")

    rebuilt_rows = rebuild_elo_history(
        matches,
        k_factor=k_factor,
        model_version=f"{MODEL_VERSION}_k_{k_factor:g}",
    )

    metric_rows: list[dict[str, float]] = []
    for home_advantage in home_advantages:
        metrics = evaluate_rebuilt_elo_rows(
            rebuilt_rows,
            home_advantage_bonus=home_advantage,
        )
        metric_rows.append(
            {
                "home_advantage": float(home_advantage),
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
    k_factor: float = FIXED_K_FACTOR,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)
    payload: dict[str, Any] = {
        "fixed_k_factor": k_factor,
        "results": frame.to_dict(orient="records"),
        "summary": summary,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_home_advantages(values: list[str] | None) -> tuple[float, ...]:
    if not values:
        return DEFAULT_HOME_ADVANTAGES
    parsed = tuple(float(value) for value in values)
    if not parsed:
        raise ValueError("at least one home advantage candidate is required")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tune Elo home advantage bonus with fixed K=80.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/matches_with_elo.csv"),
        help="Input processed matches CSV. Only date/team/score/neutral columns are used for rebuilding and evaluation.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/home_advantage_results.csv"),
        help="Output CSV path for home-advantage metrics.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/home_advantage_results.json"),
        help="Output JSON path for visualization and ranking summary.",
    )
    parser.add_argument(
        "--home-advantage",
        action="append",
        help="Candidate home advantage in Elo points. Repeat to pass multiple values.",
    )
    parser.add_argument(
        "--k-factor",
        type=float,
        default=FIXED_K_FACTOR,
        help="Fixed K factor for rebuild. Defaults to calibrated candidate K=80.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame, summary = tune_home_advantages(
        args.input,
        parse_home_advantages(args.home_advantage),
        k_factor=args.k_factor,
    )
    write_outputs(frame, summary, args.output_csv, args.output_json, k_factor=args.k_factor)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    print(f"fixed_k_factor: {args.k_factor:g}")
    print(frame.to_string(index=False))
    print(
        "best_accuracy: "
        f"home_advantage={summary['best_accuracy']['home_advantage']:g}, "
        f"accuracy={summary['best_accuracy']['accuracy']:.6f}"
    )
    print(
        "best_log_loss: "
        f"home_advantage={summary['best_log_loss']['home_advantage']:g}, "
        f"log_loss={summary['best_log_loss']['log_loss']:.6f}"
    )
    print(
        "best_brier_score: "
        f"home_advantage={summary['best_brier_score']['home_advantage']:g}, "
        f"brier_score={summary['best_brier_score']['brier_score']:.6f}"
    )


if __name__ == "__main__":
    main()
