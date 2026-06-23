import csv
import json
import subprocess
import sys
from pathlib import Path

from src.tuning.tune_xg_parameters import REPORT_COLUMNS, tune_xg_parameters, write_outputs


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


def test_tune_xg_parameters_runs_grid(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    write_matches(matches)
    write_universe(universe)

    rows, payload = tune_xg_parameters(
        matches,
        universe,
        base_home_values=(1.2, 1.3),
        base_away_values=(1.1, 1.2),
        c1_values=(0.75, 1.0),
    )

    assert len(rows) == 8
    assert rows[0]["matches"] == 3
    assert payload["formal_formula_unchanged"] is True
    assert "recommended_calibrated_xg_v1_candidate" in payload["summary"]


def test_write_xg_parameter_outputs(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "xg.csv"
    json_path = tmp_path / "xg.json"
    write_matches(matches)
    write_universe(universe)
    rows, payload = tune_xg_parameters(
        matches,
        universe,
        base_home_values=(1.2,),
        base_away_values=(1.2,),
        c1_values=(0.75,),
    )

    write_outputs(rows, payload, csv_path, json_path)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output_rows = list(reader)
    parsed = json.loads(json_path.read_text(encoding="utf-8"))

    assert reader.fieldnames == REPORT_COLUMNS
    assert len(output_rows) == 1
    assert "current_formula" in parsed["summary"]


def test_tune_xg_parameters_cli(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "xg.csv"
    json_path = tmp_path / "xg.json"
    write_matches(matches)
    write_universe(universe)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/tune_xg_parameters.py",
            "--input",
            str(matches),
            "--team-universe",
            str(universe),
            "--output-csv",
            str(csv_path),
            "--output-json",
            str(json_path),
            "--base-home",
            "1.2",
            "--base-away",
            "1.2",
            "--c1",
            "0.75",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    assert csv_path.exists()
    assert json_path.exists()
    assert "best_poisson_log_loss:" in result.stdout
