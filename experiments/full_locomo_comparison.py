#!/usr/bin/env python3
"""
Full LOCOMO Benchmark Comparison — All Memory Systems
=====================================================
Compares: User as Code v2, SimpleMem, A-MEM, Mem0, Full Context
LLM: Gemini 3 Flash with thinking enabled
Metrics: Token F1 + LLM-as-Judge
Scale: 2 conversations, 60 QAs per conversation per system
"""

import json
import os
import re
import sys
import time
import traceback
import pathlib
from collections import defaultdict
from datetime import datetime

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "gemini-3-flash-preview"
DATA_PATH = pathlib.Path(__file__).parent.parent / "benchmarks" / "locomo" / "data" / "locomo10.json"
RESULTS_PATH = pathlib.Path(__file__).parent / "results" / "full_locomo_comparison.json"
RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

MAX_CONVERSATIONS = 2
MAX_QA_PER_CONV = 60

from google import genai
gclient = genai.Client()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def token_f1(prediction: str, gold: str) -> float:
    """Token-level F1 using word set overlap."""
    pred_tokens = set(re.findall(r'\b\w+\b', str(prediction).lower()))
    gold_tokens = set(re.findall(r'\b\w+\b', str(gold).lower()))
    if not gold_tokens:
        return 1.0 if not pred_tokens else 0.0
    if not pred_tokens:
        return 0.0
    overlap = pred_tokens & gold_tokens
    if not overlap:
        return 0.0
    precision = len(overlap) / len(pred_tokens)
    recall = len(overlap) / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)

