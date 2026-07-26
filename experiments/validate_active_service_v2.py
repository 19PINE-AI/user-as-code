#!/usr/bin/env python3
"""Strictly validate a complete Active Service v2 result directory.

The validator performs no model calls. It reconstructs prompts, retrieval,
program validation and execution, rubric scores, aggregate statistics, usage,
and provenance from the persisted traces and frozen protocol.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn


EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

import run_active_service_v2 as v2


class ArtifactValidationError(RuntimeError):
    """Raised when a result artifact violates a frozen invariant."""


def fail(message: str) -> NoReturn:
    raise ArtifactValidationError(message)


def require(condition: Any, message: str) -> None:
    if not condition:
        fail(message)


def load_json(path: Path) -> dict:
    require(path.is_file(), f"missing file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read JSON {path}: {exc}")
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def committed_file(commit: str, relative_path: str) -> bytes:
    require(
        bool(re.fullmatch(r"[0-9a-f]{40}", commit)),
        f"manifest has invalid git_commit: {commit!r}",
    )
    completed = subprocess.run(
        ["git", "show", f"{commit}:{relative_path}"],
        cwd=v2.ROOT,
        check=False,
        capture_output=True,
        timeout=30,
    )
    require(
        completed.returncode == 0,
        f"cannot load {relative_path} from recorded commit {commit}",
    )
    return completed.stdout


def validate_generation(generation: dict, label: str) -> None:
    require(isinstance(generation, dict), f"{label}: generation is not an object")
    require(
        isinstance(generation.get("text"), str) and bool(generation["text"].strip()),
        f"{label}: missing model response text (transport failure)",
    )
    require(
        isinstance(generation.get("latency_seconds"), (int, float))
        and generation["latency_seconds"] >= 0,
        f"{label}: invalid latency",
    )
    usage = generation.get("usage")
    require(isinstance(usage, dict), f"{label}: missing usage object")
    require(usage.get("requests") == 1, f"{label}: expected exactly one API request")
    for key, value in usage.items():
        require(
            isinstance(key, str)
            and isinstance(value, int)
            and not isinstance(value, bool)
            and value >= 0,
            f"{label}: invalid usage field {key!r}",
        )


def resolve_program_path(raw_path: str, output_dir: Path, expected: Path) -> Path:
    require(raw_path == v2.trace_path(expected), f"unexpected program path: {raw_path}")
    path = Path(raw_path)
    resolved = (v2.ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    programs_root = (output_dir / "programs").resolve()
    require(
        resolved.is_relative_to(programs_root),
        f"program escapes result directory: {raw_path}",
    )
    require(resolved == expected.resolve(), f"program path mismatch: {raw_path}")
    return resolved


def validate_uac(
    trace: dict,
    sessions: list[dict],
    rubric: dict,
    output_dir: Path,
    expected_programs: set[Path],
) -> None:
    scenario_id = trace["scenario_id"]
    result = trace["systems"]["uac"]
    require(isinstance(result, dict), f"{scenario_id}/uac: invalid result")
    updates = result.get("updates")
    require(
        isinstance(updates, list) and len(updates) == len(sessions),
        f"{scenario_id}/uac: one update is required per session",
    )

    cumulative: list[dict] = []
    valid_flags: list[bool] = []
    executable_flags: list[bool] = []
    pretrigger_alert_count = 0
    trigger_candidates: list[str] = []

    for index, (update, session) in enumerate(zip(updates, sessions)):
        label = f"{scenario_id}/uac/update-{index + 1}"
        require(isinstance(update, dict), f"{label}: invalid update")
        cumulative.append(session)
        stage = "trigger" if index == len(sessions) - 1 else "pretrigger"
        require(update.get("stage") == stage, f"{label}: stage mismatch")
        require(update.get("session") == session, f"{label}: session mismatch")
        expected_prompt = v2.UAC_UPDATE_TEMPLATE.format(
            timestamp=session["timestamp"],
            history=v2.render_history(cumulative),
        )
        require(
            update.get("system_prompt") == v2.UAC_SYSTEM_PROMPT,
            f"{label}: system prompt mismatch",
        )
        require(update.get("user_prompt") == expected_prompt, f"{label}: prompt mismatch")
        require("generation" in update, f"{label}: API transport failure")
        validate_generation(update["generation"], label)

        try:
            extracted_source = v2.extract_python_source(update["generation"]["text"])
        except v2.GeneratedCodeError:
            require("source" not in update, f"{label}: source should not exist")
            require(
                update.get("error_stage") == "generation_or_validation",
                f"{label}: unrecorded extraction failure",
            )
            valid_flags.append(False)
            executable_flags.append(False)
            continue

        require(update.get("source") == extracted_source, f"{label}: source mismatch")
        expected_path = (
            output_dir / "programs" / scenario_id / f"{index + 1:02d}_{stage}.py"
        )
        raw_path = update.get("source_path")
        require(isinstance(raw_path, str), f"{label}: missing source path")
        source_path = resolve_program_path(raw_path, output_dir, expected_path)
        require(source_path.is_file(), f"{label}: source file is missing")
        require(
            source_path.read_text(encoding="utf-8") == extracted_source,
            f"{label}: persisted source differs from trace",
        )
        expected_programs.add(source_path)

        try:
            validation = v2.validate_generated_source(extracted_source)
        except v2.GeneratedCodeError as exc:
            require("validation" not in update, f"{label}: invalid source marked valid")
            require(
                update.get("error_stage") == "generation_or_validation",
                f"{label}: validation failure stage is missing",
            )
            require(update.get("error") == str(exc), f"{label}: validation error mismatch")
            valid_flags.append(False)
            executable_flags.append(False)
            continue

        require(update.get("validation") == validation, f"{label}: validation mismatch")
        require(
            validation["source_sha256"]
            == hashlib.sha256(extracted_source.encode("utf-8")).hexdigest(),
            f"{label}: source digest mismatch",
        )
        valid_flags.append(True)

        try:
            execution = v2.execute_generated_source(source_path, session["timestamp"])
        except v2.GeneratedCodeError as exc:
            require("execution" not in update, f"{label}: failed execution was persisted")
            require(update.get("error_stage") == "execution", f"{label}: wrong error stage")
            require(update.get("error") == str(exc), f"{label}: execution error mismatch")
            executable_flags.append(False)
            continue

        require(update.get("execution") == execution, f"{label}: execution mismatch")
        require("error" not in update, f"{label}: successful update contains an error")
        executable_flags.append(True)
        alerts = execution["alerts"]
        if stage == "pretrigger":
            pretrigger_alert_count += len(alerts)
        else:
            trigger_candidates = [str(alert["message"]) for alert in alerts]

    all_valid = all(valid_flags)
    all_executable = all(executable_flags)
    posttrigger_score = v2.score_candidates(trigger_candidates, rubric)
    passed = (
        all_valid
        and all_executable
        and pretrigger_alert_count == 0
        and posttrigger_score["passed"]
    )
    expected_fields = {
        "all_updates_valid": all_valid,
        "all_updates_executable": all_executable,
        "pretrigger_alert_count": pretrigger_alert_count,
        "trigger_alert_count": len(trigger_candidates),
        "trigger_candidates": trigger_candidates,
        "posttrigger_score": posttrigger_score,
        "passed": passed,
    }
    for key, expected_value in expected_fields.items():
        require(result.get(key) == expected_value, f"{scenario_id}/uac: {key} mismatch")


def validate_baseline(
    trace: dict,
    sessions: list[dict],
    rubric: dict,
    system: str,
) -> None:
    scenario_id = trace["scenario_id"]
    label = f"{scenario_id}/{system}"
    result = trace["systems"][system]
    history = sessions[:-1]
    trigger = sessions[-1]
    if system == "full_context":
        selected = history
        retrieval_scores = None
    else:
        top_session, retrieval_scores = v2.lexical_top_one(history, trigger["user_text"])
        selected = [top_session]
    selected_ids = [session["session_id"] for session in selected]
    require(
        result.get("selected_history_session_ids") == selected_ids,
        f"{label}: selected history mismatch",
    )
    require(
        result.get("retrieval_scores") == retrieval_scores,
        f"{label}: retrieval scores mismatch",
    )
    expected_prompt = v2.BASELINE_USER_TEMPLATE.format(
        history=v2.render_history(selected),
        timestamp=trigger["timestamp"],
        trigger=trigger["user_text"],
    )
    require(
        result.get("system_prompt") == v2.BASELINE_SYSTEM_PROMPT,
        f"{label}: system prompt mismatch",
    )
    require(result.get("user_prompt") == expected_prompt, f"{label}: prompt mismatch")
    require("generation" in result, f"{label}: API transport failure")
    validate_generation(result["generation"], label)
    response = result["generation"]["text"]
    require(result.get("response") == response, f"{label}: response mismatch")
    score = v2.score_text(response, rubric)
    require(result.get("score") == score, f"{label}: score mismatch")
    require(result.get("passed") == score["passed"], f"{label}: pass flag mismatch")
    require("error" not in result, f"{label}: successful API call contains an error")


def validate_trace(
    trace: dict,
    scenario: dict,
    rubric: dict,
    output_dir: Path,
    expected_programs: set[Path],
) -> None:
    scenario_id = scenario["id"]
    require(trace.get("protocol_id") == "active-service-v2.1", f"{scenario_id}: protocol mismatch")
    require(trace.get("scenario_id") == scenario_id, f"{scenario_id}: ID mismatch")
    require(trace.get("category") == scenario["category"], f"{scenario_id}: category mismatch")
    require(
        trace.get("description") == scenario["description"],
        f"{scenario_id}: description mismatch",
    )
    sessions = v2.scenario_sessions(scenario)
    require(trace.get("sessions") == sessions, f"{scenario_id}: session content mismatch")
    systems = trace.get("systems")
    require(
        isinstance(systems, dict) and list(systems) == list(v2.SYSTEMS),
        f"{scenario_id}: systems must be exactly {v2.SYSTEMS}",
    )
    validate_uac(trace, sessions, rubric, output_dir, expected_programs)
    validate_baseline(trace, sessions, rubric, "full_context")
    validate_baseline(trace, sessions, rubric, "retrieval")


def validate_result_dir(output_dir: Path) -> dict:
    output_dir = output_dir.resolve()
    manifest = load_json(output_dir / "manifest.json")
    protocol = v2.load_protocol()
    source_path = v2.ROOT / protocol["source_suite"]["path"]

    require(manifest.get("protocol_id") == protocol["protocol_id"], "manifest protocol mismatch")
    require(
        manifest.get("protocol_sha256") == v2.sha256_file(v2.DEFAULT_PROTOCOL_PATH),
        "manifest protocol digest mismatch",
    )
    require(
        manifest.get("source_suite_sha256") == v2.sha256_file(source_path),
        "manifest source-suite digest mismatch",
    )
    commit = str(manifest.get("git_commit", ""))
    require(
        manifest.get("runner_sha256")
        == sha256_bytes(committed_file(commit, "experiments/run_active_service_v2.py")),
        "runner digest does not match the recorded commit",
    )
    require(
        manifest.get("sandbox_sha256")
        == sha256_bytes(committed_file(commit, "experiments/active_service_sandbox.py")),
        "sandbox digest does not match the recorded commit",
    )
    model_map = {model["name"]: model for model in protocol["models"]}
    model = manifest.get("model")
    require(isinstance(model, dict) and model.get("name") in model_map, "unknown model panel")
    require(model == model_map[model["name"]], "model settings differ from protocol")
    require(manifest.get("systems") == list(v2.SYSTEMS), "manifest systems mismatch")
    eligible_ids = list(protocol["eligible_ids"])
    require(manifest.get("selected_ids") == eligible_ids, "manifest case order mismatch")
    require(manifest.get("complete_frozen_suite") is True, "manifest is not a complete suite")

    traces_dir = output_dir / "traces"
    actual_trace_files = sorted(traces_dir.glob("*.json"))
    expected_trace_files = [traces_dir / f"{scenario_id}.json" for scenario_id in eligible_ids]
    require(
        set(actual_trace_files) == set(expected_trace_files),
        "trace files do not exactly match the eligible case set",
    )
    scenario_map = v2.load_scenario_map(source_path)
    traces = []
    expected_programs: set[Path] = set()
    for scenario_id, path in zip(eligible_ids, expected_trace_files):
        trace = load_json(path)
        validate_trace(
            trace,
            scenario_map[scenario_id],
            protocol["rubrics"][scenario_id],
            output_dir,
            expected_programs,
        )
        traces.append(trace)

    actual_programs = {
        path.resolve() for path in (output_dir / "programs").rglob("*.py") if path.is_file()
    }
    require(actual_programs == expected_programs, "program files do not exactly match traces")
    summary = v2.aggregate_traces(traces, list(v2.SYSTEMS))
    require(manifest.get("summary") == summary, "manifest summary mismatch")
    usage = v2.usage_totals(traces)
    require(manifest.get("usage") == usage, "manifest usage mismatch")
    return {
        "valid": True,
        "protocol_id": protocol["protocol_id"],
        "model": model["name"],
        "case_count": len(traces),
        "generation_count": usage["requests"],
        "summary": summary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_dir", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        report = validate_result_dir(args.result_dir)
    except ArtifactValidationError as exc:
        raise SystemExit(f"INVALID: {exc}") from exc
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
