from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.model.elo import DEFAULT_K_FACTOR, elo_expected_score

INITIAL_RATING = 1500.0
HOME_ADVANTAGE = 0.0
GOAL_DIFF_MULTIPLIER = 1.0
TOURNAMENT_WEIGHT = 1.0
PROVISIONAL_MATCH_THRESHOLD = 30
MODEL_VERSION = "standard_elo_v1"

REQUIRED_COLUMNS = (
    "date",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
)

OPTIONAL_PASSTHROUGH_COLUMNS = (
    "tournament",
    "city",
    "country",
    "neutral",
)

OUTPUT_COLUMNS = [
    "match_id",
    "source_row_number",
    "date",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "tournament",
    "city",
    "country",
    "neutral",
    "home_pre_match_elo",
    "away_pre_match_elo",
    "home_post_match_elo",
    "away_post_match_elo",
    "home_elo_change",
    "away_elo_change",
    "expected_home_score",
    "expected_away_score",
    "actual_home_score",
    "actual_away_score",
    "home_matches_before",
    "away_matches_before",
    "home_matches_after",
    "away_matches_after",
    "home_is_provisional",
    "away_is_provisional",
    "elo_initial_rating",
    "elo_k_factor",
    "elo_home_advantage",
    "elo_goal_diff_multiplier",
    "elo_tournament_weight",
    "elo_model_version",
]


@dataclass(frozen=True)
class MatchInput:
    source_row_number: int
    match_date: date
    date_text: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    tournament: str
    city: str
    country: str
    neutral: str


@dataclass(frozen=True)
class RebuildSummary:
    total_matches: int
    unique_teams: int
    date_min: str
    date_max: str
    rating_min: float
    rating_max: float
    mean_rating: float
    max_abs_conservation_error: float
    teams_with_provisional_final_rating: int


def parse_match_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"invalid date {value!r}; expected YYYY-MM-DD") from exc


def actual_score_from_goals(home_score: int, away_score: int) -> tuple[float, float]:
    if home_score > away_score:
        return 1.0, 0.0
    if home_score < away_score:
        return 0.0, 1.0
    return 0.5, 0.5


def update_elo_pair(
    home_elo: float,
    away_elo: float,
    actual_home: float,
    k_factor: float = DEFAULT_K_FACTOR,
) -> tuple[float, float, float, float, float, float]:
    expected_home = elo_expected_score(home_elo, away_elo)
    expected_away = 1.0 - expected_home
    actual_away = 1.0 - actual_home
    home_change = k_factor * (actual_home - expected_home)
    away_change = -home_change
    return (
        home_elo + home_change,
        away_elo + away_change,
        home_change,
        away_change,
        expected_home,
        expected_away,
    )


def _is_unplayed_score(value: str) -> bool:
    return value.strip().upper() in {"", "NA", "N/A"}


def parse_match_rows(rows: list[dict[str, str]], skip_unplayed: bool = False) -> list[MatchInput]:
    parsed: list[MatchInput] = []
    for index, row in enumerate(rows, start=2):
        missing = [column for column in REQUIRED_COLUMNS if column not in row]
        if missing:
            raise ValueError(f"CSV row {index} missing columns: {missing}")

        home_team = row["home_team"].strip()
        away_team = row["away_team"].strip()
        if not home_team or not away_team:
            raise ValueError(f"CSV row {index} has an empty team name")

        try:
            home_score = int(row["home_score"])
            away_score = int(row["away_score"])
        except ValueError as exc:
            if skip_unplayed and (
                _is_unplayed_score(row["home_score"]) or _is_unplayed_score(row["away_score"])
            ):
                continue
            raise ValueError(f"CSV row {index} has invalid score values: {exc}") from exc
        if home_score < 0 or away_score < 0:
            raise ValueError(f"CSV row {index} has negative score values")

        neutral = row.get("neutral", "").strip()
        if neutral and neutral not in {"TRUE", "FALSE"}:
            raise ValueError(f"CSV row {index} has invalid neutral value {neutral!r}")

        parsed.append(
            MatchInput(
                source_row_number=index,
                match_date=parse_match_date(row["date"].strip()),
                date_text=row["date"].strip(),
                home_team=home_team,
                away_team=away_team,
                home_score=home_score,
                away_score=away_score,
                tournament=row.get("tournament", ""),
                city=row.get("city", ""),
                country=row.get("country", ""),
                neutral=neutral,
            )
        )
    return parsed


def sort_matches_chronologically(matches: list[MatchInput]) -> list[MatchInput]:
    return sorted(matches, key=lambda match: (match.match_date, match.source_row_number))


def _format_float(value: float) -> str:
    return f"{value:.6f}"


