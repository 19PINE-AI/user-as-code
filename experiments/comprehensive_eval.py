"""
Comprehensive evaluation: User as Code (Full 3-Tier) vs all baselines
on LOCOMO and LongMemEval.

Systems:
- user_as_code_full: Structured state (Tiers 1-2) + Archive RAG (Tier 3)
- user_as_code_state: Structured state only (Tiers 1-2, no archive)
- mem0: Flat fact extraction + vector retrieval
- full_context: Raw-conversation Full Context reference
- no_memory: No context (lower bound)
"""

import json
import os
import re
import sys
import time
import pathlib
from datetime import datetime
from collections import defaultdict

from google import genai

# Clean Qdrant locks before importing Mem0
for p in [pathlib.Path('/tmp/qdrant/.lock'),
          pathlib.Path.home() / '.mem0' / 'migrations_qdrant' / '.lock']:
    p.unlink(missing_ok=True)

from user_as_code_full import UserAsCodeFull

MODEL = "gemini-3-flash-preview"
gclient = genai.Client()

RESULTS_DIR = pathlib.Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def answer_with_thinking(question: str, context: str) -> str:
    """Answer a question using thinking mode. Returns concise final answer."""
    system = f"""You have access to stored information about a conversation between two people.
Use ONLY the provided context to answer questions.
Think through the information carefully, then provide ONLY the final answer as a short phrase on the last line.
If the question asks about a date, resolve relative dates ("yesterday", "last week") using conversation timestamps.
If the information is not available in the context, say "No information available".

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
        # Extract the final answer (last non-empty line of the non-thinking part)
        text = response.text.strip()
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        # Return last line as the concise answer, or full text if short
        if len(lines) > 1:
            return lines[-1]
        return text
    except Exception as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# LOCOMO helpers
# ---------------------------------------------------------------------------

def load_locomo(max_convs=None):
    path = pathlib.Path(__file__).parent.parent / "benchmarks" / "locomo" / "data" / "locomo10.json"
    with open(path) as f:
        data = json.load(f)
    return data[:max_convs] if max_convs else data


def locomo_conversation_to_turns(conv_data):
    """Convert LOCOMO conversation format to list of (session_id, turns)."""
    conversation = conv_data.get("conversation", {})
    all_turns = []

    if isinstance(conversation, dict):
        # LOCOMO format: dict with session_1, session_2, etc.
        session_keys = sorted(
            [k for k in conversation.keys()
             if k.startswith("session_") and not k.endswith("_date_time")],
            key=lambda x: int(x.split("_")[1])
        )
        for sk in session_keys:
            session = conversation[sk]
            date_key = f"{sk}_date_time"
            date_str = conversation.get(date_key, "")
            if isinstance(session, list):
                for turn in session:
                    if isinstance(turn, dict):
                        speaker = turn.get("speaker", "unknown")
                        text = turn.get("text", "")
                        all_turns.append(f"{speaker}: {text}")
    elif isinstance(conversation, list):
        for turn in conversation:
            if isinstance(turn, dict):
                speaker = turn.get("speaker", turn.get("role", "user"))
                text = turn.get("text", turn.get("content", ""))
                all_turns.append(f"{speaker}: {text}")

    return all_turns


def compute_f1(prediction: str, reference: str) -> float:
    """Compute token-level F1 with stemming (LOCOMO-style)."""
    def tokenize(text):
        return set(re.findall(r'\b\w+\b', str(text).lower()))

    pred_tokens = tokenize(prediction)
    ref_tokens = tokenize(reference)

    if not ref_tokens:
        return 1.0 if not pred_tokens else 0.0
    if not pred_tokens:
        return 0.0

    common = pred_tokens & ref_tokens
    if not common:
        return 0.0

    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


# ---------------------------------------------------------------------------
# LongMemEval helpers
# ---------------------------------------------------------------------------

def load_longmemeval_stratified(n_per_type=10, seed=42):
    """Load a stratified sample from LongMemEval."""
    import random
    random.seed(seed)

    path = pathlib.Path(__file__).parent.parent / "benchmarks" / "longmemeval" / "data" / "longmemeval_oracle.json"
    with open(path) as f:
        data = json.load(f)

    by_type = defaultdict(list)
    for q in data:
        by_type[q["question_type"]].append(q)

    sampled = []
    for qtype, questions in sorted(by_type.items()):
        sample = random.sample(questions, min(n_per_type, len(questions)))
        sampled.extend(sample)

    return sampled


def judge_answer(question, gold, predicted):
    """LLM-as-judge: is the predicted answer correct?"""
    prompt = f"""You are evaluating whether a predicted answer is correct.

