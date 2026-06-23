import csv
import json
import subprocess
import sys
from pathlib import Path

from src.tuning.elo_benchmark_report import (
    REPORT_COLUMNS,
    build_benchmark_report,
    write_report_outputs,
)


def write_fixture(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "home_team", "away_team", "home_score", "away_score"])
        writer.writerow(["2020-01-01", "Alpha", "Beta", "3", "0"])
        writer.writerow(["2020-01-02", "Beta", "Alpha", "1", "1"])
        writer.writerow(["2020-01-03", "Gamma", "Alpha", "0", "2"])
        writer.writerow(["2020-01-04", "Gamma", "Beta", "0", "1"])


def test_build_benchmark_report_contains_models_and_analysis(tmp_path: Path) -> None:
    input_path = tmp_path / "matches.csv"
    write_fixture(input_path)

    rows, payload = build_benchmark_report(input_path)

    assert [row["model"] for row in rows] == ["standard_elo_v1", "calibrated_elo_v2_candidate"]
    assert set(REPORT_COLUMNS).issubset(rows[0])
    assert "largest_team_elo_changes" in payload
    assert "top20_ranking_comparison" in payload
    assert "recommendation" in payload


def test_write_report_outputs(tmp_path: Path) -> None:
    input_path = tmp_path / "matches.csv"
    csv_path = tmp_path / "report.csv"
    json_path = tmp_path / "report.json"
    write_fixture(input_path)
    rows, payload = build_benchmark_report(input_path)

    write_report_outputs(rows, payload, csv_path, json_path)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output_rows = list(reader)
    report_payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert reader.fieldnames == REPORT_COLUMNS
    assert len(output_rows) == 2
    assert "models" in report_payload


def test_elo_benchmark_report_cli(tmp_path: Path) -> None:
    input_path = tmp_path / "matches.csv"
    csv_path = tmp_path / "report.csv"
    json_path = tmp_path / "report.json"
    write_fixture(input_path)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/elo_benchmark_report.py",
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

    assert csv_path.exists()
    assert json_path.exists()
    assert "standard_elo_v1" in result.stdout
    assert "calibrated_elo_v2_candidate" in result.stdout
    assert "improvement" in result.stdout
