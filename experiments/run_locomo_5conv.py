#!/usr/bin/env python3
"""Run a single memory system on the first 5 LOCOMO conversations.

Usage: run_locomo_5conv.py <system> [--max-qa 60] [--conv-start 0] [--conv-end 5]
  system: uac_v5 | mem0 | a_mem | full_context

Resumable: writes to results/locomo5_<system>.json after every QA. Re-running
skips already-completed (system, conv_id, qa_idx) tuples.
"""
from __future__ import annotations
import argparse
import json
import pathlib
import re
import sys
import time
import traceback
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from runner_utils import (  # noqa: E402
    _log, answer_question, judge_answer, token_f1, GEMINI_MODEL,
)

DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "benchmarks/locomo/data/locomo10.json"
RESULTS_DIR = pathlib.Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def get_sessions(conv):
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


def build_full_text(sessions):
    parts = []
    for s in sessions:
        header = f"=== {s['session_id']} ({s['date']}) ==="
        turn_lines = [f"{t['speaker']}: {t['text']}" for t in s["turns"]]
        parts.append(header + "\n" + "\n".join(turn_lines))
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# System wrappers (4 systems only; UaC v2 and SimpleMem dropped)
# ---------------------------------------------------------------------------

def _make_uac_wrapper(version_tag: str, import_path: str, class_name: str,
                      tag_label: str, structure_after: bool):
    """Factory for UaC v2/v3/v4/v5 wrappers with uniform ingest/answer API."""
    class _UaCWrapper:
        name = version_tag

        def __init__(self):
            mod = __import__(import_path)
            self.cls = getattr(mod, class_name)
            self.system = None

        def ingest(self, sessions, conv_id):
            self.system = self.cls(user_id=f"locomo5_{version_tag}_{conv_id}_{int(time.time())}")
            for s in sessions:
                turn_lines = [f"{t['speaker']}: {t['text']}" for t in s["turns"]]
                self.system.ingest_session(turn_lines, s["session_id"], s["date"])
                _log(f"    {tag_label}: ingested {s['session_id']}")
            if structure_after and hasattr(self.system, "structure"):
                self.system.structure()
                if hasattr(self.system, "code_state"):
                    _log(f"    {tag_label}: structured ({len(self.system.code_state)} chars)")

        def answer(self, question):
            return self.system.answer(question)

        def reset(self):
            if self.system and hasattr(self.system, "reset"):
                self.system.reset()
            self.system = None

    _UaCWrapper.__name__ = f"UaC{version_tag.upper()}Wrapper"
    return _UaCWrapper


UaCV2System = _make_uac_wrapper("uac_v2", "user_as_code_v2", "UserAsCodeV2", "UAC v2", False)
UaCV3System = _make_uac_wrapper("uac_v3", "user_as_code_v3", "UserAsCodeV3", "UAC v3", False)
UaCV4System = _make_uac_wrapper("uac_v4", "user_as_code_v4", "UserAsCodeV4", "UAC v4", False)
UaCV5System = _make_uac_wrapper("uac_v5", "user_as_code_v5", "UserAsCodeV5", "UAC v5", True)


