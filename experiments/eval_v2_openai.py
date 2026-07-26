"""
Evaluation of User as Code v2 on LOCOMO using OpenAI GPT-4o-mini
for all LLM calls (extraction, summarization, answering, judging).

This makes results directly comparable to published SOTA numbers
(MemMachine 91.7%, EverMemOS 93.05%, Mem0 66.9%) which use LLM-as-Judge.
"""

import json
import os
import re
import sys
import time
import hashlib
import pathlib
import traceback
from collections import defaultdict
from datetime import datetime

# ---------------------------------------------------------------------------
# Clean Qdrant locks before any mem0 import
# ---------------------------------------------------------------------------
for p in [pathlib.Path('/tmp/qdrant/.lock'),
          pathlib.Path.home() / '.mem0' / 'migrations_qdrant' / '.lock']:
    p.unlink(missing_ok=True)

# ---------------------------------------------------------------------------
# OpenAI setup
# ---------------------------------------------------------------------------
from openai import OpenAI
client = OpenAI()

OPENAI_MODEL = "gpt-4o-mini"
RESULTS_DIR = pathlib.Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def openai_chat(messages, temperature=0, max_tokens=1024):
    """Wrapper for OpenAI chat completions."""
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# UserAsCodeV2 with OpenAI backbone (adapted from user_as_code_v2.py)
# ---------------------------------------------------------------------------
import chromadb


