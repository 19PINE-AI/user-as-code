#!/usr/bin/env python3
"""Full cross-family rejudge: Claude Opus 4.7 judges every prediction.

Re-judges all predictions in:
  - locomo5_<system>.json for system in {uac_v5, full_context, memmachine, mem0}
  - lme200_<system>.json for the same 4 systems

Output:
  results/full_rejudge.json — per-prediction records with both Gemini and
  Claude judgments, plus per-system concordance and a recomputed accuracy
  under the Claude judge.
"""
from __future__ import annotations
import json
import pathlib
import sys
import time

import os
import openai

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from runner_utils import _log  # noqa: E402

RESULTS_DIR = pathlib.Path(__file__).resolve().parent / "results"
OUT_PATH = RESULTS_DIR / "full_rejudge.json"

SYSTEMS = ["uac_v5", "full_context", "memmachine", "mem0", "a_mem", "hindsight", "evermemos"]

# Use OpenRouter for the cross-family Claude judge so the same key/route is
# used for any non-Gemini model we may want to call.
CLAUDE_MODEL = "anthropic/claude-opus-4.7"
client = openai.OpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
)


def claude_judge(question: str, gold: str, prediction: str) -> tuple[bool, str]:
    prompt = f"""You are a generous judge evaluating question answering accuracy.

Question: {question}
Gold answer: {gold}
Predicted answer: {prediction}

Judge whether the predicted answer is CORRECT or WRONG.
Be generous: CORRECT if it conveys the same core information, even with different wording or format.
WRONG only if factually wrong or says not available when gold has answer.

Respond with exactly one line: CORRECT or WRONG, followed by a brief explanation."""
    last_err = None
    for attempt in range(5):
        try:
            r = client.chat.completions.create(
                model=CLAUDE_MODEL,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            text = (r.choices[0].message.content or "").strip()
            first = text.split("\n")[0].upper().strip()
            correct = "CORRECT" in first and "WRONG" not in first
            return correct, text
        except Exception as e:
            last_err = e
            err = str(e)
            if "rate" in err.lower() or "overload" in err.lower() or "429" in err:
                wait = 15 * (attempt + 1)
            else:
                wait = 5 * (attempt + 1)
            _log(f"  claude retry {attempt+1}/5: {err[:120]} (wait {wait}s)")
            time.sleep(wait)
    return False, f"Claude judge error: {last_err}"


def load_existing_state():
    if OUT_PATH.exists():
        with open(OUT_PATH) as f:
            return json.load(f)
    return {"locomo": {sys: {} for sys in SYSTEMS},
            "lme": {sys: {} for sys in SYSTEMS}}


def save_state(state):
    with open(OUT_PATH, "w") as f:
        json.dump(state, f, indent=2, default=str)


def rejudge_locomo(state):
    for system in SYSTEMS:
        # Prefer 10-conv results if present; fall back to 5-conv
        path = RESULTS_DIR / f"locomo10_{system}.json"
        if not path.exists():
            path = RESULTS_DIR / f"locomo5_{system}.json"
        if not path.exists():
            _log(f"  locomo5_{system}.json not found, skipping")
            continue
        with open(path) as f:
            d = json.load(f)
        sys_state = state["locomo"].setdefault(system, {})
        done = sum(1 for v in sys_state.values() if "claude_correct" in v)
        total = sum(len(v) for v in d.get("details", {}).values())
        _log(f"=== LOCOMO {system} ===  done={done}/{total}")
        for conv_id, recs in d.get("details", {}).items():
            for r in recs:
                key = f"{conv_id}_{r['qa_idx']}"
                if key in sys_state and "claude_correct" in sys_state[key]:
                    continue
                jc, jr = claude_judge(r["question"], r["gold"], r["prediction"])
                sys_state[key] = {
                    "question": r["question"],
                    "gold": r["gold"],
                    "prediction": r["prediction"],
                    "gemini_correct": bool(r["judge_correct"]),
                    "claude_correct": bool(jc),
                    "claude_reason": jr,
                    "conv_id": conv_id,
                    "qa_idx": r["qa_idx"],
                    "category": r.get("category", "uncategorized"),
                }
                done += 1
                if done % 20 == 0:
                    save_state(state)
                    _log(f"  [{system}] {done}/{total}  g={'C' if r['judge_correct'] else 'W'} c={'C' if jc else 'W'}")
        save_state(state)


def rejudge_lme(state):
    for system in SYSTEMS:
        # Prefer 500 results if present; fall back to 200
        path = RESULTS_DIR / f"lme500_{system}.json"
        if not path.exists():
            path = RESULTS_DIR / f"lme200_{system}.json"
        if not path.exists():
            _log(f"  lme200_{system}.json not found, skipping")
            continue
        with open(path) as f:
            d = json.load(f)
        sys_state = state["lme"].setdefault(system, {})
        items = d.get("by_question", {})
        done = sum(1 for v in sys_state.values() if "claude_correct" in v)
        total = len(items)
        _log(f"=== LME {system} ===  done={done}/{total}")
        for qid, r in items.items():
            if qid in sys_state and "claude_correct" in sys_state[qid]:
                continue
            jc, jr = claude_judge(r["question"], r["gold"], r["prediction"])
            sys_state[qid] = {
                "question": r["question"],
                "gold": r["gold"],
                "prediction": r["prediction"],
                "gemini_correct": bool(r["judge_correct"]),
                "claude_correct": bool(jc),
                "claude_reason": jr,
                "question_id": qid,
                "question_type": r.get("question_type", "uncategorized"),
            }
            done += 1
            if done % 20 == 0:
                save_state(state)
                _log(f"  [{system}] {done}/{total}  g={'C' if r['judge_correct'] else 'W'} c={'C' if jc else 'W'}")
        save_state(state)


def summarize(state):
    """Compute concordance and Claude-judge accuracies per system per dataset."""
    out = {"summary": {}}
    for dataset in ("locomo", "lme"):
        out["summary"][dataset] = {}
        for system in SYSTEMS:
            recs = list(state[dataset].get(system, {}).values())
            recs = [r for r in recs if "claude_correct" in r]
            n = len(recs)
            if n == 0:
                continue
            g_yes = sum(1 for r in recs if r["gemini_correct"])
            c_yes = sum(1 for r in recs if r["claude_correct"])
            agree = sum(1 for r in recs if r["gemini_correct"] == r["claude_correct"])
            both = sum(1 for r in recs if r["gemini_correct"] and r["claude_correct"])
            g_only = sum(1 for r in recs if r["gemini_correct"] and not r["claude_correct"])
            c_only = sum(1 for r in recs if r["claude_correct"] and not r["gemini_correct"])
            neither = n - both - g_only - c_only
            # Cohen's kappa
            pa = g_yes / n
            pb = c_yes / n
            expected = pa * pb + (1 - pa) * (1 - pb)
            agreement = agree / n
            kappa = (agreement - expected) / (1 - expected) if expected < 0.999 else 1.0
            out["summary"][dataset][system] = {
                "n": n,
                "gemini_accuracy": g_yes / n,
                "claude_accuracy": c_yes / n,
                "agreement": agreement,
                "kappa": kappa,
                "both_correct": both,
                "gemini_only_correct": g_only,
                "claude_only_correct": c_only,
                "both_wrong": neither,
            }
    state["summary"] = out["summary"]
    save_state(state)
    return out["summary"]


def main():
    state = load_existing_state()
    rejudge_locomo(state)
    rejudge_lme(state)
    summary = summarize(state)
    _log("\n=== SUMMARY ===")
    for dataset, sysdict in summary.items():
        _log(f"--- {dataset} ---")
        for system, s in sysdict.items():
            _log(f"  {system:14s} n={s['n']:>3d}  gemini={s['gemini_accuracy']:.3f}  "
                 f"claude={s['claude_accuracy']:.3f}  agree={s['agreement']:.3f}  k={s['kappa']:.3f}")


if __name__ == "__main__":
    main()
