#!/usr/bin/env python3
"""Run Active Service with the actual mem0ai 1.0.5 library as the memory.

This is a sanity check against the existing hand-crafted flat-fact baseline:
do real Mem0 retrievals reach a similar number on Active Service?
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from active_service_experiment import (  # noqa: E402
    SYSTEM_PROMPT_FLAT, MODEL, client, load_scenarios,
)
from google import genai

EVAL_DIR = pathlib.Path(__file__).resolve().parent.parent / "evaluation"
RESULTS_DIR = pathlib.Path(__file__).resolve().parent / "results"


def _build_session_text(session: dict) -> str:
    """Render a scenario session as conversational text.

    Active-service scenarios store the dialogue under `conversation` as a
    plain string. Some other formats use `turns: [{speaker, text}]` instead;
    handle both.
    """
    if "conversation" in session and isinstance(session["conversation"], str):
        return session["conversation"]
    parts = []
    for turn in session.get("turns", []):
        speaker = turn.get("speaker", turn.get("role", "user"))
        text = turn.get("text", turn.get("content", ""))
        parts.append(f"{speaker}: {text}")
    return "\n".join(parts)


def run_one(scenario: dict) -> dict:
    """Run a single scenario through actual mem0ai."""
    from mem0 import Memory

    # Clean any stale qdrant lock.
    for p in [pathlib.Path("/tmp/qdrant/.lock"),
              pathlib.Path.home() / ".mem0" / "migrations_qdrant" / ".lock"]:
        p.unlink(missing_ok=True)

    m = Memory()
    uid = f"as_{scenario.get('id', 'x')}_{int(time.time())}"

    # Ingest seed sessions.
    for s in scenario.get("sessions", []):
        text = _build_session_text(s)
        try:
            m.add([{"role": "user", "content": text}], user_id=uid)
        except Exception:
            pass

    # Trigger message — same as the original Active Service experiment.
    user_message = scenario.get("trigger_session", {}).get(
        "user_message", "Hey! Just checking in. Anything I should know about?"
    )
    # Active Service tests *proactive* alerts, not retrieval, so we surface
    # the system's full memory rather than top-k results. This matches how
    # the existing flat-fact baseline gives the LLM the full fact list.
    try:
        all_mems = m.get_all(user_id=uid)
    except Exception:
        all_mems = []
    if isinstance(all_mems, dict) and "results" in all_mems:
        mems = all_mems["results"]
    elif isinstance(all_mems, list):
        mems = all_mems
    else:
        mems = []
    memory_text = "\n".join(
        f"{i+1}. {m_.get('memory', str(m_))}" if isinstance(m_, dict) else f"{i+1}. {m_}"
        for i, m_ in enumerate(mems)
    ) if mems else "(no memories retrieved)"

    # Build the flat-fact-style prompt with retrieved memories.
    system = SYSTEM_PROMPT_FLAT.format(memory=memory_text)
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=user_message,
            config=genai.types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.3,
                max_output_tokens=1024,
            ),
        )
        response_text = resp.text
    except Exception as e:
        response_text = f"ERROR: {e}"

    # Score using the same alert-detection rules as the original experiment.
    expected = scenario.get("expected_alert", {})
    msg = expected.get("message", "")
    expected_keywords = []
    for term in re.findall(r"\b\w{4,}\b", msg):
        if term.lower() not in {"that", "this", "with", "from", "your", "have", "been",
                                 "will", "should", "could", "would", "there", "their",
                                 "than", "more", "only", "days", "before", "after"}:
            expected_keywords.append(term.lower())
    response_lower = response_text.lower()
    keyword_hits = sum(1 for kw in expected_keywords if kw in response_lower)
    keyword_score = keyword_hits / max(len(expected_keywords), 1)
    alert_phrases = ["alert", "warning", "caution", "important", "notice",
                     "heads up", "concern", "issue", "problem", "conflict",
                     "expires", "expiring", "expired", "contraindicated",
                     "interaction", "conflicting", "deadline", "urgent",
                     "remind", "flag", "attention"]
    has_alert = any(p in response_lower for p in alert_phrases)
    detected = keyword_score > 0.15 and has_alert

    try:
        m.delete_all(user_id=uid)
    except Exception:
        pass

    return {
        "scenario_id": scenario.get("id", "unknown"),
        "category": scenario.get("category", "unknown"),
        "representation": "mem0_lib",
        "response": response_text,
        "keyword_score": round(keyword_score, 3),
        "has_alert_language": has_alert,
        "proactive_alert_detected": detected,
        "n_retrieved": len(mems),
    }


def main() -> None:
    out_path = RESULTS_DIR / "active_service_mem0lib.json"
    if out_path.exists():
        results = json.load(open(out_path))
    else:
        results = {"by_scenario": {}}

    for fname, label in [("active_service_scenarios.json", "standard"),
                         ("hard_active_service_scenarios.json", "hard")]:
        scenarios = load_scenarios(EVAL_DIR / fname)
        results.setdefault(label, {"by_scenario": {}})
        for i, sc in enumerate(scenarios):
            sid = sc.get("id", f"{label}_{i}")
            if sid in results[label]["by_scenario"]:
                continue
            print(f"[{label} {i+1}/{len(scenarios)}] {sid} ...", flush=True)
            r = run_one(sc)
            results[label]["by_scenario"][sid] = r
            with open(out_path, "w") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"  detected={r['proactive_alert_detected']}  retrieved={r['n_retrieved']}")

    # Aggregate.
    for label in ("standard", "hard"):
        if label not in results:
            continue
        det = sum(1 for v in results[label]["by_scenario"].values()
                  if v.get("proactive_alert_detected"))
        n = len(results[label]["by_scenario"])
        results[label]["alert_rate"] = det / max(n, 1)
        results[label]["n"] = n
        print(f"{label}: {det}/{n} = {det/max(n,1):.3f}")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)


if __name__ == "__main__":
    main()
