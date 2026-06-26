import csv
import json
import subprocess
import sys
from pathlib import Path

from src.tuning.elo_mismatch_conditional_tail_benchmark import (
    REPORT_COLUMNS,
    build_elo_mismatch_conditional_tail_benchmark,
    build_variant_configs,
    should_apply,
    split_rows,
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
        writer.writerow(["1988-01-01", "France", "Iraq", "4", "0", "FIFA World Cup", "", "", "TRUE"])
        writer.writerow(["1992-01-02", "Brazil", "Haiti", "5", "0", "UEFA Euro", "", "", "TRUE"])
        writer.writerow(["1998-01-03", "France", "Brazil", "1", "1", "FIFA World Cup", "", "", "TRUE"])
        writer.writerow(["2002-01-04", "Iraq", "Haiti", "0", "0", "UEFA Euro", "", "", "TRUE"])
        writer.writerow(["2006-01-05", "France", "Haiti", "3", "0", "FIFA World Cup", "", "", "TRUE"])
        writer.writerow(["2010-01-06", "Brazil", "Iraq", "2", "1", "UEFA Euro", "", "", "TRUE"])
        writer.writerow(["2014-01-07", "France", "Iraq", "2", "0", "FIFA World Cup", "", "", "TRUE"])
        writer.writerow(["2018-01-08", "Brazil", "Haiti", "1", "0", "UEFA Euro", "", "", "TRUE"])
        writer.writerow(["2020-01-09", "Jersey", "France", "0", "4", "FIFA World Cup", "", "", "TRUE"])


def write_universe(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["team", "category", "include_fifa_only", "include_fifa_historical", "notes"])
        writer.writerow(["France", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Brazil", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Iraq", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Haiti", "fifa_current", "TRUE", "TRUE", ""])
        writer.writerow(["Jersey", "regional", "FALSE", "FALSE", ""])


def test_variant_configs_and_conditions() -> None:
    configs = build_variant_configs()
    assert configs[0]["variant"] == "baseline"
    assert len(configs) == 51
    config = {
        "method": "conditional_gd_tail_redistribution",
        "threshold": 300,
        "alpha": 0.1,
    }
    assert should_apply({"abs_elo_diff": 300.0}, config) is True
    assert should_apply({"abs_elo_diff": 299.9}, config) is False


def test_split_rows() -> None:
    rows = [
        {"date": "1989-01-01", "tournament": "FIFA World Cup", "home_pre_match_elo": "1700", "away_pre_match_elo": "1300"},
        {"date": "2001-01-01", "tournament": "UEFA Euro", "home_pre_match_elo": "1700", "away_pre_match_elo": "1680"},
    ]
    splits = split_rows(rows)
    assert len(splits["all_pooled"]) == 2
    assert len(splits["high_mismatch_abs_elo_diff_300_plus"]) == 1
    assert len(splits["balanced_abs_elo_diff_lt_200"]) == 1


def test_build_elo_mismatch_conditional_tail_benchmark(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    write_matches(matches)
    write_universe(universe)

    rows, payload = build_elo_mismatch_conditional_tail_benchmark(matches, universe)

    assert payload["model_context"]["research_benchmark_layer_only"] is True
    assert {
        "all_pooled",
        "fifa_world_cup_only",
        "uefa_euro_only",
        "world_cup_modern_1990_plus",
        "world_cup_recent_2000_plus",
        "balanced_abs_elo_diff_lt_200",
    }.issubset(set(payload["summary"]["split_summaries"]))
    assert any(row["variant"] == "baseline" for row in rows)
    assert any(float(row["affected_match_rate"]) >= 0.0 for row in rows)


def test_write_elo_mismatch_conditional_tail_benchmark_outputs(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "conditional.csv"
    json_path = tmp_path / "conditional.json"
    markdown_path = tmp_path / "conditional.md"
    write_matches(matches)
    write_universe(universe)
    rows, payload = build_elo_mismatch_conditional_tail_benchmark(matches, universe)

    write_outputs(rows, payload, csv_path, json_path, markdown_path)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output_rows = list(reader)
    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert reader.fieldnames == REPORT_COLUMNS
    assert len(output_rows) == len(rows)
    assert parsed["benchmark"] == "elo_mismatch_conditional_tail_benchmark"
    assert "# Elo Mismatch Conditional Tail Benchmark" in markdown


def test_elo_mismatch_conditional_tail_benchmark_cli(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "conditional.csv"
    json_path = tmp_path / "conditional.json"
    markdown_path = tmp_path / "conditional.md"
    write_matches(matches)
    write_universe(universe)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/elo_mismatch_conditional_tail_benchmark.py",
            "--input",
            str(matches),
            "--team-universe",
            str(universe),
            "--output-csv",
            str(csv_path),
            "--output-json",
            str(json_path),
            "--output-md",
            str(markdown_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    assert csv_path.exists()
    assert json_path.exists()
    assert markdown_path.exists()
    assert "keep_formal_model_baseline_unchanged:" in result.stdout
