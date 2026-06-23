from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
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
ALPHAS = (0.0, 0.25, 0.5, 0.75, 1.0)
TRACKED_TEAMS = ("Argentina", "Spain", "France", "Norway", "Brazil")
OUTPUT_COLUMNS = [
    "alpha",
    "accuracy",
    "log_loss",
    "brier_score",
    "elo_std",
    "elo_min",
    "elo_max",
    "argentina_final_elo",
    "spain_final_elo",
    "france_final_elo",
    "norway_final_elo",
    "brazil_final_elo",
]

MultiplierFn = Callable[[int, int], float]


def gd_shrinkage_multiplier(alpha: float) -> MultiplierFn:
    def multiplier(home_score: int, away_score: int) -> float:
        goal_diff = abs(home_score - away_score)
        if goal_diff == 0:
            return 1.0
        return 1.0 + alpha * (math.log(goal_diff + 1) - 1.0)

    return multiplier


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


def distribution_summary(teams: dict[str, dict[str, float | int]]) -> dict[str, float]:
    ratings = [float(values["final_elo"]) for values in teams.values()]
    if not ratings:
        raise ValueError("cannot summarize empty team ratings")
    return {
        "elo_std": statistics.pstdev(ratings),
        "elo_min": min(ratings),
        "elo_max": max(ratings),
    }


def tracked_team_summary(
    teams: dict[str, dict[str, float | int]],
    ranking_rows: list[dict[str, float | int | str]],
    tracked_teams: tuple[str, ...] = TRACKED_TEAMS,
) -> dict[str, dict[str, float | int | None]]:
    rank_by_team = {str(row["team"]): row for row in ranking_rows}
    summary: dict[str, dict[str, float | int | None]] = {}
    for team in tracked_teams:
        values = teams.get(team)
        rank_row = rank_by_team.get(team)
        summary[team] = {
            "final_elo": float(values["final_elo"]) if values else None,
            "rank": int(rank_row["rank"]) if rank_row else None,
            "matches": int(values["matches"]) if values else None,
        }
    return summary


def _tracked_csv_columns(
    tracked: dict[str, dict[str, float | int | None]],
) -> dict[str, float | None]:
    return {
        f"{team.lower().replace(' ', '_')}_final_elo": (
            float(values["final_elo"]) if values["final_elo"] is not None else None
        )
        for team, values in tracked.items()
    }


def _tracked_deltas(
    current: dict[str, dict[str, float | int | None]],
    reference: dict[str, dict[str, float | int | None]],
) -> dict[str, float | None]:
    deltas: dict[str, float | None] = {}
    for team, values in current.items():
        current_elo = values["final_elo"]
        reference_elo = reference.get(team, {}).get("final_elo")
        deltas[team] = (
            float(current_elo) - float(reference_elo)
            if current_elo is not None and reference_elo is not None
            else None
        )
    return deltas


def build_recommendation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    best_log_loss = min(rows, key=lambda row: float(row["log_loss"]))
    best_brier = min(rows, key=lambda row: float(row["brier_score"]))
    full_log = next(row for row in rows if float(row["alpha"]) == 1.0)
    no_multiplier = next(row for row in rows if float(row["alpha"]) == 0.0)

    candidates = [
        row
        for row in rows
        if float(row["log_loss"]) < float(no_multiplier["log_loss"])
        and float(row["brier_score"]) < float(no_multiplier["brier_score"])
    ]
    if candidates:
        recommended = min(
            candidates,
            key=lambda row: (
                float(row["elo_max"]),
                float(row["elo_std"]),
                float(row["log_loss"]),
            ),
        )
    else:
        recommended = best_log_loss

    return {
        "best_accuracy": max(rows, key=lambda row: float(row["accuracy"])),
        "best_log_loss": best_log_loss,
        "best_brier_score": best_brier,
        "no_multiplier_alpha": no_multiplier,
        "full_log_margin_alpha": full_log,
        "recommended_calibrated_elo_v3_candidate": {
            "alpha": recommended["alpha"],
            "reason": (
                "lowest Elo max/std among alphas that still improve LogLoss and Brier over alpha=0"
                if candidates
                else "no alpha improved both LogLoss and Brier over alpha=0; fallback to best LogLoss"
            ),
        },
    }


