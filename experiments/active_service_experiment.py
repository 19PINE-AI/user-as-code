"""
Active Service Experiment: User as Code vs. Flat-Fact Baseline

Compares two memory representations on proactive alerting:
1. User as Code: Python dataclasses + executable constraints
2. Flat Facts: Mem0-style atomic fact list (no structure, no execution)

For each scenario, we seed both representations with the same user information,
then ask the LLM to act as a personal assistant starting a new conversation.
The LLM is NOT asked about the constraint — we measure whether it proactively
surfaces an alert.

Uses Gemini 3 Flash (gemini-3-flash-preview) as the LLM backbone.
"""

import json
import os
import sys
import time
import re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime

from google import genai

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODEL = "gemini-3-flash-preview"
client = genai.Client()

EVAL_DIR = Path(__file__).parent.parent / "evaluation"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Scenario loader
# ---------------------------------------------------------------------------
def load_scenarios(path: Path | None = None) -> list[dict]:
    """Load evaluation scenarios from JSON."""
    if path is None:
        path = EVAL_DIR / "active_service_scenarios.json"
    with open(path) as f:
        data = json.load(f)
    # Handle both raw list and {"scenarios": [...]} wrapper
    if isinstance(data, list):
        return data
    return data.get("scenarios", data.get("test_cases", []))


# ---------------------------------------------------------------------------
# Memory representations
# ---------------------------------------------------------------------------

def build_code_representation(scenario: dict) -> str:
    """Build a User-as-Code Python representation from scenario facts."""
    facts = extract_facts(scenario)

    code_lines = [
        "# === User Project: Auto-generated from conversation ===",
        "from dataclasses import dataclass",
        "from datetime import date",
        "from typing import Optional",
        "",
    ]

    # Group facts by domain
    domains: dict[str, list[str]] = {}
    for fact in facts:
        domain = classify_domain(fact)
        domains.setdefault(domain, []).append(fact)

    for domain, domain_facts in domains.items():
        code_lines.append(f"# --- Domain: {domain} ---")
        for fact in domain_facts:
            code_lines.append(f"# Fact: {fact}")
            code_lines.append(fact_to_python(fact, domain))
        code_lines.append("")

    code_lines.append("# --- Constraints (agent should generate and execute) ---")
    code_lines.append("# The agent can write Python checks against the above state")
    code_lines.append("# and execute them to detect cross-domain issues.")

    return "\n".join(code_lines)


def build_flat_fact_representation(scenario: dict) -> str:
    """Build a Mem0-style flat fact list from scenario."""
    facts = extract_facts(scenario)
    lines = ["# User Memory (flat facts extracted from conversations):"]
    for i, fact in enumerate(facts, 1):
        lines.append(f"{i}. {fact}")
    return "\n".join(lines)


def extract_facts(scenario: dict) -> list[str]:
    """Extract factual statements from scenario conversations."""
    facts = []
    for session in scenario.get("sessions", []):
        conv = session.get("conversation", "")
        # Extract user statements (lines starting with "User:")
        for line in conv.split("\n"):
            line = line.strip()
            if line.startswith("User:"):
                content = line[5:].strip()
                # Skip greetings and meta-talk
                if len(content) > 20 and not content.lower().startswith(("hi", "hey", "hello", "thanks", "ok", "sure")):
                    facts.append(content)
    return facts


def classify_domain(fact: str) -> str:
    """Simple keyword-based domain classification."""
    fact_lower = fact.lower()
    if any(w in fact_lower for w in ["passport", "flight", "trip", "travel", "visa", "airport", "hotel"]):
        return "travel"
    if any(w in fact_lower for w in ["allergy", "medication", "doctor", "prescription", "pill", "drug", "health", "medical"]):
        return "health"
    if any(w in fact_lower for w in ["bank", "transfer", "payment", "account", "money", "salary", "credit", "wire"]):
        return "finance"
    if any(w in fact_lower for w in ["meeting", "calendar", "schedule", "appointment", "deadline"]):
        return "schedule"
    if any(w in fact_lower for w in ["warranty", "expire", "renew", "subscription", "license"]):
        return "deadlines"
    return "general"


def fact_to_python(fact: str, domain: str) -> str:
    """Convert a natural language fact to a Python-ish variable assignment.
    This is a simplified version — in the real system the LLM does this."""
    # Extract dates using simple patterns
    date_match = re.search(r'(\w+ \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2})', fact)
    if date_match:
        date_str = date_match.group(1)
        return f'# -> date noted: "{date_str}"'
    return f'# -> noted'


