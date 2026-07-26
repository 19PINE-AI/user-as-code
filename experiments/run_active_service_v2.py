#!/usr/bin/env python3
"""Run the frozen, cue-free Active Service v2 evaluation.

The v2 protocol is intentionally separate from the deprecated pilot runners.
It consumes user-authored text only, persists and executes generated UaC
constraints after every session, records complete traces, and scores outputs
with frozen deterministic rubrics.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from active_service_sandbox import ALLOWED_IMPORTS
from krill_client import krill_call, usage_snapshot


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROTOCOL_PATH = ROOT / "evaluation" / "active_service_v2_protocol.json"
DEFAULT_OUTPUT_ROOT = ROOT / "experiments" / "results"
SANDBOX_PATH = Path(__file__).resolve().with_name("active_service_sandbox.py")

SYSTEMS = ("uac", "full_context", "retrieval")

UAC_SYSTEM_PROMPT = """You maintain an executable, persistent memory view for a personal assistant.

Return ONLY a self-contained Python module, without Markdown fences or prose. The module must:
1. define STATE as a JSON-serializable dictionary containing the durable facts established by the user-authored history;
2. define check_constraints(current_time), where current_time is an ISO YYYY-MM-DD string;
3. return a list of alert dictionaries with exactly the useful fields severity, type, and message;
4. use only facts, rules, limits, commitments, preferences, dates, and direct semantic relationships stated by the user; never invent an external medical, legal, tax, immigration, or policy rule;
5. emit an alert only when information available by current_time creates a concrete conflict, violated explicit limit or preference, unavailable resource, post-cancellation event, invalid explicit date window, or a user-stated deadline no more than seven days away;
6. return [] when there is no currently actionable violation. A stored fact alone is not an alert.

The program is regenerated after every session and executed immediately. Use the supplied current_time argument for all temporal comparisons; do not read the system clock. Permitted imports are datetime, math, calendar, decimal, statistics, and collections. Do not perform file, network, process, input, reflection, or dynamic-code operations."""

UAC_UPDATE_TEMPLATE = """Current session timestamp: {timestamp}

Complete user-authored history through this session:
{history}

Generate the replacement Python memory-and-constraint module now."""

BASELINE_SYSTEM_PROMPT = """You are a personal assistant. Respond directly and helpfully to the user's current message. Prior user-authored memory is provided when available; use it when naturally relevant. Do not invent missing facts or external rules. Do not discuss this evaluation or the memory format."""

BASELINE_USER_TEMPLATE = """Prior user-authored memory:
{history}

Current session ({timestamp}):
{trigger}"""


class ProtocolError(RuntimeError):
    """Raised when a frozen protocol invariant is violated."""


class GeneratedCodeError(RuntimeError):
    """Raised when generated source violates the execution contract."""


