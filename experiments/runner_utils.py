"""Shared utilities for LOCOMO/LME runners.

Wraps the common Krill-hosted backbone, plus token-F1 and LLM-as-Judge scoring
used across all systems.
"""
from __future__ import annotations

import re
import time
from collections import Counter
from typing import Optional

from krill_client import KRILL_MODEL, krill_call

# Backward-compatible name imported by existing runners. New result artifacts
# record the actual configured model (gpt-5.6-luna by default).
GEMINI_MODEL = KRILL_MODEL


def _log(msg: str):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def gemini_call(contents: str, system_instruction: Optional[str] = None,
                thinking_budget: int = 2048, temperature: float = 1.0,
                max_retries: int = 6) -> str:
    """Call the shared model through Krill (legacy function name)."""
    return krill_call(
        contents,
        system_instruction=system_instruction,
        thinking_budget=thinking_budget,
        temperature=temperature,
        max_retries=max_retries,
    )


def extract_concise(text: str) -> str:
    lines = [l.strip() for l in str(text).split("\n") if l.strip()]
    return lines[-1] if lines else str(text)


def answer_question(question: str, context: str) -> str:
    """Generate an answer from context with the shared Krill backbone."""
    system = f"""You have access to stored information about a conversation between people.
Use the provided context to answer the question.
Think through carefully, then provide ONLY the final answer as a short phrase on the last line.
If the question asks about a date, resolve relative dates using conversation timestamps.
If the information is not available in the context, say "No information available".

Context:
{context}"""
    out = gemini_call(
        contents=f"{question}\n\nThink carefully, then give ONLY a concise final answer on the last line.",
        system_instruction=system,
        thinking_budget=2048,
        temperature=1.0,
    )
    return extract_concise(out)


def judge_answer(question: str, prediction: str, gold: str) -> tuple[bool, str]:
    """LLM-as-Judge with generous scoring."""
    prompt = f"""You are a generous judge evaluating question answering accuracy.

Question: {question}
Gold answer: {gold}
Predicted answer: {prediction}

Judge whether the predicted answer is CORRECT or WRONG.
Be generous: CORRECT if it conveys the same core information, even with different wording or format.
WRONG only if factually wrong or says not available when gold has answer.

Respond with exactly one line: CORRECT or WRONG, followed by a brief explanation."""
    try:
        out = gemini_call(prompt, thinking_budget=256, temperature=1.0)
    except Exception as e:
        return False, f"Judge error: {e}"
    first_line = out.split("\n")[0].upper().strip()
    correct = "CORRECT" in first_line and "WRONG" not in first_line
    return correct, out


_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def token_f1(prediction: str, gold: str) -> float:
    """Standard QA token F1."""
    pred = _TOKEN_RE.findall(str(prediction).lower())
    gold_t = _TOKEN_RE.findall(str(gold).lower())
    if not pred or not gold_t:
        return 0.0
    common = Counter(pred) & Counter(gold_t)
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0
    p = overlap / len(pred)
    r = overlap / len(gold_t)
    return 2 * p * r / (p + r)
