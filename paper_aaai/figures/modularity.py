"""Modularity / Progressive Disclosure ablation figure.

Bar chart pairing accuracy (left axis) and prompt-token cost (right axis,
log scale) for the three loading strategies: monolithic, modular, manifest.
"""
import json
import pathlib
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from generate_figures import BLUE, GREEN, ORANGE, GRAY, RED  # noqa: E402

R = pathlib.Path(__file__).resolve().parents[2] / "experiments" / "results"

plt.rcParams.update({
    "font.family": "serif", "font.size": 10,
    "savefig.dpi": 300, "savefig.bbox": "tight", "savefig.pad_inches": 0.05,
})

INPUT_PRICE = 0.30 / 1_000_000
OUTPUT_PRICE = 2.50 / 1_000_000


def load_strategy(name):
    p = R / f"modularity_{name}.json"
    if not p.exists():
        return None
    d = json.load(open(p))
    a = d["aggregate"]
    cost = (a["prompt_tokens"] * INPUT_PRICE
            + (a["output_tokens"] + a["thoughts_tokens"]) * OUTPUT_PRICE)
    return {
        "name": name,
        "accuracy": a["accuracy"],
        "prompt_tokens": a["prompt_tokens"],
        "cost_usd": cost,
        "n": a["n"],
    }


def main():
    strategies = [
        ("monolithic", "Monolithic\n(always dump)", GRAY),
        ("modular", "Modular\n(on demand)", GREEN),
        ("manifest", "Manifest+\nrouting", BLUE),
    ]
    rows = []
    for sid, _label, _color in strategies:
        r = load_strategy(sid)
        if r:
            rows.append((sid, _label, _color, r))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.5, 3.4))

    # Accuracy
    xs = list(range(len(rows)))
    accs = [r[3]["accuracy"] * 100 for r in rows]
    bars = ax1.bar(xs, accs, color=[r[2] for r in rows], edgecolor="white", linewidth=0.5, width=0.7)
    ax1.set_xticks(xs)
    ax1.set_xticklabels([r[1] for r in rows], fontsize=8)
    ax1.set_ylabel("Accuracy (%)")
    ax1.set_title("Accuracy", fontweight="bold")
    ax1.set_ylim(0, 105)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    for bar, val in zip(bars, accs):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5,
                 f"{val:.0f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")

    # Prompt tokens
    toks = [r[3]["prompt_tokens"] / 1000 for r in rows]
    bars2 = ax2.bar(xs, toks, color=[r[2] for r in rows], edgecolor="white", linewidth=0.5, width=0.7)
    ax2.set_xticks(xs)
    ax2.set_xticklabels([r[1] for r in rows], fontsize=8)
    ax2.set_ylabel("Prompt tokens, all 100 cases (K)")
    ax2.set_title("Prompt-token cost", fontweight="bold")
    ax2.set_yscale("log")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    for bar, val in zip(bars2, toks):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() * 1.1,
                 f"{val:.0f}K", ha="center", va="bottom", fontsize=9, fontweight="bold")

    plt.tight_layout()
    out = pathlib.Path(__file__).parent / "modularity.pdf"
    plt.savefig(out)
    plt.savefig(str(out).replace(".pdf", ".png"))
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
