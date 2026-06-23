import csv
import subprocess
import sys
from pathlib import Path

import pytest

from src.model.elo_rebuilder import (
    OUTPUT_COLUMNS,
    actual_score_from_goals,
    parse_match_rows,
    rebuild_elo_history,
    summarize_rebuild,
)


def test_actual_score_from_goals() -> None:
    assert actual_score_from_goals(2, 0) == (1.0, 0.0)
    assert actual_score_from_goals(1, 1) == (0.5, 0.5)
    assert actual_score_from_goals(0, 2) == (0.0, 1.0)


def test_rebuild_uses_standard_elo_and_preserves_conservation() -> None:
    matches = parse_match_rows(
        [
            {
                "date": "2020-01-01",
                "home_team": "Alpha",
                "away_team": "Beta",
                "home_score": "1",
                "away_score": "0",
                "tournament": "Friendly",
                "city": "A",
                "country": "A",
                "neutral": "FALSE",
            }
        ]
    )

    rows = rebuild_elo_history(matches)

    assert rows[0]["home_pre_match_elo"] == "1500.000000"
    assert rows[0]["away_pre_match_elo"] == "1500.000000"
    assert rows[0]["expected_home_score"] == "0.500000"
    assert rows[0]["home_elo_change"] == "10.000000"
    assert rows[0]["away_elo_change"] == "-10.000000"
    assert rows[0]["home_post_match_elo"] == "1510.000000"
    assert rows[0]["away_post_match_elo"] == "1490.000000"
    assert rows[0]["elo_k_factor"] == "20.000000"
    assert rows[0]["elo_home_advantage"] == "0.000000"
    assert rows[0]["elo_goal_diff_multiplier"] == "1.000000"
    assert rows[0]["elo_tournament_weight"] == "1.000000"
    assert abs(float(rows[0]["home_elo_change"]) + float(rows[0]["away_elo_change"])) < 1e-9


def test_rebuild_sort_is_date_then_source_row_number() -> None:
    matches = parse_match_rows(
        [
            {
                "date": "2020-01-02",
                "home_team": "Late",
                "away_team": "Team",
                "home_score": "1",
                "away_score": "0",
            },
            {
                "date": "2020-01-01",
                "home_team": "Early",
                "away_team": "Team",
                "home_score": "1",
                "away_score": "0",
            },
            {
                "date": "2020-01-01",
                "home_team": "SecondSameDay",
                "away_team": "Team",
                "home_score": "0",
                "away_score": "0",
            },
        ]
    )

    rows = rebuild_elo_history(matches)

    assert [row["home_team"] for row in rows] == ["Early", "SecondSameDay", "Late"]
    assert [row["source_row_number"] for row in rows] == [3, 4, 2]


def test_invalid_neutral_value_raises() -> None:
    with pytest.raises(ValueError, match="invalid neutral"):
        parse_match_rows(
            [
                {
                    "date": "2020-01-01",
                    "home_team": "Alpha",
                    "away_team": "Beta",
                    "home_score": "1",
                    "away_score": "0",
                    "neutral": "NOPE",
                }
            ]
        )


def test_parse_match_rows_can_skip_unplayed_rows() -> None:
    rows = parse_match_rows(
        [
            {
                "date": "2020-01-01",
                "home_team": "Alpha",
                "away_team": "Beta",
                "home_score": "NA",
                "away_score": "NA",
            },
            {
                "date": "2020-01-02",
                "home_team": "Gamma",
                "away_team": "Delta",
                "home_score": "1",
                "away_score": "0",
            },
        ],
        skip_unplayed=True,
    )

    assert len(rows) == 1
    assert rows[0].home_team == "Gamma"


def test_summary_reports_core_sanity_metrics() -> None:
    rows = rebuild_elo_history(
        parse_match_rows(
            [
                {
                    "date": "2020-01-01",
                    "home_team": "Alpha",
                    "away_team": "Beta",
                    "home_score": "1",
                    "away_score": "0",
                }
            ]
        )
    )

    summary = summarize_rebuild(rows)

    assert summary.total_matches == 1
    assert summary.unique_teams == 2
    assert summary.date_min == "2020-01-01"
    assert summary.date_max == "2020-01-01"
    assert summary.max_abs_conservation_error == 0.0
    assert summary.teams_with_provisional_final_rating == 2


def test_build_elo_history_cli_writes_expected_schema(tmp_path: Path) -> None:
    input_path = tmp_path / "results.csv"
    output_path = tmp_path / "matches_with_elo.csv"
    with input_path.open("w", encoding="utf-8", newline="") as handle:
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
        writer.writerow(["2020-01-01", "Alpha", "Beta", "1", "0", "Friendly", "A", "A", "FALSE"])

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_elo_history.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "total_matches: 1" in result.stdout
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert reader.fieldnames == OUTPUT_COLUMNS
    assert rows[0]["home_pre_match_elo"] == "1500.000000"
    assert rows[0]["home_elo_change"] == "10.000000"
