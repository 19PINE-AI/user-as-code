#!/usr/bin/env python3
"""Deprecated legacy paper updater.

This former helper consumed superseded subset artifacts and patched manuscript
claims in place. Current paper updates must instead use the strict full-LOCOMO
validator, certified analytical artifacts, and current figure generators.
"""


def main():
    raise RuntimeError(
        "Deprecated: this updater consumes legacy subset artifacts."
    )


if __name__ == "__main__":
    main()
