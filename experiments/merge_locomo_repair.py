#!/usr/bin/env python3
"""Atomically merge a verified LOCOMO repair into a completed main artifact.

Stochastic memory systems must replace an entire conversation.  MemMachine's
index is deterministic, so it may also accept explicitly selected QA records.
The command refuses to modify an artifact while its main evaluation writer is
still active.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import pathlib
import shlex
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone

from run_locomo_full import (
    DATA_PATH,
    KRILL_BASE_URL,
    RESULTS_ROOT,
    _aggregate,
    _atomic_write,
    gemini_cli_user_agent,
    official_locomo_score,
)


FULL_RUNS = {
    "full_locomo_gpt56_luna": "gpt-5.6-luna",
    "full_locomo_gemini3_flash_preview": "gemini-3-flash-preview",
}
STOCHASTIC_SYSTEMS = {"uac_v5", "hindsight", "evermemos", "a_mem", "mem0"}
SYSTEMS = STOCHASTIC_SYSTEMS | {"full_context", "memmachine"}
EXPECTED_TOTAL = 1_986


def _load(path: pathlib.Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ValueError(f"missing artifact: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON artifact {path}: {exc}") from exc


def _effective_run_name(tokens: list[str]) -> str:
    for index, token in enumerate(tokens):
        if token == "--run-name" and index + 1 < len(tokens):
            return tokens[index + 1]
        if token.startswith("--run-name="):
            return token.split("=", 1)[1]
    return "full_locomo_gpt56_luna"


def _active_writer_pids(run_name: str, system: str) -> list[int]:
    """Find run_locomo_full writers for the exact target run and system."""
    output = subprocess.check_output(
        ["ps", "-axo", "pid=,command="], text=True
    )
    matches: list[int] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid_text, _, command = stripped.partition(" ")
        try:
            tokens = shlex.split(command)
        except ValueError:
            continue
        script_positions = [
            i for i, token in enumerate(tokens) if token.endswith("run_locomo_full.py")
        ]
        if not script_positions:
            continue
        script_index = script_positions[0]
        if script_index + 1 >= len(tokens) or tokens[script_index + 1] != system:
            continue
        if _effective_run_name(tokens) == run_name:
            matches.append(int(pid_text))
    return matches


def _validate_metadata(
    artifact: dict,
    path: pathlib.Path,
    *,
    system: str,
    model: str,
    dataset_hash: str,
) -> None:
    expected = {
        "benchmark": "LOCOMO",
        "provider": "krill",
        "base_url": KRILL_BASE_URL,
        "model": model,
        "system": system,
        "dataset_sha256": dataset_hash,
        "user_agent": gemini_cli_user_agent(model),
    }
    problems = [
        f"{key}={artifact.get(key)!r}, expected {value!r}"
        for key, value in expected.items()
        if artifact.get(key) != value
    ]
    if problems:
        raise ValueError(f"metadata mismatch in {path}: " + "; ".join(problems))


def _records_by_index(records: list[dict], label: str) -> dict[int, dict]:
    indexed: dict[int, dict] = {}
    for record in records:
        try:
            qa_idx = int(record["qa_idx"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{label} has a record without an integer qa_idx") from exc
        if qa_idx in indexed:
            raise ValueError(f"{label} has duplicate qa_idx={qa_idx}")
        indexed[qa_idx] = record
    return indexed


def _validate_repair_records(
    records: dict[int, dict],
    expected_qas: dict[int, dict],
    *,
    conv_id: str,
    selected_indices: set[int],
) -> None:
    if set(records) != selected_indices:
        missing = sorted(selected_indices - set(records))
        extra = sorted(set(records) - selected_indices)
        raise ValueError(
            f"repair coverage mismatch for {conv_id}: missing={missing[:10]}, "
            f"extra={extra[:10]}"
        )
    for qa_idx, record in records.items():
        qa = expected_qas[qa_idx]
        label = f"{conv_id}:{qa_idx}"
        if record.get("status") != "ok":
            raise ValueError(f"repair record {label} has status={record.get('status')!r}")
        if record.get("qa_id") != label:
            raise ValueError(f"repair record {label} has qa_id={record.get('qa_id')!r}")
        if int(record.get("category", -1)) != int(qa["category"]):
            raise ValueError(f"repair record {label} has the wrong category")
        expected_score = official_locomo_score(
            str(record.get("scored_prediction", "")), qa
        )
        if not math.isclose(
            float(record.get("official_score", -1)),
            expected_score,
            abs_tol=1e-12,
        ):
            raise ValueError(f"repair record {label} has an invalid official score")
        judge = record.get("judge_correct")
        if int(qa["category"]) in {1, 2, 3, 4} and not isinstance(judge, bool):
            raise ValueError(f"repair record {label} lacks a boolean judge result")
        if int(qa["category"]) == 5 and judge is not None:
            raise ValueError(f"adversarial repair record {label} has an LLM judge result")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-run", required=True, choices=sorted(FULL_RUNS))
    parser.add_argument("--repair-run", required=True)
    parser.add_argument("--system", required=True, choices=sorted(SYSTEMS))
    parser.add_argument("--conversation", required=True)
    parser.add_argument(
        "--qa-index",
        type=int,
        action="append",
        help="replace selected QA only; permitted only for deterministic MemMachine",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    active_pids = _active_writer_pids(args.target_run, args.system)
    if active_pids:
        raise SystemExit(
            "refusing to merge while the target writer is active: "
            + ", ".join(str(pid) for pid in active_pids)
        )
    if args.qa_index and args.system != "memmachine":
        parser.error(
            "targeted QA replacement is permitted only for deterministic MemMachine; "
            "replace the entire conversation for this system"
        )

    conversations = json.loads(DATA_PATH.read_text())
    benchmark = {
        str(conv["sample_id"]): {idx: qa for idx, qa in enumerate(conv["qa"])}
        for conv in conversations
    }
    if args.conversation not in benchmark:
        parser.error(f"unknown conversation: {args.conversation}")
    expected_qas = benchmark[args.conversation]
    selected_indices = (
        set(args.qa_index) if args.qa_index else set(expected_qas)
    )
    unknown = selected_indices - set(expected_qas)
    if unknown:
        parser.error(f"unknown QA indices for {args.conversation}: {sorted(unknown)}")

    target_path = RESULTS_ROOT / args.target_run / f"{args.system}.json"
    repair_path = RESULTS_ROOT / args.repair_run / f"{args.system}.json"
    target = _load(target_path)
    repair = _load(repair_path)
    dataset_hash = hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()
    model = FULL_RUNS[args.target_run]
    _validate_metadata(
        target, target_path, system=args.system, model=model, dataset_hash=dataset_hash
    )
    _validate_metadata(
        repair, repair_path, system=args.system, model=model, dataset_hash=dataset_hash
    )

    selection = target.get("selection", {})
    full_selection = {
        "conv_start": 0,
        "conv_end": 10,
        "max_questions_per_conv": None,
        "max_sessions_per_conv": None,
        "qa_index": None,
    }
    if any(selection.get(key) != value for key, value in full_selection.items()):
        raise ValueError(f"target is not a full ten-conversation artifact: {target_path}")

    repair_records = _records_by_index(
        repair.get("details", {}).get(args.conversation, []),
        f"{repair_path}:{args.conversation}",
    )
    _validate_repair_records(
        repair_records,
        expected_qas,
        conv_id=args.conversation,
        selected_indices=selected_indices,
    )

    target_records = _records_by_index(
        target.get("details", {}).get(args.conversation, []),
        f"{target_path}:{args.conversation}",
    )
    if args.qa_index:
        target_records.update(copy.deepcopy(repair_records))
        merged_records = [target_records[idx] for idx in sorted(target_records)]
        mode = "targeted"
    else:
        merged_records = [copy.deepcopy(repair_records[idx]) for idx in sorted(repair_records)]
        mode = "whole-conversation"

    if args.dry_run:
        print(
            f"DRY RUN PASSED: {mode} merge of {len(repair_records)} records from "
            f"{repair_path} into {target_path}"
        )
        return 0

    timestamp = datetime.now(timezone.utc)
    backup = target_path.with_name(
        f"{target_path.name}.premerge-"
        f"{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}.bak"
    )
    shutil.copy2(target_path, backup)
    target.setdefault("details", {})[args.conversation] = merged_records
    target.setdefault("merge_history", []).append(
        {
            "merged_at": timestamp.isoformat(),
            "repair_run": args.repair_run,
            "conversation": args.conversation,
            "mode": mode,
            "qa_indices": sorted(selected_indices) if args.qa_index else None,
            "backup": backup.name,
        }
    )

    usage = Counter(target.get("shared_krill_usage", {}))
    prior_repair_runs = {
        str(entry.get("repair_run"))
        for entry in target.get("merge_history", [])[:-1]
        if isinstance(entry, dict)
    }
    if args.repair_run not in prior_repair_runs:
        usage.update(repair.get("shared_krill_usage", {}))
    _aggregate(target, EXPECTED_TOTAL, dict(usage))
    _atomic_write(target_path, target)
    print(
        f"MERGED: {mode} replacement of {len(repair_records)} records; "
        f"backup={backup}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
