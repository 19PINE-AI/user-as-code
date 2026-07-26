#!/usr/bin/env python3
"""Validate and summarize completed full-LOCOMO evaluation artifacts.

The validator treats the benchmark source as authoritative.  It checks every
``(conversation, qa_idx)`` identifier, category, stored official score,
judge field, model/provider disclosure, dataset hash, and aggregate before
printing paper-facing metrics.  By default incomplete artifacts are errors;
``--allow-partial`` is intended only for monitoring active runs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import sys
from collections import defaultdict


EXPERIMENTS_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENTS_DIR.parent
DATA_PATH = REPO_ROOT / "benchmarks/locomo/data/locomo10.json"
RESULTS_ROOT = EXPERIMENTS_DIR / "results"

sys.path.insert(0, str(EXPERIMENTS_DIR))
from krill_client import KRILL_BASE_URL, gemini_cli_user_agent  # noqa: E402
from run_locomo_full import official_locomo_score  # noqa: E402


RUN_MODELS = {
    "full_locomo_gpt56_luna": "gpt-5.6-luna",
    "full_locomo_gemini3_flash_preview": "gemini-3-flash-preview",
}
SYSTEMS = (
    "full_context",
    "uac_v5",
    "memmachine",
    "hindsight",
    "evermemos",
    "a_mem",
    "mem0",
)
EXPECTED_TOTAL = 1_986
EXPECTED_STANDARD = 1_540
EXPECTED_ADVERSARIAL = 446
TOLERANCE = 1e-12


def _close(actual, expected) -> bool:
    if actual is None or expected is None:
        return actual is expected
    return math.isclose(float(actual), float(expected), abs_tol=TOLERANCE)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _load_benchmark() -> tuple[list[dict], dict[str, dict[int, dict]], str]:
    raw = DATA_PATH.read_bytes()
    conversations = json.loads(raw)
    expected = {
        str(conv["sample_id"]): {idx: qa for idx, qa in enumerate(conv["qa"])}
        for conv in conversations
    }
    return conversations, expected, hashlib.sha256(raw).hexdigest()


def _recompute(records: list[dict]) -> dict:
    ok = [record for record in records if record.get("status") == "ok"]
    standard = [r for r in ok if int(r["category"]) in {1, 2, 3, 4}]
    adversarial = [r for r in ok if int(r["category"]) == 5]
    by_category: dict[str, list[dict]] = defaultdict(list)
    for record in ok:
        by_category[str(record["category"])].append(record)
    return {
        "n_completed": len(ok),
        "official_locomo_score": _mean([float(r["official_score"]) for r in ok]),
        "answer_bearing": {
            "n": len(standard),
            "official_token_f1": _mean(
                [float(r["official_score"]) for r in standard]
            ),
            "judge_accuracy": _mean(
                [float(r["judge_correct"]) for r in standard]
            ),
        },
        "adversarial": {
            "n": len(adversarial),
            "refusal_accuracy": _mean(
                [float(r["official_score"]) for r in adversarial]
            ),
        },
        "per_category": {
            category: {
                "n": len(values),
                "official_score": _mean(
                    [float(r["official_score"]) for r in values]
                ),
                "judge_accuracy": _mean(
                    [float(r["judge_correct"]) for r in values]
                )
                if category != "5"
                else None,
            }
            for category, values in sorted(by_category.items())
        },
    }


def _compare_aggregate(path: pathlib.Path, stored: dict, recomputed: dict) -> list[str]:
    errors = []
    scalar_paths = (
        ("n_completed",),
        ("official_locomo_score",),
        ("answer_bearing", "n"),
        ("answer_bearing", "official_token_f1"),
        ("answer_bearing", "judge_accuracy"),
        ("adversarial", "n"),
        ("adversarial", "refusal_accuracy"),
    )
    for keys in scalar_paths:
        left = stored
        right = recomputed
        for key in keys:
            left = left.get(key) if isinstance(left, dict) else None
            right = right.get(key) if isinstance(right, dict) else None
        if isinstance(right, int):
            matches = left == right
        else:
            matches = _close(left, right)
        if not matches:
            errors.append(
                f"{path}: aggregate {'.'.join(keys)}={left!r}, "
                f"recomputed={right!r}"
            )

    stored_categories = stored.get("per_category", {})
    if set(stored_categories) != set(recomputed["per_category"]):
        errors.append(
            f"{path}: aggregate category keys {sorted(stored_categories)} != "
            f"recomputed {sorted(recomputed['per_category'])}"
        )
    for category, expected_values in recomputed["per_category"].items():
        actual_values = stored_categories.get(category, {})
        for key, expected_value in expected_values.items():
            actual_value = actual_values.get(key)
            matches = (
                actual_value == expected_value
                if isinstance(expected_value, int)
                else _close(actual_value, expected_value)
            )
            if not matches:
                errors.append(
                    f"{path}: category {category} {key}={actual_value!r}, "
                    f"recomputed={expected_value!r}"
                )
    return errors


def validate_artifact(
    path: pathlib.Path,
    *,
    run_name: str,
    expected_model: str,
    expected_qas: dict[str, dict[int, dict]],
    dataset_hash: str,
    allow_partial: bool,
) -> tuple[dict, list[str]]:
    result = json.loads(path.read_text())
    errors: list[str] = []

    expected_metadata = {
        "benchmark": "LOCOMO",
        "provider": "krill",
        "base_url": KRILL_BASE_URL,
        "model": expected_model,
        "dataset_sha256": dataset_hash,
        "system": path.stem,
        "user_agent": gemini_cli_user_agent(expected_model),
    }
    for key, expected_value in expected_metadata.items():
        if result.get(key) != expected_value:
            errors.append(
                f"{path}: {key}={result.get(key)!r}, expected={expected_value!r}"
            )

    selection = result.get("selection", {})
    selection_expected = {
        "categories": [1, 2, 3, 4, 5],
        "answer_bearing_questions": EXPECTED_STANDARD,
        "adversarial_questions": EXPECTED_ADVERSARIAL,
        "conv_start": 0,
        "conv_end": 10,
        "max_questions_per_conv": None,
        "max_sessions_per_conv": None,
        "qa_index": None,
    }
    for key, expected_value in selection_expected.items():
        if selection.get(key) != expected_value:
            errors.append(
                f"{path}: selection.{key}={selection.get(key)!r}, "
                f"expected={expected_value!r}"
            )

    details = result.get("details", {})
    unknown_conversations = set(details) - set(expected_qas)
    if unknown_conversations:
        errors.append(f"{path}: unknown conversations {sorted(unknown_conversations)}")

    all_records: list[dict] = []
    for conv_id, qa_map in expected_qas.items():
        records = details.get(conv_id, [])
        by_idx: dict[int, dict] = {}
        for record in records:
            try:
                qa_idx = int(record["qa_idx"])
            except (KeyError, TypeError, ValueError):
                errors.append(f"{path}: {conv_id} has record without integer qa_idx")
                continue
            if qa_idx in by_idx:
                errors.append(f"{path}: duplicate {conv_id}:{qa_idx}")
            by_idx[qa_idx] = record
            all_records.append(record)

        unknown_indices = set(by_idx) - set(qa_map)
        if unknown_indices:
            errors.append(f"{path}: {conv_id} unknown qa_idx {sorted(unknown_indices)}")
        missing = set(qa_map) - set(by_idx)
        if missing and not allow_partial:
            errors.append(
                f"{path}: {conv_id} missing {len(missing)} qa_idx values; "
                f"first={sorted(missing)[:10]}"
            )

        for qa_idx, record in by_idx.items():
            if qa_idx not in qa_map:
                continue
            qa = qa_map[qa_idx]
            label = f"{path}:{conv_id}:{qa_idx}"
            if record.get("qa_id") != f"{conv_id}:{qa_idx}":
                errors.append(f"{label}: invalid qa_id {record.get('qa_id')!r}")
            if int(record.get("category", -1)) != int(qa["category"]):
                errors.append(
                    f"{label}: category={record.get('category')!r}, "
                    f"expected={qa['category']!r}"
                )
            if record.get("status") != "ok":
                if not allow_partial:
                    errors.append(f"{label}: status={record.get('status')!r}")
                continue
            expected_score = official_locomo_score(
                str(record.get("scored_prediction", "")), qa
            )
            if not _close(record.get("official_score"), expected_score):
                errors.append(
                    f"{label}: official_score={record.get('official_score')!r}, "
                    f"recomputed={expected_score!r}"
                )
            category = int(qa["category"])
            judge_value = record.get("judge_correct")
            if category in {1, 2, 3, 4} and not isinstance(judge_value, bool):
                errors.append(f"{label}: missing boolean judge_correct")
            if category == 5 and judge_value is not None:
                errors.append(f"{label}: adversarial record was sent to LLM judge")

    if not allow_partial and len(all_records) != EXPECTED_TOTAL:
        errors.append(
            f"{path}: details contain {len(all_records)} records, "
            f"expected {EXPECTED_TOTAL}"
        )

    recomputed = _recompute(all_records)
    errors.extend(_compare_aggregate(path, result.get("aggregate", {}), recomputed))
    if not allow_partial:
        aggregate = result.get("aggregate", {})
        if aggregate.get("n_expected") != EXPECTED_TOTAL:
            errors.append(
                f"{path}: aggregate.n_expected={aggregate.get('n_expected')!r}, "
                f"expected={EXPECTED_TOTAL}"
            )
        if recomputed["answer_bearing"]["n"] != EXPECTED_STANDARD:
            errors.append(
                f"{path}: answer-bearing n={recomputed['answer_bearing']['n']}, "
                f"expected={EXPECTED_STANDARD}"
            )
        if recomputed["adversarial"]["n"] != EXPECTED_ADVERSARIAL:
            errors.append(
                f"{path}: adversarial n={recomputed['adversarial']['n']}, "
                f"expected={EXPECTED_ADVERSARIAL}"
            )

    return recomputed, errors


def _percent(value: float | None) -> str:
    return "--" if value is None else f"{100 * value:.1f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run",
        action="append",
        choices=sorted(RUN_MODELS),
        help="validate one run (repeatable); defaults to both full runs",
    )
    parser.add_argument(
        "--system",
        action="append",
        choices=SYSTEMS,
        help="validate one system (repeatable); defaults to all seven systems",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="permit missing/error records while checking all available records",
    )
    args = parser.parse_args()

    _conversations, expected_qas, dataset_hash = _load_benchmark()
    runs = args.run or list(RUN_MODELS)
    systems = args.system or list(SYSTEMS)
    rows = []
    failures = []
    for run_name in runs:
        expected_model = RUN_MODELS[run_name]
        run_root = RESULTS_ROOT / run_name
        for system in systems:
            path = run_root / f"{system}.json"
            if not path.exists():
                failures.append(f"{path}: missing artifact")
                continue
            metrics, errors = validate_artifact(
                path,
                run_name=run_name,
                expected_model=expected_model,
                expected_qas=expected_qas,
                dataset_hash=dataset_hash,
                allow_partial=args.allow_partial,
            )
            failures.extend(errors)
            rows.append((expected_model, system, metrics))

    if args.allow_partial:
        print("PARTIAL MONITORING OUTPUT -- DO NOT REPORT AS FINAL\n")
    print("| Model | System | n | Token F1 | Judge accuracy | Adv. refusal |")
    print("|---|---|---:|---:|---:|---:|")
    for model, system, metrics in rows:
        answer = metrics["answer_bearing"]
        adversarial = metrics["adversarial"]
        print(
            f"| {model} | {system} | {metrics['n_completed']} | "
            f"{_percent(answer['official_token_f1'])} | "
            f"{_percent(answer['judge_accuracy'])} | "
            f"{_percent(adversarial['refusal_accuracy'])} |"
        )

    if failures:
        print(f"\nVALIDATION FAILED ({len(failures)} issues)", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    if args.allow_partial:
        print("\nPARTIAL VALIDATION PASSED (coverage incomplete; metrics are non-final)")
    else:
        print("\nFINAL VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
