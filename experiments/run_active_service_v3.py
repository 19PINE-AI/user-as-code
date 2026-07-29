#!/usr/bin/env python3
"""Run the regression-tuned Active Service constraint-IR system.

Paper map: "Cue-Free Constraint Detection" (sec:active-service), including the
explicit
qualification that the v3 result is post-evaluation regression coverage rather
than an unbiased held-out estimate.

This runner deliberately leaves the frozen v2.1 publication runner and its
4/17 artifact untouched.  It reuses the unchanged eligible cases and scoring
rubrics as a regression suite while replacing free-form model-authored Python
with a validated declarative IR and deterministic compiler.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

import active_service_engine as engine
import run_active_service_v2 as v2


SYSTEM_ID = "active-service-v3.0-regression"
DEFAULT_OUTPUT_ROOT = v2.ROOT / "experiments" / "results"
MAX_IR_ATTEMPTS = 3


class IRGenerationError(engine.ConstraintIRError):
    """Structural generation failure with every attempted response retained."""

    def __init__(self, message: str, attempts: list[dict[str, Any]]):
        super().__init__(message)
        self.attempts = attempts

IR_SYSTEM_PROMPT = r"""You maintain persistent memory and explicit constraints for a personal assistant.

Return ONLY one JSON object with exactly two top-level keys: state and constraints.

STATE
- state is a JSON object containing every durable fact in the complete user-authored history.
- Preserve exact names, people, organizations, accounts, amounts, dates, times, commitments, limits, cancellations, preferences, resource availability, credential properties, and unresolved deadlines.
- Treat the user's stated calendar date and weekday as one authored fact; do not create an alert merely because an external calendar could disagree.

CONSTRAINTS
- constraints is a JSON list. Each item must have exactly these keys:
  id, severity, type, message_template, active_from, active_until, deadline,
  deadline_anchor, deadline_offset_days.
- id and type are short snake_case strings. severity is info, warning, high, or critical.
- All date fields are ISO YYYY-MM-DD strings or null. deadline_offset_days is an integer or null.
- For a direct conflict, active_from is the session date when both sides are first known; active_until is normally null; deadline, deadline_anchor, and deadline_offset_days are null. Exhausted capacity or a completed use is state, not an alert by itself; create a constraint only after a new proposed action attempts to use that exhausted capacity.
- For an unresolved deadline whose exact date the user states, set deadline to that date. Set active_from, active_until, deadline_anchor, and deadline_offset_days to null.
- For a deadline derived from a user-stated date and duration, do not calculate the result yourself. Set deadline to null, put the source date in deadline_anchor, and put the signed calendar-day offset in deadline_offset_days (for example, a 30-day window from a purchase uses 30; notice required 60 days before an expiry uses -60). Set active_from and active_until to null.
- Trusted code derives deadline activation seven calendar days before every deadline and suppresses it after the deadline.
- It is valid and useful to store a future deadline constraint before it becomes active; trusted code suppresses it until active_from.

WHEN TO CREATE A CONSTRAINT
- Create one for a concrete conflict between user-stated facts: incompatible events or resources, a proposal over an explicit limit, an action after cancellation/closure, a proposal contrary to an explicit preference, exhausted stated usage, a plan outside a stated validity window, or an unresolved user-stated deadline.
- Semantic relationships stated by the user count. For example, a completed use consumes a stated single-use credential; an event scheduled during a trip conflicts with the user's availability.
- Never invent external medical, legal, tax, immigration, financial, travel, or policy rules.
- Do not create an alert from a lone fact, a future plan that conflicts with nothing, a generic request, or a deadline more than seven days away. Store such facts in state instead. A constraint with a future active_from is dormant, not an alert.
- Do not treat the current session itself as a violation. It must conflict with or make urgent something else in the accumulated history.
- Re-evaluate unresolved deadlines after every session even when the newest user message is unrelated to the deadline.

MESSAGE QUALITY
- Each message must stand alone without access to state.
- Name both sides of a conflict and the nature of the conflict. Every direct incompatibility message must explicitly use the word "conflict"; do not rely only on vague phrases such as "needs a resolution."
- Include all identifying evidence needed to act: relevant people, event or service names, account or credential, exact dates/times, amounts/limits, prior action or preference, and the grounded consequence or resolution.
- Repeat the user's concrete nouns and ordinary action verbs instead of replacing them with abstract synonyms. For example, if the credential is a visa, say that the user cannot enter or needs a new visa, not merely that separate authorization is required.
- State comparisons explicitly: say exceeds, is above, overlaps, occurs after cancellation, or lies outside the stated window rather than merely placing two values or facts next to each other.
- For every deadline message, name the subject and user-stated action, and use the literal placeholders {deadline} and {days_remaining}. The countdown placeholder must be followed immediately by its unit, as in "{days_remaining} days remaining." Trusted code replaces the placeholders with the exact derived deadline and live count; never hard-code a calculated deadline in the message.
- Prefer a complete two- or three-sentence alert over a vague or compressed warning.