def tune_gd_shrinkage(
    input_path: Path,
    alphas: tuple[float, ...] = ALPHAS,
    k_factor: float = FIXED_K_FACTOR,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = read_match_rows(input_path)
    matches = parse_match_rows(source_rows, skip_unplayed=True)
    if not matches:
        raise ValueError(f"{input_path} contains no completed match rows")

    rows: list[dict[str, Any]] = []
    alpha_payloads: dict[str, Any] = {}
    tracked_by_alpha: dict[float, dict[str, dict[str, float | int | None]]] = {}

    for alpha in alphas:
        rebuilt_rows = rebuild_elo_history(
            matches,
            k_factor=k_factor,
            goal_diff_multiplier_fn=gd_shrinkage_multiplier(alpha),
            model_version=f"{MODEL_VERSION}_k_{k_factor:g}_gd_shrinkage_alpha_{alpha:g}",
        )
        metrics = evaluate_rebuilt_elo_rows(rebuilt_rows)
        teams = final_team_ratings(rebuilt_rows)
        rank_rows = ranking(teams)
        dist = distribution_summary(teams)
        tracked = tracked_team_summary(teams, rank_rows)
        tracked_by_alpha[alpha] = tracked

        row: dict[str, Any] = {
            "alpha": alpha,
            "accuracy": metrics["accuracy"],
            "log_loss": metrics["log_loss"],
            "brier_score": metrics["brier_score"],
            **dist,
            **_tracked_csv_columns(tracked),
        }
        rows.append(row)
        alpha_payloads[f"{alpha:.2f}"] = {
            "metrics": metrics,
            "distribution": dist,
            "tracked_teams": tracked,
            "top20": rank_rows[:20],
        }

    reference_no_multiplier = tracked_by_alpha.get(0.0, {})
    reference_full_log = tracked_by_alpha.get(1.0, {})
    for alpha in alphas:
        payload = alpha_payloads[f"{alpha:.2f}"]
        tracked = tracked_by_alpha[alpha]
        payload["tracked_team_delta_vs_alpha_0"] = _tracked_deltas(
            tracked,
            reference_no_multiplier,
        )
        payload["tracked_team_delta_vs_alpha_1"] = _tracked_deltas(
            tracked,
            reference_full_log,
        )

    summary = rank_metric_rows(rows)  # type: ignore[arg-type]
    payload = {
        "fixed_k_factor": k_factor,
        "tournament_weight": 1.0,
        "home_advantage": 0.0,
        "pqs": "disabled",
        "formula": "1 + alpha * (log(goal_diff + 1) - 1); draws use 1.0",
        "alphas": alpha_payloads,
        "results": rows,
        "summary": {
            **summary,
            **build_recommendation(rows),
        },
    }
    return rows, payload


def write_outputs(rows: list[dict[str, Any]], payload: dict[str, Any], csv_path: Path, json_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_alphas(values: list[str] | None) -> tuple[float, ...]:
    if not values:
        return ALPHAS
    return tuple(float(value) for value in values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Research Elo goal-difference shrinkage.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/matches_with_elo.csv"),
        help="Input processed matches CSV. Only date/team/score columns are used for rebuild.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/gd_shrinkage_results.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/gd_shrinkage_results.json"),
    )
    parser.add_argument("--k-factor", type=float, default=FIXED_K_FACTOR)
    parser.add_argument("--alpha", action="append", help="Alpha to evaluate. Repeat for multiple.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = tune_gd_shrinkage(
        args.input,
        alphas=parse_alphas(args.alpha),
        k_factor=args.k_factor,
    )
    write_outputs(rows, payload, args.output_csv, args.output_json)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    print(f"fixed_k_factor: {args.k_factor:g}")
    print("alpha accuracy log_loss brier_score elo_std elo_min elo_max")
    for row in rows:
        print(
            f"{float(row['alpha']):.2f} "
            f"{float(row['accuracy']):.6f} "
            f"{float(row['log_loss']):.6f} "
            f"{float(row['brier_score']):.6f} "
            f"{float(row['elo_std']):.3f} "
            f"{float(row['elo_min']):.3f} "
            f"{float(row['elo_max']):.3f}"
        )
    recommendation = payload["summary"]["recommended_calibrated_elo_v3_candidate"]
    print(f"recommended_alpha: {float(recommendation['alpha']):.2f}")


if __name__ == "__main__":
    main()
