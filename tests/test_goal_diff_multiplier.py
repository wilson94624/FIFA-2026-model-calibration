import csv
import json
import math
import subprocess
import sys
from pathlib import Path

from src.model.elo_rebuilder import parse_match_rows, rebuild_elo_history
from src.tuning.tune_goal_diff_multiplier import (
    OUTPUT_COLUMNS,
    goal_diff_multiplier,
    tune_goal_diff_multipliers,
    write_outputs,
)


def test_goal_diff_multiplier_variants() -> None:
    assert goal_diff_multiplier("none")(4, 1) == 1.0
    assert goal_diff_multiplier("simple_linear_capped")(4, 1) == 3.0
    assert goal_diff_multiplier("simple_linear_capped")(6, 1) == 3.0
    assert goal_diff_multiplier("sqrt_margin")(5, 1) == 2.0
    assert goal_diff_multiplier("log_margin")(3, 1) == math.log(3)
    assert goal_diff_multiplier("sqrt_margin")(1, 1) == 1.0


def test_rebuild_uses_goal_diff_multiplier_as_optional_effective_k() -> None:
    matches = parse_match_rows(
        [
            {
                "date": "2020-01-01",
                "home_team": "Alpha",
                "away_team": "Beta",
                "home_score": "3",
                "away_score": "0",
            }
        ]
    )

    rows = rebuild_elo_history(
        matches,
        k_factor=80.0,
        goal_diff_multiplier_fn=goal_diff_multiplier("simple_linear_capped"),
    )

    assert rows[0]["elo_k_factor"] == "240.000000"
    assert rows[0]["elo_goal_diff_multiplier"] == "3.000000"
    assert rows[0]["home_elo_change"] == "120.000000"


def write_fixture(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "home_team", "away_team", "home_score", "away_score"])
        writer.writerow(["2020-01-01", "Alpha", "Beta", "3", "0"])
        writer.writerow(["2020-01-02", "Beta", "Alpha", "1", "1"])
        writer.writerow(["2020-01-03", "Gamma", "Alpha", "0", "2"])


def test_tune_goal_diff_multipliers_and_outputs(tmp_path: Path) -> None:
    input_path = tmp_path / "matches.csv"
    csv_path = tmp_path / "goal_diff.csv"
    json_path = tmp_path / "goal_diff.json"
    write_fixture(input_path)

    rows, summary = tune_goal_diff_multipliers(input_path, ("none", "sqrt_margin"))
    write_outputs(rows, summary, csv_path, json_path)

    assert [row["variant"] for row in rows] == ["none", "sqrt_margin"]
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output_rows = list(reader)
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert reader.fieldnames == OUTPUT_COLUMNS
    assert len(output_rows) == 2
    assert "best_log_loss" in payload["summary"]


def test_goal_diff_multiplier_cli_writes_outputs(tmp_path: Path) -> None:
    input_path = tmp_path / "matches.csv"
    csv_path = tmp_path / "goal_diff.csv"
    json_path = tmp_path / "goal_diff.json"
    write_fixture(input_path)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/tune_goal_diff_multiplier.py",
            "--input",
            str(input_path),
            "--output-csv",
            str(csv_path),
            "--output-json",
            str(json_path),
            "--variant",
            "none",
            "--variant",
            "log_margin",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    assert csv_path.exists()
    assert json_path.exists()
    assert "best_accuracy:" in result.stdout
    assert "best_log_loss:" in result.stdout
    assert "best_brier_score:" in result.stdout
