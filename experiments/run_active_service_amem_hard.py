#!/usr/bin/env python3
"""Run a deprecated proactive-alert pilot with the A-MEM library.

This prompt-based pilot is not publication-ready evidence for constraint
execution or cross-system Active Service performance.
"""
from __future__ import annotations
import json
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from active_service_experiment import (  # noqa: E402
    SYSTEM_PROMPT_FLAT, MODEL, client, history_sessions, load_scenarios,
    trigger_user_message, user_only_text,
)
from google import genai

EVAL_DIR = pathlib.Path(__file__).resolve().parent.parent / "evaluation"
RESULTS_DIR = pathlib.Path(__file__).resolve().parent / "results"


def _session_text(session: dict) -> str:
    return user_only_text(session)


def run_one(scenario: dict) -> dict:
    from agentic_memory.memory_system import AgenticMemorySystem

    memory = AgenticMemorySystem(
        model_name="all-MiniLM-L6-v2", llm_backend="openai", llm_model="gpt-4o-mini",
    )
    for s in history_sessions(scenario):
        text = _session_text(s)
        if text:
            memory.add_note(text)

    user_message = trigger_user_message(scenario)

    # Use raw retrieval that includes content (top-20).
    try:
        ctx = memory.find_related_memories_raw(user_message, k=20)
    except Exception:
        ctx = ""
    if not ctx.strip():
        try:
            results = memory.retriever.search(user_message, 20)
            parts = []
            if results.get("metadatas") and results["metadatas"]:
                for md in results["metadatas"][0]:
                    if md and md.get("content"):
                        parts.append(md["content"])
            ctx = "\n\n".join(parts)
        except Exception:
            ctx = ""
    if not ctx.strip():
        ctx = "(no memories retrieved)"

    system = SYSTEM_PROMPT_FLAT.format(memory=ctx)
    try:
        resp = client.models.generate_content(
            model=MODEL, contents=user_message,
            config=genai.types.GenerateContentConfig(
                system_instruction=system, temperature=0.3, max_output_tokens=1024,
            ),
        )
        response_text = resp.text or ""
    except Exception as e:
        response_text = f"ERROR: {e}"

    expected = scenario.get("expected_alert", {})
    msg = expected.get("message", "")
    keywords = []
    for term in re.findall(r"\b\w{4,}\b", msg):
        if term.lower() not in {"that", "this", "with", "from", "your", "have", "been",
                                 "will", "should", "could", "would", "there", "their",
                                 "than", "more", "only", "days", "before", "after"}:
            keywords.append(term.lower())
    rl = response_text.lower()
    hits = sum(1 for kw in keywords if kw in rl)
    kscore = hits / max(len(keywords), 1)
    has_alert = any(p in rl for p in [
        "alert", "warning", "caution", "important", "notice", "heads up", "concern",
        "issue", "problem", "conflict", "expires", "expiring", "expired",
        "contraindicated", "interaction", "conflicting", "deadline", "urgent",
        "remind", "flag", "attention",
    ])
    detected = kscore > 0.15 and has_alert
    return {
        "scenario_id": scenario.get("id", "unknown"),
        "category": scenario.get("category", "unknown"),
        "response": response_text,
        "keyword_score": round(kscore, 3),
        "has_alert_language": has_alert,
        "proactive_alert_detected": detected,
    }


def main() -> None:
    print(
        "WARNING: deprecated exploratory protocol; do not report as Active "
        "Service evidence.",
        flush=True,
    )
    out_path = RESULTS_DIR / "active_service_amem_hard.json"
    if out_path.exists():
        results = json.load(open(out_path))
    else:
        results = {"by_scenario": {}}
    results["publication_ready"] = False
    results["protocol_status"] = "deprecated exploratory alert-prompting pilot"

    scenarios = load_scenarios(EVAL_DIR / "hard_active_service_scenarios.json")
    for i, sc in enumerate(scenarios):
        sid = sc.get("id", f"hard_{i}")
        if sid in results["by_scenario"]:
            continue
        print(f"[{i+1}/{len(scenarios)}] {sid} ...", flush=True)
        r = run_one(sc)
        results["by_scenario"][sid] = r
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"  detected={r['proactive_alert_detected']}", flush=True)

    n = len(results["by_scenario"])
    det = sum(1 for v in results["by_scenario"].values() if v.get("proactive_alert_detected"))
    results["alert_rate"] = det / max(n, 1)
    results["n"] = n
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"DONE: {det}/{n} = {det/max(n,1):.3f}")


if __name__ == "__main__":
    main()