@dataclass(frozen=True)
class ModelSettings:
    name: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def trace_path(path: Path) -> str:
    """Store repository paths relatively and external smoke paths absolutely."""
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def load_protocol(path: Path = DEFAULT_PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("protocol_id") != "active-service-v2.1":
        raise ProtocolError("unsupported protocol_id")
    models = protocol.get("models")
    if not isinstance(models, list) or not models:
        raise ProtocolError("protocol must define at least one model")
    model_names = [str(model.get("name", "")) for model in models]
    if any(not name for name in model_names) or len(model_names) != len(set(model_names)):
        raise ProtocolError("protocol model names must be non-empty and unique")

    source = protocol.get("source_suite", {})
    source_path = ROOT / str(source.get("path", ""))
    if not source_path.is_file():
        raise ProtocolError(f"source suite not found: {source_path}")
    actual_digest = sha256_file(source_path)
    if actual_digest != source.get("sha256"):
        raise ProtocolError(
            f"source suite digest changed: expected {source.get('sha256')}, got {actual_digest}"
        )

    scenarios = load_scenario_map(source_path)
    if len(scenarios) != int(source.get("total_scenarios", -1)):
        raise ProtocolError("source scenario count does not match protocol")

    eligible = list(protocol.get("eligible_ids", []))
    excluded = dict(protocol.get("exclusions", {}))
    rubrics = dict(protocol.get("rubrics", {}))
    if len(eligible) != len(set(eligible)):
        raise ProtocolError("eligible_ids contains duplicates")
    if set(eligible) & set(excluded):
        raise ProtocolError("eligible and excluded IDs overlap")
    if set(eligible) | set(excluded) != set(scenarios):
        raise ProtocolError("eligible and excluded IDs do not partition the source suite")
    if set(rubrics) != set(eligible):
        raise ProtocolError("rubric IDs do not exactly match eligible IDs")

    for scenario_id, rubric in rubrics.items():
        required = rubric.get("required")
        if not isinstance(required, dict) or not required:
            raise ProtocolError(f"{scenario_id}: empty rubric")
        for group, patterns in required.items():
            if not isinstance(patterns, list) or not patterns:
                raise ProtocolError(f"{scenario_id}/{group}: empty pattern group")
            for pattern in patterns:
                try:
                    re.compile(pattern, re.IGNORECASE | re.DOTALL)
                except re.error as exc:
                    raise ProtocolError(
                        f"{scenario_id}/{group}: invalid regex {pattern!r}: {exc}"
                    ) from exc

    for scenario_id in eligible:
        validate_scenario(scenarios[scenario_id])
    return protocol


def load_scenario_map(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scenarios = payload if isinstance(payload, list) else payload.get("scenarios", [])
    if not isinstance(scenarios, list):
        raise ProtocolError("scenario payload has no list")
    result: dict[str, dict] = {}
    for scenario in scenarios:
        scenario_id = str(scenario.get("id", ""))
        if not scenario_id or scenario_id in result:
            raise ProtocolError(f"missing or duplicate scenario ID: {scenario_id!r}")
        result[scenario_id] = scenario
    return result


def user_only_text(session: dict) -> str:
    """Extract only user-authored content from either supported schema."""
    if isinstance(session.get("turns"), list):
        chunks = []
        for turn in session["turns"]:
            role = str(turn.get("speaker", turn.get("role", ""))).strip().lower()
            text = str(turn.get("text", turn.get("content", ""))).strip()
            if role == "user" and text:
                chunks.append(text)
        return "\n".join(chunks)

    chunks = []
    for line in str(session.get("conversation", "")).splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("user:"):
            text = stripped.split(":", 1)[1].strip()
            if text:
                chunks.append(text)
    return "\n".join(chunks)


def validate_scenario(scenario: dict) -> None:
    scenario_id = str(scenario.get("id", "unknown"))
    sessions = scenario.get("sessions")
    if not isinstance(sessions, list) or len(sessions) < 2:
        raise ProtocolError(f"{scenario_id}: expected at least two sessions")
    trigger_id = str(scenario.get("trigger_session", {}).get("session_id", ""))
    ids = [str(session.get("session_id", "")) for session in sessions]
    if ids.count(trigger_id) != 1:
        raise ProtocolError(f"{scenario_id}: trigger session is missing or duplicated")
    if ids[-1] != trigger_id:
        raise ProtocolError(f"{scenario_id}: trigger must be the final stored session")
    for session in sessions:
        timestamp = str(session.get("timestamp", ""))
        try:
            datetime.strptime(timestamp, "%Y-%m-%d")
        except ValueError as exc:
            raise ProtocolError(f"{scenario_id}: invalid timestamp {timestamp!r}") from exc
        text = user_only_text(session)
        if not text:
            raise ProtocolError(f"{scenario_id}: session has no user text")
        if "Assistant:" in text:
            raise ProtocolError(f"{scenario_id}: assistant continuation leaked")


def scenario_sessions(scenario: dict) -> list[dict]:
    return [
        {
            "session_id": str(session["session_id"]),
            "timestamp": str(session["timestamp"]),
            "user_text": user_only_text(session),
        }
        for session in scenario["sessions"]
    ]


def render_history(sessions: Iterable[dict]) -> str:
    chunks = [
        f"[{session['timestamp']}; session {session['session_id']}]\n{session['user_text']}"
        for session in sessions
    ]
    return "\n\n".join(chunks) if chunks else "(none)"


TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def lexical_top_one(history: list[dict], query: str) -> tuple[dict, list[dict]]:
    """Return top-1 session using a frozen BM25-style lexical score."""
    if not history:
        raise ProtocolError("retrieval baseline requires at least one history session")
    documents = [tokenize(session["user_text"]) for session in history]
    query_terms = sorted(set(tokenize(query)))
    average_length = sum(len(doc) for doc in documents) / len(documents)
    k1 = 1.2
    b = 0.75
    scores: list[dict] = []
    for index, document in enumerate(documents):
        counts = Counter(document)
        score = 0.0
        for term in query_terms:
            document_frequency = sum(1 for candidate in documents if term in candidate)
            inverse_document_frequency = math.log(
                1.0 + (len(documents) - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            frequency = counts.get(term, 0)
            if not frequency:
                continue
            normalization = frequency + k1 * (
                1.0 - b + b * len(document) / max(average_length, 1.0)
            )
            score += inverse_document_frequency * frequency * (k1 + 1.0) / normalization
        scores.append(
            {
                "session_id": history[index]["session_id"],
                "score": round(score, 12),
                "source_index": index,
            }
        )
    # Stable earliest-session tie break is part of the frozen rule.
    best = max(scores, key=lambda item: (item["score"], -item["source_index"]))
    return history[best["source_index"]], scores


def extract_python_source(text: str) -> str:
    stripped = text.strip()
    fenced = re.findall(r"```(?:python)?\s*(.*?)```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        stripped = fenced[0].strip()
    else:
        starts = []
        for marker in ("from ", "import ", "STATE", "\"\"\"", "'''"):
            index = stripped.find(marker)
            if index >= 0:
                starts.append(index)
        if starts and min(starts) > 0:
            stripped = stripped[min(starts):]
    if not stripped:
        raise GeneratedCodeError("model returned empty source")
    return stripped.rstrip() + "\n"


FORBIDDEN_CALLS = {
    "breakpoint",
    "compile",
    "delattr",
    "dir",
    "eval",
    "exec",
    "getattr",
    "globals",
    "help",
    "input",
    "locals",
    "memoryview",
    "open",
    "setattr",
    "type",
    "vars",
    "__import__",
}

FORBIDDEN_ATTRIBUTES = {
    "now",
    "today",
    "utcnow",
    "system",
    "popen",
    "read_text",
    "read_bytes",
    "write_text",
    "write_bytes",
    "open",
}

FORBIDDEN_NODE_TYPES = (
    ast.AsyncFunctionDef,
    ast.Await,
    ast.ClassDef,
    ast.Delete,
    ast.Global,
    ast.Lambda,
    ast.Nonlocal,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Yield,
    ast.YieldFrom,
)


def validate_generated_source(source: str) -> dict:
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        raise GeneratedCodeError(f"syntax error at line {exc.lineno}: {exc.msg}") from exc

    allowed_top_level = (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign, ast.FunctionDef)
    state_defined = False
    checker: ast.FunctionDef | None = None
    imports: list[str] = []

    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if not isinstance(node, allowed_top_level):
            raise GeneratedCodeError(
                f"top-level {type(node).__name__} is not allowed; use definitions only"
            )
        if isinstance(node, ast.Assign):
            state_defined |= any(isinstance(target, ast.Name) and target.id == "STATE" for target in node.targets)
        if isinstance(node, ast.AnnAssign):
            state_defined |= isinstance(node.target, ast.Name) and node.target.id == "STATE"
        if isinstance(node, ast.FunctionDef) and node.name == "check_constraints":
            checker = node

    for node in ast.walk(tree):
        if isinstance(node, FORBIDDEN_NODE_TYPES):
            raise GeneratedCodeError(f"{type(node).__name__} is not allowed")
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root not in ALLOWED_IMPORTS:
                    raise GeneratedCodeError(f"import not allowed: {alias.name}")
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            if node.level or root not in ALLOWED_IMPORTS:
                raise GeneratedCodeError(f"import not allowed: {module}")
            if any(alias.name == "*" for alias in node.names):
                raise GeneratedCodeError("star imports are not allowed")
            imports.append(module)
        elif isinstance(node, ast.Name) and node.id.startswith("__"):
            raise GeneratedCodeError(f"dunder name is not allowed: {node.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("_") or node.attr in FORBIDDEN_ATTRIBUTES:
                raise GeneratedCodeError(f"attribute is not allowed: {node.attr}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALLS:
                raise GeneratedCodeError(f"call is not allowed: {node.func.id}")

    if not state_defined:
        raise GeneratedCodeError("STATE is not defined at module scope")
    if checker is None:
        raise GeneratedCodeError("check_constraints(current_time) is not defined")
    positional_args = list(checker.args.posonlyargs) + list(checker.args.args)
    if not positional_args or positional_args[0].arg != "current_time":
        raise GeneratedCodeError("check_constraints must accept current_time as its first argument")
    if checker.decorator_list:
        raise GeneratedCodeError("decorators are not allowed")

    return {
        "valid": True,
        "ast_nodes": sum(1 for _ in ast.walk(tree)),
        "imports": sorted(set(imports)),
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
    }


def execute_generated_source(source_path: Path, current_time: str, timeout: int = 5) -> dict:
    command = [
        sys.executable,
        "-I",
        "-S",
        str(SANDBOX_PATH),
        str(source_path),
        current_time,
    ]
    minimal_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONHASHSEED": "0",
    }
    try:
        completed = subprocess.run(
            command,
            cwd=source_path.parent,
            env=minimal_env,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise GeneratedCodeError(f"sandbox timed out after {timeout}s") from exc
    if completed.returncode != 0:
        stderr = completed.stderr.strip().replace(str(ROOT), "<repo>")
        raise GeneratedCodeError(
            f"sandbox exited {completed.returncode}: {stderr[-1000:]}"
        )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise GeneratedCodeError("sandbox returned invalid JSON") from exc
    if not isinstance(value, dict) or not isinstance(value.get("state"), dict) or not isinstance(value.get("alerts"), list):
        raise GeneratedCodeError("sandbox result has invalid shape")
    return value


def score_text(text: str, rubric: dict) -> dict:
    groups: dict[str, dict] = {}
    for group, patterns in rubric["required"].items():
        matches = []
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
            if match:
                matches.append({"pattern": pattern, "text": match.group(0)})
        groups[group] = {"passed": bool(matches), "matches": matches}
    return {
        "passed": all(value["passed"] for value in groups.values()),
        "matched_groups": sum(1 for value in groups.values() if value["passed"]),
        "required_groups": len(groups),
        "groups": groups,
    }


def score_candidates(candidates: list[str], rubric: dict) -> dict:
    scored = [score_text(candidate, rubric) for candidate in candidates]
    passing_indices = [index for index, score in enumerate(scored) if score["passed"]]
    return {
        "passed": bool(passing_indices),
        "passing_candidate_indices": passing_indices,
        "candidates": scored,
    }


class KrillModelGenerator:
    def __init__(self, settings: ModelSettings, max_retries: int = 6):
        self.settings = settings
        self.max_retries = max_retries

    def generate(self, system_prompt: str, user_prompt: str) -> dict:
        started = time.monotonic()
        before = usage_snapshot()
        text = krill_call(
            user_prompt,
            system_instruction=system_prompt,
            model=self.settings.name,
            max_retries=self.max_retries,
        )
        after = usage_snapshot()
        usage = {
            key: int(after.get(key, 0)) - int(before.get(key, 0))
            for key in set(before) | set(after)
            if int(after.get(key, 0)) - int(before.get(key, 0))
        }
        return {
            "text": text,
            "latency_seconds": round(time.monotonic() - started, 3),
            "usage": usage,
        }


def run_uac(
    scenario_id: str,
    sessions: list[dict],
    rubric: dict,
    generator: KrillModelGenerator,
    programs_dir: Path,
) -> dict:
    updates = []
    cumulative: list[dict] = []
    pretrigger_alert_count = 0
    all_updates_valid = True
    all_updates_executable = True
    trigger_candidates: list[str] = []

    for index, session in enumerate(sessions):
        cumulative.append(session)
        stage = "trigger" if index == len(sessions) - 1 else "pretrigger"
        prompt = UAC_UPDATE_TEMPLATE.format(
            timestamp=session["timestamp"],
            history=render_history(cumulative),
        )
        update: dict[str, Any] = {
            "stage": stage,
            "session": session,
            "system_prompt": UAC_SYSTEM_PROMPT,
            "user_prompt": prompt,
        }
        try:
            generation = generator.generate(UAC_SYSTEM_PROMPT, prompt)
            update["generation"] = generation
            source = extract_python_source(generation["text"])
            update["source"] = source
            source_path = programs_dir / scenario_id / f"{index + 1:02d}_{stage}.py"
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_text(source, encoding="utf-8")
            update["source_path"] = trace_path(source_path)
            validation = validate_generated_source(source)
            update["validation"] = validation
        except Exception as exc:
            all_updates_valid = False
            all_updates_executable = False
            update["error_stage"] = "generation_or_validation"
            update["error"] = str(exc)
            updates.append(update)
            continue

        try:
            execution = execute_generated_source(source_path, session["timestamp"])
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

    posttrigger_score = score_candidates(trigger_candidates, rubric)
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


def run_baseline(
    system: str,
    sessions: list[dict],
    rubric: dict,
    generator: KrillModelGenerator,
) -> dict:
    history = sessions[:-1]
    trigger = sessions[-1]
    retrieval_scores: list[dict] | None = None
    if system == "full_context":
        selected = history
    elif system == "retrieval":
        top_session, retrieval_scores = lexical_top_one(history, trigger["user_text"])
        selected = [top_session]
    else:
        raise ValueError(f"unknown baseline: {system}")

    prompt = BASELINE_USER_TEMPLATE.format(
        history=render_history(selected),
        timestamp=trigger["timestamp"],
        trigger=trigger["user_text"],
    )
    result: dict[str, Any] = {
        "selected_history_session_ids": [session["session_id"] for session in selected],
        "retrieval_scores": retrieval_scores,
        "system_prompt": BASELINE_SYSTEM_PROMPT,
        "user_prompt": prompt,
    }
    try:
        generation = generator.generate(BASELINE_SYSTEM_PROMPT, prompt)
        result["generation"] = generation
        result["response"] = generation["text"]
        result["score"] = score_text(generation["text"], rubric)
        result["passed"] = result["score"]["passed"]
    except Exception as exc:
        result["passed"] = False
        result["error"] = str(exc)
    return result


def run_case(
    scenario: dict,
    rubric: dict,
    generator: KrillModelGenerator,
    systems: list[str],
    programs_dir: Path,
) -> dict:
    sessions = scenario_sessions(scenario)
    trace: dict[str, Any] = {
        "protocol_id": "active-service-v2.1",
        "scenario_id": scenario["id"],
        "category": scenario["category"],
        "description": scenario["description"],
        "started_at": utc_now(),
        "sessions": sessions,
        "systems": {},
    }
    if "uac" in systems:
        trace["systems"]["uac"] = run_uac(
            scenario["id"], sessions, rubric, generator, programs_dir
        )
    for system in ("full_context", "retrieval"):
        if system in systems:
            trace["systems"][system] = run_baseline(
                system, sessions, rubric, generator
            )
    trace["completed_at"] = utc_now()
    return trace


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> list[float]:
    if total == 0:
        return [0.0, 0.0]
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt(
        proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total)
    ) / denominator
    return [round(max(0.0, center - margin), 6), round(min(1.0, center + margin), 6)]


def exact_mcnemar_p(discordant_a: int, discordant_b: int) -> float:
    total = discordant_a + discordant_b
    if total == 0:
        return 1.0
    tail = sum(math.comb(total, k) for k in range(0, min(discordant_a, discordant_b) + 1)) / (2 ** total)
    return round(min(1.0, 2.0 * tail), 8)


def aggregate_traces(traces: list[dict], systems: list[str]) -> dict:
    by_system: dict[str, dict] = {}
    for system in systems:
        available = [trace for trace in traces if system in trace.get("systems", {})]
        successes = sum(bool(trace["systems"][system].get("passed")) for trace in available)
        by_category: dict[str, dict] = {}
        for category in sorted({trace["category"] for trace in available}):
            category_traces = [trace for trace in available if trace["category"] == category]
            category_successes = sum(
                bool(trace["systems"][system].get("passed")) for trace in category_traces
            )
            by_category[category] = {
                "passed": category_successes,
                "total": len(category_traces),
                "recall": round(category_successes / len(category_traces), 6),
            }
        by_system[system] = {
            "passed": successes,
            "total": len(available),
            "recall": round(successes / len(available), 6) if available else 0.0,
            "wilson_95": wilson_interval(successes, len(available)),
            "by_category": by_category,
        }

    pairwise: dict[str, dict] = {}
    for left_index, left in enumerate(systems):
        for right in systems[left_index + 1:]:
            paired = [
                trace for trace in traces
                if left in trace.get("systems", {}) and right in trace.get("systems", {})
            ]
            left_only = sum(
                bool(trace["systems"][left].get("passed"))
                and not bool(trace["systems"][right].get("passed"))
                for trace in paired
            )
            right_only = sum(
                bool(trace["systems"][right].get("passed"))
                and not bool(trace["systems"][left].get("passed"))
                for trace in paired
            )
            both = sum(
                bool(trace["systems"][left].get("passed"))
                and bool(trace["systems"][right].get("passed"))
                for trace in paired
            )
            neither = len(paired) - left_only - right_only - both
            pairwise[f"{left}_vs_{right}"] = {
                "both_pass": both,
                "left_only_pass": left_only,
                "right_only_pass": right_only,
                "neither_pass": neither,
                "exact_mcnemar_p": exact_mcnemar_p(left_only, right_only),
            }
    return {
        "case_count": len(traces),
        "by_system": by_system,
        "pairwise": pairwise,
    }


def usage_totals(traces: list[dict]) -> dict[str, int]:
    totals: Counter = Counter()
    for trace in traces:
        for system_result in trace.get("systems", {}).values():
            generations = []
            if "generation" in system_result:
                generations.append(system_result["generation"])
            for update in system_result.get("updates", []):
                if "generation" in update:
                    generations.append(update["generation"])
            for generation in generations:
                usage = generation.get("usage", {})
                for key, value in usage.items():
                    totals[key] += int(value)
                # The shared Krill client records one request in every usage
                # snapshot. Retain a fallback for test doubles or historical
                # generators that omit that field, but never count both.
                if "requests" not in usage:
                    totals["requests"] += 1
    return dict(totals)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL_PATH)
    parser.add_argument("--model", help="one model name frozen in the protocol")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--case", action="append", dest="case_ids", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--systems", nargs="+", choices=SYSTEMS, default=list(SYSTEMS))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="validate the frozen protocol and exit without loading the model client",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    protocol_path = args.protocol.resolve()
    protocol = load_protocol(protocol_path)
    source_path = ROOT / protocol["source_suite"]["path"]
    scenario_map = load_scenario_map(source_path)
    selected_ids = list(protocol["eligible_ids"])
    if args.case_ids:
        unknown = set(args.case_ids) - set(selected_ids)
        if unknown:
            raise ProtocolError(f"requested non-eligible case(s): {sorted(unknown)}")
        selected_ids = [scenario_id for scenario_id in selected_ids if scenario_id in args.case_ids]
    if args.limit is not None:
        if args.limit < 1:
            raise ProtocolError("--limit must be positive")
        selected_ids = selected_ids[: args.limit]
    systems = list(dict.fromkeys(args.systems))

    print(
        f"Validated {protocol['protocol_id']}: {len(protocol['eligible_ids'])} eligible "
        f"of {protocol['source_suite']['total_scenarios']} scenarios."
    )
    if args.validate_only:
        return

    model_map = {str(model["name"]): model for model in protocol["models"]}
    model_name = args.model or next(iter(model_map))
    if model_name not in model_map:
        raise ProtocolError(
            f"model {model_name!r} is not frozen in the protocol; choose {sorted(model_map)}"
        )
    model_payload = model_map[model_name]
    settings = ModelSettings(name=model_name)
    generator = KrillModelGenerator(settings)
    slug = re.sub(r"[^a-z0-9]+", "_", model_name.lower()).strip("_")
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir
        else DEFAULT_OUTPUT_ROOT / f"active_service_v2_{slug}"
    )
    traces_dir = output_dir / "traces"
    programs_dir = output_dir / "programs"
    traces_dir.mkdir(parents=True, exist_ok=True)
    programs_dir.mkdir(parents=True, exist_ok=True)

    run_started = utc_now()
    traces: list[dict] = []
    for index, scenario_id in enumerate(selected_ids, start=1):
        trace_path = traces_dir / f"{scenario_id}.json"
        if args.resume and trace_path.is_file():
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            if set(systems).issubset(trace.get("systems", {})):
                print(f"[{index}/{len(selected_ids)}] {scenario_id}: resume existing trace")
                traces.append(trace)
                continue
        print(f"[{index}/{len(selected_ids)}] {scenario_id}: running", flush=True)
        trace = run_case(
            scenario_map[scenario_id],
            protocol["rubrics"][scenario_id],
            generator,
            systems,
            programs_dir,
        )
        atomic_write_json(trace_path, trace)
        traces.append(trace)
        statuses = ", ".join(
            f"{system}={'PASS' if trace['systems'][system]['passed'] else 'MISS'}"
            for system in systems
        )
        print(f"    {statuses}", flush=True)

    summary = aggregate_traces(traces, systems)
    manifest = {
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": sha256_file(protocol_path),
        "source_suite_sha256": sha256_file(source_path),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "sandbox_sha256": sha256_file(SANDBOX_PATH),
        "git_commit": git_commit(),
        "model": model_payload,
        "systems": systems,
        "selected_ids": selected_ids,
        "complete_frozen_suite": selected_ids == protocol["eligible_ids"] and systems == list(SYSTEMS),
        "started_at": run_started,
        "completed_at": utc_now(),
        "usage": usage_totals(traces),
        "summary": summary,
    }
    atomic_write_json(output_dir / "manifest.json", manifest)
    print(json.dumps(summary["by_system"], indent=2))
    print(f"Results: {output_dir}")


if __name__ == "__main__":
    main()
