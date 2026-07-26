#!/usr/bin/env python3
"""Restricted child interpreter for Active Service v2 generated programs.

This module is invoked with ``python -I -S`` by ``run_active_service_v2.py``.
The parent performs AST validation first; this child adds restricted builtins,
resource limits, and strict output-shape checks. It prints exactly one JSON
object to stdout.
"""
from __future__ import annotations

import argparse
import builtins
import json
import resource
import signal
from pathlib import Path


ALLOWED_IMPORTS = {
    "calendar",
    "collections",
    "datetime",
    "decimal",
    "math",
    "statistics",
}


def restricted_import(
    name: str,
    globals_dict: dict | None = None,
    locals_dict: dict | None = None,
    fromlist: tuple | list = (),
    level: int = 0,
):
    """Import only the standard-library modules allowed by the parent."""
    del globals_dict, locals_dict
    root = name.split(".", 1)[0]
    if level != 0 or root not in ALLOWED_IMPORTS:
        raise ImportError(f"import not allowed: {name}")
    return builtins.__import__(name, fromlist=fromlist, level=level)


SAFE_BUILTINS = {
    "__import__": restricted_import,
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}


def set_limits() -> None:
    """Apply conservative limits before evaluating generated source."""
    def lower_soft_limit(kind: int, target: int) -> None:
        _, hard = resource.getrlimit(kind)
        soft = target if hard == resource.RLIM_INFINITY else min(target, hard)
        resource.setrlimit(kind, (soft, hard))

    lower_soft_limit(resource.RLIMIT_CPU, 2)
    memory_limit = 256 * 1024 * 1024
    for memory_resource in (resource.RLIMIT_AS, resource.RLIMIT_DATA):
        try:
            lower_soft_limit(memory_resource, memory_limit)
            break
        except (OSError, ValueError):
            # Darwin can reject memory rlimits for an already mapped
            # interpreter. The AST restrictions and CPU/wall limits still
            # apply; Linux uses the first supported memory limit above.
            continue
    lower_soft_limit(resource.RLIMIT_FSIZE, 0)
    lower_soft_limit(resource.RLIMIT_NOFILE, 16)
    signal.alarm(3)


def normalize_alerts(value: object) -> list[dict]:
    if not isinstance(value, list):
        raise TypeError("check_constraints() must return a list")
    alerts: list[dict] = []
    for index, alert in enumerate(value):
        if not isinstance(alert, dict):
            raise TypeError(f"alert {index} is not a dictionary")
        message = alert.get("message")
        if not isinstance(message, str) or not message.strip():
            raise TypeError(f"alert {index} has no non-empty message")
        alerts.append(
            {
                "severity": str(alert.get("severity", "warning")),
                "type": str(alert.get("type", "constraint")),
                "message": message.strip(),
            }
        )
    return alerts


def execute(source_path: Path, current_time: str) -> dict:
    source = source_path.read_text(encoding="utf-8")
    namespace = {
        "__builtins__": SAFE_BUILTINS,
        "__name__": "active_service_generated",
    }
    exec(compile(source, str(source_path), "exec"), namespace, namespace)

    state = namespace.get("STATE")
    checker = namespace.get("check_constraints")
    if not isinstance(state, dict):
        raise TypeError("STATE must be a dictionary")
    if not callable(checker):
        raise TypeError("check_constraints must be callable")

    alerts = normalize_alerts(checker(current_time))
    # Round-trip here so generated objects cannot leak through the trace.
    json.dumps(state, ensure_ascii=False, allow_nan=False)
    return {"state": state, "alerts": alerts}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("current_time")
    args = parser.parse_args()
    set_limits()
    result = execute(args.source, args.current_time)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
