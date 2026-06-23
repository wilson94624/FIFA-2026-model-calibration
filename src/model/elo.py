from __future__ import annotations

DEFAULT_K_FACTOR = 20.0


def elo_expected_score(home_elo: float, away_elo: float) -> float:
    """Return the expected home-team result on the standard ELO scale."""
    return 1.0 / (1.0 + 10.0 ** ((away_elo - home_elo) / 400.0))


def elo_update(
    home_elo: float,
    away_elo: float,
    home_score: int,
    away_score: int,
    k: float = DEFAULT_K_FACTOR,
) -> tuple[float, float]:
    """Update ELO ratings after a match.

    This is the standard baseline update. The phase-one prediction CLI uses only
    the pre-match ELO values already present in its input CSV.
    """
    actual_home = 1.0 if home_score > away_score else 0.0 if home_score < away_score else 0.5
    expected_home = elo_expected_score(home_elo, away_elo)
    delta = k * (actual_home - expected_home)
    return home_elo + delta, away_elo - delta
