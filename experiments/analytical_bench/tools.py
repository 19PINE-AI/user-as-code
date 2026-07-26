"""Sandboxed Python REPL and read_file tools, plus a Gemini tool-use loop driver.

The REPL is a long-lived namespace per case: each `python(code)` call mutates
the same namespace, so the LLM can build state across turns.  Stdout is
captured and returned.  A SIGALRM-based wall-clock timeout prevents runaway
loops (Linux only).

The tool-use loop is generic over which tools the agent has, so the same
driver runs the FC+REPL baseline (read_file + python) and the UaC code-exec
variant (python only, with the structured code preloaded).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import pathlib
import random
import signal
import time
import traceback
from typing import Any, Optional

from openai import OpenAI
try:
    from krill_client import KRILL_BASE_URL, request_headers_for_model
except ModuleNotFoundError:  # package import from the repository root
    from experiments.krill_client import KRILL_BASE_URL, request_headers_for_model

GEMINI_MODEL = os.environ.get("ANALYTICAL_MODEL", "gemini-3-flash-preview")
_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("KRILL_API_KEY")
        if not api_key:
            raise RuntimeError("KRILL_API_KEY is not set")
        _client = OpenAI(
            base_url=KRILL_BASE_URL,
            api_key=api_key,
            max_retries=0,
        )
    return _client


# ---------------------------------------------------------------------------
# Sandboxed Python REPL with persistent namespace
# ---------------------------------------------------------------------------

class _ExecTimeout(Exception):
    pass


class PythonREPL:
    """Persistent-namespace Python REPL with SIGALRM-based wall timeout."""

    def __init__(self, initial_namespace: Optional[dict] = None, timeout: float = 30.0):
        self.namespace: dict[str, Any] = dict(initial_namespace or {})
        self.timeout = timeout

    def run(self, code: str) -> dict[str, Any]:
        """Execute `code`. Returns {stdout, error}; namespace persists."""
        buf = io.StringIO()
        err: Optional[str] = None

        def _handler(signum, frame):  # noqa: ARG001
            raise _ExecTimeout(f"Code did not finish within {self.timeout}s")

        old_handler = signal.signal(signal.SIGALRM, _handler)
        signal.setitimer(signal.ITIMER_REAL, self.timeout)
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                exec(code, self.namespace)
        except _ExecTimeout as e:
            err = f"TimeoutError: {e}"
        except SystemExit as e:
            err = f"SystemExit: {e}"
        except BaseException:  # noqa: BLE001
            err = traceback.format_exc()
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)
        return {"stdout": buf.getvalue(), "error": err}


# ---------------------------------------------------------------------------
# read_file tool
# ---------------------------------------------------------------------------

class ReadFileTool:
    """Reads files from a fixed allowlist of paths."""

    def __init__(self, allow: list[str]):
        self.allow = [pathlib.Path(p).resolve() for p in allow]

    def read(self, path: str) -> str:
        try:
            target = pathlib.Path(path).resolve()
        except Exception as e:
            return f"Error: invalid path: {e}"
        for a in self.allow:
            if target == a or target.is_relative_to(a) if hasattr(target, "is_relative_to") else str(target).startswith(str(a)):
                try:
                    return target.read_text()
                except Exception as e:
                    return f"Error reading {target}: {e}"
        return f"Error: path {path} not in allowlist"


# ---------------------------------------------------------------------------
# Gemini tool-use loop
# ---------------------------------------------------------------------------

def extract_usage(resp: Any) -> dict[str, int]:
    """Pull token counts from an OpenAI-compatible completion."""
    usage = {"prompt": 0, "output": 0, "thoughts": 0, "cached": 0}
    um = getattr(resp, "usage", None)
    if um is None:
        return usage
    usage["prompt"] = int(getattr(um, "prompt_tokens", 0) or 0)
    usage["output"] = int(getattr(um, "completion_tokens", 0) or 0)
    completion_details = getattr(um, "completion_tokens_details", None)
    prompt_details = getattr(um, "prompt_tokens_details", None)
    usage["thoughts"] = int(
        getattr(completion_details, "reasoning_tokens", 0) or 0
    )
    usage["cached"] = int(getattr(prompt_details, "cached_tokens", 0) or 0)
    return usage


def _chat_completion(
    *,
    messages: list[dict[str, Any]],
    tools: Optional[list[dict[str, Any]]] = None,
    thinking_budget: int = 2048,
    max_retries: int = 6,
) -> Any:
    """Call Gemini through Krill's OpenAI-compatible endpoint."""
    del thinking_budget  # Krill's compatibility API does not expose this knob.
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            kwargs: dict[str, Any] = {
                "model": GEMINI_MODEL,
                "messages": messages,
                "extra_headers": request_headers_for_model(GEMINI_MODEL) or None,
            }
            if tools:
                kwargs["tools"] = tools
            return _get_client().chat.completions.create(**kwargs)
        except Exception as e:
            last_err = e
            status = getattr(e, "status_code", None)
            retryable = (
                status == 429
                or (isinstance(status, int) and status >= 500)
                or type(e).__name__ in {"APIConnectionError", "APITimeoutError"}
            )
            if not retryable or attempt + 1 >= max_retries:
                break
            base = 15 if status == 429 else 5
            wait = min(base * (attempt + 1), 60) + random.uniform(0, 2)
            time.sleep(wait)
    raise RuntimeError(f"Krill Gemini request failed: {last_err}") from last_err


