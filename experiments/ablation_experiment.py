"""
Ablation Experiment: Code vs JSON vs Markdown format

Tests the format effect on proactive alerting, holding the pipeline constant.
Two sub-experiments:
1. With pre-computed alerts (read path) — does format affect alert surfacing?
2. Without alerts, prompted to check (ad-hoc generation) — does format affect
   the LLM's ability to generate and reason about constraints?
"""

import json
import re
import time
from pathlib import Path
from datetime import datetime

from google import genai

MODEL = "gemini-3-flash-preview"
client = genai.Client()

EVAL_DIR = Path(__file__).parent.parent / "evaluation"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def load_scenarios(max_n=None):
    with open(EVAL_DIR / "active_service_scenarios.json") as f:
        data = json.load(f)
    scenarios = data if isinstance(data, list) else data.get("scenarios", [])
    return scenarios[:max_n] if max_n else scenarios


def extract_facts(scenario):
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


def build_python_repr(facts, alert_msg=None):
    """Build Python dataclass-style representation."""
    lines = ["# === User State (Python) ===", "from dataclasses import dataclass", "from datetime import date", ""]
    for fact in facts:
        varname = re.sub(r'[^a-z0-9]', '_', fact[:40].lower()).strip('_')[:30]
        lines.append(f"# User said: {fact}")
        # Try to extract dates and numbers for typed representation
        date_match = re.search(r'(\w+ \d{1,2},?\s*\d{4})', fact)
        if date_match:
            lines.append(f"# date_value = \"{date_match.group(1)}\"")
        lines.append("")
    if alert_msg:
        lines.append(f'ACTIVE_ALERTS = ["{alert_msg}"]')
    else:
        lines.append("ACTIVE_ALERTS = []")
    return "\n".join(lines)


def build_json_repr(facts, alert_msg=None):
    """Build JSON representation of the same facts."""
    entries = []
    for fact in facts:
        entry = {"fact": fact}
        date_match = re.search(r'(\w+ \d{1,2},?\s*\d{4})', fact)
        if date_match:
            entry["date"] = date_match.group(1)
        entries.append(entry)
    obj = {
        "user_facts": entries,
        "active_alerts": [alert_msg] if alert_msg else []
    }
    return json.dumps(obj, indent=2)


def build_markdown_repr(facts, alert_msg=None):
    """Build Markdown representation of the same facts."""
    lines = ["# User Profile", ""]
    for fact in facts:
        lines.append(f"- {fact}")
    lines.append("")
    if alert_msg:
        lines.append(f"## Active Alerts")
        lines.append(f"- **CRITICAL**: {alert_msg}")
    else:
        lines.append("## Active Alerts")
        lines.append("- None")
    return "\n".join(lines)


SYSTEM_TEMPLATE = """You are the user's personal AI assistant. Their information is stored below.

{memory}

Respond naturally to the user's message."""

SYSTEM_TEMPLATE_CHECK = """You are the user's personal AI assistant. Their information is stored below.

{memory}

IMPORTANT: Before responding, carefully review ALL the user's stored information. Check for any conflicts, safety issues, expiring deadlines, or cross-domain problems. If you find any issues, alert the user immediately with specific details and numbers.

Respond to the user's message."""


def evaluate_response(response_text, scenario):
    expected = scenario.get("expected_alert", {})
    expected_msg = expected.get("message", "")
    text_lower = response_text.lower()

    key_terms = set()
    for word in re.findall(r'\b[a-z]{4,}\b', expected_msg.lower()):
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

    comp = expected.get("computation", "")
    comp_nums = re.findall(r'\d+', comp)
    num_hits = sum(1 for n in comp_nums if n in response_text) if comp_nums else 0
    has_computation = num_hits >= 2

    return {
        "keyword_score": round(kw_score, 3),
        "has_alert": has_alert,
        "has_computation": has_computation,
        "proactive": kw_score >= 0.2 and has_alert,
    }


