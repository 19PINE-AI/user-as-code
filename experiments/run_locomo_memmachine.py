#!/usr/bin/env python3
"""Run a MemMachine-style memory system on the 5-conversation LOCOMO subset.

Reimplements MemMachine's described architecture (arXiv 2604.04853):
- Stores entire conversational episodes verbatim (no LLM-extracted facts)
- Indexes turns at sentence level via dense retrieval
- At query time, retrieves nucleus matches and expands with surrounding context

Uses Gemini 3 Flash for backbone parity with the UaC v5 LOCOMO run.
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
from runner_utils import _log, answer_question, judge_answer, token_f1, GEMINI_MODEL  # noqa: E402

DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "benchmarks/locomo/data/locomo10.json"
RESULTS_DIR = pathlib.Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def get_sessions(conv: dict) -> list[dict]:
    c = conv["conversation"]
    keys = sorted([k for k in c.keys() if re.match(r"^session_\d+$", k)],
                  key=lambda x: int(x.split("_")[1]))
    return [{"session_id": sk, "date": c.get(f"{sk}_date_time", ""), "turns": c[sk]} for sk in keys]


class MemMachine:
    """MemMachine-style episodic memory with contextualized retrieval."""

    name = "memmachine"

    def __init__(self):
        import chromadb
        from chromadb.utils import embedding_functions
        self._chromadb = chromadb
        self._embed_fn = embedding_functions.DefaultEmbeddingFunction()
        self.client = None
        self.coll = None
        self.sentences: list[str] = []  # full ordered episode for context expansion

    def ingest(self, sessions: list[dict], conv_id: str) -> None:
        self.client = self._chromadb.Client()
        coll_name = f"memmachine_{conv_id}_{int(time.time())}"
        try:
            self.client.delete_collection(coll_name)
        except Exception:
            pass
        self.coll = self.client.create_collection(
            name=coll_name,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

        # Build sentence-level index. Each turn becomes one indexed sentence.
        self.sentences = []
        ids = []
        for s in sessions:
            for t in s["turns"]:
                idx = len(self.sentences)
                self.sentences.append(
                    f"[{s['session_id']} {s['date']}] {t['speaker']}: {t['text']}"
                )
                ids.append(f"s{idx}")
            _log(f"    MemMachine: ingested {s['session_id']} ({len(s['turns'])} turns)")
        if self.sentences:
            self.coll.add(documents=self.sentences, ids=ids)

    def answer(self, question: str) -> str:
        if not self.sentences:
            return "No information available"
        # Nucleus retrieval: top-30 most similar sentences.
        k = min(30, len(self.sentences))
        res = self.coll.query(query_texts=[question], n_results=k)
        nucleus_idx = []
        for sid in res["ids"][0]:
            try:
                nucleus_idx.append(int(sid.lstrip("s")))
            except ValueError:
                pass
        # Contextual expansion: +/- 3 surrounding sentences.
        expanded = set()
        for i in nucleus_idx:
            for j in range(max(0, i - 3), min(len(self.sentences), i + 4)):
                expanded.add(j)
        ctx_lines = [self.sentences[j] for j in sorted(expanded)]
        ctx = "\n".join(ctx_lines)
        return answer_question(question, ctx)

    def reset(self) -> None:
        if self.client and self.coll:
            try:
                self.client.delete_collection(self.coll.name)
            except Exception:
                pass
        self.client = None
        self.coll = None
        self.sentences = []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-qa", type=int, default=60)
    ap.add_argument("--conv-start", type=int, default=0)
    ap.add_argument("--conv-end", type=int, default=5)
    args = ap.parse_args()

    out = RESULTS_DIR / "locomo5_memmachine.json"

    if out.exists():
        results = json.load(open(out))
    else:
        results = {
            "system": "memmachine",
            "model": GEMINI_MODEL,
            "max_qa_per_conv": args.max_qa,
            "per_conversation": {},
            "details": {},
        }

    with open(DATA_PATH) as f:
        all_convs = json.load(f)
    convs = all_convs[args.conv_start:args.conv_end]

    sysobj = MemMachine()

    total_f1, total_judge = [], []
    cat_f1, cat_judge = defaultdict(list), defaultdict(list)

    for ci, conv in enumerate(convs):
        conv_id = conv.get("sample_id", f"conv_{ci}")
        prev_details = results["details"].get(conv_id, [])
        completed_idx = {d["qa_idx"] for d in prev_details}
        if conv_id in results["per_conversation"]:
            pc = results["per_conversation"][conv_id]
            if pc.get("n_questions", 0) >= args.max_qa:
                _log(f"\n=== Conv {conv_id}: SKIP (n={pc['n_questions']}) ===")
                for d in prev_details:
                    total_f1.append(d["f1"])
                    total_judge.append(1.0 if d["judge_correct"] else 0.0)
                    cat_f1[d["category"]].append(d["f1"])
                    cat_judge[d["category"]].append(1.0 if d["judge_correct"] else 0.0)
                continue

        _log(f"\n=== Conv {ci} ({conv_id}) [memmachine] ===")
        sessions = get_sessions(conv)
        _log(f"  {len(sessions)} sessions")

        try:
            sysobj.ingest(sessions, conv_id)
        except Exception as e:
            _log(f"  INGEST FAILED: {e}")
            traceback.print_exc()
            sysobj.reset()
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
                pred = sysobj.answer(question)
                dt = time.time() - t0
                f1 = token_f1(pred, gold)
                correct, expl = judge_answer(question, pred, gold)
                d = {"qa_idx": qi, "question": question, "gold": gold,
                     "prediction": pred, "category": category, "f1": f1,
                     "judge_correct": correct, "judge_explanation": expl,
                     "answer_time": dt}
                conv_details.append(d)
                conv_f1.append(f1)
                conv_judge.append(1.0 if correct else 0.0)
                total_f1.append(f1)
                total_judge.append(1.0 if correct else 0.0)
                cat_f1[category].append(f1)
                cat_judge[category].append(1.0 if correct else 0.0)
                status = "OK" if correct else "WR"
                _log(f"    Q{qi+1}/{len(qa_pairs)} cat={category} F1={f1:.2f} J={status} [{dt:.1f}s]")
            except Exception as e:
                _log(f"    Q{qi+1} ERROR: {e}")
                conv_details.append({"qa_idx": qi, "question": question, "gold": gold,
                                     "prediction": f"ERROR: {e}", "category": category,
                                     "f1": 0.0, "judge_correct": False, "error": str(e)})
                conv_f1.append(0.0)
                conv_judge.append(0.0)
                total_f1.append(0.0)
                total_judge.append(0.0)
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

        results["details"][conv_id] = conv_details
        results["per_conversation"][conv_id] = {
            "f1": sum(conv_f1)/len(conv_f1) if conv_f1 else 0.0,
            "judge_accuracy": sum(conv_judge)/len(conv_judge) if conv_judge else 0.0,
            "n_questions": len(conv_details),
        }
        sysobj.reset()
        with open(out, "w") as f:
            json.dump(results, f, indent=2, default=str)
        _log(f"  conv {conv_id} done: F1={results['per_conversation'][conv_id]['f1']:.3f} Judge={results['per_conversation'][conv_id]['judge_accuracy']:.3f}")

    if total_f1:
        results["aggregate"] = {
            "n_total": len(total_f1),
            "f1": sum(total_f1)/len(total_f1),
            "judge_accuracy": sum(total_judge)/len(total_judge),
        }
        results["per_category"] = {
            str(c): {"n": len(cat_f1[c]),
                     "f1": sum(cat_f1[c])/len(cat_f1[c]),
                     "judge_accuracy": sum(cat_judge[c])/len(cat_judge[c])}
            for c in sorted(cat_f1.keys())
        }
    with open(out, "w") as f:
        json.dump(results, f, indent=2, default=str)
    _log(f"\nDONE memmachine: n={results.get('aggregate',{}).get('n_total',0)}  judge={results.get('aggregate',{}).get('judge_accuracy',0):.3f}")


if __name__ == "__main__":
    main()
