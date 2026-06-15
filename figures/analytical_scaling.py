"""Generate the analytical-benchmark scaling-by-N figure.

A line plot of accuracy vs N for each system, highlighting how UaC and
FC+REPL stay flat while MemMachine collapses and Full Context (no tool)
degrades past N=100.
"""
import json
import pathlib
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from generate_figures import BLUE, GREEN, ORANGE, RED, GRAY, PURPLE  # noqa: E402

R = pathlib.Path(__file__).resolve().parent.parent / "experiments" / "results"

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "legend.fontsize": 9,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
})


def per_n(name):
    path = R / f"analytical_{name}.json"
    if not path.exists():
        return None
    d = json.load(open(path))
    out = {}
    for v in d["by_case"].values():
        n = v["n"]
        out.setdefault(n, [0, 0])
        out[n][0] += 1
        if v.get("correct"):
            out[n][1] += 1
    return {n: c / max(t, 1) * 100 for n, (t, c) in out.items()}


def main():
    systems = [
        ("fc_repl", "Full Context + REPL", BLUE, "o", "-"),
        ("uac_v5", "UaC (ours)", GREEN, "s", "-"),
        ("full_context", "Full Context (no tool)", GRAY, "^", "--"),
        ("memmachine", "MemMachine", ORANGE, "d", ":"),
        ("mem0", "Mem0", RED, "v", ":"),
    ]
    ns = [20, 50, 100, 200, 500]
    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    for name, label, color, marker, ls in systems:
        data = per_n(name)
        if not data:
            continue
        ys = [data.get(n, 0) for n in ns]
        ax.plot(ns, ys, marker=marker, color=color, label=label,
                linewidth=2, markersize=7, linestyle=ls)
    ax.set_xscale("log")
    ax.set_xticks(ns)
    ax.set_xticklabels([str(n) for n in ns])
    ax.set_xlabel("Records per case (N, log scale)")
    ax.set_ylabel("Accuracy (%)")
    ax.set_ylim(-5, 105)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_title("Analytical inference: accuracy vs. record count", fontweight="bold")
    ax.grid(True, alpha=0.3, linestyle="-", linewidth=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="lower left", framealpha=0.9, ncol=1)
    plt.tight_layout()
    out = pathlib.Path(__file__).parent / "analytical_scaling.pdf"
    plt.savefig(out)
    plt.savefig(str(out).replace(".pdf", ".png"))
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
