from __future__ import annotations

from typing import Any


def player_is_unavailable(player_name: str, unavailable: list[Any]) -> bool:
    normalized = player_name.casefold().replace(".", " ").split()
    last_name = normalized[-1] if normalized else player_name.casefold()
    for item in unavailable:
        name = str(item.get("name", "")) if isinstance(item, dict) else str(item)
        if last_name in name.casefold() or name.casefold() in player_name.casefold():
            return True
    return False


def active_pqs(
    team: dict[str, Any],
    unavailable: list[Any] | None = None,
    fatigue: float = 0.0,
) -> tuple[float, float, float]:
    """Legacy PQS roster logic kept for future calibration experiments.

    The ELO-only phase-one baseline does not import this module.
    """
    unavailable = unavailable or []
    if not team.get("has_data") or not team.get("players"):
        base = float(team.get("starting_pqs", 0.25))
        return base * (1.0 - fatigue), base * (1.0 - fatigue), float(team.get("bench_pqs", 0.2))

    active = [
        player
        for player in team["players"]
        if not player_is_unavailable(str(player.get("name", "")), unavailable)
    ]
    if not active:
        active = list(team["players"])

    active.sort(key=lambda player: float(player.get("efficiency_score", 0.0)), reverse=True)
    starters = active[:11]
    bench = active[11:]
    attackers = [player for player in starters if player.get("position") in {"FW", "MF"}]
    defenders = [player for player in starters if player.get("position") in {"DF", "GK"}]

    fallback = float(team.get("starting_pqs", 0.25))
    attack = (
        sum(float(player.get("efficiency_score", 0.0)) for player in attackers) / len(attackers)
        if attackers
        else fallback
    )
    defense = (
        sum(float(player.get("efficiency_score", 0.0)) for player in defenders) / len(defenders)
        if defenders
        else fallback
    )
    bench_score = (
        sum(float(player.get("efficiency_score", 0.0)) for player in bench) / len(bench)
        if bench
        else 0.01
    )
    return attack * (1.0 - fatigue), defense * (1.0 - fatigue), bench_score
