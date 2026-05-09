#!/usr/bin/env python3
"""Generate the LaTeX tables for the paper from experiment results.

Outputs body_tables.tex which body.tex can \\input{} into.
"""
import json
import pathlib
from collections import defaultdict

R = pathlib.Path(__file__).resolve().parent / "results"


def load(name):
    p = R / name
    return json.load(open(p)) if p.exists() else None


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
        "cat_n": {c: v["n"] for c, v in cat.items()},
    }


def lme_agg(data):
    if not data:
        return None
    n_total = len(data.get("by_question", {}))
    if n_total == 0:
        return None
    n_correct = sum(1 for q in data["by_question"].values() if q.get("judge_correct"))
    by_type = defaultdict(lambda: {"n": 0, "correct": 0})
    for q in data["by_question"].values():
        t = q["question_type"]
        by_type[t]["n"] += 1
        if q.get("judge_correct"):
            by_type[t]["correct"] += 1
    return {
        "n": n_total,
        "acc": n_correct / n_total,
        "per_type": {t: v["correct"] / v["n"] for t, v in by_type.items()},
        "per_type_n": {t: v["n"] for t, v in by_type.items()},
    }


def fmt_pct(v, prec=1):
    if v is None:
        return "---"
    return f"{v*100:.{prec}f}"


