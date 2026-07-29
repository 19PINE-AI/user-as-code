# Author Information Requests for Reproducibility

This document lists the facts we cannot recover reliably from the paper,
repository, result artifacts, or Git history. We need to answer these questions
before finalizing Section 4 of the AAAI reproducibility checklist.

We need to add the requested information to the manuscript itself; recording it
only in the anonymous code appendix does not satisfy checklist items 4.2 or 4.8.

## Current checklist status

All checklist items are complete except these three:

| Item | Current answer | What remains |
|---|---|---|
| 4.2 Parameter values tried and selection criteria | **partial** | Obtain the development history requested below and add it to Section 4.1 |
| 4.7 Seed-setting method | **partial** | No information is missing; hosted-model inference seeds were not supplied and cannot be added retrospectively |
| 4.8 Computing infrastructure | **partial** | Obtain the host details requested below and add them to Section 4.1 |

After receiving the requested information, this file is the only internal
checklist note needed to finish the checklist. The manuscript and checklist
already contain the repository-recoverable information for all other items.

## Request 1: Development-time parameter selection (checklist 4.2)

### Information to request

For each setting below, ask the author who selected it:

1. Was the setting fixed a priori, inherited from an earlier implementation or
   publication, left at a provider/library default, or tuned during development?
2. If it was tuned, what exact values were tried?
3. What development cases, conversations, or split were used to compare them?
4. What quantitative metric or qualitative criterion selected the final value?
5. Was any reported benchmark test set inspected while choosing the value?

Settings requiring confirmation:

| Setting | Final value already established | Missing information |
|---|---:|---|
| UaC Phase-1 session-input cap | 12,000 characters | Provenance; values tried; selection data and criterion |
| UaC Phase-2 serialized-fact cap | 30,000 characters | Provenance; values tried; selection data and criterion |
| UaC answer-state cap | 6,000 characters | Provenance; values tried; selection data and criterion |
| UaC fact retrieval depth | 20 | Provenance; values tried; selection data and criterion |
| UaC archive retrieval depth | 10 chunks | Provenance; values tried; selection data and criterion |
| Archive chunk size and overlap | 300 words, approximately 75-word overlap | Provenance; alternatives tried; selection criterion |
| Archive duplicate key | First 80 characters | Provenance; alternatives tried; selection criterion |
| MemMachine controlled retrieval | 30 turns with three neighbors per side | Confirm fixed from the published design versus chosen for this study |
| EverMemOS controlled retrieval | Top-3 scenes; top-20 semantic and BM25 cells; top-10 final cells | Confirm fixed/inherited versus tuned; provide values tried if tuned |
| Cue-free v3 generation retries | Three attempts | Confirm development process and criterion after v2.1 failure inspection |

### Complete recoverable parameter record

This table preserves the known values and provenance so no separate internal
parameter note is needed.

