"""OpenAI-compatible Krill client shared by the LOCOMO experiments.

The API key is read lazily from ``KRILL_API_KEY`` so importing experiment
modules remains safe in environments where credentials are not configured.
No credential is ever written to an experiment artifact.
"""
from __future__ import annotations

import os
import platform
import random
import sys
import threading
import time
from collections import Counter
from typing import Optional

from openai import OpenAI


KRILL_BASE_URL = os.environ.get("KRILL_BASE_URL", "https://api.krill-ai.net/v1")
KRILL_MODEL = os.environ.get("KRILL_MODEL", "gpt-5.6-luna")
GEMINI_CLI_VERSION = os.environ.get("GEMINI_CLI_VERSION", "0.28.0")

_client: Optional[OpenAI] = None
_client_lock = threading.Lock()
_usage_lock = threading.Lock()
_usage = Counter()


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is None:
            api_key = os.environ.get("KRILL_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "KRILL_API_KEY is not set; export it before running the experiments"
                )
            # Retry in this module so delays and retryable status codes are
            # explicit and consistent across all systems.
            _client = OpenAI(
                base_url=KRILL_BASE_URL,
                api_key=api_key,
                max_retries=0,
            )
    return _client


def _safe_error(exc: Exception) -> str:
    message = str(exc)
    api_key = os.environ.get("KRILL_API_KEY")
    if api_key:
        message = message.replace(api_key, "<redacted>")
    return message


def _retryable(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status == 429 or (isinstance(status, int) and status >= 500):
        return True
    return type(exc).__name__ in {"APIConnectionError", "APITimeoutError"}


def _record_usage(completion) -> None:
    usage = getattr(completion, "usage", None)
    if usage is None:
        return
    values = {
        "requests": 1,
        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }
    with _usage_lock:
        _usage.update(values)


def usage_snapshot() -> dict[str, int]:
    """Return token and successful-request totals for the current process."""
    with _usage_lock:
        return dict(_usage)


def gemini_cli_user_agent(model: str) -> Optional[str]:
    """Return the official Gemini CLI header format for Gemini routes.

    Krill currently returns HTTP 500 for its Gemini models when called with
    the OpenAI SDK user agent, but accepts the standard model-aware Gemini CLI
    user agent. The format comes from google-gemini/gemini-cli's
    ``contentGenerator.ts``.
    """
    if not model.lower().startswith("gemini-"):
        return None
    node_platform = {
        "darwin": "darwin",
        "linux": "linux",
        "win32": "win32",
    }.get(sys.platform, sys.platform)
    node_arch = {
        "arm64": "arm64",
        "aarch64": "arm64",
        "x86_64": "x64",
        "amd64": "x64",
    }.get(platform.machine().lower(), platform.machine().lower())
    surface = os.environ.get("GEMINI_CLI_SURFACE", "terminal")
    return f"GeminiCLI/{GEMINI_CLI_VERSION}/{model} ({node_platform}; {node_arch}; {surface})"


def request_headers_for_model(model: str) -> dict[str, str]:
    user_agent = gemini_cli_user_agent(model)
    return {"User-Agent": user_agent} if user_agent else {}


def krill_call(
    contents: str,
    system_instruction: Optional[str] = None,
    *,
    model: Optional[str] = None,
    max_retries: int = 6,
    # Retained for source compatibility with the former Gemini helper. Krill's
    # documented OpenAI-compatible example does not expose Gemini token-budget
    # controls, and the Luna evaluation uses the provider defaults.
    thinking_budget: Optional[int] = None,
    temperature: Optional[float] = None,
) -> str:
    """Generate text with the configured model through Krill.

    Only transient connection, rate-limit, and server failures are retried.
    Authentication and request-validation errors fail immediately.
    """
    del thinking_budget, temperature
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": contents})
    target_model = model or KRILL_MODEL
    headers = request_headers_for_model(target_model)

    last_error: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            completion = _get_client().chat.completions.create(
                model=target_model,
                messages=messages,
                extra_headers=headers or None,
            )
            _record_usage(completion)
            if not completion.choices:
                raise RuntimeError("Krill returned no completion choices")
            text = completion.choices[0].message.content
            if not isinstance(text, str) or not text.strip():
                raise RuntimeError("Krill returned an empty text completion")
            return text.strip()
        except Exception as exc:
            last_error = exc
            if not _retryable(exc) or attempt + 1 >= max_retries:
                break
            status = getattr(exc, "status_code", None)
            base = 15 if status == 429 else 5
            wait = min(base * (attempt + 1), 60) + random.uniform(0, 2)
            print(
                f"{time.strftime('%H:%M:%S')} Krill retry "
                f"{attempt + 1}/{max_retries}: {_safe_error(exc)[:160]} "
                f"(wait {wait:.0f}s)",
                flush=True,
            )
            time.sleep(wait)

    assert last_error is not None
    raise RuntimeError(f"Krill request failed: {_safe_error(last_error)}") from last_error
