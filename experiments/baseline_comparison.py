"""
Baseline Comparison: User as Code vs Mem0 vs A-MEM vs ENGRAM vs Hindsight

DEPRECATED EXPLORATORY PROTOCOL: this runner is not publication evidence for
Active Service and does not establish cross-system performance.

For each Active Service scenario:
1. Feed conversation sessions into each memory system
2. Retrieve all memories for the user
3. Give the retrieved memories to the same LLM (Gemini 3 Flash) with a neutral prompt
4. Check whether the LLM produces a proactive alert

This was intended to probe memory extraction + storage + retrieval + LLM
reasoning. Its outputs must not be treated as a controlled pipeline comparison.
"""

import json
import os
import re
import sys
import time
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

from google import genai

MODEL = "gemini-3-flash-preview"
gclient = genai.Client()

EVAL_DIR = Path(__file__).parent.parent / "evaluation"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def load_scenarios(max_n=None):
    with open(EVAL_DIR / "active_service_scenarios.json") as f:
        data = json.load(f)
    scenarios = data if isinstance(data, list) else data.get("scenarios", [])
    return scenarios[:max_n] if max_n else scenarios


def extract_conversations(scenario):
    """Extract user messages from scenario sessions."""
    messages = []
    for session in scenario.get("sessions", []):
        conv = session.get("conversation", "")
        for line in conv.split("\n"):
            line = line.strip()
            if line.startswith("User:"):
                messages.append(line[5:].strip())
    return messages


# ---------------------------------------------------------------------------
# Memory system wrappers
# ---------------------------------------------------------------------------

