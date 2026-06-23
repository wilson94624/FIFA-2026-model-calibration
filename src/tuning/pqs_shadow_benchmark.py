from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Iterable
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model.expected_goals import MIN_XG
from src.model.poisson import GAMMA, outcome_probabilities, score_matrix
from src.tuning.tune_dixon_coles_rho import CALIBRATED_XG_WORLDCUP_V1, LOW_SCORELINES, score_probability
from src.tuning.worldcup_xg_parameter_search import neutral_symmetric_xg

PQS_WEIGHTS = (0.00, 0.10, 0.20, 0.25, 0.30)
FIXED_RHO = 0.05
FIXED_GAMMA = GAMMA

REPORT_COLUMNS = [
    "match_id",
    "team_a",
    "team_b",
    "pqs_weight",
    "baseline_team_a_xg",
    "baseline_team_b_xg",
    "pqs_team_a_xg",
    "pqs_team_b_xg",
    "team_a_xg_delta",
    "team_b_xg_delta",
    "baseline_home_or_team_a_win_prob",
    "pqs_home_or_team_a_win_prob",
    "win_prob_delta",
    "draw_prob_delta",
    "low_score_prob_delta",
    "score_matrix_mean_abs_delta",
    "pqs_data_status",
    "warnings",
]

SCHEMA_HEADERS = {
    "data/schema/teams_db_snapshot_schema.csv": [
        "snapshot_id",
        "snapshot_date",
        "team_key",
        "team_name",
        "has_data",
        "starting_pqs",
        "bench_pqs",
        "fifa_points",
        "style",
        "source",
        "notes",
    ],
    "data/schema/player_ratings_schema.csv": [
        "snapshot_id",
        "snapshot_date",
        "team_key",
        "player_id",
        "player_name",
        "position",
        "overall",
        "efficiency_score",
        "rating_source",
        "rating_timestamp",
        "is_in_squad_pool",
        "notes",
    ],
    "data/schema/match_roster_schema.csv": [
        "match_id",
        "match_date",
        "team_key",
        "player_id",
        "player_name",
        "roster_status",
        "position",
        "source",
        "lineup_confirmed",
        "notes",
    ],
    "data/schema/unavailable_players_schema.csv": [
        "match_id",
        "match_date",
        "team_key",
        "player_id",
        "player_name",
        "unavailable_reason",
        "status_confidence",
        "reported_at",
        "source",
        "notes",
    ],
    "data/schema/fatigue_state_schema.csv": [
        "match_id",
        "match_date",
        "team_key",
        "pre_match_fatigue",
        "fatigue_method",
        "prior_matches_counted",
        "extra_time_prior",
        "bench_pqs_used",
        "source",
        "notes",
    ],
    "data/schema/team_name_mapping_schema.csv": [
        "source_team_name",
        "source_system",
        "team_key",
        "teams_db_name",
        "valid_from",
        "valid_to",
        "mapping_confidence",
        "notes",
    ],
}


def read_csv_rows(path: Path, required: bool = True) -> list[dict[str, str]]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_date(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def parse_timestamp(value: str) -> datetime:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("timestamp is required")
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(cleaned).replace(tzinfo=None)
    except ValueError:
        return datetime.combine(parse_date(cleaned), time.min)


def truthy(value: str) -> bool:
    return value.strip().upper() in {"TRUE", "1", "YES", "Y"}


def row_value(row: dict[str, str], *names: str, default: str = "") -> str:
    for name in names:
        if name in row and row[name] != "":
            return row[name]
    return default


def low_score_probability(matrix: list[dict[str, float | int]]) -> float:
    return sum(score_probability(matrix, home, away) for home, away in LOW_SCORELINES)


def matrix_mean_abs_delta(
    baseline: list[dict[str, float | int]],
    adjusted: list[dict[str, float | int]],
) -> float:
    if len(baseline) != len(adjusted):
        raise ValueError("score matrices must have the same length")
    return sum(
        abs(float(base["probability"]) - float(adj["probability"]))
        for base, adj in zip(baseline, adjusted, strict=True)
    ) / len(baseline)


def mapping_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], str]:
    mapping: dict[tuple[str, str], str] = {}
    for row in rows:
        mapping[(row["source_team_name"], row["source_system"])] = row["team_key"]
    return mapping