# ---------------------------------------------------------------------------
# LLM evaluation
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_CODE = """You are a personal AI assistant for a user. Below is the user's memory, stored as a Python code project (User as Code). You can read the state and mentally execute checks against it.

IMPORTANT: At the start of every conversation, you should review the user's state for any cross-domain issues, conflicts, or time-sensitive concerns. If you detect any issues, proactively alert the user WITHOUT being asked.

You have the ability to reason about the code: perform date arithmetic, check constraints, and detect conflicts by mentally executing Python logic against the stored state.

{memory}

The user is starting a new conversation. Review their state and respond. If you detect any proactive alerts, mention them FIRST before addressing the user's message."""

SYSTEM_PROMPT_FLAT = """You are a personal AI assistant for a user. Below is the user's memory, stored as a list of facts from previous conversations.

IMPORTANT: At the start of every conversation, you should review the user's stored facts for any cross-domain issues, conflicts, or time-sensitive concerns. If you detect any issues, proactively alert the user WITHOUT being asked.

{memory}

The user is starting a new conversation. Review their stored facts and respond. If you detect any proactive alerts, mention them FIRST before addressing the user's message."""

SYSTEM_PROMPT_NONE = """You are a personal AI assistant. The user is starting a new conversation. Respond helpfully."""


def run_single_evaluation(
    scenario: dict,
    representation: str,  # "code", "flat", "none"
) -> dict:
    """Run a single scenario with a given memory representation."""

    if representation == "code":
        memory = build_code_representation(scenario)
        system = SYSTEM_PROMPT_CODE.format(memory=memory)
    elif representation == "flat":
        memory = build_flat_fact_representation(scenario)
        system = SYSTEM_PROMPT_FLAT.format(memory=memory)
    else:
        system = SYSTEM_PROMPT_NONE

    # The user's opening message in the trigger session — something unrelated
    # to the constraint, so the agent must proactively bring it up
    user_message = scenario.get("trigger_session", {}).get(
        "user_message",
        "Hey! Just checking in. Anything I should know about?"
    )

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=user_message,
            config=genai.types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.3,  # Low temp for more deterministic evaluation
                max_output_tokens=1024,
            ),
        )
        response_text = response.text
    except Exception as e:
        response_text = f"ERROR: {e}"

    # Evaluate whether the response contains a proactive alert
    expected = scenario.get("expected_alert", {})
    expected_keywords = []

    # Extract key terms from expected alert
    msg = expected.get("message", "")
    for term in re.findall(r'\b\w{4,}\b', msg):
        if term.lower() not in {"that", "this", "with", "from", "your", "have", "been",
                                 "will", "should", "could", "would", "there", "their",
                                 "than", "more", "only", "days", "before", "after"}:
            expected_keywords.append(term.lower())

    # Also check for key identifiers from the scenario
    alert_type = expected.get("type", "")

    # Score: how many expected keywords appear in the response
    response_lower = response_text.lower()
    keyword_hits = sum(1 for kw in expected_keywords if kw in response_lower)
    keyword_total = max(len(expected_keywords), 1)
    keyword_score = keyword_hits / keyword_total

    # Check if the response contains any alert-like language
    alert_phrases = ["alert", "warning", "caution", "important", "notice",
                     "heads up", "concern", "issue", "problem", "conflict",
                     "expires", "expiring", "expired", "contraindicated",
                     "interaction", "conflicting", "deadline", "urgent",
                     "remind", "flag", "attention"]
    has_alert_language = any(phrase in response_lower for phrase in alert_phrases)

    # Did it mention the specific constraint computation?
    computation = expected.get("computation", "")
    has_computation = False
    if computation:
        # Look for numbers from the computation
        numbers = re.findall(r'\d+', computation)
        number_hits = sum(1 for n in numbers if n in response_text)
        has_computation = number_hits >= 2  # At least 2 numbers match

    # Overall proactive alert score
    proactive_alert_detected = keyword_score > 0.15 and has_alert_language

    return {
        "scenario_id": scenario.get("id", "unknown"),
        "category": scenario.get("category", "unknown"),
        "representation": representation,
        "response": response_text,
        "keyword_score": round(keyword_score, 3),
        "has_alert_language": has_alert_language,
        "has_computation": has_computation,
        "proactive_alert_detected": proactive_alert_detected,
    }


# ---------------------------------------------------------------------------
# Main experiment runner
# ---------------------------------------------------------------------------

