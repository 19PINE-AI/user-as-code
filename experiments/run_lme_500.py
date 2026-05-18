#!/usr/bin/env python3
"""Run a single memory system on the full 500-question LongMemEval.

Reuses lme200 results: pre-loads lme200_<system>.json into lme500_<system>.json
so already-judged questions are not re-run. Same wrapper classes as run_lme_200.py
"""
from __future__ import annotations
import argparse
import json
import pathlib
import sys
import time
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from runner_utils import _log, judge_answer, GEMINI_MODEL  # noqa: E402
from run_lme_200 import SYSTEMS  # noqa: E402

SAMPLE_PATH = pathlib.Path(__file__).resolve().parent / "results" / "lme_500_full.json"
RESULTS_DIR = pathlib.Path(__file__).resolve().parent / "results"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("system", choices=list(SYSTEMS.keys()))
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int, default=500)
    args = ap.parse_args()

    out = RESULTS_DIR / f"lme500_{args.system}.json"
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

    # Pre-load existing lme200 results so the 200 already-judged aren't re-run
    lme200_path = RESULTS_DIR / f"lme200_{args.system}.json"
    if lme200_path.exists():
        lme200 = json.load(open(lme200_path))
        for qid, d in lme200.get("by_question", {}).items():
            if qid not in results["by_question"]:
                results["by_question"][qid] = d
        _log(f"Loaded {len(lme200.get('by_question', {}))} prior results from {lme200_path.name}")

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

    # Aggregate over all by_question entries (including the 200 reused)
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
