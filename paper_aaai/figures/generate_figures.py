"""Generate all paper figures."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import numpy as np

plt.rcParams.update({
    'font.family': 'serif',
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
    phase1 = mpatches.FancyBboxPatch((0.3, 3.45), 4.2, 2.1,
        boxstyle="round,pad=0.08", facecolor=LIGHTBLUE, edgecolor=BLUE, linewidth=1.5)
    ax.add_patch(phase1)
    ax.text(2.4, 5.35, 'Phase 1: Memorizing', ha='center', fontweight='bold', fontsize=10, color=BLUE)
    ax.text(2.4, 5.05, '(per session, append-only)', ha='center', fontsize=8, color=DARKGRAY)

    # Session boxes
    for i, label in enumerate(['Session 1', 'Session 2', 'Session 3', '...']):
        x = 0.6 + i * 1.0
        box = mpatches.FancyBboxPatch((x, 4.35), 0.85, 0.4,
            boxstyle="round,pad=0.05", facecolor='white', edgecolor=BLUE, linewidth=0.8)
        ax.add_patch(box)
        ax.text(x + 0.425, 4.55, label, ha='center', va='center', fontsize=7)

    # Arrow down to fact list
    ax.annotate('', xy=(2.2, 3.88), xytext=(2.2, 4.30),
        arrowprops=dict(arrowstyle='->', color=BLUE, lw=1.5))
    ax.text(2.32, 4.12, 'Extract facts\n(thinking LLM)', ha='left', va='center',
            fontsize=6.1, linespacing=1.1, color=BLUE)

    # Fact list
    fact_box = mpatches.FancyBboxPatch((0.7, 3.55), 3.4, 0.32,
        boxstyle="round,pad=0.05", facecolor='white', edgecolor=BLUE, linewidth=0.8)
    ax.add_patch(fact_box)
    ax.text(2.4, 3.71, 'Append-only Fact List (~1600 facts)', ha='center', fontsize=7.5, fontweight='bold')

    # Phase 2 box
    phase2 = mpatches.FancyBboxPatch((5.5, 3.45), 4.2, 2.1,
        boxstyle="round,pad=0.08", facecolor=LIGHTGREEN, edgecolor=GREEN, linewidth=1.5)
    ax.add_patch(phase2)
    ax.text(7.6, 5.35, 'Phase 2: Structuring', ha='center', fontweight='bold', fontsize=10, color='#15803D')
    ax.text(7.6, 5.05, '(periodic, from all facts)', ha='center', fontsize=8, color=DARKGRAY)

    # Code representation
    code_box = mpatches.FancyBboxPatch((5.9, 4.32), 3.4, 0.48,
        boxstyle="round,pad=0.04", facecolor='white', edgecolor=GREEN, linewidth=0.8)
    ax.add_patch(code_box)
    ax.text(7.6, 4.56, 'Typed state modules (Code)', ha='center', va='center', fontsize=8, fontweight='bold')

    # Arrow from facts to code
    ax.annotate('', xy=(5.5, 4.55), xytext=(4.5, 3.72),
        arrowprops=dict(arrowstyle='->', color='#15803D', lw=1.5, connectionstyle='arc3,rad=-0.2'))
    ax.text(4.98, 4.07, 'Structure\n(thinking LLM)', ha='center', va='center',
            fontsize=6.1, linespacing=1.1, color='#15803D', rotation=39)

    # Constraint box (label wrapped to two lines so it stays inside the box)
    const_box = mpatches.FancyBboxPatch((5.9, 3.58), 3.4, 0.48,
        boxstyle="round,pad=0.05", facecolor=LIGHTORANGE, edgecolor=ORANGE, linewidth=0.8)
    ax.add_patch(const_box)
    ax.text(7.6, 3.82, 'Constraint execution  ->  ACTIVE_ALERTS',
            ha='center', va='center', fontsize=7.5, fontweight='bold', color='#92400E')

    # Tier 3 Archive
    archive_box = mpatches.FancyBboxPatch((0.3, 2.40), 4.2, 0.68,
        boxstyle="round,pad=0.06", facecolor=LIGHTPURPLE, edgecolor=PURPLE, linewidth=1.2)
    ax.add_patch(archive_box)
    ax.text(2.4, 2.86, 'Archive (ChromaDB)', ha='center', fontweight='bold', fontsize=9, color=PURPLE)
    ax.text(2.4, 2.60, 'Raw conversation chunks + fact vectors', ha='center', fontsize=7.5, color=DARKGRAY)

    # Retrieval box
    ret_box = mpatches.FancyBboxPatch((5.5, 2.40), 4.2, 0.68,
        boxstyle="round,pad=0.06", facecolor=LIGHTRED, edgecolor=RED, linewidth=1.2)
    ax.add_patch(ret_box)
    ax.text(7.6, 2.86, 'Multi-Strategy Retrieval', ha='center', fontweight='bold', fontsize=9, color=RED)
    ax.text(7.6, 2.60, 'Code + Facts + Archive  \u2192  Answer', ha='center', fontsize=7.5, color=DARKGRAY)

    # Arrows to retrieval
    ax.annotate('', xy=(5.5, 2.74), xytext=(4.5, 2.74),
        arrowprops=dict(arrowstyle='->', color=PURPLE, lw=1.2))
    ax.annotate('', xy=(7.6, 3.10), xytext=(7.6, 3.45),
        arrowprops=dict(arrowstyle='->', color=GREEN, lw=1.2))

    # Bottom: output
    out_box = mpatches.FancyBboxPatch((2.5, 1.55), 5, 0.55,
        boxstyle="round,pad=0.06", facecolor='#F3F4F6', edgecolor=DARKGRAY, linewidth=1.2)
    ax.add_patch(out_box)
    ax.text(5, 1.91, 'Manifest: Domains + ACTIVE_ALERTS', ha='center', fontweight='bold', fontsize=9)
    ax.text(5, 1.69, 'Always in agent context (~300 tokens)', ha='center', fontsize=7.5, color=DARKGRAY)
    ax.annotate('', xy=(5, 2.1), xytext=(6, 2.40),
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
# Figure 3: Active Service — standard vs hard
# =====================================================================
def fig_active_service():
    fig, ax = plt.subplots(figsize=(5, 3.2))

    systems = ['UaC\n+ pipeline', 'Mem0', 'Full Context', 'UaC\n(no alerts)']
    standard = [100, 92.5, 0, 52.5]
    hard = [85, 65, 55, 45]
    has_standard = [True, True, False, True]

    x = np.arange(len(systems))
    width = 0.32

    bars1 = ax.bar(x - width/2, standard, width,
                   label='Standard (40 scenarios)', color=BLUE, edgecolor='white', alpha=0.85)
    bars2 = ax.bar(x + width/2, hard, width,
                   label='Hard (20 scenarios)', color=ORANGE, edgecolor='white', alpha=0.85)

    # Hide missing standard bar for Full Context
    bars1[2].set_alpha(0)

    ax.set_ylabel('Alert Detection Rate (%)')
    ax.set_title('Active Service: Standard vs Hard Scenarios', fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(systems, fontsize=8)
    ax.set_ylim(0, 118)
    ax.legend(loc='upper right', framealpha=0.9, fontsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    for bar, val, has in zip(bars1, standard, has_standard):
        if has and val:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                    f'{val:.0f}%', ha='center', va='bottom', fontsize=7.5, fontweight='bold', color=BLUE)
    for bar, val in zip(bars2, hard):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                f'{val:.0f}%', ha='center', va='bottom', fontsize=7.5, fontweight='bold', color='#92400E')

    # Annotate Mem0 drop
    ax.annotate('-27.5pp', xy=(1, 78), fontsize=7.5, color=RED, fontweight='bold',
                ha='center', va='center',
                bbox=dict(boxstyle='round,pad=0.2', facecolor=LIGHTRED, edgecolor=RED, alpha=0.8))

    plt.tight_layout()
    plt.savefig('figures/active_service.pdf')
    plt.savefig('figures/active_service.png')
    print('Saved active service figure')
    plt.close()


# =====================================================================
# Figure 4: Ablation progression
# =====================================================================
def fig_ablation():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7, 3))

    versions = ['Basic\n3-tier', 'Flat\nfacts', 'Incremental\ncode', 'Two-\nphase', '+\npipeline']
    locomo_j = [56.7, 75.7, 65.7, 78.0, 78.0]
    active_s = [30.0, 37.5, 40.0, 67.5, 100.0]

    x = range(len(versions))

    # LOCOMO ablation
    ax1.plot(x, locomo_j, 'o-', color=BLUE, linewidth=2, markersize=8, zorder=5)
    ax1.fill_between(x, locomo_j, alpha=0.1, color=BLUE)
    offsets = [(0, 12), (8, 10), (0, -18), (0, 12), (0, 12)]
    for i, (xi, yi) in enumerate(zip(x, locomo_j)):
        ax1.annotate(f'{yi:.1f}%', (xi, yi), textcoords="offset points",
                    xytext=offsets[i], ha='center', fontsize=8, fontweight='bold', color=BLUE)
    ax1.set_xticks(x)
    ax1.set_xticklabels(versions, fontsize=7)
    ax1.set_ylabel('LLM-Judge Accuracy (%)')
    ax1.set_title('LOCOMO Recall', fontweight='bold')
    ax1.set_ylim(20, 95)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)

    # Annotate key transitions
    ax1.annotate('+19pp', xy=(0.5, 70), fontsize=7, color=GREEN, fontweight='bold', ha='center')
    ax1.annotate('-10pp', xy=(1.5, 73), fontsize=7, color=RED, fontweight='bold', ha='center')

    # Active Service ablation
    ax2.plot(x, active_s, 's-', color=ORANGE, linewidth=2, markersize=8, zorder=5)
    ax2.fill_between(x, active_s, alpha=0.1, color=ORANGE)
    offsets2 = [(0, 10), (0, 10), (0, 10), (0, 10), (0, 10)]
    for i, (xi, yi) in enumerate(zip(x, active_s)):
        ax2.annotate(f'{yi:.1f}%', (xi, yi), textcoords="offset points",
                    xytext=offsets2[i], ha='center', fontsize=8, fontweight='bold', color='#92400E')
    ax2.set_xticks(x)
    ax2.set_xticklabels(versions, fontsize=7)
    ax2.set_title('Active Service', fontweight='bold')
    ax2.set_ylim(10, 118)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)

    ax2.annotate('+32.5pp', xy=(3.5, 83), fontsize=7, color=GREEN, fontweight='bold', ha='center')

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
