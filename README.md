# User as Code: Executable Memory for Personalized Agents

Research artifact for the paper **_User as Code: Executable Memory for Personalized Agents_** (Bojie Li, Pine AI).

- 📄 **Paper:** [arXiv:2606.16707](https://arxiv.org/abs/2606.16707) (LaTeX sources in this repo; build with `make`)
- 🌐 **Interactive companion site:** <https://01.me/research/user-as-code> — explore every graded test case across all four benchmarks
- ⚖️ **License:** [Apache-2.0](LICENSE)

---

## The idea in one paragraph

Personalized agents need a **user memory**: a model of the user that accumulates across
conversations. Today that memory is stored as unstructured text, knowledge graphs, or flat
fact stores and consulted by **retrieval** (similarity search). Because storing a fact and
acting on it are separate steps, such "bag-of-facts" memory recalls well but struggles to
resolve contradictions, aggregate over many records, or enforce logical rules. **User as
Code (UaC)** instead makes memory *executable*: a user's state is a directory of typed
Python objects, and the rules over that state are ordinary Python functions, so representing
the user and reasoning about the user happen in one medium an interpreter can run. The
enabling mechanism is a **two-phase pipeline** — an append-only fact log, periodically
checkpointed into structured typed code.

## What's in this repository

| Path | What it is |
|------|------------|
| [`paper.tex`](paper.tex), `body*.tex`, [`reference.bib`](reference.bib), [`Makefile`](Makefile) | LaTeX sources for the paper (compiles with `arxiv.sty` + `plainnat`) |
| [`figures/`](figures/) | Paper figures (PDF) and the scripts that generate them |
| [`prototype/`](prototype/) | **Reference UaC implementation** — a worked example user (`jessica_thompson`) as typed domains + executable constraints + tests |
| [`experiments/`](experiments/) | Full experiment harness, the UaC pipeline (`user_as_code_v5.py`), baseline reimplementations, generated `results/`, and strict validators. See [`experiments/README.md`](experiments/README.md) |
| [`evaluation/`](evaluation/) | The **Active Service benchmark** scenario definitions (60 scenarios, 5 categories). See [`evaluation/README.md`](evaluation/README.md) |
| [`benchmarks/`](benchmarks/) | Fetch script + instructions for the third-party datasets (LOCOMO, LongMemEval). Raw data is **not** redistributed. See [`benchmarks/README.md`](benchmarks/README.md) |
| [`web/`](web/) | React companion site that visualizes every graded test case. See [`web/README.md`](web/README.md) |
| [`scripts/`](scripts/) | `build_site_data.py` — turns `experiments/results/` into the site's data bundles |
| [`user-as-code/`](user-as-code/) | Slidev slide deck (talk version of the paper) |

## Quick start

### Building the paper

```bash
make            # -> paper.pdf  (pdflatex + bibtex; needs a TeX Live install)
```

### Running the reference prototype

The fastest way to see "user as code" concretely — no API keys or datasets needed:

```bash
cd prototype
python runner.py                         # run every constraint, print the alerts
python -m pytest jessica_thompson/tests/ # validate constraint behavior
```

Each user is a self-contained Python project: `manifest.py` (compact always-loaded index),
`domains/` (typed dataclass schemas + state), `constraints/` (executable invariants that
return alerts), and `tests/`.

### Reproducing the experiments

```bash
# 1. install the pinned full-LOCOMO environment
python -m venv .venv-locomo
.venv-locomo/bin/pip install -r experiments/requirements-locomo-full.txt

# 2. fetch the benchmark datasets (LOCOMO downloads directly; LongMemEval is author-distributed)
./benchmarks/fetch_benchmarks.sh

# 3. configure the Krill endpoint and API key (do not commit the key)
export KRILL_API_KEY=...
export KRILL_BASE_URL=https://api.krill-ai.net/v1

# 4. run all seven systems under both full-LOCOMO backbones
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

# 5. certify all 14 artifacts; partial output is not paper-ready
.venv-locomo/bin/python experiments/summarize_locomo_full.py
```

The two full suites use `gpt-5.6-luna` and `gemini-3-flash-preview` through
`https://api.krill-ai.net/v1`. The reported Gemini run sends the exact User-Agent
`GeminiCLI/0.28.0/gemini-3-flash-preview (darwin; arm64; terminal)`. Runs write
inspectable per-question outputs under [`experiments/results/`](experiments/results/),
and the strict summarizer must print 14 rows plus `FINAL VALIDATION PASSED`
before any aggregate is reported. See the
[`experiments/README.md`](experiments/README.md) for scoring denominators,
provider-fallback disclosures, parallel execution, repair procedures, and the
full script-to-result map. Some older experiments use direct Gemini or
cross-family provider keys; they are documented separately there and are not
the full-LOCOMO reproduction path.

### Running the companion website

```bash
cd web
npm install
npm run dev      # http://localhost:5173
# data bundles are regenerated with:  python3 ../scripts/build_site_data.py
```

## Headline results

| Capability | Evaluation | UaC | Interpretation |
|------------|------------|-----|----------------|
| **Factual recall and refusal** | Full LOCOMO, all 1,986 questions; validated GPT-5.6 Luna / Gemini 3 Flash Preview suites | 39.4% / 46.9% token F1 and 78.8% / 80.6% judge accuracy on 1,540 answer-bearing questions; 64.3% / 95.7% refusal accuracy on 446 adversarial questions | lexical overlap, semantic correctness, and refusal behavior are reported separately within each backbone panel |
| **Analytical inference** | 100 aggregate queries | 99% exact match | answer is a one-line computation over typed state, not a search over text |
| **Active Service** | 40 standard + 20 hard scenarios | 100% standard / 85% hard observed detection | constraints execute on state change; rates and Wilson intervals are descriptive |

All fourteen full-LOCOMO artifacts pass the strict two-suite validator. See the
paper and experiment guide for the complete two-backbone table,
reimplementation caveats, provider-fallback disclosures, ablations, and cost
analysis.

## Reproducibility notes

- **Version-controlled source:** experiment and validation scripts, the synthetic analytical
  benchmark, the Active Service scenarios, and the reference prototype.
- **Generated results:** per-run JSON artifacts are written under `experiments/results/`.
  A paper-facing full LOCOMO artifact is valid only after strict validation of
  coverage, provenance, stored scores, judge fields, and aggregates.
- **Not committed (regenerable / third-party):** the vector-index cache
  (`experiments/chroma_db/`), the raw benchmark datasets (`benchmarks/*/data/`, fetched via
  the script), and a few large LongMemEval-derived dumps (rebuilt by the pipeline). See the
  [`.gitignore`](.gitignore) for the exact list and the per-directory READMEs for how each is
  regenerated.

## Cite this work

If you use this work, please cite the paper ([arXiv:2606.16707](https://arxiv.org/abs/2606.16707)):

```bibtex
@article{li2026userascode,
  title         = {User as Code: Executable Memory for Personalized Agents},
  author        = {Li, Bojie},
  journal       = {arXiv preprint arXiv:2606.16707},
  year          = {2026},
  eprint        = {2606.16707},
  archivePrefix = {arXiv},
  primaryClass  = {cs.AI},
  url           = {https://arxiv.org/abs/2606.16707}
}
```

## License

Code and documentation are released under the [Apache License 2.0](LICENSE) (see also
[`NOTICE`](NOTICE)). Third-party datasets (LOCOMO, LongMemEval) and memory libraries (Mem0,
A-MEM, MemMachine, EverMemOS, Hindsight) are governed by their own licenses and are not
included here.