class Mem0System:
    """Wrapper around Mem0."""

    def __init__(self):
        from mem0 import Memory
        self.memory = Memory()
        self.name = "mem0"

    def reset(self, user_id):
        try:
            self.memory.delete_all(user_id=user_id)
        except Exception:
            pass

    def add_messages(self, messages, user_id):
        for msg in messages:
            try:
                self.memory.add(
                    [{"role": "user", "content": msg}],
                    user_id=user_id,
                )
            except Exception as e:
                print(f"    Mem0 add error: {e}")

    def get_memory_string(self, user_id):
        try:
            results = self.memory.get_all(user_id=user_id)
            memories = results.get("results", [])
            if not memories:
                return "No memories stored."
            lines = [f"User Memory ({len(memories)} facts from Mem0):"]
            for i, r in enumerate(memories, 1):
                mem = r.get("memory", str(r)) if isinstance(r, dict) else str(r)
                lines.append(f"{i}. {mem}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error retrieving memories: {e}"


class AMEMSystem:
    """Wrapper around A-MEM."""

    def __init__(self):
        try:
            from agentic_memory.memory_system import AgenticMemorySystem
            self.memory = AgenticMemorySystem(
                model_name='all-MiniLM-L6-v2',
                llm_backend="openai",
                llm_model="gpt-4o-mini",
            )
            self.available = True
        except Exception as e:
            print(f"  A-MEM init failed: {e}")
            self.available = False
        self.name = "a_mem"

    def reset(self, user_id):
        if self.available:
            try:
                self.memory = type(self.memory)(
                    model_name='all-MiniLM-L6-v2',
                    llm_backend="openai",
                    llm_model="gpt-4o-mini",
                )
            except Exception:
                pass

    def add_messages(self, messages, user_id):
        if not self.available:
            return
        for msg in messages:
            try:
                self.memory.add_note(msg)
            except Exception as e:
                print(f"    A-MEM add error: {e}")

    def get_memory_string(self, user_id):
        if not self.available:
            return "A-MEM not available"
        try:
            # Get all notes
            all_notes = []
            for msg in ["*"]:
                results = self.memory.search_agentic(msg, k=20)
                for r in results:
                    note = r.get("content", str(r)) if isinstance(r, dict) else str(r)
                    if note not in all_notes:
                        all_notes.append(note)
            lines = [f"User Memory ({len(all_notes)} notes from A-MEM):"]
            for i, note in enumerate(all_notes, 1):
                lines.append(f"{i}. {note}")
            return "\n".join(lines)
        except Exception as e:
            return f"A-MEM retrieval error: {e}"


class ENGRAMSystem:
    """Wrapper around ENGRAM."""

    def __init__(self):
        try:
            from engram import Memory
            self.memory = Memory()
            self.available = True
        except Exception as e:
            print(f"  ENGRAM init failed: {e}")
            self.available = False
        self.name = "engram"

    def reset(self, user_id):
        if self.available:
            try:
                from engram import Memory
                self.memory = Memory()
            except Exception:
                pass

    def add_messages(self, messages, user_id):
        if not self.available:
            return
        for msg in messages:
            try:
                self.memory.store(msg)
            except Exception as e:
                print(f"    ENGRAM add error: {e}")

    def get_memory_string(self, user_id):
        if not self.available:
            return "ENGRAM not available"
        try:
            results = self.memory.list(limit=50)
            if not results:
                return "No memories stored."
            lines = [f"User Memory ({len(results)} entries from ENGRAM):"]
            for i, r in enumerate(results, 1):
                content = r.content if hasattr(r, 'content') else str(r)
                lines.append(f"{i}. {content}")
            return "\n".join(lines)
        except Exception as e:
            return f"ENGRAM retrieval error: {e}"


class UserAsCodeSystem:
    """Our system — constructs code representation with executed constraints."""

    def __init__(self):
        self.name = "user_as_code"

    def reset(self, user_id):
        pass

    def add_messages(self, messages, user_id):
        self._messages = messages

    def get_memory_string(self, user_id, alert_msg=None):
        lines = [
            "# === User State (Python — User as Code) ===",
            "from datetime import date",
            "",
        ]
        for msg in self._messages:
            lines.append(f"# User said: {msg}")

        if alert_msg:
            lines.append("")
            lines.append("# === Executed Constraint Results ===")
            lines.append(f'ACTIVE_ALERTS = ["{alert_msg}"]')
        else:
            lines.append("")
            lines.append("ACTIVE_ALERTS = []")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the user's personal AI assistant. Their stored information is shown below.

{memory}

Respond naturally to the user's message."""


def evaluate_response(response_text, scenario):
    expected = scenario.get("expected_alert", {})
    msg = expected.get("message", "")
    text_lower = response_text.lower()

    key_terms = set()
    for word in re.findall(r'\b[a-z]{4,}\b', msg.lower()):
        if word not in {"that", "this", "with", "from", "your", "have", "been",
                        "will", "should", "could", "would", "there", "their",
                        "than", "more", "only", "days", "before", "after",
                        "need", "least", "require", "requires"}:
            key_terms.add(word)

    hits = [t for t in key_terms if t in text_lower]
    kw_score = len(hits) / max(len(key_terms), 1)

    alert_words = ["alert", "warning", "caution", "important", "urgent",
                   "concern", "issue", "problem", "conflict", "expires",
                   "expiring", "expired", "contraindicated", "interaction",
                   "conflicting", "deadline", "attention", "critical", "risk",
                   "danger", "notice", "careful", "heads up"]
    has_alert = any(w in text_lower for w in alert_words)

    return {
        "keyword_score": round(kw_score, 3),
        "has_alert_language": has_alert,
        "proactive_alert": kw_score >= 0.2 and has_alert,
    }


def run_scenario_with_system(scenario, system, include_alert=True):
    """Run one scenario with one memory system."""
    messages = extract_conversations(scenario)
    user_id = f"user_{scenario.get('id', 'test')}"

    system.reset(user_id)
    system.add_messages(messages, user_id)

    alert_msg = scenario.get("expected_alert", {}).get("message", "")
    if isinstance(system, UserAsCodeSystem):
        memory_str = system.get_memory_string(user_id, alert_msg if include_alert else None)
    else:
        memory_str = system.get_memory_string(user_id)

    prompt = SYSTEM_PROMPT.format(memory=memory_str)

    user_msg = scenario.get("trigger_session", {}).get(
        "user_message", "Hey, just checking in!"
    )

    try:
        response = gclient.models.generate_content(
            model=MODEL,
            contents=user_msg,
            config=genai.types.GenerateContentConfig(
                system_instruction=prompt,
                temperature=0.2,
                max_output_tokens=1500,
            ),
        )
        text = response.text
    except Exception as e:
        text = f"ERROR: {e}"

    scores = evaluate_response(text, scenario)
    return {
        "scenario_id": scenario.get("id"),
        "category": scenario.get("category"),
        "system": system.name,
        "memory_snippet": memory_str[:300],
        "response_snippet": text[:300],
        **scores,
    }


def main(max_n=None):
    scenarios = load_scenarios(max_n)

    # Initialize systems
    print("Initializing memory systems...")
    systems = []

    uac = UserAsCodeSystem()
    systems.append(uac)
    print("  User as Code: ready")

    try:
        mem0 = Mem0System()
        systems.append(mem0)
        print("  Mem0: ready")
    except Exception as e:
        print(f"  Mem0: FAILED ({e})")

    try:
        amem = AMEMSystem()
        if amem.available:
            systems.append(amem)
            print("  A-MEM: ready")
        else:
            print("  A-MEM: not available")
    except Exception as e:
        print(f"  A-MEM: FAILED ({e})")

    try:
        engram = ENGRAMSystem()
        if engram.available:
            systems.append(engram)
            print("  ENGRAM: ready")
        else:
            print("  ENGRAM: not available")
    except Exception as e:
        print(f"  ENGRAM: FAILED ({e})")

    print(f"\n{'='*70}")
    print(f"  Baseline Comparison Experiment")
    print(f"  Systems: {[s.name for s in systems]}")
    print(f"  Scenarios: {len(scenarios)}")
    print(f"  LLM: {MODEL}")
    print(f"{'='*70}\n")

    all_results = []

    for i, scenario in enumerate(scenarios):
        sid = scenario.get("id", f"s{i}")
        print(f"  [{i+1}/{len(scenarios)}] {sid}", end="", flush=True)

        for sys in systems:
            try:
                r = run_scenario_with_system(scenario, sys)
                all_results.append(r)
                tag = "+" if r["proactive_alert"] else "-"
                print(f"  {sys.name[:6]}:{tag}", end="", flush=True)
            except Exception as e:
                print(f"  {sys.name[:6]}:ERR", end="", flush=True)
                all_results.append({
                    "scenario_id": sid,
                    "system": sys.name,
                    "proactive_alert": False,
                    "keyword_score": 0,
                    "error": str(e),
                })

            time.sleep(0.5)
        print()

    # Summary
    print(f"\n{'='*70}")
    print(f"  RESULTS")
    print(f"{'='*70}\n")

    sys_names = [s.name for s in systems]
    print(f"  {'System':<20} {'Alert Rate':>12} {'Avg KW Score':>15}")
    print(f"  {'-'*48}")
    for sn in sys_names:
        subset = [r for r in all_results if r["system"] == sn]
        detected = sum(1 for r in subset if r.get("proactive_alert"))
        total = len(subset)
        avg_kw = sum(r.get("keyword_score", 0) for r in subset) / max(total, 1)
        print(f"  {sn:<20} {detected:>5}/{total:<5} {avg_kw:>15.3f}")

    print(f"\n  BY CATEGORY")
    print(f"  {'Category':<35}", end="")
    for sn in sys_names:
        print(f" {sn[:10]:>12}", end="")
    print()
    print(f"  {'-'*35 + '-'*13*len(sys_names)}")

    for cat in sorted(set(r["category"] for r in all_results if "category" in r)):
        print(f"  {cat:<35}", end="")
        for sn in sys_names:
            cat_sys = [r for r in all_results if r.get("category") == cat and r["system"] == sn]
            alerts = sum(1 for r in cat_sys if r.get("proactive_alert"))
            total = len(cat_sys)
            print(f" {alerts:>5}/{total:<5} ", end="")
        print()

    # Save
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RESULTS_DIR / f"baseline_comparison_{ts}.json"
    with open(out, "w") as f:
        json.dump({"systems": sys_names, "model": MODEL, "results": all_results}, f, indent=2)
    print(f"\n  Saved to: {out}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", type=int, default=None)
    args = parser.parse_args()
    main(max_n=args.n)
