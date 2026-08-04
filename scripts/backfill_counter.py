#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COUNTER_FILE = REPO_ROOT / "counter.txt"
COMMIT_PATTERN = re.compile(
    r"^chore: update daily counter \((\d{4}-\d{2}-\d{2})\)$"
)


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid ISO date: {value}") from exc


def read_counter() -> int:
    raw_value = COUNTER_FILE.read_text(encoding="utf-8").strip()

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{COUNTER_FILE} must contain a whole number") from exc

    if value < 0:
        raise ValueError(f"{COUNTER_FILE} must contain a non-negative number")

    return value


def existing_backfill_dates() -> set[str]:
    result = subprocess.run(
        ["git", "log", "--all", "--format=%s"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    dates = set()
    for subject in result.stdout.splitlines():
        match = COMMIT_PATTERN.fullmatch(subject)
        if match:
            dates.add(match.group(1))

    return dates


def create_commit(day: date, counter_value: int) -> None:
    COUNTER_FILE.write_text(f"{counter_value}\n", encoding="utf-8")
    relative_counter_path = COUNTER_FILE.relative_to(REPO_ROOT).as_posix()

    subprocess.run(
        ["git", "add", relative_counter_path],
        cwd=REPO_ROOT,
        check=True,
    )

    timestamp = f"{day.isoformat()}T12:00:00+00:00"
    commit_environment = {
        **os.environ,
        "GIT_AUTHOR_DATE": timestamp,
        "GIT_COMMITTER_DATE": timestamp,
    }

    subprocess.run(
        [
            "git",
            "commit",
            "-m",
            f"chore: update daily counter ({day.isoformat()})",
        ],
        cwd=REPO_ROOT,
        env=commit_environment,
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create one idempotent counter commit per historical day."
    )
    parser.add_argument("--start-date", required=True, type=parse_date)
    parser.add_argument("--end-date", required=True, type=parse_date)
    arguments = parser.parse_args()

    if arguments.start_date > arguments.end_date:
        parser.error("--start-date must be on or before --end-date")

    known_dates = existing_backfill_dates()
    counter_value = read_counter()
    current_day = arguments.start_date
    created_count = 0
    skipped_count = 0

    while current_day <= arguments.end_date:
        date_key = current_day.isoformat()

        if date_key in known_dates:
            skipped_count += 1
        else:
            counter_value += 1
            create_commit(current_day, counter_value)
            created_count += 1

        current_day += timedelta(days=1)

    print(
        f"Historical fill complete: {created_count} commits created, "
        f"{skipped_count} already-existing dates skipped."
    )


if __name__ == "__main__":
    main()
