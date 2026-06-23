import csv
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.tuning.evaluation import rank_metric_rows
from src.tuning.tune_k_factor import OUTPUT_COLUMNS, tune_k_factors, write_outputs


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


def test_tune_k_factors_returns_dataframe_and_summary(tmp_path: Path) -> None:
    input_path = tmp_path / "matches_with_elo.csv"
    write_processed_fixture(input_path)

    frame, summary = tune_k_factors(input_path, (10.0, 20.0))

    assert isinstance(frame, pd.DataFrame)
    assert list(frame.columns) == OUTPUT_COLUMNS
    assert frame["k_factor"].tolist() == [10.0, 20.0]
    assert set(summary) == {"best_accuracy", "best_log_loss", "best_brier_score"}
    assert summary["best_accuracy"]["k_factor"] in {10.0, 20.0}


def test_write_outputs_creates_csv_and_json(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        [
            {"k_factor": 10.0, "accuracy": 0.5, "log_loss": 1.0, "brier_score": 0.7},
            {"k_factor": 20.0, "accuracy": 0.7, "log_loss": 0.9, "brier_score": 0.6},
        ],
        columns=OUTPUT_COLUMNS,
    )
    summary = rank_metric_rows(frame.to_dict(orient="records"))
    csv_path = tmp_path / "k_factor_results.csv"
    json_path = tmp_path / "k_factor_results.json"

    write_outputs(frame, summary, csv_path, json_path)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert rows[0]["k_factor"] == "10.0"
    assert payload["results"][1]["k_factor"] == 20.0
    assert payload["summary"]["best_accuracy"]["k_factor"] == 20.0


def test_tune_k_factor_cli_writes_outputs_and_prints_ranking(tmp_path: Path) -> None:
    input_path = tmp_path / "matches_with_elo.csv"
    csv_path = tmp_path / "k_factor_results.csv"
    json_path = tmp_path / "k_factor_results.json"
    write_processed_fixture(input_path)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/tune_k_factor.py",
            "--input",
            str(input_path),
            "--output-csv",
            str(csv_path),
            "--output-json",
            str(json_path),
            "--k-factor",
            "10",
            "--k-factor",
            "20",
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
