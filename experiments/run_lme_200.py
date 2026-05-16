#!/usr/bin/env python3
"""Run a single memory system on the 200-question LongMemEval stratified sample.

Each question's haystack_sessions are ingested fresh (system reset between questions).
Resumable: skip already-completed question_ids in results/lme200_<system>.json.

Usage: run_lme_200.py <system> [--limit N] [--start IDX]
"""
from __future__ import annotations
import argparse
import json
import pathlib
import sys
import time
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from runner_utils import _log, answer_question, judge_answer, GEMINI_MODEL  # noqa: E402

SAMPLE_PATH = pathlib.Path(__file__).resolve().parent / "results" / "lme_200_sample.json"
RESULTS_DIR = pathlib.Path(__file__).resolve().parent / "results"


def session_to_text(session_turns, session_date):
    """Format a session's turns into text. LME turns: list of {role, content}."""
    lines = []
    for t in session_turns:
        role = t.get("role", "user")
        content = t.get("content", "")
        speaker = "User" if role == "user" else "Assistant"
        lines.append(f"{speaker}: {content}")
    return f"[{session_date}]\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# System wrappers — one fresh instance per question
# ---------------------------------------------------------------------------

class UaCV5Runner:
    name = "uac_v5"

    def __init__(self):
        from user_as_code_v5 import UserAsCodeV5
        self.cls = UserAsCodeV5

    def run_question(self, q):
        sys = self.cls(user_id=f"lme_{q['question_id']}_{int(time.time())}")
        for sid, sess, date in zip(q["haystack_session_ids"], q["haystack_sessions"], q["haystack_dates"]):
            turns = [f"User: {t['content']}" if t["role"] == "user" else f"Assistant: {t['content']}" for t in sess]
            sys.ingest_session(turns, sid, date)
        sys.structure()
        ans = sys.answer(q["question"])
        sys.reset()
        return ans


class Mem0Runner:
    name = "mem0"

    def __init__(self):
        from mem0 import Memory
        self.cls = Memory
        for p in [pathlib.Path("/tmp/qdrant/.lock"),
                  pathlib.Path.home() / ".mem0" / "migrations_qdrant" / ".lock"]:
            p.unlink(missing_ok=True)

    def run_question(self, q):
        for p in [pathlib.Path("/tmp/qdrant/.lock"),
                  pathlib.Path.home() / ".mem0" / "migrations_qdrant" / ".lock"]:
            p.unlink(missing_ok=True)
        m = self.cls()
        uid = f"lme_{q['question_id']}_{int(time.time())}"
        for sess, date in zip(q["haystack_sessions"], q["haystack_dates"]):
            txt = session_to_text(sess, date)
            try:
                m.add([{"role": "user", "content": txt}], user_id=uid)
            except Exception as e:
                _log(f"  mem0 ingest err: {e}")
        results = m.search(q["question"], user_id=uid)
        if isinstance(results, dict) and "results" in results:
            mem = results["results"]
        elif isinstance(results, list):
            mem = results
        else:
            mem = []
        ctx = "\n".join(m_.get("memory", str(m_)) if isinstance(m_, dict) else str(m_) for m_ in mem) if mem else "No info."
        ans = answer_question(q["question"], ctx)
        try:
            m.delete_all(user_id=uid)
        except Exception:
            pass
        return ans


class AMemRunner:
    name = "a_mem"

    def __init__(self):
        from agentic_memory.memory_system import AgenticMemorySystem
        self.cls = AgenticMemorySystem

    def run_question(self, q):
        memory = self.cls(model_name="all-MiniLM-L6-v2", llm_backend="openai", llm_model="gpt-4o-mini")
        for sess, date in zip(q["haystack_sessions"], q["haystack_dates"]):
            memory.add_note(session_to_text(sess, date))
        # find_related_memories_raw can crash if chromadb returns None metadata.
        # Use a defensive search via _search_raw + metadata fallback.
        try:
            ctx = memory.find_related_memories_raw(q["question"], k=10)
        except AttributeError:
            ctx = ""
        if not ctx.strip():
            # Fallback: get every note's content directly.
            try:
                results = memory.retriever.search(q["question"], 10)
                parts = []
                if results.get("metadatas") and results["metadatas"]:
                    for md in results["metadatas"][0]:
                        if md and md.get("content"):
                            parts.append(md.get("content"))
                ctx = "\n\n".join(parts) if parts else "No info."
            except Exception:
                ctx = "No info."
        return answer_question(q["question"], ctx)


class FullContextRunner:
    name = "full_context"

    def __init__(self):
        pass

    def run_question(self, q):
        parts = []
        for sid, sess, date in zip(q["haystack_session_ids"], q["haystack_sessions"], q["haystack_dates"]):
            parts.append(f"=== {sid} ({date}) ===")
            parts.append(session_to_text(sess, date))
        ctx = "\n\n".join(parts)
        return answer_question(q["question"], ctx)


