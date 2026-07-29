"""Historical direct-Google client used for the reported LongMemEval runs."""
from __future__ import annotations
import os, random, time
from typing import Optional

from google import genai

MODEL = "gemini-3-flash-preview"
_client = None

def _get_client():
    global _client
    if _client is None:
        # google-genai accepts GEMINI_API_KEY from the environment.
        if not os.environ.get("GEMINI_API_KEY"):
            raise RuntimeError("GEMINI_API_KEY is required for LME_PROVIDER=direct-google")
        _client = genai.Client()
    return _client

def direct_google_call(contents: str, system_instruction: Optional[str] = None,
                       thinking_budget: int = 2048, temperature: float = 1.0,
                       max_retries: int = 6) -> str:
    """Reproduce the direct-Google generation settings preserved in Git history."""
    cfg = genai.types.GenerateContentConfig(
        thinking_config=genai.types.ThinkingConfig(thinking_budget=thinking_budget),
        temperature=temperature,
    )
    if system_instruction: cfg.system_instruction = system_instruction
    last = None
    for attempt in range(max_retries):
        try:
            response = _get_client().models.generate_content(model=MODEL, contents=contents, config=cfg)
            return (response.text or "").strip()
        except Exception as exc:
            last = exc; message = str(exc)
            if "429" in message or "RESOURCE_EXHAUSTED" in message:
                wait = 15*(attempt+1) + random.uniform(0, 5)
            elif "500" in message or "503" in message or "UNAVAILABLE" in message:
                wait = 10*(attempt+1) + random.uniform(0, 5)
            else: wait = 5 + random.uniform(0, 3)
            time.sleep(wait)
    raise RuntimeError(f"direct Google Gemini failed: {last}")
