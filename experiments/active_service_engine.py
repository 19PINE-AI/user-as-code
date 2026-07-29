#!/usr/bin/env python3
"""Validated constraint IR and deterministic compiler for Active Service.

Paper map: "Cue-Free Constraint Detection" (sec:active-service) and
"Compiled deadline check" (fig:constraint-example). This module
implements the validated-constraint, deterministic-compilation, date-arithmetic,
activation-window, and sandbox-facing steps described there.

The first Active Service implementation asked the model to write unrestricted
Python after every session.  That coupled semantic memory quality to incidental
code-generation details (imports, date APIs, and even stray Unicode).  This
module narrows the model boundary to a JSON-serializable intermediate
representation (IR).  Trusted code validates the IR and compiles it into the
small executable module consumed by the existing sandbox.
"""
from __future__ import annotations

import json
import pprint
import re
from datetime import date, timedelta
from typing import Any


ENGINE_ID = "active-service-constraint-ir-v1"
CONSTRAINT_KEYS = {
    "id",
    "severity",
    "type",
    "message_template",
    "active_from",
    "active_until",
    "deadline",
    "deadline_anchor",
    "deadline_offset_days",
}
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
IDENTIFIER_RE = re.compile(r"[a-z][a-z0-9_]{0,79}\Z")