def gemini_call(contents, system_instruction=None, thinking_budget=2048, temperature=1.0, max_retries=3):
    """Call Gemini with thinking enabled and retry logic."""
    config = genai.types.GenerateContentConfig(
        thinking_config=genai.types.ThinkingConfig(thinking_budget=thinking_budget),
        temperature=temperature,
    )
    if system_instruction:
        config.system_instruction = system_instruction

    for attempt in range(max_retries):
        try:
            response = gclient.models.generate_content(
                model=MODEL,
                contents=contents,
                config=config,
            )
            return response.text.strip()
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                wait = 15 * (attempt + 1)
                log(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            elif "500" in err or "503" in err:
                wait = 10 * (attempt + 1)
                log(f"  Server error, retrying in {wait}s...")
                time.sleep(wait)
            else:
                log(f"  Gemini error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                else:
                    raise
    raise RuntimeError("Max retries exceeded")

def gemini_call_no_thinking(contents, system_instruction=None, temperature=0.1, max_output_tokens=500, max_retries=3):
    """Call Gemini WITHOUT thinking for ingestion tasks."""
    config = genai.types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )
    if system_instruction:
        config.system_instruction = system_instruction

    for attempt in range(max_retries):
        try:
            response = gclient.models.generate_content(
                model=MODEL,
                contents=contents,
                config=config,
            )
            return response.text.strip()
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                wait = 15 * (attempt + 1)
                log(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            elif "500" in err or "503" in err:
                wait = 10 * (attempt + 1)
                log(f"  Server error, retrying in {wait}s...")
                time.sleep(wait)
            else:
                if attempt < max_retries - 1:
                    time.sleep(5)
                else:
                    raise
    raise RuntimeError("Max retries exceeded")

def extract_concise_answer(text: str) -> str:
    """Extract last line of multi-line answer as the concise answer."""
    lines = [l.strip() for l in str(text).split('\n') if l.strip()]
    return lines[-1] if lines else str(text)

def answer_question(question: str, context: str) -> str:
    """Answer a question given context, using thinking."""
    system = f"""You have access to stored information about a conversation between two people.
Use ONLY the provided context to answer questions.
Think through the information carefully, then provide ONLY the final answer as a short phrase on the last line.
If the question asks about a date, resolve relative dates using conversation timestamps.
If the information is not available in the context, say "No information available".

Context:
{context}"""

    response = gemini_call(
        contents=f"{question}\n\nThink carefully, then give ONLY a concise final answer.",
        system_instruction=system,
        thinking_budget=2048,
        temperature=1.0,
    )
    return extract_concise_answer(response)

def judge_answer(question: str, prediction: str, gold: str) -> tuple:
    """LLM-as-Judge: generous scoring. Returns (correct: bool, explanation: str)."""
    prompt = f"""You are a generous judge evaluating question answering accuracy.

Question: {question}
Gold answer: {gold}
Predicted answer: {prediction}

Judge whether the predicted answer is CORRECT or WRONG.
Be generous: CORRECT if it conveys the same core information, even with different wording or format.
WRONG only if factually wrong or says not available when gold has answer.

Respond with exactly one line: CORRECT or WRONG, followed by a brief explanation."""

    response = gemini_call(
        contents=prompt,
        thinking_budget=256,
        temperature=1.0,
    )
    text = response.upper()
    correct = "CORRECT" in text.split('\n')[0] if text else False
    return correct, response

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_conversations():
    """Load LOCOMO conversations."""
    with open(DATA_PATH) as f:
        data = json.load(f)
    return data[:MAX_CONVERSATIONS]

def get_sessions(conv):
    """Extract ordered sessions from a conversation."""
    c = conv['conversation']
    session_keys = sorted(
        [k for k in c.keys() if re.match(r'^session_\d+$', k)],
        key=lambda x: int(x.split('_')[1])
    )
    sessions = []
    for sk in session_keys:
        date_key = f"{sk}_date_time"
        date = c.get(date_key, "")
        turns = c[sk]  # list of {"speaker": ..., "dia_id": ..., "text": ...}
        sessions.append({
            "session_id": sk,
            "date": date,
            "turns": turns,
        })
    return sessions

def build_full_text(sessions):
    """Build full conversation text from all sessions."""
    parts = []
    for s in sessions:
        header = f"=== {s['session_id']} ({s['date']}) ==="
        turn_lines = [f"{t['speaker']}: {t['text']}" for t in s['turns']]
        parts.append(header + "\n" + "\n".join(turn_lines))
    return "\n\n".join(parts)

# ---------------------------------------------------------------------------
# Memory System Wrappers
# ---------------------------------------------------------------------------

class UserAsCodeV2System:
    """Wrapper for User as Code v2."""
    name = "user_as_code_v2"

    def __init__(self):
        sys.path.insert(0, str(pathlib.Path(__file__).parent))
        from user_as_code_v2 import UserAsCodeV2
        self.system = None
        self.cls = UserAsCodeV2

    def ingest(self, sessions, conv_id):
        self.system = self.cls(user_id=f"locomo_{conv_id}")
        for s in sessions:
            turn_lines = [f"{t['speaker']}: {t['text']}" for t in s['turns']]
            self.system.ingest_session(turn_lines, s['session_id'], s['date'])
            log(f"    UAC v2: ingested {s['session_id']}")

    def answer(self, question):
        context = self.system.retrieve(question)
        return answer_question(question, context)

    def reset(self):
        if self.system:
            self.system.reset()


class SimpleMemSystem:
    """Wrapper for SimpleMem."""
    name = "simplemem"

    def __init__(self):
        import simplemem
        self.simplemem = simplemem
        # Fix model: default gpt-4.1-mini is not accessible, use gpt-4o-mini
        cfg = simplemem.get_config()
        cfg.llm_model = 'gpt-4o-mini'
        simplemem.set_config(cfg)
        self.system = None

    def ingest(self, sessions, conv_id):
        self.system = self.simplemem.create_system(clear_db=True)
        dia_id = 0
        for s in sessions:
            for t in s['turns']:
                self.system.add_dialogue(
                    speaker=t['speaker'],
                    content=t['text'],
                    timestamp=s['date'],
                )
                dia_id += 1
            log(f"    SimpleMem: ingested {s['session_id']}")
        log("    SimpleMem: finalizing...")
        self.system.finalize()
        log("    SimpleMem: finalized")

    def answer(self, question):
        # SimpleMem has its own ask() that does retrieval + answering
        # But we want to control the answering with our own prompt for fair comparison
        # Try to use its vector store for retrieval directly
        try:
            results = self.system.hybrid_retriever.retrieve(question)
            if results:
                parts = []
                for r in results:
                    # Results could be dicts, objects with various attributes
                    if isinstance(r, dict):
                        text = r.get('content', r.get('text', r.get('memory_text', str(r))))
                    elif hasattr(r, 'content'):
                        text = r.content
                    elif hasattr(r, 'memory_text'):
                        text = r.memory_text
                    elif hasattr(r, 'text'):
                        text = r.text
                    else:
                        text = str(r)
                    parts.append(str(text))
                context = "\n\n".join(parts)
                return answer_question(question, context)
        except Exception as e:
            log(f"    SimpleMem retriever error: {e}")
        # Fallback: use ask() which does its own answering
        return extract_concise_answer(self.system.ask(question))

    def reset(self):
        self.system = None


class AMemSystem:
    """Wrapper for A-MEM (Agentic Memory)."""
    name = "a_mem"

    def __init__(self):
        from agentic_memory.memory_system import AgenticMemorySystem
        self.cls = AgenticMemorySystem
        self.memory = None

    def ingest(self, sessions, conv_id):
        self.memory = self.cls(
            model_name='all-MiniLM-L6-v2',
            llm_backend="openai",
            llm_model="gpt-4o-mini",
        )
        for s in sessions:
            # Build session text and add as a note
            session_text = f"[{s['date']}] " + " ".join(
                f"{t['speaker']}: {t['text']}" for t in s['turns']
            )
            # A-MEM works with notes - add each session as a note
            self.memory.add_note(session_text)
            log(f"    A-MEM: ingested {s['session_id']}")

    def answer(self, question):
        results = self.memory.search_agentic(question, k=10)
        if results:
            context = "\n\n".join([
                getattr(r, 'content', getattr(r, 'text', str(r)))
                if hasattr(r, 'content') or hasattr(r, 'text')
                else str(r)
                for r in results
            ])
        else:
            context = "No relevant information found."
        return answer_question(question, context)

    def reset(self):
        self.memory = None


class Mem0System:
    """Wrapper for Mem0."""
    name = "mem0"

    def _clean_locks(self):
        for p in [
            pathlib.Path('/tmp/qdrant/.lock'),
            pathlib.Path.home() / '.mem0' / 'migrations_qdrant' / '.lock',
        ]:
            p.unlink(missing_ok=True)

    def __init__(self):
        self._clean_locks()
        from mem0 import Memory
        self.cls = Memory
        self.m = None
        self.uid = None

    def ingest(self, sessions, conv_id):
        self._clean_locks()
        self.m = self.cls()
        self.uid = f"locomo_{conv_id}_{int(time.time())}"
        for s in sessions:
            # Batch turns into session-level messages to speed up ingestion
            session_text = f"[{s['date']}] " + " ".join(
                f"{t['speaker']}: {t['text']}" for t in s['turns']
            )
            try:
                self.m.add(
                    [{"role": "user", "content": session_text}],
                    user_id=self.uid,
                )
            except Exception as e:
                log(f"    Mem0: error ingesting {s['session_id']}: {e}")
            log(f"    Mem0: ingested {s['session_id']}")

    def answer(self, question):
        results = self.m.search(question, user_id=self.uid)
        if results and isinstance(results, dict) and 'results' in results:
            memories = results['results']
        elif results and isinstance(results, list):
            memories = results
        else:
            memories = []

        if memories:
            context = "\n".join([
                m.get('memory', m.get('text', str(m))) if isinstance(m, dict) else str(m)
                for m in memories
            ])
        else:
            context = "No relevant information found."
        return answer_question(question, context)

    def reset(self):
        if self.m and self.uid:
            try:
                self.m.delete_all(user_id=self.uid)
            except Exception:
                pass
        self.m = None


class FullContextSystem:
    """Baseline: pass all conversation text to LLM."""
    name = "full_context"

    def __init__(self):
        self.full_text = ""

    def ingest(self, sessions, conv_id):
        self.full_text = build_full_text(sessions)
        log(f"    Full Context: loaded {len(self.full_text)} chars")

    def answer(self, question):
        return answer_question(question, self.full_text)

    def reset(self):
        self.full_text = ""


# ---------------------------------------------------------------------------
# Main benchmark runner
# ---------------------------------------------------------------------------

def run_benchmark():
    log("=" * 70)
    log("FULL LOCOMO COMPARISON — ALL MEMORY SYSTEMS")
    log("=" * 70)

    conversations = load_conversations()
    log(f"Loaded {len(conversations)} conversations")

    systems = [
        ("user_as_code_v2", UserAsCodeV2System),
        ("simplemem", SimpleMemSystem),
        ("a_mem", AMemSystem),
        ("mem0", Mem0System),
        ("full_context", FullContextSystem),
    ]

    # Resume from previous run if available
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH) as f:
            all_results = json.load(f)
        log(f"Resuming from previous run. Already completed: {list(all_results.get('systems', {}).keys())}")
    else:
        all_results = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "model": MODEL,
                "max_conversations": MAX_CONVERSATIONS,
                "max_qa_per_conv": MAX_QA_PER_CONV,
                "thinking_budget_answer": 2048,
                "thinking_budget_judge": 256,
            },
            "systems": {},
        }

    for sys_name, sys_cls in systems:
        # Skip already completed systems
        if sys_name in all_results.get("systems", {}) and all_results["systems"][sys_name].get("average", {}):
            prev = all_results["systems"][sys_name]["average"]
            log(f"\n  SKIPPING {sys_name} (already completed: F1={prev.get('f1', 0):.3f}, Judge={prev.get('judge_accuracy', 0):.3f})")
            continue

        log(f"\n{'='*60}")
        log(f"SYSTEM: {sys_name}")
        log(f"{'='*60}")

        system_results = {
            "conversations": {},
            "per_conversation": {},
            "average": {},
            "errors": [],
        }

        try:
            system_obj = sys_cls()
        except Exception as e:
            log(f"  FAILED to initialize {sys_name}: {e}")
            traceback.print_exc()
            system_results["errors"].append(f"Init failed: {e}")
            all_results["systems"][sys_name] = system_results
            continue

        total_f1 = []
        total_judge = []
        category_f1 = defaultdict(list)
        category_judge = defaultdict(list)

        for conv_idx, conv in enumerate(conversations):
            conv_id = conv.get('sample_id', f'conv_{conv_idx}')
            log(f"\n  --- Conversation {conv_idx}: {conv_id} ---")

            sessions = get_sessions(conv)
            log(f"  {len(sessions)} sessions")

            # Ingest
            try:
                t0 = time.time()
                system_obj.ingest(sessions, conv_id)
                ingest_time = time.time() - t0
                log(f"  Ingestion complete in {ingest_time:.1f}s")
            except Exception as e:
                log(f"  INGEST FAILED for {sys_name}/{conv_id}: {e}")
                traceback.print_exc()
                system_results["errors"].append(f"Ingest {conv_id}: {e}")
                try:
                    system_obj.reset()
                except Exception:
                    pass
                continue

            # QA
            qa_pairs = conv['qa'][:MAX_QA_PER_CONV]
            log(f"  Evaluating {len(qa_pairs)} QAs...")

            conv_results = []
            conv_f1 = []
            conv_judge = []

            for qi, qa in enumerate(qa_pairs):
                question = qa['question']
                gold = str(qa['answer'])
                category = qa.get('category', 0)

                try:
                    t0 = time.time()
                    prediction = system_obj.answer(question)
                    answer_time = time.time() - t0

                    # Token F1
                    f1 = token_f1(prediction, gold)

                    # LLM Judge
                    try:
                        correct, explanation = judge_answer(question, prediction, gold)
                    except Exception as je:
                        log(f"    Judge error Q{qi}: {je}")
                        correct = False
                        explanation = f"Judge error: {je}"

                    result = {
                        "question": question,
                        "gold": gold,
                        "prediction": prediction,
                        "category": category,
                        "f1": f1,
                        "judge_correct": correct,
                        "judge_explanation": explanation,
                        "answer_time": answer_time,
                    }
                    conv_results.append(result)
                    conv_f1.append(f1)
                    conv_judge.append(1.0 if correct else 0.0)
                    total_f1.append(f1)
                    total_judge.append(1.0 if correct else 0.0)
                    category_f1[category].append(f1)
                    category_judge[category].append(1.0 if correct else 0.0)

                    status = "OK" if correct else "WRONG"
                    log(f"    Q{qi+1}/{len(qa_pairs)} cat={category} F1={f1:.2f} Judge={status} [{answer_time:.1f}s] {question[:50]}...")

                except Exception as e:
                    log(f"    Q{qi+1} ERROR: {e}")
                    conv_results.append({
                        "question": question,
                        "gold": gold,
                        "prediction": f"ERROR: {e}",
                        "category": category,
                        "f1": 0.0,
                        "judge_correct": False,
                        "error": str(e),
                    })
                    conv_f1.append(0.0)
                    conv_judge.append(0.0)
                    total_f1.append(0.0)
                    total_judge.append(0.0)

                # Brief pause to avoid rate limits
                time.sleep(0.3)

            # Per-conversation stats
            avg_f1 = sum(conv_f1) / len(conv_f1) if conv_f1 else 0.0
            avg_judge = sum(conv_judge) / len(conv_judge) if conv_judge else 0.0
            log(f"  Conv {conv_id}: F1={avg_f1:.3f}, Judge={avg_judge:.3f} ({sum(conv_judge):.0f}/{len(conv_judge)})")

            system_results["conversations"][conv_id] = conv_results
            system_results["per_conversation"][conv_id] = {
                "f1": avg_f1,
                "judge_accuracy": avg_judge,
                "n_questions": len(conv_results),
            }

            # Reset for next conversation
            try:
                system_obj.reset()
            except Exception:
                pass

        # System-level averages
        if total_f1:
            system_results["average"] = {
                "f1": sum(total_f1) / len(total_f1),
                "judge_accuracy": sum(total_judge) / len(total_judge),
                "n_questions": len(total_f1),
            }
            # Per-category
            system_results["per_category"] = {}
            for cat in sorted(category_f1.keys()):
                system_results["per_category"][str(cat)] = {
                    "f1": sum(category_f1[cat]) / len(category_f1[cat]),
                    "judge_accuracy": sum(category_judge[cat]) / len(category_judge[cat]),
                    "n": len(category_f1[cat]),
                }

            log(f"\n  SYSTEM {sys_name} AVERAGE: F1={system_results['average']['f1']:.3f}, Judge={system_results['average']['judge_accuracy']:.3f}")
            for cat in sorted(category_f1.keys()):
                c = system_results['per_category'][str(cat)]
                log(f"    Cat {cat}: F1={c['f1']:.3f}, Judge={c['judge_accuracy']:.3f} (n={c['n']})")

        all_results["systems"][sys_name] = system_results

        # Save intermediate results
        with open(RESULTS_PATH, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        log(f"  Intermediate results saved to {RESULTS_PATH}")

    # ---------------------------------------------------------------------------
    # Final Summary
    # ---------------------------------------------------------------------------
    log(f"\n{'='*70}")
    log("FINAL SUMMARY")
    log(f"{'='*70}")

    header = f"{'System':<20} {'F1':>8} {'Judge':>8} {'N':>6}"
    log(header)
    log("-" * len(header))
    for sys_name in [s[0] for s in systems]:
        sr = all_results["systems"].get(sys_name, {})
        avg = sr.get("average", {})
        if avg:
            log(f"{sys_name:<20} {avg['f1']:>8.3f} {avg['judge_accuracy']:>8.3f} {avg['n_questions']:>6}")
        else:
            log(f"{sys_name:<20} {'FAILED':>8} {'':>8} {'':>6}")

    log(f"\nPer-Category Breakdown:")
    cat_names = {1: "Multi-hop", 2: "Temporal", 3: "Open-domain", 4: "Single-hop", 5: "Adversarial"}
    for cat in [1, 2, 3, 4, 5]:
        log(f"\n  Category {cat} ({cat_names.get(cat, '?')}):")
        header = f"    {'System':<20} {'F1':>8} {'Judge':>8} {'N':>6}"
        log(header)
        for sys_name in [s[0] for s in systems]:
            sr = all_results["systems"].get(sys_name, {})
            pc = sr.get("per_category", {}).get(str(cat), {})
            if pc:
                log(f"    {sys_name:<20} {pc['f1']:>8.3f} {pc['judge_accuracy']:>8.3f} {pc['n']:>6}")

    # Final save
    with open(RESULTS_PATH, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    log(f"\nResults saved to {RESULTS_PATH}")


if __name__ == "__main__":
    run_benchmark()
