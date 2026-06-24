import csv
import json
import subprocess
import sys
from pathlib import Path

from src.tuning.domination_layer_benchmark import (
    REPORT_COLUMNS,
    blend_xg,
    build_domination_layer_benchmark,
    domination_xg,
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


def test_domination_xg_boosts_clear_favorite_and_penalizes_underdog() -> None:
    favorite_xg, underdog_xg = domination_xg(1.6, 1.0, 1800.0, 1400.0)

    assert favorite_xg > 1.6
    assert underdog_xg < 1.0


def test_blend_xg_weight_zero_drift_at_full_normal() -> None:
    blended = blend_xg(1.4, 1.2, 1.8, 1.0, normal_weight=1.0)

    assert blended == (1.4, 1.2)


def test_build_domination_layer_benchmark(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    write_matches(matches)
    write_universe(universe)

    rows, payload = build_domination_layer_benchmark(matches, universe)

    assert [row["normal_weight"] for row in rows] == [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]
    assert rows[0]["matches"] == 6
    assert payload["formal_model_formulas_unchanged"] is True
    assert "current_70_30_vs_100_normal" in payload["summary"]
    assert "largest_affected_matches_at_70_30" in payload["summary"]


def test_write_domination_layer_benchmark_outputs(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "domination.csv"
    json_path = tmp_path / "domination.json"
    write_matches(matches)
    write_universe(universe)
    rows, payload = build_domination_layer_benchmark(matches, universe)

    write_outputs(rows, payload, csv_path, json_path)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output_rows = list(reader)
    parsed = json.loads(json_path.read_text(encoding="utf-8"))

    assert reader.fieldnames == REPORT_COLUMNS
    assert len(output_rows) == 6
    assert parsed["summary"]["recommendation"]["selection_metric"] == "log_loss"


def test_domination_layer_benchmark_cli(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "domination.csv"
    json_path = tmp_path / "domination.json"
    write_matches(matches)
    write_universe(universe)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/domination_layer_benchmark.py",
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
    assert "current_70_30_vs_100_normal:" in result.stdout
