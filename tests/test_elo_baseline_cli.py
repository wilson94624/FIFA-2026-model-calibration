import csv
import subprocess
import sys
from pathlib import Path

from scripts.run_elo_baseline import run


def write_fixture(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "home_team",
                "away_team",
                "home_score",
                "away_score",
                "home_pre_match_elo",
                "away_pre_match_elo",
            ]
        )
        writer.writerow(["Alpha", "Beta", "2", "0", "1600", "1500"])
        writer.writerow(["Gamma", "Delta", "1", "1", "1400", "1400"])


def test_run_elo_baseline_writes_expected_columns_without_updating_elo(tmp_path: Path) -> None:
    input_path = tmp_path / "matches.csv"
    output_path = tmp_path / "predictions.csv"
    write_fixture(input_path)

    metrics = run(input_path, output_path)

    assert metrics["matches"] == 2.0
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["home_pre_match_elo"] == "1600.0"
    assert rows[0]["away_pre_match_elo"] == "1500.0"
    assert rows[1]["home_pre_match_elo"] == "1400.0"
    assert rows[1]["away_pre_match_elo"] == "1400.0"
    assert {
        "home_xg",
        "away_xg",
        "prob_home",
        "prob_draw",
        "prob_away",
        "predicted_label",
        "actual_label",
    }.issubset(rows[0].keys())


def test_cli_prints_metrics_summary(tmp_path: Path) -> None:
    input_path = tmp_path / "matches.csv"
    output_path = tmp_path / "predictions.csv"
    write_fixture(input_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_elo_baseline.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "matches: 2" in result.stdout
    assert "accuracy:" in result.stdout
    assert "log_loss:" in result.stdout
    assert "brier_score:" in result.stdout
    assert output_path.exists()
