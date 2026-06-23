from src.model.expected_goals import elo_only_expected_goals


def test_equal_elo_returns_base_expected_goals() -> None:
    assert elo_only_expected_goals(1500.0, 1500.0) == (1.2, 1.2)


def test_higher_home_elo_increases_home_xg_and_decreases_away_xg() -> None:
    home_xg, away_xg = elo_only_expected_goals(1700.0, 1500.0)

    assert home_xg > 1.2
    assert away_xg < 1.2


def test_expected_goals_respects_minimum_floor() -> None:
    home_xg, away_xg = elo_only_expected_goals(900.0, 2400.0)

    assert home_xg == 0.2
    assert away_xg > 1.2
