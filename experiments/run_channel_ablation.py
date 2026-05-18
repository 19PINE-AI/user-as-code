#!/usr/bin/env python3
"""Retrieval-channel ablation for UaC v5.

For each of the 5 LOCOMO conversations, ingest once with UaC v5 (Phase 1
extraction + Phase 2 structuring), then answer each of the 60 QAs three times
under three leave-one-out channel configurations:
  - no_state:    only FACTS + ARCHIVE
  - no_facts:    only STATE + ARCHIVE
  - no_archive:  only STATE + FACTS

For comparison, the full-3-channel UaC v5 numbers are already in
results/locomo5_uac_v5.json (78.0% overall) so we do not re-run them here.

Resumable: writes results/locomo5_uac_v5_ablate_<config>.json after every QA.
"""
from __future__ import annotations
import argparse
import json
import pathlib
import re
import sys
import time
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from runner_utils import (  # noqa: E402
    _log, gemini_call, extract_concise, judge_answer, token_f1, GEMINI_MODEL,
)
from user_as_code_v5 import UserAsCodeV5  # noqa: E402

DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "benchmarks/locomo/data/locomo10.json"
RESULTS_DIR = pathlib.Path(__file__).resolve().parent / "results"

CHANNEL_CONFIGS = {
    "no_state":   {"state": False, "facts": True,  "archive": True},
    "no_facts":   {"state": True,  "facts": False, "archive": True},
    "no_archive": {"state": True,  "facts": True,  "archive": False},
}


def retrieve_with_channels(uac: UserAsCodeV5, query: str, *,
                           use_state: bool, use_facts: bool, use_archive: bool,
                           top_k_archive: int = 10) -> str:
    """Copy of UaC v5 retrieve() with per-channel gating."""
    parts = []

    if use_state and uac.code_state and not uac._code_stale:
        code = uac.code_state
        if len(code) > 6000:
            code = code[:6000] + "\n# ... (truncated)"
        parts.append("=== Structured User State (Python) ===")
        parts.append(code)

    if use_facts and uac._facts_db.count() > 0:
        try:
            results = uac._facts_db.query(
                query_texts=[query],
                n_results=min(20, uac._facts_db.count()),
            )
            if results["documents"][0]:
                parts.append("\n=== Relevant Facts ===")
                for doc in results["documents"][0]:
                    parts.append(f"- {doc}")
        except Exception:
            pass

    if use_archive and uac._archive.count() > 0:
        try:
            results = uac._archive.query(
                query_texts=[query],
                n_results=min(top_k_archive, uac._archive.count()),
            )
            if results["documents"][0]:
                parts.append("\n=== Conversation Excerpts ===")
                seen = set()
                for doc in results["documents"][0]:
                    key = doc[:80]
                    if key not in seen:
                        seen.add(key)
                        parts.append(doc)
        except Exception:
            pass

    return "\n\n".join(parts)


def answer_with_channels(uac: UserAsCodeV5, question: str, channels) -> str:
    """Run UaC v5 answer with retrieval limited to selected channels."""
    if uac._code_stale and uac.fact_list:
        uac.structure()

    context = retrieve_with_channels(
        uac, question,
        use_state=channels["state"], use_facts=channels["facts"],
        use_archive=channels["archive"],
    )

    system_instruction = f"""You have access to a user's stored information: structured Python code, extracted facts, and conversation excerpts.
Use ALL available information to answer. Think carefully about dates, relationships, and details.
If the answer requires computation, compute it from the data.
If truly not available, say "No information available".

{context}"""

    try:
        out = gemini_call(
            contents=f"{question}\n\nThink step by step using the stored information, then give ONLY a concise final answer on the last line.",
            system_instruction=system_instruction,
            thinking_budget=2048,
            temperature=1.0,
        )
        return extract_concise(out)
    except Exception as e:
        return f"Error: {e}"


