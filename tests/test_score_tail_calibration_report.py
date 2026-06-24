import json
import subprocess
import sys
from pathlib import Path

from src.tuning.score_tail_calibration_report import (
    bucket_for_probability,
    build_score_tail_calibration_report,
    scoreline_key,
    total_goals_probability,
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


def test_tail_helpers() -> None:
    matrix = [
        {"home": 0, "away": 0, "probability": 0.10},
        {"home": 3, "away": 0, "probability": 0.20},
        {"home": 2, "away": 2, "probability": 0.30},
        {"home": 5, "away": 0, "probability": 0.40},
    ]

    assert scoreline_key(4, 0) == "4-0"
    assert total_goals_probability(matrix, 4) == 0.70
    assert bucket_for_probability(0.049) == "0-5%"
    assert bucket_for_probability(0.30) == "30%+"


def test_build_score_tail_calibration_report(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    write_matches(matches)
    write_universe(universe)

    report = build_score_tail_calibration_report(matches, universe)

    assert report["dataset"]["target_matches"] == 6
    assert report["model_context"]["domination"] == "disabled / 100% normal"
    assert report["model_context"]["formal_model_formulas_unchanged"] is True
    assert len(report["actual_scoreline_distribution"]["top_20"]) > 0
    assert len(report["predicted_scoreline_probability_distribution"]["top_20_predicted_scorelines"]) == 20
    assert report["missed_blowout_analysis"]["actual_blowout_matches"] >= 1
    assert len(report["calibration_buckets"]) == 5
    assert "recommended_next_step" in report["diagnostic_conclusions"]


def test_write_score_tail_calibration_report_outputs(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    json_path = tmp_path / "score_tail.json"
    markdown_path = tmp_path / "score_tail.md"
    write_matches(matches)
    write_universe(universe)
    report = build_score_tail_calibration_report(matches, universe)

    write_outputs(report, json_path, markdown_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert parsed["report"] == "score_tail_calibration_report"
    assert "# Score Tail Calibration Report" in markdown
    assert "Systematically underestimates blowouts" in markdown


def test_score_tail_calibration_report_cli(tmp_path: Path) -> None:
    matches = tmp_path / "matches.csv"
    universe = tmp_path / "universe.csv"
    json_path = tmp_path / "score_tail.json"
    markdown_path = tmp_path / "score_tail.md"
    write_matches(matches)
    write_universe(universe)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/score_tail_calibration_report.py",
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
    assert "systematically_underestimates_blowouts:" in result.stdout
