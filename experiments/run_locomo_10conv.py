#!/usr/bin/env python3
"""Extend an existing locomo5 run to all 10 LOCOMO conversations.

Copies the existing locomo5_<system>.json results into locomo10_<system>.json
(preserving completed conv-26..43) then continues with conv-44..50.

Reuses the SYSTEMS dict and helpers from run_locomo_5conv.py.
"""
from __future__ import annotations
import argparse
import json
import pathlib
import re
import sys
import time
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from runner_utils import (  # noqa: E402
    _log, answer_question, judge_answer, token_f1, GEMINI_MODEL,
)
from run_locomo_5conv import SYSTEMS, get_sessions, build_full_text  # noqa: E402

DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "benchmarks/locomo/data/locomo10.json"
RESULTS_DIR = pathlib.Path(__file__).resolve().parent / "results"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("system", choices=list(SYSTEMS.keys()))
    ap.add_argument("--max-qa", type=int, default=60)
    ap.add_argument("--conv-start", type=int, default=0)
    ap.add_argument("--conv-end", type=int, default=10)
    args = ap.parse_args()

    out = RESULTS_DIR / f"locomo10_{args.system}.json"
    prior = RESULTS_DIR / f"locomo5_{args.system}.json"

    if out.exists():
        with open(out) as f:
            results = json.load(f)
        _log(f"Resuming from {out}")
    elif prior.exists():
        with open(prior) as f:
            results = json.load(f)
        results["system"] = args.system
        _log(f"Seeded from {prior.name} (preserving conv-26..43 results)")
    else:
        results = {
            "system": args.system,
            "model": GEMINI_MODEL,
            "max_qa_per_conv": args.max_qa,
            "per_conversation": {},
            "details": {},
        }
        _log(f"Fresh run for {args.system}")

    with open(DATA_PATH) as f:
        all_convs = json.load(f)
    convs = all_convs[args.conv_start:args.conv_end]

    sys_obj = SYSTEMS[args.system]()

    for ci, conv in enumerate(convs):
        conv_id = conv.get("sample_id", f"conv_{ci}")
        prev_details = results["details"].get(conv_id, [])
        completed_idx = {d["qa_idx"] for d in prev_details}

        if conv_id in results["per_conversation"]:
            pc = results["per_conversation"][conv_id]
            if pc.get("n_questions", 0) >= args.max_qa:
                _log(f"=== Conv {conv_id}: SKIP done n={pc['n_questions']} judge={pc['judge_accuracy']:.3f} ===")
                continue

        _log(f"\n=== Conv {ci} ({conv_id}) [{args.system}] ===")
        sessions = get_sessions(conv)
        try:
            sys_obj.ingest(sessions, conv_id)
        except Exception as e:
            _log(f"  ERROR ingest: {e}")
            continue

        qas = conv["qa"][:args.max_qa]
        for qi, qa in enumerate(qas):
            if qi in completed_idx:
                continue
            q = qa.get("question", "")
            gold = str(qa.get("answer", ""))
            cat = str(qa.get("category", "uncategorized"))
            try:
                t0 = time.time()
                pred = sys_obj.answer(q)
                dt = time.time() - t0
            except Exception as e:
                pred = f"Error: {e}"
                dt = 0.0
            f1 = token_f1(pred, gold)
            jc, jr = judge_answer(q, pred, gold)
            prev_details.append({
                "qa_idx": qi, "question": q, "gold": gold,
                "prediction": pred, "f1": f1, "judge_correct": bool(jc),
                "judge_reason": jr, "category": cat,
                "answer_time": round(dt, 2),
            })
            acc = sum(1.0 if d["judge_correct"] else 0.0 for d in prev_details) / len(prev_details)
            results["per_conversation"][conv_id] = {"n_questions": len(prev_details),
                                                   "judge_accuracy": acc}
            results["details"][conv_id] = prev_details
            with open(out, "w") as f:
                json.dump(results, f, indent=2, default=str)
            if qi % 10 == 0 or qi == len(qas) - 1:
                _log(f"  {conv_id} QA {qi+1}/{len(qas)}  judge={'C' if jc else 'W'}  rolling={acc:.3f}")
        sys_obj.reset()

    # Aggregate
    total = []
    cat_judge = defaultdict(list)
    for conv_id, recs in results["details"].items():
        for r in recs:
            total.append(1.0 if r["judge_correct"] else 0.0)
            cat_judge[r["category"]].append(1.0 if r["judge_correct"] else 0.0)
    if total:
        results["aggregate"] = {"judge_accuracy": sum(total) / len(total), "n": len(total)}
        results["per_category"] = {
            c: {"n": len(v), "judge_accuracy": sum(v) / len(v)} for c, v in cat_judge.items()
        }
    with open(out, "w") as f:
        json.dump(results, f, indent=2, default=str)
    _log(f"\nDONE {args.system}: {results.get('aggregate', {}).get('judge_accuracy', 0):.3f} "
         f"(n={results.get('aggregate', {}).get('n', 0)})")


if __name__ == "__main__":
    main()