def team_key_for(
    team_name: str,
    source_system: str,
    mapping: dict[tuple[str, str], str],
) -> str | None:
    return mapping.get((team_name, source_system)) or mapping.get((team_name, "fixture"))


def latest_eligible_snapshot(
    team_key: str,
    match_date: date,
    snapshots: list[dict[str, str]],
) -> dict[str, str] | None:
    eligible = [
        row
        for row in snapshots
        if row.get("team_key") == team_key and parse_date(row["snapshot_date"]) <= match_date
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda row: parse_date(row["snapshot_date"]))


def valid_player_ratings(
    snapshot_id: str,
    team_key: str,
    prediction_timestamp: datetime,
    player_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    return [
        row
        for row in player_rows
        if row.get("snapshot_id") == snapshot_id
        and row.get("team_key") == team_key
        and parse_timestamp(row["rating_timestamp"]) <= prediction_timestamp
    ]


def rows_for_match_team(
    rows: Iterable[dict[str, str]],
    match_id: str,
    team_key: str,
) -> list[dict[str, str]]:
    return [row for row in rows if row.get("match_id") == match_id and row.get("team_key") == team_key]


def unavailable_for_team(
    rows: list[dict[str, str]],
    prediction_timestamp: datetime,
    warnings: list[str],
) -> tuple[set[str], set[str]]:
    unavailable_ids: set[str] = set()
    unavailable_names: set[str] = set()
    for row in rows:
        reported_at = row.get("reported_at", "")
        if not reported_at:
            warnings.append("unavailable_player_missing_reported_at")
            continue
        if parse_timestamp(reported_at) > prediction_timestamp:
            warnings.append(f"future_unavailable_report_ignored:{row.get('player_name', '')}")
            continue
        if row.get("player_id"):
            unavailable_ids.add(row["player_id"])
        if row.get("player_name"):
            unavailable_names.add(row["player_name"].casefold())
    return unavailable_ids, unavailable_names


def fatigue_for_team(rows: list[dict[str, str]]) -> float:
    if not rows:
        return 0.0
    return max(0.0, min(0.35, float(rows[0].get("pre_match_fatigue") or 0.0)))


def calculate_active_pqs(
    team_key: str,
    snapshot: dict[str, str],
    player_rows: list[dict[str, str]],
    roster_rows: list[dict[str, str]],
    unavailable_ids: set[str],
    unavailable_names: set[str],
    fatigue: float,
    warnings: list[str],
) -> tuple[float, float, float] | None:
    if not truthy(snapshot.get("has_data", "")):
        warnings.append(f"team_has_no_player_data:{team_key}")
        return None
    if not player_rows:
        warnings.append(f"missing_player_ratings:{team_key}")
        return None

    players_by_id = {row["player_id"]: row for row in player_rows if row.get("player_id")}
    active_players = [
        row
        for row in player_rows
        if row.get("player_id") not in unavailable_ids
        and row.get("player_name", "").casefold() not in unavailable_names
    ]
    if not active_players:
        warnings.append(f"all_players_unavailable:{team_key}")
        return None

    starting_ids = [
        row["player_id"]
        for row in roster_rows
        if row.get("roster_status") == "starting_xi" and row.get("player_id")
    ]
    bench_ids = [
        row["player_id"]
        for row in roster_rows
        if row.get("roster_status") == "bench" and row.get("player_id")
    ]
    if starting_ids:
        starters = [
            players_by_id[player_id]
            for player_id in starting_ids
            if player_id in players_by_id
            and player_id not in unavailable_ids
            and players_by_id[player_id].get("player_name", "").casefold() not in unavailable_names
        ]
        missing_starters = set(starting_ids) - {row["player_id"] for row in starters}
        if missing_starters:
            warnings.append(f"missing_or_unavailable_starting_players:{team_key}:{len(missing_starters)}")
        bench = [
            players_by_id[player_id]
            for player_id in bench_ids
            if player_id in players_by_id
            and player_id not in unavailable_ids
            and players_by_id[player_id].get("player_name", "").casefold() not in unavailable_names
        ]
    else:
        sorted_active = sorted(
            active_players,
            key=lambda row: float(row.get("efficiency_score") or 0.0),
            reverse=True,
        )
        starters = sorted_active[:11]
        bench = sorted_active[11:]

    if not starters:
        warnings.append(f"missing_active_starters:{team_key}")
        return None

    attackers = [row for row in starters if row.get("position") in {"FW", "MF"}]
    defenders = [row for row in starters if row.get("position") in {"DF", "GK"}]
    fallback = float(snapshot.get("starting_pqs") or 0.25)
    attack = (
        sum(float(row.get("efficiency_score") or 0.0) for row in attackers) / len(attackers)
        if attackers
        else fallback
    )
    defense = (
        sum(float(row.get("efficiency_score") or 0.0) for row in defenders) / len(defenders)
        if defenders
        else fallback
    )
    bench_score = (
        sum(float(row.get("efficiency_score") or 0.0) for row in bench) / len(bench)
        if bench
        else float(snapshot.get("bench_pqs") or 0.2)
    )
    return attack * (1.0 - fatigue), defense * (1.0 - fatigue), bench_score


def fixture_context(row: dict[str, str]) -> dict[str, Any]:
    match_date_text = row_value(row, "match_date", "date")
    prediction_text = row_value(row, "prediction_timestamp", "prediction_time")
    if not prediction_text:
        raise ValueError("fixture rows must include prediction_timestamp for PQS time safety")
    return {
        "match_id": row_value(row, "match_id", default=f"{row_value(row, 'team_a', 'home_team')}_{row_value(row, 'team_b', 'away_team')}_{match_date_text}"),
        "match_date": parse_date(match_date_text),
        "prediction_timestamp": parse_timestamp(prediction_text),
        "team_a": row_value(row, "team_a", "home_team"),
        "team_b": row_value(row, "team_b", "away_team"),
        "team_a_elo": float(row_value(row, "team_a_pre_match_elo", "home_pre_match_elo")),
        "team_b_elo": float(row_value(row, "team_b_pre_match_elo", "away_pre_match_elo")),
        "source_system": row_value(row, "source_system", default="fixture"),
    }


def pqs_for_fixture_team(
    team_name: str,
    context: dict[str, Any],
    mapping: dict[tuple[str, str], str],
    snapshots: list[dict[str, str]],
    player_rows: list[dict[str, str]],
    roster_rows: list[dict[str, str]],
    unavailable_rows: list[dict[str, str]],
    fatigue_rows: list[dict[str, str]],
    warnings: list[str],
) -> tuple[str | None, tuple[float, float, float] | None]:
    team_key = team_key_for(team_name, str(context["source_system"]), mapping)
    if not team_key:
        warnings.append(f"missing_team_mapping:{team_name}")
        return None, None

    snapshot = latest_eligible_snapshot(team_key, context["match_date"], snapshots)
    if snapshot is None:
        warnings.append(f"missing_time_safe_snapshot:{team_key}")
        return team_key, None

    valid_ratings = valid_player_ratings(
        snapshot["snapshot_id"],
        team_key,
        context["prediction_timestamp"],
        player_rows,
    )
    if not valid_ratings:
        warnings.append(f"missing_time_safe_player_ratings:{team_key}")
        return team_key, None

    team_roster_rows = rows_for_match_team(roster_rows, str(context["match_id"]), team_key)
    team_unavailable_rows = rows_for_match_team(unavailable_rows, str(context["match_id"]), team_key)
    unavailable_ids, unavailable_names = unavailable_for_team(
        team_unavailable_rows,
        context["prediction_timestamp"],
        warnings,
    )
    team_fatigue_rows = rows_for_match_team(fatigue_rows, str(context["match_id"]), team_key)
    fatigue = fatigue_for_team(team_fatigue_rows)
    pqs = calculate_active_pqs(
        team_key,
        snapshot,
        valid_ratings,
        team_roster_rows,
        unavailable_ids,
        unavailable_names,
        fatigue,
        warnings,
    )
    return team_key, pqs


def evaluate_fixture_weight(
    context: dict[str, Any],
    pqs_weight: float,
    pqs_a: tuple[float, float, float] | None,
    pqs_b: tuple[float, float, float] | None,
    warnings: list[str],
) -> dict[str, Any]:
    baseline_a_xg, baseline_b_xg = neutral_symmetric_xg(
        float(context["team_a_elo"]),
        float(context["team_b_elo"]),
        base=float(CALIBRATED_XG_WORLDCUP_V1["base"]),
        c1=float(CALIBRATED_XG_WORLDCUP_V1["c1"]),
        scale=float(CALIBRATED_XG_WORLDCUP_V1["scale"]),
    )
    pqs_data_ok = pqs_a is not None and pqs_b is not None
    data_status = "ok" if pqs_data_ok else "missing_pqs_data"

    if pqs_weight == 0.0 or not pqs_data_ok:
        pqs_a_xg, pqs_b_xg = baseline_a_xg, baseline_b_xg
    else:
        attack_a, defense_a, _ = pqs_a
        attack_b, defense_b, _ = pqs_b
        pqs_a_xg = max(
            MIN_XG,
            baseline_a_xg + pqs_weight * (attack_a - defense_b) / 0.3,
        )
        pqs_b_xg = max(
            MIN_XG,
            baseline_b_xg + pqs_weight * (attack_b - defense_a) / 0.3,
        )

    baseline_matrix = score_matrix(baseline_a_xg, baseline_b_xg, gamma=FIXED_GAMMA, rho=FIXED_RHO)
    pqs_matrix = score_matrix(pqs_a_xg, pqs_b_xg, gamma=FIXED_GAMMA, rho=FIXED_RHO)
    baseline_probs = outcome_probabilities(baseline_matrix)
    pqs_probs = outcome_probabilities(pqs_matrix)

    return {
        "match_id": context["match_id"],
        "team_a": context["team_a"],
        "team_b": context["team_b"],
        "pqs_weight": pqs_weight,
        "baseline_team_a_xg": baseline_a_xg,
        "baseline_team_b_xg": baseline_b_xg,
        "pqs_team_a_xg": pqs_a_xg,
        "pqs_team_b_xg": pqs_b_xg,
        "team_a_xg_delta": pqs_a_xg - baseline_a_xg,
        "team_b_xg_delta": pqs_b_xg - baseline_b_xg,
        "baseline_home_or_team_a_win_prob": baseline_probs["home"],
        "pqs_home_or_team_a_win_prob": pqs_probs["home"],
        "win_prob_delta": pqs_probs["home"] - baseline_probs["home"],
        "draw_prob_delta": pqs_probs["draw"] - baseline_probs["draw"],
        "low_score_prob_delta": low_score_probability(pqs_matrix)
        - low_score_probability(baseline_matrix),
        "score_matrix_mean_abs_delta": matrix_mean_abs_delta(baseline_matrix, pqs_matrix),
        "pqs_data_status": data_status,
        "warnings": ";".join(sorted(set(warnings))),
    }


def build_pqs_shadow_benchmark(
    fixtures_path: Path,
    teams_db_snapshot_path: Path,
    player_ratings_path: Path,
    team_mapping_path: Path,
    match_roster_path: Path | None = None,
    unavailable_players_path: Path | None = None,
    fatigue_state_path: Path | None = None,
    pqs_weights: tuple[float, ...] = PQS_WEIGHTS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fixtures = read_csv_rows(fixtures_path)
    snapshots = read_csv_rows(teams_db_snapshot_path)
    player_rows = read_csv_rows(player_ratings_path)
    mappings = mapping_lookup(read_csv_rows(team_mapping_path))
    roster_rows = read_csv_rows(match_roster_path, required=False) if match_roster_path else []
    unavailable_rows = (
        read_csv_rows(unavailable_players_path, required=False) if unavailable_players_path else []
    )
    fatigue_rows = read_csv_rows(fatigue_state_path, required=False) if fatigue_state_path else []

    output_rows: list[dict[str, Any]] = []
    missing_pqs_matches = 0
    for fixture in fixtures:
        context = fixture_context(fixture)
        warnings: list[str] = []
        _, pqs_a = pqs_for_fixture_team(
            str(context["team_a"]),
            context,
            mappings,
            snapshots,
            player_rows,
            roster_rows,
            unavailable_rows,
            fatigue_rows,
            warnings,
        )
        _, pqs_b = pqs_for_fixture_team(
            str(context["team_b"]),
            context,
            mappings,
            snapshots,
            player_rows,
            roster_rows,
            unavailable_rows,
            fatigue_rows,
            warnings,
        )
        if pqs_a is None or pqs_b is None:
            missing_pqs_matches += 1
        for weight in pqs_weights:
            output_rows.append(evaluate_fixture_weight(context, weight, pqs_a, pqs_b, list(warnings)))

    payload = {
        "model": {
            "baseline": "final_worldcup_model_v1_candidate_without_pqs",
            "elo": "calibrated_elo_v3_candidate",
            "xg": "calibrated_xg_worldcup_v1_candidate",
            "rho": FIXED_RHO,
            "gamma": FIXED_GAMMA,
            "pqs_mode": "shadow_additive_xg_layer",
        },
        "inputs": {
            "fixtures": str(fixtures_path),
            "teams_db_snapshot": str(teams_db_snapshot_path),
            "player_ratings": str(player_ratings_path),
            "team_mapping": str(team_mapping_path),
            "match_roster": str(match_roster_path) if match_roster_path else None,
            "unavailable_players": str(unavailable_players_path) if unavailable_players_path else None,
            "fatigue_state": str(fatigue_state_path) if fatigue_state_path else None,
        },
        "pqs_weights": list(pqs_weights),
        "rows": output_rows,
        "summary": {
            "fixtures": len(fixtures),
            "rows": len(output_rows),
            "missing_pqs_matches": missing_pqs_matches,
            "can_claim_pqs_calibrated": False,
            "outputs_accuracy_claim": False,
        },
    }
    return output_rows, payload


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


def _parse_float_tuple(values: list[str] | None, default: tuple[float, ...]) -> tuple[float, ...]:
    if not values:
        return default
    return tuple(float(value) for value in values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PQS shadow benchmark drift outputs.")
    parser.add_argument("--fixtures", type=Path, default=Path("data/processed/worldcup_shadow_fixtures.csv"))
    parser.add_argument("--teams-db-snapshot", type=Path, default=Path("data/processed/teams_db_snapshot.csv"))
    parser.add_argument("--player-ratings", type=Path, default=Path("data/processed/player_ratings.csv"))
    parser.add_argument("--team-mapping", type=Path, default=Path("data/processed/team_name_mapping.csv"))
    parser.add_argument("--match-roster", type=Path)
    parser.add_argument("--unavailable-players", type=Path)
    parser.add_argument("--fatigue-state", type=Path)
    parser.add_argument("--pqs-weight", action="append", help="Candidate PQS additive xG weight.")
    parser.add_argument("--output-csv", type=Path, default=Path("results/pqs_shadow_benchmark.csv"))
    parser.add_argument("--output-json", type=Path, default=Path("results/pqs_shadow_benchmark.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, payload = build_pqs_shadow_benchmark(
        args.fixtures,
        args.teams_db_snapshot,
        args.player_ratings,
        args.team_mapping,
        match_roster_path=args.match_roster,
        unavailable_players_path=args.unavailable_players,
        fatigue_state_path=args.fatigue_state,
        pqs_weights=_parse_float_tuple(args.pqs_weight, PQS_WEIGHTS),
    )
    write_outputs(rows, payload, args.output_csv, args.output_json)
    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    print(f"fixtures: {payload['summary']['fixtures']}")
    print(f"rows: {payload['summary']['rows']}")
    print(f"missing_pqs_matches: {payload['summary']['missing_pqs_matches']}")


if __name__ == "__main__":
    main()
