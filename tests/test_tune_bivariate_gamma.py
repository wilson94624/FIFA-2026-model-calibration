import csv
import json
import subprocess
import sys
from pathlib import Path

from src.tuning.tune_bivariate_gamma import (
    REPORT_COLUMNS,
    search_bivariate_gamma,
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
        writer.writerow(["2020-01-01", "Argentina", "Brazil", "0", "0", "FIFA World Cup", "", "", "TRUE"])
        writer.writerow(["2020-01-02", "Spain", "France", "1", "0", "UEFA Euro", "", "", "TRUE"])
        writer.writerow(["2020-01-03", "Argentina", "France", "0", "1", "FIFA World Cup", "", "", "TRUE"])
        writer.writerow(["2020-01-04", "Spain", "Brazil", "1", "1", "UEFA Euro", "", "", "TRUE"])
        writer.writerow(["2020-01-05", "Argentina", "Brazil", "3", "0", "Copa América", "", "", "TRUE"])
        writer.writerow(["2020-01-06", "Jersey", "Brazil", "1", "0", "FIFA World Cup", "", "", "TRUE"])


def write_universe(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["team", "category", "include_fifa_only", "include_fifa_historical", "notes"])
        writer.writerow(["Argentina", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Brazil", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Spain", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["France", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Jersey", "regional", "FALSE", "FALSE", ""])


def test_search_bivariate_gamma(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    write_matches(matches)
    write_universe(universe)

    rows, payload = search_bivariate_gamma(matches, universe, gamma_values=(0.0, 0.08))

    assert len(rows) == 2
    assert rows[0]["matches"] == 4
    assert payload["universe"]["target_matches"] == 4
    assert "best_log_loss" in payload["summary"]
    assert "gamma_0_00_vs_current_gamma" in payload["summary"]


def test_write_bivariate_gamma_outputs(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "gamma.csv"
    json_path = tmp_path / "gamma.json"
    write_matches(matches)
    write_universe(universe)
    rows, payload = search_bivariate_gamma(matches, universe, gamma_values=(0.0, 0.08))

    write_outputs(rows, payload, csv_path, json_path)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output_rows = list(reader)
    parsed = json.loads(json_path.read_text(encoding="utf-8"))

    assert reader.fieldnames == REPORT_COLUMNS
    assert len(output_rows) == 2
    assert "recommended_calibrated_poisson_worldcup_v1_candidate" in parsed["summary"]


def test_bivariate_gamma_cli(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "gamma.csv"
    json_path = tmp_path / "gamma.json"
    write_matches(matches)
    write_universe(universe)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/tune_bivariate_gamma.py",
            "--input",
            str(matches),
            "--team-universe",
            str(universe),
            "--output-csv",
            str(csv_path),
            "--output-json",
            str(json_path),
            "--gamma",
            "0.0",
            "--gamma",
            "0.08",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    assert csv_path.exists()
    assert json_path.exists()
    assert "best_log_loss:" in result.stdout
