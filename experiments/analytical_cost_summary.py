#!/usr/bin/env python3
"""Aggregate accuracy and token usage for the analytical benchmark and emit
the LaTeX cost-vs-accuracy table.

Gemini 3 Flash pricing assumed: $0.30/M input, $2.50/M output (output incl.
reasoning/thoughts). Adjust if rates change.
"""
import json
import pathlib
from collections import defaultdict

INPUT_PRICE = 0.30 / 1_000_000  # USD per token
OUTPUT_PRICE = 2.50 / 1_000_000  # USD per token (incl thoughts)

R = pathlib.Path(__file__).resolve().parent / "results"

SYSTEMS = [
    ("fc_repl", "Full Context + REPL"),
    ("uac_v5", "UaC v5 (structured + REPL)"),
    ("full_context", "Full Context (no tool)"),
    ("memmachine", "MemMachine"),
    ("mem0", "Mem0"),
]


def load(name):
    p = R / f"analytical_{name}.json"
    if not p.exists():
        return None
    return json.load(open(p))


def aggregate(d):
    if d is None:
        return None
    out = {"n": 0, "correct": 0, "prompt": 0, "output": 0, "thoughts": 0,
           "by_n": defaultdict(lambda: {"n": 0, "correct": 0, "prompt": 0,
                                         "output": 0, "thoughts": 0})}
    for v in d["by_case"].values():
        out["n"] += 1
        if v.get("correct"):
            out["correct"] += 1
        u = v.get("usage", {})
        out["prompt"] += u.get("prompt", 0)
        out["output"] += u.get("output", 0)
        out["thoughts"] += u.get("thoughts", 0)
        bn = out["by_n"][v["n"]]
        bn["n"] += 1
        if v.get("correct"):
            bn["correct"] += 1
        bn["prompt"] += u.get("prompt", 0)
        bn["output"] += u.get("output", 0)
        bn["thoughts"] += u.get("thoughts", 0)
    out["accuracy"] = out["correct"] / max(out["n"], 1)
    out["cost_usd"] = out["prompt"] * INPUT_PRICE + (out["output"] + out["thoughts"]) * OUTPUT_PRICE
    out["cost_per_case"] = out["cost_usd"] / max(out["n"], 1)
    return out


def main():
    print(f"{'System':<28} {'Acc':>6} {'Prompt':>10} {'Output':>10} {'Thoughts':>10} {'Cost ($)':>10} {'$/case':>9}")
    print("-" * 88)
    rows = []
    for sys_id, label in SYSTEMS:
        agg = aggregate(load(sys_id))
        if agg is None:
            print(f"{label:<28} (no data)")
            continue
        rows.append((sys_id, label, agg))
        print(f"{label:<28} {agg['accuracy']*100:>5.1f}% {agg['prompt']:>10,} {agg['output']:>10,} {agg['thoughts']:>10,} {agg['cost_usd']:>10.3f} {agg['cost_per_case']*1000:>8.2f}m$")

    print()
    print("Per-N accuracy:")
    print(f"  {'System':<28}  N=20    N=50    N=100   N=200   N=500")
    for sys_id, label, agg in rows:
        cells = []
        for n in (20, 50, 100, 200, 500):
            d = agg["by_n"].get(n, {"n": 0, "correct": 0})
            if d["n"]:
                cells.append(f"{d['correct']/d['n']*100:>5.0f}%")
            else:
                cells.append("  ---")
        print(f"  {label:<28} " + "   ".join(cells))

    # ----- LaTeX table -----
    out_path = pathlib.Path(__file__).resolve().parent.parent / "body_cost_table.tex"
    with open(out_path, "w") as f:
        f.write(r"""\begin{table}[t]
\centering
\caption{Analytical inference: accuracy and token cost across 100 cases. Cost assumes Gemini~3 Flash pricing of \$0.30/M input and \$2.50/M output (output includes reasoning/thoughts). Per-case cost is the total across the 100 cases divided by 100.}
\label{tab:analytical-cost}
\small
\begin{tabular}{@{}lcrrrrr@{}}
\toprule
\textbf{System} & \textbf{Acc} & \textbf{Input} & \textbf{Output} & \textbf{Thoughts} & \textbf{Total} & \textbf{Per case} \\
 & & (M tok) & (M tok) & (M tok) & (USD) & (m\$) \\
\midrule
""")
        for sys_id, label, agg in rows:
            f.write(f"{label} & {agg['accuracy']*100:.1f}\\% & "
                    f"{agg['prompt']/1e6:.2f} & "
                    f"{agg['output']/1e6:.3f} & "
                    f"{agg['thoughts']/1e6:.3f} & "
                    f"\\${agg['cost_usd']:.2f} & "
                    f"{agg['cost_per_case']*1000:.1f} \\\\\n")
        f.write(r"""\bottomrule
\end{tabular}
\end{table}
""")
    print(f"\nWrote {out_path}")

    # Cost-vs-N scaling figure (FC+REPL grows with N, UaC structuring grows with N too,
    # but UaC's per-query cost stays small).
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams.update({"font.family": "serif", "font.size": 10,
                             "savefig.dpi": 300, "savefig.bbox": "tight"})
        ns = [20, 50, 100, 200, 500]
        plot_systems = [
            ("fc_repl", "Full Context + REPL", "#4A90D9"),
            ("uac_v5", "UaC v5 (1 query)", "#50B86C"),
            ("full_context", "Full Context (no tool)", "#9CA3AF"),
            ("memmachine", "MemMachine", "#F5A623"),
            ("mem0", "Mem0", "#D94A4A"),
        ]
        fig, ax = plt.subplots(figsize=(6.0, 3.6))
        for sys_id, label, color in plot_systems:
            agg = aggregate(load(sys_id))
            if agg is None:
                continue
            ys = []
            for n in ns:
                d = agg["by_n"].get(n)
                if d:
                    cost = d["prompt"]*INPUT_PRICE + (d["output"]+d["thoughts"])*OUTPUT_PRICE
                    ys.append(cost / d["n"] * 1000)  # in m$
                else:
                    ys.append(0)
            ax.plot(ns, ys, marker="o", color=color, label=label, linewidth=2)
        # Add UaC v5 amortized line: structuring cost stays fixed, per-query goes to ~$0.001
        # Approximate: UaC structuring is ~98% of one-shot cost, query is ~$0.0014/case
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xticks(ns)
        ax.set_xticklabels([str(n) for n in ns])
        ax.set_xlabel("Records per case (N)")
        ax.set_ylabel("Cost per case (m\\$, log scale)")
        ax.set_title("Per-case cost vs. record count", fontweight="bold")
        ax.grid(True, alpha=0.3, linewidth=0.5)
        ax.legend(loc="lower right", framealpha=0.9, fontsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout()
        fig_path = pathlib.Path(__file__).resolve().parent.parent / "figures" / "analytical_cost.pdf"
        plt.savefig(fig_path)
        plt.savefig(str(fig_path).replace(".pdf", ".png"))
        print(f"Wrote {fig_path}")
    except Exception as e:
        print(f"figure failed: {e}")


if __name__ == "__main__":
    main()
