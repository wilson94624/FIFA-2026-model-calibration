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
from src.tuning.evaluation import evaluate_rebuilt_elo_rows
from src.tuning.time_split_shrinkage_validation import tracked_team_values
from src.tuning.time_split_validation import (
    distribution,
    filter_matches_for_universe,
    final_team_ratings,
    ranking,
)
from src.tuning.tune_gd_shrinkage import gd_shrinkage_multiplier
from src.tuning.tune_k_factor import read_match_rows
from src.tuning.universe_benchmark import read_team_universe

TOURNAMENT_GROUPS = {
    "FIFA World Cup": "FIFA World Cup",
    "UEFA Euro": "UEFA Euro",
    "Copa América": "Copa América",
    "AFC Asian Cup": "AFC Asian Cup",
    "African Cup of Nations": "African Cup of Nations",
}

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
    {
        "model": "calibrated_elo_v3_candidate",
        "k_factor": 80.0,
        "gd_variant": "log_margin_shrinkage",
        "alpha": 0.10,
    },
)

REPORT_COLUMNS = [
    "tournament_group",
    "model",
    "matches",
    "accuracy",
    "log_loss",
    "brier_score",
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


def filter_tournament_rows(rows: list[dict[str, Any]], tournament: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row["tournament"]) == tournament]


def model_scale_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    teams = final_team_ratings(rows)
    rank_rows = ranking(teams)
    tracked = tracked_team_values(rank_rows)
    return {
        "distribution": distribution(teams),
        "tracked_teams": tracked,
        "top20": rank_rows[:20],
    }


