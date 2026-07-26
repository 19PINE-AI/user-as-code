"""Per-system runners for the analytical benchmark.

Each runner takes a single case (records + question) and returns a predicted
answer string. They share the tools module so the comparison stays apples-to-
apples on tool semantics.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
from types import SimpleNamespace
from typing import Any

from .tools import (
    GEMINI_MODEL,
    PythonREPL,
    ReadFileTool,
    _chat_completion,
    extract_usage,
    run_tool_loop,
)
try:
    from krill_client import KRILL_BASE_URL, request_headers_for_model
except ModuleNotFoundError:  # package import from the repository root
    from experiments.krill_client import KRILL_BASE_URL, request_headers_for_model


def _add_usage(a: dict, b: dict) -> dict:
    keys = set(a) | set(b)
    return {k: int(a.get(k, 0)) + int(b.get(k, 0)) for k in keys}

# Import UaC v5 from the parent experiments dir.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_final_line(text: str) -> str:
    lines = [ln.strip() for ln in str(text).split("\n") if ln.strip()]
    return lines[-1] if lines else ""


def _record_to_sentence(type_label: str, rec: dict) -> str:
    """Render one record as a natural-language sentence.

    Used by Mem0 (and any other extractor that needs prose) since structured
    JSON tends to defeat LLM-based memory extraction.
    """
    fields = ", ".join(f"{k}={v!r}" if isinstance(v, str) else f"{k}={v}"
                       for k, v in rec.items() if k != "id")
    label = type_label.rstrip("s")  # trips -> trip, meals -> meal, etc.
    rec_id = rec.get("id", "?")
    return f"{label.capitalize()} #{rec_id}: {fields}."


# ---------------------------------------------------------------------------
# Runner 1: Full Context (no tool, in-head reasoning)
# ---------------------------------------------------------------------------

def run_full_context(case: dict) -> dict[str, Any]:
    records_text = json.dumps(case["records"], indent=2)
    sys_inst = (
        "You will be given a JSON array of records belonging to a user. "
        "Answer the question using only those records. Reason carefully, then "
        "provide ONLY the final answer on the last line, with no extra text."
    )
    user = (
        f"Records ({len(case['records'])} items):\n"
        f"{records_text}\n\n"
        f"Question: {case['question']}\n\n"
        f"Final answer on the last line."
    )
    resp = _chat_completion(
        messages=[
            {"role": "system", "content": sys_inst},
            {"role": "user", "content": user},
        ],
        thinking_budget=4096,
    )
    usage = extract_usage(resp)
    text = (resp.choices[0].message.content or "").strip() if resp.choices else ""
    return {"answer": _extract_final_line(text), "raw": text, "turns": 1, "tool_calls": 0,
            "usage": usage}


# ---------------------------------------------------------------------------
# Runner 2: Full Context + Python REPL (records written to file, REPL + read_file tool)
# ---------------------------------------------------------------------------

def run_full_context_repl(case: dict) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "records.json"
        path.write_text(json.dumps(case["records"], indent=2))
        repl = PythonREPL(timeout=20.0)
        rf = ReadFileTool([tmp])
        sys_inst = (
            "You have two tools: `read_file(path)` reads a file, and "
            "`python(code)` runs Python in a persistent REPL. "
            f"The user's records are in a JSON file at {path}. "
            "Read the file, parse the JSON, and run Python to compute the answer. "
            "Use ONE python call to compute the answer when possible. As soon as "
            "you have the numeric answer, STOP calling python and return ONLY "
            "the final answer on the last line. Do not verify the same "
            "computation more than once."
        )
        question = (
            f"{case['question']}\n\n"
            f"The records file is at: {path}"
        )
        result = run_tool_loop(
            question=question,
            system_instruction=sys_inst,
            repl=repl,
            read_file=rf,
            max_turns=15,
            thinking_budget=2048,
        )
        return result


# ---------------------------------------------------------------------------
# Runner 3: UaC v5 with code-exec layer
#
# Skip the conversation-extraction step (records are already structured) and
# go straight to UaC v5's structuring stage: a single LLM call converts the
# records into typed Python dataclasses. The resulting code is exec'd into a
# REPL namespace, and the LLM writes typed queries against it.
# ---------------------------------------------------------------------------

_UAC_STRUCTURE_PROMPT = """Convert this list of {type_label} records into structured Python code using dataclasses.

RECORDS ({n} total):
{records}

