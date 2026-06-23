from __future__ import annotations

from collections.abc import Iterable, Mapping

from src.model.expected_goals import elo_only_expected_goals
from src.model.metrics import accuracy, brier_score, multiclass_log_loss
from src.model.poisson import outcome_probabilities, score_matrix

LABEL_ORDER = ("home", "draw", "away")


def actual_label(home_score: int, away_score: int) -> str:
    return "home" if home_score > away_score else "away" if away_score > home_score else "draw"


def probabilities_from_pre_match_elo(home_elo: float, away_elo: float) -> dict[str, float]:
    home_xg, away_xg = elo_only_expected_goals(home_elo, away_elo)
    return outcome_probabilities(score_matrix(home_xg, away_xg))


def _is_neutral(row: Mapping[str, object]) -> bool:
    return str(row.get("neutral", "")).strip().upper() == "TRUE"


def evaluate_rebuilt_elo_rows(
    rows: Iterable[Mapping[str, object]],
    home_advantage_bonus: float = 0.0,
) -> dict[str, float]:
    y_true: list[str] = []
    y_prob: list[dict[str, float]] = []

    for index, row in enumerate(rows, start=1):
        try:
            home_score = int(row["home_score"])
            away_score = int(row["away_score"])
            home_elo = float(row["home_pre_match_elo"])
            away_elo = float(row["away_pre_match_elo"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid rebuilt Elo row {index}: {exc}") from exc

        adjusted_home_elo = home_elo if _is_neutral(row) else home_elo + home_advantage_bonus
        y_true.append(actual_label(home_score, away_score))
        y_prob.append(probabilities_from_pre_match_elo(adjusted_home_elo, away_elo))

    if not y_true:
        raise ValueError("at least one rebuilt Elo row is required")

    return {
        "accuracy": accuracy(y_true, y_prob),
        "log_loss": multiclass_log_loss(y_true, y_prob),
        "brier_score": brier_score(y_true, y_prob),
    }


def rank_metric_rows(rows: list[dict[str, float]]) -> dict[str, dict[str, float]]:
    if not rows:
        raise ValueError("at least one metric row is required")

    return {
        "best_accuracy": max(rows, key=lambda row: row["accuracy"]),
        "best_log_loss": min(rows, key=lambda row: row["log_loss"]),
        "best_brier_score": min(rows, key=lambda row: row["brier_score"]),
    }
