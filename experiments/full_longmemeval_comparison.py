"""
Full LongMemEval Benchmark: Compare ALL memory systems using Gemini 3 Flash w/ thinking.

Systems:
1. User as Code v2
2. SimpleMem
3. A-MEM (Agentic Memory)
4. Mem0
5. Full Context (baseline)

Stratified sample: 8 questions per type (6 types) = 48 total.
"""

import json
import os
import sys
import time
import random
import pathlib
import traceback
import subprocess
import tempfile
from collections import defaultdict
from datetime import datetime

# ---------------------------------------------------------------------------
# LLM setup
# ---------------------------------------------------------------------------
from google import genai

gclient = genai.Client()
MODEL = "gemini-3-flash-preview"


def llm_answer(question: str, context: str) -> str:
    """Answer a question given context, using thinking."""
    system = f"""You have access to stored information about conversations between a user and an assistant.
Use ONLY the provided context to answer questions.
Give ONLY a concise final answer (a short phrase or sentence). No explanation.
If the information is not available in the context, say "Not available".

Context:
{context}"""

    try:
        resp = gclient.models.generate_content(
            model=MODEL,
            contents=f"{question}",
            config=genai.types.GenerateContentConfig(
                system_instruction=system,
                thinking_config=genai.types.ThinkingConfig(thinking_budget=2048),
                temperature=1.0,
            ),
        )
        text = resp.text.strip()
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        return lines[-1] if lines else text
    except Exception as e:
        return f"Error: {e}"


def llm_judge(question: str, gold: str, predicted: str) -> bool:
    """Judge whether predicted answer is correct."""
    prompt = f"""Question: {question}
Gold answer: {gold}
Predicted answer: {predicted}

CORRECT if it conveys the same core information. WRONG only if factually wrong or says not available when gold has answer. Say YES or NO."""

    try:
        resp = gclient.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                thinking_config=genai.types.ThinkingConfig(thinking_budget=256),
                temperature=1.0,
            ),
        )
        text = resp.text.strip().upper()
        return "YES" in text and "NO" not in text.replace("YES", "")
    except Exception as e:
        print(f"  [judge error: {e}]")
        return False


# ---------------------------------------------------------------------------
# Helper: format sessions
# ---------------------------------------------------------------------------
def sessions_to_full_text(haystack_sessions):
    """Convert all sessions to a single text blob."""
    parts = []
    for i, session in enumerate(haystack_sessions):
        parts.append(f"--- Session {i+1} ---")
        for turn in session:
            parts.append(f"{turn['role']}: {turn['content']}")
    return "\n".join(parts)


def sessions_to_session_groups(haystack_sessions):
    """Return list of (session_id, turns_list) tuples."""
    groups = []
    for i, session in enumerate(haystack_sessions):
        sid = f"session_{i}"
        turns = [f"{t['role']}: {t['content']}" for t in session]
        groups.append((sid, turns))
    return groups


# ---------------------------------------------------------------------------
# System 1: User as Code v2
# ---------------------------------------------------------------------------
def run_user_as_code_v2(question, haystack_sessions):
    sys.path.insert(0, "/Users/boj/UserAsCode/experiments")
    from user_as_code_v2 import UserAsCodeV2

    uid = f"bench_{random.randint(0, 999999)}"
    v2 = UserAsCodeV2(user_id=uid)
    try:
        groups = sessions_to_session_groups(haystack_sessions)
        for sid, turns in groups:
            v2.ingest_session(turns, sid)
        answer = v2.answer(question)
        return answer
    finally:
        try:
            v2.reset()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# System 2: SimpleMem
# ---------------------------------------------------------------------------
def run_simplemem(question, haystack_sessions):
    """Run SimpleMem, configuring it to use gpt-4o-mini (gpt-4.1-mini not available)."""
    import simplemem

    # Configure SimpleMem to use available model
    cfg = simplemem.get_config()
    cfg.llm_model = "gpt-4o-mini"
    simplemem.set_config(cfg)

    mem = simplemem.create_system(clear_db=True)
    try:
        for i, session in enumerate(haystack_sessions):
            for turn in session:
                mem.add_dialogue(
                    speaker=turn["role"],
                    content=turn["content"],
                )
        mem.finalize()
        answer = mem.ask(question)
        return answer
    except Exception as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# System 3: A-MEM (Agentic Memory) — runs in subprocess to avoid ChromaDB conflict
