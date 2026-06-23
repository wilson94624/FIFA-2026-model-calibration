import csv
import json
import subprocess
import sys
from pathlib import Path

from src.tuning.universe_benchmark import REPORT_COLUMNS, build_universe_benchmark, write_outputs


def write_matches(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "home_team", "away_team", "home_score", "away_score"])
        writer.writerow(["2020-01-01", "Alpha", "Beta", "3", "0"])
        writer.writerow(["2020-01-02", "Beta", "Alpha", "1", "1"])
        writer.writerow(["2020-01-03", "Jersey", "Alpha", "0", "2"])


def write_universe(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["team", "category", "include_fifa_only", "include_fifa_historical", "notes"])
        writer.writerow(["Alpha", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Beta", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Jersey", "regional", "FALSE", "FALSE", ""])


def test_build_universe_benchmark_filters_rows(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    write_matches(matches)
    write_universe(universe)

    rows, payload = build_universe_benchmark(matches, universe)

    assert len(rows) == 6
    assert payload["universes"]["all"]["models"]["standard_elo_v1"]["matches"] == 3
    assert payload["universes"]["fifa_only"]["models"]["standard_elo_v1"]["matches"] == 2
    assert payload["universes"]["fifa_historical"]["models"]["standard_elo_v1"]["matches"] == 2
    assert payload["analysis"]["jersey_removed_from_fifa_universes"] is True


def test_write_universe_benchmark_outputs(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "benchmark.csv"
    json_path = tmp_path / "benchmark.json"
    write_matches(matches)
    write_universe(universe)
    rows, payload = build_universe_benchmark(matches, universe)

    write_outputs(rows, payload, csv_path, json_path)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output_rows = list(reader)
    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert reader.fieldnames == REPORT_COLUMNS
    assert len(output_rows) == 6
    assert "universes" in parsed


def test_universe_benchmark_cli(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "benchmark.csv"
    json_path = tmp_path / "benchmark.json"
    write_matches(matches)
    write_universe(universe)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/universe_benchmark.py",
            "--input",
            str(matches),
            "--team-universe",
            str(universe),
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
    assert "fifa_only" in result.stdout
