"""Regenerate benchmarks figure using actual experiment results."""
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
    # Load all results
    sys.path.insert(0, str(Path(__file__).parent))
    from generate_figures import (BLUE, GRAY, ORANGE, RED, LIGHTBLUE, GREEN, PURPLE,
                                  fig_architecture, fig_active_service, fig_ablation)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "serif", "font.size": 10,
                         "savefig.dpi": 300, "savefig.bbox": "tight",
                         "savefig.pad_inches": 0.05, "figure.dpi": 300})

    locomo_uac = aggregate_locomo(load("locomo5_uac_v5.json"))
    locomo_fc = aggregate_locomo(load("locomo5_full_context.json"))
    locomo_amem = aggregate_locomo(load("locomo5_a_mem.json"))
    locomo_mem0 = aggregate_locomo(load("locomo5_mem0.json"))
    locomo_gpt = aggregate_locomo(load("locomo_gpt54_uac_v5.json"))

    lme_uac = aggregate_lme(load("lme200_uac_v5.json"))
    lme_fc = aggregate_lme(load("lme200_full_context.json"))
    lme_amem = aggregate_lme(load("lme200_a_mem.json"))
    lme_mem0 = aggregate_lme(load("lme200_mem0.json"))

    print(f"LOCOMO UaC v5      : {locomo_uac}")
    print(f"LOCOMO Full Context: {locomo_fc}")
    print(f"LOCOMO A-MEM       : {locomo_amem}")
    print(f"LOCOMO Mem0        : {locomo_mem0}")
    print(f"LOCOMO UaC GPT-5.4 : {locomo_gpt}")
    print(f"LME UaC v5         : {lme_uac}")
    print(f"LME Full Context   : {lme_fc}")
    print(f"LME A-MEM          : {lme_amem}")
    print(f"LME Mem0           : {lme_mem0}")

    # Build benchmarks figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7, 3))

    def pct(t):
        return t[0] * 100 if t else 0

    locomo_systems = ["UaC v5\n(ours)", "Full\nContext", "A-MEM", "Mem0"]
    locomo = [pct(locomo_uac), pct(locomo_fc), pct(locomo_amem), pct(locomo_mem0)]
    locomo_n = [
        locomo_uac[1] if locomo_uac else 0,
        locomo_fc[1] if locomo_fc else 0,
        locomo_amem[1] if locomo_amem else 0,
        locomo_mem0[1] if locomo_mem0 else 0,
    ]
    colors_l = [BLUE, GRAY, ORANGE, RED]

    bars = ax1.bar(range(len(locomo_systems)), locomo, color=colors_l, edgecolor="white", linewidth=0.5, width=0.7)
    ax1.set_xticks(range(len(locomo_systems)))
    ax1.set_xticklabels(locomo_systems, fontsize=8)
    ax1.set_ylabel("LLM-Judge Accuracy (%)")
    n_str = "/".join(str(n) for n in locomo_n if n)
    ax1.set_title(f"LOCOMO (5 conversations, n=300)", fontweight="bold")
    ax1.set_ylim(0, 100)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    for bar, val in zip(bars, locomo):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                 f"{val:.1f}", ha="center", va="bottom", fontsize=8, fontweight="bold")
    bars[0].set_edgecolor(BLUE)
    bars[0].set_linewidth(2)

    lme_systems = ["UaC v5\n(ours)", "Full\nContext", "A-MEM", "Mem0"]
    lme = [pct(lme_uac), pct(lme_fc), pct(lme_amem), pct(lme_mem0)]
    bars2 = ax2.bar(range(len(lme_systems)), lme, color=[BLUE, GRAY, ORANGE, RED],
                    edgecolor="white", linewidth=0.5, width=0.7)
    ax2.set_xticks(range(len(lme_systems)))
    ax2.set_xticklabels(lme_systems, fontsize=8)
    ax2.set_title(f"LongMemEval (n=200)", fontweight="bold")
    ax2.set_ylim(0, 100)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    for bar, val in zip(bars2, lme):
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
