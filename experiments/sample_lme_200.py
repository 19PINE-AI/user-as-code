#!/usr/bin/env python3
"""Stratified-sample 200 LongMemEval questions (40% of 500).

Per-type counts proportional to the source dataset:
  temporal-reasoning: 133 -> ~53
  multi-session:       133 -> ~53
  knowledge-update:     78 -> ~31
  single-session-user:  70 -> ~28
  single-session-assistant: 56 -> ~22
  single-session-preference: 30 -> ~12 (round to 13)
Target total: 200, seed=42.
"""
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "benchmarks/longmemeval/data/longmemeval_oracle.json"
OUT = Path(__file__).resolve().parent / "results" / "lme_200_sample.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

random.seed(42)
items = json.load(open(DATA))
by_type = defaultdict(list)
for q in items:
    by_type[q["question_type"]].append(q)

total_per_type = {t: len(v) for t, v in by_type.items()}
target = 200
total_src = sum(total_per_type.values())
allocations = {t: round(c * target / total_src) for t, c in total_per_type.items()}
diff = target - sum(allocations.values())
if diff != 0:
    biggest = max(allocations, key=allocations.get)
    allocations[biggest] += diff

sample = []
for t, n in allocations.items():
    pool = by_type[t]
    random.shuffle(pool)
    sample.extend(pool[:n])

random.shuffle(sample)

with open(OUT, "w") as f:
    json.dump({
        "seed": 42,
        "total": len(sample),
        "by_type_target": allocations,
        "by_type_actual": dict(Counter(q["question_type"] for q in sample)),
        "questions": [
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
            for q in sample
        ],
    }, f, indent=2)

print(f"Wrote {len(sample)} questions to {OUT}")
print("By type:", dict(Counter(q["question_type"] for q in sample)))