def main():
    # Load
    res = {
        "uac_v5_locomo": loc_agg(load("locomo5_uac_v5.json")),
        "fc_locomo": loc_agg(load("locomo5_full_context.json")),
        "amem_locomo": loc_agg(load("locomo5_a_mem.json")),
        "mem0_locomo": loc_agg(load("locomo5_mem0.json")),
        "memmachine_locomo": loc_agg(load("locomo5_memmachine.json")),
        "gpt54_locomo": loc_agg(load("locomo_gpt54_uac_v5.json")),
        "uac_v5_lme": lme_agg(load("lme200_uac_v5.json")),
        "fc_lme": lme_agg(load("lme200_full_context.json")),
        "amem_lme": lme_agg(load("lme200_a_mem.json")),
        "mem0_lme": lme_agg(load("lme200_mem0.json")),
    }

    print("=" * 70)
    for k, v in res.items():
        if v is None:
            print(f"  {k:<20}: (no data)")
        elif "judge" in v:
            print(f"  {k:<20}: n={v['n']:>3}  judge={fmt_pct(v['judge'])}  f1={v['f1']:.3f}")
        else:
            print(f"  {k:<20}: n={v['n']:>3}  acc={fmt_pct(v['acc'])}")
    print("=" * 70)

    # ----- Build LaTeX tables -----
    out = []

    # Table 1: LOCOMO
    out.append(r"""\begin{table}[t]
\centering
\caption{LOCOMO results (5 conversations, 60 QAs each, 300 total). LLM-as-Judge accuracy with thinking-enabled Gemini~3 Flash judge. UaC, Full Context, Mem0, and A-MEM use Gemini~3 Flash for answer generation; UaC (GPT-5.4) substitutes GPT-5.4 for cross-LLM portability.}
\label{tab:locomo}
\begin{tabular}{@{}lccc@{}}
\toprule
\textbf{System} & \textbf{LLM-Judge} & \textbf{Token F1} & \textbf{N} \\
\midrule""")
    rows = [
        ("Full Context (upper bound)", res["fc_locomo"]),
        ("UaC v5 (ours, Gemini)", res["uac_v5_locomo"]),
        ("MemMachine~\\citep{wang2026memmachine}", res["memmachine_locomo"]),
        ("A-MEM", res["amem_locomo"]),
        ("Mem0", res["mem0_locomo"]),
    ]
    for label, r in rows:
        if r:
            judge = fmt_pct(r["judge"])
            f1 = f"{r['f1']:.3f}"
            n = r["n"]
            row = f"{label} & {judge}\\% & {f1} & {n} \\\\"
        else:
            row = f"{label} & --- & --- & --- \\\\"
        out.append(row)
    out.append(r"\midrule")
    out.append(r"\multicolumn{4}{@{}l}{\textit{Cross-LLM portability (2 conversations, 120 QAs)}} \\")
    if res["gpt54_locomo"]:
        r = res["gpt54_locomo"]
        out.append(f"UaC v5 (ours, GPT-5.4) & {fmt_pct(r['judge'])}\\% & {r['f1']:.3f} & {r['n']} \\\\")
    out.append(r"""\bottomrule
\end{tabular}
\end{table}""")

    # Table 2: LongMemEval
    out.append("")
    out.append(r"""\begin{table}[t]
\centering
\caption{LongMemEval results (200 stratified questions, 40\% sample of the full 500-question split, seed 42). All systems use Gemini~3 Flash for answer generation.}
\label{tab:longmemeval}
\begin{tabular}{@{}lcccccc|c@{}}
\toprule
\textbf{System} & \textbf{KU} & \textbf{MS} & \textbf{SA} & \textbf{SP} & \textbf{SU} & \textbf{TR} & \textbf{Overall} \\
\midrule""")
    types = ["knowledge-update", "multi-session", "single-session-assistant",
             "single-session-preference", "single-session-user", "temporal-reasoning"]
    for label, r in [
        ("Full Context", res["fc_lme"]),
        ("UaC v5 (ours)", res["uac_v5_lme"]),
        ("A-MEM", res["amem_lme"]),
        ("Mem0", res["mem0_lme"]),
    ]:
        if r:
            cells = [fmt_pct(r["per_type"].get(t, 0), prec=0) for t in types]
            row = f"{label} & " + " & ".join(cells) + f" & {fmt_pct(r['acc'])} \\\\"
        else:
            row = f"{label} & --- & --- & --- & --- & --- & --- & --- \\\\"
        out.append(row)
    out.append(r"""\bottomrule
\end{tabular}
\begin{flushleft}
\small KU=knowledge-update, MS=multi-session, SA=single-asst, SP=single-pref, SU=single-user, TR=temporal-reasoning. Percentages shown.
\end{flushleft}
\end{table}""")

    # Table 3: Analytical Inference benchmark
    out.append("")
    ana_systems = ["full_context", "fc_repl", "uac_v5", "memmachine", "mem0"]
    ana_data = {}
    for s in ana_systems:
        p = R / f"analytical_{s}.json"
        if p.exists():
            d = json.load(open(p))
            ana_data[s] = d
    if ana_data:
        out.append(r"""\begin{table}[t]
\centering
\caption{Analytical inference benchmark: 100 cases across 10 record types (10 per type) with $N$ records per case ($N \in \{20, 50, 100, 200, 500\}$). Exact-match scoring against deterministic ground truth. \emph{FC+REPL} is Full Context with a Python REPL tool; \emph{UaC v5} loads structured records into a typed-Python REPL.}
\label{tab:analytical}
\begin{tabular}{@{}lccccccc@{}}
\toprule
\textbf{System} & \textbf{Overall} & $N{=}20$ & $N{=}50$ & $N{=}100$ & $N{=}200$ & $N{=}500$ \\
\midrule""")
        labels = {
            "fc_repl": "Full Context + Python REPL",
            "uac_v5": "UaC v5 (structured + REPL)",
            "full_context": "Full Context (no tool)",
            "memmachine": "MemMachine",
            "mem0": "Mem0",
        }
        order = ["fc_repl", "uac_v5", "full_context", "memmachine", "mem0"]
        for s in order:
            if s not in ana_data:
                continue
            d = ana_data[s]
            n_total = len(d["by_case"])
            n_correct = sum(1 for v in d["by_case"].values() if v.get("correct"))
            row = [labels[s], f"{n_correct/n_total*100:.1f}\\%"]
            for n_val in (20, 50, 100, 200, 500):
                cs = [v for v in d["by_case"].values() if v["n"] == n_val]
                c = sum(1 for v in cs if v.get("correct"))
                row.append(f"{c/max(len(cs),1)*100:.0f}\\%")
            out.append(" & ".join(row) + " \\\\")
        out.append(r"""\bottomrule
\end{tabular}
\end{table}""")

    body = "\n".join(out)

    out_path = pathlib.Path(__file__).resolve().parent.parent / "body_tables.tex"
    with open(out_path, "w") as f:
        f.write(body + "\n")
    print(f"\nWrote {out_path}")
    print()
    print(body[:3000])


if __name__ == "__main__":
    main()