def run_tool_loop(
    *,
    question: str,
    system_instruction: str,
    repl: Optional[PythonREPL] = None,
    read_file: Optional[ReadFileTool] = None,
    max_turns: int = 10,
    thinking_budget: int = 2048,
) -> dict[str, Any]:
    """Drive a Gemini tool-use loop through Krill.

    Returns:
      {"answer": str, "turns": int, "tool_calls": int, "log": [...]}
    """
    tools: list[dict[str, Any]] = []
    if repl is not None:
        tools.append({
            "type": "function",
            "function": {
                "name": "python",
                "description": (
                    "Execute Python code in a persistent REPL namespace. "
                    "Use print() to surface values you want to read back."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"code": {"type": "string"}},
                    "required": ["code"],
                },
            },
        })
    if read_file is not None:
        tools.append({
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a file at the given path.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        })

    user_msg = (
        f"{question}\n\n"
        "Use the available tools to compute the answer from the data. "
        "When you are done, reply with ONLY the final answer on the last line, "
        "with no extra commentary."
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_msg},
    ]
    log: list[dict] = []
    tool_calls = 0
    total_usage = {"prompt": 0, "output": 0, "thoughts": 0, "cached": 0}

    for turn in range(max_turns):
        resp = _chat_completion(
            messages=messages,
            tools=tools,
            thinking_budget=thinking_budget,
        )
        u = extract_usage(resp)
        for k in total_usage:
            total_usage[k] += u[k]
        choice = resp.choices[0] if resp.choices else None
        if choice is None or choice.message is None:
            return {"answer": "", "turns": turn + 1, "tool_calls": tool_calls,
                    "log": log, "error": "no completion choice", "usage": total_usage}

        message = choice.message
        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": message.content or "",
        }
        if message.tool_calls:
            assistant_message["tool_calls"] = [
                call.model_dump(exclude_none=True) for call in message.tool_calls
            ]
        messages.append(assistant_message)

        # Look for function calls.
        if message.tool_calls:
            for call in message.tool_calls:
                fc = call.function
                tool_calls += 1
                try:
                    args = json.loads(fc.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                if fc.name == "python" and repl is not None:
                    code = args.get("code", "")
                    out = repl.run(code)
                    log.append({"tool": "python", "code": code[:500], "stdout": out["stdout"][:500], "error": out["error"]})
                    payload = {"stdout": out["stdout"][:6000],
                               "error": (out["error"] or "")[:2000]}
                elif fc.name == "read_file" and read_file is not None:
                    path = args.get("path", "")
                    text = read_file.read(path)
                    log.append({"tool": "read_file", "path": path, "len": len(text)})
                    payload = {"content": text[:80000]}
                else:
                    payload = {"error": f"unknown tool: {fc.name}"}
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(payload),
                })
            continue

        # No function call — extract final text answer.
        text = (message.content or "").strip()
        # The last non-empty line is the final answer.
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        answer = lines[-1] if lines else ""
        return {"answer": answer, "raw": text, "turns": turn + 1,
                "tool_calls": tool_calls, "log": log, "usage": total_usage}

    return {"answer": "", "raw": "", "turns": max_turns, "tool_calls": tool_calls,
            "log": log, "error": "max_turns_exceeded", "usage": total_usage}
