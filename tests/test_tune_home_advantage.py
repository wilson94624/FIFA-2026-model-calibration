import csv
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.tuning.evaluation import evaluate_rebuilt_elo_rows, rank_metric_rows
from src.tuning.tune_home_advantage import OUTPUT_COLUMNS, tune_home_advantages, write_outputs


def write_processed_fixture(path: Path) -> None:
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
                "home_pre_match_elo",
                "away_pre_match_elo",
            ]
        )
        writer.writerow(["2020-01-01", "Alpha", "Beta", "1", "0", "Friendly", "A", "A", "FALSE", "1500", "1500"])
        writer.writerow(["2020-01-02", "Beta", "Alpha", "0", "0", "Friendly", "B", "B", "FALSE", "1490", "1510"])
        writer.writerow(["2020-01-03", "Gamma", "Alpha", "0", "2", "Friendly", "C", "C", "TRUE", "1500", "1500"])


def test_evaluator_applies_home_advantage_only_to_non_neutral_matches() -> None:
    rows = [
        {
            "home_team": "Alpha",
            "away_team": "Beta",
            "home_score": "1",
            "away_score": "0",
            "home_pre_match_elo": "1500",
            "away_pre_match_elo": "1500",
            "neutral": "FALSE",
        },
        {
            "home_team": "Gamma",
            "away_team": "Delta",
            "home_score": "0",
            "away_score": "1",
            "home_pre_match_elo": "1500",
            "away_pre_match_elo": "1500",
            "neutral": "TRUE",
        },
    ]

    no_bonus = evaluate_rebuilt_elo_rows(rows, home_advantage_bonus=0.0)
    bonus = evaluate_rebuilt_elo_rows(rows, home_advantage_bonus=100.0)

    assert bonus["log_loss"] != no_bonus["log_loss"]


def test_tune_home_advantages_returns_dataframe_and_summary(tmp_path: Path) -> None:
    input_path = tmp_path / "matches_with_elo.csv"
    write_processed_fixture(input_path)

    frame, summary = tune_home_advantages(input_path, (0.0, 50.0), k_factor=80.0)

    assert isinstance(frame, pd.DataFrame)
    assert list(frame.columns) == OUTPUT_COLUMNS
    assert frame["home_advantage"].tolist() == [0.0, 50.0]
    assert set(summary) == {"best_accuracy", "best_log_loss", "best_brier_score"}


def test_write_outputs_creates_csv_and_json(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        [
            {"home_advantage": 0.0, "accuracy": 0.5, "log_loss": 1.0, "brier_score": 0.7},
            {"home_advantage": 50.0, "accuracy": 0.7, "log_loss": 0.9, "brier_score": 0.6},
        ],
        columns=OUTPUT_COLUMNS,
    )
    summary = rank_metric_rows(frame.to_dict(orient="records"))
    csv_path = tmp_path / "home_advantage_results.csv"
    json_path = tmp_path / "home_advantage_results.json"

    write_outputs(frame, summary, csv_path, json_path, k_factor=80.0)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert rows[0]["home_advantage"] == "0.0"
    assert payload["fixed_k_factor"] == 80.0
    assert payload["summary"]["best_accuracy"]["home_advantage"] == 50.0


def test_tune_home_advantage_cli_writes_outputs_and_prints_ranking(tmp_path: Path) -> None:
    input_path = tmp_path / "matches_with_elo.csv"
    csv_path = tmp_path / "home_advantage_results.csv"
    json_path = tmp_path / "home_advantage_results.json"
    write_processed_fixture(input_path)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/tune_home_advantage.py",
            "--input",
            str(input_path),
            "--output-csv",
            str(csv_path),
            "--output-json",
            str(json_path),
            "--home-advantage",
            "0",
            "--home-advantage",
            "50",
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
