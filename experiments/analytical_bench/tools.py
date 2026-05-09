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
import pathlib
import signal
import time
import traceback
from typing import Any, Optional

from google import genai

GEMINI_MODEL = "gemini-3-flash-preview"
_gclient = genai.Client()


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
    """Pull token counts from a Gemini response's usage_metadata."""
    usage = {"prompt": 0, "output": 0, "thoughts": 0, "cached": 0}
    um = getattr(resp, "usage_metadata", None)
    if um is None:
        return usage
    usage["prompt"] = int(getattr(um, "prompt_token_count", 0) or 0)
    usage["output"] = int(getattr(um, "candidates_token_count", 0) or 0)
    usage["thoughts"] = int(getattr(um, "thoughts_token_count", 0) or 0)
    usage["cached"] = int(getattr(um, "cached_content_token_count", 0) or 0)
    return usage


def _gemini_call(contents: list, tools: list, system_instruction: str,
                 thinking_budget: int = 2048, max_retries: int = 6) -> Any:
    cfg = genai.types.GenerateContentConfig(
        thinking_config=genai.types.ThinkingConfig(thinking_budget=thinking_budget),
        temperature=1.0,
        system_instruction=system_instruction,
        tools=tools,
        # Disable automatic function calling so we drive the loop ourselves.
        automatic_function_calling=genai.types.AutomaticFunctionCallingConfig(disable=True),
    )
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            return _gclient.models.generate_content(
                model=GEMINI_MODEL, contents=contents, config=cfg)
        except Exception as e:
            last_err = e
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                wait = 15 * (attempt + 1)
            elif "500" in err or "503" in err or "UNAVAILABLE" in err:
                wait = 10 * (attempt + 1)
            else:
                wait = 5
            time.sleep(wait)
    raise RuntimeError(f"gemini failed after {max_retries} attempts: {last_err}")


def run_tool_loop(
    *,
    question: str,
    system_instruction: str,
    repl: Optional[PythonREPL] = None,
    read_file: Optional[ReadFileTool] = None,
    max_turns: int = 10,
    thinking_budget: int = 2048,
) -> dict[str, Any]:
    """Drive a Gemini tool-use loop.

    Returns:
      {"answer": str, "turns": int, "tool_calls": int, "log": [...]}
    """
    tool_decls = []
    if repl is not None:
        tool_decls.append(genai.types.FunctionDeclaration(
            name="python",
            description=(
                "Execute Python code in a persistent REPL namespace. "
                "Use print() to surface values you want to read back."
            ),
            parameters=genai.types.Schema(
                type=genai.types.Type.OBJECT,
                properties={"code": genai.types.Schema(type=genai.types.Type.STRING)},
                required=["code"],
            ),
        ))
    if read_file is not None:
        tool_decls.append(genai.types.FunctionDeclaration(
            name="read_file",
            description="Read the contents of a file at the given path.",
            parameters=genai.types.Schema(
                type=genai.types.Type.OBJECT,
                properties={"path": genai.types.Schema(type=genai.types.Type.STRING)},
                required=["path"],
            ),
        ))
    tools = [genai.types.Tool(function_declarations=tool_decls)] if tool_decls else []

    user_msg = (
        f"{question}\n\n"
        "Use the available tools to compute the answer from the data. "
        "When you are done, reply with ONLY the final answer on the last line, "
        "with no extra commentary."
    )
    contents: list = [
        genai.types.Content(role="user", parts=[genai.types.Part(text=user_msg)])
    ]
    log: list[dict] = []
    tool_calls = 0
    total_usage = {"prompt": 0, "output": 0, "thoughts": 0, "cached": 0}

    for turn in range(max_turns):
        resp = _gemini_call(
            contents=contents,
            tools=tools,
            system_instruction=system_instruction,
            thinking_budget=thinking_budget,
        )
        u = extract_usage(resp)
        for k in total_usage:
            total_usage[k] += u[k]
        cand = resp.candidates[0] if resp.candidates else None
        if cand is None or cand.content is None:
            return {"answer": "", "turns": turn + 1, "tool_calls": tool_calls,
                    "log": log, "error": "no candidate", "usage": total_usage}

        contents.append(cand.content)

        # Look for function calls.
        fc_parts = [p for p in (cand.content.parts or []) if getattr(p, "function_call", None)]
        if fc_parts:
            response_parts = []
            for p in fc_parts:
                fc = p.function_call
                tool_calls += 1
                if fc.name == "python" and repl is not None:
                    code = (fc.args or {}).get("code", "")
                    out = repl.run(code)
                    log.append({"tool": "python", "code": code[:500], "stdout": out["stdout"][:500], "error": out["error"]})
                    response_parts.append(genai.types.Part(
                        function_response=genai.types.FunctionResponse(
                            name="python",
                            response={"stdout": out["stdout"][:6000],
                                      "error": (out["error"] or "")[:2000]},
                        ),
                    ))
                elif fc.name == "read_file" and read_file is not None:
                    path = (fc.args or {}).get("path", "")
                    text = read_file.read(path)
                    log.append({"tool": "read_file", "path": path, "len": len(text)})
                    response_parts.append(genai.types.Part(
                        function_response=genai.types.FunctionResponse(
                            name="read_file",
                            response={"content": text[:80000]},
                        ),
                    ))
                else:
                    response_parts.append(genai.types.Part(
                        function_response=genai.types.FunctionResponse(
                            name=fc.name,
                            response={"error": f"unknown tool: {fc.name}"},
                        ),
                    ))
            contents.append(genai.types.Content(role="user", parts=response_parts))
            continue

        # No function call — extract final text answer.
        text_parts = [p.text for p in (cand.content.parts or []) if getattr(p, "text", None)]
        text = "\n".join(text_parts).strip()
        # The last non-empty line is the final answer.
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        answer = lines[-1] if lines else ""
        return {"answer": answer, "raw": text, "turns": turn + 1,
                "tool_calls": tool_calls, "log": log, "usage": total_usage}

    return {"answer": "", "raw": "", "turns": max_turns, "tool_calls": tool_calls,
            "log": log, "error": "max_turns_exceeded", "usage": total_usage}