# ---------------------------------------------------------------------------
AMEM_WORKER_SCRIPT = '''
import json, sys

def run_amem(question, haystack_sessions):
    from agentic_memory.memory_system import AgenticMemorySystem
    memory = AgenticMemorySystem(
        model_name="all-MiniLM-L6-v2",
        llm_backend="openai",
        llm_model="gpt-4o-mini",
    )
    for i, session in enumerate(haystack_sessions):
        session_text = "\\n".join(f"{t['role']}: {t['content']}" for t in session)
        memory.add_note(session_text)

    results = memory.search_agentic(question, k=10)
    if results:
        context = "\\n\\n".join(
            r.get("content", r.get("text", str(r))) for r in results
        )
    else:
        context = "No relevant memories found."
    return context

data = json.loads(sys.stdin.read())
try:
    context = run_amem(data["question"], data["haystack_sessions"])
    print(json.dumps({"status": "ok", "context": context}))
except Exception as e:
    print(json.dumps({"status": "error", "error": str(e)}))
'''


def run_amem(question, haystack_sessions):
    """Run A-MEM in a subprocess to avoid ChromaDB singleton conflicts."""
    input_data = json.dumps({
        "question": question,
        "haystack_sessions": haystack_sessions,
    })

    try:
        result = subprocess.run(
            [sys.executable, "-c", AMEM_WORKER_SCRIPT],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=300,
        )

        # Find the JSON output line (last non-empty line of stdout)
        stdout_lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
        if not stdout_lines:
            return f"Error: No output from A-MEM subprocess. stderr: {result.stderr[:200]}"

        resp = json.loads(stdout_lines[-1])
        if resp["status"] == "ok":
            context = resp["context"]
            return llm_answer(question, context)
        else:
            return f"Error: {resp['error']}"
    except subprocess.TimeoutExpired:
        return "Error: A-MEM subprocess timed out (300s)"
    except Exception as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# System 4: Mem0
# ---------------------------------------------------------------------------
def run_mem0(question, haystack_sessions):
    # Clean locks first
    for p in [
        pathlib.Path("/tmp/qdrant/.lock"),
        pathlib.Path.home() / ".mem0" / "migrations_qdrant" / ".lock",
    ]:
        p.unlink(missing_ok=True)

    from mem0 import Memory

    m = Memory()
    user_id = f"bench_{random.randint(0, 999999)}"
    try:
        for i, session in enumerate(haystack_sessions):
            messages = [
                {"role": turn["role"], "content": turn["content"]}
                for turn in session
            ]
            m.add(messages, user_id=user_id)

        results = m.search(question, user_id=user_id, limit=20)
        if results and isinstance(results, dict) and "results" in results:
            memories = results["results"]
        elif results and isinstance(results, list):
            memories = results
        else:
            memories = []

        if memories:
            context = "\n".join(
                r.get("memory", str(r)) for r in memories
            )
        else:
            context = "No relevant memories found."

        answer = llm_answer(question, context)
        return answer
    except Exception as e:
        return f"Error: {e}"
    finally:
        try:
            m.delete_all(user_id=user_id)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# System 5: Full Context
# ---------------------------------------------------------------------------
def run_full_context(question, haystack_sessions):
    full_text = sessions_to_full_text(haystack_sessions)
    # Truncate to ~200k chars to stay within context limits
    if len(full_text) > 200000:
        full_text = full_text[:200000] + "\n... (truncated)"
    answer = llm_answer(question, full_text)
    return answer


# ---------------------------------------------------------------------------
# Main benchmark
# ---------------------------------------------------------------------------
SYSTEMS = {
    "user_as_code_v2": run_user_as_code_v2,
    "simplemem": run_simplemem,
    "amem": run_amem,
    "mem0": run_mem0,
    "full_context": run_full_context,
}


def load_and_sample(data_path, seed=42, per_type=8):
    """Load dataset and take stratified sample."""
    with open(data_path) as f:
        data = json.load(f)

    print(f"Loaded {len(data)} questions")

    # Group by type
    by_type = defaultdict(list)
    for q in data:
        by_type[q["question_type"]].append(q)

    print(f"Question types: {list(by_type.keys())}")
    for qtype, qs in sorted(by_type.items()):
        print(f"  {qtype}: {len(qs)} questions")

    # Stratified sample
    random.seed(seed)
    sample = []
    for qtype in sorted(by_type.keys()):
        pool = by_type[qtype]
        k = min(per_type, len(pool))
        chosen = random.sample(pool, k)
        sample.extend(chosen)

    print(f"\nStratified sample: {len(sample)} questions ({per_type} per type)")
    return sample


