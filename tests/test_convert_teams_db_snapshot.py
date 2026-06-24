import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.convert_teams_db_snapshot import (
    convert_teams_db,
    team_key_for,
    write_processed_outputs,
)

REAL_TEAMS_DB = Path("/Users/wilson/Desktop/FIFA-2026-prediction-3.0/frontend/src/teams_db.json")


def sample_teams_db() -> dict[str, dict]:
    return {
        "USA": {
            "team_name": "USA",
            "has_data": True,
            "starting_pqs": 0.3,
            "bench_pqs": 0.2,
            "fifa_points": 1800,
            "style": "Standard",
            "players": [
                {"name": "A. Keeper", "position": "GK", "overall": 80, "efficiency_score": 0.30},
                {"name": "A. Forward", "position": "FW", "overall": 82, "efficiency_score": 0.32},
            ],
        },
        "Czechia": {
            "team_name": "Czechia",
            "has_data": True,
            "starting_pqs": 0.25,
            "bench_pqs": 0.18,
            "fifa_points": 1700,
            "style": "Possession",
            "players": [
                {"name": "B. Keeper", "position": "GK", "overall": 78, "efficiency_score": 0.28},
                {"name": "B. Defender", "position": "DF", "overall": 76, "efficiency_score": 0.26},
            ],
        },
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_real_teams_db_converts_48_teams_and_1248_players() -> None:
    if not REAL_TEAMS_DB.exists():
        pytest.skip("real FIFA Predictor teams_db.json is not available")

    team_rows, player_rows, mapping_rows = convert_teams_db(
        REAL_TEAMS_DB,
        "teams_db_2026_worldcup_pre_tournament_v1",
        "2026-06-01",
        "2026-06-01T00:00:00",
        "FIFA Predictor 4.0 teams_db.json",
    )

    assert len(team_rows) == 48
    assert len(player_rows) == 1248
    assert len(mapping_rows) >= 48


def test_required_team_field_missing_raises_clear_error(tmp_path: Path) -> None:
    payload = sample_teams_db()
    del payload["USA"]["style"]
    path = tmp_path / "teams_db.json"
    write_json(path, payload)

    with pytest.raises(ValueError, match="team 'USA' missing required fields"):
        convert_teams_db(path, "snap", "2026-06-01", "2026-06-01T00:00:00", "test")


def test_required_player_field_missing_raises_clear_error(tmp_path: Path) -> None:
    payload = sample_teams_db()
    del payload["USA"]["players"][0]["efficiency_score"]
    path = tmp_path / "teams_db.json"
    write_json(path, payload)

    with pytest.raises(ValueError, match="team 'USA' player #1 missing required fields"):
        convert_teams_db(path, "snap", "2026-06-01", "2026-06-01T00:00:00", "test")


def test_team_key_overrides() -> None:
    assert team_key_for("USA") == "united_states"
    assert team_key_for("Czechia") == "czech_republic"
    assert team_key_for("Cabo Verde") == "cape_verde"
    assert team_key_for("Congo DR") == "dr_congo"
    assert team_key_for("Curacao") == "curacao"
    assert team_key_for("South Korea") == "south_korea"
    assert team_key_for("South Africa") == "south_africa"
    assert team_key_for("Bosnia and Herzegovina") == "bosnia_and_herzegovina"


def test_snapshot_date_and_rating_timestamp_are_written(tmp_path: Path) -> None:
    path = tmp_path / "teams_db.json"
    write_json(path, sample_teams_db())

    team_rows, player_rows, _ = convert_teams_db(
        path,
        "snap_v1",
        "2026-06-01",
        "2026-06-01T12:30:00",
        "test source",
    )

    assert {row["snapshot_date"] for row in team_rows} == {"2026-06-01"}
    assert {row["snapshot_id"] for row in player_rows} == {"snap_v1"}
    assert {row["rating_timestamp"] for row in player_rows} == {"2026-06-01T12:30:00"}


def test_output_headers_and_alias_mappings(tmp_path: Path) -> None:
    input_path = tmp_path / "teams_db.json"
    output_dir = tmp_path / "processed"
    write_json(input_path, sample_teams_db())

    team_rows, player_rows, mapping_rows = convert_teams_db(
        input_path,
        "snap",
        "2026-06-01",
        "2026-06-01T00:00:00",
        "test",
    )
    teams_path, players_path, mapping_path = write_processed_outputs(
        team_rows,
        player_rows,
        mapping_rows,
        output_dir,
    )

    with teams_path.open("r", encoding="utf-8", newline="") as handle:
        assert next(csv.reader(handle)) == [
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
    with players_path.open("r", encoding="utf-8", newline="") as handle:
        assert next(csv.reader(handle))[0:4] == ["snapshot_id", "snapshot_date", "team_key", "player_id"]

    mapping = list(csv.DictReader(mapping_path.open("r", encoding="utf-8", newline="")))
    assert any(row["source_team_name"] == "United States" for row in mapping)
    assert any(row["source_team_name"] == "Czech Republic" for row in mapping)


def test_converter_does_not_create_roster_injury_or_fatigue_files(tmp_path: Path) -> None:
    input_path = tmp_path / "teams_db.json"
    output_dir = tmp_path / "processed"
    write_json(input_path, sample_teams_db())
    team_rows, player_rows, mapping_rows = convert_teams_db(
        input_path,
        "snap",
        "2026-06-01",
        "2026-06-01T00:00:00",
        "test",
    )
    write_processed_outputs(team_rows, player_rows, mapping_rows, output_dir)

    assert not (output_dir / "match_roster.csv").exists()
    assert not (output_dir / "unavailable_players.csv").exists()
    assert not (output_dir / "fatigue_state.csv").exists()


def test_cli_requires_snapshot_date_and_rating_timestamp(tmp_path: Path) -> None:
    input_path = tmp_path / "teams_db.json"
    write_json(input_path, sample_teams_db())

    result = subprocess.run(
        [
            sys.executable,
            "scripts/convert_teams_db_snapshot.py",
            "--input",
            str(input_path),
            "--snapshot-id",
            "snap",
            "--source",
            "test",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "--snapshot-date" in result.stderr
    assert "--rating-timestamp" in result.stderr


def test_cli_writes_expected_processed_files(tmp_path: Path) -> None:
    input_path = tmp_path / "teams_db.json"
    output_dir = tmp_path / "processed"
    write_json(input_path, sample_teams_db())

    result = subprocess.run(
        [
            sys.executable,
            "scripts/convert_teams_db_snapshot.py",
            "--input",
            str(input_path),
            "--snapshot-id",
            "snap",
            "--snapshot-date",
            "2026-06-01",
            "--rating-timestamp",
            "2026-06-01T00:00:00",
            "--source",
            "test",
            "--output-dir",
            str(output_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    assert (output_dir / "teams_db_snapshot.csv").exists()
    assert (output_dir / "player_ratings.csv").exists()
    assert (output_dir / "team_name_mapping.csv").exists()
    assert "pqs_calibration_completed: false" in result.stdout