Before returning JSON, silently audit that (1) all history facts are represented, (2) every direct actionable relationship is encoded, (3) no alert can fire before its evidence exists, and (4) every message includes both evidence and consequence. Do not return Markdown or commentary."""

IR_UPDATE_TEMPLATE = """Current session timestamp: {timestamp}

Complete user-authored history through this session:
{history}

Produce the replacement memory-and-constraint JSON now."""

IR_REPAIR_TEMPLATE = """{original_prompt}

Your previous JSON could not be accepted by the deterministic compiler.
Machine validation error: {error}

Previous response:
{previous_response}

Return a corrected complete JSON object only. Preserve all facts and constraints from the history."""


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_valid_ir(
    generator: v2.KrillModelGenerator,
    timestamp: str,
    history: str,
    max_attempts: int = MAX_IR_ATTEMPTS,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Generate and structurally validate the constraint IR used in
    "Cue-Free Constraint Detection" (sec:active-service), retrying only
    machine failures.
    """
    original_prompt = IR_UPDATE_TEMPLATE.format(timestamp=timestamp, history=history)
    prompt = original_prompt
    attempts: list[dict[str, Any]] = []
    for attempt_index in range(max_attempts):
        attempt: dict[str, Any] = {
            "attempt": attempt_index + 1,
            "system_prompt": IR_SYSTEM_PROMPT,
            "user_prompt": prompt,
        }
        generation = generator.generate(IR_SYSTEM_PROMPT, prompt)
        attempt["generation"] = generation
        try:
            parsed = engine.extract_json_object(generation["text"])
            canonical = engine.validate_constraint_ir(parsed)
        except engine.ConstraintIRError as exc:
            attempt["error"] = str(exc)
            attempts.append(attempt)
            if attempt_index + 1 == max_attempts:
                raise IRGenerationError(
                    f"IR failed after {max_attempts} attempts: {exc}", attempts
                ) from exc
            prompt = IR_REPAIR_TEMPLATE.format(
                original_prompt=original_prompt,
                error=str(exc),
                previous_response=generation["text"],
            )
            continue
        attempt["ir"] = canonical
        attempts.append(attempt)
        return canonical, attempts
    raise AssertionError("unreachable IR generation loop")


def run_uac_case(
    scenario_id: str,
    sessions: list[dict],
    rubric: dict,
    generator: v2.KrillModelGenerator,
    programs_dir: Path,
) -> dict[str, Any]:
    """Execute the update/compile/check loop illustrated in Paper Figure 5."""
    updates: list[dict[str, Any]] = []
    cumulative: list[dict] = []
    pretrigger_alert_count = 0
    all_updates_valid = True
    all_updates_executable = True
    trigger_candidates: list[str] = []

    for index, session in enumerate(sessions):
        cumulative.append(session)
        stage = "trigger" if index == len(sessions) - 1 else "pretrigger"
        update: dict[str, Any] = {"stage": stage, "session": session}
        history = v2.render_history(cumulative)
        try:
            ir, attempts = generate_valid_ir(
                generator,
                session["timestamp"],
                history,
            )
            update["attempts"] = attempts
            update["ir"] = ir
            source = engine.compile_constraint_module(ir)
            update["source"] = source
            source_path = programs_dir / scenario_id / f"{index + 1:02d}_{stage}.py"
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_text(source, encoding="utf-8")
            update["source_path"] = v2.trace_path(source_path)
            update["validation"] = v2.validate_generated_source(source)
        except Exception as exc:
            all_updates_valid = False
            all_updates_executable = False
            if isinstance(exc, IRGenerationError):
                update["attempts"] = exc.attempts
            update["error_stage"] = "generation_ir_or_compilation"
            update["error"] = str(exc)
            updates.append(update)
            continue

        try:
            execution = v2.execute_generated_source(source_path, session["timestamp"])
            update["execution"] = execution
            alerts = execution["alerts"]
            if stage == "pretrigger":
                pretrigger_alert_count += len(alerts)
            else:
                trigger_candidates = [str(alert["message"]) for alert in alerts]
        except Exception as exc:
            all_updates_executable = False
            update["error_stage"] = "execution"
            update["error"] = str(exc)
        updates.append(update)

    posttrigger_score = v2.score_candidates(trigger_candidates, rubric)
    passed = (
        all_updates_valid
        and all_updates_executable
        and pretrigger_alert_count == 0
        and posttrigger_score["passed"]
    )
    return {
        "passed": passed,
        "all_updates_valid": all_updates_valid,
        "all_updates_executable": all_updates_executable,
        "pretrigger_alert_count": pretrigger_alert_count,
        "trigger_alert_count": len(trigger_candidates),
        "trigger_candidates": trigger_candidates,
        "posttrigger_score": posttrigger_score,
        "updates": updates,
    }


