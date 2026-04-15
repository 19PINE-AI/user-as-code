#!/usr/bin/env python3
"""
Final Full Evaluation Suite for User as Code Paper
===================================================
Runs all 3 benchmarks (LOCOMO, LongMemEval, Active Service) across all systems.
Outputs: experiments/results/final_full_evaluation.json
"""

import json
import os
import re
import sys
import time
import random
import pathlib
import traceback
from collections import defaultdict, Counter
from datetime import datetime

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE = "/Users/boj/UserAsCode"
LOCOMO_PATH = f"{BASE}/benchmarks/locomo/data/locomo10.json"
LME_PATH = f"{BASE}/benchmarks/longmemeval/data/longmemeval_oracle.json"
ACTIVE_PATH = f"{BASE}/evaluation/active_service_scenarios.json"
OUTPUT_PATH = f"{BASE}/experiments/results/final_full_evaluation.json"

sys.path.insert(0, f"{BASE}/experiments")

# ─── LLM Client (Gemini 3 Flash) ─────────────────────────────────────────────
from google import genai
gclient = genai.Client()
GEMINI_MODEL = "gemini-3-flash-preview"

def llm_answer(prompt, system=None):
    """Call Gemini for answering (thinking_budget=2048)."""
    cfg = genai.types.GenerateContentConfig(
        thinking_config=genai.types.ThinkingConfig(thinking_budget=2048),
        temperature=1.0,
    )
    if system:
        cfg.system_instruction = system
    for attempt in range(3):
        try:
            r = gclient.models.generate_content(model=GEMINI_MODEL, contents=prompt, config=cfg)
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
    cfg = genai.types.GenerateContentConfig(
        thinking_config=genai.types.ThinkingConfig(thinking_budget=256),
        temperature=1.0,
    )
    for attempt in range(3):
        try:
            r = gclient.models.generate_content(model=GEMINI_MODEL, contents=prompt, config=cfg)
            text = r.text.strip().upper()
            # Extract YES/NO
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

# ─── Token F1 ────────────────────────────────────────────────────────────────
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


# ─── ChromaDB Cache Clearing ──────────────────────────────────────────────────
def clear_chroma_cache():
    """Clear ChromaDB singleton cache to avoid conflicts between systems."""
    try:
        import chromadb.api.client
        chromadb.api.client.SharedSystemClient.clear_system_cache()
    except Exception:
        pass

# ─── Mem0 Lock Cleaning ──────────────────────────────────────────────────────
def clean_mem0_locks():
    """Clean Qdrant locks before Mem0 operations."""
    locks = [
        pathlib.Path('/tmp/qdrant/.lock'),
        pathlib.Path.home() / '.mem0' / 'migrations_qdrant' / '.lock',
    ]
    for p in locks:
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass


# ─── Full Context Baseline ────────────────────────────────────────────────────
def full_context_answer(all_text, question):
    """Pass all conversation text directly to LLM."""
    # Truncate to ~100K chars if needed
    text = all_text[:100000] if len(all_text) > 100000 else all_text
    system = (
        "You have access to the full conversation history below. "
        "Use it to answer the question. Give ONLY a concise final answer.\n\n"
        f"{text}"
    )
    return llm_answer(question + "\n\nGive ONLY a concise final answer.", system=system)


