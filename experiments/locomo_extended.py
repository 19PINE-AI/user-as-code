#!/usr/bin/env python3
"""
LOCOMO Extended Evaluation — Conversations 3, 4, 5 (indices 2, 3, 4)
=====================================================================
Runs UaC v5 and Full Context on 3 additional LOCOMO conversations.
Reports Token F1 and LLM-Judge accuracy per conversation and aggregate.
"""

import json
import os
import re
import sys
import time
import random
import traceback
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from google import genai
from google.genai import types

gclient = genai.Client()
MODEL = "gemini-3-flash-preview"

LOCOMO_PATH = Path(__file__).parent.parent / "benchmarks" / "locomo" / "data" / "locomo10.json"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = RESULTS_DIR / "locomo_extended_results.json"

# Conversation indices to evaluate (0-based): we already have 0, 1
CONV_INDICES = [2, 3, 4]
MAX_QAS_PER_CONV = 60


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------

def llm_answer(prompt, system=None):
    """Call Gemini for answering (thinking_budget=2048)."""
    cfg = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=2048),
        temperature=1.0,
    )
    if system:
        cfg.system_instruction = system
    for attempt in range(3):
        try:
            r = gclient.models.generate_content(model=MODEL, contents=prompt, config=cfg)
            return r.text.strip()
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower() or "resource" in str(e).lower():
                wait = 10 * (attempt + 1)
                print(f"    [rate-limit] waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"    [llm_answer error] {e}")
                time.sleep(5)
    return "Error: LLM call failed"


def llm_judge(question, gold, predicted):
    """Call Gemini as judge (thinking_budget=256)."""
    prompt = (
        f"Question: {question}\n"
        f"Gold answer: {gold}\n"
        f"Predicted answer: {predicted}\n\n"
        "Is the predicted answer correct? CORRECT if same core info. "
        "WRONG only if factually wrong or says not available when gold has answer. YES or NO."
    )
    cfg = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=256),
        temperature=1.0,
    )
    for attempt in range(3):
        try:
            r = gclient.models.generate_content(model=MODEL, contents=prompt, config=cfg)
            text = r.text.strip().upper()
            if "YES" in text:
                return True
            return False
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower() or "resource" in str(e).lower():
                wait = 10 * (attempt + 1)
                print(f"    [rate-limit judge] waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"    [judge error] {e}")
                time.sleep(5)
    return False


# ---------------------------------------------------------------------------
# Token F1
# ---------------------------------------------------------------------------

def token_f1(prediction, gold):
    """Compute token-level F1 score."""
    pred_tokens = set(prediction.lower().split())
    gold_tokens = set(gold.lower().split())
    if not gold_tokens:
        return 1.0 if not pred_tokens else 0.0
    if not pred_tokens:
        return 0.0
    common = pred_tokens & gold_tokens
    if not common:
        return 0.0
    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


# ---------------------------------------------------------------------------
# Session extraction helpers
# ---------------------------------------------------------------------------

def get_sessions(conv):
    """Extract sorted sessions from a LOCOMO conversation."""
    c = conv["conversation"]
    sess_keys = sorted(
        [k for k in c.keys() if re.match(r'^session_\d+$', k) and isinstance(c[k], list)],
        key=lambda x: int(x.split('_')[1])
    )
    sessions = []
    for sk in sess_keys:
        date_key = f"{sk}_date_time"
        date = c.get(date_key, "")
        turns = c[sk]
        turn_strs = [f"{t['speaker']}: {t['text']}" for t in turns]
        sessions.append({
            "id": sk,
            "date": date,
            "turns": turn_strs,
            "text": "\n".join(turn_strs),
        })
    return sessions


def get_full_text(conv):
    """Get full conversation text for full-context baseline."""
    sessions = get_sessions(conv)
    return "\n\n".join(f"[{s['id']} - {s['date']}]\n{s['text']}" for s in sessions)


def full_context_answer(all_text, question):
    """Pass all conversation text directly to LLM."""
    text = all_text[:100000] if len(all_text) > 100000 else all_text
    system = (
        "You have access to the full conversation history below. "
        "Use it to answer the question. Give ONLY a concise final answer.\n\n"
        f"{text}"
    )
    return llm_answer(question + "\n\nGive ONLY a concise final answer.", system=system)


# ---------------------------------------------------------------------------
# QA selection (stratified, 60 per conv)
# ---------------------------------------------------------------------------

def select_qas(conv, conv_index, max_qas=60):
    """Select up to max_qas QAs, stratified by category."""
    all_qa = [q for q in conv["qa"] if "answer" in q]
    if len(all_qa) <= max_qas:
        return all_qa

    random.seed(42 + conv_index)
    by_cat = defaultdict(list)
    for q in all_qa:
        by_cat[q["category"]].append(q)

    cats = sorted(by_cat.keys())
    per_cat = {}
    for cat in cats:
        per_cat[cat] = max(1, round(len(by_cat[cat]) / len(all_qa) * max_qas))

    while sum(per_cat.values()) > max_qas:
        biggest = max(cats, key=lambda c: per_cat[c])
        per_cat[biggest] -= 1
    while sum(per_cat.values()) < max_qas:
        biggest = max(cats, key=lambda c: len(by_cat[c]))
        per_cat[biggest] += 1

    selected = []
    for cat in cats:
        pool = by_cat[cat]
        random.shuffle(pool)
        n = min(per_cat.get(cat, 0), len(pool))
        selected.extend(pool[:n])

    random.shuffle(selected)
    return selected[:max_qas]


# ---------------------------------------------------------------------------
# ChromaDB cache clearing
# ---------------------------------------------------------------------------

def clear_chroma_cache():
    """Clear ChromaDB singleton cache to avoid conflicts between v5 instances."""
    try:
        import chromadb.api.client
        chromadb.api.client.SharedSystemClient.clear_system_cache()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Save helper
# ---------------------------------------------------------------------------

def save_results(results_data):
    """Save results to JSON."""
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results_data, f, indent=2, default=str)
    print(f"  Results saved to {OUTPUT_PATH}")


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def main():
    print(f"Loading LOCOMO dataset from {LOCOMO_PATH}")
    with open(LOCOMO_PATH) as f:
        dataset = json.load(f)
    print(f"  {len(dataset)} conversations total")

    # Prepare conversations and QAs
    conv_data = []
    for idx in CONV_INDICES:
        conv = dataset[idx]
        sample_id = conv.get("sample_id", f"conv_{idx}")
        c = conv["conversation"]
        speaker_a = c.get("speaker_a", "Speaker A")
        speaker_b = c.get("speaker_b", "Speaker B")
        sessions = get_sessions(conv)
        qas = select_qas(conv, idx, MAX_QAS_PER_CONV)
        n_turns = sum(len(c[k]) for k in c if re.match(r'^session_\d+$', k) and isinstance(c[k], list))
        print(f"  Conv {idx} ({sample_id}): {speaker_a} & {speaker_b}, "
              f"{len(sessions)} sessions, {n_turns} turns, "
              f"{len(conv['qa'])} total QAs -> selected {len(qas)}")
        cat_counts = Counter(q["category"] for q in qas)
        print(f"    Category distribution: {dict(sorted(cat_counts.items()))}")
        conv_data.append({
            "idx": idx,
            "sample_id": sample_id,
            "conv": conv,
            "sessions": sessions,
            "qas": qas,
        })

    # Results storage
    results = {
        "model": MODEL,
        "timestamp": datetime.now().isoformat(),
        "conversations": [cd["sample_id"] for cd in conv_data],
        "per_conversation": {},
        "aggregate": {},
        "details": [],
    }

    # ── Run each system ──
    for sys_name in ["uac_v5", "full_context"]:
        print(f"\n{'='*70}")
        print(f"  System: {sys_name}")
        print(f"{'='*70}")

        all_preds = []  # list of dicts across all convs

        for cd in conv_data:
            idx = cd["idx"]
            sample_id = cd["sample_id"]
            sessions = cd["sessions"]
            qas = cd["qas"]
            conv = cd["conv"]

            print(f"\n  [{sample_id}] ({len(sessions)} sessions, {len(qas)} QAs)")

            if sys_name == "uac_v5":
                clear_chroma_cache()
                from user_as_code_v5 import UserAsCodeV5
                v5 = UserAsCodeV5(user_id=f"locomo_ext_{idx}")

                # Ingest all sessions
                for s in sessions:
                    print(f"    Ingesting {s['id']} ({s['date']})...")
                    v5.ingest_session(s["turns"], s["id"], s["date"])
                    time.sleep(0.5)

                print(f"    Structuring ({len(v5.fact_list)} facts)...")
                v5.structure()
                time.sleep(1)

                # Answer QAs
                for qi, qa in enumerate(qas):
                    try:
                        pred = v5.answer(qa["question"])
                    except Exception as e:
                        pred = f"Error: {e}"
                        traceback.print_exc()
                    gold = str(qa["answer"])
                    all_preds.append({
                        "system": sys_name,
                        "conv_idx": idx,
                        "sample_id": sample_id,
                        "question": qa["question"],
                        "gold": gold,
                        "predicted": pred,
                        "category": qa["category"],
                    })
                    if (qi + 1) % 10 == 0:
                        print(f"    Answered {qi+1}/{len(qas)}")
                    time.sleep(0.3)

                del v5
                clear_chroma_cache()

            elif sys_name == "full_context":
                full_text = get_full_text(conv)
                print(f"    Full text: {len(full_text)} chars")

                for qi, qa in enumerate(qas):
                    try:
                        pred = full_context_answer(full_text, qa["question"])
                    except Exception as e:
                        pred = f"Error: {e}"
                        traceback.print_exc()
                    gold = str(qa["answer"])
                    all_preds.append({
                        "system": sys_name,
                        "conv_idx": idx,
                        "sample_id": sample_id,
                        "question": qa["question"],
                        "gold": gold,
                        "predicted": pred,
                        "category": qa["category"],
                    })
                    if (qi + 1) % 10 == 0:
                        print(f"    Answered {qi+1}/{len(qas)}")
                    time.sleep(0.3)

        # ── Compute metrics: Token F1 + LLM Judge ──
        print(f"\n  Running LLM Judge for {sys_name} ({len(all_preds)} predictions)...")
        for pi, pred_item in enumerate(all_preds):
            # Token F1
            pred_item["f1"] = token_f1(pred_item["predicted"], pred_item["gold"])

            # LLM Judge
            judge_result = llm_judge(
                pred_item["question"],
                pred_item["gold"],
                pred_item["predicted"],
            )
            pred_item["judge_correct"] = judge_result

            if (pi + 1) % 20 == 0:
                print(f"    Judged {pi+1}/{len(all_preds)}")
            time.sleep(0.1)

        # ── Store results ──
        results["details"].extend(all_preds)

        # Per-conversation metrics
        for cd in conv_data:
            sample_id = cd["sample_id"]
            conv_preds = [p for p in all_preds if p["sample_id"] == sample_id]
            if not conv_preds:
                continue

            key = f"{sys_name}_{sample_id}"
            avg_f1 = sum(p["f1"] for p in conv_preds) / len(conv_preds)
            judge_acc = sum(1 for p in conv_preds if p["judge_correct"]) / len(conv_preds)

            results["per_conversation"][key] = {
                "system": sys_name,
                "sample_id": sample_id,
                "n_qas": len(conv_preds),
                "token_f1": round(avg_f1, 4),
                "judge_accuracy": round(judge_acc, 4),
            }
            print(f"    {sample_id}: F1={avg_f1:.3f}, Judge={judge_acc:.3f} (n={len(conv_preds)})")

        # Aggregate for this system
        if all_preds:
            agg_f1 = sum(p["f1"] for p in all_preds) / len(all_preds)
            agg_judge = sum(1 for p in all_preds if p["judge_correct"]) / len(all_preds)
            results["aggregate"][sys_name] = {
                "n_total": len(all_preds),
                "token_f1": round(agg_f1, 4),
                "judge_accuracy": round(agg_judge, 4),
            }
            print(f"\n  {sys_name} AGGREGATE: F1={agg_f1:.3f}, Judge={agg_judge:.3f} (n={len(all_preds)})")

        # Incremental save after each system
        save_results(results)

    # ── Final summary ──
    print(f"\n{'='*70}")
    print(f"  LOCOMO EXTENDED RESULTS SUMMARY")
    print(f"{'='*70}")
    print(f"\n  {'System':<16} {'Token F1':>10} {'Judge Acc':>10} {'N':>6}")
    print(f"  {'-'*44}")
    for sys_name in ["uac_v5", "full_context"]:
        if sys_name in results["aggregate"]:
            agg = results["aggregate"][sys_name]
            print(f"  {sys_name:<16} {agg['token_f1']:>10.4f} {agg['judge_accuracy']:>10.4f} {agg['n_total']:>6}")

    print(f"\n  Per-conversation breakdown:")
    print(f"  {'Key':<35} {'F1':>8} {'Judge':>8} {'N':>5}")
    print(f"  {'-'*58}")
    for key in sorted(results["per_conversation"].keys()):
        pc = results["per_conversation"][key]
        print(f"  {key:<35} {pc['token_f1']:>8.4f} {pc['judge_accuracy']:>8.4f} {pc['n_qas']:>5}")

    print(f"\n  Results saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
