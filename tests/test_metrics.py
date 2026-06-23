import pytest

from src.model.metrics import accuracy, brier_score, multiclass_log_loss


def test_perfect_predictions_have_full_accuracy() -> None:
    y_true = ["home", "draw", "away"]
    y_prob = [
        {"home": 1.0, "draw": 0.0, "away": 0.0},
        {"home": 0.0, "draw": 1.0, "away": 0.0},
        {"home": 0.0, "draw": 0.0, "away": 1.0},
    ]

    assert accuracy(y_true, y_prob) == 1.0


def test_log_loss_and_brier_use_fixed_label_order() -> None:
    y_true = ["home", "away"]
    y_prob = [
        (0.7, 0.2, 0.1),
        (0.1, 0.2, 0.7),
    ]

    assert multiclass_log_loss(y_true, y_prob) == pytest.approx(0.3566749439)
    assert brier_score(y_true, y_prob) == pytest.approx(0.14)


def test_invalid_label_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="invalid label"):
        accuracy(["win"], [{"home": 1.0, "draw": 0.0, "away": 0.0}])
