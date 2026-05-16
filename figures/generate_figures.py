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
    fig, ax = plt.subplots(1, 1, figsize=(7, 4.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7)
    ax.axis('off')

    # Title
    ax.text(5, 6.7, 'User as Code: Two-Phase Architecture',
            ha='center', va='center', fontsize=13, fontweight='bold')

    # Phase 1 box
    phase1 = mpatches.FancyBboxPatch((0.3, 3.8), 4.2, 2.5,
        boxstyle="round,pad=0.15", facecolor=LIGHTBLUE, edgecolor=BLUE, linewidth=1.5)
    ax.add_patch(phase1)
    ax.text(2.4, 6.05, 'Phase 1: Memorizing', ha='center', fontweight='bold', fontsize=10, color=BLUE)
    ax.text(2.4, 5.6, '(per session, append-only)', ha='center', fontsize=8, color=DARKGRAY)

    # Session boxes
    for i, label in enumerate(['Session 1', 'Session 2', 'Session 3', '...']):
        x = 0.6 + i * 1.0
        box = mpatches.FancyBboxPatch((x, 4.8), 0.85, 0.5,
            boxstyle="round,pad=0.05", facecolor='white', edgecolor=BLUE, linewidth=0.8)
        ax.add_patch(box)
        ax.text(x + 0.425, 5.05, label, ha='center', va='center', fontsize=7)

    # Arrow down to fact list
    ax.annotate('', xy=(2.2, 4.2), xytext=(2.2, 4.7),
        arrowprops=dict(arrowstyle='->', color=BLUE, lw=1.5))
    ax.text(1.0, 4.45, 'Extract facts\n(thinking LLM)', ha='center', fontsize=7, color=BLUE)

    # Fact list
    fact_box = mpatches.FancyBboxPatch((0.7, 3.9), 3.4, 0.35,
        boxstyle="round,pad=0.05", facecolor='white', edgecolor=BLUE, linewidth=0.8)
    ax.add_patch(fact_box)
    ax.text(2.4, 4.08, 'Append-only Fact List (~1600 facts)', ha='center', fontsize=7.5, fontweight='bold')

    # Phase 2 box
    phase2 = mpatches.FancyBboxPatch((5.5, 3.8), 4.2, 2.5,
        boxstyle="round,pad=0.15", facecolor=LIGHTGREEN, edgecolor=GREEN, linewidth=1.5)
    ax.add_patch(phase2)
    ax.text(7.6, 6.05, 'Phase 2: Structuring', ha='center', fontweight='bold', fontsize=10, color='#15803D')
    ax.text(7.6, 5.6, '(periodic, from all facts)', ha='center', fontsize=8, color=DARKGRAY)

    # Code representation
    code_box = mpatches.FancyBboxPatch((5.9, 4.6), 3.4, 1.0,
        boxstyle="round,pad=0.08", facecolor='white', edgecolor=GREEN, linewidth=0.8)
    ax.add_patch(code_box)
    ax.text(7.6, 5.35, 'Typed Python Code', ha='center', fontsize=8, fontweight='bold')
    ax.text(7.6, 5.05, 'passport = PassportInfo(\n  expiry=date(2025,2,18))',
            ha='center', fontsize=6.5, family='monospace', color=DARKGRAY)
    ax.text(7.6, 4.72, 'notes=["Prefers aisle..."]',
            ha='center', fontsize=6.5, family='monospace', color=DARKGRAY)

    # Arrow from facts to code
    ax.annotate('', xy=(5.5, 5.1), xytext=(4.5, 4.1),
        arrowprops=dict(arrowstyle='->', color='#15803D', lw=1.5, connectionstyle='arc3,rad=-0.2'))
    ax.text(5.1, 4.55, 'Structure\n(thinking LLM)', ha='center', fontsize=7, color='#15803D')

    # Constraint box
    const_box = mpatches.FancyBboxPatch((5.9, 3.9), 3.4, 0.5,
        boxstyle="round,pad=0.05", facecolor=LIGHTORANGE, edgecolor=ORANGE, linewidth=0.8)
    ax.add_patch(const_box)
    ax.text(7.6, 4.15, 'Constraint Execution  \u2192  ACTIVE_ALERTS',
            ha='center', fontsize=7.5, fontweight='bold', color='#92400E')

    # Tier 3 Archive
    archive_box = mpatches.FancyBboxPatch((0.3, 2.5), 4.2, 0.9,
        boxstyle="round,pad=0.1", facecolor=LIGHTPURPLE, edgecolor=PURPLE, linewidth=1.2)
    ax.add_patch(archive_box)
    ax.text(2.4, 3.1, 'Tier 3: Archive (ChromaDB)', ha='center', fontweight='bold', fontsize=9, color=PURPLE)
    ax.text(2.4, 2.75, 'Raw conversation chunks + fact vectors', ha='center', fontsize=7.5, color=DARKGRAY)

    # Retrieval box
    ret_box = mpatches.FancyBboxPatch((5.5, 2.5), 4.2, 0.9,
        boxstyle="round,pad=0.1", facecolor=LIGHTRED, edgecolor=RED, linewidth=1.2)
    ax.add_patch(ret_box)
    ax.text(7.6, 3.1, 'Multi-Strategy Retrieval', ha='center', fontweight='bold', fontsize=9, color=RED)
    ax.text(7.6, 2.75, 'Code + Facts + Archive  \u2192  Answer', ha='center', fontsize=7.5, color=DARKGRAY)

    # Arrows to retrieval
    ax.annotate('', xy=(5.5, 2.95), xytext=(4.5, 2.95),
        arrowprops=dict(arrowstyle='->', color=PURPLE, lw=1.2))
    ax.annotate('', xy=(7.6, 3.5), xytext=(7.6, 3.8),
        arrowprops=dict(arrowstyle='->', color=GREEN, lw=1.2))

    # Bottom: output
    out_box = mpatches.FancyBboxPatch((2.5, 1.5), 5, 0.7,
        boxstyle="round,pad=0.1", facecolor='#F3F4F6', edgecolor=DARKGRAY, linewidth=1.2)
    ax.add_patch(out_box)
    ax.text(5, 1.95, 'Manifest: Domains + ACTIVE_ALERTS', ha='center', fontweight='bold', fontsize=9)
    ax.text(5, 1.65, 'Always in agent context (~300 tokens)', ha='center', fontsize=7.5, color=DARKGRAY)
    ax.annotate('', xy=(5, 2.2), xytext=(6, 2.5),
        arrowprops=dict(arrowstyle='->', color=DARKGRAY, lw=1.2))

    plt.savefig('figures/architecture.pdf')
    plt.savefig('figures/architecture.png')
    print('Saved architecture figure')
    plt.close()


# =====================================================================
# Figure 2: Benchmark comparison (grouped bar chart)
# =====================================================================
def fig_benchmarks():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 3.2))

    # LOCOMO (5 conversations, 300 QAs total)
    systems = ['UaC v5\n(ours)', 'Full\nContext', 'MemMachine', 'Hindsight\n(lite)', 'EverMemOS\n(lite)', 'A-MEM', 'Mem0']
    locomo = [78.0, 82.3, 75.3, 70.0, 55.0, 56.7, 32.7]
    colors_l = [BLUE, GRAY, GREEN, ORANGE, LIGHTBLUE, ORANGE, RED]

    bars = ax1.bar(range(len(systems)), locomo, color=colors_l, edgecolor='white', linewidth=0.5, width=0.7)
    ax1.set_xticks(range(len(systems)))
    ax1.set_xticklabels(systems, fontsize=7)
    ax1.set_ylabel('LLM-Judge Accuracy (%)')
    ax1.set_title('LOCOMO (5 conv, 300 QAs)', fontweight='bold')
    ax1.set_ylim(0, 100)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    for bar, val in zip(bars, locomo):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5,
                f'{val:.1f}', ha='center', va='bottom', fontsize=7, fontweight='bold')
    bars[0].set_edgecolor(BLUE)
    bars[0].set_linewidth(2)

    # LongMemEval (200-question stratified sample)
    systems2 = ['UaC v5\n(ours)', 'Full\nContext', 'MemMachine', 'EverMemOS\n(lite)', 'Hindsight\n(lite)', 'A-MEM', 'Mem0']
    lme = [84.5, 86.5, 84.0, 79.5, 70.5, 58.0, 24.5]
    colors_r = [BLUE, GRAY, GREEN, LIGHTBLUE, ORANGE, ORANGE, RED]

    bars2 = ax2.bar(range(len(systems2)), lme, color=colors_r, edgecolor='white', linewidth=0.5, width=0.7)
    ax2.set_xticks(range(len(systems2)))
    ax2.set_xticklabels(systems2, fontsize=7)
    ax2.set_title('LongMemEval (200 stratified Qs)', fontweight='bold')
    ax2.set_ylim(0, 100)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    for bar, val in zip(bars2, lme):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5,
                f'{val:.1f}', ha='center', va='bottom', fontsize=7, fontweight='bold')
    bars2[0].set_edgecolor(BLUE)
    bars2[0].set_linewidth(2)

    plt.tight_layout()
    plt.savefig('figures/benchmarks.pdf')
    plt.savefig('figures/benchmarks.png')
    print('Saved benchmarks figure')
    plt.close()


# =====================================================================
# Figure 3: Active Service — standard vs hard
# =====================================================================
def fig_active_service():
    fig, ax = plt.subplots(figsize=(5, 3.2))

    systems = ['UaC v5\n+ pipeline', 'Mem0', 'Full Context', 'UaC v5\n(no alerts)']
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

    versions = ['v2\nBasic', 'v3\nFlat\nFacts', 'v4\nCode+\nNotes', 'v5\nTwo-\nPhase', 'v5+\nPipeline']
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
