from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TEAM_SNAPSHOT_COLUMNS = [
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
]
PLAYER_RATINGS_COLUMNS = [
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
]
TEAM_MAPPING_COLUMNS = [
    "source_team_name",
    "source_system",
    "team_key",
    "teams_db_name",
    "valid_from",
    "valid_to",
    "mapping_confidence",
    "notes",
]

TEAM_REQUIRED_FIELDS = (
    "team_name",
    "has_data",
    "starting_pqs",
    "bench_pqs",
    "fifa_points",
    "style",
    "players",
)
PLAYER_REQUIRED_FIELDS = ("name", "position", "overall", "efficiency_score")

TEAM_KEY_OVERRIDES = {
    "USA": "united_states",
    "Czechia": "czech_republic",
    "Cabo Verde": "cape_verde",
    "Congo DR": "dr_congo",
    "Curacao": "curacao",
    "South Korea": "south_korea",
    "South Africa": "south_africa",
}

INTERNATIONAL_RESULTS_ALIASES = {
    "USA": "United States",
    "Czechia": "Czech Republic",
    "Cabo Verde": "Cape Verde",
    "Congo DR": "DR Congo",
    "Curacao": "Curaçao",
}


def normalize_slug(value: str) -> str:
    normalized = value.casefold()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def team_key_for(team_name: str) -> str:
    return TEAM_KEY_OVERRIDES.get(team_name, normalize_slug(team_name))


def player_id_for(team_key: str, player_name: str, position: str, index: int) -> str:
    return f"{team_key}:{normalize_slug(player_name)}:{position}:{index:03d}"


def validate_required_fields(
    payload: dict[str, Any],
    required_fields: tuple[str, ...],
    context: str,
) -> None:
    missing = [field for field in required_fields if field not in payload or payload[field] in (None, "")]
    if missing:
        raise ValueError(f"{context} missing required fields: {missing}")


def load_teams_db(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("teams_db JSON root must be an object keyed by team name")
    return data


def build_team_mapping_rows(team_name: str, team_key: str) -> list[dict[str, str]]:
    rows = [
        {
            "source_team_name": team_name,
            "source_system": "teams_db",
            "team_key": team_key,
            "teams_db_name": team_name,
            "valid_from": "",
            "valid_to": "",
            "mapping_confidence": "exact",
            "notes": "",
        },
        {
            "source_team_name": team_name,
            "source_system": "fixture",
            "team_key": team_key,
            "teams_db_name": team_name,
            "valid_from": "",
            "valid_to": "",
            "mapping_confidence": "exact",
            "notes": "teams_db fixture name",
        },
    ]
    alias = INTERNATIONAL_RESULTS_ALIASES.get(team_name)
    if alias:
        rows.append(
            {
                "source_team_name": alias,
                "source_system": "international_results",
                "team_key": team_key,
                "teams_db_name": team_name,
                "valid_from": "",
                "valid_to": "",
                "mapping_confidence": "alias",
                "notes": "common international_results alias",
            }
        )
        rows.append(
            {
                "source_team_name": alias,
                "source_system": "fixture",
                "team_key": team_key,
                "teams_db_name": team_name,
                "valid_from": "",
                "valid_to": "",
                "mapping_confidence": "alias",
                "notes": "common fixture alias",
            }
        )
    return rows


def convert_teams_db(
    input_path: Path,
    snapshot_id: str,
    snapshot_date: str,
    rating_timestamp: str,
    source: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    if not snapshot_id:
        raise ValueError("snapshot_id is required")
    if not snapshot_date:
        raise ValueError("snapshot_date is required")
    if not rating_timestamp:
        raise ValueError("rating_timestamp is required")
    if not source:
        raise ValueError("source is required")

    teams_db = load_teams_db(input_path)
    team_rows: list[dict[str, Any]] = []
    player_rows: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, str]] = []

    for raw_team_name, team in teams_db.items():
        if not isinstance(team, dict):
            raise ValueError(f"team {raw_team_name!r} must be an object")
        validate_required_fields(team, TEAM_REQUIRED_FIELDS, f"team {raw_team_name!r}")
        players = team["players"]
        if not isinstance(players, list):
            raise ValueError(f"team {raw_team_name!r} players must be a list")

        team_name = str(team["team_name"])
        team_key = team_key_for(team_name)
        team_rows.append(
            {
                "snapshot_id": snapshot_id,
                "snapshot_date": snapshot_date,
                "team_key": team_key,
                "team_name": team_name,
                "has_data": str(bool(team["has_data"])).upper(),
                "starting_pqs": team["starting_pqs"],
                "bench_pqs": team["bench_pqs"],
                "fifa_points": team["fifa_points"],
                "style": team["style"],
                "source": source,
                "notes": "",
            }
        )
        mapping_rows.extend(build_team_mapping_rows(team_name, team_key))

        for index, player in enumerate(players, start=1):
            if not isinstance(player, dict):
                raise ValueError(f"team {team_name!r} player #{index} must be an object")
            validate_required_fields(player, PLAYER_REQUIRED_FIELDS, f"team {team_name!r} player #{index}")
            player_name = str(player["name"])
            position = str(player["position"])
            player_rows.append(
                {
                    "snapshot_id": snapshot_id,
                    "snapshot_date": snapshot_date,
                    "team_key": team_key,
                    "player_id": player_id_for(team_key, player_name, position, index),
                    "player_name": player_name,
                    "position": position,
                    "overall": player["overall"],
                    "efficiency_score": player["efficiency_score"],
                    "rating_source": source,
                    "rating_timestamp": rating_timestamp,
                    "is_in_squad_pool": "TRUE",
                    "notes": "",
                }
            )

    return team_rows, player_rows, mapping_rows


def write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_processed_outputs(
    team_rows: list[dict[str, Any]],
    player_rows: list[dict[str, Any]],
    mapping_rows: list[dict[str, str]],
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    teams_path = output_dir / "teams_db_snapshot.csv"
    players_path = output_dir / "player_ratings.csv"
    mapping_path = output_dir / "team_name_mapping.csv"
    write_csv(teams_path, TEAM_SNAPSHOT_COLUMNS, team_rows)
    write_csv(players_path, PLAYER_RATINGS_COLUMNS, player_rows)
    write_csv(mapping_path, TEAM_MAPPING_COLUMNS, mapping_rows)
    return teams_path, players_path, mapping_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert teams_db.json to PQS shadow benchmark CSV inputs.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--snapshot-date", required=True)
    parser.add_argument("--rating-timestamp", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    team_rows, player_rows, mapping_rows = convert_teams_db(
        args.input,
        args.snapshot_id,
        args.snapshot_date,
        args.rating_timestamp,
        args.source,
    )
    teams_path, players_path, mapping_path = write_processed_outputs(
        team_rows,
        player_rows,
        mapping_rows,
        args.output_dir,
    )
    print(f"teams_db_snapshot: {teams_path}")
    print(f"player_ratings: {players_path}")
    print(f"team_name_mapping: {mapping_path}")
    print(f"teams: {len(team_rows)}")
    print(f"players: {len(player_rows)}")
    print("pqs_calibration_completed: false")


if __name__ == "__main__":
    main()