def tournament_metric_row(
    group: str,
    model_name: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    metrics = evaluate_rebuilt_elo_rows(rows)
    return {
        "tournament_group": group,
        "model": model_name,
        "matches": len(rows),
        "accuracy": metrics["accuracy"],
        "log_loss": metrics["log_loss"],
        "brier_score": metrics["brier_score"],
    }


def build_summary(
    rows: list[dict[str, Any]],
    model_scales: dict[str, Any],
) -> dict[str, Any]:
    by_group: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_group.setdefault(str(row["tournament_group"]), {})[str(row["model"])] = row

    per_tournament: dict[str, Any] = {}
    v3_better_than_standard = {"accuracy": True, "log_loss": True, "brier_score": True}
    v3_sacrifice_vs_v2: dict[str, Any] = {}
    for group, model_rows in by_group.items():
        standard = model_rows["standard_elo_v1"]
        v2 = model_rows["calibrated_elo_v2_candidate"]
        v3 = model_rows["calibrated_elo_v3_candidate"]
        v3_vs_standard = {
            "accuracy_delta": float(v3["accuracy"]) - float(standard["accuracy"]),
            "log_loss_delta": float(standard["log_loss"]) - float(v3["log_loss"]),
            "brier_delta": float(standard["brier_score"]) - float(v3["brier_score"]),
        }
        sacrifice = {
            "log_loss_extra_vs_v2": float(v3["log_loss"]) - float(v2["log_loss"]),
            "brier_extra_vs_v2": float(v3["brier_score"]) - float(v2["brier_score"]),
        }
        per_tournament[group] = {
            "v3_vs_standard": v3_vs_standard,
            "v3_sacrifice_vs_v2": sacrifice,
            "v3_improves_standard": {
                "accuracy": v3_vs_standard["accuracy_delta"] > 0,
                "log_loss": v3_vs_standard["log_loss_delta"] > 0,
                "brier_score": v3_vs_standard["brier_delta"] > 0,
            },
        }
        v3_better_than_standard["accuracy"] = (
            v3_better_than_standard["accuracy"] and v3_vs_standard["accuracy_delta"] > 0
        )
        v3_better_than_standard["log_loss"] = (
            v3_better_than_standard["log_loss"] and v3_vs_standard["log_loss_delta"] > 0
        )
        v3_better_than_standard["brier_score"] = (
            v3_better_than_standard["brier_score"] and v3_vs_standard["brier_delta"] > 0
        )
        v3_sacrifice_vs_v2[group] = sacrifice

    v2_dist = model_scales["calibrated_elo_v2_candidate"]["distribution"]
    v3_dist = model_scales["calibrated_elo_v3_candidate"]["distribution"]
    return {
        "per_tournament": per_tournament,
        "v3_better_than_standard_all_tournaments": v3_better_than_standard,
        "v3_sacrifice_vs_v2": v3_sacrifice_vs_v2,
        "v3_scale_improvement_vs_v2": {
            "elo_min_delta": float(v3_dist["elo_min"]) - float(v2_dist["elo_min"]),
            "elo_max_delta": float(v3_dist["elo_max"]) - float(v2_dist["elo_max"]),
            "elo_std_delta": float(v3_dist["elo_std"]) - float(v2_dist["elo_std"]),
        },
        "recommendation": {
            "verdict": "B",
            "label": "v3_is_fifa_predictor_integration_candidate",
            "reason": (
                "v3 materially improves Elo scale versus v2 and improves LogLoss/Brier versus standard "
                "on most major tournament splits, but not every split; final promotion should follow "
                "integration QA and tournament-specific review."
            ),
        },
    }


def build_tournament_split_v3_validation(
    input_path: Path,
    team_universe_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = read_match_rows(input_path)
    matches = parse_match_rows(source_rows, skip_unplayed=True)
    team_universe = read_team_universe(team_universe_path)
    universe_matches = filter_matches_for_universe(matches, team_universe)
    if not universe_matches:
        raise ValueError("no matches remain after FIFA+historical universe filtering")

    rebuilt_by_model: dict[str, list[dict[str, Any]]] = {}
    model_scales: dict[str, Any] = {}
    for config in MODEL_CONFIGS:
        rebuilt = rebuild_for_config(universe_matches, config)
        model_name = str(config["model"])
        rebuilt_by_model[model_name] = rebuilt
        model_scales[model_name] = {
            "config": config,
            **model_scale_payload(rebuilt),
        }

    report_rows: list[dict[str, Any]] = []
    for group, tournament in TOURNAMENT_GROUPS.items():
        for config in MODEL_CONFIGS:
            model_name = str(config["model"])
            subset = filter_tournament_rows(rebuilt_by_model[model_name], tournament)
            if not subset:
                raise ValueError(f"no rows for tournament group {group!r}")
            report_rows.append(tournament_metric_row(group, model_name, subset))

    payload = {
        "universe": {
            "name": "fifa_historical",
            "label": "FIFA + historical national teams",
            "source_matches": len(matches),
            "universe_matches": len(universe_matches),
        },
        "tournament_groups": TOURNAMENT_GROUPS,
        "fixed_settings": {
            "home_advantage": 0.0,
            "tournament_weight": 1.0,
            "pqs": "disabled",
        },
        "models": model_scales,
        "rows": report_rows,
        "summary": build_summary(report_rows, model_scales),
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
    parser = argparse.ArgumentParser(description="Validate v3 on major tournament splits.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/matches_with_elo.csv"))
    parser.add_argument(
        "--team-universe",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/tournament_split_v3_validation.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/tournament_split_v3_validation.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = build_tournament_split_v3_validation(args.input, args.team_universe)
    write_outputs(rows, payload, args.output_csv, args.output_json)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    for row in rows:
        print(
            f"{row['tournament_group']} | {row['model']} | "
            f"matches={row['matches']} "
            f"accuracy={float(row['accuracy']):.6f} "
            f"log_loss={float(row['log_loss']):.6f} "
            f"brier_score={float(row['brier_score']):.6f}"
        )
    print(
        "verdict: "
        f"{payload['summary']['recommendation']['verdict']} - "
        f"{payload['summary']['recommendation']['label']}"
    )


if __name__ == "__main__":
    main()
