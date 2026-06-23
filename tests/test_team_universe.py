import csv
import json
import subprocess
import sys
from pathlib import Path

from src.tuning.team_universe import (
    build_report,
    build_team_universe_rows,
    classify_team,
    read_final_teams,
    universe_flags,
)


def test_classify_team_categories() -> None:
    assert classify_team("Argentina") == "fifa_current"
    assert classify_team("Yugoslavia") == "fifa_historical"
    assert classify_team("Czechoslovakia") == "fifa_historical"
    assert classify_team("Croatia") == "successor_state"
    assert classify_team("Basque Country") == "regional"
    assert classify_team("Ambazonia") == "conifa"
    assert classify_team("Iraqi Kurdistan") == "conifa"
    assert classify_team("Kiribati") == "non_fifa_representative"


def test_universe_flags() -> None:
    assert universe_flags("fifa_current") == (True, True)
    assert universe_flags("successor_state") == (True, True)
    assert universe_flags("fifa_historical") == (False, True)
    assert universe_flags("regional") == (False, False)


def write_fixture(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "home_team",
                "away_team",
                "home_post_match_elo",
                "away_post_match_elo",
                "home_matches_after",
                "away_matches_after",
            ]
        )
        writer.writerow(["Argentina", "Yugoslavia", "1900", "1700", "10", "10"])
        writer.writerow(["Basque Country", "Czechoslovakia", "1650", "1680", "5", "20"])


def test_build_team_universe_report(tmp_path: Path) -> None:
    path = tmp_path / "matches.csv"
    write_fixture(path)
    teams = read_final_teams(path)
    rows = build_team_universe_rows(teams)
    report = build_report(teams, rows)

    assert report["team_count"] == 4
    assert report["fifa_plus_historical_team_count"] == 3
    assert report["excluded_team_count"] == 1
    assert report["historical_retention_check"]["Yugoslavia"]["include_fifa_historical"] is True
    assert report["historical_retention_check"]["Czechoslovakia"]["include_fifa_historical"] is True


def test_build_team_universe_cli(tmp_path: Path) -> None:
    input_path = tmp_path / "matches.csv"
    csv_path = tmp_path / "team_universe.csv"
    json_path = tmp_path / "report.json"
    write_fixture(input_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_team_universe.py",
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

    rows = list(csv.DictReader(csv_path.open("r", encoding="utf-8", newline="")))
    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(rows) == 4
    assert report["recommendation"]["default_universe"] == "fifa_plus_historical"
    assert "fifa_plus_historical_team_count" in result.stdout