class ConstraintIRError(ValueError):
    """Raised when a model response does not satisfy the constraint IR."""


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract one JSON object, tolerating a surrounding Markdown fence."""
    stripped = text.strip()
    fenced = re.findall(
        r"```(?:json)?\s*(.*?)```",
        stripped,
        flags=re.IGNORECASE | re.DOTALL,
    )
    candidate = fenced[0].strip() if fenced else stripped
    start = candidate.find("{")
    if start < 0:
        raise ConstraintIRError("model response contains no JSON object")
    try:
        value, _ = json.JSONDecoder().raw_decode(candidate[start:])
    except json.JSONDecodeError as exc:
        raise ConstraintIRError(
            f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(value, dict):
        raise ConstraintIRError("model response must contain a JSON object")
    return value


def _validate_iso_date(value: object, label: str, *, optional: bool) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        raise ConstraintIRError(f"{label} must be an ISO YYYY-MM-DD string")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ConstraintIRError(f"{label} is not a real calendar date: {value}") from exc
    return value


def validate_constraint_ir(value: object) -> dict[str, Any]:
    """Validate the model-authored IR before execution as described in
    "Cue-Free Constraint Detection" (sec:active-service).
    """
    if not isinstance(value, dict):
        raise ConstraintIRError("IR must be a dictionary")
    if set(value) != {"state", "constraints"}:
        raise ConstraintIRError("IR must have exactly the keys state and constraints")
    state = value["state"]
    constraints = value["constraints"]
    if not isinstance(state, dict):
        raise ConstraintIRError("state must be a dictionary")
    if not isinstance(constraints, list):
        raise ConstraintIRError("constraints must be a list")

    # Round-trip once to reject model-specific objects, NaN, or non-string keys
    # and to detach the validated value from the parser's mutable containers.
    try:
        canonical_state = json.loads(
            json.dumps(state, ensure_ascii=False, allow_nan=False)
        )
    except (TypeError, ValueError) as exc:
        raise ConstraintIRError(f"state is not strict JSON: {exc}") from exc

    canonical_constraints: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for index, constraint in enumerate(constraints):
        label = f"constraint {index}"
        if not isinstance(constraint, dict):
            raise ConstraintIRError(f"{label} must be a dictionary")
        if set(constraint) != CONSTRAINT_KEYS:
            missing = sorted(CONSTRAINT_KEYS - set(constraint))
            extra = sorted(set(constraint) - CONSTRAINT_KEYS)
            raise ConstraintIRError(
                f"{label} has wrong keys (missing={missing}, extra={extra})"
            )

        identifier = constraint["id"]
        if not isinstance(identifier, str) or not IDENTIFIER_RE.fullmatch(identifier):
            raise ConstraintIRError(f"{label}.id must be a short snake_case identifier")
        if identifier in identifiers:
            raise ConstraintIRError(f"duplicate constraint id: {identifier}")
        identifiers.add(identifier)

        severity = constraint["severity"]
        constraint_type = constraint["type"]
        message = constraint["message_template"]
        if severity not in {"info", "warning", "high", "critical"}:
            raise ConstraintIRError(f"{label}.severity is unsupported")
        if not isinstance(constraint_type, str) or not IDENTIFIER_RE.fullmatch(constraint_type):
            raise ConstraintIRError(f"{label}.type must be snake_case")
        if not isinstance(message, str) or not message.strip():
            raise ConstraintIRError(f"{label}.message_template must be non-empty")
        unknown_placeholders = set(re.findall(r"\{([^{}]+)\}", message)) - {
            "days_remaining",
            "deadline",
        }
        if unknown_placeholders:
            raise ConstraintIRError(
                f"{label}.message_template has unsupported placeholders: "
                f"{sorted(unknown_placeholders)}"
            )

        active_from = _validate_iso_date(
            constraint["active_from"], f"{label}.active_from", optional=True
        )
        active_until = _validate_iso_date(
            constraint["active_until"], f"{label}.active_until", optional=True
        )
        deadline = _validate_iso_date(
            constraint["deadline"], f"{label}.deadline", optional=True
        )
        deadline_anchor = _validate_iso_date(
            constraint["deadline_anchor"],
            f"{label}.deadline_anchor",
            optional=True,
        )
        deadline_offset_days = constraint["deadline_offset_days"]
        if deadline_offset_days is not None and (
            not isinstance(deadline_offset_days, int)
            or isinstance(deadline_offset_days, bool)
            or abs(deadline_offset_days) > 3660
        ):
            raise ConstraintIRError(
                f"{label}.deadline_offset_days must be an integer or null"
            )
        derived_deadline = deadline_anchor is not None or deadline_offset_days is not None
        if derived_deadline and (
            deadline_anchor is None or deadline_offset_days is None
        ):
            raise ConstraintIRError(
                f"{label} must provide both deadline_anchor and deadline_offset_days"
            )
        if deadline is not None and derived_deadline:
            raise ConstraintIRError(
                f"{label} must use either an explicit deadline or an anchor/offset, not both"
            )
        has_deadline = deadline is not None or derived_deadline
        if has_deadline:
            if active_from is not None or active_until is not None:
                raise ConstraintIRError(
                    f"{label} deadline activation is compiler-derived; "
                    "active_from and active_until must be null"
                )
            if "{days_remaining}" not in message or "{deadline}" not in message:
                raise ConstraintIRError(
                    f"{label} deadline messages must use deadline and days_remaining placeholders"
                )
            if not re.search(r"\{days_remaining\}\s+days?\b", message, re.IGNORECASE):
                raise ConstraintIRError(
                    f"{label} must put the word days after days_remaining"
                )
        elif active_from is None:
            raise ConstraintIRError(
                f"{label} direct conflicts require active_from"
            )
        if not has_deadline and not re.search(
            r"\bconflict(?:s|ed|ing)?\b", message, re.IGNORECASE
        ):
            raise ConstraintIRError(
                f"{label} direct conflict messages must explicitly say conflict"
            )
        if active_until is not None and active_from is not None and active_until < active_from:
            raise ConstraintIRError(f"{label} ends before it becomes active")
        if ("{days_remaining}" in message or "{deadline}" in message) and not has_deadline:
            raise ConstraintIRError(
                f"{label} uses deadline placeholders without a deadline"
            )

        canonical_constraints.append(
            {
                "id": identifier,
                "severity": severity,
                "type": constraint_type,
                "message_template": message.strip(),
                "active_from": active_from,
                "active_until": active_until,
                "deadline": deadline,
                "deadline_anchor": deadline_anchor,
                "deadline_offset_days": deadline_offset_days,
            }
        )

    canonical = {"state": canonical_state, "constraints": canonical_constraints}
    # A final strict serialization is also a useful size-independent invariant
    # for artifacts and downstream trace storage.
    json.dumps(canonical, ensure_ascii=False, allow_nan=False)
    return canonical


def compile_constraint_module(ir: dict[str, Any]) -> str:
    """Compile validated IR into the trusted executable code described in
    "Cue-Free Constraint Detection" (sec:active-service) and illustrated by
    "Compiled deadline check" (fig:constraint-example).
    """
    canonical = validate_constraint_ir(ir)
    compiled_constraints: list[dict[str, Any]] = []
    for constraint in canonical["constraints"]:
        compiled = dict(constraint)
        deadline_text = compiled["deadline"]
        if deadline_text is None and compiled["deadline_anchor"] is not None:
            anchor = date.fromisoformat(compiled["deadline_anchor"])
            deadline_text = (
                anchor + timedelta(days=compiled["deadline_offset_days"])
            ).isoformat()
        if deadline_text is not None:
            deadline_value = date.fromisoformat(deadline_text)
            compiled["deadline"] = deadline_text
            compiled["active_from"] = (deadline_value - timedelta(days=7)).isoformat()
            compiled["active_until"] = deadline_text
        compiled_constraints.append(compiled)

    state = {
        "memory": canonical["state"],
        "constraints": compiled_constraints,
    }
    literal = pprint.pformat(
        state,
        width=100,
        sort_dicts=True,
        compact=False,
    )
    return f'''from datetime import date

STATE = {literal}


def check_constraints(current_time):
    current = date.fromisoformat(current_time)
    alerts = []
    for constraint in STATE["constraints"]:
        active_from = date.fromisoformat(constraint["active_from"])
        active_until_text = constraint["active_until"]
        active_until = date.fromisoformat(active_until_text) if active_until_text else None
        if current < active_from or (active_until is not None and current > active_until):
            continue
        message = constraint["message_template"]
        deadline_text = constraint["deadline"]
        if deadline_text:
            remaining = (date.fromisoformat(deadline_text) - current).days
            message = message.replace("{{days_remaining}}", str(remaining))
            message = message.replace("{{deadline}}", deadline_text)
        alerts.append({{
            "severity": constraint["severity"],
            "type": constraint["type"],
            "message": message,
        }})
    return alerts
'''
