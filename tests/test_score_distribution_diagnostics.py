import json
import subprocess
import sys
from pathlib import Path

from src.tuning.score_distribution_diagnostics import (
    build_score_distribution_diagnostics,
    gd_bucket,
    missing_tail_mass,
    predicted_favorite_margin_bucket,
    raw_grid_mass,
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


def test_distribution_helpers() -> None:
    assert gd_bucket(0) == "GD=0"
    assert gd_bucket(1) == "GD=1"
    assert gd_bucket(2) == "GD=2"
    assert gd_bucket(3) == "GD>=3"
    assert predicted_favorite_margin_bucket(2, 1, True) == "favorite_win_by_1"
    assert predicted_favorite_margin_bucket(0, 3, False) == "favorite_win_by_3_plus"

    mass_5 = raw_grid_mass(1.5, 1.2, 5)
    mass_10 = raw_grid_mass(1.5, 1.2, 10)
    assert mass_10 >= mass_5
    assert missing_tail_mass(1.5, 1.2, 10) <= missing_tail_mass(1.5, 1.2, 5)


def test_build_score_distribution_diagnostics(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    write_matches(matches)
    write_universe(universe)

    report = build_score_distribution_diagnostics(matches, universe, max_goals_values=(5, 6))

    assert report["dataset"]["target_matches"] == 6
    assert report["model_context"]["diagnostic_only"] is True
    assert [row["max_goals"] for row in report["max_goals_sensitivity"]] == [5, 6]
    assert "score_grid_truncation_analysis" in report
    assert "poisson_shape_analysis" in report
    assert len(report["goal_difference_tail_analysis"]) == 4
    assert len(report["favorite_blowout_analysis"]) == 3
    assert "primary_gd_3_plus_underestimation_cause" in report["diagnostic_conclusions"]


def test_write_score_distribution_diagnostics_outputs(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    json_path = tmp_path / "diagnostics.json"
    markdown_path = tmp_path / "diagnostics.md"
    write_matches(matches)
    write_universe(universe)
    report = build_score_distribution_diagnostics(matches, universe, max_goals_values=(5, 6))

    write_outputs(report, json_path, markdown_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert parsed["report"] == "score_distribution_diagnostics"
    assert "# Score Distribution Diagnostics Report" in markdown
    assert "MAX_GOALS Sensitivity" in markdown


def test_score_distribution_diagnostics_cli(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    json_path = tmp_path / "diagnostics.json"
    markdown_path = tmp_path / "diagnostics.md"
    write_matches(matches)
    write_universe(universe)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/score_distribution_diagnostics.py",
            "--input",
            str(matches),
            "--team-universe",
            str(universe),
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

    assert json_path.exists()
    assert markdown_path.exists()
    assert "fat_tail_score_distribution_research_recommended:" in result.stdout
