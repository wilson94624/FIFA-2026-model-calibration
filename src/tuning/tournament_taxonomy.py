from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

TOURNAMENT_CATEGORIES = (
    "Friendly",
    "Qualifier",
    "Nations League",
    "Continental Finals",
    "World Cup Finals",
    "Other",
)

CONTINENTAL_FINALS = {
    "AFC Asian Cup",
    "African Cup of Nations",
    "Copa América",
    "CONCACAF Championship",
    "CONCACAF Gold Cup",
    "Gold Cup",
    "Oceania Nations Cup",
    "UEFA Euro",
}

NATIONS_LEAGUE_KEYWORDS = (
    "Nations League",
)


def tournament_category(tournament: str) -> str:
    name = tournament.strip()
    lower = name.lower()
    if name == "Friendly":
        return "Friendly"
    if name == "FIFA World Cup":
        return "World Cup Finals"
    if "qualification" in lower or "qualifier" in lower:
        return "Qualifier"
    if any(keyword.lower() in lower for keyword in NATIONS_LEAGUE_KEYWORDS):
        return "Nations League"
    if name in CONTINENTAL_FINALS:
        return "Continental Finals"
    return "Other"


def category_counts(tournaments: Iterable[str]) -> dict[str, int]:
    counts = Counter(tournament_category(tournament) for tournament in tournaments)
    return {category: counts.get(category, 0) for category in TOURNAMENT_CATEGORIES}


def weight_for_tournament(tournament: str, weights: dict[str, float]) -> float:
    return float(weights.get(tournament_category(tournament), weights.get("Other", 1.0)))
