#!/usr/bin/env python3
"""Different-family judge spot-check.

Take an existing UaC v5 / MemMachine / Mem0 LOCOMO run, stratify-sample 100
already-judged QAs, re-judge each prediction with Claude (Anthropic) and
optionally OpenAI as a non-Gemini judge, then compute concordance with the
original Gemini judge.

We rejudge across three systems so the concordance estimate is not anchored to
one system's distribution of error types.
"""
from __future__ import annotations
import json
import pathlib
import random
import sys
import time
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from runner_utils import _log  # noqa: E402

RESULTS_DIR = pathlib.Path(__file__).resolve().parent / "results"
OUT_PATH = RESULTS_DIR / "judge_crosscheck.json"

SYSTEMS_TO_SAMPLE = ["uac_v5", "memmachine", "mem0"]
PER_SYSTEM_SAMPLE = 40   # 40 * 3 = 120 rejudge calls per family
RANDOM_SEED = 17


def sample_existing(system_name: str, n: int):
    """Load an existing run file and stratify-sample n details, balancing CORRECT/WRONG."""
    path = RESULTS_DIR / f"locomo5_{system_name}.json"
    with open(path) as f:
        d = json.load(f)
    details = []
    for conv_id, recs in d.get("details", {}).items():
        for r in recs:
            details.append({
                "system": system_name,
                "conv_id": conv_id,
                "qa_idx": r["qa_idx"],
                "question": r["question"],
                "gold": r["gold"],
                "prediction": r["prediction"],
                "gemini_correct": bool(r["judge_correct"]),
                "category": r.get("category", "uncategorized"),
            })
    rng = random.Random(RANDOM_SEED + len(system_name))
    correct = [d for d in details if d["gemini_correct"]]
    wrong = [d for d in details if not d["gemini_correct"]]
    rng.shuffle(correct)
    rng.shuffle(wrong)
    half = n // 2
    # Stratify: equal correct/wrong where possible
    sample = correct[:half] + wrong[: n - half]
    rng.shuffle(sample)
    return sample[:n]


def claude_judge(question: str, gold: str, prediction: str) -> tuple[bool, str]:
    import os, openai
    client = openai.OpenAI(api_key=os.environ["OPENROUTER_API_KEY"],
                           base_url="https://openrouter.ai/api/v1")
    prompt = f"""You are a generous judge evaluating question answering accuracy.

Question: {question}
Gold answer: {gold}
Predicted answer: {prediction}

Judge whether the predicted answer is CORRECT or WRONG.
Be generous: CORRECT if it conveys the same core information, even with different wording or format.
WRONG only if factually wrong or says not available when gold has answer.

Respond with exactly one line: CORRECT or WRONG, followed by a brief explanation."""
    last_err = None
    for attempt in range(4):
        try:
            r = client.chat.completions.create(
                model="anthropic/claude-opus-4.7",
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
            wait = (10 if "rate" in err.lower() or "overload" in err.lower() else 5) * (attempt + 1)
            _log(f"  claude retry {attempt+1}/4: {err[:120]} (wait {wait}s)")
            time.sleep(wait)
    return False, f"Claude judge error: {last_err}"


def openai_judge(question: str, gold: str, prediction: str) -> tuple[bool, str]:
    import openai
    client = openai.OpenAI()
    prompt = f"""You are a generous judge evaluating question answering accuracy.

Question: {question}
Gold answer: {gold}
Predicted answer: {prediction}

Judge whether the predicted answer is CORRECT or WRONG.
Be generous: CORRECT if it conveys the same core information, even with different wording or format.
WRONG only if factually wrong or says not available when gold has answer.

Respond with exactly one line: CORRECT or WRONG, followed by a brief explanation."""
    last_err = None
    for attempt in range(4):
        try:
            r = client.chat.completions.create(
                model="gpt-5",
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=200,
            )
            text = (r.choices[0].message.content or "").strip()
            first = text.split("\n")[0].upper().strip()
            correct = "CORRECT" in first and "WRONG" not in first
            return correct, text
        except Exception as e:
            last_err = e
            err = str(e)
            wait = (10 if "rate" in err.lower() else 5) * (attempt + 1)
            _log(f"  openai retry {attempt+1}/4: {err[:120]} (wait {wait}s)")
            time.sleep(wait)
    return False, f"OpenAI judge error: {last_err}"


def cohen_kappa(a: list[bool], b: list[bool]) -> float:
    """Cohen's kappa between two binary judges."""
    n = len(a)
    if n == 0:
        return 0.0
    agreement = sum(1 for x, y in zip(a, b) if x == y) / n
    pa_yes = sum(a) / n
    pb_yes = sum(b) / n
    expected = pa_yes * pb_yes + (1 - pa_yes) * (1 - pb_yes)
    if expected >= 0.999:
        return 1.0 if agreement >= 0.999 else 0.0
    return (agreement - expected) / (1 - expected)


def main():
    out = {"per_system": {}, "all": {}}

    # 1. Sample
    all_samples = []
    for sysname in SYSTEMS_TO_SAMPLE:
        s = sample_existing(sysname, PER_SYSTEM_SAMPLE)
        out["per_system"][sysname] = {"n_sampled": len(s), "rows": []}
        all_samples.extend(s)
        _log(f"Sampled {len(s)} QAs from {sysname}")

    # 2. Rejudge with Claude (OpenAI access is restricted in this environment;
    # using Claude as the cross-family judge is sufficient for the bias check)
    for i, row in enumerate(all_samples):
        c_ok, c_reason = claude_judge(row["question"], row["gold"], row["prediction"])
        row["claude_correct"] = bool(c_ok)
        row["claude_reason"] = c_reason
        out["per_system"][row["system"]]["rows"].append(row)
        if i % 5 == 0 or i == len(all_samples) - 1:
            _log(f"  [{i+1}/{len(all_samples)}] {row['system']:10s} gemini={'C' if row['gemini_correct'] else 'W'}  claude={'C' if c_ok else 'W'}")
        with open(OUT_PATH, "w") as f:
            json.dump(out, f, indent=2, default=str)

    # 3. Concordance per system + overall
    def stats(rows):
        gemini = [r["gemini_correct"] for r in rows]
        claude = [r["claude_correct"] for r in rows]
        n = len(rows)
        return {
            "n": n,
            "gemini_yes_rate": sum(gemini) / n if n else 0,
            "claude_yes_rate": sum(claude) / n if n else 0,
            "gemini_vs_claude_agreement": sum(1 for a, b in zip(gemini, claude) if a == b) / n if n else 0,
            "gemini_vs_claude_kappa": cohen_kappa(gemini, claude),
        }

    for sysname, block in out["per_system"].items():
        block["concordance"] = stats(block["rows"])
        _log(f"  {sysname} concordance: gemini vs claude agree={block['concordance']['gemini_vs_claude_agreement']:.3f} "
             f"k={block['concordance']['gemini_vs_claude_kappa']:.3f}")

    out["all"] = stats(all_samples)
    _log(f"  ALL concordance: gemini vs claude agree={out['all']['gemini_vs_claude_agreement']:.3f} "
         f"k={out['all']['gemini_vs_claude_kappa']:.3f}")

    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2, default=str)
    _log(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