def run_one(scenario, fmt, with_alerts, with_check_prompt):
    facts = extract_facts(scenario)
    alert_msg = scenario.get("expected_alert", {}).get("message", "Alert")

    if fmt == "python":
        memory = build_python_repr(facts, alert_msg if with_alerts else None)
    elif fmt == "json":
        memory = build_json_repr(facts, alert_msg if with_alerts else None)
    else:
        memory = build_markdown_repr(facts, alert_msg if with_alerts else None)

    template = SYSTEM_TEMPLATE_CHECK if with_check_prompt else SYSTEM_TEMPLATE
    system = template.format(memory=memory)

    user_msg = scenario.get("trigger_session", {}).get(
        "user_message", "Hey, just checking in! How's everything?"
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
        # Count tokens approximately
        prompt_tokens = len(system.split()) + len(user_msg.split())
        response_tokens = len(text.split())
    except Exception as e:
        text = f"ERROR: {e}"
        prompt_tokens = 0
        response_tokens = 0

    scores = evaluate_response(text, scenario)
    return {
        "scenario_id": scenario.get("id", "?"),
        "category": scenario.get("category", "?"),
        "format": fmt,
        "with_alerts": with_alerts,
        "with_check_prompt": with_check_prompt,
        "prompt_tokens": prompt_tokens,
        "response_tokens": response_tokens,
        **scores,
    }


def main(max_n=None):
    scenarios = load_scenarios(max_n)
    formats = ["python", "json", "markdown"]

    print(f"\n{'='*70}")
    print(f"  Ablation: Code vs JSON vs Markdown")
    print(f"  Model: {MODEL}, Scenarios: {len(scenarios)}")
    print(f"{'='*70}")

    all_results = []

    # Sub-experiment 1: With pre-computed alerts (read path)
    print(f"\n  --- SUB-EXPERIMENT 1: With pre-computed alerts ---\n")
    for i, scenario in enumerate(scenarios):
        sid = scenario.get("id", f"s{i}")
        print(f"  [{i+1}/{len(scenarios)}] {sid}", end="", flush=True)
        for fmt in formats:
            r = run_one(scenario, fmt, with_alerts=True, with_check_prompt=False)
            all_results.append(r)
            tag = "+" if r["proactive"] else "-"
            print(f"  {fmt[0]}:{tag}", end="", flush=True)
            time.sleep(0.3)
        print()

    # Sub-experiment 2: Without alerts, prompted to check (ad-hoc generation)
    print(f"\n  --- SUB-EXPERIMENT 2: No alerts, prompted to check ---\n")
    for i, scenario in enumerate(scenarios):
        sid = scenario.get("id", f"s{i}")
        print(f"  [{i+1}/{len(scenarios)}] {sid}", end="", flush=True)
        for fmt in formats:
            r = run_one(scenario, fmt, with_alerts=False, with_check_prompt=True)
            all_results.append(r)
            tag = "+" if r["proactive"] else "-"
            print(f"  {fmt[0]}:{tag}", end="", flush=True)
            time.sleep(0.3)
        print()

    # Summary
    print(f"\n{'='*70}")
    print(f"  RESULTS")
    print(f"{'='*70}")

    for sub in [True, False]:
        label = "WITH alerts (read path)" if sub else "NO alerts, prompted (ad-hoc)"
        print(f"\n  {label}")
        print(f"  {'Format':<12} {'Alert Rate':>12} {'Avg KW':>10} {'Computation':>12}")
        print(f"  {'-'*48}")
        for fmt in formats:
            subset = [r for r in all_results if r["format"] == fmt and r["with_alerts"] == sub]
            detected = sum(1 for r in subset if r["proactive"])
            total = len(subset)
            avg_kw = sum(r["keyword_score"] for r in subset) / max(total, 1)
            comp = sum(1 for r in subset if r["has_computation"]) / max(total, 1)
            print(f"  {fmt:<12} {detected:>5}/{total:<5} {avg_kw:>10.3f} {comp:>12.1%}")

    # Token analysis
    print(f"\n  TOKEN USAGE (avg per query)")
    print(f"  {'Format':<12} {'Prompt':>10} {'Response':>10} {'Total':>10}")
    print(f"  {'-'*44}")
    for fmt in formats:
        subset = [r for r in all_results if r["format"] == fmt and r["with_alerts"]]
        avg_p = sum(r["prompt_tokens"] for r in subset) / max(len(subset), 1)
        avg_r = sum(r["response_tokens"] for r in subset) / max(len(subset), 1)
        print(f"  {fmt:<12} {avg_p:>10.0f} {avg_r:>10.0f} {avg_p+avg_r:>10.0f}")

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RESULTS_DIR / f"ablation_{timestamp}.json"
    with open(out, "w") as f:
        json.dump({"results": all_results, "model": MODEL}, f, indent=2)
    print(f"\n  Saved to: {out}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", type=int, default=None)
    args = parser.parse_args()
    main(max_n=args.n)
