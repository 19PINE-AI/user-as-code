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
from matplotlib.ticker import NullFormatter

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from generate_figures import BLUE, GREEN, ORANGE, RED, GRAY, PURPLE  # noqa: E402

R = pathlib.Path(__file__).resolve().parents[2] / "experiments" / "results"

# The paper repository does not ship the raw experiment directory. Keep the
# published per-N values here so the committed figure remains reproducible;
# local raw results take precedence when they are available.
PUBLISHED_PER_N = {
    "fc_repl": {20: 100, 50: 100, 100: 100, 200: 100, 500: 100},
    "uac_v5": {20: 100, 50: 100, 100: 100, 200: 100, 500: 100},
    "full_context": {20: 100, 50: 90, 100: 100, 200: 90, 500: 90},
    "memmachine": {20: 100, 50: 55, 100: 20, 200: 15, 500: 25},
    "mem0": {20: 5, 50: 10, 100: 0, 200: 0, 500: 15},
}

plt.rcParams.update({
    "font.family": "STIXGeneral",
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
})


def per_n(name):
    path = R / f"analytical_{name}.json"
    if not path.exists():
        return PUBLISHED_PER_N.get(name)
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
        ("uac_v5", "UaC", GREEN, "s", "-"),
        ("full_context", "Full Context (no tool)", GRAY, "^", "--"),
        ("memmachine", "MemMachine", ORANGE, "d", ":"),
        ("mem0", "Mem0", RED, "v", ":"),
    ]
    ns = [20, 50, 100, 200, 500]
    # Reserve a separate band below the axes for the legend so it never
    # obscures the accuracy curves.
    # Generate near the final AAAI column size so LaTeX does not shrink the
    # labels below the required 9-point minimum.
    fig, ax = plt.subplots(figsize=(3.2, 3.0))
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
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.tick_params(axis="x", which="minor", labelbottom=False)
    ax.set_xlabel("Records per case (N, log scale)")
    ax.set_ylabel("Accuracy (%)")
    ax.set_ylim(-5, 105)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.grid(True, alpha=0.3, linestyle="-", linewidth=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.08),
               framealpha=0.9, ncol=2, columnspacing=0.8, handlelength=1.5)
    plt.tight_layout(rect=(0, 0.27, 1, 1))
    out = pathlib.Path(__file__).parent / "analytical_scaling.pdf"
    plt.savefig(out)
    plt.savefig(str(out).replace(".pdf", ".png"))
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
