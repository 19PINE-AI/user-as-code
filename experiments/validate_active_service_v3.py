#!/usr/bin/env python3
"""Replay and validate a complete Active Service v3 regression artifact."""
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

import active_service_engine as engine
import run_active_service_v2 as v2
import run_active_service_v3 as v3


class ValidationError(RuntimeError):
    """Raised when a v3 trace cannot be reproduced exactly."""


def fail(message: str) -> NoReturn:
    raise ValidationError(message)


def require(condition: Any, message: str) -> None:
    if not condition:
        fail(message)


def load_json(path: Path) -> dict:
    require(path.is_file(), f"missing file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read {path}: {exc}")
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


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


def validate_generation(value: object, label: str) -> None:
    require(isinstance(value, dict), f"{label}: generation is not an object")
    require(
        isinstance(value.get("text"), str) and bool(value["text"].strip()),
        f"{label}: missing response text",
    )
    require(
        isinstance(value.get("latency_seconds"), (int, float))
        and value["latency_seconds"] >= 0,
        f"{label}: invalid latency",
    )
    usage = value.get("usage")
    require(isinstance(usage, dict), f"{label}: missing usage")
    require(usage.get("requests") == 1, f"{label}: expected one request")
    for key, number in usage.items():
        require(
            isinstance(key, str)
            and isinstance(number, int)
            and not isinstance(number, bool)
            and number >= 0,
            f"{label}: invalid usage field {key!r}",
        )


def validate_attempts(
    attempts: object,
    timestamp: str,
    history: str,
    label: str,
) -> dict:
    require(isinstance(attempts, list) and attempts, f"{label}: no attempts")
    require(len(attempts) <= v3.MAX_IR_ATTEMPTS, f"{label}: too many attempts")
    original_prompt = v3.IR_UPDATE_TEMPLATE.format(
        timestamp=timestamp,
        history=history,
    )
    expected_prompt = original_prompt
    accepted: dict | None = None
    for index, attempt in enumerate(attempts):
        attempt_label = f"{label}/attempt-{index + 1}"
        require(isinstance(attempt, dict), f"{attempt_label}: invalid object")
        require(attempt.get("attempt") == index + 1, f"{attempt_label}: index mismatch")
        require(
            attempt.get("system_prompt") == v3.IR_SYSTEM_PROMPT,
            f"{attempt_label}: system prompt mismatch",
        )
        require(
            attempt.get("user_prompt") == expected_prompt,
            f"{attempt_label}: user prompt mismatch",
        )
        generation = attempt.get("generation")
        validate_generation(generation, attempt_label)
        try:
            parsed = engine.extract_json_object(generation["text"])
            canonical = engine.validate_constraint_ir(parsed)
        except engine.ConstraintIRError as exc:
            require(attempt.get("error") == str(exc), f"{attempt_label}: error mismatch")
            require("ir" not in attempt, f"{attempt_label}: invalid IR was accepted")
            require(index + 1 < len(attempts), f"{attempt_label}: terminal invalid attempt")
            expected_prompt = v3.IR_REPAIR_TEMPLATE.format(
                original_prompt=original_prompt,
                error=str(exc),
                previous_response=generation["text"],
            )
            continue
        require(attempt.get("ir") == canonical, f"{attempt_label}: IR mismatch")
        require("error" not in attempt, f"{attempt_label}: accepted attempt has error")
        require(index + 1 == len(attempts), f"{attempt_label}: calls after accepted IR")
        accepted = canonical
    require(accepted is not None, f"{label}: no accepted IR")
    return accepted


def validate_trace(
    trace: dict,
    scenario: dict,
    rubric: dict,
    output_dir: Path,
    expected_programs: set[Path],
) -> None:
    scenario_id = str(scenario["id"])
    require(trace.get("system_id") == v3.SYSTEM_ID, f"{scenario_id}: system mismatch")
    require(
        trace.get("benchmark_protocol_id") == "active-service-v2.1",
        f"{scenario_id}: benchmark mismatch",
    )
    require(trace.get("scenario_id") == scenario_id, f"{scenario_id}: ID mismatch")
    require(trace.get("category") == scenario["category"], f"{scenario_id}: category mismatch")
    require(
        trace.get("description") == scenario["description"],
        f"{scenario_id}: description mismatch",
    )
    sessions = v2.scenario_sessions(scenario)
    require(trace.get("sessions") == sessions, f"{scenario_id}: sessions mismatch")
    require(list(trace.get("systems", {})) == ["uac"], f"{scenario_id}: systems mismatch")
    result = trace["systems"]["uac"]
    updates = result.get("updates")
    require(
        isinstance(updates, list) and len(updates) == len(sessions),
        f"{scenario_id}: update count mismatch",
    )

    cumulative: list[dict] = []
    pretrigger_alert_count = 0
    trigger_candidates: list[str] = []
    for index, (session, update) in enumerate(zip(sessions, updates)):
        label = f"{scenario_id}/update-{index + 1}"
        require(isinstance(update, dict), f"{label}: invalid update")
        cumulative.append(session)
        stage = "trigger" if index == len(sessions) - 1 else "pretrigger"
        require(update.get("stage") == stage, f"{label}: stage mismatch")
        require(update.get("session") == session, f"{label}: session mismatch")
        ir = validate_attempts(
            update.get("attempts"),
            session["timestamp"],
            v2.render_history(cumulative),
            label,
        )
        require(update.get("ir") == ir, f"{label}: accepted IR mismatch")
        source = engine.compile_constraint_module(ir)
        require(update.get("source") == source, f"{label}: compiled source mismatch")
        expected_path = (
            output_dir / "programs" / scenario_id / f"{index + 1:02d}_{stage}.py"
        ).resolve()
        require(
            update.get("source_path") == v2.trace_path(expected_path),
            f"{label}: source path mismatch",
        )
        require(expected_path.is_file(), f"{label}: missing source file")
        require(
            expected_path.read_text(encoding="utf-8") == source,
            f"{label}: persisted source mismatch",
        )
        expected_programs.add(expected_path)
        validation = v2.validate_generated_source(source)
        require(update.get("validation") == validation, f"{label}: validation mismatch")
        execution = v2.execute_generated_source(expected_path, session["timestamp"])
        require(update.get("execution") == execution, f"{label}: execution mismatch")
        require("error" not in update, f"{label}: successful update contains error")
        if stage == "pretrigger":
            pretrigger_alert_count += len(execution["alerts"])
        else:
            trigger_candidates = [str(alert["message"]) for alert in execution["alerts"]]

    posttrigger_score = v2.score_candidates(trigger_candidates, rubric)
    expected_fields = {
        "all_updates_valid": True,
        "all_updates_executable": True,
        "pretrigger_alert_count": pretrigger_alert_count,
        "trigger_alert_count": len(trigger_candidates),
        "trigger_candidates": trigger_candidates,
        "posttrigger_score": posttrigger_score,
        "passed": pretrigger_alert_count == 0 and posttrigger_score["passed"],
    }
    for key, expected in expected_fields.items():
        require(result.get(key) == expected, f"{scenario_id}: {key} mismatch")