def run_case(
    scenario: dict,
    rubric: dict,
    generator: v2.KrillModelGenerator,
    programs_dir: Path,
) -> dict[str, Any]:
    sessions = v2.scenario_sessions(scenario)
    started = v2.utc_now()
    result = run_uac_case(
        str(scenario["id"]), sessions, rubric, generator, programs_dir
    )
    return {
        "system_id": SYSTEM_ID,
        "benchmark_protocol_id": "active-service-v2.1",
        "scenario_id": scenario["id"],
        "category": scenario["category"],
        "description": scenario["description"],
        "started_at": started,
        "completed_at": v2.utc_now(),
        "sessions": sessions,
        "systems": {"uac": result},
    }


def usage_totals(traces: list[dict]) -> dict[str, int]:
    totals: Counter = Counter()
    for trace in traces:
        for update in trace["systems"]["uac"].get("updates", []):
            for attempt in update.get("attempts", []):
                usage = attempt.get("generation", {}).get("usage", {})
                for key, value in usage.items():
                    totals[key] += int(value)
                if "requests" not in usage:
                    totals["requests"] += 1
    return dict(totals)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--case", action="append", dest="case_ids", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    protocol = v2.load_protocol()
    source_path = v2.ROOT / protocol["source_suite"]["path"]
    scenario_map = v2.load_scenario_map(source_path)
    selected_ids = list(protocol["eligible_ids"])
    if args.case_ids:
        unknown = set(args.case_ids) - set(selected_ids)
        if unknown:
            raise v2.ProtocolError(f"requested non-eligible cases: {sorted(unknown)}")
        selected_ids = [case_id for case_id in selected_ids if case_id in args.case_ids]
    if args.limit is not None:
        if args.limit < 1:
            raise v2.ProtocolError("--limit must be positive")
        selected_ids = selected_ids[: args.limit]

    print(
        f"Validated {SYSTEM_ID} against {len(protocol['eligible_ids'])} unchanged "
        "Active Service v2.1 cases."
    )
    if args.validate_only:
        return

    model_map = {str(model["name"]): model for model in protocol["models"]}
    model_name = args.model or next(iter(model_map))
    if model_name not in model_map:
        raise v2.ProtocolError(f"unknown model {model_name!r}; choose {sorted(model_map)}")
    generator = v2.KrillModelGenerator(v2.ModelSettings(name=model_name))
    slug = re.sub(r"[^a-z0-9]+", "_", model_name.lower()).strip("_")
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir
        else DEFAULT_OUTPUT_ROOT / f"active_service_v3_{slug}"
    )
    traces_dir = output_dir / "traces"
    programs_dir = output_dir / "programs"
    traces_dir.mkdir(parents=True, exist_ok=True)
    programs_dir.mkdir(parents=True, exist_ok=True)

    started = v2.utc_now()
    traces: list[dict] = []
    for index, scenario_id in enumerate(selected_ids, start=1):
        path = traces_dir / f"{scenario_id}.json"
        if args.resume and path.is_file():
            trace = json.loads(path.read_text(encoding="utf-8"))
            if trace.get("system_id") == SYSTEM_ID:
                print(f"[{index}/{len(selected_ids)}] {scenario_id}: resume existing trace")
                traces.append(trace)
                continue
        print(f"[{index}/{len(selected_ids)}] {scenario_id}: running", flush=True)
        trace = run_case(
            scenario_map[scenario_id],
            protocol["rubrics"][scenario_id],
            generator,
            programs_dir,
        )
        v2.atomic_write_json(path, trace)
        traces.append(trace)
        result = trace["systems"]["uac"]
        print(
            f"    uac={'PASS' if result['passed'] else 'MISS'} "
            f"valid={result['all_updates_valid']} "
            f"exec={result['all_updates_executable']} "
            f"prealerts={result['pretrigger_alert_count']}",
            flush=True,
        )

    runner_path = Path(__file__).resolve()
    engine_path = Path(engine.__file__).resolve()
    summary = v2.aggregate_traces(traces, ["uac"])
    manifest = {
        "system_id": SYSTEM_ID,
        "benchmark_protocol_id": protocol["protocol_id"],
        "benchmark_protocol_sha256": v2.sha256_file(v2.DEFAULT_PROTOCOL_PATH),
        "source_suite_sha256": v2.sha256_file(source_path),
        "engine_id": engine.ENGINE_ID,
        "engine_sha256": v2.sha256_file(engine_path),
        "runner_sha256": v2.sha256_file(runner_path),
        "sandbox_sha256": v2.sha256_file(v2.SANDBOX_PATH),
        "git_commit": v2.git_commit(),
        "model": model_map[model_name],
        "selected_ids": selected_ids,
        "complete_regression_suite": selected_ids == protocol["eligible_ids"],
        "started_at": started,
        "completed_at": v2.utc_now(),
        "usage": usage_totals(traces),
        "summary": summary,
    }
    v2.atomic_write_json(output_dir / "manifest.json", manifest)
    print(json.dumps(summary["by_system"], indent=2))
    print(f"Results: {output_dir}")


if __name__ == "__main__":
    main()
