# Active Service v2.0 protocol

Active Service v2.0 is a preregistered replacement for the deprecated
proactive-alert pilot. Its purpose is narrow: test whether a persistent
User-as-Code program can turn facts established in earlier user sessions into
an executable constraint that fires at the first objectively conflicting or
time-critical user event.

The machine-readable protocol and rubrics are frozen in
`active_service_v2_protocol.json`. The runner refuses to proceed if the source
scenario file's SHA-256 digest differs from the registered digest.

## Eligibility

The original 40 standard scenarios are preserved unchanged. Eighteen are
eligible. They involve direct semantic constraints over user-stated data:

- two travel-document state/date cases;
- five financial authorization, cancellation, or preference conflicts;
- seven calendar/resource conflicts; and
- four user-stated deadlines.

The other 22 standard cases are excluded before model execution. The exclusion
reasons are recorded individually in the protocol JSON. In particular, v2.0
does not score medical advice, externally supplied immigration/tax/legal
rules, unknown account or filing status, subjective risk thresholds, or a
trigger that explicitly asks the assistant to recall reminders. All 20 legacy
hard scenarios are also outside v2.0: their authored golds have not been
reconciled and several contain contradictory dates, arithmetic, or policy
assumptions.

This eligibility decision deliberately produces a smaller but auditable suite.
Results must be described as an 18-case curated evaluation, never as results on
the original 40- or 60-case pilot.

## Cue-free interaction

For every session, only lines authored by the user are retained. Assistant
continuations are never passed to any system because several reveal the
intended alert. The trigger is the actual user text from the designated trigger
session; the `trigger_session.description`, expected alert, authored
computation, and explanation are evaluation metadata and remain hidden.

UaC receives the same update instruction after every user session. It must
produce a self-contained Python module with JSON-serializable `STATE` and a
`check_constraints(current_time)` function. The program is persisted,
validated, and executed after each update. A successful case requires:

1. valid and executable code after every session;
2. no alert before the designated trigger; and
3. at least one post-trigger alert whose message satisfies the frozen rubric.

Full Context receives all pre-trigger user sessions and their timestamps.
Retrieval receives the single pre-trigger session selected by frozen lexical
BM25-style scoring. Both baselines then answer the same trigger once under the
same neutral personal-assistant instruction. Neither prompt asks for an alert.

## Code validation and execution

Generated modules are parsed before execution. Imports are limited to a small
standard-library allowlist. File, network, process, dynamic-code, reflection,
interactive-input, nondeterministic-clock, and dunder access are rejected.
The isolated interpreter uses restricted builtins, CPU and platform-supported
memory limits, a wall-clock timeout, and a minimal environment. Validation or runtime
errors are stored in the trace and count as misses; there is no manual repair.

Every case trace contains the exact user-only updates, raw model generations,
extracted source, validation outcome, executed `STATE`, emitted alerts,
baseline prompts/responses, and deterministic rubric matches. Credentials and
API transport metadata are never stored.

## Frozen scoring

Each case has named concept groups. A candidate alert or response passes only
when it matches at least one regular expression in every group. This is an
all-groups rule: there is no partial-credit threshold, LLM judge, or manual
override. UaC additionally fails if any pre-trigger alert is emitted. Errors
are misses. Aggregate recall is accompanied by a two-sided 95% Wilson interval.

The canonical evaluation runs one completion per update/response under both
GPT-5.6 Luna and Gemini 3 Flash Preview through the same shared Krill AI client
used by the completed LOCOMO experiments. The client selects its established
model-specific request profile: the OpenAI SDK identity for Luna and the
model-aware Gemini CLI identity for Gemini. Krill controls the remaining
generation defaults; no unsupported seed, temperature, output cap, or Gemini
thinking budget is claimed. The model/API names and exact runner/scorer commit
are written to each result manifest.
Smoke tests may validate transport and trace completeness, but neither the
eligibility set nor scorer may be changed after inspecting model outputs.

Initial smoke attempts incorrectly used direct Gemini and OpenAI credentials;
they returned authentication or quota errors and produced no scenario
completion. Before any scenario output was observed, the transport declaration
was amended to reuse the repository's proven Krill integration and its two
established backbones. The case set, prompts, program contract, retrieval rule,
and scorer were unchanged. This amendment is recorded in the machine-readable
protocol.