class UserAsCodeV2OpenAI:
    """User as Code v2 with all LLM calls using OpenAI GPT-4o-mini."""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.structured_state = ""
        self.session_summaries = {}
        self.alerts = []

        self._chroma = chromadb.Client()
        uid_hash = hashlib.md5(user_id.encode()).hexdigest()[:8]

        for name in [f"v2o_episodes_{uid_hash}", f"v2o_summaries_{uid_hash}"]:
            try:
                self._chroma.delete_collection(name)
            except Exception:
                pass

        self._episodes = self._chroma.create_collection(
            name=f"v2o_episodes_{uid_hash}",
            metadata={"hnsw:space": "cosine"},
        )
        self._summaries = self._chroma.create_collection(
            name=f"v2o_summaries_{uid_hash}",
            metadata={"hnsw:space": "cosine"},
        )
        self._session_texts = {}

    def ingest_session(self, turns: list[str], session_id: str, session_date: str = ""):
        session_text = "\n".join(turns)
        self._session_texts[session_id] = session_text

        date_prefix = f"[{session_date}] " if session_date else ""
        chunks = self._smart_chunk(session_text, session_id, date_prefix,
                                   chunk_size=300, overlap=75)
        if chunks:
            self._episodes.add(
                documents=[c["text"] for c in chunks],
                ids=[c["id"] for c in chunks],
                metadatas=[{"session": session_id, "date": session_date}
                           for c in chunks],
            )

        summary = self._summarize_session(session_text, session_id, session_date)
        if summary:
            self.session_summaries[session_id] = summary
            self._summaries.add(
                documents=[summary],
                ids=[f"summary_{session_id}"],
                metadatas=[{"session": session_id, "date": session_date,
                            "type": "summary"}],
            )

        self._incremental_extract(session_text, session_id, session_date)

    def _smart_chunk(self, text, session_id, prefix, chunk_size=300, overlap=75):
        turn_pattern = re.compile(r'(?=\w+:)')
        segments = turn_pattern.split(text)
        segments = [s.strip() for s in segments if s.strip()]

        chunks = []
        current_chunk = []
        current_words = 0
        chunk_idx = 0

        for segment in segments:
            seg_words = len(segment.split())
            if current_words + seg_words > chunk_size and current_chunk:
                chunk_text = f"{prefix}{' '.join(current_chunk)}"
                chunks.append({
                    "id": f"{session_id}_chunk_{chunk_idx}",
                    "text": chunk_text,
                })
                chunk_idx += 1
                overlap_words = 0
                overlap_start = len(current_chunk)
                for j in range(len(current_chunk) - 1, -1, -1):
                    overlap_words += len(current_chunk[j].split())
                    if overlap_words >= overlap:
                        overlap_start = j
                        break
                current_chunk = current_chunk[overlap_start:]
                current_words = sum(len(s.split()) for s in current_chunk)

            current_chunk.append(segment)
            current_words += seg_words

        if current_chunk:
            chunk_text = f"{prefix}{' '.join(current_chunk)}"
            chunks.append({
                "id": f"{session_id}_chunk_{chunk_idx}",
                "text": chunk_text,
            })

        return chunks

    def _summarize_session(self, session_text, session_id, date):
        if len(session_text) < 50:
            return session_text

        text = session_text[:8000] if len(session_text) > 8000 else session_text

        try:
            return openai_chat([
                {"role": "system", "content": "You are a precise summarizer. Include ALL specific facts: names, dates, numbers, places, preferences, events, plans, and relationships. Do not omit any factual details."},
                {"role": "user", "content": f"Summarize this conversation session concisely.\n\nSession {session_id} ({date}):\n{text}\n\nSummary (include all facts):"},
            ], temperature=0.1, max_tokens=500)
        except Exception as e:
            return f"Session {session_id}: {session_text[:200]}"

    def _incremental_extract(self, session_text, session_id, date):
        text = session_text[:10000] if len(session_text) > 10000 else session_text

        prompt = f"""Update the structured Python state below with new information from this conversation session.
Preserve ALL existing information. Add new facts. Resolve conflicts (newer session wins).
Use typed Python with dates, lists, and dataclasses. Include ALL names, dates, numbers.

Current state:
{self.structured_state if self.structured_state else '# (empty -- initialize from this session)'}

New session ({session_id}, {date}):
{text}

Output ONLY updated Python code:"""

        try:
            new_state = openai_chat([
                {"role": "user", "content": prompt},
            ], temperature=0.1, max_tokens=4000)
            if "```python" in new_state:
                new_state = new_state.split("```python")[1].split("```")[0]
            elif "```" in new_state:
                new_state = new_state.split("```")[1].split("```")[0]
            self.structured_state = new_state.strip()
        except Exception:
            pass

    def retrieve(self, query: str, top_k: int = 8) -> str:
        parts = []

        if self.structured_state:
            parts.append("=== Structured State ===")
            state = self.structured_state
            if len(state) > 3000:
                state = state[:3000] + "\n# ... (truncated)"
            parts.append(state)

        if self._summaries.count() > 0:
            try:
                results = self._summaries.query(
                    query_texts=[query],
                    n_results=min(3, self._summaries.count()),
                )
                if results["documents"][0]:
                    parts.append("\n=== Relevant Session Summaries ===")
                    for doc in results["documents"][0]:
                        parts.append(doc)
            except Exception:
                pass

        if self._episodes.count() > 0:
            try:
                results = self._episodes.query(
                    query_texts=[query],
                    n_results=min(top_k, self._episodes.count()),
                )
                if results["documents"][0]:
                    parts.append("\n=== Relevant Conversation Excerpts ===")
                    seen = set()
                    for doc in results["documents"][0]:
                        doc_key = doc[:100]
                        if doc_key not in seen:
                            seen.add(doc_key)
                            parts.append(doc)
            except Exception:
                pass

        return "\n\n".join(parts)

    def answer(self, question: str) -> str:
        context = self.retrieve(question)

        system = f"""You have access to stored information about a conversation between two people.
Use ONLY the provided context to answer questions.
Think through the information carefully, then provide ONLY the final answer as a short phrase on the last line.
If the question asks about a date, resolve relative dates using conversation timestamps.
If the information is not available in the context, say "No information available".

Context:
{context}"""

        try:
            text = openai_chat([
                {"role": "system", "content": system},
                {"role": "user", "content": f"{question}\n\nThink carefully, then give ONLY a concise final answer."},
            ], temperature=0, max_tokens=300)
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            return lines[-1] if len(lines) > 1 else text
        except Exception as e:
            return f"Error: {e}"

    def reset(self):
        self.structured_state = ""
        self.session_summaries = {}
        self.alerts = []
        self._session_texts = {}
        uid_hash = hashlib.md5(self.user_id.encode()).hexdigest()[:8]
        for name in [f"v2o_episodes_{uid_hash}", f"v2o_summaries_{uid_hash}"]:
            try:
                self._chroma.delete_collection(name)
            except Exception:
                pass
        self._episodes = self._chroma.create_collection(
            name=f"v2o_episodes_{uid_hash}", metadata={"hnsw:space": "cosine"})
        self._summaries = self._chroma.create_collection(
            name=f"v2o_summaries_{uid_hash}", metadata={"hnsw:space": "cosine"})


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_f1(pred, ref):
    """Token-level F1 score."""
    def tok(t):
        return set(re.findall(r'\b\w+\b', str(t).lower()))
    pt, rt = tok(pred), tok(ref)
    if not rt:
        return 1.0 if not pt else 0.0
    if not pt:
        return 0.0
    common = pt & rt
    if not common:
        return 0.0
    p, r = len(common) / len(pt), len(common) / len(rt)
    return 2 * p * r / (p + r)


