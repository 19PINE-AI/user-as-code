# Exploratory Proactive-Alert Scenarios

This directory contains the deprecated exploratory pilot, the frozen Active
Service v2.1 evaluation reported in the paper, and the post-evaluation v3
engineering regression. Only the legacy pilot artifacts are not suitable for
reporting.

The stored pilot runs do not evaluate the constraint-execution architecture
described by the reference prototype. In particular, the standard evaluator
asks the answer model to look for alerts, some trigger dialogues contain
assistant-side cues, and the UaC experiment implementation does not generate,
persist, and execute `ACTIVE_ALERTS` constraints. Consequently, we do not use
the historical detection rates to support claims about proactive constraint
execution or cross-system performance.

`active_service_scenarios.json` retains 40 authored scenarios across travel,
health, finance, scheduling, and deadline categories. Each scenario includes
multi-session dialogue, a nominal trigger, an expected alert, and an author
explanation. The files are useful as test-design material only.

We replaced this pilot with a protocol that:

1. ingest user messages only and exclude assistant continuations that reveal
   the intended alert;
2. deliver the actual trigger user message without an explicit alert request;
3. generate, persist, and execute constraints in the evaluated UaC system;
4. record an inspectable execution trace linking stored state, constraint code,
   and emitted alert;
5. apply the same cue-free interaction protocol to every baseline; and
6. preregister deterministic scoring before running the comparison.

The older result JSONs and figures bearing the Active Service label do not meet
these conditions, so we retain them only as deprecated pilot artifacts.

We document the frozen replacement protocol and our completed Luna evaluation in
[`ACTIVE_SERVICE_V2.md`](ACTIVE_SERVICE_V2.md) and
`active_service_v2_protocol.json`. It preregisters a 17-case subset with
user-only histories, cue-free triggers, executable UaC constraints, matched
baselines, isolated traces, and deterministic scoring. We report results only
from a complete frozen run that passes the integrity checks described there. We
preregistered Luna and Gemini as candidate backbones, but we completed and
report the cue-free evaluation with Luna only.

The post-evaluation Active Service v3 engineering work is documented in
[`ACTIVE_SERVICE_V3.md`](ACTIVE_SERVICE_V3.md). It preserves the 17 frozen
cases and rubrics but was tuned after inspecting v2.1 failures, so its 17/17
result is a regression result rather than an unbiased benchmark estimate.
