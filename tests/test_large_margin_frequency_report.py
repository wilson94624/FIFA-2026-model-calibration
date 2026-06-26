import json
import subprocess
import sys
from pathlib import Path

from src.tuning.large_margin_frequency_report import (
    add_world_cup_stage_proxy,
    build_large_margin_frequency_report,
    elo_bucket,
    gd_bucket,
    summarize_rows,
    write_outputs,
)


def write_processed_matches(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "match_id,source_row_number,date,home_team,away_team,home_score,away_score,tournament,city,country,neutral,home_pre_match_elo,away_pre_match_elo",
                "m1,1,1986-06-01,France,Iraq,4,0,FIFA World Cup,,,TRUE,1800,1450",
                "m2,2,1986-06-02,Brazil,Haiti,5,0,FIFA World Cup,,,TRUE,1820,1400",
                "m3,3,1986-06-03,France,Brazil,1,1,FIFA World Cup,,,TRUE,1800,1820",
                "m4,4,1986-06-04,Iraq,Haiti,0,0,FIFA World Cup,,,TRUE,1450,1400",
                "m5,5,1986-06-05,France,Haiti,3,0,FIFA World Cup,,,TRUE,1800,1400",
                "m6,6,1986-06-06,Brazil,Iraq,2,1,FIFA World Cup,,,TRUE,1820,1450",
                "m7,7,2004-06-01,Spain,Italy,1,0,UEFA Euro,,,TRUE,1750,1740",
                "m8,8,2004-06-02,Germany,Latvia,4,1,UEFA Euro,,,TRUE,1780,1500",
                "m9,9,2006-06-01,Argentina,Serbia,6,0,FIFA World Cup,,,TRUE,1850,1500",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_bucket_helpers() -> None:
    assert gd_bucket(0) == "GD=0"
    assert gd_bucket(1) == "GD=1"
    assert gd_bucket(2) == "GD=2"
    assert gd_bucket(3) == "GD=3"
    assert gd_bucket(4) == "GD=4"
    assert gd_bucket(5) == "GD>=5"
    assert elo_bucket({"home_pre_match_elo": "1800", "away_pre_match_elo": "1710"}) == "abs_elo_diff_lt_100"
    assert elo_bucket({"home_pre_match_elo": "1800", "away_pre_match_elo": "1300"}) == "abs_elo_diff_400_plus"


def test_stage_proxy_and_summary(tmp_path: Path) -> None:
    path = tmp_path / "matches.csv"
    write_processed_matches(path)
    import csv

    rows = list(csv.DictReader(path.open("r", encoding="utf-8", newline="")))
    add_world_cup_stage_proxy(rows)
    world_cup_rows = [row for row in rows if row["tournament"] == "FIFA World Cup"]
    assert any(row["world_cup_stage_proxy"] == "group_stage_proxy" for row in world_cup_rows)
    assert any(row["world_cup_stage_proxy"] == "knockout_stage_proxy" for row in world_cup_rows)

    summary = summarize_rows("sample", rows)
    assert summary["matches"] == 9
    assert summary["large_margin_rates"]["gd_3_plus"]["matches"] >= 1


def test_build_large_margin_frequency_report(tmp_path: Path) -> None:
    path = tmp_path / "matches.csv"
    write_processed_matches(path)

    report = build_large_margin_frequency_report(path)

    assert report["research_only"] is True
    assert report["model_formulas_unchanged"] is True
    assert "all_processed_matches" in report["splits"]
    assert "stage_effect" in report
    assert report["stage_effect"]["stage_field_available"] is False
    assert len(report["elo_mismatch_buckets"]) == 5
    assert report["conclusions"]["keep_formal_model_baseline_unchanged"] is True


def test_write_large_margin_frequency_report_outputs(tmp_path: Path) -> None:
    path = tmp_path / "matches.csv"
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    write_processed_matches(path)
    report = build_large_margin_frequency_report(path)

    write_outputs(report, json_path, markdown_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert parsed["report"] == "large_margin_frequency_and_overfitting_risk"
    assert "# Large Margin Frequency" in markdown
    assert "Elo Mismatch Buckets" in markdown


def test_large_margin_frequency_report_cli(tmp_path: Path) -> None:
    path = tmp_path / "matches.csv"
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    write_processed_matches(path)

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/large_margin_frequency_report.py",
            "--input",
            str(path),
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
    assert "overfitting_risk:" in result.stdout
