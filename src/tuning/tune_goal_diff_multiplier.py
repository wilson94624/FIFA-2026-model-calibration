from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model.elo_rebuilder import MODEL_VERSION, parse_match_rows, rebuild_elo_history
from src.tuning.evaluation import evaluate_rebuilt_elo_rows, rank_metric_rows
from src.tuning.tune_k_factor import read_match_rows

FIXED_K_FACTOR = 80.0
VARIANTS = ("none", "simple_linear_capped", "sqrt_margin", "log_margin")
OUTPUT_COLUMNS = ["variant", "accuracy", "log_loss", "brier_score"]
MultiplierFn = Callable[[int, int], float]


def goal_diff_multiplier(variant: str) -> MultiplierFn:
    if variant not in VARIANTS:
        raise ValueError(f"unknown goal difference multiplier variant {variant!r}")

    def multiplier(home_score: int, away_score: int) -> float:
        goal_diff = abs(home_score - away_score)
        if goal_diff == 0:
            return 1.0
        if variant == "none":
            return 1.0
        if variant == "simple_linear_capped":
            return float(min(goal_diff, 3))
        if variant == "sqrt_margin":
            return math.sqrt(goal_diff)
        if variant == "log_margin":
            return math.log(goal_diff + 1)
        raise AssertionError("unreachable variant")

    return multiplier


def tune_goal_diff_multipliers(
    input_path: Path,
    variants: tuple[str, ...] = VARIANTS,
    k_factor: float = FIXED_K_FACTOR,
) -> tuple[list[dict[str, float | str]], dict[str, dict[str, float | str]]]:
    source_rows = read_match_rows(input_path)
    matches = parse_match_rows(source_rows, skip_unplayed=True)
    if not matches:
        raise ValueError(f"{input_path} contains no completed match rows")

    metric_rows: list[dict[str, float | str]] = []
    for variant in variants:
        rebuilt_rows = rebuild_elo_history(
            matches,
            k_factor=k_factor,
            goal_diff_multiplier_fn=goal_diff_multiplier(variant),
            model_version=f"{MODEL_VERSION}_k_{k_factor:g}_goal_diff_{variant}",
        )
        metrics = evaluate_rebuilt_elo_rows(rebuilt_rows)
        metric_rows.append(
            {
                "variant": variant,
                "accuracy": metrics["accuracy"],
                "log_loss": metrics["log_loss"],
                "brier_score": metrics["brier_score"],
            }
        )

    summary = rank_metric_rows(metric_rows)  # type: ignore[arg-type]
    return metric_rows, summary


def write_outputs(
    rows: list[dict[str, float | str]],
    summary: dict[str, dict[str, float | str]],
    csv_path: Path,
    json_path: Path,
    k_factor: float = FIXED_K_FACTOR,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    payload: dict[str, Any] = {
        "fixed_k_factor": k_factor,
        "results": rows,
        "summary": summary,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_variants(values: list[str] | None) -> tuple[str, ...]:
    if not values:
        return VARIANTS
    parsed = tuple(values)
    for variant in parsed:
        if variant not in VARIANTS:
            raise ValueError(f"unknown goal difference multiplier variant {variant!r}")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tune optional Elo goal-difference multipliers.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/matches_with_elo.csv"),
        help="Input processed matches CSV. Only date/team/score columns are used for rebuild.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/goal_diff_multiplier_results.csv"),
        help="Output CSV path for goal-difference multiplier metrics.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/goal_diff_multiplier_results.json"),
        help="Output JSON path for visualization and ranking summary.",
    )
    parser.add_argument("--k-factor", type=float, default=FIXED_K_FACTOR)
    parser.add_argument("--variant", action="append", help="Variant to evaluate. Repeat for multiple.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, summary = tune_goal_diff_multipliers(
        args.input,
        variants=parse_variants(args.variant),
        k_factor=args.k_factor,
    )
    write_outputs(rows, summary, args.output_csv, args.output_json, k_factor=args.k_factor)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    print(f"fixed_k_factor: {args.k_factor:g}")
    print("variant accuracy log_loss brier_score")
    for row in rows:
        print(
            f"{row['variant']} "
            f"{float(row['accuracy']):.6f} "
            f"{float(row['log_loss']):.6f} "
            f"{float(row['brier_score']):.6f}"
        )
    print(
        "best_accuracy: "
        f"variant={summary['best_accuracy']['variant']}, "
        f"accuracy={float(summary['best_accuracy']['accuracy']):.6f}"
    )
    print(
        "best_log_loss: "
        f"variant={summary['best_log_loss']['variant']}, "
        f"log_loss={float(summary['best_log_loss']['log_loss']):.6f}"
    )
    print(
        "best_brier_score: "
        f"variant={summary['best_brier_score']['variant']}, "
        f"brier_score={float(summary['best_brier_score']['brier_score']):.6f}"
    )


if __name__ == "__main__":
    main()
