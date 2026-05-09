#!/usr/bin/env python3
"""Aggregate all new experiment results into a single summary for the paper."""
import json
import pathlib
from collections import defaultdict

R = pathlib.Path(__file__).resolve().parent / "results"

def load(name):
    p = R / name
    return json.load(open(p)) if p.exists() else None


def summarize_locomo(name, data):
    if not data:
        return None
    # Aggregate over ALL details, including in-flight (per-conv stats may not
    # have been written yet if a conversation is still running).
    n_total, n_judge, sum_f1 = 0, 0, 0.0
    cat = defaultdict(lambda: {"n": 0, "judge": 0, "f1": 0.0})
    for conv_id, details in data.get("details", {}).items():
        for d in details:
            n_total += 1
            sum_f1 += d.get("f1", 0)
            if d.get("judge_correct"):
                n_judge += 1
            c = d.get("category", 0)
            cat[c]["n"] += 1
            cat[c]["f1"] += d.get("f1", 0)
            if d.get("judge_correct"):
                cat[c]["judge"] += 1
    out = {
        "name": name,
        "n_total": n_total,
        "judge_accuracy": n_judge / n_total if n_total else 0,
        "f1": sum_f1 / n_total if n_total else 0,
        "per_category": {
            str(c): {
                "n": v["n"],
                "judge_accuracy": v["judge"] / v["n"] if v["n"] else 0,
                "f1": v["f1"] / v["n"] if v["n"] else 0,
            }
            for c, v in sorted(cat.items())
        },
    }
    out["per_conversation"] = data.get("per_conversation", {})
    return out


def summarize_lme(name, data):
    if not data:
        return None
    by_type = defaultdict(lambda: {"n": 0, "correct": 0})
    n_total, n_correct = 0, 0
    for qid, d in data.get("by_question", {}).items():
        n_total += 1
        t = d["question_type"]
        by_type[t]["n"] += 1
        if d.get("judge_correct"):
            n_correct += 1
            by_type[t]["correct"] += 1
    return {
        "name": name,
        "n_total": n_total,
        "accuracy": n_correct / n_total if n_total else 0,
        "per_type": {
            t: {
                "n": v["n"],
                "accuracy": v["correct"] / v["n"] if v["n"] else 0,
            }
            for t, v in sorted(by_type.items())
        },
    }


def main():
    print("=" * 70)
    print("LOCOMO 5-CONVERSATION RESULTS")
    print("=" * 70)
    print(f"{'System':<22} {'N':>6} {'Judge':>10} {'F1':>10}")
    print("-" * 50)
    for name, fn in [
        ("UaC v5", "locomo5_uac_v5.json"),
        ("Full Context", "locomo5_full_context.json"),
        ("Mem0", "locomo5_mem0.json"),
        ("A-MEM", "locomo5_a_mem.json"),
        ("UaC v5 (GPT-5.4)", "locomo_gpt54_uac_v5.json"),
    ]:
        d = load(fn)
        s = summarize_locomo(name, d)
        if s:
            print(f"{name:<22} {s['n_total']:>6} {s['judge_accuracy']:>10.3f} {s['f1']:>10.3f}")
        else:
            print(f"{name:<22} (no results)")

    print()
    print("=" * 70)
    print("LongMemEval 200-QUESTION RESULTS")
    print("=" * 70)
    print(f"{'System':<22} {'N':>6} {'Acc':>10}")
    print("-" * 40)
    for name, fn in [
        ("UaC v5", "lme200_uac_v5.json"),
        ("Full Context", "lme200_full_context.json"),
        ("Mem0", "lme200_mem0.json"),
        ("A-MEM", "lme200_a_mem.json"),
    ]:
        d = load(fn)
        s = summarize_lme(name, d)
        if s:
            print(f"{name:<22} {s['n_total']:>6} {s['accuracy']:>10.3f}")
        else:
            print(f"{name:<22} (no results)")

    # Per-category for UaC v5 vs Full Context on LOCOMO
    print()
    print("=" * 70)
    print("LOCOMO PER-CATEGORY (UaC v5 vs Full Context)")
    print("=" * 70)
    uac = summarize_locomo("UaC v5", load("locomo5_uac_v5.json")) or {}
    fc = summarize_locomo("Full Context", load("locomo5_full_context.json")) or {}
    cats = sorted(set(uac.get("per_category", {}).keys()) | set(fc.get("per_category", {}).keys()))
    for c in cats:
        u = uac.get("per_category", {}).get(c, {})
        f = fc.get("per_category", {}).get(c, {})
        print(f"  cat {c}: UaC={u.get('judge_accuracy', 0):.3f} (n={u.get('n', 0)}) | FC={f.get('judge_accuracy', 0):.3f} (n={f.get('n', 0)})")

    # Per-type for LME UaC v5 vs Full Context
    print()
    print("=" * 70)
    print("LongMemEval PER-TYPE")
    print("=" * 70)
    types = sorted([t for t in ["knowledge-update","multi-session","single-session-assistant",
                                "single-session-preference","single-session-user","temporal-reasoning"]])
    rows = {
        "UaC v5": summarize_lme("UaC v5", load("lme200_uac_v5.json")) or {},
        "Full Context": summarize_lme("Full Context", load("lme200_full_context.json")) or {},
        "Mem0": summarize_lme("Mem0", load("lme200_mem0.json")) or {},
        "A-MEM": summarize_lme("A-MEM", load("lme200_a_mem.json")) or {},
    }
    print(f"  {'Type':<28} " + " ".join(f"{n:>14}" for n in rows.keys()))
    for t in types:
        cells = []
        for n, r in rows.items():
            v = r.get("per_type", {}).get(t, {})
            cells.append(f"{v.get('accuracy', 0):.3f} (n={v.get('n', 0)})")
        print(f"  {t:<28} " + " ".join(f"{c:>14}" for c in cells))


if __name__ == "__main__":
    main()
