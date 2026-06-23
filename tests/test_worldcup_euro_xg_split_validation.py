import csv
import json
import subprocess
import sys
from pathlib import Path

from src.tuning.worldcup_euro_xg_split_validation import (
    REPORT_COLUMNS,
    build_worldcup_euro_xg_split_validation,
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
        writer.writerow(["2020-01-01", "Argentina", "Brazil", "2", "0", "FIFA World Cup", "", "", "TRUE"])
        writer.writerow(["2020-01-02", "Spain", "France", "1", "1", "UEFA Euro", "", "", "TRUE"])
        writer.writerow(["2020-01-03", "Argentina", "France", "0", "1", "FIFA World Cup", "", "", "FALSE"])
        writer.writerow(["2020-01-04", "Argentina", "Brazil", "3", "0", "Copa América", "", "", "TRUE"])
        writer.writerow(["2020-01-05", "Jersey", "Brazil", "1", "0", "FIFA World Cup", "", "", "TRUE"])


def write_universe(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["team", "category", "include_fifa_only", "include_fifa_historical", "notes"])
        writer.writerow(["Argentina", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Brazil", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Spain", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["France", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Jersey", "regional", "FALSE", "FALSE", ""])


def test_build_worldcup_euro_xg_split_validation(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    write_matches(matches)
    write_universe(universe)

    rows, payload = build_worldcup_euro_xg_split_validation(matches, universe)

    assert len(rows) == 6
    assert {row["split"] for row in rows} == {
        "FIFA World Cup neutral",
        "UEFA Euro neutral",
        "World Cup + Euro neutral",
    }
    assert payload["universe"]["target_matches"] == 2
    assert "comparisons" in payload["summary"]


def test_write_worldcup_euro_xg_split_outputs(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "split.csv"
    json_path = tmp_path / "split.json"
    write_matches(matches)
    write_universe(universe)
    rows, payload = build_worldcup_euro_xg_split_validation(matches, universe)

    write_outputs(rows, payload, csv_path, json_path)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output_rows = list(reader)
    parsed = json.loads(json_path.read_text(encoding="utf-8"))

    assert reader.fieldnames == REPORT_COLUMNS
    assert len(output_rows) == 6
    assert "pooled_recommendation" in parsed["summary"]


def test_worldcup_euro_xg_split_cli(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "split.csv"
    json_path = tmp_path / "split.json"
    write_matches(matches)
    write_universe(universe)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/worldcup_euro_xg_split_validation.py",
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
    assert "pooled_recommendation:" in result.stdout