| Setting | Final value | What we know about its provenance |
|---|---|---|
| UaC Phase-1 session cap | 12,000 characters | Fixed in the evaluated implementation; selection history still requested above |
| UaC Phase-2 serialization cap | 30,000 characters | Fixed in the evaluated implementation and discussed as a limitation; selection history still requested above |
| UaC answer-state cap | 6,000 characters | Fixed in the evaluated implementation; selection history still requested above |
| UaC fact retrieval | 20 | Fixed in the evaluated implementation; selection history still requested above |
| UaC archive retrieval | 10 chunks | Fixed in the evaluated implementation; selection history still requested above |
| Archive chunks | At most 300 words with approximately 75-word overlap | Fixed in the evaluated implementation; selection history still requested above |
| Archive duplicate key | First 80 characters | Fixed in the evaluated implementation; selection history still requested above |
| Analytical structuring cap | 500,000 characters | Separate nonbinding benchmark ceiling; no evaluated case reaches it |
| Analytical tool limit | 15 turns and 20 seconds per call | Fixed protocol shared by UaC and Full Context+REPL |
| MemMachine retrieval | 30 turns plus three neighbors per side for full LOCOMO | Controlled implementation of contextual expansion; inheritance versus study-specific choice still requires confirmation |
| Hindsight constants | Temporal scale 30 days, semantic threshold 0.7, graph decay 0.6, two hops, RRF 60, rerank to 20, and 4,000-token context | Source comments identify the principal constants as inherited from the Hindsight paper; not tuned for this evaluation |
| EverMemOS retrieval | Top-3 scenes, top-20 semantic cells, top-20 BM25 cells, final top-10 cells, and foresight boost 0.5 | Fixed controlled reimplementation; selection history still requires confirmation |
| A-MEM evolution/retrieval | Evolution threshold 100, five evolution neighbors, and answer retrieval 10 | Library/source defaults plus the evaluated wrapper retrieval setting |
| Mem0 analytical retrieval | Ingestion batches 20 and search limit 20 | Explicit controlled analytical-runner settings |
| Full-LOCOMO generation | Krill provider defaults; no transmitted temperature, thinking budget, or seed | The Krill compatibility path did not expose the nominal wrapper controls; not selected in a local sweep |
| LongMemEval generation | Temperature 1.0; answer/judge thinking budgets 2,048/256 | Historical direct-Google client configuration; no documented sweep |
| Cue-free v3 IR retries | Three attempts | Post-v2.1 engineering regression setting developed after inspecting v2.1 failures; not a held-out selection |
| Modularity turn limits | Eight for Monolithic and ten for Modular/Manifest | Fixed evaluated protocol; no documented sweep |

The Hindsight constants are already documented as inherited rather than tuned.
Provider defaults were not selected in a local sweep. The analytical 500,000-
character cap was nonbinding. These need no further request unless an author
knows that they were also varied during development.

### Preferred response format

One row per setting:

```text
Setting:
Classification: fixed a priori / inherited / provider default / tuned
Values tried:
Development data or cases:
Selection metric or qualitative criterion:
Test-set involvement:
Reason for final choice:
```

If no alternatives were tried, write `one value: <final value>` and explain why
it was fixed. Do not invent a range or describe historical exploratory scripts
as a sweep unless they actually informed the final choice.

### Where to add it in the paper

Add a compact paragraph in Section 4.1 immediately after **Models and
software** and before **Run integrity**, titled **Parameter selection.** A
suitable structure is:

```text
Parameter selection. [List settings fixed a priori or inherited and their
sources.] For settings tuned during development, we tried [exact values] on
[development data] and selected [final values] using [criterion]. [State
whether the reported test sets were excluded from parameter selection.]
```

If the answer requires more than a short paragraph, use a compact standalone
selection/provenance table while retaining the distributed final values beside
their corresponding methods and experiments.

### Checklist consequence

- Answer **yes** only when the manuscript gives the number/range of values tried
  and the selection criterion for every tuned setting, and identifies settings
  for which only one value was used.
- Otherwise answer **partial** or **no**, depending on the completeness of the
  author response.

## Request 2: Computing infrastructure (checklist 4.8)

### Information to request

For every materially distinct machine or environment used for the reported
experiments, request:

1. Experiment families run on that machine.
2. CPU manufacturer and exact model; core count if known.
3. Installed RAM.
4. GPU model and GPU memory, or an explicit statement that no local GPU was
   used for the experiment.
5. Operating system and version.
6. Python version.
7. Whether model inference was hosted remotely, executed locally, or mixed.
8. Any separate environment used for the original LongMemEval, analytical,
   channel, modularity, or cue-free runs.
9. A frozen dependency export or lock file, if the original environment still
   exists.

At minimum, map the following experiment families to machines/environments:

- Full LOCOMO, Luna panel;
- Full LOCOMO, Gemini panel;
- LongMemEval;
- analytical benchmark and corrected-item rerun;
- cue-free constraint evaluation;
- answer-channel lesions; and
- modularity/progressive-disclosure evaluation.

