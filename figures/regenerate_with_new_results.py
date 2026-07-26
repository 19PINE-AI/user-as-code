"""Regenerate the benchmark figure from certified full-LOCOMO artifacts.

The figure reports all 1,986 questions for both Krill-hosted backbones. Token
F1 and judge accuracy use the 1,540 answer-bearing questions (categories 1--4);
refusal accuracy uses the 446 adversarial questions (category 5).
"""

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent

BLUE = "#4A90D9"
GREEN = "#50B86C"
ORANGE = "#F5A623"
RED = "#D94A4A"
PURPLE = "#8B5CF6"
GRAY = "#9CA3AF"
LIGHTBLUE = "#78B7E5"

SYSTEMS = [
    ("full_context", "Full Context", GRAY),
    ("uac_v5", "UaC (ours)", BLUE),
    ("memmachine", "MemMachine", GREEN),
    ("hindsight", "Hindsight (lite)", LIGHTBLUE),
    ("evermemos", "EverMemOS (lite)", PURPLE),
    ("a_mem", "A-MEM", ORANGE),
    ("mem0", "Mem0", RED),
]

SUITES = [
    ("full_locomo_gpt56_luna", "GPT-5.6 Luna"),
    ("full_locomo_gemini3_flash_preview", "Gemini 3 Flash Preview"),
]

METRICS = [
    ("official_token_f1", "Token F1"),
    ("judge_accuracy", "Judge accuracy"),
    ("refusal_accuracy", "Refusal accuracy"),
]


def find_results_dir():
    """Find the repository-level experiments/results directory."""
    for parent in (HERE, *HERE.parents):
        candidate = parent / "experiments" / "results"
        if all((candidate / suite).is_dir() for suite, _ in SUITES):
            return candidate
    raise FileNotFoundError(
        "Could not locate both certified full-LOCOMO result directories"
    )


def load_suite(results_dir, suite):
    """Load and validate the three plotted metrics for one backbone."""
    metrics = {}
    for system, _, _ in SYSTEMS:
        path = results_dir / suite / f"{system}.json"
        with path.open(encoding="utf-8") as handle:
            artifact = json.load(handle)

        aggregate = artifact["aggregate"]
        answer = aggregate["answer_bearing"]
        adversarial = aggregate["adversarial"]
        if artifact.get("system") != system:
            raise ValueError(f"System mismatch in {path}")
        if (
            aggregate.get("n_expected") != 1986
            or aggregate.get("n_completed") != 1986
            or aggregate.get("coverage") != 1.0
            or answer.get("n") != 1540
            or adversarial.get("n") != 446
        ):
            raise ValueError(f"Incomplete or unexpected aggregate in {path}")

        metrics[system] = {
            "official_token_f1": 100 * answer["official_token_f1"],
            "judge_accuracy": 100 * answer["judge_accuracy"],
            "refusal_accuracy": 100 * adversarial["refusal_accuracy"],
        }
    return metrics


def generate_benchmark_figure(output_dir=None):
    """Generate PDF and PNG benchmark figures and return their paths."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 9,
            "axes.titlesize": 10,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "figure.dpi": 300,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.05,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    results_dir = find_results_dir()
    suite_metrics = {
        suite: load_suite(results_dir, suite) for suite, _ in SUITES
    }
    output_dir = Path(output_dir) if output_dir else HERE
    output_dir.mkdir(parents=True, exist_ok=True)

    labels = [label for _, label, _ in SYSTEMS]
    colors = [color for _, _, color in SYSTEMS]
    y_positions = list(range(len(SYSTEMS)))
    fig, axes = plt.subplots(2, 3, figsize=(9.8, 4.9), sharex=True, sharey=True)

    for row, (suite, backbone_label) in enumerate(SUITES):
        for column, (metric_key, metric_label) in enumerate(METRICS):
            ax = axes[row][column]
            values = [
                suite_metrics[suite][system][metric_key]
                for system, _, _ in SYSTEMS
            ]
            bars = ax.barh(
                y_positions,
                values,
                color=colors,
                edgecolor="white",
                linewidth=0.6,
                height=0.68,
            )
            bars[0].set_hatch("///")
            bars[0].set_edgecolor("#6B7280")
            bars[1].set_edgecolor("#1F5F99")
            bars[1].set_linewidth(1.2)

            if row == 0:
                ax.set_title(metric_label, fontweight="bold", pad=6)
            if column == 0:
                ax.set_yticks(y_positions, labels)
            ax.tick_params(axis="y", labelleft=(column == 0), length=0)
            ax.set_xlim(0, 106)
            ax.set_xticks([0, 25, 50, 75, 100])
            ax.grid(axis="x", color="#D1D5DB", linewidth=0.5, alpha=0.8)
            ax.set_axisbelow(True)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_visible(False)
            if row == 1:
                ax.set_xlabel("Score (%)", labelpad=2)

            for bar, value in zip(bars, values):
                ax.text(
                    min(value + 1.1, 102.0),
                    bar.get_y() + bar.get_height() / 2,
                    f"{value:.1f}",
                    ha="left",
                    va="center",
                    fontsize=7,
                    color="#111827",
                )

        axes[row][0].text(
            -0.49,
            0.5,
            backbone_label,
            transform=axes[row][0].transAxes,
            rotation=90,
            ha="center",
            va="center",
            fontsize=9.5,
            fontweight="bold",
        )

    axes[0][0].invert_yaxis()

    fig.suptitle(
        "Full LOCOMO evaluation (all 1,986 questions)",
        y=0.99,
        fontsize=11,
        fontweight="bold",
    )
    fig.text(
        0.56,
        0.012,
        "F1/Judge: categories 1–4 (n=1,540)   •   Refusal: category 5 (n=446)",
        ha="center",
        va="bottom",
        fontsize=8,
        color="#374151",
    )
    fig.subplots_adjust(
        left=0.205, right=0.995, top=0.90, bottom=0.14, wspace=0.17, hspace=0.17
    )

    pdf_path = output_dir / "benchmarks.pdf"
    png_path = output_dir / "benchmarks.png"
    fig.savefig(pdf_path)
    fig.savefig(png_path)
    plt.close(fig)

    for suite, backbone_label in SUITES:
        print(backbone_label)
        for system, label, _ in SYSTEMS:
            values = suite_metrics[suite][system]
            print(
                f"  {label:18s} "
                f"F1={values['official_token_f1']:.1f}  "
                f"Judge={values['judge_accuracy']:.1f}  "
                f"Refusal={values['refusal_accuracy']:.1f}"
            )
    print(f"Saved {pdf_path}")
    print(f"Saved {png_path}")
    return pdf_path, png_path


def main():
    generate_benchmark_figure()


if __name__ == "__main__":
    main()
