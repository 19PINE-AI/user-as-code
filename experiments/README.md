# Experiments — reproduction guide

This directory holds the full experiment harness for *User as Code*. Runs write
their inspectable per-question outputs under `results/`; the scripts and strict
validator below regenerate and certify the paper-facing aggregates.

## Setup

From the repository root:

1. Fetch the benchmark datasets (see `benchmarks/README.md`):
   ```bash
   ./benchmarks/fetch_benchmarks.sh
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
   routes. The reported run used exactly
   `GeminiCLI/0.28.0/gemini-3-flash-preview (darwin; arm64; terminal)` against
   `https://api.krill-ai.net/v1`. Krill's OpenAI-compatible interface does not
   expose Gemini's `thinking_budget`, so the full Luna and Gemini suites do not
   transmit an explicit thinking budget; numerical budgets in older scripts
   apply only to their direct-Gemini experiments.
   Some legacy experiment scripts still import `google-genai` directly and
   require `GEMINI_API_KEY`. Cross-family checks require their provider keys.
3. The ChromaDB index under `experiments/chroma_db/` is a regenerable cache
   (git-ignored); the runners rebuild it on first use.

## Core implementation

- `user_as_code_v5.py` — the evaluated UaC pipeline (Phase-1 extraction,
  bounded Phase-2 structuring, and three-channel retrieval). Its
  `structure()` method passes at most the first 30,000 serialized fact
  characters to Phase 2; the fact and archive indices remain separate.
- Baselines reimplemented on the shared backbone: `run_locomo_memmachine.py`
  (MemMachine), `hindsight_lite.py` (Hindsight), `evermemos_lite.py` (EverMemOS).
  Mem0 (`mem0ai` 1.0.5) and A-MEM (`agentic-memory` 0.0.1) use their published
  libraries, configured with the selected Krill backbone for LLM-mediated
  memory construction. The same-backbone reimplementations use the shared
  ChromaDB / `all-MiniLM-L6-v2` infrastructure rather than every system's
  published native retrieval stack, so these are controlled implementations,
  not claims to reproduce each published system's best reported number.

## Script → paper result map

| Paper artifact | Script | Output in `results/` |
|----------------|--------|----------------------|
| Legacy LOCOMO 600 (first 60 QAs per conversation; superseded as the headline result) | `run_locomo_10conv.py` | `locomo10_*.json` |
| Full LOCOMO 1,986, Table 1 (Luna + Gemini) | `run_locomo_full.py`, `summarize_locomo_full.py` | `full_locomo_gpt56_luna/*.json`, `full_locomo_gemini3_flash_preview/*.json` |
| LongMemEval 500 (Table 2) | `run_lme_500.py`, `full_longmemeval_comparison.py` | `lme500_*.json` |
| Analytical inference (Table 3) | `run_analytical_bench.py`; one-case repair via `merge_analytical_case.py` | `analytical_*.json` |
| Withdrawn analytical cost pilot (canonical UaC artifacts lack separate structuring usage) | `analytical_cost_summary.py` | `analytical_cost_*` |
| Exploratory proactive-alert pilot (not paper evidence) | legacy `run_active_service_*.py` scripts | `active_service_*.json`, `hard_active_service_results.json` |
| Historical development-version comparison (not controlled component lesions) | `ablation_experiment.py` | `ablation_v3_v4.json` |
| Retrieval-channel ablation | `run_channel_ablation.py` | `locomo5_uac_v5_ablate_*.json` |
| Modularity / progressive disclosure | `run_modularity.py` | `modularity_*` |
| Deprecated Phase-2 token-overlap pilot (not an information-preservation measure) | `run_phase2_failure_analysis.py` | `phase2_failure_analysis.json` |
| Separate 500K-cap Phase-2 stress test (not the evaluated 30K-cap UaC path) | `run_phase2_scalability.py` | `phase2_scalability.json` |
| Cross-family judge re-judging | `run_full_rejudge.py`, `run_judge_crosscheck.py` | `full_rejudge.json`, `judge_crosscheck.json` |
| Legacy cross-LLM portability (GPT-5.4; superseded by the two full suites) | `run_locomo_gpt54.py` | `locomo_gpt54_*` |
| `conv-30` case study (Appendix) | `run_conv30_extraction.py`, `gen_case_memory.py` | `conv30_extraction/` |

Legacy tables and aggregate figures are assembled by `build_paper_tables.py` /
`aggregate_results.py`. The full LOCOMO table must use the strictly validated
output of `summarize_locomo_full.py`.

The analytical item `sleep_sleep_trend_q1_q2_n500` originally omitted the
year even though its deterministic gold calculation used 2024. The canonical
case now asks explicitly about Q1 to Q2 of 2024. It was rerun for all five
systems through Krill/Gemini and merged from isolated artifacts with:

```bash
case_id=sleep_sleep_trend_q1_q2_n500
for system in fc_repl uac_v5 full_context memmachine mem0; do
  ANALYTICAL_MODEL=gemini-3-flash-preview \
    python experiments/run_analytical_bench.py "$system" \
      --case-id "$case_id" \
      --output "experiments/results/analytical_rerun_2024_${system}.json" \
      --force
  python experiments/merge_analytical_case.py \
      --target "experiments/results/analytical_${system}.json" \
      --rerun "experiments/results/analytical_rerun_2024_${system}.json" \
      --case-id "$case_id" --dry-run
done
```

Inspect each isolated row and remove `--dry-run` only when its question is
year-qualified and its `error` field is empty. Each canonical artifact stores
the repair reason and model/endpoint/User-Agent provenance under
`case_repairs`. The corrected aggregate is 100/100 for UaC and FC+REPL; the
other totals remain Full Context 94/100, MemMachine 43/100, and Mem0 6/100.

For the full LOCOMO evaluation, run each of the seven systems in a separate
process under each model. The explicit run names keep the suites isolated:

```bash
systems=(full_context uac_v5 memmachine hindsight evermemos a_mem mem0)

for system in "${systems[@]}"; do
  KRILL_MODEL=gpt-5.6-luna \
    .venv-locomo/bin/python experiments/run_locomo_full.py "$system" \
      --run-name full_locomo_gpt56_luna
done

for system in "${systems[@]}"; do
  KRILL_MODEL=gemini-3-flash-preview \
    .venv-locomo/bin/python experiments/run_locomo_full.py "$system" \
      --run-name full_locomo_gemini3_flash_preview
done
```

The loops show the complete command set; independent systems may be launched
concurrently when provider and local-resource limits permit. Each system covers
all 1,986 annotations across all 10 conversations. Categories 1--4 contain
1,540 answer-bearing questions and report LOCOMO's category-aware token F1 plus
a binary same-backbone LLM-judge accuracy. Category 5 contains 446 adversarial
questions and reports deterministic refusal accuracy; those questions are never
sent to the LLM judge.

After all artifacts finish, validate their exact coverage, provenance, stored
scores, judge fields, and aggregates and print the paper-facing metrics with:

```bash
.venv-locomo/bin/python experiments/summarize_locomo_full.py
```

The validator fails on missing or error records. A complete paper-facing run
must print all 14 model/system rows followed by `FINAL VALIDATION PASSED`. Its
`--allow-partial` option is only for monitoring an active run and must not be
used to certify or report results.

For publication packaging, the canonical set is exactly the seven basenames
`full_context.json`, `uac_v5.json`, `memmachine.json`, `hindsight.json`,
`evermemos.json`, `a_mem.json`, and `mem0.json` in each of the two run
directories. Timestamped `.bak`, `.invalid`, and other repair artifacts are
audit history, not members of the 14-file result set, and must be excluded from
the submission bundle.

Krill/Luna currently safety-blocks one benign Mem0 extraction prompt in
LOCOMO `conv-44` (`session_15`, turn `D15:3`, about four dogs and veterinary
checkups). `Mem0Wrapper` handles only this explicit refusal by first splitting
the unchanged session into contiguous turn groups and, for the one exact
single-turn false positive, using the documented semantic paraphrase in source.
The model, facts, and Mem0 extraction path remain unchanged; every activation
is logged. Unknown safety refusals still fail the conversation build.

Krill/Luna also refused the LLM-judge prompt for a benign LOCOMO book comparison
(`conv-43`, QA index 66) in four artifacts: UaC, MemMachine,
EverMemOS, and A-MEM. The harness re-frames only an explicit provider refusal
as a semantic-equivalence check and, if needed, deterministically substitutes
domain-neutral book terms in the retry prompt. The stored question, gold
answer, prediction, and `scored_prediction` remain unchanged, as does official
token-F1 scoring. All four resulting decisions are `WRONG` and are tagged
`[provider-safety fallback]` in their `judge_reason` fields; other failures keep
the normal error path.

Transient failures should be repaired in an isolated run directory. After the
corresponding main writer exits, merge a complete repaired conversation with:

```bash
.venv-locomo/bin/python experiments/merge_locomo_repair.py \
  --target-run full_locomo_gpt56_luna \
  --repair-run repair_luna_a_mem_conv43 \
  --system a_mem --conversation conv-43 --dry-run
# Remove --dry-run only after the check passes.
```

UaC, Hindsight, EverMemOS, A-MEM, and Mem0 use stochastic memory construction,
so the merge tool requires whole-conversation replacements for them. Targeted
QA replacement is accepted only for deterministic MemMachine, using one or
more `--qa-index` arguments. The tool verifies provenance, coverage, scores,
and judge fields, refuses to run against an active target writer, makes a
timestamped backup, and rewrites the aggregate atomically. Run the strict
validator again after every merge.

## Regenerable derived data (git-ignored)

These are large and rebuilt from the fetched benchmarks, so they are not tracked:

- `results/memory_lme.json` — per-question LongMemEval memory stores.
- `results/lme_500_full.json` — assembled 500-question set (`build_lme_full_500.py`).
- `results/lme_200_sample.json` — stratified 200-question sample (`sample_lme_200.py`).
- `chroma_db/` — vector index cache.