def main():
    data_path = "/Users/boj/UserAsCode/benchmarks/longmemeval/data/longmemeval_oracle.json"
    results_path = "/Users/boj/UserAsCode/experiments/results/full_longmemeval_comparison.json"

    sample = load_and_sample(data_path)

    # Results storage
    all_results = []
    system_scores = {s: defaultdict(lambda: {"correct": 0, "total": 0}) for s in SYSTEMS}
    system_totals = {s: {"correct": 0, "total": 0} for s in SYSTEMS}

    start_time = time.time()

    for qi, q in enumerate(sample):
        qid = q["question_id"]
        qtype = q["question_type"]
        question = q["question"]
        gold = q["answer"]
        haystack = q["haystack_sessions"]

        print(f"\n{'='*80}")
        print(f"[{qi+1}/{len(sample)}] {qtype} | Q: {question[:80]}...")
        print(f"  Gold: {gold}")
        print(f"  Sessions: {len(haystack)}, Total turns: {sum(len(s) for s in haystack)}")

        q_result = {
            "question_id": qid,
            "question_type": qtype,
            "question": question,
            "gold_answer": gold,
            "systems": {},
        }

        for sys_name, sys_fn in SYSTEMS.items():
            print(f"\n  --- {sys_name} ---")
            t0 = time.time()
            try:
                predicted = sys_fn(question, haystack)
            except Exception as e:
                predicted = f"SYSTEM ERROR: {e}"
                traceback.print_exc()

            elapsed = time.time() - t0
            print(f"  Predicted: {predicted[:120]}")
            print(f"  Time: {elapsed:.1f}s")

            # Judge
            try:
                correct = llm_judge(question, gold, predicted)
            except Exception as e:
                print(f"  Judge error: {e}")
                correct = False

            verdict = "CORRECT" if correct else "WRONG"
            print(f"  Verdict: {verdict}")

            q_result["systems"][sys_name] = {
                "answer": predicted,
                "correct": correct,
                "time_seconds": round(elapsed, 2),
            }

            system_scores[sys_name][qtype]["total"] += 1
            system_scores[sys_name][qtype]["correct"] += 1 if correct else 0
            system_totals[sys_name]["total"] += 1
            system_totals[sys_name]["correct"] += 1 if correct else 0

        all_results.append(q_result)

        # Print running totals
        print(f"\n  --- Running Totals ---")
        for sys_name in SYSTEMS:
            t = system_totals[sys_name]
            acc = t["correct"] / t["total"] * 100 if t["total"] > 0 else 0
            print(f"  {sys_name}: {t['correct']}/{t['total']} ({acc:.1f}%)")

        # Save intermediate results after each question
        _save_results(results_path, all_results, system_scores, system_totals, start_time)

    total_time = time.time() - start_time
    _save_results(results_path, all_results, system_scores, system_totals, start_time)

    # Final summary
    print(f"\n{'='*80}")
    print(f"FINAL RESULTS ({total_time:.0f}s total)")
    print(f"{'='*80}")

    # Per-type table
    qtypes = sorted(set(q["question_type"] for q in sample))
    header = f"{'System':<20}" + "".join(f"{qt[:16]:>18}" for qt in qtypes) + f"{'OVERALL':>13}"
    print(header)
    print("-" * len(header))

    for sys_name in SYSTEMS:
        row = f"{sys_name:<20}"
        for qt in qtypes:
            s = system_scores[sys_name][qt]
            if s["total"] > 0:
                acc = s["correct"] / s["total"] * 100
                row += f"{s['correct']}/{s['total']} ({acc:.0f}%)".rjust(18)
            else:
                row += f"{'N/A':>18}"
        t = system_totals[sys_name]
        acc = t["correct"] / t["total"] * 100 if t["total"] > 0 else 0
        row += f"{t['correct']}/{t['total']} ({acc:.0f}%)".rjust(13)
        print(row)

    print(f"\nResults saved to {results_path}")


def _save_results(path, all_results, system_scores, system_totals, start_time):
    """Save results to JSON."""
    # Convert defaultdicts to regular dicts for JSON serialization
    scores_dict = {}
    for sys_name, type_scores in system_scores.items():
        scores_dict[sys_name] = {}
        for qtype, counts in type_scores.items():
            scores_dict[sys_name][qtype] = dict(counts)
            total = counts["total"]
            correct = counts["correct"]
            scores_dict[sys_name][qtype]["accuracy"] = correct / total if total > 0 else 0

    totals_dict = {}
    for sys_name, counts in system_totals.items():
        totals_dict[sys_name] = dict(counts)
        total = counts["total"]
        correct = counts["correct"]
        totals_dict[sys_name]["accuracy"] = correct / total if total > 0 else 0

    output = {
        "benchmark": "LongMemEval",
        "model": MODEL,
        "timestamp": datetime.now().isoformat(),
        "elapsed_seconds": round(time.time() - start_time, 1),
        "sample_size": len(all_results),
        "per_type_scores": scores_dict,
        "overall_scores": totals_dict,
        "detailed_results": all_results,
    }

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(output, f, indent=2, default=str)


if __name__ == "__main__":
    main()
