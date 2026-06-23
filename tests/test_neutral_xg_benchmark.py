import csv
import json
import subprocess
import sys
from pathlib import Path

from src.tuning.neutral_xg_benchmark import REPORT_COLUMNS, build_neutral_xg_benchmark, write_outputs


def write_matches(path: Path) -> None:
    tournaments = [
        "FIFA World Cup",
        "UEFA Euro",
        "Copa América",
        "AFC Asian Cup",
        "African Cup of Nations",
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
        for index, tournament in enumerate(tournaments, start=1):
            writer.writerow(
                [
                    f"2020-01-{index:02d}",
                    "Argentina",
                    "Brazil",
                    "2",
                    "0",
                    tournament,
                    "",
                    "",
                    "TRUE",
                ]
            )
            writer.writerow(
                [
                    f"2020-02-{index:02d}",
                    "Spain",
                    "France",
                    "1",
                    "1",
                    tournament,
                    "",
                    "",
                    "TRUE",
                ]
            )
        writer.writerow(["2021-01-01", "Jersey", "Brazil", "1", "0", "FIFA World Cup", "", "", "TRUE"])


def write_universe(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["team", "category", "include_fifa_only", "include_fifa_historical", "notes"])
        writer.writerow(["Argentina", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Brazil", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Spain", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["France", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Jersey", "regional", "FALSE", "FALSE", ""])


def test_build_neutral_xg_benchmark(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    write_matches(matches)
    write_universe(universe)

    rows, payload = build_neutral_xg_benchmark(matches, universe)

    assert len(rows) == 12
    assert payload["universe"]["source_matches"] == 11
    assert payload["universe"]["universe_matches"] == 10
    assert "neutral_symmetric" in payload["formulas"]
    assert "recommended_worldcup_xg_direction" in payload["summary"]


def test_write_neutral_xg_outputs(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "neutral_xg.csv"
    json_path = tmp_path / "neutral_xg.json"
    write_matches(matches)
    write_universe(universe)
    rows, payload = build_neutral_xg_benchmark(matches, universe)

    write_outputs(rows, payload, csv_path, json_path)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output_rows = list(reader)
    parsed = json.loads(json_path.read_text(encoding="utf-8"))

    assert reader.fieldnames == REPORT_COLUMNS
    assert len(output_rows) == 12
    assert "formula_comparisons" in parsed["summary"]


def test_neutral_xg_cli(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "neutral_xg.csv"
    json_path = tmp_path / "neutral_xg.json"
    write_matches(matches)
    write_universe(universe)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/neutral_xg_benchmark.py",
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
    assert "recommended_worldcup_xg_direction:" in result.stdout