def get_sessions(conv):
    c = conv["conversation"]
    keys = sorted(
        [k for k in c.keys() if re.match(r"^session_\d+$", k)],
        key=lambda x: int(x.split("_")[1]),
    )
    out = []
    for sk in keys:
        date = c.get(f"{sk}_date_time", "")
        turns = c[sk]
        out.append({"session_id": sk, "date": date, "turns": turns})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", choices=list(CHANNEL_CONFIGS.keys()), required=True)
    ap.add_argument("--max-qa", type=int, default=60)
    ap.add_argument("--conv-start", type=int, default=0)
    ap.add_argument("--conv-end", type=int, default=5)
    args = ap.parse_args()

    out_path = RESULTS_DIR / f"locomo5_uac_v5_ablate_{args.config}.json"
    channels = CHANNEL_CONFIGS[args.config]

    if out_path.exists():
        with open(out_path) as f:
            results = json.load(f)
    else:
        results = {
            "system": f"uac_v5_ablate_{args.config}",
            "channels": channels,
            "model": GEMINI_MODEL,
            "max_qa_per_conv": args.max_qa,
            "per_conversation": {},
            "details": {},
        }

    with open(DATA_PATH) as f:
        all_convs = json.load(f)
    convs = all_convs[args.conv_start:args.conv_end]

    total_judge = []

    for ci, conv in enumerate(convs):
        conv_id = conv.get("sample_id", f"conv_{ci}")

        prev_details = results["details"].get(conv_id, [])
        completed_idx = {d["qa_idx"] for d in prev_details}

        if conv_id in results["per_conversation"]:
            pc = results["per_conversation"][conv_id]
            if pc.get("n_questions", 0) >= args.max_qa:
                _log(f"\n=== Conv {conv_id}: SKIP (already done, n={pc['n_questions']}, judge={pc['judge_accuracy']:.3f}) ===")
                for d in prev_details:
                    total_judge.append(1.0 if d["judge_correct"] else 0.0)
                continue

        _log(f"\n=== Conv {ci} ({conv_id}) ablation={args.config} ===")
        sessions = get_sessions(conv)

        uac = UserAsCodeV5(user_id=f"locomo5_ablate_{args.config}_{conv_id}_{int(time.time())}")
        for s in sessions:
            turn_lines = [f"{t['speaker']}: {t['text']}" for t in s["turns"]]
            uac.ingest_session(turn_lines, s["session_id"], s["date"])
            _log(f"    ingested {s['session_id']}")
        uac.structure()
        _log(f"    structured ({len(uac.code_state)} chars)")

        qas = conv["qa"][: args.max_qa]
        for qi, qa in enumerate(qas):
            if qi in completed_idx:
                continue
            q = qa.get("question", "")
            gold = str(qa.get("answer", ""))
            category = str(qa.get("category", "uncategorized"))

            pred = answer_with_channels(uac, q, channels)
            f1 = token_f1(pred, gold)
            jc, jr = judge_answer(q, pred, gold)

            d = {
                "qa_idx": qi,
                "question": q,
                "gold": gold,
                "prediction": pred,
                "f1": f1,
                "judge_correct": bool(jc),
                "judge_reason": jr,
                "category": category,
            }
            prev_details.append(d)
            total_judge.append(1.0 if jc else 0.0)

            judge_acc = sum(1.0 if d["judge_correct"] else 0.0 for d in prev_details) / len(prev_details)
            results["per_conversation"][conv_id] = {
                "n_questions": len(prev_details),
                "judge_accuracy": judge_acc,
            }
            results["details"][conv_id] = prev_details

            with open(out_path, "w") as f:
                json.dump(results, f, indent=2, default=str)

            if qi % 5 == 0 or qi == len(qas) - 1:
                _log(f"    {conv_id} QA {qi+1}/{len(qas)}  judge={'C' if jc else 'W'}  rolling={judge_acc:.3f}")

        uac.reset()

    if total_judge:
        overall = sum(total_judge) / len(total_judge)
        results["aggregate"] = {"judge_accuracy": overall, "n": len(total_judge)}
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        _log(f"\n=== {args.config}: overall judge accuracy = {overall:.3f} (n={len(total_judge)}) ===")


if __name__ == "__main__":
    main()
