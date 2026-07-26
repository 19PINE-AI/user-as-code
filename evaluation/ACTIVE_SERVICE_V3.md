# Active Service v3 regression system

Active Service v3 is the engineering successor to the frozen v2.1 evaluation.
It addresses the observed v2.1 failure modes while preserving the eligible
17 cases, user-only histories, trigger timing, sandbox, and deterministic
rubrics. Because its design was developed after inspecting v2.1 outputs, its
result is a regression-suite result and must not replace the preregistered
4/17 result as an unbiased evaluation.

## Why v2.1 passed only 4/17

The validated v2.1 artifact contains thirteen UaC misses:

- Five cases failed at the generated-Python boundary. Two otherwise allowed
  date operations caused lazy imports rejected by the sandbox
  (`finance_06`, `schedule_02`); one module used forbidden dynamic import
  (`schedule_03`); one referenced an unimported module (`schedule_06`); and
  one ended with a stray invalid Unicode code point (`schedule_07`).
- `finance_05` emitted an alert about an upcoming account closure before a
  dependent payment was known. State was incorrectly treated as a violation.
- Seven executable trigger alerts omitted necessary semantic evidence or an
  actionable relationship: `travel_03`, `travel_07`, `finance_01`,
  `finance_03`, `schedule_04`, `deadline_03`, and `deadline_07`.

The failures were architectural. Free-form Python made semantic success depend
on incidental import and syntax choices; unstructured alert generation
compressed away names, parties, comparison words, consequences, or countdown
units; and the same model was responsible for date arithmetic, activation
timing, and prose.

## System changes

`experiments/active_service_engine.py` introduces a strict declarative
constraint intermediate representation (IR):

1. The model records durable state and explicit constraints as JSON.
2. The IR validator enforces an exact schema, real ISO dates, unique IDs,
   explicit conflict wording, self-contained deadline placeholders, and valid
   activation semantics. Structurally invalid generations receive bounded,
   automatic machine-feedback retries.
3. Trusted code compiles validated IR into the small Python module executed by
   the existing AST validator and isolated sandbox. The model no longer writes
   executable Python.
4. Trusted code performs deadline arithmetic. Exact deadlines can be stored
   directly; derived deadlines use an anchor date and signed day offset. The
   compiler calculates the deadline, seven-day activation window, expiry, and
   live days-remaining value.
5. Direct conflicts activate only after both sides are known. Completed use or
   exhausted capacity remains state until a new proposal attempts to use it.
6. Alert messages must retain concrete user vocabulary, name both sides,
   state numeric or temporal comparisons explicitly, say that a direct
   incompatibility is a conflict, and include a grounded consequence or next
   action.

The model receives only the complete user-authored history and session
timestamp. Expected alerts, trigger descriptions, rubric groups, assistant
continuations, and scenario metadata are not included in its prompts.

## Result and verification

The final GPT-5.6 Luna artifact is stored at
`experiments/results/active_service_v3_gpt_5_6_luna`.

| Category | Passed |
|---|---:|
| Travel-document validity | 2/2 |
| Financial authorization conflicts | 5/5 |
| Scheduling conflicts | 7/7 |
| Deadline expiration | 3/3 |
| **All** | **17/17** |

All 36 session updates produced valid and executable modules. No case emitted
a pre-trigger alert. The independent replay validator reconstructs each prompt,
model attempt, parsed IR, compiled source, AST validation, sandbox execution,
activation decision, alert candidate, and frozen rubric score.

Run the local integrity tests:

```bash
python -m unittest \
  experiments/test_active_service_v2.py \
  experiments/test_active_service_engine.py \
  experiments/test_active_service_v3.py -v
```

Replay the final artifact without model calls:

```bash
python experiments/validate_active_service_v3.py \
  experiments/results/active_service_v3_gpt_5_6_luna
```

Run a new model-backed regression (requires `KRILL_API_KEY`):

```bash
python experiments/run_active_service_v3.py \
  --model gpt-5.6-luna \
  --output-dir experiments/results/active_service_v3_gpt_5_6_luna
```

## Interpretation

The 17/17 replay proves that the revised system handles every known v2.1
regression under the unchanged scorer. It does not establish out-of-sample
accuracy: the suite influenced the new IR, prompt, and quality invariants.
Publication claims should retain the preregistered v2.1 result and describe v3
as post-evaluation engineering until a new held-out scenario set is frozen and
run once.
