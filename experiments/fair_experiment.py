"""
Fair Active Service Experiment

Key insight from POC: when we explicitly tell the LLM "check for issues",
both code and flat representations score well because the LLM is smart enough
to reason over any presented facts.

The REAL test of Active Service is: does the representation ITSELF trigger
proactive checking without being told to? This tests the "initiation asymmetry"
— who/what triggers the alert.

Protocol:
1. Code condition: Agent sees Python code with schema+state. The manifest
   includes ACTIVE_ALERTS (pre-computed by constraint execution). The system
   prompt says "you are a helpful assistant" — NO instruction to check for issues.
   The code representation naturally surfaces alerts via the manifest.

2. Code-no-manifest condition: Same as Code but without ACTIVE_ALERTS in manifest.
   Tests whether the LLM can generate and mentally execute constraints from
   the code representation alone.

3. Flat condition: Agent sees a flat fact list. System prompt says "you are a
   helpful assistant" — same as code condition. No instruction to check.
   Tests whether flat facts trigger proactive alerting.

4. None condition: No memory at all. Control.

This isolates the representation effect: same LLM, same prompt framing,
different memory format.
"""

import json
import sys
import time
import re
from pathlib import Path
from datetime import datetime

from google import genai

MODEL = "gemini-3-flash-preview"
client = genai.Client()

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Build representations for each scenario
# ---------------------------------------------------------------------------

def build_code_with_alerts(scenario: dict) -> str:
    """Build code representation WITH pre-computed constraint alerts."""
    facts = extract_all_facts(scenario)
    alert = scenario.get("expected_alert", {})

    code = f"""# === manifest.py ===
\"\"\"User Project | Updated: {datetime.now().strftime('%Y-%m-%d')}\"\"\"

DOMAINS = {{
    "personal": "Core profile and identity",
{build_domain_summary(facts)}
}}

ACTIVE_ALERTS = [
    "[CRITICAL] {alert.get('type', 'constraint')}: {alert.get('message', 'Alert detected')}",
]

# === Relevant domain state (Python) ===
{build_python_state(facts)}
"""
    return code


def build_code_no_alerts(scenario: dict) -> str:
    """Build code representation WITHOUT pre-computed alerts."""
    facts = extract_all_facts(scenario)

    code = f"""# === manifest.py ===
\"\"\"User Project | Updated: {datetime.now().strftime('%Y-%m-%d')}\"\"\"

DOMAINS = {{
    "personal": "Core profile and identity",
{build_domain_summary(facts)}
}}

ACTIVE_ALERTS = []  # No pre-computed alerts

# === Relevant domain state (Python) ===
{build_python_state(facts)}
"""
    return code


def build_flat_facts(scenario: dict) -> str:
    """Build Mem0-style flat fact list."""
    facts = extract_all_facts(scenario)
    lines = ["# User Memory (facts from previous conversations):"]
    for i, fact in enumerate(facts, 1):
        lines.append(f"{i}. {fact}")
    return "\n".join(lines)


def extract_all_facts(scenario: dict) -> list[str]:
    """Extract key facts from scenario sessions."""
    facts = []
    for session in scenario.get("sessions", []):
        conv = session.get("conversation", "")
        for line in conv.split("\n"):
            line = line.strip()
            if line.startswith("User:"):
                content = line[5:].strip()
                if len(content) > 15:
                    facts.append(content)
    return facts


def build_domain_summary(facts: list[str]) -> str:
    """Generate domain summary entries from facts."""
    domains = set()
    for fact in facts:
        fl = fact.lower()
        if any(w in fl for w in ["passport", "flight", "trip", "visa", "travel"]):
            domains.add('    "travel": "Trip and passport information"')
        if any(w in fl for w in ["allergy", "medication", "doctor", "prescription", "drug"]):
            domains.add('    "health": "Medical info, allergies, medications"')
        if any(w in fl for w in ["bank", "transfer", "payment", "account", "money"]):
            domains.add('    "finance": "Accounts and transfers"')
        if any(w in fl for w in ["meeting", "calendar", "schedule", "appointment"]):
            domains.add('    "schedule": "Calendar and appointments"')
        if any(w in fl for w in ["warranty", "expire", "subscription", "license", "renew", "lease", "deadline"]):
            domains.add('    "deadlines": "Warranties, renewals, deadlines"')
    return ",\n".join(sorted(domains)) if domains else '    "general": "General information"'


def build_python_state(facts: list[str]) -> str:
    """Convert facts to Python-like state declarations."""
    lines = []
    for fact in facts:
        # Try to extract structured info
        varname = re.sub(r'[^a-z0-9_]', '_', fact[:30].lower()).strip('_')
        lines.append(f'# {fact}')
        # Look for dates
        date_match = re.search(r'(\w+ \d{1,2},?\s*\d{4})', fact)
        if date_match:
            lines.append(f'# date: {date_match.group(1)}')
        lines.append('')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM evaluation
# ---------------------------------------------------------------------------

NEUTRAL_SYSTEM = """You are {name}'s personal AI assistant. You have access to their stored information shown below.

{memory}

Respond naturally to the user's message."""

NO_MEMORY_SYSTEM = """You are a helpful personal AI assistant. Respond naturally to the user's message."""


