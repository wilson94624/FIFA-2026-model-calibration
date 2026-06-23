from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

CATEGORIES = (
    "fifa_current",
    "fifa_historical",
    "successor_state",
    "regional",
    "conifa",
    "non_fifa_representative",
)

HISTORICAL_FIFA_TEAMS = {
    "Bohemia",
    "Bohemia and Moravia",
    "CIS",
    "Ceylon",
    "Czechoslovakia",
    "Dahomey",
    "Dutch East Indies",
    "FR Yugoslavia",
    "German DR",
    "Gold Coast",
    "Ireland",
    "Malaya",
    "Netherlands Antilles",
    "North Vietnam",
    "North Yemen",
    "Rhodesia",
    "Saarland",
    "Serbia and Montenegro",
    "South Vietnam",
    "Soviet Union",
    "Swaziland",
    "United Arab Republic",
    "Upper Volta",
    "Yemen DPR",
    "Yugoslavia",
    "Zaire",
}

SUCCESSOR_STATES = {
    "Armenia",
    "Azerbaijan",
    "Belarus",
    "Benin",
    "Bosnia and Herzegovina",
    "Burkina Faso",
    "Cambodia",
    "Croatia",
    "Curaçao",
    "Czech Republic",
    "Czechia",
    "DR Congo",
    "Djibouti",
    "Eswatini",
    "Estonia",
    "Georgia",
    "Ghana",
    "Guinea-Bissau",
    "Guyana",
    "Indonesia",
    "Israel",
    "Kazakhstan",
    "Kosovo",
    "Kyrgyzstan",
    "Latvia",
    "Lithuania",
    "Malawi",
    "Malaysia",
    "Moldova",
    "Montenegro",
    "Myanmar",
    "North Macedonia",
    "Republic of Ireland",
    "Russia",
    "Samoa",
    "Serbia",
    "Slovakia",
    "Slovenia",
    "Sri Lanka",
    "Tajikistan",
    "Turkmenistan",
    "Ukraine",
    "Uzbekistan",
    "Yemen",
}

CONIFA_TEAMS = {
    "Abkhazia",
    "Ambazonia",
    "Artsakh",
    "Aymara",
    "Barawa",
    "Cascadia",
    "Chagos Islands",
    "Ellan Vannin",
    "Felvidék",
    "Iraqi Kurdistan",
    "Kabylia",
    "Kurdistan",
    "Kárpátalja",
    "Matabeleland",
    "Northern Cyprus",
    "Occitania",
    "Padania",
    "Panjab",
    "Raetia",
    "Romani people",
    "South Ossetia",
    "Székely Land",
    "Tamil Eelam",
    "Tibet",
    "Tuvalu",
    "United Koreans in Japan",
    "Western Armenia",
    "Yorkshire",
}

REGIONAL_TEAMS = {
    "Alderney",
    "Andalusia",
    "Arameans Suryoye",
    "Asturias",
    "Basque Country",
    "Biafra",
    "Brittany",
    "Canary Islands",
    "Catalonia",
    "Central Spain",
    "Chameria",
    "Chechnya",
    "Cilento",
    "Corsica",
    "County of Nice",
    "Crimea",
    "Darfur",
    "Donetsk PR",
    "Délvidék",
    "East Turkestan",
    "Elba Island",
    "Franconia",
    "Frøya",
    "Galicia",
    "Gotland",
    "Gozo",
    "Guernsey",
    "Găgăuzia",
    "Hitra",
    "Hmong",
    "Isle of Man",
    "Isle of Wight",
    "Jersey",
    "Kernow",
    "Luhansk PR",
    "Madrid",
    "Mapuche",
    "Maule Sur",
    "Menorca",
    "Monaco",
    "Nice",
    "Orkney",
    "Palestinian Territories",
    "Parishes of Jersey",
    "Provence",
    "Rhodes",
    "Sark",
    "Shetland",
    "Silesia",
    "Somaliland",
    "Two Sicilies",
    "Western Armenia",
    "Western Australia",
    "Western Isles",
    "Western Sahara",
    "Ynys Môn",
    "Åland Islands",
}

NON_FIFA_REPRESENTATIVE_TEAMS = {
    "Christmas Island",
    "Cocos Islands",
    "Falkland Islands",
    "Kiribati",
    "Marshall Islands",
    "Micronesia",
    "Nauru",
    "Niue",
    "Palau",
    "Saint Helena",
    "Saint Pierre and Miquelon",
    "Vatican City",
    "Wallis Islands and Futuna",
}


