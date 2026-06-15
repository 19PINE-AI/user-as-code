"""Regenerate benchmarks figure using full-benchmark experiment results
(LOCOMO 10-conv n=600, LongMemEval n=500)."""
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent / "experiments" / "results"


def load(name):
    p = R / name
    return json.load(open(p)) if p.exists() else None


def aggregate_locomo(data):
    if not data:
        return None
    n_total, n_correct = 0, 0
    for cid, det in data.get("details", {}).items():
        for d in det:
            n_total += 1
            if d.get("judge_correct"):
                n_correct += 1
    return n_correct / n_total if n_total else 0, n_total


def aggregate_lme(data):
    if not data:
        return None
    n_total = len(data.get("by_question", {}))
    n_correct = sum(1 for q in data["by_question"].values() if q.get("judge_correct"))
    return n_correct / n_total if n_total else 0, n_total


def main():
    sys.path.insert(0, str(Path(__file__).parent))
    from generate_figures import (BLUE, GRAY, ORANGE, RED, LIGHTBLUE, GREEN, PURPLE)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "serif", "font.size": 10,
                         "savefig.dpi": 300, "savefig.bbox": "tight",
                         "savefig.pad_inches": 0.05, "figure.dpi": 300})

    sysnames = [
        ("uac_v5",       "UaC",         BLUE),
        ("full_context", "Full Ctx",    GRAY),
        ("memmachine",   "MemMachine",  GREEN),
        ("evermemos",    "EverMemOS",   PURPLE),
        ("hindsight",    "Hindsight",   LIGHTBLUE),
        ("a_mem",        "A-MEM",       ORANGE),
        ("mem0",         "Mem0",        RED),
    ]

    # LOCOMO 10-conv
    locomo_scores, locomo_colors, locomo_labels = [], [], []
    for s, label, col in sysnames:
        agg = aggregate_locomo(load(f"locomo10_{s}.json"))
        if agg is None:
            agg = aggregate_locomo(load(f"locomo5_{s}.json"))
        locomo_scores.append(agg[0] * 100 if agg else 0)
        locomo_colors.append(col)
        locomo_labels.append(label)
        print(f"LOCOMO {s:14s} {agg[1] if agg else 0:>4d}  {agg[0]*100 if agg else 0:.1f}%")

    # LongMemEval 500
    lme_scores, lme_labels, lme_colors = [], [], []
    for s, label, col in sysnames:
        agg = aggregate_lme(load(f"lme500_{s}.json"))
        if agg is None:
            agg = aggregate_lme(load(f"lme200_{s}.json"))
        lme_scores.append(agg[0] * 100 if agg else 0)
        lme_colors.append(col)
        lme_labels.append(label)
        print(f"LME    {s:14s} {agg[1] if agg else 0:>4d}  {agg[0]*100 if agg else 0:.1f}%")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 3.4))

    bars = ax1.bar(range(len(locomo_labels)), locomo_scores, color=locomo_colors,
                   edgecolor="white", linewidth=0.5, width=0.7)
    ax1.set_xticks(range(len(locomo_labels)))
    ax1.set_xticklabels(locomo_labels, fontsize=8.5, rotation=20, ha="right")
    ax1.set_ylabel("LLM-Judge Accuracy (%)")
    ax1.set_title("LOCOMO (10 conversations, n=600)", fontweight="bold")
    ax1.set_ylim(0, 100)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    for bar, val in zip(bars, locomo_scores):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                 f"{val:.1f}", ha="center", va="bottom", fontsize=8, fontweight="bold")
    bars[0].set_edgecolor(BLUE)
    bars[0].set_linewidth(2)

    bars2 = ax2.bar(range(len(lme_labels)), lme_scores, color=lme_colors,
                    edgecolor="white", linewidth=0.5, width=0.7)
    ax2.set_xticks(range(len(lme_labels)))
    ax2.set_xticklabels(lme_labels, fontsize=8.5, rotation=20, ha="right")
    ax2.set_title("LongMemEval (n=500)", fontweight="bold")
    ax2.set_ylim(0, 100)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    for bar, val in zip(bars2, lme_scores):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                 f"{val:.1f}", ha="center", va="bottom", fontsize=8, fontweight="bold")
    bars2[0].set_edgecolor(BLUE)
    bars2[0].set_linewidth(2)

    plt.tight_layout()
    out = Path(__file__).parent / "benchmarks.pdf"
    plt.savefig(str(out))
    plt.savefig(str(out).replace(".pdf", ".png"))
    print(f"Saved {out}")
    plt.close()


if __name__ == "__main__":
    main()
