#!/usr/bin/env python3
"""
SOTA Comparison: LOCOMO Benchmark Evaluation

Compares four memory systems on the LOCOMO benchmark:
  1. SimpleMem (pip install simplemem)    — published LOCOMO F1=43.24%
  2. OMEGA (pip install omega-memory)     — published 95.4% LongMemEval
  3. User as Code v2                      — our system
  4. Mem0 (from mem0 import Memory)       — published 64% LOCOMO

Scoring:
  a. Token F1 (stemmed word overlap)
  b. LLM-as-Judge accuracy using OpenAI GPT-4o-mini

All answer generation uses GPT-4o-mini as backbone for fair comparison.
"""

import json
import os
import re
import sys
import time
import hashlib
import pathlib
import string
import traceback
from collections import Counter, defaultdict
from datetime import datetime

# ---------------------------------------------------------------------------
# Clean Qdrant locks before any mem0 import
# ---------------------------------------------------------------------------
for p in [pathlib.Path('/tmp/qdrant/.lock'),
          pathlib.Path.home() / '.mem0' / 'migrations_qdrant' / '.lock']:
    p.unlink(missing_ok=True)

# ---------------------------------------------------------------------------
# OpenAI setup (backbone for all answer generation + judge)
# ---------------------------------------------------------------------------
from openai import OpenAI
oai_client = OpenAI()
OPENAI_MODEL = "gpt-4o-mini"

LOCOMO_DATA = pathlib.Path(__file__).parent.parent / "benchmarks" / "locomo" / "data" / "locomo10.json"
RESULTS_DIR = pathlib.Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

MAX_CONVS = 2
MAX_QA = 60


# ---------------------------------------------------------------------------
# OpenAI helpers
# ---------------------------------------------------------------------------

def openai_chat(messages, temperature=0, max_tokens=1024):
    """Wrapper for OpenAI chat completions."""
    for attempt in range(3):
        try:
            resp = oai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            if attempt < 2:
                time.sleep(1.0 * (attempt + 1))
            else:
                raise


def answer_with_openai(question, context):
    """Generate an answer from context using GPT-4o-mini."""
    system = """You have access to stored information about a conversation between two people.
Use ONLY the provided context to answer questions.
Think carefully, then provide ONLY the final answer as a short phrase on the last line.
Resolve relative dates using conversation timestamps.
If information is not available, say "No information available".

Context:
""" + context

    try:
        text = openai_chat([
            {"role": "system", "content": system},
            {"role": "user", "content": f"{question}\n\nThink carefully, then give ONLY a concise final answer."},
        ], temperature=0, max_tokens=300)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        return lines[-1] if len(lines) > 1 else text
    except Exception as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

try:
    from nltk.stem import PorterStemmer
    _stemmer = PorterStemmer()
    def stem(w):
        return _stemmer.stem(w)
except ImportError:
    def stem(w):
        return w.lower()


def normalize_answer(s: str) -> str:
    """Normalize answer string for F1 comparison."""
    s = s.replace(",", "")
    s = re.sub(r'\b(a|an|the|and)\b', ' ', s.lower())
    s = ''.join(ch for ch in s if ch not in string.punctuation)
    return ' '.join(s.split())


