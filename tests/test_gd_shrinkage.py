import csv
import json
import math
import subprocess
import sys
from pathlib import Path

from src.tuning.tune_gd_shrinkage import (
    OUTPUT_COLUMNS,
    gd_shrinkage_multiplier,
    tune_gd_shrinkage,
    write_outputs,
)


def test_gd_shrinkage_multiplier_boundaries() -> None:
    assert gd_shrinkage_multiplier(0.0)(4, 1) == 1.0
    assert gd_shrinkage_multiplier(1.0)(4, 1) == math.log(4)
    assert gd_shrinkage_multiplier(0.5)(4, 1) == 1.0 + 0.5 * (math.log(4) - 1.0)
    assert gd_shrinkage_multiplier(1.0)(2, 2) == 1.0


def write_fixture(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "home_team", "away_team", "home_score", "away_score"])
        writer.writerow(["2020-01-01", "Argentina", "Brazil", "3", "0"])
        writer.writerow(["2020-01-02", "Spain", "France", "1", "1"])
        writer.writerow(["2020-01-03", "Norway", "Brazil", "2", "0"])
        writer.writerow(["2020-01-04", "France", "Argentina", "0", "1"])


def test_tune_gd_shrinkage_and_outputs(tmp_path: Path) -> None:
    input_path = tmp_path / "matches.csv"
    csv_path = tmp_path / "gd_shrinkage.csv"
    json_path = tmp_path / "gd_shrinkage.json"
    write_fixture(input_path)

    rows, payload = tune_gd_shrinkage(input_path, alphas=(0.0, 0.5, 1.0))
    write_outputs(rows, payload, csv_path, json_path)

    assert [row["alpha"] for row in rows] == [0.0, 0.5, 1.0]
    assert "recommended_calibrated_elo_v3_candidate" in payload["summary"]
    assert "tracked_team_delta_vs_alpha_0" in payload["alphas"]["0.50"]

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output_rows = list(reader)
    parsed = json.loads(json_path.read_text(encoding="utf-8"))

    assert reader.fieldnames == OUTPUT_COLUMNS
    assert len(output_rows) == 3
    assert "Argentina" in parsed["alphas"]["1.00"]["tracked_teams"]


def test_gd_shrinkage_cli_writes_outputs(tmp_path: Path) -> None:
    input_path = tmp_path / "matches.csv"
    csv_path = tmp_path / "gd_shrinkage.csv"
    json_path = tmp_path / "gd_shrinkage.json"
    write_fixture(input_path)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/tune_gd_shrinkage.py",
            "--input",
            str(input_path),
            "--output-csv",
            str(csv_path),
            "--output-json",
            str(json_path),
            "--alpha",
            "0.0",
            "--alpha",
            "1.0",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    assert csv_path.exists()
    assert json_path.exists()
    assert "recommended_alpha:" in result.stdout