def judge_answer(question, gold, pred):
    """LLM-as-Judge binary accuracy using GPT-4o-mini."""
    try:
        resp = openai_chat([
            {"role": "user", "content": f"""Is this answer correct? Consider semantic equivalence (same meaning, even if phrased differently).
Question: {question}
Gold answer: {gold}
Predicted answer: {pred}
Answer ONLY "yes" or "no"."""},
        ], temperature=0, max_tokens=10)
        return resp.lower().startswith("yes")
    except Exception:
        return False


def answer_with_openai(question, context):
    """Answer a question given context, using OpenAI."""
    system = f"""You have access to stored information about a conversation between two people.
Use ONLY the provided context to answer questions.
Think carefully, then provide ONLY the final answer as a short phrase on the last line.
Resolve relative dates using conversation timestamps.
If information is not available, say "No information available".

Context:
{context}"""

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
# LOCOMO loading & parsing
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


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def run_locomo_eval(max_convs=2, max_qa=60):
    data = load_locomo(max_convs)
    print(f"\n  LOCOMO: {len(data)} conversations, max {max_qa} QAs each")
    print(f"  LLM backbone: OpenAI {OPENAI_MODEL}")

    cat_names = {1: "multi-hop", 2: "temporal", 3: "open-domain",
                 4: "single-hop", 5: "adversarial"}

    # Store per-question details for JSON output
    all_results = {}
    per_system_f1s = defaultdict(list)
    per_system_judge = defaultdict(list)
    per_question_log = []

    for ci, conv_data in enumerate(data):
        sessions = parse_locomo_sessions(conv_data)
        qa_pairs = conv_data.get("qa", [])[:max_qa]
        sid = conv_data.get("sample_id", f"conv_{ci}")
        all_turns = []
        for _, _, turns in sessions:
            all_turns.extend(turns)

        print(f"\n  Conv {ci+1}/{len(data)} ({sid}): "
              f"{len(sessions)} sessions, {len(all_turns)} turns, "
              f"{len(qa_pairs)} QAs")

        # ===================================================================
        # System 1: UaC v2 (OpenAI)
        # ===================================================================
        print(f"    uac_v2: ingesting...", end="", flush=True)
        t0 = time.time()
        v2 = UserAsCodeV2OpenAI(f"locomo_v2o_{sid}_{ci}")
        for sk, date, turns in sessions:
            v2.ingest_session(turns, sk, date)
        ingest_time = time.time() - t0
        print(f" ({ingest_time:.0f}s) answering...", end="", flush=True)

        t0 = time.time()
        v2_f1s, v2_judges = [], []
        for qi, qa in enumerate(qa_pairs):
            gold = str(qa.get("answer", ""))
            pred = v2.answer(qa["question"])
            f1 = compute_f1(pred, gold)
            judge = judge_answer(qa["question"], gold, pred)
            v2_f1s.append(f1)
            v2_judges.append(1 if judge else 0)
            per_question_log.append({
                "conv": sid, "qi": qi, "system": "uac_v2",
                "question": qa["question"], "gold": gold, "pred": pred,
                "f1": f1, "judge": int(judge),
                "category": qa.get("category"),
            })
            if qi % 15 == 0 and qi > 0:
                print(f" {qi}", end="", flush=True)
            time.sleep(0.05)

        avg_v2_f1 = sum(v2_f1s) / len(v2_f1s) if v2_f1s else 0
        avg_v2_judge = sum(v2_judges) / len(v2_judges) if v2_judges else 0
        per_system_f1s["uac_v2"].extend(v2_f1s)
        per_system_judge["uac_v2"].extend(v2_judges)
        print(f" -> F1={avg_v2_f1:.3f} Judge={avg_v2_judge:.1%} "
              f"({len(v2_f1s)}Q, {time.time()-t0:.0f}s)")

        # ===================================================================
        # System 2: Mem0
        # ===================================================================
        print(f"    mem0: ingesting...", end="", flush=True)
        t0 = time.time()
        try:
            from mem0 import Memory
            for p in [pathlib.Path('/tmp/qdrant/.lock'),
                      pathlib.Path.home() / '.mem0' / 'migrations_qdrant' / '.lock']:
                p.unlink(missing_ok=True)
            mem = Memory()
            mem_uid = f"locomo_mem0o_{sid}_{ci}"
            try:
                mem.delete_all(user_id=mem_uid)
            except Exception:
                pass
            batch_size = 20
            for i in range(0, len(all_turns), batch_size):
                batch = "\n".join(all_turns[i:i+batch_size])
                try:
                    mem.add([{"role": "user", "content": batch}],
                            user_id=mem_uid)
                except Exception:
                    pass
            ingest_time = time.time() - t0
            print(f" ({ingest_time:.0f}s) answering...", end="", flush=True)

            t0 = time.time()
            mem0_f1s, mem0_judges = [], []
            for qi, qa in enumerate(qa_pairs):
                gold = str(qa.get("answer", ""))
                try:
                    results = mem.search(qa["question"], user_id=mem_uid)
                    memories = [r.get("memory", str(r))
                                for r in results.get("results", [])]
                    all_m = mem.get_all(user_id=mem_uid)
                    for r in all_m.get("results", []):
                        m = r.get("memory", str(r)) if isinstance(r, dict) else str(r)
                        if m not in memories:
                            memories.append(m)
                    context = "\n".join(f"- {m}" for m in memories[:30])
                except Exception:
                    context = "No memories available."
                pred = answer_with_openai(qa["question"], context)
                f1 = compute_f1(pred, gold)
                judge = judge_answer(qa["question"], gold, pred)
                mem0_f1s.append(f1)
                mem0_judges.append(1 if judge else 0)
                per_question_log.append({
                    "conv": sid, "qi": qi, "system": "mem0",
                    "question": qa["question"], "gold": gold, "pred": pred,
                    "f1": f1, "judge": int(judge),
                    "category": qa.get("category"),
                })
                if qi % 15 == 0 and qi > 0:
                    print(f" {qi}", end="", flush=True)
                time.sleep(0.05)

            avg_mem0_f1 = sum(mem0_f1s) / len(mem0_f1s) if mem0_f1s else 0
            avg_mem0_judge = sum(mem0_judges) / len(mem0_judges) if mem0_judges else 0
            per_system_f1s["mem0"].extend(mem0_f1s)
            per_system_judge["mem0"].extend(mem0_judges)
            print(f" -> F1={avg_mem0_f1:.3f} Judge={avg_mem0_judge:.1%} "
                  f"({len(mem0_f1s)}Q, {time.time()-t0:.0f}s)")

        except Exception as e:
            print(f" FAILED: {e}")
            traceback.print_exc()
            avg_mem0_f1 = 0
            avg_mem0_judge = 0

        # ===================================================================
        # System 3: Full Context reference
        # ===================================================================
        print(f"    full_ctx: answering...", end="", flush=True)
        t0 = time.time()
        full_text = "\n".join(all_turns)
        # GPT-4o-mini has 128k context; truncate if needed
        if len(full_text) > 100000:
            full_text = full_text[:100000]
        fc_f1s, fc_judges = [], []
        for qi, qa in enumerate(qa_pairs):
            gold = str(qa.get("answer", ""))
            pred = answer_with_openai(qa["question"], full_text)
            f1 = compute_f1(pred, gold)
            judge = judge_answer(qa["question"], gold, pred)
            fc_f1s.append(f1)
            fc_judges.append(1 if judge else 0)
            per_question_log.append({
                "conv": sid, "qi": qi, "system": "full_context",
                "question": qa["question"], "gold": gold, "pred": pred,
                "f1": f1, "judge": int(judge),
                "category": qa.get("category"),
            })
            if qi % 15 == 0 and qi > 0:
                print(f" {qi}", end="", flush=True)
            time.sleep(0.05)

        avg_fc_f1 = sum(fc_f1s) / len(fc_f1s) if fc_f1s else 0
        avg_fc_judge = sum(fc_judges) / len(fc_judges) if fc_judges else 0
        per_system_f1s["full_context"].extend(fc_f1s)
        per_system_judge["full_context"].extend(fc_judges)
        print(f" -> F1={avg_fc_f1:.3f} Judge={avg_fc_judge:.1%} "
              f"({len(fc_f1s)}Q, {time.time()-t0:.0f}s)")

        all_results[sid] = {
            "uac_v2": {"f1": avg_v2_f1, "judge": avg_v2_judge},
            "mem0": {"f1": avg_mem0_f1, "judge": avg_mem0_judge},
            "full_context": {"f1": avg_fc_f1, "judge": avg_fc_judge},
        }

    # ===================================================================
    # Summary table
    # ===================================================================
    print(f"\n{'='*70}")
    print(f"  LOCOMO RESULTS (OpenAI {OPENAI_MODEL})")
    print(f"  {len(data)} conversations, up to {max_qa} QAs each")
    print(f"{'='*70}")
    print(f"\n  {'System':<15} {'Token F1':>10} {'LLM-Judge Acc':>15} {'N':>6}")
    print(f"  {'-'*48}")

    for sys_name in ["full_context", "uac_v2", "mem0"]:
        f1s = per_system_f1s[sys_name]
        judges = per_system_judge[sys_name]
        if f1s:
            avg_f1 = sum(f1s) / len(f1s)
            avg_judge = sum(judges) / len(judges)
            print(f"  {sys_name:<15} {avg_f1:>10.3f} {avg_judge:>14.1%} {len(f1s):>6}")
        else:
            print(f"  {sys_name:<15} {'N/A':>10} {'N/A':>15} {'0':>6}")

    print(f"\n  Published SOTA (LLM-Judge on LOCOMO):")
    print(f"  {'EverMemOS':<15} {'--':>10} {'93.05%':>15}")
    print(f"  {'MemMachine':<15} {'--':>10} {'91.7%':>15}")
    print(f"  {'Mem0 (pub.)':<15} {'--':>10} {'66.9%':>15}")

    return all_results, per_question_log, per_system_f1s, per_system_judge


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"\n{'='*70}")
    print(f"  LOCOMO Evaluation — User as Code v2 with OpenAI {OPENAI_MODEL}")
    print(f"  Timestamp: {datetime.now().isoformat()}")
    print(f"{'='*70}")

    all_results, per_question_log, f1s, judges = run_locomo_eval(
        max_convs=2, max_qa=60
    )

    # Build output JSON
    output = {
        "model": OPENAI_MODEL,
        "timestamp": datetime.now().isoformat(),
        "config": {"max_convs": 2, "max_qa": 60},
        "per_conversation": all_results,
        "aggregate": {},
        "per_question": per_question_log,
    }

    for sys_name in ["full_context", "uac_v2", "mem0"]:
        sys_f1s = f1s[sys_name]
        sys_judges = judges[sys_name]
        if sys_f1s:
            output["aggregate"][sys_name] = {
                "token_f1": sum(sys_f1s) / len(sys_f1s),
                "llm_judge_accuracy": sum(sys_judges) / len(sys_judges),
                "n_questions": len(sys_f1s),
            }

    out_path = RESULTS_DIR / "v2_openai_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")
