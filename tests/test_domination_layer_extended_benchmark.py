import csv
import json
import subprocess
import sys
from pathlib import Path

from src.tuning.domination_layer_extended_benchmark import (
    REPORT_COLUMNS,
    build_domination_layer_extended_benchmark,
    blowout_probability,
    goal_difference_probabilities,
    predicted_goal_difference,
    top_scorelines,
    write_outputs,
)


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
        writer.writerow(["2020-01-01", "France", "Iraq", "3", "0", "FIFA World Cup", "", "", "TRUE"])
        writer.writerow(["2020-01-02", "Brazil", "Haiti", "4", "0", "UEFA Euro", "", "", "TRUE"])
        writer.writerow(["2020-01-03", "France", "Brazil", "1", "1", "FIFA World Cup", "", "", "TRUE"])
        writer.writerow(["2020-01-04", "Iraq", "Haiti", "0", "0", "UEFA Euro", "", "", "TRUE"])
        writer.writerow(["2020-01-05", "France", "Haiti", "2", "0", "FIFA World Cup", "", "", "TRUE"])
        writer.writerow(["2020-01-06", "Brazil", "Iraq", "2", "1", "UEFA Euro", "", "", "TRUE"])
        writer.writerow(["2020-01-07", "Jersey", "France", "0", "4", "FIFA World Cup", "", "", "TRUE"])


def write_universe(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["team", "category", "include_fifa_only", "include_fifa_historical", "notes"])
        writer.writerow(["France", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Brazil", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Iraq", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Haiti", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Jersey", "regional", "FALSE", "FALSE", ""])


def test_scoreline_and_goal_difference_helpers() -> None:
    matrix = [
        {"home": 0, "away": 0, "probability": 0.10},
        {"home": 1, "away": 0, "probability": 0.40},
        {"home": 2, "away": 0, "probability": 0.30},
        {"home": 0, "away": 1, "probability": 0.20},
    ]

    assert top_scorelines(matrix, 2) == [(1, 0, 0.40), (2, 0, 0.30)]
    assert goal_difference_probabilities(matrix) == {0: 0.10, 1: 0.40, 2: 0.30, -1: 0.20}
    assert predicted_goal_difference(matrix) == 1
    assert blowout_probability(matrix) == 0.0


def test_build_domination_layer_extended_benchmark(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    write_matches(matches)
    write_universe(universe)

    rows, payload = build_domination_layer_extended_benchmark(matches, universe)

    assert [row["normal_weight"] for row in rows] == [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]
    assert rows[0]["matches"] == 6
    assert rows[0]["high_margin_matches"] >= 1
    assert "best_correct_score_top3" in payload["summary"]
    assert "base_domination_benchmark_rows" in payload
    assert payload["formal_model_formulas_unchanged"] is True


def test_write_domination_layer_extended_benchmark_outputs(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "domination_extended.csv"
    json_path = tmp_path / "domination_extended.json"
    write_matches(matches)
    write_universe(universe)
    rows, payload = build_domination_layer_extended_benchmark(matches, universe)

    write_outputs(rows, payload, csv_path, json_path)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output_rows = list(reader)
    parsed = json.loads(json_path.read_text(encoding="utf-8"))

    assert reader.fieldnames == REPORT_COLUMNS
    assert len(output_rows) == 6
    assert "metric_definitions" in parsed


def test_domination_layer_extended_benchmark_cli(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "domination_extended.csv"
    json_path = tmp_path / "domination_extended.json"
    write_matches(matches)
    write_universe(universe)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/domination_layer_extended_benchmark.py",
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
    assert "wdl_and_betting_best_weights_differ:" in result.stdout
