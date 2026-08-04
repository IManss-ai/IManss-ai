#!/usr/bin/env python3
import argparse
import hashlib
import os
import random
import re
import subprocess
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COUNTER_FILE = REPO_ROOT / "counter.txt"
ORIGINAL_PATTERN = re.compile(
    r"^chore: update daily counter \((\d{4}-\d{2}-\d{2})\)$"
)
VARIED_PATTERN = re.compile(
    r"^chore: activity counter \((\d{4}-\d{2}-\d{2}) #\d+\)$"
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


def day_rng(day: date) -> random.Random:
    digest = hashlib.sha256(f"IManss-ai-activity-v1:{day.isoformat()}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def target_for_day(day: date) -> int:
    rng = day_rng(day)
    if day.weekday() >= 5:
        target = rng.choices([1, 2, 3, 4, 5], weights=[24, 32, 24, 14, 6])[0]
    else:
        target = rng.choices(
            [2, 3, 4, 5, 6, 7, 8, 10],
            weights=[6, 12, 18, 21, 18, 13, 8, 4],
        )[0]
        if rng.random() < 0.08:
            target += rng.randint(4, 8)
    return target


def commit_times(day: date, target: int) -> list[str]:
    rng = day_rng(day)
    minutes = sorted(rng.sample(range(9 * 60, 22 * 60), target))
    return [
        f"{day.isoformat()}T{minute // 60:02d}:{minute % 60:02d}:00+05:00"
        for minute in minutes
    ]


def existing_counts() -> Counter[str]:
    result = subprocess.run(
        ["git", "log", "--all", "--format=%ad%x00%s", "--date=short"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    counts: Counter[str] = Counter()
    for line in result.stdout.splitlines():
        _, separator, subject = line.partition("\x00")
        if not separator:
            continue
        match = ORIGINAL_PATTERN.fullmatch(subject) or VARIED_PATTERN.fullmatch(subject)
        if match:
            counts[match.group(1)] += 1
    return counts


def create_commit(day: date, sequence: int, counter_value: int, timestamp: str) -> None:
    COUNTER_FILE.write_text(f"{counter_value}\n", encoding="utf-8")
    relative_path = COUNTER_FILE.relative_to(REPO_ROOT).as_posix()
    subprocess.run(["git", "add", relative_path], cwd=REPO_ROOT, check=True)
    environment = {
        **os.environ,
        "GIT_AUTHOR_DATE": timestamp,
        "GIT_COMMITTER_DATE": timestamp,
    }
    subprocess.run(
        [
            "git",
            "commit",
            "-m",
            f"chore: activity counter ({day.isoformat()} #{sequence:02d})",
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=True,
    )


def push_commits() -> None:
    subprocess.run(
        ["git", "-c", "pack.window=0", "-c", "pack.depth=0", "push"],
        cwd=REPO_ROOT,
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an idempotent, varied number of counter commits per day."
    )
    parser.add_argument("--start-date", required=True, type=parse_date)
    parser.add_argument("--end-date", required=True, type=parse_date)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--push-every", type=int, default=0)
    arguments = parser.parse_args()
    if arguments.start_date > arguments.end_date:
        parser.error("--start-date must be on or before --end-date")
    if arguments.push_every < 0:
        parser.error("--push-every must be zero or greater")

    counts = existing_counts()
    counter_value = read_counter()
    current_day = arguments.start_date
    created = 0
    unpushed = 0

    while current_day <= arguments.end_date:
        key = current_day.isoformat()
        target = target_for_day(current_day)
        present = counts[key]
        missing = max(0, target - present)
        print(f"{key}: target={target}, existing={present}, create={missing}")

        if not arguments.dry_run:
            times = commit_times(current_day, target)
            for sequence in range(present + 1, target + 1):
                counter_value += 1
                create_commit(current_day, sequence, counter_value, times[sequence - 1])
                created += 1
                unpushed += 1
                if arguments.push_every and unpushed >= arguments.push_every:
                    push_commits()
                    unpushed = 0

        current_day += timedelta(days=1)

    if not arguments.dry_run and arguments.push_every and unpushed:
        push_commits()

    print(f"Varied activity complete: {created} commits created.")


if __name__ == "__main__":
    main()
