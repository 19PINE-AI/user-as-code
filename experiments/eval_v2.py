"""
Evaluation of User as Code v2 (with SOTA recall mechanisms)
on LOCOMO and LongMemEval, compared against v1 and baselines.
"""

import json
import os
import re
import sys
import time
import pathlib
import random
from collections import defaultdict
from datetime import datetime

# Clean Qdrant locks
for p in [pathlib.Path('/tmp/qdrant/.lock'),
          pathlib.Path.home() / '.mem0' / 'migrations_qdrant' / '.lock']:
    p.unlink(missing_ok=True)

from google import genai
from user_as_code_v2 import UserAsCodeV2
from user_as_code_full import UserAsCodeFull

MODEL = "gemini-3-flash-preview"
gclient = genai.Client()

RESULTS_DIR = pathlib.Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def answer_with_thinking(question, context):
    system = f"""You have access to stored information about a conversation between two people.
Use ONLY the provided context to answer questions.
Think carefully, then provide ONLY the final answer as a short phrase on the last line.
Resolve relative dates using conversation timestamps.
If information is not available, say "No information available".

Context:
{context}"""
    try:
        response = gclient.models.generate_content(
            model=MODEL,
            contents=f"{question}\n\nThink carefully, then give ONLY a concise final answer.",
            config=genai.types.GenerateContentConfig(
                system_instruction=system,
                thinking_config=genai.types.ThinkingConfig(thinking_budget=2048),
                temperature=1.0,
            ),
        )
        text = response.text.strip()
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        return lines[-1] if len(lines) > 1 else text
    except Exception as e:
        return f"Error: {e}"


def compute_f1(pred, ref):
    def tok(t): return set(re.findall(r'\b\w+\b', str(t).lower()))
    pt, rt = tok(pred), tok(ref)
    if not rt: return 1.0 if not pt else 0.0
    if not pt: return 0.0
    common = pt & rt
    if not common: return 0.0
    p, r = len(common)/len(pt), len(common)/len(rt)
    return 2*p*r/(p+r)


def judge_answer(question, gold, pred):
    try:
        response = gclient.models.generate_content(
            model=MODEL,
            contents=f"""Is this answer correct? Consider semantic equivalence.
Question: {question}
Gold: {gold}
Predicted: {pred}
Answer ONLY "yes" or "no".""",
            config=genai.types.GenerateContentConfig(temperature=0.0, max_output_tokens=10),
        )
        return response.text.strip().lower().startswith("yes")
    except:
        return False


# ---------------------------------------------------------------------------
# LOCOMO
# ---------------------------------------------------------------------------

def load_locomo(max_convs=2):
    path = pathlib.Path(__file__).parent.parent / "benchmarks" / "locomo" / "data" / "locomo10.json"
    with open(path) as f:
        return json.load(f)[:max_convs]


def parse_locomo_sessions(conv_data):
    """Parse LOCOMO conversation into (session_id, date, turns) tuples."""
    conversation = conv_data.get("conversation", {})
    sessions = []
    session_keys = sorted(
        [k for k in conversation.keys()
         if k.startswith("session_") and not k.endswith("_date_time")],
        key=lambda x: int(x.split("_")[1])
    )
    for sk in session_keys:
        date_key = f"{sk}_date_time"
        date = conversation.get(date_key, "")
        turns = []
        for turn in conversation[sk]:
            if isinstance(turn, dict):
                speaker = turn.get("speaker", "?")
                text = turn.get("text", "")
                turns.append(f"{speaker}: {text}")
        sessions.append((sk, date, turns))
    return sessions


