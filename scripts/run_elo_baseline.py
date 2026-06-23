from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model.expected_goals import elo_only_expected_goals
from src.model.metrics import accuracy, brier_score, multiclass_log_loss
from src.model.poisson import outcome_probabilities, score_matrix
from src.utils.io import read_csv_rows, write_csv_rows

OUTPUT_COLUMNS = [
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "home_pre_match_elo",
    "away_pre_match_elo",
    "home_xg",
    "away_xg",
    "prob_home",
    "prob_draw",
    "prob_away",
    "predicted_label",
    "actual_label",
]


def actual_label(home_score: int, away_score: int) -> str:
    return "home" if home_score > away_score else "away" if away_score > home_score else "draw"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the phase-one ELO-only calibration baseline.")
    parser.add_argument("--input", required=True, type=Path, help="Historical matches CSV path.")
    parser.add_argument("--output", required=True, type=Path, help="Prediction output CSV path.")
    return parser.parse_args()


def run(input_path: Path, output_path: Path) -> dict[str, float]:
    rows = read_csv_rows(input_path)
    if not rows:
        raise ValueError(f"{input_path} contains no match rows")

    output_rows: list[dict[str, object]] = []
    y_true: list[str] = []
    y_prob: list[dict[str, float]] = []

    for index, row in enumerate(rows, start=2):
        try:
            home_score = int(row["home_score"])
            away_score = int(row["away_score"])
            home_elo = float(row["home_pre_match_elo"])
            away_elo = float(row["away_pre_match_elo"])
        except ValueError as exc:
            raise ValueError(f"invalid numeric value on CSV row {index}: {exc}") from exc

        home_xg, away_xg = elo_only_expected_goals(home_elo, away_elo)
        probabilities = outcome_probabilities(score_matrix(home_xg, away_xg))
        predicted_label = max(("home", "draw", "away"), key=lambda label: probabilities[label])
        label = actual_label(home_score, away_score)

        y_true.append(label)
        y_prob.append(probabilities)
        output_rows.append(
            {
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "home_score": home_score,
                "away_score": away_score,
                "home_pre_match_elo": home_elo,
                "away_pre_match_elo": away_elo,
                "home_xg": round(home_xg, 6),
                "away_xg": round(away_xg, 6),
                "prob_home": round(probabilities["home"], 8),
                "prob_draw": round(probabilities["draw"], 8),
                "prob_away": round(probabilities["away"], 8),
                "predicted_label": predicted_label,
                "actual_label": label,
            }
        )

    write_csv_rows(output_path, output_rows, OUTPUT_COLUMNS)
    return {
        "matches": float(len(output_rows)),
        "accuracy": accuracy(y_true, y_prob),
        "log_loss": multiclass_log_loss(y_true, y_prob),
        "brier_score": brier_score(y_true, y_prob),
    }


def main() -> None:
    args = parse_args()
    metrics = run(args.input, args.output)
    print(f"matches: {int(metrics['matches'])}")
    print(f"accuracy: {metrics['accuracy']:.6f}")
    print(f"log_loss: {metrics['log_loss']:.6f}")
    print(f"brier_score: {metrics['brier_score']:.6f}")


if __name__ == "__main__":
    main()
