import csv
import json
import subprocess
import sys
from pathlib import Path

from src.tuning.pqs_shadow_benchmark import (
    SCHEMA_HEADERS,
    build_pqs_shadow_benchmark,
    write_outputs,
)


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def write_fixture(path: Path) -> None:
    write_csv(
        path,
        [
            "match_id",
            "match_date",
            "prediction_timestamp",
            "team_a",
            "team_b",
            "team_a_pre_match_elo",
            "team_b_pre_match_elo",
            "source_system",
        ],
        [["m1", "2026-06-11", "2026-06-10T12:00:00", "Argentina", "Brazil", "1900", "1800", "fixture"]],
    )


def write_mapping(path: Path) -> None:
    write_csv(
        path,
        SCHEMA_HEADERS["data/schema/team_name_mapping_schema.csv"],
        [
            ["Argentina", "fixture", "ARG", "Argentina", "", "", "exact", ""],
            ["Brazil", "fixture", "BRA", "Brazil", "", "", "exact", ""],
        ],
    )


def write_snapshots(path: Path, snapshot_date: str = "2026-06-01") -> None:
    write_csv(
        path,
        SCHEMA_HEADERS["data/schema/teams_db_snapshot_schema.csv"],
        [
            ["snap1", snapshot_date, "ARG", "Argentina", "TRUE", "0.75", "0.65", "", "", "test", ""],
            ["snap1", snapshot_date, "BRA", "Brazil", "TRUE", "0.65", "0.60", "", "", "test", ""],
        ],
    )


def write_ratings(path: Path) -> None:
    rows = []
    for team_key, prefix, attack, defense in (
        ("ARG", "arg", "0.90", "0.70"),
        ("BRA", "bra", "0.70", "0.50"),
    ):
        rows.extend(
            [
                ["snap1", "2026-06-01", team_key, f"{prefix}_fw", f"{prefix} FW", "FW", "", attack, "test", "2026-06-01T00:00:00", "TRUE", ""],
                ["snap1", "2026-06-01", team_key, f"{prefix}_mf", f"{prefix} MF", "MF", "", attack, "test", "2026-06-01T00:00:00", "TRUE", ""],
                ["snap1", "2026-06-01", team_key, f"{prefix}_df", f"{prefix} DF", "DF", "", defense, "test", "2026-06-01T00:00:00", "TRUE", ""],
                ["snap1", "2026-06-01", team_key, f"{prefix}_gk", f"{prefix} GK", "GK", "", defense, "test", "2026-06-01T00:00:00", "TRUE", ""],
            ]
        )
    write_csv(path, SCHEMA_HEADERS["data/schema/player_ratings_schema.csv"], rows)


def base_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    fixtures = tmp_path / "fixtures.csv"
    snapshots = tmp_path / "snapshots.csv"
    ratings = tmp_path / "ratings.csv"
    mapping = tmp_path / "mapping.csv"
    write_fixture(fixtures)
    write_snapshots(snapshots)
    write_ratings(ratings)
    write_mapping(mapping)
    return fixtures, snapshots, ratings, mapping


def test_schema_headers_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    for relative_path, expected_header in SCHEMA_HEADERS.items():
        path = root / relative_path
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            assert next(reader) == expected_header
            assert list(reader) == []


def test_time_safety_rejects_future_snapshots(tmp_path: Path) -> None:
    fixtures, snapshots, ratings, mapping = base_inputs(tmp_path)
    write_snapshots(snapshots, snapshot_date="2026-07-01")

    rows, payload = build_pqs_shadow_benchmark(
        fixtures,
        snapshots,
        ratings,
        mapping,
        pqs_weights=(0.10,),
    )

    assert payload["summary"]["missing_pqs_matches"] == 1
    assert rows[0]["pqs_data_status"] == "missing_pqs_data"
    assert "missing_time_safe_snapshot" in rows[0]["warnings"]


def test_missing_pqs_data_does_not_crash(tmp_path: Path) -> None:
    fixtures, snapshots, ratings, mapping = base_inputs(tmp_path)
    ratings.write_text(",".join(SCHEMA_HEADERS["data/schema/player_ratings_schema.csv"]) + "\n", encoding="utf-8")

    rows, payload = build_pqs_shadow_benchmark(
        fixtures,
        snapshots,
        ratings,
        mapping,
        pqs_weights=(0.10,),
    )

    assert payload["summary"]["missing_pqs_matches"] == 1
    assert rows[0]["pqs_data_status"] == "missing_pqs_data"
    assert rows[0]["team_a_xg_delta"] == 0.0
    assert rows[0]["team_b_xg_delta"] == 0.0


def test_pqs_weight_zero_produces_zero_drift(tmp_path: Path) -> None:
    fixtures, snapshots, ratings, mapping = base_inputs(tmp_path)

    rows, _ = build_pqs_shadow_benchmark(
        fixtures,
        snapshots,
        ratings,
        mapping,
        pqs_weights=(0.0,),
    )

    assert rows[0]["pqs_data_status"] == "ok"
    assert rows[0]["team_a_xg_delta"] == 0.0
    assert rows[0]["team_b_xg_delta"] == 0.0
    assert rows[0]["win_prob_delta"] == 0.0
    assert rows[0]["score_matrix_mean_abs_delta"] == 0.0


def test_positive_attack_vs_defense_pqs_diff_increases_xg(tmp_path: Path) -> None:
    fixtures, snapshots, ratings, mapping = base_inputs(tmp_path)

    rows, _ = build_pqs_shadow_benchmark(
        fixtures,
        snapshots,
        ratings,
        mapping,
        pqs_weights=(0.10,),
    )

    assert rows[0]["pqs_data_status"] == "ok"
    assert rows[0]["team_a_xg_delta"] > 0.0
    assert rows[0]["pqs_team_a_xg"] > rows[0]["baseline_team_a_xg"]


def test_write_outputs_and_cli(tmp_path: Path) -> None:
    fixtures, snapshots, ratings, mapping = base_inputs(tmp_path)
    csv_path = tmp_path / "pqs_shadow.csv"
    json_path = tmp_path / "pqs_shadow.json"
    rows, payload = build_pqs_shadow_benchmark(
        fixtures,
        snapshots,
        ratings,
        mapping,
        pqs_weights=(0.0, 0.10),
    )

    write_outputs(rows, payload, csv_path, json_path)
    parsed = json.loads(json_path.read_text(encoding="utf-8"))

    assert csv_path.exists()
    assert parsed["summary"]["can_claim_pqs_calibrated"] is False

    cli_csv = tmp_path / "cli.csv"
    cli_json = tmp_path / "cli.json"
    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/pqs_shadow_benchmark.py",
            "--fixtures",
            str(fixtures),
            "--teams-db-snapshot",
            str(snapshots),
            "--player-ratings",
            str(ratings),
            "--team-mapping",
            str(mapping),
            "--pqs-weight",
            "0.0",
            "--output-csv",
            str(cli_csv),
            "--output-json",
            str(cli_json),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    assert cli_csv.exists()
    assert cli_json.exists()
    assert "missing_pqs_matches:" in result.stdout
