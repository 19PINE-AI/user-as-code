#!/usr/bin/env python3
"""Build the Modularity / Progressive-Disclosure ablation benchmark.

A user has 10 life domains (each is a record type from analytical_bench).
Each domain holds N=50 records. We synthesize 100 questions (10 per
domain, the full question-pattern coverage from analytical_bench), each
requiring only its own domain's records. The benchmark tests three
loading strategies on the same data:

  1. monolithic: all 500 records inlined every query
  2. modular:    10 domain files, accessed via load_domain() helper
  3. manifest:   one-line summary per domain in system prompt + load_domain()

Output: results/modularity_cases.json with shape:
  {
    "user_state": { "trips": [...], "meals": [...], ... },
    "domain_summaries": { "trips": "...", ... },
    "cases": [{case_id, target_domain, question, gold, kind}, ...]
  }
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from analytical_bench.schemas import SCHEMAS  # noqa: E402

DOMAINS = list(SCHEMAS.keys())  # all 10 schemas
N_PER_DOMAIN = 50
QUESTIONS_PER_DOMAIN = 10  # full coverage per domain


def build() -> dict:
    user_state: dict[str, list[dict]] = {}
    summaries: dict[str, str] = {}
    cases: list[dict] = []
    for di, domain in enumerate(DOMAINS):
        sch = SCHEMAS[domain]
        records = sch["gen"](seed=10_000 + di, n=N_PER_DOMAIN)
        user_state[domain] = records
        # Brief summary for the manifest condition.
        sample_keys = ", ".join(records[0].keys()) if records else ""
        summaries[domain] = (
            f"{sch['label']} log ({len(records)} records; fields: {sample_keys})."
        )
        # All 10 question patterns for each domain.
        qs = sch["qfn"](records)[:QUESTIONS_PER_DOMAIN]
        for q in qs:
            cases.append({
                "case_id": f"{domain}_{q['id']}",
                "target_domain": domain,
                "question": q["q"],
                "answer_kind": q["kind"],
                "gold": q["a"],
            })

    return {
        "user_state": user_state,
        "domain_summaries": summaries,
        "cases": cases,
    }


def main() -> None:
    bundle = build()
    out = pathlib.Path(__file__).resolve().parents[1] / "results" / "modularity_cases.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(bundle, f, indent=2)
    n_records = sum(len(v) for v in bundle["user_state"].values())
    print(f"Wrote {len(bundle['cases'])} cases over {len(DOMAINS)} domains "
          f"({n_records} records total) to {out}")


if __name__ == "__main__":
    main()
