# Benchmark datasets

The experiments use two third-party long-term-memory benchmarks. We do **not**
redistribute their raw data here (each has its own license); instead, fetch them
into the paths below with `./fetch_benchmarks.sh` (or manually).

| Benchmark | Expected path | Source |
|-----------|---------------|--------|
| LOCOMO | `benchmarks/locomo/data/locomo10.json` | <https://github.com/snap-research/locomo> |
| LongMemEval | `benchmarks/longmemeval/data/longmemeval_oracle.json` | <https://github.com/xiaowu0162/LongMemEval> |

## Quick start

```bash
cd benchmarks
./fetch_benchmarks.sh
```

LOCOMO downloads directly from GitHub. LongMemEval is distributed by its authors
via Google Drive / Hugging Face; the script prints the current instructions and
the exact destination path to drop the file into.

## What the experiments expect

- **LOCOMO** (`locomo10.json`): 10 conversations, 60 QAs each (600 total). Used by
  the headline LOCOMO numbers, the ablations, and the `conv-30` case study.
- **LongMemEval** (`longmemeval_oracle.json`): the 500-question oracle split. The
  200-question stratified sample and the assembled 500-question file used in the
  paper are *regenerated* from this by `experiments/sample_lme_200.py` and
  `experiments/build_lme_full_500.py` (they are git-ignored as derived data).
