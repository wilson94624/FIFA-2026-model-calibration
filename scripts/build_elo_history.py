from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model.elo_rebuilder import (
    DEFAULT_K_FACTOR,
    INITIAL_RATING,
    MODEL_VERSION,
    count_csv_data_rows,
    read_results_csv,
    rebuild_elo_history,
    summarize_rebuild,
    write_rebuilt_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild standard Elo history from results.csv.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/raw/international_results-master/results.csv"),
        help="Input international_results results.csv path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/matches_with_elo.csv"),
        help="Output processed matches-with-Elo CSV path.",
    )
    parser.add_argument("--initial-rating", type=float, default=INITIAL_RATING)
    parser.add_argument("--k-factor", type=float, default=DEFAULT_K_FACTOR)
    parser.add_argument("--model-version", default=MODEL_VERSION)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on unplayed rows with blank/NA scores instead of skipping them.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_rows = count_csv_data_rows(args.input)
    matches = read_results_csv(args.input, skip_unplayed=not args.strict)
    rows = rebuild_elo_history(
        matches,
        initial_rating=args.initial_rating,
        k_factor=args.k_factor,
        model_version=args.model_version,
    )
    write_rebuilt_csv(args.output, rows)
    summary = summarize_rebuild(rows)

    print(f"output: {args.output}")
    print(f"raw_rows: {raw_rows}")
    print(f"skipped_unplayed_rows: {raw_rows - len(matches)}")
    print(f"total_matches: {summary.total_matches}")
    print(f"unique_teams: {summary.unique_teams}")
    print(f"date_min: {summary.date_min}")
    print(f"date_max: {summary.date_max}")
    print(f"rating_min: {summary.rating_min:.6f}")
    print(f"rating_max: {summary.rating_max:.6f}")
    print(f"mean_final_rating: {summary.mean_rating:.6f}")
    print(f"max_abs_conservation_error: {summary.max_abs_conservation_error:.12f}")
    print(f"teams_with_provisional_final_rating: {summary.teams_with_provisional_final_rating}")


if __name__ == "__main__":
    main()
