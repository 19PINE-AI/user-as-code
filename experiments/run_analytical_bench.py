#!/usr/bin/env python3
"""Run a single system over all 100 analytical-benchmark cases.

Usage: run_analytical_bench.py <system> [--cases path] [--limit N] [--start N]
       [--case-id ID] [--output path] [--force]
  system: uac_v5 | full_context | fc_repl | mem0 | memmachine

Resumable: writes per-case results to results/analytical_<system>.json after
every case. Re-running skips already-completed cases.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from analytical_bench.runners import RUNNERS  # noqa: E402
from analytical_bench.scoring import score  # noqa: E402
from analytical_bench.tools import GEMINI_MODEL  # noqa: E402
from krill_client import KRILL_BASE_URL, gemini_cli_user_agent  # noqa: E402

CASES_PATH = pathlib.Path(__file__).resolve().parent / "results" / "analytical_cases.json"
RESULTS_DIR = pathlib.Path(__file__).resolve().parent / "results"


def _log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("system", choices=list(RUNNERS.keys()))
    ap.add_argument("--cases", default=str(CASES_PATH))
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument(
        "--case-id",
        help="Run exactly one case by stable case_id (applied before --start/--limit).",
    )
    ap.add_argument(
        "--output",
        help="Write to an isolated result file instead of results/analytical_<system>.json.",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Recompute selected cases even when they already exist in the output file.",
    )
    args = ap.parse_args()

    runner = RUNNERS[args.system]
    out = pathlib.Path(args.output) if args.output else RESULTS_DIR / f"analytical_{args.system}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    all_cases = json.load(open(args.cases))["cases"]
    if args.case_id:
        all_cases = [case for case in all_cases if case["case_id"] == args.case_id]
        if not all_cases:
            ap.error(f"unknown --case-id: {args.case_id}")
    cases = all_cases[args.start:args.start + args.limit]

    if out.exists():
        results = json.load(open(out))
    else:
        results = {"system": args.system, "by_case": {}}
    results["run_config"] = {
        "provider": "krill",
        "base_url": KRILL_BASE_URL,
        "model": GEMINI_MODEL,
        "user_agent": gemini_cli_user_agent(GEMINI_MODEL),
        "embedding": (
            "chroma-default-onnx-all-MiniLM-L6-v2"
            if args.system in {"mem0", "memmachine"}
            else None
        ),
    }

    n_done = sum(1 for cid in results["by_case"] if cid in {c["case_id"] for c in cases})
    _log(f"system={args.system}  cases={len(cases)}  already_done={n_done}")

    for i, case in enumerate(cases):
        cid = case["case_id"]
        if cid in results["by_case"] and not args.force:
            continue
        try:
            t0 = time.time()
            r = runner(case)
            dt = time.time() - t0
            ok = score(case["answer_kind"], r["answer"], case["gold"])
            results["by_case"][cid] = {
                "type": case["type"],
                "n": case["n"],
                "question_id": case["question_id"],
                "question": case["question"],
                "answer_kind": case["answer_kind"],
                "gold": case["gold"],
                "prediction": r["answer"],
                "correct": ok,
                "answer_time": round(dt, 1),
                "turns": r.get("turns", 1),
                "tool_calls": r.get("tool_calls", 0),
                "usage": r.get("usage", {"prompt": 0, "output": 0, "thoughts": 0, "cached": 0}),
                "structuring_usage": r.get("structuring_usage"),
                "n_retrieved": r.get("n_retrieved"),
                "log": r.get("log", [])[-5:],  # last 5 tool calls only
                "raw": (r.get("raw", "") or "")[-800:],
                "error": r.get("error"),
            }
            status = "OK" if ok else "WR"
            _log(f"  [{i+1}/{len(cases)}] {cid} type={case['type']} n={case['n']} {status} [{dt:.1f}s]  pred={str(r['answer'])[:60]!r}")
        except Exception as e:
            _log(f"  [{i+1}/{len(cases)}] {cid} ERROR: {e}")
            traceback.print_exc()
            results["by_case"][cid] = {
                "type": case["type"], "n": case["n"],
                "question_id": case["question_id"],
                "question": case["question"],
                "answer_kind": case["answer_kind"],
                "gold": case["gold"],
                "prediction": f"ERROR: {e}",
                "correct": False,
                "error": str(e),
            }
        # Save after every case so we can resume cleanly.
        with open(out, "w") as f:
            json.dump(results, f, indent=2, default=str)

    # Aggregate
    by_type: dict[str, dict[str, int]] = {}
    by_n: dict[int, dict[str, int]] = {}
    n_correct = 0
    for v in results["by_case"].values():
        if v.get("correct"):
            n_correct += 1
        t = v["type"]
        n = v["n"]
        by_type.setdefault(t, {"n": 0, "correct": 0})
        by_type[t]["n"] += 1
        if v.get("correct"):
            by_type[t]["correct"] += 1
        by_n.setdefault(n, {"n": 0, "correct": 0})
        by_n[n]["n"] += 1
        if v.get("correct"):
            by_n[n]["correct"] += 1
    total = len(results["by_case"])
    results["aggregate"] = {
        "n_total": total,
        "n_correct": n_correct,
        "accuracy": n_correct / total if total else 0,
    }
    results["per_type"] = {
        t: {"n": v["n"], "correct": v["correct"], "accuracy": v["correct"]/v["n"] if v["n"] else 0}
        for t, v in by_type.items()
    }
    results["per_n"] = {
        str(n): {"n": v["n"], "correct": v["correct"], "accuracy": v["correct"]/v["n"] if v["n"] else 0}
        for n, v in sorted(by_n.items())
    }

    with open(out, "w") as f:
        json.dump(results, f, indent=2, default=str)

    _log(f"\nDONE {args.system}: {n_correct}/{total} = {(n_correct/total if total else 0):.3f}")
    _log(f"  Saved: {out}")
    for t, v in sorted(by_type.items()):
        _log(f"    {t:<14} {v['correct']}/{v['n']}")
    for n, v in sorted(by_n.items()):
        _log(f"    N={n:<4} {v['correct']}/{v['n']}")


if __name__ == "__main__":
    main()
