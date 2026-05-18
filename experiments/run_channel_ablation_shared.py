#!/usr/bin/env python3
"""Retrieval-channel ablation for UaC v5, sharing ingestion across configs.

For each of the 5 LOCOMO conversations, ingest+structure ONCE, then for each
of the 3 leave-one-out channel configurations answer all 60 QAs.

Resumable per (config, conv_id, qa_idx). Writes 3 result files,
locomo5_uac_v5_ablate_{no_state,no_facts,no_archive}.json, after every QA.
"""
from __future__ import annotations
import json
import pathlib
import re
import sys
import time

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


def retrieve_with_channels(uac, query, *, use_state, use_facts, use_archive, top_k_archive=10):
    parts = []
    if use_state and uac.code_state and not uac._code_stale:
        code = uac.code_state
        if len(code) > 6000:
            code = code[:6000] + "\n# ... (truncated)"
        parts.append("=== Structured User State (Python) ===")
        parts.append(code)

    if use_facts and uac._facts_db.count() > 0:
        try:
            r = uac._facts_db.query(query_texts=[query],
                                    n_results=min(20, uac._facts_db.count()))
            if r["documents"][0]:
                parts.append("\n=== Relevant Facts ===")
                for doc in r["documents"][0]:
                    parts.append(f"- {doc}")
        except Exception:
            pass

    if use_archive and uac._archive.count() > 0:
        try:
            r = uac._archive.query(query_texts=[query],
                                   n_results=min(top_k_archive, uac._archive.count()))
            if r["documents"][0]:
                parts.append("\n=== Conversation Excerpts ===")
                seen = set()
                for doc in r["documents"][0]:
                    key = doc[:80]
                    if key not in seen:
                        seen.add(key)
                        parts.append(doc)
        except Exception:
            pass
    return "\n\n".join(parts)


def answer_with_channels(uac, question, channels):
    context = retrieve_with_channels(
        uac, question,
        use_state=channels["state"], use_facts=channels["facts"], use_archive=channels["archive"],
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
            thinking_budget=2048, temperature=1.0,
        )
        return extract_concise(out)
    except Exception as e:
        return f"Error: {e}"


def get_sessions(conv):
    c = conv["conversation"]
    keys = sorted([k for k in c.keys() if re.match(r"^session_\d+$", k)],
                  key=lambda x: int(x.split("_")[1]))
    return [{"session_id": sk, "date": c.get(f"{sk}_date_time", ""), "turns": c[sk]} for sk in keys]


def load_results(config: str):
    out_path = RESULTS_DIR / f"locomo5_uac_v5_ablate_{config}.json"
    if out_path.exists():
        with open(out_path) as f:
            return out_path, json.load(f)
    return out_path, {
        "system": f"uac_v5_ablate_{config}",
        "channels": CHANNEL_CONFIGS[config],
        "model": GEMINI_MODEL,
        "max_qa_per_conv": 60,
        "per_conversation": {},
        "details": {},
    }


def save_results(out_path, results):
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)


def all_done(results, conv_id, max_qa):
    pc = results["per_conversation"].get(conv_id, {})
    return pc.get("n_questions", 0) >= max_qa


def main():
    max_qa = 60
    conv_start, conv_end = 0, 5

    # Load all 3 result files
    out_paths = {}
    results_all = {}
    for cfg in CHANNEL_CONFIGS:
        op, res = load_results(cfg)
        out_paths[cfg] = op
        results_all[cfg] = res

    with open(DATA_PATH) as f:
        all_convs = json.load(f)
    convs = all_convs[conv_start:conv_end]

    for ci, conv in enumerate(convs):
        conv_id = conv.get("sample_id", f"conv_{ci}")

        # Skip ingestion if all 3 configs are already done for this conv
        if all(all_done(results_all[cfg], conv_id, max_qa) for cfg in CHANNEL_CONFIGS):
            _log(f"\n=== Conv {conv_id}: SKIP (all 3 configs already complete) ===")
            continue

        _log(f"\n=== Conv {ci} ({conv_id}): ingesting once for all configs ===")
        sessions = get_sessions(conv)
        uac = UserAsCodeV5(user_id=f"locomo5_ablate_shared_{conv_id}_{int(time.time())}")
        for s in sessions:
            turn_lines = [f"{t['speaker']}: {t['text']}" for t in s["turns"]]
            uac.ingest_session(turn_lines, s["session_id"], s["date"])
        uac.structure()
        _log(f"  structured ({len(uac.code_state)} chars), facts={len(uac.fact_list)}")

        qas = conv["qa"][:max_qa]
        for cfg, channels in CHANNEL_CONFIGS.items():
            results = results_all[cfg]
            out_path = out_paths[cfg]
            prev_details = results["details"].get(conv_id, [])
            completed_idx = {d["qa_idx"] for d in prev_details}

            if len(prev_details) >= max_qa:
                _log(f"  [{cfg}] already complete ({len(prev_details)} QAs)")
                continue

            _log(f"  [{cfg}] starting from {len(prev_details)}/{max_qa}")
            for qi, qa in enumerate(qas):
                if qi in completed_idx:
                    continue
                q = qa.get("question", "")
                gold = str(qa.get("answer", ""))
                cat = str(qa.get("category", "uncategorized"))
                pred = answer_with_channels(uac, q, channels)
                f1 = token_f1(pred, gold)
                jc, jr = judge_answer(q, pred, gold)
                prev_details.append({
                    "qa_idx": qi, "question": q, "gold": gold,
                    "prediction": pred, "f1": f1, "judge_correct": bool(jc),
                    "judge_reason": jr, "category": cat,
                })
                acc = sum(1.0 if d["judge_correct"] else 0.0 for d in prev_details) / len(prev_details)
                results["per_conversation"][conv_id] = {"n_questions": len(prev_details),
                                                       "judge_accuracy": acc}
                results["details"][conv_id] = prev_details
                save_results(out_path, results)
                if qi % 10 == 0 or qi == len(qas) - 1:
                    _log(f"    [{cfg}] {conv_id} QA {qi+1}/{len(qas)}  judge={'C' if jc else 'W'}  rolling={acc:.3f}")
            _log(f"  [{cfg}] {conv_id} done: {acc:.3f}")

        try:
            uac.reset()
        except Exception:
            pass

    # Aggregate
    for cfg in CHANNEL_CONFIGS:
        results = results_all[cfg]
        total = []
        for conv_id, recs in results["details"].items():
            for r in recs:
                total.append(1.0 if r["judge_correct"] else 0.0)
        if total:
            results["aggregate"] = {"judge_accuracy": sum(total) / len(total), "n": len(total)}
        save_results(out_paths[cfg], results)
        _log(f"[FINAL] {cfg}: overall = {results.get('aggregate', {}).get('judge_accuracy', 0):.3f} "
             f"(n={results.get('aggregate', {}).get('n', 0)})")


if __name__ == "__main__":
    main()
