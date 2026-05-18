#!/usr/bin/env python3
"""Phase-2 (structuring) scalability data point.

We take the actual append-only fact corpus produced by UaC v5 Phase 1 on the
five LOCOMO conversations, concatenate them to simulate progressively longer
session histories, and time + token-count a single Phase-2 structuring call at
each scale.

Output: results/phase2_scalability.json with rows
  { n_sessions, n_facts, input_tokens, output_tokens, thoughts_tokens,
    wall_seconds, est_usd, output_chars }
"""
from __future__ import annotations
import json
import pathlib
import sys
import time

from google import genai

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from runner_utils import _log, GEMINI_MODEL  # noqa: E402

RESULTS_DIR = pathlib.Path(__file__).resolve().parent / "results"
OUT_PATH = RESULTS_DIR / "phase2_scalability.json"

# Gemini 3 Flash pricing
USD_PER_M_INPUT = 0.30
USD_PER_M_OUTPUT = 2.50

# Real Phase-1 fact lists from existing UaC v5 runs are kept in
# locomo5_uac_v5.json indirectly, but we want the raw fact list. We rebuild
# them quickly here by running Phase 1 on one conversation and replicating.

DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "benchmarks/locomo/data/locomo10.json"

client = genai.Client()


def get_sessions(conv):
    import re
    c = conv["conversation"]
    keys = sorted(
        [k for k in c.keys() if re.match(r"^session_\d+$", k)],
        key=lambda x: int(x.split("_")[1]),
    )
    out = []
    for sk in keys:
        date = c.get(f"{sk}_date_time", "")
        turns = c[sk]
        out.append({"session_id": sk, "date": date, "turns": turns})
    return out


def build_fact_corpus_for_one_conv():
    """Use UaC v5 Phase 1 on conv-26 to get a realistic ~50-fact-per-session list."""
    from user_as_code_v5 import UserAsCodeV5
    with open(DATA_PATH) as f:
        all_convs = json.load(f)
    conv = all_convs[0]  # conv-26
    sessions = get_sessions(conv)

    uac = UserAsCodeV5(user_id=f"phase2_scalability_{int(time.time())}")
    for s in sessions:
        turn_lines = [f"{t['speaker']}: {t['text']}" for t in s["turns"]]
        uac.ingest_session(turn_lines, s["session_id"], s["date"])
        _log(f"  Phase 1 ingested {s['session_id']}, total facts={len(uac.fact_list)}")
    return uac.fact_list, len(sessions)


def run_structuring_call(fact_list: list[str], thinking_budget: int = 16384):
    """Call Phase 2 structuring on the given fact list. Return token counts + time."""
    all_facts = "\n".join(f"{i+1}. {f}" for i, f in enumerate(fact_list))
    if len(all_facts) > 500_000:
        all_facts = all_facts[:500_000] + "\n... (truncated at 500K chars)"

    prompt = f"""Organize ALL these facts into structured Python code using dataclasses.

FACTS ({len(fact_list)} total):
{all_facts}

RULES:
- Use Python dataclasses with proper type annotations
- Use date(year, month, day) for ALL dates -- never store dates as strings
- Group by entity: create a dataclass per person, per event type, etc.
- Every dataclass should have a notes: list[str] field for facts that don't fit typed fields
- Include ALL facts -- either as typed fields or in the notes list
- ZERO facts should be lost -- if a fact doesn't fit a typed field, put it in notes
- Organize collections: people = [...], events = [...], etc.

Output ONLY Python code:"""

    t0 = time.time()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            thinking_config=genai.types.ThinkingConfig(thinking_budget=thinking_budget),
            temperature=1.0,
        ),
    )
    dt = time.time() - t0

    usage = response.usage_metadata
    in_tok = getattr(usage, "prompt_token_count", 0) or 0
    out_tok = getattr(usage, "candidates_token_count", 0) or 0
    thought_tok = getattr(usage, "thoughts_token_count", 0) or 0

    usd = (in_tok / 1_000_000) * USD_PER_M_INPUT + ((out_tok + thought_tok) / 1_000_000) * USD_PER_M_OUTPUT
    text = response.text or ""
    return {
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "thoughts_tokens": thought_tok,
        "wall_seconds": round(dt, 2),
        "est_usd": round(usd, 5),
        "output_chars": len(text),
    }


def main():
    _log("Building real fact corpus from conv-26 (Phase 1)...")
    base_facts, base_sessions = build_fact_corpus_for_one_conv()
    _log(f"  base: {base_sessions} sessions, {len(base_facts)} facts")
    base_per_session = max(1, len(base_facts) // base_sessions)

    # Scale points: simulate growing session histories by duplicating fact blocks.
    # The duplication is a worst-case stress test (no compression assumed); a
    # real long-running deployment would partially compress, so the costs we
    # report here are an upper bound on what the structuring step needs at
    # each session scale.
    scales = [19, 50, 100, 200]  # n_sessions
    results = {"base_sessions": base_sessions, "base_facts": len(base_facts),
               "rows": []}

    for n_sessions in scales:
        if n_sessions <= base_sessions:
            fact_list = base_facts[: n_sessions * base_per_session]
        else:
            # Replicate the base corpus, lightly varying the session-id prefix
            # so the LLM doesn't see literally identical lines.
            fact_list = list(base_facts)
            shadow_idx = 0
            while len(fact_list) < n_sessions * base_per_session:
                f = base_facts[shadow_idx % len(base_facts)]
                fact_list.append("[shadow{}] ".format(shadow_idx // base_per_session) + f)
                shadow_idx += 1

        _log(f"Running Phase 2 at n_sessions={n_sessions}, n_facts={len(fact_list)}")
        try:
            row = run_structuring_call(fact_list)
            row["n_sessions"] = n_sessions
            row["n_facts"] = len(fact_list)
            results["rows"].append(row)
            _log(f"  result: in={row['input_tokens']} out={row['output_tokens']} "
                 f"thoughts={row['thoughts_tokens']} time={row['wall_seconds']}s "
                 f"usd={row['est_usd']} chars={row['output_chars']}")
        except Exception as e:
            _log(f"  FAILED at n_sessions={n_sessions}: {e}")
            results["rows"].append({"n_sessions": n_sessions, "n_facts": len(fact_list),
                                    "error": str(e)})

        with open(OUT_PATH, "w") as f:
            json.dump(results, f, indent=2)

    _log(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
