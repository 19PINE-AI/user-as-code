#!/usr/bin/env python3
"""Run UaC v5 with GPT-5.4 backbone on the 2-conv LOCOMO subset (120 QAs).

The Gemini-3-Flash judge is reused for fair scoring against the Gemini run.
Resumable; saves to results/locomo_gpt54_uac_v5.json.
"""
from __future__ import annotations
import argparse
import json
import pathlib
import re
import sys
import time
import traceback
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from runner_utils import _log, judge_answer, token_f1  # noqa: E402

DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "benchmarks/locomo/data/locomo10.json"
RESULTS_DIR = pathlib.Path(__file__).resolve().parent / "results"


def get_sessions(conv):
    c = conv["conversation"]
    keys = sorted([k for k in c.keys() if re.match(r"^session_\d+$", k)],
                  key=lambda x: int(x.split("_")[1]))
    return [{"session_id": sk, "date": c.get(f"{sk}_date_time", ""), "turns": c[sk]} for sk in keys]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-qa", type=int, default=60)
    ap.add_argument("--conv-start", type=int, default=0)
    ap.add_argument("--conv-end", type=int, default=2)
    ap.add_argument("--openai-model", type=str, default="gpt-5.4")
    args = ap.parse_args()

    import os
    os.environ["UAC_OPENAI_MODEL"] = args.openai_model

    from user_as_code_v5_openai import UserAsCodeV5OpenAI

    out = RESULTS_DIR / f"locomo_{args.openai_model.replace('.','').replace('-','')}_uac_v5.json"

    if out.exists():
        results = json.load(open(out))
    else:
        results = {
            "system": "uac_v5_gpt54",
            "model": args.openai_model,
            "judge_model": "gemini-3-flash-preview",
            "max_qa_per_conv": args.max_qa,
            "per_conversation": {},
            "details": {},
        }

    with open(DATA_PATH) as f:
        all_convs = json.load(f)
    convs = all_convs[args.conv_start:args.conv_end]

    total_f1, total_judge = [], []
    cat_f1, cat_judge = defaultdict(list), defaultdict(list)

    for ci, conv in enumerate(convs):
        conv_id = conv.get("sample_id", f"conv_{ci}")
        prev_details = results["details"].get(conv_id, [])
        completed_idx = {d["qa_idx"] for d in prev_details}

        if conv_id in results["per_conversation"]:
            pc = results["per_conversation"][conv_id]
            if pc.get("n_questions", 0) >= args.max_qa:
                _log(f"\n=== Conv {conv_id}: SKIP (n={pc['n_questions']}, judge={pc['judge_accuracy']:.3f}) ===")
                for d in prev_details:
                    total_f1.append(d["f1"])
                    total_judge.append(1.0 if d["judge_correct"] else 0.0)
                    cat_f1[d["category"]].append(d["f1"])
                    cat_judge[d["category"]].append(1.0 if d["judge_correct"] else 0.0)
                continue

        _log(f"\n=== Conv {ci} ({conv_id}) [GPT-5.4 UaC v5] ===")
        sessions = get_sessions(conv)
        _log(f"  {len(sessions)} sessions")

        sysobj = UserAsCodeV5OpenAI(user_id=f"locomo_gpt_{conv_id}_{int(time.time())}")
        try:
            t0 = time.time()
            for s in sessions:
                turn_lines = [f"{t['speaker']}: {t['text']}" for t in s["turns"]]
                sysobj.ingest_session(turn_lines, s["session_id"], s["date"])
                _log(f"    GPT-5.4: ingested {s['session_id']}")
            sysobj.structure()
            _log(f"    GPT-5.4: structured ({len(sysobj.code_state)} chars, {len(sysobj.fact_list)} facts) in {time.time()-t0:.1f}s")
        except Exception as e:
            _log(f"  INGEST FAILED: {e}")
            traceback.print_exc()
            try: sysobj.reset()
            except Exception: pass
            continue

        qa_pairs = conv["qa"][:args.max_qa]
        conv_details = list(prev_details)
        conv_f1 = [d["f1"] for d in prev_details]
        conv_judge = [1.0 if d["judge_correct"] else 0.0 for d in prev_details]

        for qi, qa in enumerate(qa_pairs):
            if qi in completed_idx:
                continue
            question = qa["question"]
            gold = str(qa["answer"])
            category = qa.get("category", 0)
            try:
                t0 = time.time()
                pred = sysobj.answer(question)
                dt = time.time() - t0
                f1 = token_f1(pred, gold)
                correct, expl = judge_answer(question, pred, gold)
                d = {
                    "qa_idx": qi,
                    "question": question,
                    "gold": gold,
                    "prediction": pred,
                    "category": category,
                    "f1": f1,
                    "judge_correct": correct,
                    "judge_explanation": expl,
                    "answer_time": dt,
                }
                conv_details.append(d)
                conv_f1.append(f1)
                conv_judge.append(1.0 if correct else 0.0)
                total_f1.append(f1)
                total_judge.append(1.0 if correct else 0.0)
                cat_f1[category].append(f1)
                cat_judge[category].append(1.0 if correct else 0.0)
                status = "OK" if correct else "WR"
                _log(f"    Q{qi+1}/{len(qa_pairs)} cat={category} F1={f1:.2f} J={status} [{dt:.1f}s] {question[:60]}")
            except Exception as e:
                _log(f"    Q{qi+1} ERROR: {e}")
                traceback.print_exc()
                conv_details.append({
                    "qa_idx": qi,
                    "question": question,
                    "gold": gold,
                    "prediction": f"ERROR: {e}",
                    "category": category,
                    "f1": 0.0,
                    "judge_correct": False,
                    "error": str(e),
                })
                conv_f1.append(0.0)
                conv_judge.append(0.0)
                total_f1.append(0.0)
                total_judge.append(0.0)

            if (qi + 1) % 5 == 0:
                results["details"][conv_id] = conv_details
                results["per_conversation"][conv_id] = {
                    "f1": sum(conv_f1)/len(conv_f1) if conv_f1 else 0.0,
                    "judge_accuracy": sum(conv_judge)/len(conv_judge) if conv_judge else 0.0,
                    "n_questions": len(conv_details),
                }
                with open(out, "w") as f:
                    json.dump(results, f, indent=2, default=str)

            time.sleep(0.2)

        results["details"][conv_id] = conv_details
        results["per_conversation"][conv_id] = {
            "f1": sum(conv_f1)/len(conv_f1) if conv_f1 else 0.0,
            "judge_accuracy": sum(conv_judge)/len(conv_judge) if conv_judge else 0.0,
            "n_questions": len(conv_details),
        }
        try: sysobj.reset()
        except Exception: pass
        with open(out, "w") as f:
            json.dump(results, f, indent=2, default=str)
        _log(f"  conv {conv_id} done: F1={results['per_conversation'][conv_id]['f1']:.3f} Judge={results['per_conversation'][conv_id]['judge_accuracy']:.3f}")

    if total_f1:
        results["aggregate"] = {
            "n_total": len(total_f1),
            "f1": sum(total_f1)/len(total_f1),
            "judge_accuracy": sum(total_judge)/len(total_judge),
        }
        results["per_category"] = {
            str(c): {
                "n": len(cat_f1[c]),
                "f1": sum(cat_f1[c])/len(cat_f1[c]),
                "judge_accuracy": sum(cat_judge[c])/len(cat_judge[c]),
            }
            for c in sorted(cat_f1.keys())
        }
    with open(out, "w") as f:
        json.dump(results, f, indent=2, default=str)
    _log(f"\nDONE. n={results.get('aggregate',{}).get('n_total',0)} judge={results.get('aggregate',{}).get('judge_accuracy',0):.3f}")
    _log(f"Saved: {out}")


if __name__ == "__main__":
    main()
