#!/usr/bin/env python3
"""Safely merge one isolated analytical-case rerun into a canonical artifact."""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import tempfile


def aggregate(results: dict) -> None:
    by_type: dict[str, dict[str, int]] = {}
    by_n: dict[int, dict[str, int]] = {}
    for value in results["by_case"].values():
        type_row = by_type.setdefault(value["type"], {"n": 0, "correct": 0})
        n_row = by_n.setdefault(int(value["n"]), {"n": 0, "correct": 0})
        type_row["n"] += 1
        n_row["n"] += 1
        if value.get("correct"):
            type_row["correct"] += 1
            n_row["correct"] += 1

    total = len(results["by_case"])
    correct = sum(bool(value.get("correct")) for value in results["by_case"].values())
    results["aggregate"] = {
        "n_total": total,
        "n_correct": correct,
        "accuracy": correct / total if total else 0,
    }
    results["per_type"] = {
        key: {**value, "accuracy": value["correct"] / value["n"]}
        for key, value in by_type.items()
    }
    results["per_n"] = {
        str(key): {**value, "accuracy": value["correct"] / value["n"]}
        for key, value in sorted(by_n.items())
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--rerun", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--previous-question")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target_path = pathlib.Path(args.target)
    rerun_path = pathlib.Path(args.rerun)
    target = json.loads(target_path.read_text())
    rerun = json.loads(rerun_path.read_text())

    if target.get("system") != rerun.get("system"):
        raise SystemExit("system mismatch between target and rerun")
    if args.case_id not in target.get("by_case", {}):
        raise SystemExit("case is absent from target")
    if set(rerun.get("by_case", {})) != {args.case_id}:
        raise SystemExit("rerun must contain exactly the requested case")

    replacement = rerun["by_case"][args.case_id]
    if replacement.get("error"):
        raise SystemExit(f"replacement contains an error: {replacement['error']}")
    if "of 2024" not in replacement.get("question", ""):
        raise SystemExit("replacement does not contain the corrected year-qualified question")

    old = target["by_case"][args.case_id]
    target["by_case"][args.case_id] = replacement
    target.setdefault("case_repairs", {})[args.case_id] = {
        "reason": "year-ambiguous benchmark item corrected and rerun",
        "old_question": args.previous_question or old.get("question"),
        "new_question": replacement.get("question"),
        "rerun_artifact": rerun_path.name,
        "run_config": rerun.get("run_config"),
    }
    aggregate(target)
    print(
        f"{target['system']}: {args.case_id}: "
        f"{old.get('prediction')!r}/{old.get('correct')} -> "
        f"{replacement.get('prediction')!r}/{replacement.get('correct')}; "
        f"aggregate={target['aggregate']['n_correct']}/{target['aggregate']['n_total']}"
    )
    if args.dry_run:
        return

    with tempfile.NamedTemporaryFile(
        "w", dir=target_path.parent, prefix=target_path.name + ".", delete=False
    ) as handle:
        json.dump(target, handle, indent=2, ensure_ascii=False, default=str)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, target_path)


if __name__ == "__main__":
    main()