def run_locomo_eval(max_convs=2, max_qa=80):
    data = load_locomo(max_convs)
    print(f"\n  LOCOMO: {len(data)} conversations")

    cat_names = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop", 5: "adversarial"}
    all_results = {}

    for ci, conv_data in enumerate(data):
        sessions = parse_locomo_sessions(conv_data)
        qa_pairs = conv_data.get("qa", [])[:max_qa]
        sid = conv_data.get("sample_id", f"conv_{ci}")
        all_turns = []
        for _, _, turns in sessions:
            all_turns.extend(turns)

        print(f"\n  Conv {ci+1}/{len(data)} ({sid}): {len(sessions)} sessions, {len(all_turns)} turns, {len(qa_pairs)} QAs")

        # --- UaC v2 (SOTA mechanisms) ---
        print(f"    uac_v2: ingesting...", end="", flush=True)
        t0 = time.time()
        v2 = UserAsCodeV2(f"locomo_v2_{sid}")
        for sk, date, turns in sessions:
            v2.ingest_session(turns, sk, date)
        print(f" ({time.time()-t0:.0f}s) answering...", end="", flush=True)

        t0 = time.time()
        v2_f1s = []
        for qi, qa in enumerate(qa_pairs):
            answer = str(qa.get("answer", ""))
            pred = v2.answer(qa["question"])
            f1 = compute_f1(pred, answer)
            v2_f1s.append(f1)
            if qi % 20 == 0 and qi > 0:
                print(f" {qi}", end="", flush=True)
            time.sleep(0.1)
        avg_v2 = sum(v2_f1s)/len(v2_f1s) if v2_f1s else 0
        print(f" -> F1={avg_v2:.3f} ({len(v2_f1s)}Q, {time.time()-t0:.0f}s)")

        # --- UaC v1 (basic archive) ---
        print(f"    uac_v1: ingesting...", end="", flush=True)
        t0 = time.time()
        v1 = UserAsCodeFull(f"locomo_v1_{sid}")
        chunk_size = 50
        for i in range(0, len(all_turns), chunk_size):
            chunk = all_turns[i:i+chunk_size]
            v1.ingest_conversation("\n".join(chunk), f"s{i//chunk_size}")
        print(f" ({time.time()-t0:.0f}s) answering...", end="", flush=True)

        t0 = time.time()
        v1_f1s = []
        for qi, qa in enumerate(qa_pairs):
            answer = str(qa.get("answer", ""))
            context = v1.retrieve(qa["question"])
            pred = answer_with_thinking(qa["question"], context)
            f1 = compute_f1(pred, answer)
            v1_f1s.append(f1)
            if qi % 20 == 0 and qi > 0:
                print(f" {qi}", end="", flush=True)
            time.sleep(0.1)
        avg_v1 = sum(v1_f1s)/len(v1_f1s) if v1_f1s else 0
        print(f" -> F1={avg_v1:.3f} ({len(v1_f1s)}Q, {time.time()-t0:.0f}s)")

        # --- Mem0 ---
        print(f"    mem0: ingesting...", end="", flush=True)
        t0 = time.time()
        try:
            from mem0 import Memory
            for p in [pathlib.Path('/tmp/qdrant/.lock'),
                      pathlib.Path.home() / '.mem0' / 'migrations_qdrant' / '.lock']:
                p.unlink(missing_ok=True)
            mem = Memory()
            try:
                mem.delete_all(user_id=f"locomo_mem0_{sid}")
            except:
                pass
            batch_size = 20
            for i in range(0, len(all_turns), batch_size):
                batch = "\n".join(all_turns[i:i+batch_size])
                try:
                    mem.add([{"role": "user", "content": batch}], user_id=f"locomo_mem0_{sid}")
                except Exception as e:
                    pass
            print(f" ({time.time()-t0:.0f}s) answering...", end="", flush=True)

            t0 = time.time()
            mem0_f1s = []
            for qi, qa in enumerate(qa_pairs):
                answer = str(qa.get("answer", ""))
                try:
                    results = mem.search(qa["question"], user_id=f"locomo_mem0_{sid}")
                    memories = [r.get("memory", str(r)) for r in results.get("results", [])]
                    all_m = mem.get_all(user_id=f"locomo_mem0_{sid}")
                    for r in all_m.get("results", []):
                        m = r.get("memory", str(r)) if isinstance(r, dict) else str(r)
                        if m not in memories:
                            memories.append(m)
                    context = "\n".join(f"- {m}" for m in memories[:30])
                except:
                    context = "No memories available."
                pred = answer_with_thinking(qa["question"], context)
                f1 = compute_f1(pred, answer)
                mem0_f1s.append(f1)
                if qi % 20 == 0 and qi > 0:
                    print(f" {qi}", end="", flush=True)
                time.sleep(0.1)
            avg_mem0 = sum(mem0_f1s)/len(mem0_f1s) if mem0_f1s else 0
            print(f" -> F1={avg_mem0:.3f} ({len(mem0_f1s)}Q, {time.time()-t0:.0f}s)")
        except Exception as e:
            print(f" FAILED: {e}")
            avg_mem0 = 0
            mem0_f1s = []

        # --- Full context ---
        print(f"    full_ctx: answering...", end="", flush=True)
        t0 = time.time()
        full_text = "\n".join(all_turns)
        if len(full_text) > 80000:
            full_text = full_text[:80000]
        fc_f1s = []
        for qi, qa in enumerate(qa_pairs):
            answer = str(qa.get("answer", ""))
            pred = answer_with_thinking(qa["question"], full_text)
            f1 = compute_f1(pred, answer)
            fc_f1s.append(f1)
            if qi % 20 == 0 and qi > 0:
                print(f" {qi}", end="", flush=True)
            time.sleep(0.1)
        avg_fc = sum(fc_f1s)/len(fc_f1s) if fc_f1s else 0
        print(f" -> F1={avg_fc:.3f} ({len(fc_f1s)}Q, {time.time()-t0:.0f}s)")

        all_results[sid] = {
            "uac_v2": avg_v2, "uac_v1": avg_v1,
            "mem0": avg_mem0, "full_ctx": avg_fc,
        }

    # Summary
    print(f"\n  LOCOMO SUMMARY")
    print(f"  {'System':<15} {'Avg F1':>10}")
    print(f"  {'-'*26}")
    totals = defaultdict(list)
    for sid, scores in all_results.items():
        for sys, f1 in scores.items():
            totals[sys].append(f1)
    for sys in ["full_ctx", "uac_v2", "uac_v1", "mem0"]:
        vals = totals[sys]
        avg = sum(vals)/len(vals) if vals else 0
        print(f"  {sys:<15} {avg:>10.3f}")

    return all_results


