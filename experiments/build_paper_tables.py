#!/usr/bin/env python3
"""Deprecated legacy-subset LaTeX table generator.

The current body_tables.tex is certified from the two full-LOCOMO suites.
Regenerating it from older subset artifacts would silently restore stale paper
claims, so this entry point is intentionally disabled.
"""


def main():
    raise RuntimeError(
        "Deprecated: would overwrite current tables with legacy subset results."
    )


if __name__ == "__main__":
    main()
