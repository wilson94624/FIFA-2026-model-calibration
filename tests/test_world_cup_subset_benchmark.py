import csv
import json
import subprocess
import sys
from pathlib import Path

from src.tuning.world_cup_subset_benchmark import (
    REPORT_COLUMNS,
    build_subset_benchmark,
    write_outputs,
)


def write_fixture(path: Path) -> None:
    tournaments = [
        "FIFA World Cup",
        "UEFA Euro",
        "Copa América",
        "AFC Asian Cup",
        "African Cup of Nations",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "home_team", "away_team", "home_score", "away_score", "tournament"])
        for index, tournament in enumerate(tournaments, start=1):
            writer.writerow([f"2020-01-0{index}", "Alpha", "Beta", "2", "0", tournament])
            writer.writerow([f"2020-02-0{index}", "Gamma", "Alpha", "1", "1", tournament])


def test_build_subset_benchmark_outputs_all_target_tournaments(tmp_path: Path) -> None:
    input_path = tmp_path / "matches.csv"
    write_fixture(input_path)

    rows, payload = build_subset_benchmark(input_path)

    assert len(rows) == 10
    assert set(REPORT_COLUMNS).issubset(rows[0])
    assert set(payload["per_tournament"]) == {
        "FIFA World Cup Finals",
        "UEFA Euro",
        "Copa América",
        "AFC Asian Cup",
        "African Cup of Nations",
    }
    assert "fifa_level_team_scale" in payload
    assert "anomaly_cases" in payload


def test_write_subset_benchmark_outputs(tmp_path: Path) -> None:
    input_path = tmp_path / "matches.csv"
    csv_path = tmp_path / "subset.csv"
    json_path = tmp_path / "subset.json"
    write_fixture(input_path)
    rows, payload = build_subset_benchmark(input_path)

    write_outputs(rows, payload, csv_path, json_path)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output_rows = list(reader)
    parsed = json.loads(json_path.read_text(encoding="utf-8"))

    assert reader.fieldnames == REPORT_COLUMNS
    assert len(output_rows) == 10
    assert parsed["recommendation"]["verdict"] == "B"


def test_world_cup_subset_benchmark_cli(tmp_path: Path) -> None:
    input_path = tmp_path / "matches.csv"
    csv_path = tmp_path / "subset.csv"
    json_path = tmp_path / "subset.json"
    write_fixture(input_path)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/world_cup_subset_benchmark.py",
            "--input",
            str(input_path),
            "--output-csv",
            str(csv_path),
            "--output-json",
            str(json_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    assert csv_path.exists()
    assert json_path.exists()
    assert "FIFA World Cup Finals" in result.stdout
    assert "verdict:" in result.stdout
