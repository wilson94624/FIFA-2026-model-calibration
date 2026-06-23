from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.tuning.team_universe import (
    build_report,
    build_team_universe_rows,
    read_final_teams,
    write_report,
    write_team_universe,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build FIFA Predictor team universe files.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/matches_with_elo.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("data/processed/team_universe.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/team_universe_report.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    teams = read_final_teams(args.input)
    rows = build_team_universe_rows(teams)
    report = build_report(teams, rows)
    write_team_universe(args.output_csv, rows)
    write_report(args.output_json, report)

    print(f"output_csv: {args.output_csv}")
    print(f"output_json: {args.output_json}")
    print(f"team_count: {report['team_count']}")
    print(f"fifa_only_team_count: {report['fifa_only_team_count']}")
    print(f"fifa_plus_historical_team_count: {report['fifa_plus_historical_team_count']}")
    print(f"excluded_team_count: {report['excluded_team_count']}")


if __name__ == "__main__":
    main()
