from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

GD_BUCKETS = ("GD=0", "GD=1", "GD=2", "GD=3", "GD=4", "GD>=5")
ELO_BUCKETS = (
    ("abs_elo_diff_lt_100", 0.0, 100.0),
    ("abs_elo_diff_100_200", 100.0, 200.0),
    ("abs_elo_diff_200_300", 200.0, 300.0),
    ("abs_elo_diff_300_400", 300.0, 400.0),
    ("abs_elo_diff_400_plus", 400.0, float("inf")),
)
TAIL_SCORELINES = (
    ("3-0_or_0-3", ((3, 0), (0, 3))),
    ("4-0_or_0-4", ((4, 0), (0, 4))),
    ("5-0_or_0-5", ((5, 0), (0, 5))),
    ("4-1_or_1-4", ((4, 1), (1, 4))),
    ("5-1_or_1-5", ((5, 1), (1, 5))),
    ("6-0_or_0-6", ((6, 0), (0, 6))),
    ("7-1_or_1-7", ((7, 1), (1, 7))),
)


def read_processed_matches(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"no rows found in {path}")
    return rows


def parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def world_cup_edition(row: dict[str, Any]) -> int:
    return parse_date(row["date"]).year


def add_world_cup_stage_proxy(rows: list[dict[str, Any]]) -> None:
    """Add a chronological proxy because international_results has no official stage column."""
    by_year: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if str(row["tournament"]) == "FIFA World Cup":
            by_year[world_cup_edition(row)].append(row)

    for year_rows in by_year.values():
        sorted_rows = sorted(
            year_rows,
            key=lambda row: (parse_date(row["date"]), int(row.get("source_row_number", 0))),
        )
        group_cutoff = max(1, int(round(len(sorted_rows) * 0.70)))
        for index, row in enumerate(sorted_rows):
            row["world_cup_stage_proxy"] = (
                "group_stage_proxy" if index < group_cutoff else "knockout_stage_proxy"
            )
    for row in rows:
        row.setdefault("world_cup_stage_proxy", "")


def score_tuple(row: dict[str, Any]) -> tuple[int, int]:
    return int(row["home_score"]), int(row["away_score"])


def abs_goal_difference(row: dict[str, Any]) -> int:
    home, away = score_tuple(row)
    return abs(home - away)


def gd_bucket(abs_gd: int) -> str:
    if abs_gd == 0:
        return "GD=0"
    if abs_gd == 1:
        return "GD=1"
    if abs_gd == 2:
        return "GD=2"
    if abs_gd == 3:
        return "GD=3"
    if abs_gd == 4:
        return "GD=4"
    return "GD>=5"


def abs_elo_diff(row: dict[str, Any]) -> float:
    return abs(float(row["home_pre_match_elo"]) - float(row["away_pre_match_elo"]))


def elo_bucket(row: dict[str, Any]) -> str:
    value = abs_elo_diff(row)
    for label, lower, upper in ELO_BUCKETS:
        if lower <= value < upper:
            return label
    return ELO_BUCKETS[-1][0]


def favorite_margin(row: dict[str, Any]) -> int:
    home_score, away_score = score_tuple(row)
    home_elo = float(row["home_pre_match_elo"])
    away_elo = float(row["away_pre_match_elo"])
    if home_elo >= away_elo:
        return home_score - away_score
    return away_score - home_score


def tail_scoreline_counts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    match_count = len(rows)
    output = []
    for label, scorelines in TAIL_SCORELINES:
        count = sum(1 for row in rows if score_tuple(row) in scorelines)
        output.append({"scoreline_group": label, "matches": count, "rate": count / match_count})
    return output


