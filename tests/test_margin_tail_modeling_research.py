import csv
import json
import subprocess
import sys
from pathlib import Path

from src.model.poisson import score_matrix
from src.tuning.margin_tail_modeling_research import (
    REPORT_COLUMNS,
    build_margin_tail_modeling_research,
    favorite_tail_boost,
    gd_tail_redistribution,
    matrix_mad,
    write_outputs,
)


def write_matches(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral",
                "2020-01-01,France,Iraq,4,0,FIFA World Cup,,,TRUE",
                "2020-01-02,Brazil,Haiti,5,0,UEFA Euro,,,TRUE",
                "2020-01-03,France,Brazil,1,1,FIFA World Cup,,,TRUE",
                "2020-01-04,Iraq,Haiti,0,0,UEFA Euro,,,TRUE",
                "2020-01-05,France,Haiti,3,0,FIFA World Cup,,,TRUE",
                "2020-01-06,Brazil,Iraq,2,1,UEFA Euro,,,TRUE",
                "2020-01-07,Jersey,France,0,4,FIFA World Cup,,,TRUE",
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


def test_tail_adjustments_preserve_probability_mass() -> None:
    matrix = score_matrix(1.8, 0.8)
    redistributed = gd_tail_redistribution(matrix, 0.10)
    boosted = favorite_tail_boost(matrix, 0.10, home_is_favorite=True)

    assert abs(sum(float(cell["probability"]) for cell in redistributed) - 1.0) < 1e-12
    assert abs(sum(float(cell["probability"]) for cell in boosted) - 1.0) < 1e-12
    assert matrix_mad(matrix, redistributed) > 0.0
    assert matrix_mad(matrix, boosted) > 0.0


def test_build_margin_tail_modeling_research(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    write_matches(matches)
    write_universe(universe)

    rows, payload = build_margin_tail_modeling_research(matches, universe)

    variants = [row["variant"] for row in rows]
    assert "baseline" in variants
    assert "max_goals_10_only" in variants
    assert "gd_tail_redistribution_alpha_0.10" in variants
    assert "favorite_tail_boost_alpha_0.10" in variants
    assert rows[0]["matches"] == 6
    assert payload["model_context"]["research_layer_only"] is True
    assert payload["summary"]["recommendation"]["keep_formal_model_baseline_unchanged"] is True


def test_write_margin_tail_modeling_research_outputs(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "margin.csv"
    json_path = tmp_path / "margin.json"
    markdown_path = tmp_path / "margin.md"
    write_matches(matches)
    write_universe(universe)
    rows, payload = build_margin_tail_modeling_research(matches, universe)

    write_outputs(rows, payload, csv_path, json_path, markdown_path)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output_rows = list(reader)
    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert reader.fieldnames == REPORT_COLUMNS
    assert len(output_rows) == len(rows)
    assert parsed["benchmark"] == "margin_tail_modeling_research"
    assert "# Margin Tail Modeling Research" in markdown


def test_margin_tail_modeling_research_cli(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    csv_path = tmp_path / "margin.csv"
    json_path = tmp_path / "margin.json"
    markdown_path = tmp_path / "margin.md"
    write_matches(matches)
    write_universe(universe)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/margin_tail_modeling_research.py",
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
