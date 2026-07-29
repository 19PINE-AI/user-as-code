#!/usr/bin/env python3
"""Strict validation for reported LongMemEval, channel, and modularity results."""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

from analytical_bench.scoring import score

HERE = Path(__file__).resolve().parent
R = HERE / "results"
SYSTEMS = ("full_context", "uac_v5", "memmachine", "hindsight", "evermemos", "a_mem", "mem0")
LME_TYPES = {
    "single-session-user": 70, "single-session-assistant": 56,
    "knowledge-update": 78, "temporal-reasoning": 133,
    "single-session-preference": 30, "multi-session": 133,
}

def load(path: Path):
    with open(path, encoding="utf-8-sig") as handle: return json.load(handle)

def close(a, b, eps=1e-12):
    if abs(float(a)-float(b)) > eps: raise AssertionError(f"aggregate mismatch: {a} != {b}")

def validate_lme():
    shared_ids = None
    for system in SYSTEMS:
        path = R / f"lme500_{system}.json"; data = load(path); q = data["by_question"]
        assert data["system"] == system and data["n_target"] == 500 and len(q) == 500, path
        assert len(set(q)) == 500
        assert all("prediction" in x and "judge_correct" in x and not x.get("error") for x in q.values())
        assert Counter(x["question_type"] for x in q.values()) == Counter(LME_TYPES)
        correct = sum(bool(x["judge_correct"]) for x in q.values())
        agg = data["aggregate"]
        assert agg["n_total"] == 500 and agg["n_correct"] == correct
        close(agg["accuracy"], correct/500)
        for kind, n in LME_TYPES.items():
            values = [x for x in q.values() if x["question_type"] == kind]
            k = sum(bool(x["judge_correct"]) for x in values); stored = data["per_type"][kind]
            assert stored["n"] == n and stored["correct"] == k; close(stored["accuracy"], k/n)
        shared_ids = set(q) if shared_ids is None else shared_ids
        assert set(q) == shared_ids, f"LongMemEval IDs differ for {system}"
    print("LongMemEval: PASS (7 artifacts x 500 shared questions)")

def channel_rows(data):
    return [{"conversation": conv, **row} for conv, values in data["details"].items() for row in values]

def validate_channels():
    files = {"full":"locomo5_uac_v5.json", "no_state":"locomo5_uac_v5_ablate_no_state.json",
             "no_facts":"locomo5_uac_v5_ablate_no_facts.json", "no_archive":"locomo5_uac_v5_ablate_no_archive.json"}
    shared = None
    for name, filename in files.items():
        data = load(R/filename); values = channel_rows(data)
        keyed = {(x["conversation"], int(x["qa_idx"])): x for x in values}
        assert len(values) == len(keyed) == 300 and all("judge_correct" in x and not x.get("error") for x in values)
        accuracy = sum(bool(x["judge_correct"]) for x in values)/300
        stored = data["aggregate"].get("judge_accuracy")
        close(stored, accuracy)
        shared = set(keyed) if shared is None else shared
        assert set(keyed) == shared, f"channel keys differ for {name}"
    print("Channels: PASS (4 artifacts x 300 paired questions)")

def validate_modularity():
    bundle = load(R/"modularity_cases.json"); cases = {x["case_id"]:x for x in bundle["cases"]}
    assert len(cases) == 100
    for strategy in ("monolithic", "modular", "manifest"):
        data = load(R/f"modularity_{strategy}.json"); values = data["by_case"]
        assert data["strategy"] == strategy and set(values) == set(cases)
        recomputed = []
        for cid, row in values.items():
            assert not row.get("error") and row["gold"] == cases[cid]["gold"]
            correct = score(cases[cid]["answer_kind"], row["prediction"], cases[cid]["gold"])
            assert bool(row["correct"]) == correct; recomputed.append(correct)
        agg=data["aggregate"]; k=sum(recomputed)
        assert agg["n"] == 100 and agg["correct"] == k; close(agg["accuracy"], k/100)
        for target, key in (("prompt_tokens","prompt"),("output_tokens","output"),("thoughts_tokens","thoughts")):
            assert agg[target] == sum(x.get("usage",{}).get(key,0) for x in values.values())
    print("Modularity: PASS (3 artifacts x 100 cases; scores and usage recomputed)")

def main():
    validate_lme(); validate_channels(); validate_modularity(); print("FINAL VALIDATION PASSED")

if __name__ == "__main__": main()
