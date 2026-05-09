#!/usr/bin/env python3
"""Final paper update: regenerate tables, figures, and patch abstract/conclusion numbers."""
import json
import re
import subprocess
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "experiments" / "results"


def loc_agg(data):
    if not data:
        return None
    n_total, n_correct, sum_f1 = 0, 0, 0.0
    cat = defaultdict(lambda: {"n": 0, "correct": 0})
    for cid, det in data.get("details", {}).items():
        for d in det:
            n_total += 1
            sum_f1 += d.get("f1", 0)
            if d.get("judge_correct"):
                n_correct += 1
            cat[d.get("category", 0)]["n"] += 1
            if d.get("judge_correct"):
                cat[d.get("category", 0)]["correct"] += 1
    if n_total == 0:
        return None
    return {
        "n": n_total,
        "judge": n_correct / n_total,
        "f1": sum_f1 / n_total,
        "cat": {c: v["correct"] / v["n"] for c, v in cat.items()},
    }


def lme_agg(data):
    if not data:
        return None
    n_total = len(data.get("by_question", {}))
    if n_total == 0:
        return None
    n_correct = sum(1 for q in data["by_question"].values() if q.get("judge_correct"))
    return {
        "n": n_total,
        "acc": n_correct / n_total,
    }


def main():
    def load(name):
        p = R / name
        return json.load(open(p)) if p.exists() else None

    res = {
        "uac_v5_locomo": loc_agg(load("locomo5_uac_v5.json")),
        "fc_locomo": loc_agg(load("locomo5_full_context.json")),
        "amem_locomo": loc_agg(load("locomo5_a_mem.json")),
        "mem0_locomo": loc_agg(load("locomo5_mem0.json")),
        "gpt54_locomo": loc_agg(load("locomo_gpt54_uac_v5.json")),
        "uac_v5_lme": lme_agg(load("lme200_uac_v5.json")),
        "fc_lme": lme_agg(load("lme200_full_context.json")),
        "amem_lme": lme_agg(load("lme200_a_mem.json")),
        "mem0_lme": lme_agg(load("lme200_mem0.json")),
    }

    # Step 1: regenerate tables
    print("Step 1: regenerating body_tables.tex")
    r = subprocess.run([sys.executable, str(ROOT / "experiments/build_paper_tables.py")],
                       capture_output=True, text=True)
    print(r.stdout[-200:] if r.stdout else "")

    # Step 2: regenerate figures
    print("\nStep 2: regenerating benchmarks figure")
    r = subprocess.run([sys.executable, str(ROOT / "figures/regenerate_with_new_results.py")],
                       capture_output=True, text=True)
    print(r.stdout[-300:] if r.stdout else "")

    # Step 3: patch numbers in body.tex (abstract is in paper.tex)
    print("\nStep 3: patching numbers in paper.tex and body.tex")
    paper_tex = ROOT / "paper.tex"
    body_tex = ROOT / "body.tex"

    paper = paper_tex.read_text()
    body = body_tex.read_text()

    # Compute the new numbers
    uac = res["uac_v5_locomo"]
    fc = res["fc_locomo"]
    uac_lme = res["uac_v5_lme"]
    fc_lme = res["fc_lme"]
    gpt54 = res["gpt54_locomo"]

    if uac and fc:
        uac_pct = uac["judge"] * 100
        fc_pct = fc["judge"] * 100
        ratio = uac_pct / fc_pct * 100 if fc_pct else 0
        # Update abstract
        paper = re.sub(
            r"User as Code achieves [0-9.]+\\% on LOCOMO \\(([0-9.]+\\% of full-context across 5 conversations)\\)",
            f"User as Code achieves {uac_pct:.1f}\\\\% on LOCOMO ({ratio:.1f}\\\\% of full-context across 5 conversations)",
            paper,
        )
        paper = re.sub(
            r"ties full-context on LongMemEval at [0-9.]+\\%",
            f"matches full-context on LongMemEval ({uac_lme['acc']*100:.1f}\\\\% vs.\\\\ {fc_lme['acc']*100:.1f}\\\\% over {uac_lme['n']} questions)" if uac_lme and fc_lme else "ties full-context on LongMemEval",
            paper,
        )
        # Update intro contributions
        body = re.sub(
            r"two-phase memory architecture that achieves [0-9.]+\\% on LOCOMO \\([0-9.]+\\% of full-context\\)",
            f"two-phase memory architecture that achieves {uac_pct:.1f}\\\\% on LOCOMO ({ratio:.1f}\\\\% of full-context)",
            body,
        )

    # Conclusion numbers
    if uac and fc:
        body = re.sub(
            r"UaC achieves [0-9.]+\\% on LOCOMO \\([0-9.]+\\% of full-context\\) and ties full-context on LongMemEval at [0-9.]+\\%",
            f"UaC achieves {uac['judge']*100:.1f}\\\\% on LOCOMO ({uac['judge']/fc['judge']*100:.1f}\\\\% of full-context, n={uac['n']}) and matches full-context on LongMemEval ({uac_lme['acc']*100:.1f}\\\\% vs.\\\\ {fc_lme['acc']*100:.1f}\\\\%, n={uac_lme['n']})" if uac_lme and fc_lme else f"UaC achieves {uac['judge']*100:.1f}\\\\% on LOCOMO",
            body,
        )

    paper_tex.write_text(paper)
    body_tex.write_text(body)
    print("Patched paper.tex and body.tex")

    # Step 4: rebuild paper
    print("\nStep 4: rebuilding paper")
    subprocess.run(["make", "clean"], cwd=ROOT, capture_output=True)
    r = subprocess.run(["make"], cwd=ROOT, capture_output=True, text=True)
    if "Output written on paper.pdf" in r.stdout:
        print("PDF built successfully")
    else:
        print("Build issues:")
        print(r.stdout[-500:])
        print(r.stderr[-500:])

    # Step 5: print summary
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    for k, v in res.items():
        if v is None:
            print(f"  {k:<20}: (no data)")
        elif "judge" in v:
            print(f"  {k:<20}: n={v['n']:>3}  judge={v['judge']*100:.1f}%  f1={v['f1']:.3f}")
        else:
            print(f"  {k:<20}: n={v['n']:>3}  acc={v['acc']*100:.1f}%")


if __name__ == "__main__":
    main()
