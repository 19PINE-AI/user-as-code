"""Runners for the Modularity / Progressive-Disclosure ablation.

Three strategies, all using the same Python REPL + Gemini 3 Flash:

1. monolithic_repl
   All 300 records (all domains) loaded into the REPL as `records_raw` (a
   single dict mapping domain -> list[dict]). Models the naive "dump
   everything" baseline.

2. modular_repl
   The same 6-domain dict, but the LLM is told it can pick any subset of
   domains to load via a `load_domain(name)` Python helper. The pre-loaded
   namespace contains only `manifest` (domain summaries) plus the loader.
   Models a UaC project organized by life-domain folders.

3. manifest_repl
   Same as modular_repl but with the manifest pre-loaded into the system
   instruction (so the LLM can route without an extra read).

All three measure prompt + output + thoughts tokens via tools.extract_usage.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from analytical_bench.tools import (  # noqa: E402
    PythonREPL, run_tool_loop, _gemini_call, extract_usage,
)
from google import genai


def _final_line(text: str) -> str:
    lines = [l.strip() for l in str(text).split("\n") if l.strip()]
    return lines[-1] if lines else ""


def run_monolithic_repl(case: dict, user_state: dict, summaries: dict) -> dict[str, Any]:
    """Strategy 1: ALWAYS-DUMP — full state inlined into the LLM system prompt
    (worst case for progressive disclosure)."""
    full_text = json.dumps(user_state, indent=1)
    repl = PythonREPL(initial_namespace={"records_raw": user_state}, timeout=20.0)
    sys_inst = (
        "You have a Python REPL via the `python` tool. The user's full state "
        "is shown below in JSON, and is also available in `records_raw` "
        f"(a dict keyed by domain: {list(user_state.keys())}).\n\n"
        f"USER STATE:\n{full_text}\n\n"
        "Use ONE python call to compute the answer and return it on the last line."
    )
    return run_tool_loop(
        question=case["question"], system_instruction=sys_inst,
        repl=repl, max_turns=8, thinking_budget=2048,
    )


def run_modular_repl(case: dict, user_state: dict, summaries: dict) -> dict[str, Any]:
    """Strategy 2: domain-routed loading via `load_domain` helper.

    The REPL starts with only `manifest` (domain summaries) and a
    `load_domain(name)` helper. The LLM must call `load_domain('trips')` to
    materialize a domain into a Python variable, mirroring how a UaC project
    organized into domain folders would be queried.
    """
    # We pre-build a closure for load_domain that pulls from user_state.
    boot = {
        "manifest": summaries,
        "_full_state": user_state,
    }
    repl = PythonREPL(initial_namespace=boot, timeout=20.0)
    # Inject the loader into the namespace by running setup code once.
    repl.run(
        "def load_domain(name):\n"
        "    \"\"\"Materialize one domain into a global var named <name>_records.\"\"\"\n"
        "    if name not in _full_state:\n"
        "        return f'unknown domain {name}; available: {list(_full_state.keys())}'\n"
        "    globals()[f'{name}_records'] = _full_state[name]\n"
        "    return f'loaded {len(_full_state[name])} records into {name}_records'\n"
    )
    sys_inst = (
        "You have a Python REPL via the `python` tool. "
        "`manifest` is a dict mapping domain name to a brief summary. "
        "`load_domain(name)` materializes one domain into a list of dicts in "
        "a global named `<name>_records` (e.g., load_domain('trips') gives "
        "you `trips_records`). Pick the relevant domain(s), load them, and "
        "compute the answer. Return ONLY the final answer on the last line."
    )
    return run_tool_loop(
        question=case["question"], system_instruction=sys_inst,
        repl=repl, max_turns=10, thinking_budget=2048,
    )


def run_manifest_repl(case: dict, user_state: dict, summaries: dict) -> dict[str, Any]:
    """Strategy 3: manifest in system prompt (progressive disclosure).

    Identical to modular_repl except the manifest is embedded in the system
    prompt rather than loaded from a Python variable. Saves the LLM one
    routing step.
    """
    boot = {"_full_state": user_state}
    repl = PythonREPL(initial_namespace=boot, timeout=20.0)
    repl.run(
        "def load_domain(name):\n"
        "    if name not in _full_state:\n"
        "        return f'unknown domain {name}; available: {list(_full_state.keys())}'\n"
        "    globals()[f'{name}_records'] = _full_state[name]\n"
        "    return f'loaded {len(_full_state[name])} records into {name}_records'\n"
    )
    manifest_text = "\n".join(f"  - {k}: {v}" for k, v in summaries.items())
    sys_inst = (
        "You have a Python REPL via the `python` tool. The user's memory is "
        "organized by domain. Manifest:\n"
        f"{manifest_text}\n\n"
        "Call `load_domain('<name>')` to materialize one domain into "
        "`<name>_records` (a list of dicts). Pick the relevant domain(s), "
        "load them, compute the answer. Return ONLY the final answer on the "
        "last line."
    )
    return run_tool_loop(
        question=case["question"], system_instruction=sys_inst,
        repl=repl, max_turns=10, thinking_budget=2048,
    )


def run_uac_full_state(case: dict, user_state: dict, summaries: dict) -> dict[str, Any]:
    """Strategy 4 (control): UaC-style structured Python over the full state.

    Same as monolithic_repl but the records are already typed (we skip the
    structuring call since the records are clean). Used to confirm that the
    accuracy is preserved across strategies.
    """
    return run_monolithic_repl(case, user_state, summaries)


RUNNERS = {
    "monolithic": run_monolithic_repl,
    "modular": run_modular_repl,
    "manifest": run_manifest_repl,
}
