#!/usr/bin/env python3
"""Validate canonical artifacts and reproduce paper-facing statistics offline."""

from analyze_uncertainty import main as analyze
from validate_reported_results import main as validate


def main() -> None:
    print("== Validate canonical result artifacts ==")
    validate()
    print("\n== Reproduce paper-facing intervals and paired tests ==")
    analyze()


if __name__ == "__main__":
    main()
