#!/usr/bin/env python3
"""Build the full 500-question LongMemEval list (no sampling).
Produces results/lme_500_full.json with same record shape as lme_200_sample.json.
"""
import json
from pathlib import Path
from collections import Counter

DATA = Path(__file__).resolve().parent.parent / "benchmarks/longmemeval/data/longmemeval_oracle.json"
OUT = Path(__file__).resolve().parent / "results" / "lme_500_full.json"

items = json.load(open(DATA))

records = [
    {
        "question_id": q["question_id"],
        "question_type": q["question_type"],
        "question": q["question"],
        "answer": q["answer"],
        "question_date": q["question_date"],
        "haystack_dates": q["haystack_dates"],
        "haystack_session_ids": q["haystack_session_ids"],
        "haystack_sessions": q["haystack_sessions"],
        "answer_session_ids": q["answer_session_ids"],
    }
    for q in items
]

with open(OUT, "w") as f:
    json.dump({
        "total": len(records),
        "by_type_actual": dict(Counter(q["question_type"] for q in records)),
        "questions": records,
    }, f, indent=2)

print(f"Wrote {len(records)} questions to {OUT}")
print("By type:", dict(Counter(q["question_type"] for q in records)))
