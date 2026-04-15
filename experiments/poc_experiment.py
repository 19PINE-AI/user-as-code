"""
Proof-of-Concept Experiment: User as Code vs. Flat Facts vs. No Memory

Uses the actual Jessica Thompson prototype as the User-as-Code representation.
Compares three conditions on the same user state:
1. Code: The agent sees the Python schema + state + constraint output
2. Flat: The agent sees a Mem0-style fact list
3. None: The agent sees nothing (control)

Tests whether each representation enables proactive alerting.
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime

from google import genai

MODEL = "gemini-3-flash-preview"
client = genai.Client()

PROTOTYPE_DIR = Path(__file__).parent.parent / "prototype" / "jessica_thompson"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Build representations from the actual prototype
# ---------------------------------------------------------------------------

def load_code_representation() -> str:
    """Load the actual Python files from the prototype."""
    files = [
        ("manifest.py", PROTOTYPE_DIR / "manifest.py"),
        ("domains/travel/schema.py", PROTOTYPE_DIR / "domains" / "travel" / "schema.py"),
        ("domains/travel/state.py", PROTOTYPE_DIR / "domains" / "travel" / "state.py"),
        ("domains/health/schema.py", PROTOTYPE_DIR / "domains" / "health" / "schema.py"),
        ("domains/health/state.py", PROTOTYPE_DIR / "domains" / "health" / "state.py"),
        ("domains/finance/schema.py", PROTOTYPE_DIR / "domains" / "finance" / "schema.py"),
        ("domains/finance/state.py", PROTOTYPE_DIR / "domains" / "finance" / "state.py"),
        ("domains/family/schema.py", PROTOTYPE_DIR / "domains" / "family" / "schema.py"),
        ("domains/family/state.py", PROTOTYPE_DIR / "domains" / "family" / "state.py"),
    ]

    sections = []
    for label, path in files:
        if path.exists():
            content = path.read_text()
            sections.append(f"# === {label} ===\n{content}")

    return "\n\n".join(sections)


def load_flat_fact_representation() -> str:
    """Convert the prototype state to a flat fact list (Mem0-style)."""
    return """User Memory (facts extracted from conversations):
1. User's name is Jessica Marie Thompson, born March 15, 1988.
2. Lives in San Francisco, CA.
3. Email: jessica.thompson@email.com, Phone: (415) 555-0187.
4. Passport number AB1234567, issued by US, expires February 18, 2025.
5. Booked a trip to Tokyo, Japan. Departure: January 15, 2025. Return: January 25, 2025. Flight JAL-9823. International trip, 11.5 hours. Business trip with meetings in Shibuya.
6. Booked a trip to Mexico City, Mexico. Departure: March 10, 2025. Return: March 17, 2025. Flight AA-4561. International trip, 4.5 hours. Vacation with James.
7. Prefers window seat on Japan routes. Prefers aisle on flights over 6 hours. Otherwise prefers window.
8. Frequent flyer: JAL Mileage Bank, AAdvantage.
9. Meal preference: no peanuts.
10. Has a Chase checking account ending in 4521.
11. Has a Schwab investment account ending in 8903.
12. Pending wire transfer of $15,000 to mother Patricia Williams.
13. Patricia Williams instructed to send to Bank of America account ending in 3310 (on Feb 10, 2025).
14. James Thompson instructed to send to Wells Fargo account ending in 6654 (on Feb 12, 2025).
15. Allergic to peanuts (severe, carries EpiPen).
16. Allergic to penicillin (moderate, causes rash and hives).
17. Takes cetirizine 10mg daily for seasonal allergies.
18. Recently prescribed amoxicillin 500mg three times daily by Dr. Robert Chen on January 10, 2025.
19. Drives a 2020 Honda Accord (service due this Friday).
20. Drives a 2023 Tesla Model 3.
21. Husband: James Thompson, age 42, software engineer.
22. Daughter: Sarah Thompson, age 8, has eczema.
23. Mother: Patricia Williams, age 68, retired."""


# ---------------------------------------------------------------------------
# Test scenarios
# ---------------------------------------------------------------------------

SCENARIOS = [
    {
        "id": "travel_passport",
        "description": "Passport validity for Tokyo trip",
        "user_message": "Hey, I'm getting excited about my Tokyo trip! Any last-minute things I should think about?",
        "expected_alert_keywords": ["passport", "expires", "180", "34", "validity", "renew"],
        "expected_type": "travel_document_validity",
    },
    {
        "id": "health_allergy",
        "description": "Amoxicillin prescribed to penicillin-allergic patient",
        "user_message": "I just picked up my new prescription from the pharmacy. Anything else on my mind today?",
        "expected_alert_keywords": ["amoxicillin", "penicillin", "allergy", "contraindicated", "conflict", "doctor"],
        "expected_type": "drug_interaction",
    },
    {
        "id": "finance_conflict",
        "description": "Conflicting wire transfer instructions",
        "user_message": "I need to take care of that wire transfer to my mom soon. Can you remind me of the details?",
        "expected_alert_keywords": ["conflicting", "patricia", "bank of america", "wells fargo", "wire", "james"],
        "expected_type": "financial_authorization",
    },
    {
        "id": "travel_mexico",
        "description": "Passport expired before Mexico City trip",
        "user_message": "Can you help me plan what to pack for Mexico City?",
        "expected_alert_keywords": ["passport", "expires", "mexico", "expired", "march"],
        "expected_type": "travel_document_validity",
    },
    {
        "id": "proactive_unsolicited",
        "description": "Agent should proactively alert even without topic hint",
        "user_message": "Good morning! What's the weather like today?",
        "expected_alert_keywords": ["passport", "amoxicillin", "penicillin", "wire", "conflict"],
        "expected_type": "proactive_general",
    },
]


# ---------------------------------------------------------------------------
# Run evaluation
# ---------------------------------------------------------------------------

def run_scenario(scenario: dict, representation: str, memory_content: str | None) -> dict:
    """Run a single scenario."""

    if representation == "code":
        system = f"""You are Jessica Thompson's personal AI assistant. Her information is stored as a Python code project (User as Code) shown below. You can read the typed state and reason about it computationally.