def classify_team(team: str) -> str:
    if team in HISTORICAL_FIFA_TEAMS:
        return "fifa_historical"
    if team in SUCCESSOR_STATES:
        return "successor_state"
    if team in CONIFA_TEAMS:
        return "conifa"
    if team in REGIONAL_TEAMS:
        return "regional"
    if team in NON_FIFA_REPRESENTATIVE_TEAMS:
        return "non_fifa_representative"
    return "fifa_current"


def universe_flags(category: str) -> tuple[bool, bool]:
    include_fifa_only = category in {"fifa_current", "successor_state"}
    include_fifa_historical = category in {"fifa_current", "successor_state", "fifa_historical"}
    return include_fifa_only, include_fifa_historical


def category_note(category: str) -> str:
    notes = {
        "fifa_current": "Current FIFA/senior national team for calibration purposes.",
        "fifa_historical": "Defunct or former senior national team retained for historical Elo continuity.",
        "successor_state": "Current FIFA team or renamed/successor state with historical continuity.",
        "regional": "Regional, subnational, island-games, or autonomous representative team excluded from FIFA calibration universe.",
        "conifa": "CONIFA or non-FIFA representative team excluded from FIFA calibration universe.",
        "non_fifa_representative": "Representative entity not suitable for FIFA Predictor calibration universe.",
    }
    return notes[category]


def read_final_teams(matches_path: Path) -> dict[str, dict[str, float | int]]:
    teams: dict[str, dict[str, float | int]] = {}
    with matches_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            teams[row["home_team"]] = {
                "final_elo": float(row["home_post_match_elo"]),
                "matches": int(row["home_matches_after"]),
            }
            teams[row["away_team"]] = {
                "final_elo": float(row["away_post_match_elo"]),
                "matches": int(row["away_matches_after"]),
            }
    return teams


def build_team_universe_rows(
    teams: dict[str, dict[str, float | int]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for team in sorted(teams):
        category = classify_team(team)
        include_fifa_only, include_fifa_historical = universe_flags(category)
        rows.append(
            {
                "team": team,
                "category": category,
                "include_fifa_only": str(include_fifa_only).upper(),
                "include_fifa_historical": str(include_fifa_historical).upper(),
                "notes": category_note(category),
            }
        )
    return rows


def write_team_universe(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "team",
                "category",
                "include_fifa_only",
                "include_fifa_historical",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def build_report(
    teams: dict[str, dict[str, float | int]],
    universe_rows: list[dict[str, str]],
) -> dict[str, Any]:
    by_team = {row["team"]: row for row in universe_rows}
    top100 = [
        {"rank": index, "team": team, **values, **by_team[team]}
        for index, (team, values) in enumerate(
            sorted(teams.items(), key=lambda item: float(item[1]["final_elo"]), reverse=True)[:100],
            start=1,
        )
    ]
    excluded_top100 = [
        row for row in top100 if row["include_fifa_historical"] != "TRUE"
    ]
    counts = Counter(row["category"] for row in universe_rows)
    fifa_only_count = sum(1 for row in universe_rows if row["include_fifa_only"] == "TRUE")
    fifa_historical_count = sum(
        1 for row in universe_rows if row["include_fifa_historical"] == "TRUE"
    )
    retained_historical = {
        team: {
            "present": team in by_team,
            "include_fifa_historical": by_team.get(team, {}).get("include_fifa_historical")
            == "TRUE",
            "category": by_team.get(team, {}).get("category"),
        }
        for team in ("Yugoslavia", "Soviet Union", "Czechoslovakia", "German DR")
    }
    return {
        "team_count": len(universe_rows),
        "category_counts": dict(counts),
        "fifa_only_team_count": fifa_only_count,
        "fifa_plus_historical_team_count": fifa_historical_count,
        "excluded_team_count": len(universe_rows) - fifa_historical_count,
        "top100_excluded_teams": excluded_top100,
        "historical_retention_check": retained_historical,
        "recommendation": {
            "default_universe": "fifa_plus_historical",
            "use_as_calibration_default": True,
            "reason": "Retains current/successor FIFA teams plus major historical senior national teams while excluding regional, CONIFA, and non-FIFA representative teams.",
        },
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
