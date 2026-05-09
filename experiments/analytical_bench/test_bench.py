"""Integration tests for the analytical benchmark.

Run via: python -m experiments.analytical_bench.test_bench
or: pytest experiments/analytical_bench/test_bench.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from analytical_bench.schemas import SCHEMAS  # noqa: E402
from analytical_bench.scoring import score  # noqa: E402


class TestSchemas(unittest.TestCase):
    def test_all_schemas_produce_records(self) -> None:
        for name, schema in SCHEMAS.items():
            with self.subTest(schema=name):
                records = schema["gen"](seed=42, n=20)
                self.assertEqual(len(records), 20)
                self.assertTrue(all(isinstance(r, dict) for r in records))

    def test_all_schemas_produce_ten_questions(self) -> None:
        for name, schema in SCHEMAS.items():
            with self.subTest(schema=name):
                records = schema["gen"](seed=42, n=50)
                qs = schema["qfn"](records)
                self.assertEqual(len(qs), 10, f"{name} should have 10 questions")
                for q in qs:
                    self.assertIn("id", q)
                    self.assertIn("kind", q)
                    self.assertIn("q", q)
                    self.assertIn("a", q)
                    self.assertIn(q["kind"], {"int", "float", "string", "set", "list"})

    def test_ground_truth_self_consistent(self) -> None:
        # Each ground-truth answer should score CORRECT against itself.
        for name, schema in SCHEMAS.items():
            records = schema["gen"](seed=7, n=30)
            qs = schema["qfn"](records)
            for q in qs:
                with self.subTest(schema=name, qid=q["id"]):
                    self.assertTrue(
                        score(q["kind"], q["a"], q["a"]),
                        f"{name}/{q['id']} gold did not match itself: {q['a']!r}",
                    )

    def test_records_are_json_serializable(self) -> None:
        for name, schema in SCHEMAS.items():
            with self.subTest(schema=name):
                records = schema["gen"](seed=1, n=5)
                json.dumps(records)  # raises if not serializable


class TestScoring(unittest.TestCase):
    def test_int_exact(self) -> None:
        self.assertTrue(score("int", 42, 42))
        self.assertTrue(score("int", "42", 42))
        self.assertTrue(score("int", "The answer is 42.", 42))
        self.assertFalse(score("int", 41, 42))
        self.assertFalse(score("int", "no number here", 42))

    def test_float_tolerance(self) -> None:
        self.assertTrue(score("float", 100.0, 100.0))
        self.assertTrue(score("float", 100.5, 100.0))  # within 1%
        self.assertTrue(score("float", "100.50 USD", 100.0))
        self.assertFalse(score("float", 105.0, 100.0))  # 5% off
        self.assertTrue(score("float", "0.27", 0.27))

    def test_string_substring(self) -> None:
        self.assertTrue(score("string", "Tokyo", "Tokyo"))
        self.assertTrue(score("string", "Tokyo, Japan", "Tokyo"))
        self.assertTrue(score("string", "tokyo", "Tokyo"))
        self.assertFalse(score("string", "Paris", "Tokyo"))

    def test_set_equality(self) -> None:
        self.assertTrue(score("set", ["a", "b"], ["a", "b"]))
        self.assertTrue(score("set", ["b", "a"], ["a", "b"]))
        self.assertTrue(score("set", "a, b", ["a", "b"]))
        self.assertTrue(score("set", "A, B", ["a", "b"]))
        self.assertFalse(score("set", ["a"], ["a", "b"]))


class TestCaseFile(unittest.TestCase):
    """Verify the built case file is valid; only runs if the file exists."""

    @classmethod
    def setUpClass(cls) -> None:
        path = pathlib.Path(__file__).resolve().parents[1] / "results" / "analytical_cases.json"
        if not path.exists():
            raise unittest.SkipTest("analytical_cases.json not built yet")
        cls.data = json.load(open(path))

    def test_count(self) -> None:
        self.assertEqual(len(self.data["cases"]), 100)

    def test_unique_case_ids(self) -> None:
        ids = [c["case_id"] for c in self.data["cases"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_each_type_has_ten_cases(self) -> None:
        from collections import Counter
        c = Counter(case["type"] for case in self.data["cases"])
        for t, n in c.items():
            self.assertEqual(n, 10, f"type {t} has {n} cases, expected 10")

    def test_records_match_n(self) -> None:
        for case in self.data["cases"]:
            self.assertEqual(len(case["records"]), case["n"], f"{case['case_id']}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