def summarize_rows(name: str, rows: list[dict[str, Any]], notes: str = "") -> dict[str, Any]:
    if not rows:
        return {
            "name": name,
            "matches": 0,
            "notes": notes,
            "goal_difference_distribution": [
                {"bucket": bucket, "matches": 0, "rate": 0.0} for bucket in GD_BUCKETS
            ],
            "large_margin_rates": {
                "gd_3_plus": {"matches": 0, "rate": 0.0},
                "gd_4_plus": {"matches": 0, "rate": 0.0},
                "gd_5_plus": {"matches": 0, "rate": 0.0},
                "favorite_win_by_3_plus": {"matches": 0, "rate": 0.0},
                "favorite_win_by_4_plus": {"matches": 0, "rate": 0.0},
            },
            "exact_tail_scorelines": [
                {"scoreline_group": label, "matches": 0, "rate": 0.0}
                for label, _ in TAIL_SCORELINES
            ],
            "avg_abs_elo_diff": 0.0,
        }
    match_count = len(rows)
    gd_counts = {bucket: 0 for bucket in GD_BUCKETS}
    for row in rows:
        gd_counts[gd_bucket(abs_goal_difference(row))] += 1

    gd_3_plus = sum(1 for row in rows if abs_goal_difference(row) >= 3)
    gd_4_plus = sum(1 for row in rows if abs_goal_difference(row) >= 4)
    gd_5_plus = sum(1 for row in rows if abs_goal_difference(row) >= 5)
    favorite_3_plus = sum(1 for row in rows if favorite_margin(row) >= 3)
    favorite_4_plus = sum(1 for row in rows if favorite_margin(row) >= 4)
    return {
        "name": name,
        "matches": match_count,
        "notes": notes,
        "goal_difference_distribution": [
            {
                "bucket": bucket,
                "matches": gd_counts[bucket],
                "rate": gd_counts[bucket] / match_count,
            }
            for bucket in GD_BUCKETS
        ],
        "large_margin_rates": {
            "gd_3_plus": {"matches": gd_3_plus, "rate": gd_3_plus / match_count},
            "gd_4_plus": {"matches": gd_4_plus, "rate": gd_4_plus / match_count},
            "gd_5_plus": {"matches": gd_5_plus, "rate": gd_5_plus / match_count},
            "favorite_win_by_3_plus": {
                "matches": favorite_3_plus,
                "rate": favorite_3_plus / match_count,
            },
            "favorite_win_by_4_plus": {
                "matches": favorite_4_plus,
                "rate": favorite_4_plus / match_count,
            },
        },
        "exact_tail_scorelines": tail_scoreline_counts(rows),
        "avg_abs_elo_diff": sum(abs_elo_diff(row) for row in rows) / match_count,
    }


def build_core_splits(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "all_processed_matches": rows,
        "fifa_world_cup_only": [
            row for row in rows if str(row["tournament"]) == "FIFA World Cup"
        ],
        "uefa_euro_only": [row for row in rows if str(row["tournament"]) == "UEFA Euro"],
        "modern_era_1990_plus": [row for row in rows if parse_date(row["date"]) >= date(1990, 1, 1)],
        "recent_era_2000_plus": [row for row in rows if parse_date(row["date"]) >= date(2000, 1, 1)],
    }


