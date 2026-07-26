# Exploratory Proactive-Alert Scenarios

This directory contains pilot scenarios for studying alerts derived from
multi-session personal state. These artifacts are **exploratory and are not a
publication-ready benchmark**.

The stored pilot runs do not evaluate the constraint-execution architecture
described by the reference prototype. In particular, the standard evaluator
asks the answer model to look for alerts, some trigger dialogues contain
assistant-side cues, and the UaC experiment implementation does not generate,
persist, and execute `ACTIVE_ALERTS` constraints. Consequently, the historical
detection rates must not be cited as evidence for proactive constraint
execution or as cross-system comparisons.

`active_service_scenarios.json` retains 40 authored scenarios across travel,
health, finance, scheduling, and deadline categories. Each scenario includes
multi-session dialogue, a nominal trigger, an expected alert, and an author
explanation. The files are useful as test-design material only.

Before this can become a reportable evaluation, a replacement protocol must:

1. ingest user messages only and exclude assistant continuations that reveal
   the intended alert;
2. deliver the actual trigger user message without an explicit alert request;
3. generate, persist, and execute constraints in the evaluated UaC system;
4. record an inspectable execution trace linking stored state, constraint code,
   and emitted alert;
5. apply the same cue-free interaction protocol to every baseline; and
6. preregister deterministic scoring before running the comparison.

Until those conditions are met, result JSONs and legacy figures bearing the
Active Service label are deprecated pilot artifacts.

The frozen replacement protocol is documented in
[`ACTIVE_SERVICE_V2.md`](ACTIVE_SERVICE_V2.md) and
`active_service_v2_protocol.json`. It preregisters a 17-case subset with
user-only histories, cue-free triggers, executable UaC constraints, matched
baselines, isolated traces, and deterministic scoring. Its outputs are
publication-eligible only after the complete frozen run passes the integrity
checks described there.

The post-evaluation Active Service v3 engineering work is documented in
[`ACTIVE_SERVICE_V3.md`](ACTIVE_SERVICE_V3.md). It preserves the 17 frozen
cases and rubrics but was tuned after inspecting v2.1 failures, so its 17/17
result is a regression result rather than an unbiased benchmark estimate.
