# User as Code: Executable Memory for Personalized Agents

Research artifact for the paper **_User as Code: Executable Memory for Personalized Agents_** (Bojie Li, Pine AI).

- 📄 **Paper:** build locally with `make` (see [Building the paper](#building-the-paper)); sources in this repo
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
| [`experiments/`](experiments/) | Full experiment harness, the UaC pipeline (`user_as_code_v5.py`), baseline reimplementations, and committed `results/`. See [`experiments/README.md`](experiments/README.md) |
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
# 1. install deps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. fetch the benchmark datasets (LOCOMO downloads directly; LongMemEval is author-distributed)
./benchmarks/fetch_benchmarks.sh

# 3. set API keys
export GEMINI_API_KEY=...        # main pipeline + judge (Gemini 3 Flash)
export OPENROUTER_API_KEY=...    # cross-family judge; Mem0/A-MEM write path

# 4. run an experiment (see experiments/README.md for the full script -> result map)
cd experiments
python run_locomo_10conv.py      # LOCOMO 600-QA comparison
```

Every per-run output we report is **committed under [`experiments/results/`](experiments/results/)**,
so you can inspect the paper's numbers without re-running anything. The
[`experiments/README.md`](experiments/README.md) maps each script to the paper table/figure it
produces.

### Running the companion website

```bash
cd web
npm install
npm run dev      # http://localhost:5173
# data bundles are regenerated with:  python3 ../scripts/build_site_data.py
```

## Headline results

| Capability | UaC | Best retrieval baseline | Why |
|------------|-----|-------------------------|-----|
| **Factual recall** (LOCOMO, 600 QA) | 78.8% | within 1pt of a full-context upper bound | competitive with the strongest prior systems |
| **Analytical inference** (aggregate queries) | 99% | 6–43% | answer is a one-line computation over typed state, not a search over text |
| **Active Service** (unsolicited alerts) | 100% standard / 85% hard | n/a | constraints execute deterministically on state change — retrieval cannot initiate |

See the paper for the full tables, ablations, cost analysis, and cross-judge/cross-LLM
robustness checks.

## Reproducibility notes

- **Committed:** all experiment scripts, the per-run result JSONs, the synthetic analytical
  benchmark, the Active Service scenarios, and the reference prototype.
- **Not committed (regenerable / third-party):** the vector-index cache
  (`experiments/chroma_db/`), the raw benchmark datasets (`benchmarks/*/data/`, fetched via
  the script), and a few large LongMemEval-derived dumps (rebuilt by the pipeline). See the
  [`.gitignore`](.gitignore) for the exact list and the per-directory READMEs for how each is
  regenerated.

## Citation

```bibtex
@misc{li2026userascode,
  title  = {User as Code: Executable Memory for Personalized Agents},
  author = {Li, Bojie},
  year   = {2026},
  note   = {Pine AI},
  url    = {https://01.me/research/user-as-code}
}
```

## License

Code and documentation are released under the [Apache License 2.0](LICENSE) (see also
[`NOTICE`](NOTICE)). Third-party datasets (LOCOMO, LongMemEval) and memory libraries (Mem0,
A-MEM, MemMachine, EverMemOS, Hindsight) are governed by their own licenses and are not
included here.
