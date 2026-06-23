import csv
import json
import subprocess
import sys
from pathlib import Path

from src.tuning.tournament_split_v3_validation import (
    REPORT_COLUMNS,
    build_tournament_split_v3_validation,
    write_outputs,
)


def write_matches(path: Path) -> None:
    tournaments = [
        "FIFA World Cup",
        "UEFA Euro",
        "Copa América",
        "AFC Asian Cup",
        "African Cup of Nations",
    ]
    teams = [
        ("Argentina", "Brazil"),
        ("Spain", "France"),
        ("Norway", "Brazil"),
    ]
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
        day = 1
        for tournament in tournaments:
            for home, away in teams:
                writer.writerow(
                    [
                        f"2020-01-{day:02d}",
                        home,
                        away,
                        "2",
                        "0",
                        tournament,
                        "",
                        "",
                        "TRUE",
                    ]
                )
                day += 1
        writer.writerow(["2021-12-01", "Jersey", "Brazil", "1", "0", "FIFA World Cup", "", "", "TRUE"])


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


def test_build_tournament_split_v3_validation(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    write_matches(matches)
    write_universe(universe)

    rows, payload = build_tournament_split_v3_validation(matches, universe)

    assert len(rows) == 15
    assert payload["universe"]["source_matches"] == 16
    assert payload["universe"]["universe_matches"] == 15
    assert set(REPORT_COLUMNS).issubset(rows[0])
    assert "calibrated_elo_v3_candidate" in payload["models"]
    assert "v3_scale_improvement_vs_v2" in payload["summary"]


def test_write_tournament_split_v3_outputs(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "tournament_split.csv"
    json_path = tmp_path / "tournament_split.json"
    write_matches(matches)
    write_universe(universe)
    rows, payload = build_tournament_split_v3_validation(matches, universe)

    write_outputs(rows, payload, csv_path, json_path)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output_rows = list(reader)
    parsed = json.loads(json_path.read_text(encoding="utf-8"))

    assert reader.fieldnames == REPORT_COLUMNS
    assert len(output_rows) == 15
    assert parsed["summary"]["recommendation"]["verdict"] == "B"


def test_tournament_split_v3_cli(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "tournament_split.csv"
    json_path = tmp_path / "tournament_split.json"
    write_matches(matches)
    write_universe(universe)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/tournament_split_v3_validation.py",
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
    assert "calibrated_elo_v3_candidate" in result.stdout
    assert "verdict:" in result.stdout