# ═══════════════════════════════════════════════════════════════════════════════
# BENCHMARK 1: LOCOMO
# ═══════════════════════════════════════════════════════════════════════════════
def run_locomo():
    print("\n" + "=" * 70)
    print("BENCHMARK 1: LOCOMO (2 conversations, 60 QAs each)")
    print("=" * 70)

    data = json.load(open(LOCOMO_PATH))
    results = {}

    # Prepare conversations: take first 2
    convs = data[:2]

    # For each conversation, select 60 QAs (stratified by category)
    conv_qas = []
    for ci, conv in enumerate(convs):
        # Only use QAs that have an 'answer' key (skip adversarial-only)
        all_qa = [q for q in conv["qa"] if "answer" in q]
        print(f"  Conv {ci}: {len(conv['qa'])} total QAs, {len(all_qa)} with answer key")
        # Stratified sampling: proportional to category distribution
        random.seed(42 + ci)
        by_cat = defaultdict(list)
        for q in all_qa:
            by_cat[q["category"]].append(q)
        selected = []
        total_needed = 60
        cats = sorted(by_cat.keys())
        # Proportional allocation
        per_cat = {}
        for cat in cats:
            per_cat[cat] = max(1, round(len(by_cat[cat]) / len(all_qa) * total_needed))
        # Adjust to exactly 60
        while sum(per_cat.values()) > total_needed:
            biggest = max(cats, key=lambda c: per_cat[c])
            per_cat[biggest] -= 1
        while sum(per_cat.values()) < total_needed:
            biggest = max(cats, key=lambda c: len(by_cat[c]))
            per_cat[biggest] += 1

        for cat in cats:
            pool = by_cat[cat]
            random.shuffle(pool)
            n = min(per_cat.get(cat, 0), len(pool))
            selected.extend(pool[:n])

        random.shuffle(selected)
        conv_qas.append(selected[:60])
        print(f"  Conv {ci}: {len(conv['qa'])} total QAs, selected {len(conv_qas[-1])}")
        cat_counts = Counter(q["category"] for q in conv_qas[-1])
        print(f"    Category distribution: {dict(sorted(cat_counts.items()))}")

    # ── Helper: prepare sessions for a conversation ──
    def get_sessions(conv):
        """Extract sorted sessions from a LOCOMO conversation."""
        c = conv["conversation"]
        sess_keys = sorted(
            [k for k in c.keys() if re.match(r'^session_\d+$', k)],
            key=lambda x: int(x.split('_')[1])
        )
        sessions = []
        for sk in sess_keys:
            date_key = f"{sk}_date_time"
            date = c.get(date_key, "")
            turns = c[sk]  # list of {"speaker":..., "dia_id":..., "text":...}
            turn_strs = [f"{t['speaker']}: {t['text']}" for t in turns]
            sessions.append({
                "id": sk,
                "date": date,
                "turns": turn_strs,
                "text": "\n".join(turn_strs),
            })
        return sessions

    def get_full_text(conv):
        sessions = get_sessions(conv)
        return "\n\n".join(f"[{s['id']} - {s['date']}]\n{s['text']}" for s in sessions)

    # ── Run each system ──
    systems_to_run = ["uac_v5", "uac_v2", "full_context", "amem", "mem0"]

    for sys_name in systems_to_run:
        clear_chroma_cache()
        print(f"\n--- Running {sys_name} on LOCOMO ---")
        all_preds = []

        for ci, conv in enumerate(convs):
            sessions = get_sessions(conv)
            qas = conv_qas[ci]
            print(f"  Conv {ci}: ingesting {len(sessions)} sessions...")

            if sys_name == "uac_v5":
                from user_as_code_v5 import UserAsCodeV5
                v5 = UserAsCodeV5(user_id=f"locomo_{ci}")
                for s in sessions:
                    print(f"    Ingesting {s['id']} ({s['date']})...")
                    v5.ingest_session(s["turns"], s["id"], s["date"])
                    time.sleep(0.5)
                print(f"    Structuring...")
                v5.structure()
                time.sleep(1)
                for qi, qa in enumerate(qas):
                    try:
                        pred = v5.answer(qa["question"])
                    except Exception as e:
                        pred = f"Error: {e}"
                        traceback.print_exc()
                    all_preds.append({
                        "conv": ci, "question": qa["question"],
                        "gold": str(qa["answer"]), "predicted": pred,
                        "category": qa["category"],
                    })
                    if (qi + 1) % 10 == 0:
                        print(f"    Answered {qi+1}/{len(qas)}")
                    time.sleep(0.3)
                del v5

            elif sys_name == "uac_v2":
                from user_as_code_v2 import UserAsCodeV2
                v2 = UserAsCodeV2(user_id=f"locomo_{ci}")
                for s in sessions:
                    print(f"    Ingesting {s['id']} ({s['date']})...")
                    v2.ingest_session(s["turns"], s["id"], s["date"])
                    time.sleep(0.5)
                for qi, qa in enumerate(qas):
                    try:
                        pred = v2.answer(qa["question"])
                    except Exception as e:
                        pred = f"Error: {e}"
                        traceback.print_exc()
                    all_preds.append({
                        "conv": ci, "question": qa["question"],
                        "gold": str(qa["answer"]), "predicted": pred,
                        "category": qa["category"],
                    })
                    if (qi + 1) % 10 == 0:
                        print(f"    Answered {qi+1}/{len(qas)}")
                    time.sleep(0.3)
                del v2

            elif sys_name == "full_context":
                full_text = get_full_text(conv)
                for qi, qa in enumerate(qas):
                    try:
                        pred = full_context_answer(full_text, qa["question"])
                    except Exception as e:
                        pred = f"Error: {e}"
                        traceback.print_exc()
                    all_preds.append({
                        "conv": ci, "question": qa["question"],
                        "gold": str(qa["answer"]), "predicted": pred,
                        "category": qa["category"],
                    })
                    if (qi + 1) % 10 == 0:
                        print(f"    Answered {qi+1}/{len(qas)}")
                    time.sleep(0.3)

            elif sys_name == "amem":
                # Clear ChromaDB singleton cache to avoid conflicts
                try:
                    import chromadb.api.client
                    chromadb.api.client.SharedSystemClient.clear_system_cache()
                except Exception:
                    pass
                from agentic_memory.memory_system import AgenticMemorySystem
                amem = AgenticMemorySystem(
                    model_name='all-MiniLM-L6-v2',
                    llm_backend="openai",
                    llm_model="gpt-4o-mini",
                )
                for s in sessions:
                    text_chunk = f"[{s['date']}] {s['text']}"
                    # Split into chunks of ~2000 chars for note storage
                    for j in range(0, len(text_chunk), 2000):
                        chunk = text_chunk[j:j+2000]
                        try:
                            amem.add_note(chunk)
                        except Exception as e:
                            print(f"    [amem add_note error] {e}")
                    time.sleep(0.2)
                print(f"    Ingested. Answering {len(qas)} questions...")
                for qi, qa in enumerate(qas):
                    try:
                        results_list = amem.search_agentic(qa["question"], k=10)
                        context = "\n".join(str(r) for r in results_list) if results_list else "No relevant information found."
                        pred = llm_answer(
                            qa["question"] + "\n\nGive ONLY a concise final answer.",
                            system=f"Use the following retrieved information to answer:\n\n{context}"
                        )
                    except Exception as e:
                        pred = f"Error: {e}"
                        traceback.print_exc()
                    all_preds.append({
                        "conv": ci, "question": qa["question"],
                        "gold": str(qa["answer"]), "predicted": pred,
                        "category": qa["category"],
                    })
                    if (qi + 1) % 10 == 0:
                        print(f"    Answered {qi+1}/{len(qas)}")
                    time.sleep(0.3)
                del amem
                # Clear cache after A-MEM too
                try:
                    chromadb.api.client.SharedSystemClient.clear_system_cache()
                except Exception:
                    pass

            elif sys_name == "mem0":
                # Clear ChromaDB singleton cache to avoid conflicts
                try:
                    import chromadb.api.client
                    chromadb.api.client.SharedSystemClient.clear_system_cache()
                except Exception:
                    pass
                clean_mem0_locks()
                time.sleep(2)
                from mem0 import Memory
                m0 = Memory()
                user_id = f"locomo_{ci}"
                for s in sessions:
                    text_chunk = f"[{s['date']}] {s['text']}"
                    for j in range(0, len(text_chunk), 2000):
                        chunk = text_chunk[j:j+2000]
                        try:
                            m0.add(chunk, user_id=user_id)
                        except Exception as e:
                            print(f"    [mem0 add error] {e}")
                    time.sleep(0.2)
                print(f"    Ingested. Answering {len(qas)} questions...")
                for qi, qa in enumerate(qas):
                    try:
                        search_results = m0.search(qa["question"], user_id=user_id)
                        if isinstance(search_results, dict) and "results" in search_results:
                            entries = search_results["results"]
                        elif isinstance(search_results, list):
                            entries = search_results
                        else:
                            entries = []
                        context = "\n".join(
                            e.get("memory", str(e)) if isinstance(e, dict) else str(e)
                            for e in entries[:10]
                        ) if entries else "No relevant information found."
                        pred = llm_answer(
                            qa["question"] + "\n\nGive ONLY a concise final answer.",
                            system=f"Use the following retrieved information to answer:\n\n{context}"
                        )
                    except Exception as e:
                        pred = f"Error: {e}"
                        traceback.print_exc()
                    all_preds.append({
                        "conv": ci, "question": qa["question"],
                        "gold": str(qa["answer"]), "predicted": pred,
                        "category": qa["category"],
                    })
                    if (qi + 1) % 10 == 0:
                        print(f"    Answered {qi+1}/{len(qas)}")
                    time.sleep(0.3)
                del m0
                clean_mem0_locks()
                try:
                    chromadb.api.client.SharedSystemClient.clear_system_cache()
                except Exception:
                    pass

        # ── Compute metrics ──
        f1_scores = []
        judge_scores = []
        per_cat_f1 = defaultdict(list)
        per_cat_judge = defaultdict(list)

        for p in all_preds:
            f1 = token_f1(p["predicted"], p["gold"])
            judge = llm_judge(p["question"], p["gold"], p["predicted"])
            f1_scores.append(f1)
            judge_scores.append(judge)
            per_cat_f1[p["category"]].append(f1)
            per_cat_judge[p["category"]].append(judge)
            time.sleep(0.2)

        avg_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0
        avg_judge = sum(judge_scores) / len(judge_scores) if judge_scores else 0

        per_cat = {}
        for cat in sorted(per_cat_f1.keys()):
            cf1 = per_cat_f1[cat]
            cj = per_cat_judge[cat]
            per_cat[f"cat_{cat}"] = {
                "f1": round(sum(cf1) / len(cf1), 4) if cf1 else 0,
                "judge": round(sum(cj) / len(cj), 4) if cj else 0,
                "n": len(cf1),
            }

        results[sys_name] = {
            "f1": round(avg_f1, 4),
            "judge": round(avg_judge, 4),
            "n": len(all_preds),
            "per_category": per_cat,
            "predictions": all_preds,
        }

        print(f"\n  {sys_name}: F1={avg_f1:.4f}, Judge={avg_judge:.4f} (n={len(all_preds)})")
        for cat, vals in sorted(per_cat.items()):
            print(f"    {cat}: F1={vals['f1']:.4f}, Judge={vals['judge']:.4f} (n={vals['n']})")

    # ── Summary table ──
    print("\n" + "=" * 70)
    print("LOCOMO RESULTS SUMMARY")
    print("=" * 70)
    print(f"{'System':<15} {'F1':>8} {'Judge':>8} {'N':>5}")
    print("-" * 40)
    for sys_name in systems_to_run:
        r = results[sys_name]
        print(f"{sys_name:<15} {r['f1']:>8.4f} {r['judge']:>8.4f} {r['n']:>5}")

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# BENCHMARK 2: LongMemEval
# ═══════════════════════════════════════════════════════════════════════════════
def run_longmemeval():
    print("\n" + "=" * 70)
    print("BENCHMARK 2: LongMemEval (48 stratified questions)")
    print("=" * 70)

    data = json.load(open(LME_PATH))
    results = {}

    # Stratified sampling: 8 per question type
    random.seed(42)
    by_type = defaultdict(list)
    for q in data:
        by_type[q["question_type"]].append(q)

    selected = []
    for qtype in sorted(by_type.keys()):
        pool = by_type[qtype]
        random.shuffle(pool)
        selected.extend(pool[:8])
    random.shuffle(selected)

    print(f"  Selected {len(selected)} questions across {len(by_type)} types:")
    type_counts = Counter(q["question_type"] for q in selected)
    for t, c in sorted(type_counts.items()):
        print(f"    {t}: {c}")

    systems_to_run = ["uac_v5", "uac_v2", "full_context", "amem", "mem0"]

    for sys_name in systems_to_run:
        clear_chroma_cache()
        print(f"\n--- Running {sys_name} on LongMemEval ---")
        all_preds = []

        for qi, q in enumerate(selected):
            question = q["question"]
            gold = str(q["answer"])
            sessions = q["haystack_sessions"]
            dates = q.get("haystack_dates", [])
            session_ids = q.get("haystack_session_ids", [])

            try:
                if sys_name == "uac_v5":
                    from user_as_code_v5 import UserAsCodeV5
                    v5 = UserAsCodeV5(user_id=f"lme_{qi}")
                    for si, sess in enumerate(sessions):
                        sid = session_ids[si] if si < len(session_ids) else f"session_{si}"
                        date = dates[si] if si < len(dates) else ""
                        turns = [f"{msg['role']}: {msg['content']}" for msg in sess]
                        v5.ingest_session(turns, sid, date)
                        time.sleep(0.3)
                    v5.structure()
                    time.sleep(0.5)
                    pred = v5.answer(question)
                    del v5

                elif sys_name == "uac_v2":
                    from user_as_code_v2 import UserAsCodeV2
                    v2 = UserAsCodeV2(user_id=f"lme_{qi}")
                    for si, sess in enumerate(sessions):
                        sid = session_ids[si] if si < len(session_ids) else f"session_{si}"
                        date = dates[si] if si < len(dates) else ""
                        turns = [f"{msg['role']}: {msg['content']}" for msg in sess]
                        v2.ingest_session(turns, sid, date)
                        time.sleep(0.3)
                    pred = v2.answer(question)
                    del v2

                elif sys_name == "full_context":
                    all_text = ""
                    for si, sess in enumerate(sessions):
                        date = dates[si] if si < len(dates) else ""
                        session_text = "\n".join(f"{msg['role']}: {msg['content']}" for msg in sess)
                        all_text += f"\n\n[Session {si+1} - {date}]\n{session_text}"
                    pred = full_context_answer(all_text, question)

                elif sys_name == "amem":
                    try:
                        import chromadb.api.client
                        chromadb.api.client.SharedSystemClient.clear_system_cache()
                    except Exception:
                        pass
                    from agentic_memory.memory_system import AgenticMemorySystem
                    amem = AgenticMemorySystem(
                        model_name='all-MiniLM-L6-v2',
                        llm_backend="openai",
                        llm_model="gpt-4o-mini",
                    )
                    for si, sess in enumerate(sessions):
                        date = dates[si] if si < len(dates) else ""
                        session_text = f"[{date}] " + "\n".join(f"{msg['role']}: {msg['content']}" for msg in sess)
                        for j in range(0, len(session_text), 2000):
                            try:
                                amem.add_note(session_text[j:j+2000])
                            except Exception:
                                pass
                    results_list = amem.search_agentic(question, k=10)
                    context = "\n".join(str(r) for r in results_list) if results_list else "No relevant info."
                    pred = llm_answer(
                        question + "\n\nGive ONLY a concise final answer.",
                        system=f"Use the following retrieved information to answer:\n\n{context}"
                    )
                    del amem
                    try:
                        chromadb.api.client.SharedSystemClient.clear_system_cache()
                    except Exception:
                        pass

                elif sys_name == "mem0":
                    try:
                        import chromadb.api.client
                        chromadb.api.client.SharedSystemClient.clear_system_cache()
                    except Exception:
                        pass
                    clean_mem0_locks()
                    time.sleep(1)
                    from mem0 import Memory
                    m0 = Memory()
                    uid = f"lme_{qi}"
                    for si, sess in enumerate(sessions):
                        date = dates[si] if si < len(dates) else ""
                        session_text = f"[{date}] " + "\n".join(f"{msg['role']}: {msg['content']}" for msg in sess)
                        for j in range(0, len(session_text), 2000):
                            try:
                                m0.add(session_text[j:j+2000], user_id=uid)
                            except Exception:
                                pass
                    search_results = m0.search(question, user_id=uid)
                    if isinstance(search_results, dict) and "results" in search_results:
                        entries = search_results["results"]
                    elif isinstance(search_results, list):
                        entries = search_results
                    else:
                        entries = []
                    context = "\n".join(
                        e.get("memory", str(e)) if isinstance(e, dict) else str(e)
                        for e in entries[:10]
                    ) if entries else "No relevant info."
                    pred = llm_answer(
                        question + "\n\nGive ONLY a concise final answer.",
                        system=f"Use the following retrieved information to answer:\n\n{context}"
                    )
                    del m0
                    clean_mem0_locks()
                    try:
                        chromadb.api.client.SharedSystemClient.clear_system_cache()
                    except Exception:
                        pass

            except Exception as e:
                pred = f"Error: {e}"
                traceback.print_exc()

            all_preds.append({
                "question_id": q.get("question_id", qi),
                "question_type": q["question_type"],
                "question": question,
                "gold": gold,
                "predicted": pred,
            })
            if (qi + 1) % 8 == 0:
                print(f"    Answered {qi+1}/{len(selected)}")
            time.sleep(0.3)

        # ── Compute metrics (LLM-Judge only) ──
        judge_scores = []
        per_type_judge = defaultdict(list)

        for p in all_preds:
            judge = llm_judge(p["question"], p["gold"], p["predicted"])
            judge_scores.append(judge)
            per_type_judge[p["question_type"]].append(judge)
            time.sleep(0.2)

        avg_judge = sum(judge_scores) / len(judge_scores) if judge_scores else 0

        per_type = {}
        for t in sorted(per_type_judge.keys()):
            scores = per_type_judge[t]
            per_type[t] = {
                "accuracy": round(sum(scores) / len(scores), 4) if scores else 0,
                "n": len(scores),
            }

        results[sys_name] = {
            "accuracy": round(avg_judge, 4),
            "n": len(all_preds),
            "per_type": per_type,
            "predictions": all_preds,
        }

        print(f"\n  {sys_name}: Accuracy={avg_judge:.4f} (n={len(all_preds)})")
        for t, vals in sorted(per_type.items()):
            print(f"    {t}: {vals['accuracy']:.4f} (n={vals['n']})")

    # ── Summary table ──
    print("\n" + "=" * 70)
    print("LONGMEMEVAL RESULTS SUMMARY")
    print("=" * 70)
    print(f"{'System':<15} {'Accuracy':>10} {'N':>5}")
    print("-" * 35)
    for sys_name in systems_to_run:
        r = results[sys_name]
        print(f"{sys_name:<15} {r['accuracy']:>10.4f} {r['n']:>5}")

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# BENCHMARK 3: Active Service
# ═══════════════════════════════════════════════════════════════════════════════
def check_alert(response, expected_alert):
    """Check if the response contains an alert matching expected.
    Criteria: keyword overlap >= 0.2 AND alert language present."""
    resp_lower = response.lower()

    # Check for alert language
    alert_indicators = [
        "alert", "warning", "caution", "flag", "attention", "important",
        "notice", "concern", "issue", "problem", "risk", "danger",
        "expires", "expired", "conflict", "violation", "incompatible",
        "interaction", "deadline", "urgent", "critical",
    ]
    has_alert_language = any(ind in resp_lower for ind in alert_indicators)

    if not has_alert_language:
        return False

    # Keyword overlap with expected alert message
    expected_msg = expected_alert.get("message", "")
    expected_tokens = set(re.findall(r'\w+', expected_msg.lower()))
    response_tokens = set(re.findall(r'\w+', resp_lower))

    if not expected_tokens:
        return has_alert_language

    overlap = len(expected_tokens & response_tokens) / len(expected_tokens)
    return overlap >= 0.2


