from __future__ import annotations

C1 = 0.75
BASE_HOME_XG = 1.2
BASE_AWAY_XG = 1.2
MIN_XG = 0.2


def elo_only_expected_goals(
    home_elo: float,
    away_elo: float,
    c1: float = C1,
    base_home: float = BASE_HOME_XG,
    base_away: float = BASE_AWAY_XG,
    min_xg: float = MIN_XG,
) -> tuple[float, float]:
    """Convert pre-match ELO ratings into expected goals.

    Phase one intentionally excludes PQS, injuries, fatigue, host effects,
    tactical style, and domination adjustments.
    """
    elo_diff = home_elo - away_elo
    home_xg = max(min_xg, base_home + c1 * elo_diff / 450.0)
    away_xg = max(min_xg, base_away - c1 * elo_diff / 450.0)
    return home_xg, away_xg
