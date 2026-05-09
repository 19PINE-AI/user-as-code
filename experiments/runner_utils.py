"""Shared utilities for LOCOMO/LME runners.

Wraps Gemini and OpenAI calls with retry logic, plus token-F1 metric and
LLM-as-Judge scoring used across all systems.
"""
from __future__ import annotations

import os
import random
import re
import time
from collections import Counter
from typing import Optional

from google import genai

GEMINI_MODEL = "gemini-3-flash-preview"
_gclient = genai.Client()


def _log(msg: str):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def gemini_call(contents: str, system_instruction: Optional[str] = None,
                thinking_budget: int = 2048, temperature: float = 1.0,
                max_retries: int = 6) -> str:
    """Call Gemini with thinking. Retries on 429/5xx."""
    cfg = genai.types.GenerateContentConfig(
        thinking_config=genai.types.ThinkingConfig(thinking_budget=thinking_budget),
        temperature=temperature,
    )
    if system_instruction:
        cfg.system_instruction = system_instruction
    last_err = None
    for attempt in range(max_retries):
        try:
            r = _gclient.models.generate_content(
                model=GEMINI_MODEL, contents=contents, config=cfg)
            return (r.text or "").strip()
        except Exception as e:
            last_err = e
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                wait = 15 * (attempt + 1) + random.uniform(0, 5)
            elif "500" in err or "503" in err or "UNAVAILABLE" in err:
                wait = 10 * (attempt + 1) + random.uniform(0, 5)
            else:
                wait = 5 + random.uniform(0, 3)
            _log(f"  gemini retry {attempt+1}/{max_retries}: {err[:120]} (wait {wait:.0f}s)")
            time.sleep(wait)
    raise RuntimeError(f"gemini failed: {last_err}")


def extract_concise(text: str) -> str:
    lines = [l.strip() for l in str(text).split("\n") if l.strip()]
    return lines[-1] if lines else str(text)


def answer_question(question: str, context: str) -> str:
    """Generate an answer given context, using thinking-enabled Gemini."""
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
