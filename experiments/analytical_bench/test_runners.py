"""End-to-end runner tests.

Each runner is exercised on one small case (N=20) to verify the plumbing
works. Hits Gemini through Krill, so requires KRILL_API_KEY.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from analytical_bench.runners import (  # noqa: E402
    run_full_context, run_full_context_repl, run_uac_v5, run_mem0, run_memmachine,
)
from analytical_bench.scoring import score  # noqa: E402


SMALL_CASE = None  # populated in setUpClass


def _load_small_case() -> dict:
    """Load a small N=20 case for testing."""
    p = pathlib.Path(__file__).resolve().parents[1] / "results" / "analytical_cases.json"
    data = json.load(open(p))
    # Pick a simple count-question on N=20 — most reliable for end-to-end test.
    for c in data["cases"]:
        if c["n"] == 20 and c["answer_kind"] == "int" and "count" in c["question_id"]:
            return c
    raise RuntimeError("no small int-count case found")


class TestRunners(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        if not os.environ.get("KRILL_API_KEY"):
            raise unittest.SkipTest("KRILL_API_KEY not set")
        global SMALL_CASE
        SMALL_CASE = _load_small_case()
        print(f"\n[setup] using case {SMALL_CASE['case_id']}: {SMALL_CASE['question'][:80]}")
        print(f"[setup] gold = {SMALL_CASE['gold']}")

    def test_full_context(self) -> None:
        r = run_full_context(SMALL_CASE)
        ok = score(SMALL_CASE["answer_kind"], r["answer"], SMALL_CASE["gold"])
        print(f"\nfull_context => {r['answer']!r}  ok={ok}")
        # Don't assert correctness on tiny single-case — just that it returns a non-empty answer.
        self.assertTrue(r["answer"])

    def test_full_context_repl(self) -> None:
        r = run_full_context_repl(SMALL_CASE)
        ok = score(SMALL_CASE["answer_kind"], r["answer"], SMALL_CASE["gold"])
        print(f"\nfc_repl => {r['answer']!r}  ok={ok}  turns={r['turns']}  tool_calls={r['tool_calls']}")
        self.assertTrue(r["answer"])

    def test_uac_v5(self) -> None:
        r = run_uac_v5(SMALL_CASE)
        ok = score(SMALL_CASE["answer_kind"], r["answer"], SMALL_CASE["gold"])
        print(f"\nuac_v5 => {r['answer']!r}  ok={ok}  turns={r['turns']}  tool_calls={r['tool_calls']}")
        self.assertTrue(r["answer"])

    @unittest.skipUnless(os.environ.get("KRILL_API_KEY"), "KRILL_API_KEY not set")
    def test_mem0(self) -> None:
        r = run_mem0(SMALL_CASE)
        ok = score(SMALL_CASE["answer_kind"], r["answer"], SMALL_CASE["gold"])
        print(f"\nmem0 => {r['answer']!r}  ok={ok}  retrieved={r.get('n_retrieved')}")
        self.assertTrue(r["answer"])

    def test_memmachine(self) -> None:
        r = run_memmachine(SMALL_CASE)
        ok = score(SMALL_CASE["answer_kind"], r["answer"], SMALL_CASE["gold"])
        print(f"\nmemmachine => {r['answer']!r}  ok={ok}  retrieved={r.get('n_retrieved')}")
        self.assertTrue(r["answer"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