class HindsightRunner:
    name = "hindsight"

    def __init__(self):
        from hindsight_lite import HindsightSystem
        self.cls = HindsightSystem

    def run_question(self, q):
        sys = self.cls(user_id=f"lme_hs_{q['question_id']}_{int(time.time())}")
        for sid, sess, date in zip(q["haystack_session_ids"], q["haystack_sessions"], q["haystack_dates"]):
            turn_lines = [
                f"User: {t['content']}" if t["role"] == "user" else f"Assistant: {t['content']}"
                for t in sess
            ]
            sys.ingest_session(turn_lines, sid, date)
        ans = sys.answer(q["question"])
        sys.reset()
        return ans


class EverMemOSRunner:
    name = "evermemos"

    def __init__(self):
        from evermemos_lite import EverMemOSSystem
        self.cls = EverMemOSSystem

    def run_question(self, q):
        sys = self.cls(user_id=f"lme_em_{q['question_id']}_{int(time.time())}")
        for sid, sess, date in zip(q["haystack_session_ids"], q["haystack_sessions"], q["haystack_dates"]):
            turn_lines = [
                f"User: {t['content']}" if t["role"] == "user" else f"Assistant: {t['content']}"
                for t in sess
            ]
            sys.ingest_session(turn_lines, sid, date)
        sys.consolidate()
        ans = sys.answer(q["question"])
        sys.reset()
        return ans


class MemMachineRunner:
    name = "memmachine"

    def __init__(self):
        # MemMachine is implemented in run_locomo_memmachine.py (sentence-level
        # dense retrieval + ±3 contextual expansion). Reuse it here for LME.
        from run_locomo_memmachine import MemMachine
        self.cls = MemMachine

    def run_question(self, q):
        # Convert LME's per-session (role, content) turns into the (speaker,
        # text, session_id, date) shape MemMachine expects.
        sessions = []
        for sid, sess, date in zip(q["haystack_session_ids"], q["haystack_sessions"], q["haystack_dates"]):
            turns = [{"speaker": "User" if t["role"] == "user" else "Assistant",
                       "text": t["content"]} for t in sess]
            sessions.append({"session_id": sid, "date": date, "turns": turns})
        sysobj = self.cls()
        sysobj.ingest(sessions, conv_id=q["question_id"])
        ans = sysobj.answer(q["question"])
        sysobj.reset()
        return ans


SYSTEMS = {
    "uac_v5": UaCV5Runner,
    "mem0": Mem0Runner,
    "a_mem": AMemRunner,
    "full_context": FullContextRunner,
    "hindsight": HindsightRunner,
    "evermemos": EverMemOSRunner,
    "memmachine": MemMachineRunner,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("system", choices=list(SYSTEMS.keys()))
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--start", type=int, default=0)
    args = ap.parse_args()

    out = RESULTS_DIR / f"lme200_{args.system}.json"
    sample = json.load(open(SAMPLE_PATH))
    questions = sample["questions"][args.start:args.start + args.limit]

    if out.exists():
        results = json.load(open(out))
    else:
        results = {
            "system": args.system,
            "model": GEMINI_MODEL,
            "n_target": len(questions),
            "by_question": {},
        }

    runner = SYSTEMS[args.system]()

    n = 0
    for q in questions:
        qid = q["question_id"]
        if qid in results["by_question"]:
            continue
        n += 1
        try:
            t0 = time.time()
            pred = runner.run_question(q)
            dt = time.time() - t0
            correct, expl = judge_answer(q["question"], pred, q["answer"])
            results["by_question"][qid] = {
                "question_type": q["question_type"],
                "question": q["question"],
                "gold": q["answer"],
                "prediction": pred,
                "judge_correct": correct,
                "judge_explanation": expl,
                "answer_time": dt,
            }
            status = "OK" if correct else "WR"
            _log(f"  {n} [{q['question_type']}] {status} [{dt:.1f}s] {q['question'][:70]}")
        except Exception as e:
            _log(f"  {n} ERROR: {e}")
            traceback.print_exc()
            results["by_question"][qid] = {
                "question_type": q["question_type"],
                "question": q["question"],
                "gold": q["answer"],
                "prediction": f"ERROR: {e}",
                "judge_correct": False,
                "error": str(e),
            }

        if n % 5 == 0:
            with open(out, "w") as f:
                json.dump(results, f, indent=2, default=str)

        time.sleep(0.2)

    # Aggregate
    by_type = {}
    correct_total, n_total = 0, 0
    for qid, d in results["by_question"].items():
        t = d["question_type"]
        by_type.setdefault(t, {"n": 0, "correct": 0})
        by_type[t]["n"] += 1
        if d["judge_correct"]:
            by_type[t]["correct"] += 1
            correct_total += 1
        n_total += 1
    for t, v in by_type.items():
        v["accuracy"] = v["correct"] / v["n"] if v["n"] else 0.0
    results["aggregate"] = {
        "n_total": n_total,
        "n_correct": correct_total,
        "accuracy": correct_total / n_total if n_total else 0.0,
    }
    results["per_type"] = by_type

    with open(out, "w") as f:
        json.dump(results, f, indent=2, default=str)
    _log(f"\nDONE {args.system}: {correct_total}/{n_total} = {results['aggregate']['accuracy']:.3f}")
    for t, v in sorted(by_type.items()):
        _log(f"  {t}: {v['correct']}/{v['n']} = {v['accuracy']:.3f}")


if __name__ == "__main__":
    main()