def run_active_service():
    print("\n" + "=" * 70)
    print("BENCHMARK 3: Active Service (40 scenarios)")
    print("=" * 70)

    raw = json.load(open(ACTIVE_PATH))
    scenarios = raw["scenarios"]
    results = {}

    print(f"  Loaded {len(scenarios)} scenarios")

    systems_to_run = ["uac_v5_with_alerts", "uac_v5_no_alerts", "amem", "mem0"]

    for sys_name in systems_to_run:
        clear_chroma_cache()
        print(f"\n--- Running {sys_name} on Active Service ---")
        alerts_detected = []

        for si, scenario in enumerate(scenarios):
            sessions = scenario["sessions"]
            trigger_id = scenario["trigger_session"]["session_id"]
            expected = scenario["expected_alert"]

            try:
                if sys_name in ("uac_v5_with_alerts", "uac_v5_no_alerts"):
                    from user_as_code_v5 import UserAsCodeV5
                    v5 = UserAsCodeV5(user_id=f"active_{si}")

                    # Ingest all sessions
                    for sess in sessions:
                        turns = sess["conversation"].split("\n")
                        v5.ingest_session(turns, f"session_{sess['session_id']}", sess.get("timestamp", ""))
                        time.sleep(0.3)

                    v5.structure()
                    time.sleep(0.5)

                    # Find trigger session
                    trigger_text = ""
                    for sess in sessions:
                        if sess["session_id"] == trigger_id:
                            trigger_text = sess["conversation"]
                            break

                    if sys_name == "uac_v5_with_alerts":
                        # With constraint pipeline: ask explicitly about alerts
                        context = v5.retrieve(trigger_text)
                        prompt = (
                            f"A user just had this conversation:\n{trigger_text}\n\n"
                            f"Based on everything you know about this user from their history, "
                            f"are there any alerts, warnings, or concerns you should raise? "
                            f"Check for: document expirations, health interactions, scheduling conflicts, "
                            f"financial issues, travel requirements, or any other constraints that may be violated.\n\n"
                            f"If there are concerns, describe them clearly with specific details and dates."
                        )
                        response = llm_answer(prompt, system=f"User history:\n{context}")
                    else:
                        # Without alerts: just neutral response
                        response = v5.answer(
                            f"What should I know about this conversation? {trigger_text[:500]}"
                        )
                    del v5

                elif sys_name == "amem":
                    try:
                        import chromadb.api.client
                        chromadb.api.client.SharedSystemClient.clear_system_cache()
                    except Exception:
                        pass
                    from agentic_memory.memory_system import AgenticMemorySystem
                    amem = AgenticMemorySystem(
                        model_name='all-MiniLM-L6-v2',
                        llm_backend="openai",
                        llm_model="gpt-4o-mini",
                    )
                    for sess in sessions:
                        try:
                            amem.add_note(f"[{sess.get('timestamp','')}] {sess['conversation']}")
                        except Exception:
                            pass
                    trigger_text = ""
                    for sess in sessions:
                        if sess["session_id"] == trigger_id:
                            trigger_text = sess["conversation"]
                            break
                    results_list = amem.search_agentic(trigger_text, k=10)
                    context = "\n".join(str(r) for r in results_list) if results_list else ""
                    response = llm_answer(
                        f"The user just said:\n{trigger_text}\n\nBased on retrieved info, respond helpfully.",
                        system=f"Retrieved information:\n{context}"
                    )
                    del amem
                    try:
                        chromadb.api.client.SharedSystemClient.clear_system_cache()
                    except Exception:
                        pass

                elif sys_name == "mem0":
                    try:
                        import chromadb.api.client
                        chromadb.api.client.SharedSystemClient.clear_system_cache()
                    except Exception:
                        pass
                    clean_mem0_locks()
                    time.sleep(1)
                    from mem0 import Memory
                    m0 = Memory()
                    uid = f"active_{si}"
                    for sess in sessions:
                        try:
                            m0.add(f"[{sess.get('timestamp','')}] {sess['conversation']}", user_id=uid)
                        except Exception:
                            pass
                    trigger_text = ""
                    for sess in sessions:
                        if sess["session_id"] == trigger_id:
                            trigger_text = sess["conversation"]
                            break
                    search_results = m0.search(trigger_text, user_id=uid)
                    if isinstance(search_results, dict) and "results" in search_results:
                        entries = search_results["results"]
                    elif isinstance(search_results, list):
                        entries = search_results
                    else:
                        entries = []
                    context = "\n".join(
                        e.get("memory", str(e)) if isinstance(e, dict) else str(e)
                        for e in entries[:10]
                    ) if entries else ""
                    response = llm_answer(
                        f"The user just said:\n{trigger_text}\n\nBased on retrieved info, respond helpfully.",
                        system=f"Retrieved information:\n{context}"
                    )
                    del m0
                    clean_mem0_locks()
                    try:
                        chromadb.api.client.SharedSystemClient.clear_system_cache()
                    except Exception:
                        pass

            except Exception as e:
                response = f"Error: {e}"
                traceback.print_exc()

            detected = check_alert(response, expected)
            alerts_detected.append({
                "scenario_id": scenario["id"],
                "category": scenario["category"],
                "detected": detected,
                "response": response[:500],
                "expected": expected["message"][:200],
            })

            if (si + 1) % 10 == 0:
                print(f"    Processed {si+1}/{len(scenarios)}")
            time.sleep(0.3)

        # ── Metrics ──
        rate = sum(1 for a in alerts_detected if a["detected"]) / len(alerts_detected) if alerts_detected else 0

        # Per-category
        per_cat = defaultdict(list)
        for a in alerts_detected:
            per_cat[a["category"]].append(a["detected"])
        per_cat_rates = {}
        for cat in sorted(per_cat.keys()):
            scores = per_cat[cat]
            per_cat_rates[cat] = {
                "alert_rate": round(sum(scores) / len(scores), 4) if scores else 0,
                "n": len(scores),
            }

        results[sys_name] = {
            "alert_rate": round(rate, 4),
            "n": len(alerts_detected),
            "per_category": per_cat_rates,
            "details": alerts_detected,
        }

        print(f"\n  {sys_name}: Alert Rate={rate:.4f} ({sum(1 for a in alerts_detected if a['detected'])}/{len(alerts_detected)})")
        for cat, vals in sorted(per_cat_rates.items()):
            print(f"    {cat}: {vals['alert_rate']:.4f} (n={vals['n']})")

    # ── Summary table ──
    print("\n" + "=" * 70)
    print("ACTIVE SERVICE RESULTS SUMMARY")
    print("=" * 70)
    print(f"{'System':<25} {'Alert Rate':>12} {'N':>5}")
    print("-" * 45)
    for sys_name in systems_to_run:
        r = results[sys_name]
        print(f"{sys_name:<25} {r['alert_rate']:>12.4f} {r['n']:>5}")

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    start_time = time.time()
    print("=" * 70)
    print("FINAL FULL EVALUATION SUITE — User as Code Paper")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    final_results = {}

    def save_intermediate():
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(OUTPUT_PATH, "w") as f:
            json.dump(final_results, f, indent=2)
        print(f"  [saved intermediate results to {OUTPUT_PATH}]")

    # Benchmark 1: LOCOMO
    try:
        locomo_results = run_locomo()
        # Strip predictions for the summary JSON (keep separate)
        locomo_clean = {}
        for k, v in locomo_results.items():
            locomo_clean[k] = {key: val for key, val in v.items() if key != "predictions"}
        final_results["locomo"] = locomo_clean
        save_intermediate()
    except Exception as e:
        print(f"\n[ERROR] LOCOMO failed: {e}")
        traceback.print_exc()
        final_results["locomo"] = {"error": str(e)}

    # Benchmark 2: LongMemEval
    try:
        lme_results = run_longmemeval()
        lme_clean = {}
        for k, v in lme_results.items():
            lme_clean[k] = {key: val for key, val in v.items() if key != "predictions"}
        final_results["longmemeval"] = lme_clean
        save_intermediate()
    except Exception as e:
        print(f"\n[ERROR] LongMemEval failed: {e}")
        traceback.print_exc()
        final_results["longmemeval"] = {"error": str(e)}

    # Benchmark 3: Active Service
    try:
        active_results = run_active_service()
        active_clean = {}
        for k, v in active_results.items():
            active_clean[k] = {key: val for key, val in v.items() if key != "details"}
        final_results["active_service"] = active_clean
        save_intermediate()
    except Exception as e:
        print(f"\n[ERROR] Active Service failed: {e}")
        traceback.print_exc()
        final_results["active_service"] = {"error": str(e)}

    # Ablation (extract from LOCOMO results)
    ablation = {}
    if isinstance(final_results.get("locomo"), dict):
        for sys_key in ["uac_v5", "uac_v2", "full_context"]:
            if sys_key in final_results["locomo"]:
                ablation[sys_key] = final_results["locomo"][sys_key]
    final_results["ablation"] = ablation

    # Save
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(final_results, f, indent=2)
    print(f"\nResults saved to: {OUTPUT_PATH}")

    # ── Final summary ──
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("FINAL SUMMARY — ALL BENCHMARKS")
    print("=" * 70)

    # LOCOMO
    if "locomo" in final_results and "error" not in final_results["locomo"]:
        print("\nLOCOMO (Token F1 / LLM-Judge Accuracy):")
        print(f"  {'System':<15} {'F1':>8} {'Judge':>8}")
        print(f"  {'-'*35}")
        for s in ["uac_v5", "uac_v2", "full_context", "amem", "mem0"]:
            if s in final_results["locomo"]:
                r = final_results["locomo"][s]
                print(f"  {s:<15} {r.get('f1',0):>8.4f} {r.get('judge',0):>8.4f}")

    # LongMemEval
    if "longmemeval" in final_results and "error" not in final_results["longmemeval"]:
        print("\nLongMemEval (LLM-Judge Accuracy):")
        print(f"  {'System':<15} {'Accuracy':>10}")
        print(f"  {'-'*28}")
        for s in ["uac_v5", "uac_v2", "full_context", "amem", "mem0"]:
            if s in final_results["longmemeval"]:
                r = final_results["longmemeval"][s]
                print(f"  {s:<15} {r.get('accuracy',0):>10.4f}")

    # Active Service
    if "active_service" in final_results and "error" not in final_results["active_service"]:
        print("\nActive Service (Alert Detection Rate):")
        print(f"  {'System':<25} {'Alert Rate':>12}")
        print(f"  {'-'*40}")
        for s in ["uac_v5_with_alerts", "uac_v5_no_alerts", "amem", "mem0"]:
            if s in final_results["active_service"]:
                r = final_results["active_service"][s]
                print(f"  {s:<25} {r.get('alert_rate',0):>12.4f}")

    # Ablation
    if final_results.get("ablation"):
        print("\nAblation (LOCOMO, v5 vs v2 vs full-context):")
        print(f"  {'System':<15} {'F1':>8} {'Judge':>8}")
        print(f"  {'-'*35}")
        for s in ["uac_v5", "uac_v2", "full_context"]:
            if s in final_results["ablation"]:
                r = final_results["ablation"][s]
                print(f"  {s:<15} {r.get('f1',0):>8.4f} {r.get('judge',0):>8.4f}")

    print(f"\nTotal time: {elapsed/60:.1f} minutes")
    print(f"Results: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
