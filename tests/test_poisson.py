import pytest

from src.model.poisson import (
    bivariate_poisson_score_probabilities,
    outcome_probabilities,
    score_matrix,
)


def test_score_probabilities_sum_to_one() -> None:
    probabilities = bivariate_poisson_score_probabilities(1.2, 1.2)

    assert sum(probabilities) == pytest.approx(1.0)


def test_score_probabilities_are_non_negative() -> None:
    probabilities = bivariate_poisson_score_probabilities(1.6, 0.8)

    assert all(probability >= 0.0 for probability in probabilities)


def test_outcome_probabilities_sum_to_one() -> None:
    probabilities = outcome_probabilities(score_matrix(1.4, 1.1))

    assert sum(probabilities.values()) == pytest.approx(1.0)


def test_equal_rates_are_symmetric_for_home_and_away() -> None:
    probabilities = outcome_probabilities(score_matrix(1.2, 1.2))

    assert probabilities["home"] == pytest.approx(probabilities["away"])
