from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence

LABEL_ORDER = ("home", "draw", "away")
ProbabilityRow = Mapping[str, float] | Sequence[float]


def _validate_label(label: str) -> None:
    if label not in LABEL_ORDER:
        raise ValueError(f"invalid label {label!r}; expected one of {LABEL_ORDER}")


def _probability_for(row: ProbabilityRow, label: str) -> float:
    if isinstance(row, Mapping):
        missing = [key for key in LABEL_ORDER if key not in row]
        if missing:
            raise ValueError(f"probability row missing labels: {missing}")
        return float(row[label])

    if len(row) != len(LABEL_ORDER):
        raise ValueError(f"probability sequence must have {len(LABEL_ORDER)} values")
    return float(row[LABEL_ORDER.index(label)])


def _rows(y_true: Iterable[str], y_prob: Iterable[ProbabilityRow]) -> list[tuple[str, ProbabilityRow]]:
    rows = list(zip(y_true, y_prob, strict=True))
    for label, _ in rows:
        _validate_label(label)
    return rows


def accuracy(y_true: Iterable[str], y_prob: Iterable[ProbabilityRow]) -> float:
    rows = _rows(y_true, y_prob)
    if not rows:
        raise ValueError("at least one row is required")

    correct = 0
    for label, probabilities in rows:
        predicted = max(LABEL_ORDER, key=lambda candidate: _probability_for(probabilities, candidate))
        if predicted == label:
            correct += 1
    return correct / len(rows)


def multiclass_log_loss(
    y_true: Iterable[str],
    y_prob: Iterable[ProbabilityRow],
    eps: float = 1e-15,
) -> float:
    rows = _rows(y_true, y_prob)
    if not rows:
        raise ValueError("at least one row is required")

    total = 0.0
    for label, probabilities in rows:
        probability = min(1.0 - eps, max(eps, _probability_for(probabilities, label)))
        total -= math.log(probability)
    return total / len(rows)


def brier_score(y_true: Iterable[str], y_prob: Iterable[ProbabilityRow]) -> float:
    rows = _rows(y_true, y_prob)
    if not rows:
        raise ValueError("at least one row is required")

    total = 0.0
    for label, probabilities in rows:
        for candidate in LABEL_ORDER:
            target = 1.0 if candidate == label else 0.0
            total += (_probability_for(probabilities, candidate) - target) ** 2
    return total / len(rows)
