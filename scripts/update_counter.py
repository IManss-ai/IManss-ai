#!/usr/bin/env python3
from pathlib import Path

COUNTER_FILE = Path(__file__).resolve().parents[1] / "counter.txt"


def main() -> None:
    raw_value = COUNTER_FILE.read_text(encoding="utf-8").strip()

    try:
        current_value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{COUNTER_FILE} must contain a whole number") from exc

    if current_value < 0:
        raise ValueError(f"{COUNTER_FILE} must contain a non-negative number")

    next_value = current_value + 1
    COUNTER_FILE.write_text(f"{next_value}\n", encoding="utf-8")
    print(f"Counter updated: {current_value} -> {next_value}")


if __name__ == "__main__":
    main()