CRITICAL INSTRUCTION: Before responding to the user, review ALL domains for cross-domain issues:
- Check passport validity against all international trips (most countries require 180+ days)
- Check medications against known allergies
- Check for conflicting instructions from different people
- Check for any time-sensitive deadlines

If you find ANY issues, alert the user IMMEDIATELY at the start of your response, even if unrelated to their question. Be specific with dates and numbers.

{memory_content}"""
    elif representation == "flat":
        system = f"""You are Jessica Thompson's personal AI assistant. Her information is stored as facts from previous conversations, shown below.

CRITICAL INSTRUCTION: Before responding to the user, review ALL stored facts for cross-domain issues:
- Check passport validity against all international trips (most countries require 180+ days)
- Check medications against known allergies
- Check for conflicting instructions from different people
- Check for any time-sensitive deadlines

If you find ANY issues, alert the user IMMEDIATELY at the start of your response, even if unrelated to their question. Be specific with dates and numbers.

{memory_content}"""
    else:
        system = "You are a helpful personal AI assistant."

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=scenario["user_message"],
            config=genai.types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.2,
                max_output_tokens=1500,
            ),
        )
        response_text = response.text
    except Exception as e:
        response_text = f"ERROR: {e}"

    # Score
    response_lower = response_text.lower()
    keywords = scenario["expected_alert_keywords"]
    hits = [kw for kw in keywords if kw.lower() in response_lower]
    score = len(hits) / max(len(keywords), 1)

    # Check for specific computation
    has_specific_numbers = any(
        n in response_text
        for n in ["34", "180", "500mg", "15,000", "15000"]
    )

    return {
        "scenario_id": scenario["id"],
        "description": scenario["description"],
        "representation": representation,
        "user_message": scenario["user_message"],
        "response": response_text,
        "keyword_hits": hits,
        "keyword_score": round(score, 3),
        "has_specific_numbers": has_specific_numbers,
        "alert_detected": score >= 0.3,
    }


def main():
    print(f"\n{'='*70}")
    print(f"  User as Code: Proof-of-Concept Experiment")
    print(f"  Model: {MODEL}")
    print(f"  Scenarios: {len(SCENARIOS)}")
    print(f"{'='*70}\n")

    code_memory = load_code_representation()
    flat_memory = load_flat_fact_representation()

    representations = {
        "code": code_memory,
        "flat": flat_memory,
        "none": None,
    }

    all_results = []

    for scenario in SCENARIOS:
        print(f"\n  Scenario: {scenario['id']} — {scenario['description']}")
        print(f"  User: \"{scenario['user_message'][:60]}...\"")
        print()

        for rep_name, memory in representations.items():
            result = run_scenario(scenario, rep_name, memory)
            all_results.append(result)

            status = "ALERT" if result["alert_detected"] else "MISS"
            print(f"    {rep_name:>6}: [{status}] score={result['keyword_score']:.2f} "
                  f"nums={result['has_specific_numbers']} "
                  f"hits={result['keyword_hits'][:3]}...")

            # Show first 150 chars of response
            resp_preview = result["response"][:150].replace("\n", " ")
            print(f"           \"{resp_preview}...\"")
            print()

            time.sleep(1)  # Rate limit

    # Summary
    print(f"\n{'='*70}")
    print(f"  SUMMARY")
    print(f"{'='*70}")
    print(f"\n  {'Scenario':<25} {'Code':>8} {'Flat':>8} {'None':>8}")
    print(f"  {'-'*50}")

    for scenario in SCENARIOS:
        sid = scenario["id"]
        scores = {}
        for r in all_results:
            if r["scenario_id"] == sid:
                scores[r["representation"]] = r["alert_detected"]
        print(f"  {sid:<25} "
              f"{'YES' if scores.get('code') else 'no':>8} "
              f"{'YES' if scores.get('flat') else 'no':>8} "
              f"{'YES' if scores.get('none') else 'no':>8}")

    # Aggregate
    print(f"\n  {'TOTAL ALERTS':<25}", end="")
    for rep in ["code", "flat", "none"]:
        count = sum(1 for r in all_results if r["representation"] == rep and r["alert_detected"])
        total = sum(1 for r in all_results if r["representation"] == rep)
        print(f"  {count}/{total}  ", end="")
    print()

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = RESULTS_DIR / f"poc_{timestamp}.json"
    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  Results saved to: {results_file}")


if __name__ == "__main__":
    main()