RULES:
- Define a `@dataclass` for the record type with proper type annotations (use `from datetime import date`; parse date strings to date(year, month, day)).
- Create a list named `data` containing all records as instances of that dataclass.
- Include EVERY record. Do not summarize or skip.
- Output ONLY Python code, no markdown fences, no explanation."""


def _uac_structure_with_usage(case: dict) -> tuple[str, dict]:
    """One-shot structuring: records -> typed-dataclass Python code.

    Gemini 3 Flash supports a 1M-token context window, so we keep the records
    payload uncompressed up to ~500K characters (well under the model's
    capacity). Earlier truncation at 60K caused systematic record loss on
    N=500 cases (19-44% of records dropped, biased toward late dates).
    """
    records_text = json.dumps(case["records"], indent=1)
    MAX_CHARS = 500_000
    if len(records_text) > MAX_CHARS:
        records_text = records_text[:MAX_CHARS] + "\n... (truncated)"
    prompt = _UAC_STRUCTURE_PROMPT.format(
        type_label=case["type"], n=len(case["records"]), records=records_text)
    resp = _chat_completion(
        messages=[
            {"role": "system", "content": "You are a precise Python code generator."},
            {"role": "user", "content": prompt},
        ],
        thinking_budget=8192,
    )
    usage = extract_usage(resp)
    code = (resp.choices[0].message.content or "").strip() if resp.choices else ""
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0]
    elif "```" in code:
        code = code.split("```")[1].split("```")[0]
    return code.strip(), usage


def _uac_structure(case: dict) -> str:
    """Backward-compatible wrapper that drops usage."""
    code, _ = _uac_structure_with_usage(case)
    return code


def run_uac_v5(case: dict) -> dict[str, Any]:
    code, structuring_usage = _uac_structure_with_usage(case)
    repl = PythonREPL(initial_namespace={"records_raw": case["records"]}, timeout=20.0)
    pre = repl.run(code)
    common = (
        "Use ONE python call to compute the answer when possible. As soon as "
        "you have the numeric answer, STOP calling python and return ONLY the "
        "final answer on the last line. Do not verify the same computation "
        "more than once."
    )
    if pre["error"]:
        sys_inst = (
            "You have a Python REPL via the `python` tool. "
            "An attempt to load typed Python from records failed; the raw "
            "records are available as `records_raw` (list of dicts). " + common
        )
    else:
        sys_inst = (
            "You have a Python REPL via the `python` tool. "
            "Typed Python has been loaded: a `data` list of dataclass instances "
            "represents the user's records. The raw records are also available "
            "as `records_raw` (list of dicts). " + common
        )
    result = run_tool_loop(
        question=case["question"],
        system_instruction=sys_inst,
        repl=repl,
        max_turns=15,
        thinking_budget=2048,
    )
    result["pre_exec_error"] = pre["error"]
    result["structured_code_chars"] = len(code)
    result["usage"] = _add_usage(structuring_usage, result.get("usage", {}))
    result["structuring_usage"] = structuring_usage
    return result


# ---------------------------------------------------------------------------
# Runner 4: Mem0 (retrieval -> in-head LLM)
# ---------------------------------------------------------------------------

def run_mem0(case: dict) -> dict[str, Any]:
    import time as _time
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    from mem0 import Memory
    from openai import OpenAI

    class LocalMiniLMEmbedder:
        """Mem0 adapter for Chroma's local all-MiniLM-L6-v2 embedder."""

        def __init__(self) -> None:
            self.embedding_function = DefaultEmbeddingFunction()
            self.config = SimpleNamespace(embedding_dims=384)

        def embed(self, text: str, memory_action: str | None = None) -> list[float]:
            del memory_action
            return [float(value) for value in self.embedding_function([text])[0]]

    # Clear any leftover lock files from prior runs.
    for p in [pathlib.Path("/tmp/qdrant/.lock"),
              pathlib.Path.home() / ".mem0" / "migrations_qdrant" / ".lock"]:
        p.unlink(missing_ok=True)

    api_key = os.environ.get("KRILL_API_KEY")
    if not api_key:
        raise RuntimeError("KRILL_API_KEY is not set")
    os.environ.pop("OPENROUTER_API_KEY", None)

    with tempfile.TemporaryDirectory(prefix="analytical_mem0_") as tmp:
        m = Memory.from_config({
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": f"mem0_{os.getpid()}_{int(_time.time())}",
                    "path": tmp,
                },
            },
            "embedder": {
                # Construct a no-call placeholder, then replace it below with
                # Chroma's local ONNX all-MiniLM-L6-v2 implementation. This
                # avoids depending on sentence-transformers/PEFT at runtime.
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small",
                    "api_key": api_key,
                    "openai_base_url": KRILL_BASE_URL,
                    "embedding_dims": 384,
                },
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": GEMINI_MODEL,
                    "api_key": api_key,
                    "openai_base_url": KRILL_BASE_URL,
                },
            },
            "history_db_path": str(pathlib.Path(tmp) / "history.db"),
        })
        m.embedding_model = LocalMiniLMEmbedder()
        model_headers = request_headers_for_model(GEMINI_MODEL)
        client_options: dict[str, Any] = {
            "base_url": KRILL_BASE_URL,
            "api_key": api_key,
            "max_retries": 6,
        }
        if model_headers:
            client_options["default_headers"] = model_headers
        m.llm.client = OpenAI(**client_options)

        # Krill JSON mode requires the request itself to mention JSON.
        original_generate = m.llm.generate_response

        def generate_response(messages, response_format=None, **kwargs):
            if response_format and response_format.get("type") == "json_object":
                messages = [dict(message) for message in messages]
                messages[-1]["content"] = (
                    str(messages[-1].get("content", ""))
                    + "\n\nReturn only a valid JSON object."
                )
            return original_generate(
                messages=messages,
                response_format=response_format,
                **kwargs,
            )

        m.llm.generate_response = generate_response
        uid = f"analytical_{case['case_id']}_{int(_time.time())}"
        type_label = case["type"]
        # Convert each record to a natural-language sentence — Mem0's LLM
        # extractor produces nothing from raw JSON, but extracts cleanly from prose.
        sentences = [_record_to_sentence(type_label, rec) for rec in case["records"]]
        # Batch into chunks so Mem0's per-add LLM cost stays bounded on large N.
        BATCH = 20
        for start in range(0, len(sentences), BATCH):
            chunk = sentences[start:start + BATCH]
            text = "I want to tell you about my recent activity. " + " ".join(chunk)
            m.add([{"role": "user", "content": text}], user_id=uid)

        results = m.search(case["question"], user_id=uid, limit=20)
        if isinstance(results, dict) and "results" in results:
            mems = results["results"]
        elif isinstance(results, list):
            mems = results
        else:
            mems = []
        ctx = "\n".join(
            m_.get("memory", str(m_)) if isinstance(m_, dict) else str(m_)
            for m_ in mems
        ) if mems else "(no memories retrieved)"

    sys_inst = (
        "You will be given a list of memories about a user. "
        "Answer the question using only those memories. Reason carefully, then "
        "provide ONLY the final answer on the last line."
    )
    user = (
        f"Memories:\n{ctx}\n\n"
        f"Question: {case['question']}\n\n"
        f"Final answer on the last line."
    )
    resp = _chat_completion(
        messages=[
            {"role": "system", "content": sys_inst},
            {"role": "user", "content": user},
        ],
        thinking_budget=2048,
    )
    usage = extract_usage(resp)
    text = (resp.choices[0].message.content or "").strip() if resp.choices else ""
    try:
        m.delete_all(user_id=uid)
    except Exception:
        pass
    return {"answer": _extract_final_line(text), "raw": text, "turns": 1, "tool_calls": 0,
            "n_retrieved": len(mems), "usage": usage}