def run_one(scenario: dict, condition: str) -> dict:
    """Run one scenario under one condition."""

    # Extract a plausible user name from conversation
    name = "the user"
    for s in scenario.get("sessions", []):
        conv = s.get("conversation", "")
        if "name is" in conv.lower():
            match = re.search(r"name is (\w+)", conv, re.IGNORECASE)
            if match:
                name = match.group(1)
                break

    if condition == "code_with_alerts":
        memory = build_code_with_alerts(scenario)
        system = NEUTRAL_SYSTEM.format(name=name, memory=memory)
    elif condition == "code_no_alerts":
        memory = build_code_no_alerts(scenario)
        system = NEUTRAL_SYSTEM.format(name=name, memory=memory)
    elif condition == "flat":
        memory = build_flat_facts(scenario)
        system = NEUTRAL_SYSTEM.format(name=name, memory=memory)
    else:
        system = NO_MEMORY_SYSTEM

    user_msg = scenario.get("trigger_session", {}).get(
        "user_message",
        "Hey, just checking in! How's everything looking?"
    )

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=user_msg,
            config=genai.types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.2,
                max_output_tokens=1500,
            ),
        )
        text = response.text
    except Exception as e:
        text = f"ERROR: {e}"

    # Score: does the response contain alert-relevant content?
    expected = scenario.get("expected_alert", {})
    expected_msg = expected.get("message", "")

    text_lower = text.lower()

    # Extract key terms from expected alert
    key_terms = set()
    for word in re.findall(r'\b[a-z]{4,}\b', expected_msg.lower()):
        if word not in {"that", "this", "with", "from", "your", "have", "been",
                        "will", "should", "could", "would", "there", "their",
                        "than", "more", "only", "days", "before", "after",
                        "need", "need", "least", "require", "requires"}:
            key_terms.add(word)

    hits = [t for t in key_terms if t in text_lower]
    keyword_score = len(hits) / max(len(key_terms), 1)

    # Check for alert language
    alert_words = ["alert", "warning", "caution", "important", "urgent",
                   "heads up", "concern", "issue", "problem", "conflict",
                   "expires", "expiring", "expired", "contraindicated",
                   "interaction", "conflicting", "deadline", "attention",
                   "critical", "risk", "danger", "notice", "careful"]
    has_alert_lang = any(w in text_lower for w in alert_words)

    # Check for specific numbers from computation
    computation = expected.get("computation", "")
    comp_numbers = re.findall(r'\d+', computation)
    number_hits = sum(1 for n in comp_numbers if n in text) if comp_numbers else 0
    has_numbers = number_hits >= 2

    proactive = keyword_score >= 0.2 and has_alert_lang

    return {
        "scenario_id": scenario.get("id", "?"),
        "category": scenario.get("category", "?"),
        "condition": condition,
        "user_message": user_msg,
        "response": text[:500],
        "keyword_score": round(keyword_score, 3),
        "has_alert_language": has_alert_lang,
        "has_computation": has_numbers,
        "proactive_alert": proactive,
        "keyword_hits": hits[:5],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(max_n: int | None = None):
    # Load scenarios
    eval_path = Path(__file__).parent.parent / "evaluation" / "active_service_scenarios.json"
    with open(eval_path) as f:
        data = json.load(f)
    scenarios = data if isinstance(data, list) else data.get("scenarios", [])

    if max_n:
        scenarios = scenarios[:max_n]

    conditions = ["code_with_alerts", "code_no_alerts", "flat", "none"]

    print(f"\n{'='*70}")
    print(f"  Fair Active Service Experiment")
    print(f"  Model: {MODEL}")
    print(f"  Scenarios: {len(scenarios)}, Conditions: {len(conditions)}")
    print(f"  Total runs: {len(scenarios) * len(conditions)}")
    print(f"{'='*70}\n")

    results = []

    for i, scenario in enumerate(scenarios):
        sid = scenario.get("id", f"s{i}")
        cat = scenario.get("category", "?")
        desc = scenario.get("description", "")[:50]
        print(f"  [{i+1}/{len(scenarios)}] {sid}: {desc}")

        for cond in conditions:
            r = run_one(scenario, cond)
            results.append(r)

            tag = "ALERT" if r["proactive_alert"] else "miss "
            print(f"    {cond:<20} [{tag}] kw={r['keyword_score']:.2f} "
                  f"alert={r['has_alert_language']} nums={r['has_computation']}")
            time.sleep(0.5)

        print()

    # Summary
    print(f"\n{'='*70}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*70}")

    print(f"\n  {'Condition':<22} {'Alert Rate':>12} {'Avg KW':>10} {'Compute':>10}")
    print(f"  {'-'*55}")
    for cond in conditions:
        cond_results = [r for r in results if r["condition"] == cond]
        alert_count = sum(1 for r in cond_results if r["proactive_alert"])
        total = len(cond_results)
        avg_kw = sum(r["keyword_score"] for r in cond_results) / max(total, 1)
        comp_rate = sum(1 for r in cond_results if r["has_computation"]) / max(total, 1)
        print(f"  {cond:<22} {alert_count:>5}/{total:<5} {avg_kw:>10.3f} {comp_rate:>10.1%}")

    print(f"\n  BY CATEGORY")
    print(f"  {'Category':<35}", end="")
    for cond in conditions:
        print(f" {cond[:8]:>10}", end="")
    print()
    print(f"  {'-'*75}")

    for cat in sorted(set(r["category"] for r in results)):
        print(f"  {cat:<35}", end="")
        for cond in conditions:
            cat_cond = [r for r in results if r["category"] == cat and r["condition"] == cond]
            alerts = sum(1 for r in cat_cond if r["proactive_alert"])
            total = len(cat_cond)
            print(f" {alerts:>4}/{total:<4} ", end="")
        print()

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"fair_experiment_{timestamp}.json"
    summary = {
        "model": MODEL,
        "timestamp": datetime.now().isoformat(),
        "n_scenarios": len(scenarios),
        "conditions": conditions,
        "results": results,
    }
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n  Saved to: {out_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", type=int, default=None, help="Max scenarios")
    args = parser.parse_args()
    main(max_n=args.n)
