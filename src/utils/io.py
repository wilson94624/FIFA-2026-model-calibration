from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

REQUIRED_MATCH_COLUMNS = (
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "home_pre_match_elo",
    "away_pre_match_elo",
)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path} is missing a header row")
        missing = [column for column in REQUIRED_MATCH_COLUMNS if column not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path} missing required columns: {missing}")
        return list(reader)


def write_csv_rows(path: Path, rows: Iterable[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
