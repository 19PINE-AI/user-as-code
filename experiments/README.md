# Experiments — reproduction guide

This directory holds the full experiment harness for *User as Code*. The
per-run outputs we report are committed under `results/` so the paper's numbers
can be inspected without re-running anything; the scripts below regenerate them.

## Setup

1. Fetch the benchmark datasets (see `../benchmarks/README.md`):
   ```bash
   ../benchmarks/fetch_benchmarks.sh
   ```
   For the full seven-system LOCOMO run, create an isolated environment with
   the pinned Mem0 and A-MEM versions:
   ```bash
   python -m venv .venv-locomo
   .venv-locomo/bin/pip install -r experiments/requirements-locomo-full.txt
   ```
2. Set the API key used by the current LOCOMO pipeline and judge. The model and
   endpoint defaults are shown explicitly; override them only for a separate,
   clearly named run:
   ```bash
   export KRILL_API_KEY=...       # required; normally exported by ~/.zshrc
   export KRILL_BASE_URL=https://api.krill-ai.net/v1
   export KRILL_MODEL=gpt-5.6-luna
   ```
   For the parallel Gemini run, set
   `KRILL_MODEL=gemini-3-flash-preview`. The shared client automatically sends
   the official model-aware Gemini CLI User-Agent required by Krill's Gemini
   routes; `GEMINI_CLI_VERSION` defaults to the verified local CLI version
   `0.28.0`.
   Some legacy experiment scripts still import `google-genai` directly and
   require `GEMINI_API_KEY`. Cross-family checks require their provider keys.
3. The ChromaDB index under `chroma_db/` is a regenerable cache (git-ignored);
   the runners rebuild it on first use.

## Core implementation

- `user_as_code_v5.py` — the UaC pipeline (Phase-1 extraction, Phase-2
  structuring, multi-strategy retrieval, constraint loop).
- Baselines reimplemented on the shared backbone: `run_locomo_memmachine.py`
  (MemMachine), `hindsight_lite.py` (Hindsight), `evermemos_lite.py` (EverMemOS);
  Mem0 and A-MEM are run via their published libraries.

## Script → paper result map

| Paper artifact | Script | Output in `results/` |
|----------------|--------|----------------------|
| LOCOMO 600 (Table 1) | `run_locomo_10conv.py` | `locomo10_*.json` |
| Full LOCOMO 1,986 (fresh Luna run) | `run_locomo_full.py` | `full_locomo_gpt56_luna/*.json` |
| LongMemEval 500 (Table 2) | `run_lme_500.py`, `full_longmemeval_comparison.py` | `lme500_*.json` |
| Analytical inference (Table 3) | `run_analytical_bench.py` | `analytical_*.json` |
| Analytical cost / amortization | `analytical_cost_summary.py` | `analytical_cost_*` |
| Active Service (standard + hard) | `run_active_service_mem0lib.py`, `run_active_service_amem_hard.py` | `active_service_*.json`, `hard_active_service_results.json` |
| Ablation study | `ablation_experiment.py` | `ablation_v3_v4.json` |
| Retrieval-channel ablation | `run_channel_ablation.py` | `locomo5_uac_v5_ablate_*.json` |
| Modularity / progressive disclosure | `run_modularity.py` | `modularity_*` |
| Phase-2 failure-mode audit | `run_phase2_failure_analysis.py` | `phase2_failure_analysis.json` |
| Phase-2 scalability | `run_phase2_scalability.py` | `phase2_scalability.json` |
| Cross-family judge re-judging | `run_full_rejudge.py`, `run_judge_crosscheck.py` | `full_rejudge.json`, `judge_crosscheck.json` |
| Cross-LLM portability (GPT-5.4) | `run_locomo_gpt54.py` | `locomo_gpt54_*` |
| `conv-30` case study (Appendix) | `run_conv30_extraction.py`, `gen_case_memory.py` | `conv30_extraction/` |

Tables and aggregate figures are assembled by `build_paper_tables.py` /
`aggregate_results.py`.

## Regenerable derived data (git-ignored)

These are large and rebuilt from the fetched benchmarks, so they are not tracked:

- `results/memory_lme.json` — per-question LongMemEval memory stores.
- `results/lme_500_full.json` — assembled 500-question set (`build_lme_full_500.py`).
- `results/lme_200_sample.json` — stratified 200-question sample (`sample_lme_200.py`).
- `chroma_db/` — vector index cache.