# ---------------------------------------------------------------------------
# LongMemEval
# ---------------------------------------------------------------------------

def run_longmemeval_eval(n_per_type=8):
    random.seed(42)
    path = pathlib.Path(__file__).parent.parent / "benchmarks" / "longmemeval" / "data" / "longmemeval_oracle.json"
    with open(path) as f:
        data = json.load(f)

    by_type = defaultdict(list)
    for q in data:
        by_type[q["question_type"]].append(q)

    sampled = []
    for qtype in sorted(by_type.keys()):
        sampled.extend(random.sample(by_type[qtype], min(n_per_type, len(by_type[qtype]))))

    print(f"\n  LongMemEval: {len(sampled)} questions (stratified)")

    results = defaultdict(lambda: defaultdict(list))

    for qi, q in enumerate(sampled):
        qtype = q["question_type"]
        question = q["question"]
        gold = q["answer"]
        sessions = q.get("haystack_sessions", [])

        # Parse sessions
        session_turns = []
        for si, session in enumerate(sessions):
            turns = []
            if isinstance(session, list):
                for turn in session:
                    if isinstance(turn, dict):
                        role = turn.get("role", "user")
                        content = turn.get("content", "")
                        turns.append(f"{role}: {content}")
            session_turns.append((f"s{si}", turns))

        all_turns = []
        for _, turns in session_turns:
            all_turns.extend(turns)

        print(f"  [{qi+1}/{len(sampled)}] {qtype[:15]:>15}", end="", flush=True)

        # --- UaC v2 ---
        v2 = UserAsCodeV2(f"lme_v2_{qi}")
        for sk, turns in session_turns:
            if turns:
                v2.ingest_session(turns, sk)
        pred_v2 = v2.answer(question)
        c_v2 = judge_answer(question, gold, pred_v2)
        results["uac_v2"][qtype].append(1 if c_v2 else 0)
        results["uac_v2"]["overall"].append(1 if c_v2 else 0)

        # --- UaC v1 ---
        v1 = UserAsCodeFull(f"lme_v1_{qi}")
        if all_turns:
            v1.ingest_conversation("\n".join(all_turns), "s0")
        ctx_v1 = v1.retrieve(question)
        pred_v1 = answer_with_thinking(question, ctx_v1)
        c_v1 = judge_answer(question, gold, pred_v1)
        results["uac_v1"][qtype].append(1 if c_v1 else 0)
        results["uac_v1"]["overall"].append(1 if c_v1 else 0)

        # --- Full context ---
        full_text = "\n".join(all_turns)
        pred_fc = answer_with_thinking(question, full_text)
        c_fc = judge_answer(question, gold, pred_fc)
        results["full_ctx"][qtype].append(1 if c_fc else 0)
        results["full_ctx"]["overall"].append(1 if c_fc else 0)

        print(f"  v2={'Y' if c_v2 else 'N'}  v1={'Y' if c_v1 else 'N'}  fc={'Y' if c_fc else 'N'}")
        time.sleep(0.3)

    # Summary
    qtypes = sorted(set(q["question_type"] for q in sampled))
    print(f"\n  {'System':<12}", end="")
    for qt in qtypes:
        print(f" {qt[:12]:>12}", end="")
    print(f" {'Overall':>10}")
    print(f"  {'-'*(12 + 13*len(qtypes) + 10)}")

    for sys in ["full_ctx", "uac_v2", "uac_v1"]:
        print(f"  {sys:<12}", end="")
        for qt in qtypes:
            scores = results[sys].get(qt, [])
            acc = sum(scores)/len(scores) if scores else 0
            print(f" {acc:>11.0%} ", end="")
        overall = results[sys]["overall"]
        acc = sum(overall)/len(overall) if overall else 0
        print(f" {acc:>9.0%}")

    return dict(results)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", choices=["locomo", "longmemeval", "both"], default="both")
    parser.add_argument("--locomo-convs", type=int, default=2)
    parser.add_argument("--locomo-qa", type=int, default=80)
    parser.add_argument("--lme-per-type", type=int, default=8)
    args = parser.parse_args()

    all_results = {"model": MODEL, "timestamp": datetime.now().isoformat()}

    if args.benchmark in ("locomo", "both"):
        print(f"\n{'='*70}")
        print(f"  LOCOMO (v2 vs v1 vs Mem0 vs Full Context)")
        print(f"{'='*70}")
        all_results["locomo"] = run_locomo_eval(args.locomo_convs, args.locomo_qa)

    if args.benchmark in ("longmemeval", "both"):
        print(f"\n{'='*70}")
        print(f"  LONGMEMEVAL (v2 vs v1 vs Full Context)")
        print(f"{'='*70}")
        all_results["longmemeval"] = run_longmemeval_eval(args.lme_per_type)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RESULTS_DIR / f"v2_eval_{ts}.json"
    with open(out, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  Saved to: {out}")
