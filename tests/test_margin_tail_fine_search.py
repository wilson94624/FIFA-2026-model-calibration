import csv
import json
import subprocess
import sys
from pathlib import Path

from src.tuning.margin_tail_fine_search import (
    REPORT_COLUMNS,
    build_margin_tail_fine_search,
    build_variant_configs,
    split_rows,
    write_outputs,
)


def write_matches(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral",
                "1988-01-01,France,Iraq,4,0,FIFA World Cup,,,TRUE",
                "1992-01-02,Brazil,Haiti,5,0,UEFA Euro,,,TRUE",
                "1998-01-03,France,Brazil,1,1,FIFA World Cup,,,TRUE",
                "2002-01-04,Iraq,Haiti,0,0,UEFA Euro,,,TRUE",
                "2006-01-05,France,Haiti,3,0,FIFA World Cup,,,TRUE",
                "2010-01-06,Brazil,Iraq,2,1,UEFA Euro,,,TRUE",
                "2014-01-07,France,Iraq,2,0,FIFA World Cup,,,TRUE",
                "2018-01-08,Brazil,Haiti,1,0,UEFA Euro,,,TRUE",
                "2020-01-09,Jersey,France,0,4,FIFA World Cup,,,TRUE",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_universe(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "team,category,include_fifa_only,include_fifa_historical,notes",
                "France,fifa_current,TRUE,TRUE,",
                "Brazil,fifa_current,TRUE,TRUE,",
                "Iraq,fifa_current,TRUE,TRUE,",
                "Haiti,fifa_current,TRUE,TRUE,",
                "Jersey,regional,FALSE,FALSE,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_variant_configs_and_splits() -> None:
    configs = build_variant_configs()
    assert configs[0]["variant"] == "baseline"
    assert "gd_tail_redistribution_alpha_0.10" in [config["variant"] for config in configs]
    assert "favorite_tail_boost_alpha_0.15" in [config["variant"] for config in configs]

    rows = [
        {"date": "1989-01-01", "tournament": "FIFA World Cup"},
        {"date": "2001-01-01", "tournament": "UEFA Euro"},
    ]
    splits = split_rows(rows)
    assert len(splits["all_pooled"]) == 2
    assert len(splits["modern_era_1990_plus"]) == 1
    assert len(splits["recent_era_2000_plus"]) == 1


def test_build_margin_tail_fine_search(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    write_matches(matches)
    write_universe(universe)

    rows, payload = build_margin_tail_fine_search(matches, universe)

    assert payload["model_context"]["research_validation_layer_only"] is True
    assert set(payload["summary"]["split_summaries"]) == {
        "all_pooled",
        "fifa_world_cup_only",
        "uefa_euro_only",
        "modern_era_1990_plus",
        "recent_era_2000_plus",
    }
    assert any(row["variant"] == "baseline" for row in rows)
    assert any(row["split"] == "recent_era_2000_plus" for row in rows)


def test_write_margin_tail_fine_search_outputs(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "fine.csv"
    json_path = tmp_path / "fine.json"
    markdown_path = tmp_path / "fine.md"
    write_matches(matches)
    write_universe(universe)
    rows, payload = build_margin_tail_fine_search(matches, universe)

    write_outputs(rows, payload, csv_path, json_path, markdown_path)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output_rows = list(reader)
    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert reader.fieldnames == REPORT_COLUMNS
    assert len(output_rows) == len(rows)
    assert parsed["benchmark"] == "margin_tail_fine_search"
    assert "# Margin Tail Fine Search" in markdown


def test_margin_tail_fine_search_cli(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "fine.csv"
    json_path = tmp_path / "fine.json"
    markdown_path = tmp_path / "fine.md"
    write_matches(matches)
    write_universe(universe)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/margin_tail_fine_search.py",
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