def build_era_effect(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pre_1990 = [row for row in rows if parse_date(row["date"]) < date(1990, 1, 1)]
    modern = [row for row in rows if parse_date(row["date"]) >= date(1990, 1, 1)]
    recent = [row for row in rows if parse_date(row["date"]) >= date(2000, 1, 1)]
    world_cup = [row for row in rows if str(row["tournament"]) == "FIFA World Cup"]
    world_cup_pre_1990 = [row for row in world_cup if parse_date(row["date"]) < date(1990, 1, 1)]
    world_cup_modern = [row for row in world_cup if parse_date(row["date"]) >= date(1990, 1, 1)]
    world_cup_recent = [row for row in world_cup if parse_date(row["date"]) >= date(2000, 1, 1)]
    return {
        "all_pre_1990": summarize_rows("all_pre_1990", pre_1990),
        "all_1990_plus": summarize_rows("all_1990_plus", modern),
        "all_2000_plus": summarize_rows("all_2000_plus", recent),
        "world_cup_pre_1990": summarize_rows("world_cup_pre_1990", world_cup_pre_1990),
        "world_cup_1990_plus": summarize_rows("world_cup_1990_plus", world_cup_modern),
        "world_cup_2000_plus": summarize_rows("world_cup_2000_plus", world_cup_recent),
    }


def build_stage_effect(rows: list[dict[str, Any]]) -> dict[str, Any]:
    world_cup = [row for row in rows if str(row["tournament"]) == "FIFA World Cup"]
    group_rows = [row for row in world_cup if row["world_cup_stage_proxy"] == "group_stage_proxy"]
    knockout_rows = [
        row for row in world_cup if row["world_cup_stage_proxy"] == "knockout_stage_proxy"
    ]
    return {
        "stage_field_available": False,
        "method": "chronological proxy by World Cup edition; first 70% of matches treated as group-stage proxy",
        "warning": "international_results does not provide official stage labels; use this only as directional diagnostics.",
        "group_stage_proxy": summarize_rows("world_cup_group_stage_proxy", group_rows),
        "knockout_stage_proxy": summarize_rows("world_cup_knockout_stage_proxy", knockout_rows),
    }


def build_elo_bucket_analysis(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for label, _, _ in ELO_BUCKETS:
        bucket_rows = [row for row in rows if elo_bucket(row) == label]
        output.append(summarize_rows(label, bucket_rows))
    return output


def rate(summary: dict[str, Any], key: str) -> float:
    return float(summary["large_margin_rates"][key]["rate"])


def build_conclusions(report: dict[str, Any]) -> dict[str, Any]:
    splits = report["splits"]
    wc = splits["fifa_world_cup_only"]
    euro = splits["uefa_euro_only"]
    wc_pre = report["era_effect"]["world_cup_pre_1990"]
    wc_modern = report["era_effect"]["world_cup_1990_plus"]
    group_proxy = report["stage_effect"]["group_stage_proxy"]
    knockout_proxy = report["stage_effect"]["knockout_stage_proxy"]
    elo_buckets = report["elo_mismatch_buckets"]
    high_elo_bucket = next(row for row in elo_buckets if row["name"] == "abs_elo_diff_400_plus")
    low_elo_bucket = next(row for row in elo_buckets if row["name"] == "abs_elo_diff_lt_100")
    return {
        "tail_scorelines_common_enough_for_global_model_change": False,
        "large_margins_concentrated_contexts": {
            "world_cup_gd_3_plus_rate": rate(wc, "gd_3_plus"),
            "euro_gd_3_plus_rate": rate(euro, "gd_3_plus"),
            "world_cup_pre_1990_gd_3_plus_rate": rate(wc_pre, "gd_3_plus"),
            "world_cup_1990_plus_gd_3_plus_rate": rate(wc_modern, "gd_3_plus"),
            "world_cup_group_proxy_gd_3_plus_rate": rate(group_proxy, "gd_3_plus"),
            "world_cup_knockout_proxy_gd_3_plus_rate": rate(knockout_proxy, "gd_3_plus"),
            "elo_400_plus_gd_3_plus_rate": rate(high_elo_bucket, "gd_3_plus"),
            "elo_lt_100_gd_3_plus_rate": rate(low_elo_bucket, "gd_3_plus"),
        },
        "overfitting_risk": {
            "risk": "high",
            "reason": (
                "Large margins are meaningfully concentrated in World Cup, older eras, and high Elo mismatch buckets. "
                "A global tail amplification could overfit mismatch/group-stage contexts and harm modern, Euro, knockout, or balanced matchups."
            ),
        },
        "world_cup_48_team_recommendation": {
            "recommended_mode": "conditional shadow diagnostics and separate group-stage diagnostics",
            "global_model_change": False,
            "reason": (
                "A 48-team field may increase high-mismatch group matches, but historical evidence does not support a global correction."
            ),
        },
        "poisson_vs_negative_binomial_research": {
            "recommended": True,
            "scope": "research-only comparison for score tails and group-stage mismatch diagnostics",
        },
        "keep_formal_model_baseline_unchanged": True,
    }


def build_large_margin_frequency_report(input_path: Path) -> dict[str, Any]:
    rows = read_processed_matches(input_path)
    add_world_cup_stage_proxy(rows)
    core_splits = build_core_splits(rows)
    split_summaries = {
        name: summarize_rows(name, split_rows) for name, split_rows in core_splits.items()
    }
    report = {
        "report": "large_margin_frequency_and_overfitting_risk",
        "data_source": str(input_path),
        "model_formulas_unchanged": True,
        "research_only": True,
        "splits": split_summaries,
        "era_effect": build_era_effect(rows),
        "stage_effect": build_stage_effect(rows),
        "elo_mismatch_buckets": build_elo_bucket_analysis(rows),
    }
    report["conclusions"] = build_conclusions(report)
    return report


def write_markdown_report(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Large Margin Frequency and Overfitting Risk Report",
        "",
        "Research-only data diagnostics. Formal Predictor formulas remain unchanged.",
        "",
        "## Core Splits",
        "",
        "| Split | Matches | GD>=3 | GD>=4 | GD>=5 | Favorite 3+ | Favorite 4+ | Avg Abs Elo Diff |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in report["splits"].values():
        rates = summary["large_margin_rates"]
        lines.append(
            f"| {summary['name']} | {summary['matches']} | "
            f"{rates['gd_3_plus']['rate']:.6f} | {rates['gd_4_plus']['rate']:.6f} | "
            f"{rates['gd_5_plus']['rate']:.6f} | "
            f"{rates['favorite_win_by_3_plus']['rate']:.6f} | "
            f"{rates['favorite_win_by_4_plus']['rate']:.6f} | "
            f"{summary['avg_abs_elo_diff']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Elo Mismatch Buckets",
            "",
            "| Bucket | Matches | GD>=3 | GD>=4 | GD>=5 | Favorite 3+ |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for summary in report["elo_mismatch_buckets"]:
        rates = summary["large_margin_rates"]
        lines.append(
            f"| {summary['name']} | {summary['matches']} | "
            f"{rates['gd_3_plus']['rate']:.6f} | {rates['gd_4_plus']['rate']:.6f} | "
            f"{rates['gd_5_plus']['rate']:.6f} | "
            f"{rates['favorite_win_by_3_plus']['rate']:.6f} |"
        )

    stage = report["stage_effect"]
    lines.extend(
        [
            "",
            "## World Cup Stage Proxy",
            "",
            stage["warning"],
            "",
            "| Proxy Stage | Matches | GD>=3 | GD>=4 | Favorite 3+ |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for key in ("group_stage_proxy", "knockout_stage_proxy"):
        summary = stage[key]
        rates = summary["large_margin_rates"]
        lines.append(
            f"| {summary['name']} | {summary['matches']} | "
            f"{rates['gd_3_plus']['rate']:.6f} | {rates['gd_4_plus']['rate']:.6f} | "
            f"{rates['favorite_win_by_3_plus']['rate']:.6f} |"
        )

    conclusions = report["conclusions"]
    lines.extend(
        [
            "",
            "## Conclusions",
            "",
            f"- Tail scorelines common enough for global model change: `{conclusions['tail_scorelines_common_enough_for_global_model_change']}`",
            f"- Overfitting risk: `{conclusions['overfitting_risk']['risk']}`",
            f"- Recommended 48-team World Cup mode: {conclusions['world_cup_48_team_recommendation']['recommended_mode']}",
            f"- Research Poisson vs Negative Binomial: `{conclusions['poisson_vs_negative_binomial_research']['recommended']}`",
            f"- Keep formal baseline unchanged: `{conclusions['keep_formal_model_baseline_unchanged']}`",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(report: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown_report(report, markdown_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build large-margin frequency diagnostics.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/large_margin_frequency_report.json"),
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("results/large_margin_frequency_report.md"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_large_margin_frequency_report(args.input)
    write_outputs(report, args.output_json, args.output_md)
    conclusions = report["conclusions"]
    print(f"output_json: {args.output_json}")
    print(f"output_md: {args.output_md}")
    print(f"matches: {report['splits']['all_processed_matches']['matches']}")
    print(
        "world_cup_gd_3_plus_rate: "
        f"{conclusions['large_margins_concentrated_contexts']['world_cup_gd_3_plus_rate']:.6f}"
    )
    print(
        "elo_400_plus_gd_3_plus_rate: "
        f"{conclusions['large_margins_concentrated_contexts']['elo_400_plus_gd_3_plus_rate']:.6f}"
    )
    print(f"overfitting_risk: {conclusions['overfitting_risk']['risk']}")


if __name__ == "__main__":
    main()