class Mem0Wrapper:
    name = "mem0"

    def _clean_locks(self):
        for p in [
            pathlib.Path("/tmp/qdrant/.lock"),
            pathlib.Path.home() / ".mem0" / "migrations_qdrant" / ".lock",
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
        self.uid = f"locomo5_{conv_id}_{int(time.time())}"
        for s in sessions:
            session_text = f"[{s['date']}] " + " ".join(
                f"{t['speaker']}: {t['text']}" for t in s["turns"]
            )
            try:
                self.m.add(
                    [{"role": "user", "content": session_text}],
                    user_id=self.uid,
                )
            except Exception as e:
                _log(f"    Mem0: error ingesting {s['session_id']}: {e}")
            _log(f"    Mem0: ingested {s['session_id']}")

    def answer(self, question):
        results = self.m.search(question, user_id=self.uid)
        if isinstance(results, dict) and "results" in results:
            mem = results["results"]
        elif isinstance(results, list):
            mem = results
        else:
            mem = []
        if mem:
            ctx = "\n".join(
                m.get("memory", m.get("text", str(m))) if isinstance(m, dict) else str(m)
                for m in mem
            )
        else:
            ctx = "No relevant information found."
        return answer_question(question, ctx)

    def reset(self):
        if self.m and self.uid:
            try:
                self.m.delete_all(user_id=self.uid)
            except Exception:
                pass
        self.m = None


class AMemWrapper:
    name = "a_mem"

    def __init__(self):
        from agentic_memory.memory_system import AgenticMemorySystem
        self.cls = AgenticMemorySystem
        self.memory = None

    def ingest(self, sessions, conv_id):
        self.memory = self.cls(
            model_name="all-MiniLM-L6-v2",
            llm_backend="openai",
            llm_model="gpt-4o-mini",
        )
        for s in sessions:
            session_text = f"[{s['date']}] " + " ".join(
                f"{t['speaker']}: {t['text']}" for t in s["turns"]
            )
            self.memory.add_note(session_text)
            _log(f"    A-MEM: ingested {s['session_id']}")

    def answer(self, question):
        # Use raw retrieval which includes the actual session content (the
        # search_agentic dict returns context-only fields without content).
        try:
            ctx = self.memory.find_related_memories_raw(question, k=10)
        except AttributeError:
            ctx = ""
        if not ctx.strip():
            try:
                results = self.memory.retriever.search(question, 10)
                parts = []
                if results.get("metadatas") and results["metadatas"]:
                    for md in results["metadatas"][0]:
                        if md and md.get("content"):
                            parts.append(md.get("content"))
                ctx = "\n\n".join(parts) if parts else "No relevant information found."
            except Exception:
                ctx = "No relevant information found."
        return answer_question(question, ctx)

    def reset(self):
        self.memory = None


class FullContextWrapper:
    name = "full_context"

    def __init__(self):
        self.full_text = ""

    def ingest(self, sessions, conv_id):
        self.full_text = build_full_text(sessions)
        _log(f"    Full Context: loaded {len(self.full_text)} chars")

    def answer(self, question):
        return answer_question(question, self.full_text)

    def reset(self):
        self.full_text = ""


class HindsightWrapper:
    name = "hindsight"

    def __init__(self):
        from hindsight_lite import HindsightSystem
        self.cls = HindsightSystem
        self.system = None

    def ingest(self, sessions, conv_id):
        self.system = self.cls(user_id=f"locomo5_hs_{conv_id}_{int(time.time())}")
        for s in sessions:
            turn_lines = [f"{t['speaker']}: {t['text']}" for t in s["turns"]]
            self.system.ingest_session(turn_lines, s["session_id"], s["date"])
            _log(f"    Hindsight: ingested {s['session_id']} (facts={len(self.system.facts)})")

    def answer(self, question):
        return self.system.answer(question)

    def reset(self):
        if self.system:
            self.system.reset()
        self.system = None


class EverMemOSWrapper:
    name = "evermemos"

    def __init__(self):
        from evermemos_lite import EverMemOSSystem
        self.cls = EverMemOSSystem
        self.system = None

    def ingest(self, sessions, conv_id):
        self.system = self.cls(user_id=f"locomo5_em_{conv_id}_{int(time.time())}")
        for s in sessions:
            turn_lines = [f"{t['speaker']}: {t['text']}" for t in s["turns"]]
            self.system.ingest_session(turn_lines, s["session_id"], s["date"])
            _log(f"    EverMemOS: ingested {s['session_id']}")
        self.system.consolidate()
        _log(f"    EverMemOS: consolidated into {len(self.system.scenes)} scenes")

    def answer(self, question):
        return self.system.answer(question)

    def reset(self):
        if self.system:
            self.system.reset()
        self.system = None


SYSTEMS = {
    "uac_v5": UaCV5System,
    "uac_v4": UaCV4System,
    "uac_v3": UaCV3System,
    "uac_v2": UaCV2System,
    "mem0": Mem0Wrapper,
    "a_mem": AMemWrapper,
    "full_context": FullContextWrapper,
    "hindsight": HindsightWrapper,
    "evermemos": EverMemOSWrapper,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("system", choices=list(SYSTEMS.keys()))
    ap.add_argument("--max-qa", type=int, default=60)
    ap.add_argument("--conv-start", type=int, default=0)
    ap.add_argument("--conv-end", type=int, default=5)
    args = ap.parse_args()

    out = RESULTS_DIR / f"locomo5_{args.system}.json"

    # Load existing results for resume
    if out.exists():
        with open(out) as f:
            results = json.load(f)
    else:
        results = {
            "system": args.system,
            "model": GEMINI_MODEL,
            "max_qa_per_conv": args.max_qa,
            "per_conversation": {},
            "details": {},
        }

    with open(DATA_PATH) as f:
        all_convs = json.load(f)
    convs = all_convs[args.conv_start:args.conv_end]

    sys_obj = SYSTEMS[args.system]()

    total_f1, total_judge = [], []
    cat_f1, cat_judge = defaultdict(list), defaultdict(list)

    for ci, conv in enumerate(convs):
        conv_id = conv.get("sample_id", f"conv_{ci}")

        # Existing results for this conversation
        prev_details = results["details"].get(conv_id, [])
        completed_idx = {d["qa_idx"] for d in prev_details}

        if conv_id in results["per_conversation"]:
            pc = results["per_conversation"][conv_id]
            if pc.get("n_questions", 0) >= args.max_qa:
                _log(f"\n=== Conv {conv_id}: SKIP (already done, n={pc['n_questions']}, judge={pc['judge_accuracy']:.3f}) ===")
                # still add to global stats
                for d in prev_details:
                    total_f1.append(d["f1"])
                    total_judge.append(1.0 if d["judge_correct"] else 0.0)
                    cat_f1[d["category"]].append(d["f1"])
                    cat_judge[d["category"]].append(1.0 if d["judge_correct"] else 0.0)
                continue

        _log(f"\n=== Conv {ci} ({conv_id}) [{args.system}] ===")
        sessions = get_sessions(conv)
        _log(f"  {len(sessions)} sessions")

        try:
            t0 = time.time()
            sys_obj.ingest(sessions, conv_id)
            _log(f"  ingest done in {time.time()-t0:.1f}s")
        except Exception as e:
            _log(f"  INGEST FAILED: {e}")
            traceback.print_exc()
            try: sys_obj.reset()
            except Exception: pass
            continue

        qa_pairs = conv["qa"][:args.max_qa]
        conv_details = list(prev_details)
        conv_f1 = [d["f1"] for d in prev_details]
        conv_judge = [1.0 if d["judge_correct"] else 0.0 for d in prev_details]

        for qi, qa in enumerate(qa_pairs):
            if qi in completed_idx:
                continue
            question = qa["question"]
            gold = str(qa["answer"])
            category = qa.get("category", 0)
            try:
                t0 = time.time()
                pred = sys_obj.answer(question)
                dt = time.time() - t0
                f1 = token_f1(pred, gold)
                correct, expl = judge_answer(question, pred, gold)
                d = {
                    "qa_idx": qi,
                    "question": question,
                    "gold": gold,
                    "prediction": pred,
                    "category": category,
                    "f1": f1,
                    "judge_correct": correct,
                    "judge_explanation": expl,
                    "answer_time": dt,
                }
                conv_details.append(d)
                conv_f1.append(f1)
                conv_judge.append(1.0 if correct else 0.0)
                total_f1.append(f1)
                total_judge.append(1.0 if correct else 0.0)
                cat_f1[category].append(f1)
                cat_judge[category].append(1.0 if correct else 0.0)
                status = "OK" if correct else "WR"
                _log(f"    Q{qi+1}/{len(qa_pairs)} cat={category} F1={f1:.2f} J={status} [{dt:.1f}s] {question[:60]}")
            except Exception as e:
                _log(f"    Q{qi+1} ERROR: {e}")
                traceback.print_exc()
                conv_details.append({
                    "qa_idx": qi,
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

            # incremental save every 5 QAs
            if (qi + 1) % 5 == 0:
                results["details"][conv_id] = conv_details
                results["per_conversation"][conv_id] = {
                    "f1": sum(conv_f1)/len(conv_f1) if conv_f1 else 0.0,
                    "judge_accuracy": sum(conv_judge)/len(conv_judge) if conv_judge else 0.0,
                    "n_questions": len(conv_details),
                }
                with open(out, "w") as f:
                    json.dump(results, f, indent=2, default=str)

            time.sleep(0.2)

        # final per-conv save
        results["details"][conv_id] = conv_details
        results["per_conversation"][conv_id] = {
            "f1": sum(conv_f1)/len(conv_f1) if conv_f1 else 0.0,
            "judge_accuracy": sum(conv_judge)/len(conv_judge) if conv_judge else 0.0,
            "n_questions": len(conv_details),
        }
        try: sys_obj.reset()
        except Exception: pass

        with open(out, "w") as f:
            json.dump(results, f, indent=2, default=str)
        _log(f"  conv {conv_id} done: F1={results['per_conversation'][conv_id]['f1']:.3f} Judge={results['per_conversation'][conv_id]['judge_accuracy']:.3f}")

    # Aggregate
    if total_f1:
        results["aggregate"] = {
            "n_total": len(total_f1),
            "f1": sum(total_f1)/len(total_f1),
            "judge_accuracy": sum(total_judge)/len(total_judge),
        }
        results["per_category"] = {
            str(c): {
                "n": len(cat_f1[c]),
                "f1": sum(cat_f1[c])/len(cat_f1[c]),
                "judge_accuracy": sum(cat_judge[c])/len(cat_judge[c]),
            }
            for c in sorted(cat_f1.keys())
        }
    with open(out, "w") as f:
        json.dump(results, f, indent=2, default=str)
    _log(f"\nDONE. n={results.get('aggregate',{}).get('n_total',0)} judge={results.get('aggregate',{}).get('judge_accuracy',0):.3f}")
    _log(f"Saved: {out}")


if __name__ == "__main__":
    main()
