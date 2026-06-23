import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.model.elo_rebuilder import parse_match_rows, rebuild_elo_history
from src.tuning.tournament_taxonomy import (
    category_counts,
    tournament_category,
    weight_for_tournament,
)
from src.tuning.tune_tournament_weight import evaluate_tournament_weights, parse_weights
from src.tuning.tune_tournament_weight import (
    GRID_OUTPUT_COLUMNS,
    grid_summary,
    run_tournament_weight_grid,
    write_grid_outputs,
)


def test_tournament_category_mapping() -> None:
    assert tournament_category("Friendly") == "Friendly"
    assert tournament_category("FIFA World Cup qualification") == "Qualifier"
    assert tournament_category("UEFA Nations League") == "Nations League"
    assert tournament_category("UEFA Euro") == "Continental Finals"
    assert tournament_category("Copa América") == "Continental Finals"
    assert tournament_category("FIFA World Cup") == "World Cup Finals"
    assert tournament_category("Merdeka Tournament") == "Other"


def test_weight_for_tournament_uses_category_weights() -> None:
    weights = {"Friendly": 1.0, "Qualifier": 1.5, "Other": 1.0}

    assert weight_for_tournament("FIFA World Cup qualification", weights) == 1.5
    assert weight_for_tournament("Merdeka Tournament", weights) == 1.0


def test_rebuild_uses_tournament_weight_without_changing_formula() -> None:
    matches = parse_match_rows(
        [
            {
                "date": "2020-01-01",
                "home_team": "Alpha",
                "away_team": "Beta",
                "home_score": "1",
                "away_score": "0",
                "tournament": "FIFA World Cup",
            }
        ]
    )

    rows = rebuild_elo_history(matches, k_factor=80.0, tournament_weight_fn=lambda _: 2.5)

    assert rows[0]["elo_k_factor"] == "200.000000"
    assert rows[0]["elo_tournament_weight"] == "2.500000"
    assert rows[0]["home_elo_change"] == "100.000000"
    assert rows[0]["away_elo_change"] == "-100.000000"


def test_parse_weights_rejects_unknown_category() -> None:
    with pytest.raises(ValueError, match="unknown category"):
        parse_weights(["Cup=2.0"])


def test_category_counts_preserves_all_categories() -> None:
    counts = category_counts(["Friendly", "FIFA World Cup", "UEFA Euro"])

    assert counts["Friendly"] == 1
    assert counts["World Cup Finals"] == 1
    assert counts["Continental Finals"] == 1
    assert counts["Qualifier"] == 0


def test_tournament_weight_cli_writes_json(tmp_path: Path) -> None:
    input_path = tmp_path / "matches.csv"
    input_path.write_text(
        "\n".join(
            [
                "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral",
                "2020-01-01,Alpha,Beta,1,0,Friendly,A,A,FALSE",
                "2020-01-02,Beta,Alpha,0,1,FIFA World Cup qualification,B,B,FALSE",
                "2020-01-03,Gamma,Alpha,0,1,FIFA World Cup,C,C,TRUE",
            ]
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "tournament_weight_results.json"

    result = subprocess.run(
        [
            sys.executable,
            "src/tuning/tune_tournament_weight.py",
            "--input",
            str(input_path),
            "--output-json",
            str(output_path),
            "--weight",
            "Qualifier=1.25",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert "metrics:" in result.stdout
    assert payload["weights"]["Qualifier"] == 1.25
    assert payload["category_counts"]["Friendly"] == 1
    assert payload["category_counts"]["Qualifier"] == 1
    assert payload["category_counts"]["World Cup Finals"] == 1


def test_evaluate_tournament_weights_returns_metrics(tmp_path: Path) -> None:
    input_path = tmp_path / "matches.csv"
    input_path.write_text(
        "\n".join(
            [
                "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral",
                "2020-01-01,Alpha,Beta,1,0,Friendly,A,A,FALSE",
                "2020-01-02,Beta,Alpha,0,1,FIFA World Cup qualification,B,B,FALSE",
            ]
        ),
        encoding="utf-8",
    )

    payload = evaluate_tournament_weights(input_path)

    assert set(payload["metrics"]) == {"accuracy", "log_loss", "brier_score"}
    assert payload["category_counts"]["Friendly"] == 1
    assert payload["category_counts"]["Qualifier"] == 1


def test_run_tournament_weight_grid_and_outputs(tmp_path: Path) -> None:
    input_path = tmp_path / "matches.csv"
    input_path.write_text(
        "\n".join(
            [
                "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral",
                "2020-01-01,Alpha,Beta,1,0,Friendly,A,A,FALSE",
                "2020-01-02,Beta,Alpha,0,1,FIFA World Cup qualification,B,B,FALSE",
                "2020-01-03,Gamma,Alpha,0,1,FIFA World Cup,C,C,TRUE",
            ]
        ),
        encoding="utf-8",
    )

    rows = run_tournament_weight_grid(
        input_path,
        qualifier_weights=(1.0, 1.25),
        continental_finals_weights=(1.0,),
        world_cup_finals_weights=(1.0, 1.5),
    )
    summary = grid_summary(rows)
    csv_path = tmp_path / "grid.csv"
    json_path = tmp_path / "grid.json"
    write_grid_outputs(rows, csv_path, json_path)

    assert len(rows) == 4
    assert set(summary) == {"top_log_loss", "top_brier_score", "top_accuracy"}
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        output_rows = list(reader)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert reader.fieldnames == GRID_OUTPUT_COLUMNS
    assert len(output_rows) == 4
    assert payload["fixed_weights"]["Friendly"] == 1.0
