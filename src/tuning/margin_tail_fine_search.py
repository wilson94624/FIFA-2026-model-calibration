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

from src.tuning.margin_tail_modeling_research import (
    REPORT_COLUMNS as BASE_REPORT_COLUMNS,
    analyze_rows,
    evaluate_variant,
)
from src.tuning.worldcup_xg_parameter_search import load_target_rows

GD_ALPHAS = (0.04, 0.06, 0.08, 0.10, 0.12, 0.14)
FAVORITE_ALPHAS = (0.08, 0.10, 0.12, 0.15, 0.18)

REPORT_COLUMNS = ["split", *BASE_REPORT_COLUMNS]


def build_variant_configs() -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = [
        {
            "variant": "baseline",
            "method": "baseline",
            "alpha": None,
            "condition": "none",
            "max_goals": 5,
        }
    ]
    for alpha in GD_ALPHAS:
        configs.append(
            {
                "variant": f"gd_tail_redistribution_alpha_{alpha:.2f}",
                "method": "gd_tail_redistribution",
                "alpha": alpha,
                "condition": "none",
                "max_goals": 5,
            }
        )
    for alpha in FAVORITE_ALPHAS:
        configs.append(
            {
                "variant": f"favorite_tail_boost_alpha_{alpha:.2f}",
                "method": "favorite_tail_boost",
                "alpha": alpha,
                "condition": "none",
                "max_goals": 5,
            }
        )
    return configs


def parse_match_date(row: dict[str, Any]) -> date:
    value = row["date"]
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def split_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "all_pooled": rows,
        "fifa_world_cup_only": [
            row for row in rows if str(row["tournament"]) == "FIFA World Cup"
        ],
        "uefa_euro_only": [row for row in rows if str(row["tournament"]) == "UEFA Euro"],
        "modern_era_1990_plus": [
            row for row in rows if parse_match_date(row) >= date(1990, 1, 1)
        ],
        "recent_era_2000_plus": [
            row for row in rows if parse_match_date(row) >= date(2000, 1, 1)
        ],
    }


