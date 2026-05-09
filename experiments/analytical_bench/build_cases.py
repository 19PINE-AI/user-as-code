#!/usr/bin/env python3
"""Build the 100-case analytical benchmark.

10 record types x 10 questions each. N values are tiered across
{20, 50, 100, 200, 500} for scaling analysis. For each (type, question_idx)
pair we generate a separate user history so questions are independent.

Output: results/analytical_cases.json with shape:
{
  "cases": [
    {
      "case_id": "trips_q3_n50",
      "type": "trips",
      "n": 50,
      "question_id": "trips_groupby_purpose",
      "question": "...",
      "answer_kind": "set",
      "gold": [...],
      "records": [...],
    },
    ...
  ]
}
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from analytical_bench.schemas import SCHEMAS  # noqa: E402

# Tiered N values: each type gets 2 cases at each tier (10 cases / type).
N_TIERS = [20, 50, 100, 200, 500]


def build_cases() -> list[dict]:
    cases: list[dict] = []
    for type_idx, (type_name, schema) in enumerate(SCHEMAS.items()):
        # Generate one set of records per N tier. Each tier provides 2 questions
        # so we cover all 10 question patterns across the type.
        for tier_idx, n in enumerate(N_TIERS):
            seed = 1000 * (type_idx + 1) + n
            records = schema["gen"](seed, n)
            qs = schema["qfn"](records)
            assert len(qs) >= 10, f"{type_name} produced {len(qs)} questions, need 10"
            # Pick 2 questions per tier in a round-robin so each tier gets a mix.
            q_a = qs[2 * tier_idx]
            q_b = qs[2 * tier_idx + 1]
            for q in (q_a, q_b):
                cases.append({
                    "case_id": f"{type_name}_{q['id']}_n{n}",
                    "type": type_name,
                    "n": n,
                    "question_id": q["id"],
                    "question": q["q"],
                    "answer_kind": q["kind"],
                    "gold": q["a"],
                    "records": records,
                })
    return cases


def main() -> None:
    cases = build_cases()
    out_path = pathlib.Path(__file__).resolve().parents[1] / "results" / "analytical_cases.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"cases": cases}, f, indent=2)
    print(f"Wrote {len(cases)} cases to {out_path}")
    # Brief summary by type
    from collections import Counter
    by_type = Counter(c["type"] for c in cases)
    by_n = Counter(c["n"] for c in cases)
    by_kind = Counter(c["answer_kind"] for c in cases)
    print(f"By type: {dict(by_type)}")
    print(f"By N: {dict(by_n)}")
    print(f"By answer kind: {dict(by_kind)}")


if __name__ == "__main__":
    main()