def compute_f1(pred: str, ref: str) -> float:
    """Stemmed token-level F1 score."""
    pred_tokens = [stem(w) for w in normalize_answer(str(pred)).split()]
    ref_tokens = [stem(w) for w in normalize_answer(str(ref)).split()]
    if not ref_tokens:
        return 1.0 if not pred_tokens else 0.0
    if not pred_tokens:
        return 0.0
    common = Counter(pred_tokens) & Counter(ref_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0
    precision = num_same / len(pred_tokens)
    recall = num_same / len(ref_tokens)
    return (2 * precision * recall) / (precision + recall)


def judge_answer(question: str, gold: str, pred: str) -> bool:
    """LLM-as-Judge binary accuracy using GPT-4o-mini."""
    try:
        resp = openai_chat([
            {"role": "user", "content": f"""Is this answer correct given the gold answer? Consider semantic equivalence. Answer yes or no.

Question: {question}
Gold answer: {gold}
Predicted answer: {pred}

Answer ONLY "yes" or "no"."""},
        ], temperature=0, max_tokens=10)
        return resp.strip().lower().startswith("yes")
    except Exception:
        return False


# ---------------------------------------------------------------------------
# LOCOMO data loading
# ---------------------------------------------------------------------------

def load_locomo(max_convs=MAX_CONVS):
    with open(LOCOMO_DATA) as f:
        return json.load(f)[:max_convs]


def parse_sessions(conv_data):
    """Parse LOCOMO conversation into list of (session_id, date, turns_list)."""
    conversation = conv_data.get("conversation", {})
    sessions = []
    session_keys = sorted(
        [k for k in conversation.keys()
         if k.startswith("session_") and not k.endswith("_date_time")
         and isinstance(conversation[k], list)],
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


# ===========================================================================
# System Wrappers
# ===========================================================================

class SystemWrapper:
    """Base class for memory system wrappers."""
    name = "base"

    def reset(self):
        raise NotImplementedError

    def ingest_sessions(self, sessions):
        """Ingest list of (session_id, date, turns_list)."""
        raise NotImplementedError

    def answer_question(self, question):
        """Return a string answer."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# 1. SimpleMem
# ---------------------------------------------------------------------------

class SimpleMemWrapper(SystemWrapper):
    name = "SimpleMem"

    def __init__(self):
        self._available = False
        self._system = None
        try:
            import simplemem
            self._simplemem = simplemem
            self._available = True
            print("  [SimpleMem] imported successfully")
        except Exception as e:
            print(f"  [SimpleMem] import FAILED: {e}")

    def reset(self):
        if not self._available:
            return
        try:
            # Create fresh config with unique table name
            cfg = self._simplemem.SimpleMemConfig(
                llm_model='gpt-4o-mini',
                lancedb_path=f'./lancedb_simplemem_{int(time.time())}',
                memory_table_name=f'sm_{int(time.time())}',
            )
            self._simplemem.set_config(cfg)
            self._system = self._simplemem.create_system()
        except Exception as e:
            print(f"    [SimpleMem] reset error: {e}")
            self._system = None

    def ingest_sessions(self, sessions):
        if not self._available or self._system is None:
            return
        for session_id, date, turns in sessions:
            for turn in turns:
                parts = turn.split(":", 1)
                speaker = parts[0].strip() if len(parts) > 1 else "Unknown"
                content = parts[1].strip() if len(parts) > 1 else turn
                try:
                    self._system.add_dialogue(
                        speaker=speaker,
                        content=content,
                        timestamp=date if date else None,
                    )
                except Exception as e:
                    pass  # Continue on individual turn errors
        try:
            self._system.finalize()
        except Exception:
            pass

    def answer_question(self, question):
        if not self._available or self._system is None:
            return "System unavailable"
        try:
            # SimpleMem has its own ask() which uses its built-in LLM pipeline
            answer = self._system.ask(question)
            return answer
        except Exception as e:
            return f"Error: {e}"


# ---------------------------------------------------------------------------
# 2. OMEGA
# ---------------------------------------------------------------------------

class OmegaWrapper(SystemWrapper):
    name = "OMEGA"

    def __init__(self):
        self._available = False
        self._entity_id = None
        try:
            import omega
            self._omega = omega
            self._available = True
            print("  [OMEGA] imported successfully")
        except Exception as e:
            print(f"  [OMEGA] import FAILED: {e}")

    def reset(self):
        if not self._available:
            return
        # Use unique entity_id per conversation to isolate data
        self._entity_id = f"locomo_{int(time.time() * 1000)}"

    def ingest_sessions(self, sessions):
        if not self._available:
            return
        for session_id, date, turns in sessions:
            # Store each session as a batch
            session_text = "\n".join(turns)
            # Chunk into reasonable sizes for omega
            chunk_size = 500  # words
            words = session_text.split()
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i + chunk_size])
                try:
                    self._omega.store(
                        content=chunk,
                        event_type='conversation',
                        session_id=session_id,
                        entity_id=self._entity_id,
                        metadata={"date": date, "session": session_id},
                    )
                except Exception as e:
                    pass

    def answer_question(self, question):
        if not self._available:
            return "System unavailable"
        try:
            # Retrieve from omega
            result = self._omega.query(
                query_text=question,
                limit=10,
                entity_id=self._entity_id,
            )
            # Also try phrase search as fallback
            if "No matching memories" in str(result) or not result.strip():
                try:
                    result = self._omega.phrase_search(question)
                except Exception:
                    pass
            # Use GPT-4o-mini to generate answer from retrieved context
            context = str(result) if result else "No memories found."
            return answer_with_openai(question, context)
        except Exception as e:
            return f"Error: {e}"


# ---------------------------------------------------------------------------
# 3. User as Code v2
# ---------------------------------------------------------------------------

class UserAsCodeV2Wrapper(SystemWrapper):
    name = "UaC_v2"

    def __init__(self):
        self._available = False
        self._v2 = None
        try:
            # Import UserAsCodeV2 from the v2 module
            # We re-implement with OpenAI backbone for fair comparison
            sys.path.insert(0, str(pathlib.Path(__file__).parent))
            from eval_v2_openai import UserAsCodeV2OpenAI
            self._V2Class = UserAsCodeV2OpenAI
            self._available = True
            print("  [UaC_v2] imported successfully (OpenAI backbone)")
        except Exception as e:
            print(f"  [UaC_v2] import FAILED: {e}")
            traceback.print_exc()

    def reset(self):
        if not self._available:
            return
        uid = f"sota_v2_{int(time.time())}"
        try:
            self._v2 = self._V2Class(uid)
        except Exception as e:
            print(f"    [UaC_v2] reset error: {e}")
            self._v2 = None

    def ingest_sessions(self, sessions):
        if not self._available or self._v2 is None:
            return
        for session_id, date, turns in sessions:
            try:
                self._v2.ingest_session(turns, session_id, date)
            except Exception as e:
                print(f"    [UaC_v2] ingest error on {session_id}: {e}")

    def answer_question(self, question):
        if not self._available or self._v2 is None:
            return "System unavailable"
        try:
            return self._v2.answer(question)
        except Exception as e:
            return f"Error: {e}"


# ---------------------------------------------------------------------------
# 4. Mem0
# ---------------------------------------------------------------------------

class Mem0Wrapper(SystemWrapper):
    name = "Mem0"

    def __init__(self):
        self._available = False
        self._memory = None
        self._user_id = None
        try:
            # Clean locks first
            for p in [pathlib.Path('/tmp/qdrant/.lock'),
                      pathlib.Path.home() / '.mem0' / 'migrations_qdrant' / '.lock']:
                p.unlink(missing_ok=True)
            from mem0 import Memory
            self._MemClass = Memory
            self._available = True
            print("  [Mem0] imported successfully")
        except Exception as e:
            print(f"  [Mem0] import FAILED: {e}")

    def reset(self):
        if not self._available:
            return
        try:
            # Clean locks again
            for p in [pathlib.Path('/tmp/qdrant/.lock'),
                      pathlib.Path.home() / '.mem0' / 'migrations_qdrant' / '.lock']:
                p.unlink(missing_ok=True)
            self._memory = self._MemClass()
            self._user_id = f"locomo_mem0_{int(time.time())}"
            try:
                self._memory.delete_all(user_id=self._user_id)
            except Exception:
                pass
        except Exception as e:
            print(f"    [Mem0] reset error: {e}")
            self._memory = None

    def ingest_sessions(self, sessions):
        if not self._available or self._memory is None:
            return
        all_turns = []
        for _, _, turns in sessions:
            all_turns.extend(turns)

        # Ingest in batches of ~20 turns
        batch_size = 20
        for i in range(0, len(all_turns), batch_size):
            batch_text = "\n".join(all_turns[i:i + batch_size])
            try:
                self._memory.add(
                    [{"role": "user", "content": batch_text}],
                    user_id=self._user_id,
                )
            except Exception as e:
                pass

    def answer_question(self, question):
        if not self._available or self._memory is None:
            return "System unavailable"
        try:
            results = self._memory.search(question, user_id=self._user_id)
            memories = []
            if isinstance(results, dict):
                for r in results.get("results", []):
                    memories.append(r.get("memory", str(r)) if isinstance(r, dict) else str(r))
            elif isinstance(results, list):
                for r in results:
                    memories.append(r.get("memory", str(r)) if isinstance(r, dict) else str(r))

            # Also get all memories for broader context
            try:
                all_m = self._memory.get_all(user_id=self._user_id)
                for r in (all_m.get("results", []) if isinstance(all_m, dict) else all_m):
                    m = r.get("memory", str(r)) if isinstance(r, dict) else str(r)
                    if m not in memories:
                        memories.append(m)
            except Exception:
                pass

            context = "\n".join(f"- {m}" for m in memories[:30]) if memories else "No memories found."
            return answer_with_openai(question, context)
        except Exception as e:
            return f"Error: {e}"


# ===========================================================================
# Main evaluation
# ===========================================================================

def run_sota_comparison():
    """Run the full SOTA comparison on LOCOMO benchmark."""
    print(f"\n{'='*72}")
    print(f"  LOCOMO SOTA Comparison")
    print(f"  Backbone: OpenAI {OPENAI_MODEL}")
    print(f"  Conversations: {MAX_CONVS}, Max QAs/conv: {MAX_QA}")
    print(f"  Timestamp: {datetime.now().isoformat()}")
    print(f"{'='*72}")

    # Load data
    data = load_locomo(MAX_CONVS)
    print(f"\n  Loaded {len(data)} conversations from LOCOMO")
    for i, d in enumerate(data):
        conv = d.get("conversation", {})
        n_qa = len(d.get("qa", []))
        sa = conv.get("speaker_a", "?")
        sb = conv.get("speaker_b", "?")
        print(f"    Conv {i+1}: {sa} & {sb}, {n_qa} QAs")

    # Initialize systems
    print(f"\n  Initializing systems...")
    systems = []
    for WrapperClass in [SimpleMemWrapper, OmegaWrapper, UserAsCodeV2Wrapper, Mem0Wrapper]:
        try:
            wrapper = WrapperClass()
            systems.append(wrapper)
        except Exception as e:
            print(f"  [{WrapperClass.name}] FAILED to initialize: {e}")

    available_systems = [s for s in systems if s._available]
    print(f"\n  Available systems: {[s.name for s in available_systems]}")
    if not available_systems:
        print("  ERROR: No systems available. Exiting.")
        return

    # Results storage
    per_question_log = []
    per_system_conv_f1 = defaultdict(lambda: defaultdict(list))  # system -> conv_idx -> [f1s]
    per_system_conv_judge = defaultdict(lambda: defaultdict(list))  # system -> conv_idx -> [judge]
    per_system_f1 = defaultdict(list)
    per_system_judge = defaultdict(list)
    system_errors = defaultdict(int)
    system_times = defaultdict(float)

    # Run evaluation
    for ci, conv_data in enumerate(data):
        sessions = parse_sessions(conv_data)
        qa_pairs = conv_data.get("qa", [])[:MAX_QA]
        sid = conv_data.get("sample_id", f"conv_{ci}")
        conv = conv_data.get("conversation", {})
        sa = conv.get("speaker_a", "?")
        sb = conv.get("speaker_b", "?")

        print(f"\n{'='*72}")
        print(f"  Conversation {ci+1}/{len(data)}: {sid} ({sa} & {sb})")
        print(f"  Sessions: {len(sessions)}, QAs: {len(qa_pairs)}")
        print(f"{'='*72}")

        for sys_obj in available_systems:
            sys_name = sys_obj.name
            print(f"\n  [{sys_name}] resetting...", end="", flush=True)

            try:
                sys_obj.reset()
            except Exception as e:
                print(f" RESET FAILED: {e}")
                system_errors[sys_name] += len(qa_pairs)
                continue

            # Ingest
            print(f" ingesting...", end="", flush=True)
            t0 = time.time()
            try:
                sys_obj.ingest_sessions(sessions)
            except Exception as e:
                print(f" INGEST FAILED: {e}")
                system_errors[sys_name] += len(qa_pairs)
                continue
            ingest_time = time.time() - t0
            system_times[sys_name] += ingest_time
            print(f" ({ingest_time:.0f}s)", end="", flush=True)

            # Answer QAs
            print(f" answering {len(qa_pairs)} QAs...", end="", flush=True)
            t0 = time.time()
            f1_scores = []
            judge_scores = []

            for qi, qa in enumerate(qa_pairs):
                gold = str(qa.get("answer", ""))
                question = qa["question"]
                category = qa.get("category", 0)

                try:
                    pred = sys_obj.answer_question(question)
                except Exception as e:
                    pred = f"Error: {e}"
                    system_errors[sys_name] += 1

                # Compute F1
                f1 = compute_f1(pred, gold)
                f1_scores.append(f1)

                # LLM-as-Judge
                judge = judge_answer(question, gold, pred)
                judge_scores.append(1 if judge else 0)

                # Log
                per_question_log.append({
                    "conv": sid,
                    "conv_idx": ci,
                    "qi": qi,
                    "system": sys_name,
                    "category": category,
                    "question": question,
                    "gold": gold,
                    "pred": pred,
                    "f1": round(f1, 4),
                    "judge": int(judge),
                })

                # Progress
                if (qi + 1) % 10 == 0:
                    print(f" {qi+1}", end="", flush=True)

                time.sleep(0.05)  # Rate limiting

            answer_time = time.time() - t0
            system_times[sys_name] += answer_time

            # Store per-conv results
            per_system_conv_f1[sys_name][ci] = f1_scores
            per_system_conv_judge[sys_name][ci] = judge_scores
            per_system_f1[sys_name].extend(f1_scores)
            per_system_judge[sys_name].extend(judge_scores)

            avg_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0
            avg_judge = sum(judge_scores) / len(judge_scores) if judge_scores else 0
            print(f"\n    -> F1={avg_f1:.3f}  Judge={avg_judge:.1%}  "
                  f"({len(f1_scores)} QAs, {answer_time:.0f}s)")

    # ===========================================================================
    # Results Table
    # ===========================================================================
    print(f"\n\n{'='*90}")
    print(f"  LOCOMO SOTA COMPARISON RESULTS")
    print(f"  Backbone: {OPENAI_MODEL}  |  {len(data)} conversations  |  {MAX_QA} QAs/conv max")
    print(f"{'='*90}\n")

    # Header
    header = f"  {'System':<15}"
    for ci in range(len(data)):
        header += f" {'F1(c'+str(ci+1)+')':>8}"
    header += f" {'F1(avg)':>8}"
    for ci in range(len(data)):
        header += f" {'Jdg(c'+str(ci+1)+')':>8}"
    header += f" {'Jdg(avg)':>9}"
    header += f" {'Time':>7}"
    print(header)
    print(f"  {'-'*(len(header)-2)}")

    results_table = {}
    for sys_obj in available_systems:
        sys_name = sys_obj.name
        row = f"  {sys_name:<15}"

        conv_f1s = []
        for ci in range(len(data)):
            scores = per_system_conv_f1[sys_name].get(ci, [])
            avg = sum(scores) / len(scores) if scores else 0
            conv_f1s.append(avg)
            row += f" {avg:>8.3f}"

        overall_f1 = sum(per_system_f1[sys_name]) / len(per_system_f1[sys_name]) if per_system_f1[sys_name] else 0
        row += f" {overall_f1:>8.3f}"

        conv_judges = []
        for ci in range(len(data)):
            scores = per_system_conv_judge[sys_name].get(ci, [])
            avg = sum(scores) / len(scores) if scores else 0
            conv_judges.append(avg)
            row += f" {avg:>7.1%}"

        overall_judge = sum(per_system_judge[sys_name]) / len(per_system_judge[sys_name]) if per_system_judge[sys_name] else 0
        row += f" {overall_judge:>8.1%}"

        total_time = system_times.get(sys_name, 0)
        row += f" {total_time:>6.0f}s"

        print(row)

        results_table[sys_name] = {
            "f1_per_conv": conv_f1s,
            "f1_avg": overall_f1,
            "judge_per_conv": conv_judges,
            "judge_avg": overall_judge,
            "n_questions": len(per_system_f1[sys_name]),
            "errors": system_errors.get(sys_name, 0),
            "time_seconds": total_time,
        }

    # Published reference
    print(f"\n  Published references:")
    print(f"  {'SimpleMem (pub)':.<15} F1=43.24%")
    print(f"  {'OMEGA (pub)':.<15} 95.4% LongMemEval")
    print(f"  {'Mem0 (pub)':.<15} F1=64% LOCOMO")

    # Category breakdown
    print(f"\n\n  Category Breakdown (F1):")
    cat_names = {1: "multi-hop", 2: "temporal", 3: "open-domain",
                 4: "single-hop", 5: "adversarial"}
    cat_header = f"  {'System':<15}"
    for cat in [1, 2, 3, 4, 5]:
        cat_header += f" {cat_names[cat]:>12}"
    print(cat_header)
    print(f"  {'-'*(len(cat_header)-2)}")

    for sys_obj in available_systems:
        sys_name = sys_obj.name
        row = f"  {sys_name:<15}"
        for cat in [1, 2, 3, 4, 5]:
            cat_qs = [q for q in per_question_log
                      if q["system"] == sys_name and q["category"] == cat]
            if cat_qs:
                avg = sum(q["f1"] for q in cat_qs) / len(cat_qs)
                row += f" {avg:>12.3f}"
            else:
                row += f" {'n/a':>12}"
        print(row)

    # ===========================================================================
    # Save results
    # ===========================================================================
    output = {
        "benchmark": "LOCOMO",
        "model": OPENAI_MODEL,
        "timestamp": datetime.now().isoformat(),
        "config": {
            "max_convs": MAX_CONVS,
            "max_qa_per_conv": MAX_QA,
            "scoring": ["token_f1_stemmed", "llm_judge_gpt4o_mini"],
        },
        "systems": results_table,
        "category_breakdown": {},
        "per_question": per_question_log,
    }

    # Category breakdown for JSON
    for sys_obj in available_systems:
        sys_name = sys_obj.name
        output["category_breakdown"][sys_name] = {}
        for cat in [1, 2, 3, 4, 5]:
            cat_qs = [q for q in per_question_log
                      if q["system"] == sys_name and q["category"] == cat]
            if cat_qs:
                output["category_breakdown"][sys_name][cat_names[cat]] = {
                    "f1": round(sum(q["f1"] for q in cat_qs) / len(cat_qs), 4),
                    "judge": round(sum(q["judge"] for q in cat_qs) / len(cat_qs), 4),
                    "n": len(cat_qs),
                }

    out_path = RESULTS_DIR / "sota_comparison_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")

    return output


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    output = run_sota_comparison()