def run_experiment(
    scenarios: list[dict] | None = None,
    max_scenarios: int | None = None,
    representations: list[str] | None = None,
) -> dict:
    """Run the full Active Service experiment."""

    if scenarios is None:
        scenarios = load_scenarios()
    if max_scenarios:
        scenarios = scenarios[:max_scenarios]
    if representations is None:
        representations = ["code", "flat"]

    print(f"\n{'='*70}")
    print(f"  Active Service Experiment")
    print(f"  Model: {MODEL}")
    print(f"  Scenarios: {len(scenarios)}")
    print(f"  Representations: {representations}")
    print(f"{'='*70}\n")

    all_results = []
    for i, scenario in enumerate(scenarios):
        sid = scenario.get("id", f"scenario_{i}")
        cat = scenario.get("category", "unknown")
        desc = scenario.get("description", "")

        for rep in representations:
            print(f"  [{i+1}/{len(scenarios)}] {sid} ({rep}): {desc[:60]}...", flush=True)

            result = run_single_evaluation(scenario, rep)
            all_results.append(result)

            status = "ALERT" if result["proactive_alert_detected"] else "MISS "
            print(f"           -> {status}  (kw={result['keyword_score']:.2f}, "
                  f"alert_lang={result['has_alert_language']}, "
                  f"compute={result['has_computation']})")

            time.sleep(0.5)  # Rate limiting

    # Aggregate results
    summary = aggregate_results(all_results)
    summary["raw_results"] = all_results

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = RESULTS_DIR / f"active_service_{timestamp}.json"
    with open(results_file, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\n{'='*70}")
    print(f"  Results saved to: {results_file}")
    print_summary(summary)
    print(f"{'='*70}\n")

    return summary


def aggregate_results(results: list[dict]) -> dict:
    """Aggregate results by representation and category."""
    summary = {
        "model": MODEL,
        "timestamp": datetime.now().isoformat(),
        "total_scenarios": len(set(r["scenario_id"] for r in results)),
        "by_representation": {},
        "by_category": {},
    }

    for rep in set(r["representation"] for r in results):
        rep_results = [r for r in results if r["representation"] == rep]
        detected = sum(1 for r in rep_results if r["proactive_alert_detected"])
        total = len(rep_results)
        summary["by_representation"][rep] = {
            "total": total,
            "detected": detected,
            "recall": round(detected / max(total, 1), 3),
            "avg_keyword_score": round(
                sum(r["keyword_score"] for r in rep_results) / max(total, 1), 3
            ),
            "computation_rate": round(
                sum(1 for r in rep_results if r["has_computation"]) / max(total, 1), 3
            ),
        }

    for cat in set(r["category"] for r in results):
        cat_results = [r for r in results if r["category"] == cat]
        summary["by_category"][cat] = {}
        for rep in set(r["representation"] for r in results):
            rep_cat = [r for r in cat_results if r["representation"] == rep]
            detected = sum(1 for r in rep_cat if r["proactive_alert_detected"])
            total = len(rep_cat)
            summary["by_category"][cat][rep] = {
                "total": total,
                "detected": detected,
                "recall": round(detected / max(total, 1), 3),
            }

    return summary


def print_summary(summary: dict):
    """Print a formatted summary table."""
    print(f"\n  SUMMARY")
    print(f"  {'Representation':<20} {'Recall':>10} {'Avg KW Score':>15} {'Computation':>15}")
    print(f"  {'-'*60}")
    for rep, stats in summary["by_representation"].items():
        print(f"  {rep:<20} {stats['recall']:>10.1%} {stats['avg_keyword_score']:>15.3f} "
              f"{stats['computation_rate']:>15.1%}")

    print(f"\n  BY CATEGORY")
    print(f"  {'Category':<30} ", end="")
    reps = sorted(summary["by_representation"].keys())
    for rep in reps:
        print(f"{rep:>12}", end="")
    print()
    print(f"  {'-'*60}")
    for cat, cat_stats in sorted(summary["by_category"].items()):
        print(f"  {cat:<30} ", end="")
        for rep in reps:
            if rep in cat_stats:
                print(f"{cat_stats[rep]['recall']:>11.0%} ", end="")
            else:
                print(f"{'N/A':>12}", end="")
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Active Service experiment")
    parser.add_argument("-n", "--max-scenarios", type=int, default=None,
                        help="Max scenarios to run (default: all)")
    parser.add_argument("--reps", nargs="+", default=["code", "flat"],
                        choices=["code", "flat", "none"],
                        help="Representations to test")
    parser.add_argument("--scenarios-file", type=str, default=None,
                        help="Path to scenarios JSON file")
    args = parser.parse_args()

    scenarios_path = Path(args.scenarios_file) if args.scenarios_file else None
    run_experiment(
        scenarios=load_scenarios(scenarios_path) if scenarios_path else None,
        max_scenarios=args.max_scenarios,
        representations=args.reps,
    )