Do not infer hardware from the `darwin; arm64` Gemini CLI User-Agent. That value
is a transmitted request identity and is not reliable evidence of the local
host.

### Preferred response format

One row per distinct machine/environment:

```text
Environment name:
Experiment families:
CPU and core count:
RAM:
GPU and GPU memory, or no local GPU:
Operating system and version:
Python version:
Hosted/local inference:
Environment or lock-file path, if retained:
```

### Information already available

The paper already lists the hosted models and these Full-LOCOMO software
versions: OpenAI SDK 1.97.1, ChromaDB 1.5.7, sentence-transformers 3.4.1,
transformers 4.48.3, PEFT 0.14.0, Mem0 1.0.5, and agentic-memory 0.0.1.
We should correct these values only if we confirm that the result metadata is
inaccurate.

The following experiment-specific facts are also already recoverable and do not
need to be requested again:

| Experiment family | Remote execution and retained local information | Still needed |
|---|---|---|
| Full LOCOMO, Luna | Krill OpenAI-compatible endpoint with GPT-5.6 Luna; artifacts record OpenAI SDK 1.97.1, Mem0 1.0.5, agentic-memory 0.0.1, ChromaDB 1.5.7, and sentence-transformers 3.4.1; the reproduction overlay pins transformers 4.48.3 and PEFT 0.14.0; timestamps span July 25--26, 2026 UTC | CPU, RAM, OS/version, Python version, and GPU/no-GPU status |
| Full LOCOMO, Gemini | Krill OpenAI-compatible endpoint with Gemini 3 Flash Preview; same retained package information as Luna; timestamps span July 25--26, 2026 UTC | CPU, RAM, OS/version, Python version, and GPU/no-GPU status |
| LongMemEval | Direct Google Gemini 3 Flash Preview; historical client and per-question outputs retained; no complete environment export or start/end metadata | CPU, RAM, OS/version, Python version, GPU/no-GPU status, and full dependency versions |
| Analytical benchmark | Gemini 3 Flash Preview; corrected item through Krill; generators, runners, tools, scores, and repair provenance retained | CPU, RAM, OS/version, Python version, GPU/no-GPU status, and full dependency versions |
| Cue-free constraints | Krill with GPT-5.6 Luna; frozen protocol, generated programs, traces, manifests, sandbox, validators, and execution timestamps retained | CPU, RAM, OS/version, Python version, GPU/no-GPU status, and full dependency versions |
| Channel and modularity studies | Hosted Gemini/Krill paths recorded by runners; per-item outputs and deterministic inputs retained | CPU, RAM, OS/version, Python version, GPU/no-GPU status, and full dependency versions |

### Where to add it in the paper

Add a paragraph immediately after the proposed **Parameter selection**
paragraph and before **Run integrity**, titled **Computing infrastructure.**
Suggested structure:

```text
Computing infrastructure. Hosted inference used [providers/models]. Local
preprocessing, retrieval, sandbox execution, and analysis ran on [CPU, RAM,
GPU/no-GPU, OS, Python]. [Map any different experiment family to its separate
environment.] The preceding setup paragraphs list the relevant model and
library versions.
```

If multiple machines were used, add a compact second two-column table with
`Experiment family` and `Host environment` rather than writing an ambiguous
combined specification.

### Checklist consequence

- Answer **yes** only after the manuscript states CPU, memory, GPU/no-GPU
  status, OS, Python, relevant software versions, and which experiments used
  each environment.
- Until then, answer **partial**.

## Item that does not require an author information request

We should mark checklist item 4.7 **partial**, not because information is
missing, but because our reported hosted-model requests did not supply decoding
seeds. The manuscript already gives all local seeds and their setting methods
and explicitly discloses unseeded hosted inference. We cannot retrospectively
add seeds to completed runs.