Question: {question}
Gold answer: {gold}
Predicted answer: {predicted}

Is the predicted answer correct? Consider semantic equivalence (e.g., "bicycle" = "bike", "Denver" matches "lives in Denver").
Answer ONLY "yes" or "no"."""

    try:
        response = gclient.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=genai.types.GenerateContentConfig(temperature=0.0, max_output_tokens=10),
        )
        return response.text.strip().lower().startswith("yes")
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Memory system wrappers
# ---------------------------------------------------------------------------

class FullUACSystem:
    """User as Code with all 3 tiers."""
    name = "uac_full"

    def __init__(self):
        self.uac = None

    def reset(self, uid):
        self.uac = UserAsCodeFull(user_id=uid)

    def ingest(self, turns, session_id="s1"):
        conv_text = "\n".join(turns)
        self.uac.ingest_conversation(conv_text, session_id)

    def answer(self, question):
        context = self.uac.retrieve(question)
        return answer_with_thinking(question, context)

    def get_context(self, question):
        return self.uac.retrieve(question)


class StateOnlyUACSystem:
    """User as Code with Tiers 1-2 only (no archive RAG)."""
    name = "uac_state"

    def __init__(self):
        self.uac = None

    def reset(self, uid):
        self.uac = UserAsCodeFull(user_id=uid)

    def ingest(self, turns, session_id="s1"):
        conv_text = "\n".join(turns)
        # Only extract state, skip archive
        if len(conv_text) > 15000:
            conv_text_trunc = conv_text[:15000]
        else:
            conv_text_trunc = conv_text
        self.uac._extract_structured_state(conv_text_trunc, session_id)

    def answer(self, question):
        context = self.uac.structured_state or "No state extracted."
        return answer_with_thinking(question, context)


class Mem0System:
    """Mem0 baseline."""
    name = "mem0"

    def __init__(self):
        from mem0 import Memory
        self._mem_class = Memory
        self.mem = None

    def reset(self, uid):
        self.uid = uid
        # Clean locks
        for p in [pathlib.Path('/tmp/qdrant/.lock'),
                  pathlib.Path.home() / '.mem0' / 'migrations_qdrant' / '.lock']:
            p.unlink(missing_ok=True)
        self.mem = self._mem_class()
        try:
            self.mem.delete_all(user_id=uid)
        except Exception:
            pass

    def ingest(self, turns, session_id="s1"):
        # Feed in batches to avoid overwhelming
        batch_size = 20
        for i in range(0, len(turns), batch_size):
            batch = turns[i:i+batch_size]
            batch_text = "\n".join(batch)
            try:
                self.mem.add(
                    [{"role": "user", "content": batch_text}],
                    user_id=self.uid,
                )
            except Exception as e:
                print(f"      Mem0 ingest error: {e}")

    def answer(self, question):
        try:
            # Search for relevant memories
            results = self.mem.search(question, user_id=self.uid)
            memories = []
            for r in results.get("results", results if isinstance(results, list) else []):
                if isinstance(r, dict):
                    memories.append(r.get("memory", str(r)))
                else:
                    memories.append(str(r))

            # Also get all memories for comprehensive context
            all_mems = self.mem.get_all(user_id=self.uid)
            for r in all_mems.get("results", []):
                mem = r.get("memory", str(r)) if isinstance(r, dict) else str(r)
                if mem not in memories:
                    memories.append(mem)

            context = "User memories:\n" + "\n".join(f"- {m}" for m in memories[:30])
        except Exception as e:
            context = f"Memory retrieval error: {e}"

        return answer_with_thinking(question, context)


class FullContextSystem:
    """Reference: full conversation in context."""
    name = "full_ctx"

    def __init__(self):
        self.context = ""

    def reset(self, uid):
        self.context = ""

    def ingest(self, turns, session_id="s1"):
        self.context += "\n".join(turns) + "\n"

    def answer(self, question):
        ctx = self.context
        if len(ctx) > 80000:
            ctx = ctx[:80000] + "\n... [truncated]"
        return answer_with_thinking(question, ctx)


class NoMemorySystem:
    """Lower bound: no context."""
    name = "no_mem"

    def reset(self, uid):
        pass

    def ingest(self, turns, session_id="s1"):
        pass

    def answer(self, question):
        return answer_with_thinking(question, "No stored information available.")


# ---------------------------------------------------------------------------
# LOCOMO evaluation
# ---------------------------------------------------------------------------

def run_locomo(systems, max_convs=2, max_qa=None):
    """Run LOCOMO evaluation."""
    data = load_locomo(max_convs)
    print(f"\n  LOCOMO: {len(data)} conversations, {sum(len(c['qa']) for c in data)} QA pairs")

    cat_names = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop", 5: "adversarial"}
    results = defaultdict(lambda: defaultdict(list))

    for ci, conv_data in enumerate(data):
        turns = locomo_conversation_to_turns(conv_data)
        qa_pairs = conv_data["qa"]
        if max_qa:
            qa_pairs = qa_pairs[:max_qa]
        sid = conv_data.get("sample_id", f"conv_{ci}")

        print(f"\n  Conv {ci+1}/{len(data)} ({sid}): {len(turns)} turns, {len(qa_pairs)} QAs")

        for sys in systems:
            sys_name = sys.name
            print(f"    {sys_name}: ingesting...", end="", flush=True)
            t0 = time.time()
            sys.reset(f"locomo_{sid}")

            # Ingest in session-like chunks
            chunk_size = 50
            for i in range(0, len(turns), chunk_size):
                session_chunk = turns[i:i+chunk_size]
                sys.ingest(session_chunk, session_id=f"s{i//chunk_size}")

            ingest_time = time.time() - t0
            print(f" ({ingest_time:.1f}s) answering...", end="", flush=True)

            t0 = time.time()
            f1_scores = []
            for qi, qa in enumerate(qa_pairs):
                question = qa["question"]
                gold = qa["answer"]
                cat = qa["category"]

                pred = sys.answer(question)
                f1 = compute_f1(pred, gold)
                f1_scores.append(f1)
                results[sys_name][cat].append(f1)
                results[sys_name]["overall"].append(f1)

                if qi % 50 == 0 and qi > 0:
                    print(f" {qi}", end="", flush=True)

                time.sleep(0.2)  # Rate limit

            answer_time = time.time() - t0
            avg_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0
            print(f" -> F1={avg_f1:.3f} ({len(f1_scores)}Q, {answer_time:.1f}s)")

    # Summary
    print(f"\n  {'System':<15}", end="")
    for cat_id in sorted(cat_names.keys()):
        print(f" {cat_names[cat_id]:>10}", end="")
    print(f" {'Overall':>10}")
    print(f"  {'-'*75}")

    summary = {}
    for sys in systems:
        sn = sys.name
        summary[sn] = {}
        print(f"  {sn:<15}", end="")
        for cat_id in sorted(cat_names.keys()):
            scores = results[sn].get(cat_id, [])
            avg = sum(scores) / len(scores) if scores else 0
            summary[sn][cat_names[cat_id]] = {"f1": round(avg, 3), "n": len(scores)}
            print(f" {avg:>10.3f}", end="")
        overall = results[sn].get("overall", [])
        avg_overall = sum(overall) / len(overall) if overall else 0
        summary[sn]["overall"] = {"f1": round(avg_overall, 3), "n": len(overall)}
        print(f" {avg_overall:>10.3f}")

    return summary


# ---------------------------------------------------------------------------
# LongMemEval evaluation
# ---------------------------------------------------------------------------

def run_longmemeval(systems, n_per_type=8):
    """Run LongMemEval stratified evaluation."""
    questions = load_longmemeval_stratified(n_per_type)
    print(f"\n  LongMemEval: {len(questions)} questions (stratified)")

    type_counts = defaultdict(int)
    for q in questions:
        type_counts[q["question_type"]] += 1
    for qt, c in sorted(type_counts.items()):
        print(f"    {qt}: {c}")

    results = defaultdict(lambda: defaultdict(list))

    for qi, q in enumerate(questions):
        qtype = q["question_type"]
        question = q["question"]
        gold = q["answer"]
        sessions = q.get("haystack_sessions", [])

        # Convert sessions to turns
        turns = []
        for si, session in enumerate(sessions):
            if isinstance(session, list):
                for turn in session:
                    if isinstance(turn, dict):
                        role = turn.get("role", "user")
                        content = turn.get("content", "")
                        turns.append(f"{role}: {content}")
            elif isinstance(session, str):
                turns.append(session)

        print(f"  [{qi+1}/{len(questions)}] {qtype[:15]:>15}", end="", flush=True)

        for sys in systems:
            sn = sys.name
            sys.reset(f"lme_{qi}")

            if turns:
                sys.ingest(turns, session_id=f"s{qi}")

            pred = sys.answer(question)
            correct = judge_answer(question, gold, pred)

            results[sn][qtype].append(1 if correct else 0)
            results[sn]["overall"].append(1 if correct else 0)

            tag = "Y" if correct else "N"
            print(f"  {sn[:6]}={tag}", end="", flush=True)

            time.sleep(0.3)

        print()

    # Summary
    qtypes = sorted(type_counts.keys())
    print(f"\n  {'System':<15}", end="")
    for qt in qtypes:
        print(f" {qt[:12]:>12}", end="")
    print(f" {'Overall':>10}")
    print(f"  {'-'*(15 + 13*len(qtypes) + 10)}")

    summary = {}
    for sys in systems:
        sn = sys.name
        summary[sn] = {}
        print(f"  {sn:<15}", end="")
        for qt in qtypes:
            scores = results[sn].get(qt, [])
            acc = sum(scores) / len(scores) if scores else 0
            summary[sn][qt] = {"accuracy": round(acc, 3), "n": len(scores)}
            print(f" {acc:>11.0%} ", end="")
        overall = results[sn].get("overall", [])
        acc = sum(overall) / len(overall) if overall else 0
        summary[sn]["overall"] = {"accuracy": round(acc, 3), "n": len(overall)}
        print(f" {acc:>9.0%}")

    return summary


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", choices=["locomo", "longmemeval", "both"], default="both")
    parser.add_argument("--locomo-convs", type=int, default=2)
    parser.add_argument("--locomo-max-qa", type=int, default=None)
    parser.add_argument("--lme-per-type", type=int, default=8)
    parser.add_argument("--systems", nargs="+",
                        default=["uac_full", "uac_state", "mem0", "full_ctx", "no_mem"],
                        choices=["uac_full", "uac_state", "mem0", "full_ctx", "no_mem"])
    args = parser.parse_args()

    # Initialize systems
    sys_map = {
        "uac_full": FullUACSystem,
        "uac_state": StateOnlyUACSystem,
        "mem0": Mem0System,
        "full_ctx": FullContextSystem,
        "no_mem": NoMemorySystem,
    }

    systems = []
    for sn in args.systems:
        try:
            sys = sys_map[sn]()
            systems.append(sys)
            print(f"  {sn}: initialized")
        except Exception as e:
            print(f"  {sn}: FAILED ({e})")

    print(f"\n{'='*70}")
    print(f"  Comprehensive Evaluation")
    print(f"  Model: {MODEL}")
    print(f"  Systems: {[s.name for s in systems]}")
    print(f"{'='*70}")

    all_results = {"model": MODEL, "timestamp": datetime.now().isoformat()}

    if args.benchmark in ("locomo", "both"):
        print(f"\n{'='*70}")
        print(f"  LOCOMO BENCHMARK")
        print(f"{'='*70}")
        locomo_results = run_locomo(systems, args.locomo_convs, args.locomo_max_qa)
        all_results["locomo"] = locomo_results

    if args.benchmark in ("longmemeval", "both"):
        print(f"\n{'='*70}")
        print(f"  LONGMEMEVAL BENCHMARK")
        print(f"{'='*70}")
        lme_results = run_longmemeval(systems, args.lme_per_type)
        all_results["longmemeval"] = lme_results

    # Save
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RESULTS_DIR / f"comprehensive_{ts}.json"
    with open(out, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  Saved to: {out}")


if __name__ == "__main__":
    main()
