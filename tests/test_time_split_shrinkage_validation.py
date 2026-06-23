import csv
import json
import subprocess
import sys
from pathlib import Path

from src.tuning.time_split_shrinkage_validation import (
    REPORT_COLUMNS,
    build_time_split_shrinkage_validation,
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
        writer.writerow(["2023-01-01", "Argentina", "Brazil", "3", "0", "Friendly", "", "", "FALSE"])
        writer.writerow(["2023-02-01", "Spain", "France", "1", "1", "Friendly", "", "", "TRUE"])
        writer.writerow(["2023-03-01", "Norway", "Brazil", "2", "0", "Friendly", "", "", "FALSE"])
        writer.writerow(["2024-01-01", "France", "Argentina", "0", "1", "Friendly", "", "", "TRUE"])
        writer.writerow(["2024-02-01", "Brazil", "Spain", "2", "2", "Friendly", "", "", "FALSE"])
        writer.writerow(["2024-03-01", "Jersey", "Brazil", "1", "0", "Friendly", "", "", "FALSE"])


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


def test_build_time_split_shrinkage_validation(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    write_matches(matches)
    write_universe(universe)

    rows, payload = build_time_split_shrinkage_validation(matches, universe)

    assert len(rows) == 8
    assert rows[0]["model"] == "standard_elo_v1"
    assert rows[1]["model"] == "calibrated_elo_v2_candidate"
    assert rows[0]["validation_matches"] == 2
    assert payload["universe"]["source_matches"] == 6
    assert payload["universe"]["universe_matches"] == 5
    assert "recommended_calibrated_elo_v3_candidate" in payload["summary"]


def test_write_time_split_shrinkage_outputs(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "time_split_shrinkage.csv"
    json_path = tmp_path / "time_split_shrinkage.json"
    write_matches(matches)
    write_universe(universe)
    rows, payload = build_time_split_shrinkage_validation(matches, universe)

    write_outputs(rows, payload, csv_path, json_path)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output_rows = list(reader)
    parsed = json.loads(json_path.read_text(encoding="utf-8"))

    assert reader.fieldnames == REPORT_COLUMNS
    assert len(output_rows) == 8
    assert "calibrated_elo_v3_shrinkage_alpha_0.25" in parsed["models"]


def test_time_split_shrinkage_validation_cli(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "time_split_shrinkage.csv"
    json_path = tmp_path / "time_split_shrinkage.json"
    write_matches(matches)
    write_universe(universe)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/time_split_shrinkage_validation.py",
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
    assert "recommended_alpha:" in result.stdout
