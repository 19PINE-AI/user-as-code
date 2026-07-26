"""Integration tests for the tool layer.

Hits Gemini through Krill for the end-to-end test, so requires KRILL_API_KEY.
Keep the live test small; unit-test parts that don't need the model.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from analytical_bench.tools import PythonREPL, ReadFileTool, run_tool_loop  # noqa: E402


class TestPythonREPL(unittest.TestCase):
    def test_basic_print(self) -> None:
        r = PythonREPL()
        out = r.run("print('hello')")
        self.assertIn("hello", out["stdout"])
        self.assertIsNone(out["error"])

    def test_persistent_namespace(self) -> None:
        r = PythonREPL()
        r.run("x = [1, 2, 3, 4]")
        out = r.run("print(sum(x))")
        self.assertIn("10", out["stdout"])

    def test_error_capture(self) -> None:
        r = PythonREPL()
        out = r.run("1 / 0")
        self.assertIsNotNone(out["error"])
        self.assertIn("ZeroDivisionError", out["error"])

    def test_initial_namespace(self) -> None:
        r = PythonREPL(initial_namespace={"records": [{"a": 1}, {"a": 2}]})
        out = r.run("print(sum(r['a'] for r in records))")
        self.assertIn("3", out["stdout"])

    def test_timeout(self) -> None:
        r = PythonREPL(timeout=2.0)
        out = r.run("import time; time.sleep(5)")
        self.assertIn("Timeout", out["error"] or "")


class TestReadFileTool(unittest.TestCase):
    def test_read_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "data.txt"
            p.write_text("the data")
            t = ReadFileTool([tmp])
            self.assertEqual(t.read(str(p)), "the data")

    def test_read_outside_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            p = pathlib.Path(tmp_b) / "secret.txt"
            p.write_text("nope")
            t = ReadFileTool([tmp_a])
            result = t.read(str(p))
            self.assertIn("not in allowlist", result)


class TestToolLoopLive(unittest.TestCase):
    """End-to-end test against live Gemini. Skipped if no API key."""

    @classmethod
    def setUpClass(cls) -> None:
        import os
        if not os.environ.get("KRILL_API_KEY"):
            raise unittest.SkipTest("KRILL_API_KEY not set")

    def test_python_only_simple_count(self) -> None:
        records = [{"x": i} for i in range(50)]
        repl = PythonREPL(initial_namespace={"records": records})
        result = run_tool_loop(
            question="How many records have x >= 30?",
            system_instruction=(
                "You have access to a list called `records` and a `python` tool. "
                "Each record is a dict with key 'x'. Compute the answer with code."
            ),
            repl=repl,
            max_turns=5,
            thinking_budget=512,
        )
        self.assertIn("20", result["answer"])
        self.assertGreaterEqual(result["tool_calls"], 1)

    def test_read_file_then_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "records.json"
            records = [{"x": i} for i in range(50)]
            p.write_text(json.dumps(records))
            repl = PythonREPL()
            rf = ReadFileTool([tmp])
            result = run_tool_loop(
                question=f"Read {p} and tell me how many records have x >= 30.",
                system_instruction=(
                    "You have a `read_file` tool to read files and a `python` tool to run code. "
                    "The file at the given path contains a JSON array of records. "
                    "Read the file, parse the JSON, and compute the answer with python."
                ),
                repl=repl,
                read_file=rf,
                max_turns=8,
                thinking_budget=512,
            )
            self.assertIn("20", result["answer"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