def validate_result_dir(output_dir: Path) -> dict:
    output_dir = output_dir.resolve()
    manifest = load_json(output_dir / "manifest.json")
    protocol = v2.load_protocol()
    source_path = v2.ROOT / protocol["source_suite"]["path"]
    require(manifest.get("system_id") == v3.SYSTEM_ID, "manifest system mismatch")
    require(
        manifest.get("benchmark_protocol_id") == protocol["protocol_id"],
        "manifest benchmark mismatch",
    )
    require(
        manifest.get("benchmark_protocol_sha256") == v2.sha256_file(v2.DEFAULT_PROTOCOL_PATH),
        "benchmark protocol digest mismatch",
    )
    require(
        manifest.get("source_suite_sha256") == v2.sha256_file(source_path),
        "source suite digest mismatch",
    )
    require(manifest.get("engine_id") == engine.ENGINE_ID, "engine ID mismatch")
    commit = str(manifest.get("git_commit", ""))
    committed_engine = committed_file(commit, "experiments/active_service_engine.py")
    committed_runner = committed_file(commit, "experiments/run_active_service_v3.py")
    committed_sandbox = committed_file(commit, "experiments/active_service_sandbox.py")
    require(
        manifest.get("engine_sha256") == v2.sha256_file(Path(engine.__file__).resolve()),
        "engine digest mismatch",
    )
    require(
        manifest.get("engine_sha256") == hashlib.sha256(committed_engine).hexdigest(),
        "engine digest does not match recorded commit",
    )
    require(
        manifest.get("runner_sha256") == v2.sha256_file(Path(v3.__file__).resolve()),
        "runner digest mismatch",
    )
    require(
        manifest.get("runner_sha256") == hashlib.sha256(committed_runner).hexdigest(),
        "runner digest does not match recorded commit",
    )
    require(
        manifest.get("sandbox_sha256") == v2.sha256_file(v2.SANDBOX_PATH),
        "sandbox digest mismatch",
    )
    require(
        manifest.get("sandbox_sha256") == hashlib.sha256(committed_sandbox).hexdigest(),
        "sandbox digest does not match recorded commit",
    )
    model_map = {model["name"]: model for model in protocol["models"]}
    model = manifest.get("model")
    require(isinstance(model, dict) and model in model_map.values(), "unknown model")
    eligible_ids = list(protocol["eligible_ids"])
    require(manifest.get("selected_ids") == eligible_ids, "case order mismatch")
    require(manifest.get("complete_regression_suite") is True, "suite is incomplete")

    traces_dir = output_dir / "traces"
    expected_paths = [traces_dir / f"{case_id}.json" for case_id in eligible_ids]
    require(
        set(traces_dir.glob("*.json")) == set(expected_paths),
        "trace files do not exactly match the eligible cases",
    )
    scenario_map = v2.load_scenario_map(source_path)
    traces: list[dict] = []
    expected_programs: set[Path] = set()
    for scenario_id, path in zip(eligible_ids, expected_paths):
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
    require(actual_programs == expected_programs, "program files do not match traces")
    summary = v2.aggregate_traces(traces, ["uac"])
    require(manifest.get("summary") == summary, "summary mismatch")
    usage = v3.usage_totals(traces)
    require(manifest.get("usage") == usage, "usage mismatch")
    require(
        summary["by_system"]["uac"]["passed"] == len(eligible_ids),
        "regression acceptance requires every eligible case to pass",
    )
    return {
        "valid": True,
        "system_id": v3.SYSTEM_ID,
        "benchmark_protocol_id": protocol["protocol_id"],
        "model": model["name"],
        "case_count": len(traces),
        "generation_count": usage.get("requests", 0),
        "passed": summary["by_system"]["uac"]["passed"],
        "summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_dir", type=Path)
    args = parser.parse_args()
    try:
        report = validate_result_dir(args.result_dir)
    except ValidationError as exc:
        raise SystemExit(f"INVALID: {exc}") from exc
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
