"""Generate all paper figures."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import numpy as np

plt.rcParams.update({
    'font.family': 'STIXGeneral',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.05,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
})

BLUE = '#4A90D9'
GREEN = '#50B86C'
ORANGE = '#F5A623'
RED = '#D94A4A'
PURPLE = '#8B5CF6'
GRAY = '#9CA3AF'
DARKGRAY = '#4B5563'
LIGHTBLUE = '#DBEAFE'
LIGHTGREEN = '#D1FAE5'
LIGHTORANGE = '#FEF3C7'
LIGHTPURPLE = '#EDE9FE'
LIGHTRED = '#FEE2E2'

# =====================================================================
# Figure 1: Architecture diagram
# =====================================================================
def fig_architecture():
    # Tight canvas around the actual content (no in-figure title; it lives in
    # the caption) so there is no empty top/bottom margin.
    fig, ax = plt.subplots(1, 1, figsize=(9.5, 3.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(1.35, 5.75)
    ax.axis('off')

    # Phase 1 box
    phase1 = mpatches.FancyBboxPatch((0.3, 3.35), 4.2, 2.2,
        boxstyle="round,pad=0.08", facecolor=LIGHTBLUE, edgecolor=BLUE, linewidth=1.5)
    ax.add_patch(phase1)
    ax.text(2.4, 5.35, 'Phase 1: Memorizing', ha='center', fontweight='bold', fontsize=11.2, color=BLUE)
    ax.text(2.4, 5.05, '(per session, append-only)', ha='center', fontsize=10.2, color=DARKGRAY)

    # Session boxes
    for i, label in enumerate(['Session 1', 'Session 2', 'Session 3', '...']):
        x = 0.485 + i * 1.02
        box = mpatches.FancyBboxPatch((x, 4.35), 0.82, 0.4,
            boxstyle="round,pad=0.05", facecolor='white', edgecolor=BLUE, linewidth=0.8)
        ax.add_patch(box)
        ax.text(x + 0.41, 4.55, label, ha='center', va='center', fontsize=10.2)

    # Arrow down to fact list
    ax.annotate('', xy=(2.2, 3.77), xytext=(2.2, 4.35),
        arrowprops=dict(arrowstyle='->', color=BLUE, lw=1.5))
    ax.text(2.32, 4.06, 'Extract facts\n(thinking LLM)', ha='left', va='center',
            fontsize=10.2, linespacing=0.95, color=BLUE)

    # Fact list
    fact_box = mpatches.FancyBboxPatch((0.38, 3.45), 4.0, 0.32,
        boxstyle="round,pad=0.05", facecolor='white', edgecolor=BLUE, linewidth=0.8)
    ax.add_patch(fact_box)
    ax.text(2.38, 3.61, 'Append-only Fact List (~1600 facts)',
            ha='center', va='center', fontsize=10.2, fontweight='bold')

    # Phase 2 box
    phase2 = mpatches.FancyBboxPatch((5.5, 3.35), 4.2, 2.2,
        boxstyle="round,pad=0.08", facecolor=LIGHTGREEN, edgecolor=GREEN, linewidth=1.5)
    ax.add_patch(phase2)
    ax.text(7.6, 5.35, 'Phase 2: Structuring', ha='center', fontweight='bold', fontsize=11.2, color='#15803D')
    ax.text(7.6, 5.05, '(periodic, first 30K serialized characters)', ha='center', fontsize=10.2, color=DARKGRAY)

    # Code representation
    code_box = mpatches.FancyBboxPatch((5.9, 4.32), 3.4, 0.48,
        boxstyle="round,pad=0.04", facecolor='white', edgecolor=GREEN, linewidth=0.8)
    ax.add_patch(code_box)
    ax.text(7.6, 4.56, 'Typed state modules (Code)', ha='center', va='center', fontsize=10.2, fontweight='bold')

    # Arrow from facts to code
    ax.annotate('', xy=(5.5, 4.55), xytext=(4.5, 3.72),
        arrowprops=dict(arrowstyle='->', color='#15803D', lw=1.5, connectionstyle='arc3,rad=-0.2'))
    ax.text(4.98, 3.99, 'Structure\n(thinking LLM)', ha='center', va='center',
            fontsize=10.2, linespacing=0.95, color='#15803D', rotation=39)

    # Analytical execution over the typed view.
    const_box = mpatches.FancyBboxPatch((5.9, 3.58), 3.4, 0.48,
        boxstyle="round,pad=0.05", facecolor=LIGHTORANGE, edgecolor=ORANGE, linewidth=0.8)
    ax.add_patch(const_box)
    ax.text(7.6, 3.82, 'Python REPL  ->  exact aggregation',
            ha='center', va='center', fontsize=10.2, fontweight='bold', color='#92400E')

    # Tier 3 Archive
    archive_box = mpatches.FancyBboxPatch((0.3, 2.40), 4.2, 0.68,
        boxstyle="round,pad=0.06", facecolor=LIGHTPURPLE, edgecolor=PURPLE, linewidth=1.2)
    ax.add_patch(archive_box)
    ax.text(2.4, 2.86, 'Archive (ChromaDB)', ha='center', fontweight='bold', fontsize=10.2, color=PURPLE)
    ax.text(2.4, 2.60, 'Raw conversation chunks + fact vectors', ha='center', fontsize=10.2, color=DARKGRAY)

    # Retrieval box
    ret_box = mpatches.FancyBboxPatch((5.5, 2.40), 4.2, 0.68,
        boxstyle="round,pad=0.06", facecolor=LIGHTRED, edgecolor=RED, linewidth=1.2)
    ax.add_patch(ret_box)
    ax.text(7.6, 2.86, 'Multi-Strategy Retrieval', ha='center', fontweight='bold', fontsize=10.2, color=RED)
    ax.text(7.6, 2.60, 'Code + Facts + Archive  \u2192  Answer', ha='center', fontsize=10.2, color=DARKGRAY)

    # Arrows to retrieval
    ax.annotate('', xy=(5.5, 2.74), xytext=(4.5, 2.74),
        arrowprops=dict(arrowstyle='->', color=PURPLE, lw=1.2))
    ax.annotate('', xy=(9.45, 3.08), xytext=(9.05, 4.32),
        arrowprops=dict(arrowstyle='->', color=GREEN, lw=1.2,
                        connectionstyle='arc3,rad=-0.25'))

    # Bottom: separate analytical and standard-QA outputs.
    analytical_out = mpatches.FancyBboxPatch((0.8, 1.55), 3.7, 0.55,
        boxstyle="round,pad=0.06", facecolor='#F3F4F6', edgecolor=DARKGRAY, linewidth=1.2)
    ax.add_patch(analytical_out)
    ax.text(2.65, 1.91, 'Analytical result', ha='center', fontweight='bold', fontsize=10.2)
    ax.text(2.65, 1.69, 'Interpreter output', ha='center', fontsize=10.2, color=DARKGRAY)
    ax.annotate('', xy=(4.5, 1.92), xytext=(5.9, 3.82),
        arrowprops=dict(arrowstyle='->', color=ORANGE, lw=1.2,
                        connectionstyle='arc3,rad=0.25'))

    qa_out = mpatches.FancyBboxPatch((5.5, 1.55), 4.2, 0.55,
        boxstyle="round,pad=0.06", facecolor='#F3F4F6', edgecolor=DARKGRAY, linewidth=1.2)
    ax.add_patch(qa_out)
    ax.text(7.6, 1.91, 'Question-answering result', ha='center', fontweight='bold', fontsize=10.2)
    ax.text(7.6, 1.69, 'LLM over retrieved evidence', ha='center', fontsize=10.2, color=DARKGRAY)
    ax.annotate('', xy=(7.6, 2.1), xytext=(7.6, 2.40),
        arrowprops=dict(arrowstyle='->', color=DARKGRAY, lw=1.2))

    plt.savefig('figures/architecture.pdf')
    plt.savefig('figures/architecture.png')
    print('Saved architecture figure')
    plt.close()


# =====================================================================
# Figure 2: Full-LOCOMO benchmark comparison
# =====================================================================
def fig_benchmarks():
    from regenerate_with_new_results import generate_benchmark_figure

    generate_benchmark_figure()


# =====================================================================
# Legacy Active Service asset: explicitly mark the protocol as exploratory.
# =====================================================================
def fig_active_service():
    fig, ax = plt.subplots(figsize=(5, 2.4))
    ax.axis('off')
    ax.text(0.5, 0.68, 'Exploratory Active Service protocol',
            ha='center', va='center', fontsize=13, fontweight='bold',
            transform=ax.transAxes)
    ax.text(0.5, 0.38,
            'Not publication evidence: the stored runs prompt for alerts\n'
            'and do not execute generated persistent constraints.',
            ha='center', va='center', fontsize=10, color=DARKGRAY,
            transform=ax.transAxes)
    plt.savefig('figures/active_service.pdf')
    plt.savefig('figures/active_service.png')
    print('Saved exploratory-protocol notice')
    plt.close()


# =====================================================================
# Legacy development-version comparison (not a controlled component ablation).
# =====================================================================
def fig_ablation():
    fig, ax1 = plt.subplots(figsize=(4.6, 3))

    versions = ['v2', 'v3', 'v4', 'v5']
    locomo_j = [56.7, 75.7, 65.7, 78.0]

    x = range(len(versions))

    ax1.plot(x, locomo_j, 'o-', color=BLUE, linewidth=2, markersize=8, zorder=5)
    ax1.fill_between(x, locomo_j, alpha=0.1, color=BLUE)
    offsets = [(0, 12), (8, 10), (0, -18), (0, 12), (0, 12)]
    for i, (xi, yi) in enumerate(zip(x, locomo_j)):
        ax1.annotate(f'{yi:.1f}%', (xi, yi), textcoords="offset points",
                    xytext=offsets[i], ha='center', fontsize=8, fontweight='bold', color=BLUE)
    ax1.set_xticks(x)
    ax1.set_xticklabels(versions, fontsize=7)
    ax1.set_ylabel('LLM-Judge Accuracy (%)')
    ax1.set_title('Historical LOCOMO Development Runs', fontweight='bold')
    ax1.set_ylim(20, 95)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)

    ax1.text(0.5, -0.22, 'Versions differ in multiple implementation details; not controlled lesions.',
             ha='center', va='top', fontsize=7.5, color=DARKGRAY,
             transform=ax1.transAxes)

    plt.tight_layout()
    plt.savefig('figures/ablation.pdf')
    plt.savefig('figures/ablation.png')
    print('Saved ablation figure')
    plt.close()


if __name__ == '__main__':
    fig_architecture()
    fig_benchmarks()
    fig_active_service()
    fig_ablation()
    print('\nAll figures generated!')