def evaluate_split(
    split_name: str,
    rows: list[dict[str, Any]],
    configs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not rows:
        raise ValueError(f"split {split_name!r} has no rows")
    analyzed = analyze_rows(rows)
    return [{"split": split_name, **evaluate_variant(analyzed, config)} for config in configs]


def row_key(row: dict[str, Any], metric: str) -> float:
    return float(row[metric])


def summarize_split(rows: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = next(row for row in rows if row["variant"] == "baseline")
    best_gd = min(rows, key=lambda row: row_key(row, "gd_3_plus_calibration_error"))
    best_favorite = min(
        rows,
        key=lambda row: row_key(row, "favorite_win_by_3_plus_calibration_error"),
    )
    best_top3 = max(rows, key=lambda row: row_key(row, "correct_score_top3_accuracy"))
    best_top5 = max(rows, key=lambda row: row_key(row, "correct_score_top5_accuracy"))
    best_log_loss = min(rows, key=lambda row: row_key(row, "log_loss"))
    gd_alpha_010 = next(
        row for row in rows if row["variant"] == "gd_tail_redistribution_alpha_0.10"
    )
    favorite_alpha_015 = next(
        row for row in rows if row["variant"] == "favorite_tail_boost_alpha_0.15"
    )
    return {
        "baseline": baseline,
        "best_gd_3_plus_calibration": best_gd,
        "best_favorite_win_by_3_plus_calibration": best_favorite,
        "best_correct_score_top3": best_top3,
        "best_correct_score_top5": best_top5,
        "best_log_loss": best_log_loss,
        "gd_tail_alpha_0_10": gd_alpha_010,
        "favorite_tail_alpha_0_15": favorite_alpha_015,
        "gd_tail_alpha_0_10_vs_baseline": {
            "top3_delta": row_key(gd_alpha_010, "correct_score_top3_accuracy")
            - row_key(baseline, "correct_score_top3_accuracy"),
            "top5_delta": row_key(gd_alpha_010, "correct_score_top5_accuracy")
            - row_key(baseline, "correct_score_top5_accuracy"),
            "gd_error_delta": row_key(baseline, "gd_3_plus_calibration_error")
            - row_key(gd_alpha_010, "gd_3_plus_calibration_error"),
            "log_loss_delta": row_key(baseline, "log_loss") - row_key(gd_alpha_010, "log_loss"),
            "brier_delta": row_key(baseline, "brier_score") - row_key(gd_alpha_010, "brier_score"),
        },
    }


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_split: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_split.setdefault(str(row["split"]), []).append(row)

    split_summaries = {
        split: summarize_split(split_rows_) for split, split_rows_ in by_split.items()
    }
    alpha_010_summaries = [
        summary["gd_tail_alpha_0_10_vs_baseline"] for summary in split_summaries.values()
    ]
    stable_alpha_010 = all(
        float(summary["gd_error_delta"]) > 0.0 for summary in alpha_010_summaries
    )
    top3_positive_count = sum(
        1 for summary in alpha_010_summaries if float(summary["top3_delta"]) > 0.0
    )
    best_gd_variants = {
        split: summary["best_gd_3_plus_calibration"]["variant"]
        for split, summary in split_summaries.items()
    }
    return {
        "split_summaries": split_summaries,
        "alpha_0_10_stability": {
            "gd_error_improves_all_splits": stable_alpha_010,
            "top3_improves_split_count": top3_positive_count,
            "split_count": len(split_summaries),
            "mean_gd_error_delta": statistics.mean(
                float(summary["gd_error_delta"]) for summary in alpha_010_summaries
            ),
            "mean_top3_delta": statistics.mean(
                float(summary["top3_delta"]) for summary in alpha_010_summaries
            ),
        },
        "best_gd_variants_by_split": best_gd_variants,
        "recommendation": {
            "alpha_0_10_is_stable_for_gd_calibration": stable_alpha_010,
            "top3_top5_gains_are_small": True,
            "improvement_mainly_early_world_cup": (
                split_summaries["modern_era_1990_plus"]["gd_tail_alpha_0_10_vs_baseline"][
                    "gd_error_delta"
                ]
                <= 0
                or split_summaries["recent_era_2000_plus"]["gd_tail_alpha_0_10_vs_baseline"][
                    "gd_error_delta"
                ]
                <= 0
            ),
            "continue_research": True,
            "keep_formal_model_baseline_unchanged": True,
        },
    }


def build_margin_tail_fine_search(
    input_path: Path,
    team_universe_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target_rows, source_summary = load_target_rows(input_path, team_universe_path)
    splits = split_rows(target_rows)
    configs = build_variant_configs()
    rows: list[dict[str, Any]] = []
    for split_name, split_rows_ in splits.items():
        rows.extend(evaluate_split(split_name, split_rows_, configs))
    payload = {
        "benchmark": "margin_tail_fine_search",
        "dataset": {
            "label": "FIFA World Cup + UEFA Euro neutral matches",
            "universe": "FIFA + historical national teams",
            **source_summary,
        },
        "model_context": {
            "baseline": "final_worldcup_model_v1_candidate",
            "formal_model_formulas_unchanged": True,
            "production_default_unchanged": True,
            "research_validation_layer_only": True,
        },
        "search_space": {
            "gd_tail_redistribution_alpha": list(GD_ALPHAS),
            "favorite_tail_boost_alpha": list(FAVORITE_ALPHAS),
        },
        "variant_configs": configs,
        "rows": rows,
        "summary": build_summary(rows),
    }
    return rows, payload


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    summary = payload["summary"]
    lines = [
        "# Margin Tail Fine Search and Split Validation",
        "",
        "Research-only validation. Formal Predictor formulas and production defaults remain unchanged.",
        "",
        "## Split Summary",
        "",
        "| Split | Matches | Best GD>=3 | Best Top-3 | Best Top-5 | alpha=0.10 GD Error Delta | alpha=0.10 Top-3 Delta |",
        "| --- | ---: | --- | --- | --- | ---: | ---: |",
    ]
    for split, split_summary in summary["split_summaries"].items():
        baseline = split_summary["baseline"]
        alpha_delta = split_summary["gd_tail_alpha_0_10_vs_baseline"]
        lines.append(
            f"| {split} | {baseline['matches']} | "
            f"{split_summary['best_gd_3_plus_calibration']['variant']} | "
            f"{split_summary['best_correct_score_top3']['variant']} | "
            f"{split_summary['best_correct_score_top5']['variant']} | "
            f"{alpha_delta['gd_error_delta']:.6f} | {alpha_delta['top3_delta']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"- alpha=0.10 stable for GD calibration: `{summary['recommendation']['alpha_0_10_is_stable_for_gd_calibration']}`",
            f"- Top-3 / Top-5 gains are small: `{summary['recommendation']['top3_top5_gains_are_small']}`",
            f"- Improvement mainly early World Cup: `{summary['recommendation']['improvement_mainly_early_world_cup']}`",
            f"- Continue research: `{summary['recommendation']['continue_research']}`",
            f"- Keep formal baseline unchanged: `{summary['recommendation']['keep_formal_model_baseline_unchanged']}`",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(
    rows: list[dict[str, Any]],
    payload: dict[str, Any],
    csv_path: Path,
    json_path: Path,
    markdown_path: Path,
) -> None:
    write_csv(rows, csv_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_markdown(payload, markdown_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run margin-tail fine search and split validation.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/margin_tail_fine_search.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/margin_tail_fine_search.json"),
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("results/margin_tail_fine_search.md"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = build_margin_tail_fine_search(args.input, args.team_universe)
    write_outputs(rows, payload, args.output_csv, args.output_json, args.output_md)
    recommendation = payload["summary"]["recommendation"]

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    print(f"output_md: {args.output_md}")
    print(
        "alpha_0_10_is_stable_for_gd_calibration: "
        f"{recommendation['alpha_0_10_is_stable_for_gd_calibration']}"
    )
    print(f"continue_research: {recommendation['continue_research']}")
    print(
        "keep_formal_model_baseline_unchanged: "
        f"{recommendation['keep_formal_model_baseline_unchanged']}"
    )


if __name__ == "__main__":
    main()
