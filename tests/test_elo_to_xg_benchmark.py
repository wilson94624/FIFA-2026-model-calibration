import csv
import json
import subprocess
import sys
from pathlib import Path

from src.tuning.elo_to_xg_benchmark import (
    REPORT_COLUMNS,
    build_elo_to_xg_benchmark,
    write_outputs,
)


def write_matches(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "date",
                "home_team",
                "away_team",
                "home_score",
                "away_score",
                "tournament",
                "city",
                "country",
                "neutral",
            ]
        )
        writer.writerow(["2020-01-01", "Argentina", "Brazil", "2", "0", "Friendly", "", "", "FALSE"])
        writer.writerow(["2020-01-02", "Spain", "France", "1", "1", "Friendly", "", "", "TRUE"])
        writer.writerow(["2020-01-03", "Norway", "Brazil", "0", "2", "Friendly", "", "", "FALSE"])
        writer.writerow(["2020-01-04", "Jersey", "Brazil", "1", "0", "Friendly", "", "", "FALSE"])


def write_universe(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["team", "category", "include_fifa_only", "include_fifa_historical", "notes"])
        writer.writerow(["Argentina", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Brazil", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Spain", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["France", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Norway", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Jersey", "regional", "FALSE", "FALSE", ""])


def test_build_elo_to_xg_benchmark_filters_and_scores(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    write_matches(matches)
    write_universe(universe)

    rows, payload = build_elo_to_xg_benchmark(matches, universe)

    assert len(rows) == 3
    assert rows[0]["matches"] == 3
    assert "best_poisson_log_loss" in payload["summary"]
    assert payload["universe"]["name"] == "fifa_historical"
    assert "expected_goals_formula" in payload


def test_write_elo_to_xg_outputs(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "elo_to_xg.csv"
    json_path = tmp_path / "elo_to_xg.json"
    write_matches(matches)
    write_universe(universe)
    rows, payload = build_elo_to_xg_benchmark(matches, universe)

    write_outputs(rows, payload, csv_path, json_path)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output_rows = list(reader)
    parsed = json.loads(json_path.read_text(encoding="utf-8"))

    assert reader.fieldnames == REPORT_COLUMNS
    assert len(output_rows) == 3
    assert "sample_predictions" in parsed["models"]["standard_elo_v1"]


def test_elo_to_xg_cli(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "elo_to_xg.csv"
    json_path = tmp_path / "elo_to_xg.json"
    write_matches(matches)
    write_universe(universe)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/elo_to_xg_benchmark.py",
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
    assert "best_poisson_log_loss:" in result.stdout
