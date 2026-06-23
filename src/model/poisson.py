from __future__ import annotations

import math

MAX_GOALS = 5
GAMMA = 0.08
RHO = -0.05

ScoreCell = dict[str, float | int]


def poisson_pmf(k: int, rate: float) -> float:
    if k < 0:
        return 0.0
    if rate < 0:
        raise ValueError("rate must be non-negative")
    return rate**k * math.exp(-rate) / math.factorial(k)


def bivariate_poisson_score_probabilities(
    home_rate: float,
    away_rate: float,
    max_goals: int = MAX_GOALS,
    gamma: float = GAMMA,
    rho: float = RHO,
) -> list[float]:
    """Return normalized score probabilities with Dixon-Coles low-score correction."""
    if home_rate <= 0 or away_rate <= 0:
        raise ValueError("home_rate and away_rate must be positive")

    shared = max(0.0, min(gamma, home_rate - 0.01, away_rate - 0.01))
    home_independent = home_rate - shared
    away_independent = away_rate - shared

    home_pmfs = [poisson_pmf(k, home_independent) for k in range(max_goals + 1)]
    away_pmfs = [poisson_pmf(k, away_independent) for k in range(max_goals + 1)]
    shared_pmfs = [poisson_pmf(k, shared) for k in range(max_goals + 1)]

    probabilities: list[float] = []
    for home_goals in range(max_goals + 1):
        for away_goals in range(max_goals + 1):
            probability = 0.0
            for common in range(min(home_goals, away_goals) + 1):
                probability += (
                    home_pmfs[home_goals - common]
                    * away_pmfs[away_goals - common]
                    * shared_pmfs[common]
                )

            if home_goals == 0 and away_goals == 0:
                probability *= 1.0 - rho * home_rate * away_rate
            elif home_goals == 1 and away_goals == 1:
                probability *= 1.0 - rho
            elif home_goals == 1 and away_goals == 0:
                probability *= 1.0 + rho * away_rate
            elif home_goals == 0 and away_goals == 1:
                probability *= 1.0 + rho * home_rate

            probabilities.append(max(0.0, probability))

    total = sum(probabilities) or 1.0
    return [probability / total for probability in probabilities]


def score_matrix(
    home_rate: float,
    away_rate: float,
    max_goals: int = MAX_GOALS,
    gamma: float = GAMMA,
    rho: float = RHO,
) -> list[ScoreCell]:
    size = max_goals + 1
    probabilities = bivariate_poisson_score_probabilities(
        home_rate,
        away_rate,
        max_goals=max_goals,
        gamma=gamma,
        rho=rho,
    )
    return [
        {"home": index // size, "away": index % size, "probability": probability}
        for index, probability in enumerate(probabilities)
    ]


def outcome_probabilities(matrix: list[ScoreCell]) -> dict[str, float]:
    probabilities = {"home": 0.0, "draw": 0.0, "away": 0.0}
    for score in matrix:
        home_goals = int(score["home"])
        away_goals = int(score["away"])
        probability = float(score["probability"])
        label = "home" if home_goals > away_goals else "away" if away_goals > home_goals else "draw"
        probabilities[label] += probability
    return probabilities


def mix_matrices(
    normal: list[ScoreCell],
    domination: list[ScoreCell],
    normal_weight: float = 0.7,
) -> list[ScoreCell]:
    domination_weight = 1.0 - normal_weight
    mixed: list[ScoreCell] = []
    for normal_score, domination_score in zip(normal, domination, strict=True):
        mixed.append(
            {
                "home": int(normal_score["home"]),
                "away": int(normal_score["away"]),
                "probability": normal_weight * float(normal_score["probability"])
                + domination_weight * float(domination_score["probability"]),
            }
        )

    total = sum(float(score["probability"]) for score in mixed) or 1.0
    for score in mixed:
        score["probability"] = float(score["probability"]) / total
    return mixed