# ---------------------------------------------------------------------------
# Runner 5: MemMachine-style (full episodes + contextualized retrieval)
#
# Reimplements MemMachine's described architecture (per arXiv 2604.04853):
# stores entire conversational episodes verbatim (not LLM-extracted facts),
# indexes them at sentence level, and at query time expands nucleus matches
# with surrounding context. Used with Gemini 3 Flash for backbone parity.
# ---------------------------------------------------------------------------

def run_memmachine(case: dict) -> dict[str, Any]:
    import chromadb
    from chromadb.utils import embedding_functions

    type_label = case["type"]
    # Treat each record as a sentence-level episode; the "full episode" is the
    # complete record list so contextual expansion can include neighbors.
    sentences = [
        f"[{i}] {type_label} record: {json.dumps(rec)}"
        for i, rec in enumerate(case["records"])
    ]
    client = chromadb.Client()
    try:
        client.delete_collection("memmachine_temp")
    except Exception:
        pass
    coll = client.create_collection(
        name="memmachine_temp",
        embedding_function=embedding_functions.DefaultEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )
    coll.add(documents=sentences, ids=[f"s{i}" for i in range(len(sentences))])

    # Nucleus retrieval + contextual expansion: top-k similar + neighbors.
    k = min(20, len(sentences))
    res = coll.query(query_texts=[case["question"]], n_results=k)
    nucleus_idx = []
    for sid in res["ids"][0]:
        try:
            nucleus_idx.append(int(sid.lstrip("s")))
        except ValueError:
            pass
    # Expand with neighbors (+/- 2) per MemMachine's "contextualized retrieval".
    expanded = set()
    for i in nucleus_idx:
        for j in range(max(0, i - 2), min(len(sentences), i + 3)):
            expanded.add(j)
    ctx_lines = [sentences[j] for j in sorted(expanded)]
    ctx = "\n".join(ctx_lines) if ctx_lines else "(no episodes retrieved)"

    sys_inst = (
        "You will be given excerpts from a user's record episodes. "
        "These were retrieved using nucleus matching plus contextual expansion. "
        "Answer the question using only the episodes provided. Reason carefully, "
        "then provide ONLY the final answer on the last line."
    )
    user = (
        f"Retrieved episodes ({len(ctx_lines)} of {len(sentences)} total):\n{ctx}\n\n"
        f"Question: {case['question']}\n\n"
        f"Final answer on the last line."
    )
    resp = _chat_completion(
        messages=[
            {"role": "system", "content": sys_inst},
            {"role": "user", "content": user},
        ],
        thinking_budget=2048,
    )
    usage = extract_usage(resp)
    text = (resp.choices[0].message.content or "").strip() if resp.choices else ""
    try:
        client.delete_collection("memmachine_temp")
    except Exception:
        pass
    return {"answer": _extract_final_line(text), "raw": text, "turns": 1, "tool_calls": 0,
            "n_retrieved": len(ctx_lines), "usage": usage}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

RUNNERS = {
    "uac_v5": run_uac_v5,
    "full_context": run_full_context,
    "fc_repl": run_full_context_repl,
    "mem0": run_mem0,
    "memmachine": run_memmachine,
}
