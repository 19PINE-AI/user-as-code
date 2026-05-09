#!/usr/bin/env python3
"""Run all 3 modularity strategies on the 30-case benchmark."""
from __future__ import annotations
import argparse
import json
import pathlib
import sys
import time
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from analytical_bench.modularity_runners import RUNNERS  # noqa: E402
from analytical_bench.scoring import score  # noqa: E402

CASES_PATH = pathlib.Path(__file__).resolve().parent / "results" / "modularity_cases.json"
RESULTS_DIR = pathlib.Path(__file__).resolve().parent / "results"


def _log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("strategy", choices=list(RUNNERS.keys()))
    args = ap.parse_args()

    bundle = json.load(open(CASES_PATH))
    user_state = bundle["user_state"]
    summaries = bundle["domain_summaries"]
    cases = bundle["cases"]

    out = RESULTS_DIR / f"modularity_{args.strategy}.json"
    if out.exists():
        results = json.load(open(out))
    else:
        results = {"strategy": args.strategy, "by_case": {}}

    runner = RUNNERS[args.strategy]
    _log(f"strategy={args.strategy}  cases={len(cases)}  done={len(results['by_case'])}")
    for i, case in enumerate(cases):
        cid = case["case_id"]
        if cid in results["by_case"]:
            continue
        try:
            t0 = time.time()
            r = runner(case, user_state, summaries)
            dt = time.time() - t0
            ok = score(case["answer_kind"], r["answer"], case["gold"])
            results["by_case"][cid] = {
                "target_domain": case["target_domain"],
                "question": case["question"],
                "gold": case["gold"],
                "prediction": r["answer"],
                "correct": ok,
                "answer_time": round(dt, 1),
                "turns": r.get("turns", 1),
                "tool_calls": r.get("tool_calls", 0),
                "usage": r.get("usage", {"prompt": 0, "output": 0, "thoughts": 0, "cached": 0}),
            }
            _log(f"  [{i+1}/{len(cases)}] {cid} {'OK' if ok else 'WR'} [{dt:.1f}s]  pred={str(r['answer'])[:60]!r}")
        except Exception as e:
            _log(f"  [{i+1}/{len(cases)}] {cid} ERROR: {e}")
            traceback.print_exc()
            results["by_case"][cid] = {"target_domain": case["target_domain"],
                                        "question": case["question"], "gold": case["gold"],
                                        "prediction": f"ERROR: {e}", "correct": False,
                                        "error": str(e)}
        with open(out, "w") as f:
            json.dump(results, f, indent=2, default=str)

    n_total = len(results["by_case"])
    n_correct = sum(1 for v in results["by_case"].values() if v.get("correct"))
    tp = sum(v.get("usage", {}).get("prompt", 0) for v in results["by_case"].values())
    to = sum(v.get("usage", {}).get("output", 0) for v in results["by_case"].values())
    tt = sum(v.get("usage", {}).get("thoughts", 0) for v in results["by_case"].values())
    results["aggregate"] = {
        "n": n_total, "correct": n_correct, "accuracy": n_correct / max(n_total, 1),
        "prompt_tokens": tp, "output_tokens": to, "thoughts_tokens": tt,
    }
    with open(out, "w") as f:
        json.dump(results, f, indent=2, default=str)
    _log(f"\nDONE {args.strategy}: {n_correct}/{n_total} = {n_correct/max(n_total,1):.3f}")
    _log(f"  prompt={tp:,}  output={to:,}  thoughts={tt:,}")


if __name__ == "__main__":
    main()