def rebuild_elo_history(
    matches: list[MatchInput],
    initial_rating: float = INITIAL_RATING,
    k_factor: float = DEFAULT_K_FACTOR,
    model_version: str = MODEL_VERSION,
) -> list[dict[str, Any]]:
    ratings: dict[str, float] = {}
    matches_played: dict[str, int] = {}
    output: list[dict[str, Any]] = []

    for output_index, match in enumerate(sort_matches_chronologically(matches), start=1):
        home_pre = ratings.get(match.home_team, initial_rating)
        away_pre = ratings.get(match.away_team, initial_rating)
        home_before = matches_played.get(match.home_team, 0)
        away_before = matches_played.get(match.away_team, 0)
        actual_home, actual_away = actual_score_from_goals(match.home_score, match.away_score)
        (
            home_post,
            away_post,
            home_change,
            away_change,
            expected_home,
            expected_away,
        ) = update_elo_pair(home_pre, away_pre, actual_home, k_factor)

        home_after = home_before + 1
        away_after = away_before + 1
        ratings[match.home_team] = home_post
        ratings[match.away_team] = away_post
        matches_played[match.home_team] = home_after
        matches_played[match.away_team] = away_after

        output.append(
            {
                "match_id": f"intl_results_{output_index:06d}",
                "source_row_number": match.source_row_number,
                "date": match.date_text,
                "home_team": match.home_team,
                "away_team": match.away_team,
                "home_score": match.home_score,
                "away_score": match.away_score,
                "tournament": match.tournament,
                "city": match.city,
                "country": match.country,
                "neutral": match.neutral,
                "home_pre_match_elo": _format_float(home_pre),
                "away_pre_match_elo": _format_float(away_pre),
                "home_post_match_elo": _format_float(home_post),
                "away_post_match_elo": _format_float(away_post),
                "home_elo_change": _format_float(home_change),
                "away_elo_change": _format_float(away_change),
                "expected_home_score": _format_float(expected_home),
                "expected_away_score": _format_float(expected_away),
                "actual_home_score": _format_float(actual_home),
                "actual_away_score": _format_float(actual_away),
                "home_matches_before": home_before,
                "away_matches_before": away_before,
                "home_matches_after": home_after,
                "away_matches_after": away_after,
                "home_is_provisional": str(home_before < PROVISIONAL_MATCH_THRESHOLD).upper(),
                "away_is_provisional": str(away_before < PROVISIONAL_MATCH_THRESHOLD).upper(),
                "elo_initial_rating": _format_float(initial_rating),
                "elo_k_factor": _format_float(k_factor),
                "elo_home_advantage": _format_float(HOME_ADVANTAGE),
                "elo_goal_diff_multiplier": _format_float(GOAL_DIFF_MULTIPLIER),
                "elo_tournament_weight": _format_float(TOURNAMENT_WEIGHT),
                "elo_model_version": model_version,
            }
        )
    return output


def summarize_rebuild(rows: list[dict[str, Any]]) -> RebuildSummary:
    if not rows:
        raise ValueError("at least one rebuilt match row is required")

    teams = {str(row["home_team"]) for row in rows} | {str(row["away_team"]) for row in rows}
    final_ratings: dict[str, float] = {}
    final_matches: dict[str, int] = {}
    conservation_errors: list[float] = []
    all_ratings: list[float] = []
    for row in rows:
        home_post = float(row["home_post_match_elo"])
        away_post = float(row["away_post_match_elo"])
        final_ratings[str(row["home_team"])] = home_post
        final_ratings[str(row["away_team"])] = away_post
        final_matches[str(row["home_team"])] = int(row["home_matches_after"])
        final_matches[str(row["away_team"])] = int(row["away_matches_after"])
        all_ratings.extend([home_post, away_post])
        conservation_errors.append(abs(float(row["home_elo_change"]) + float(row["away_elo_change"])))

    return RebuildSummary(
        total_matches=len(rows),
        unique_teams=len(teams),
        date_min=min(str(row["date"]) for row in rows),
        date_max=max(str(row["date"]) for row in rows),
        rating_min=min(all_ratings),
        rating_max=max(all_ratings),
        mean_rating=sum(final_ratings.values()) / len(final_ratings),
        max_abs_conservation_error=max(conservation_errors),
        teams_with_provisional_final_rating=sum(
            1 for value in final_matches.values() if value < PROVISIONAL_MATCH_THRESHOLD
        ),
    )


def read_results_csv(path: Path, skip_unplayed: bool = True) -> list[MatchInput]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path} is missing a header row")
        missing = [column for column in REQUIRED_COLUMNS if column not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path} missing required columns: {missing}")
        return parse_match_rows(list(reader), skip_unplayed=skip_unplayed)


def count_csv_data_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def write_rebuilt_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
