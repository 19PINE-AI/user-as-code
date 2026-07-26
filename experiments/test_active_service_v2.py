"""Local integrity tests for the frozen Active Service v2 protocol."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

import run_active_service_v2 as v2


class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.protocol = v2.load_protocol()
        source = v2.ROOT / cls.protocol["source_suite"]["path"]
        cls.scenarios = v2.load_scenario_map(source)

    def test_partition_and_rubric_counts(self) -> None:
        eligible = set(self.protocol["eligible_ids"])
        excluded = set(self.protocol["exclusions"])
        self.assertEqual(18, len(eligible))
        self.assertEqual(40, len(self.scenarios))
        self.assertFalse(eligible & excluded)
        self.assertEqual(set(self.scenarios), eligible | excluded)
        self.assertEqual(eligible, set(self.protocol["rubrics"]))

    def test_frozen_krill_model_panels(self) -> None:
        self.assertEqual(
            ["gpt-5.6-luna", "gemini-3-flash-preview"],
            [model["name"] for model in self.protocol["models"]],
        )
        self.assertTrue(
            all(model["api"] == "Krill AI API" for model in self.protocol["models"])
        )

    def test_user_only_extraction_never_leaks_assistant_continuations(self) -> None:
        for scenario_id in self.protocol["eligible_ids"]:
            sessions = v2.scenario_sessions(self.scenarios[scenario_id])
            self.assertGreaterEqual(len(sessions), 2)
            for session in sessions:
                self.assertTrue(session["user_text"])
                self.assertNotIn("Assistant:", session["user_text"])
                original = next(
                    candidate
                    for candidate in self.scenarios[scenario_id]["sessions"]
                    if str(candidate["session_id"]) == session["session_id"]
                )
                assistant_text = str(original.get("conversation", "")).split("Assistant:", 1)
                if len(assistant_text) == 2:
                    self.assertNotIn(assistant_text[1].strip(), session["user_text"])

    def test_trigger_is_actual_final_user_session(self) -> None:
        for scenario_id in self.protocol["eligible_ids"]:
            scenario = self.scenarios[scenario_id]
            sessions = v2.scenario_sessions(scenario)
            self.assertEqual(
                str(scenario["trigger_session"]["session_id"]),
                sessions[-1]["session_id"],
            )
            self.assertEqual(
                v2.user_only_text(scenario["sessions"][-1]),
                sessions[-1]["user_text"],
            )

    def test_authored_gold_satisfies_every_frozen_rubric(self) -> None:
        for scenario_id in self.protocol["eligible_ids"]:
            expected = self.scenarios[scenario_id]["expected_alert"]["message"]
            score = v2.score_text(expected, self.protocol["rubrics"][scenario_id])
            missing = [
                group for group, value in score["groups"].items() if not value["passed"]
            ]
            self.assertTrue(score["passed"], f"{scenario_id}: missing {missing}")

    def test_generic_warning_does_not_pass_any_rubric(self) -> None:
        text = "Warning: there may be a relevant issue. Please check your records."
        for scenario_id in self.protocol["eligible_ids"]:
            self.assertFalse(
                v2.score_text(text, self.protocol["rubrics"][scenario_id])["passed"],
                scenario_id,
            )


class RetrievalTests(unittest.TestCase):
    def test_lexical_top_one_and_tie_break(self) -> None:
        history = [
            {"session_id": "1", "user_text": "passport renewed yesterday"},
            {"session_id": "2", "user_text": "board meeting every Tuesday"},
        ]
        selected, scores = v2.lexical_top_one(history, "Tuesday flight")
        self.assertEqual("2", selected["session_id"])
        self.assertGreater(scores[1]["score"], scores[0]["score"])

        tied, tied_scores = v2.lexical_top_one(history, "unseen vocabulary")
        self.assertEqual("1", tied["session_id"])
        self.assertEqual(0.0, tied_scores[0]["score"])
        self.assertEqual(0.0, tied_scores[1]["score"])


class GeneratedProgramTests(unittest.TestCase):
    SAFE_SOURCE = """from datetime import date
STATE = {"deadline": "2024-10-01"}

def check_constraints(current_time):
    deadline = date.fromisoformat(STATE["deadline"])
    now = date.fromisoformat(current_time)
    remaining = (deadline - now).days
    if 0 <= remaining <= 3:
        return [{
            "severity": "warning",
            "type": "deadline",
            "message": f"Deadline is in {remaining} days on October 1."
        }]
    return []
"""

    def test_safe_source_validates_and_executes(self) -> None:
        validation = v2.validate_generated_source(self.SAFE_SOURCE)
        self.assertTrue(validation["valid"])
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "candidate.py"
            source_path.write_text(self.SAFE_SOURCE, encoding="utf-8")
            before = v2.execute_generated_source(source_path, "2024-09-20")
            trigger = v2.execute_generated_source(source_path, "2024-09-28")
        self.assertEqual([], before["alerts"])
        self.assertEqual(1, len(trigger["alerts"]))
        self.assertEqual({"deadline": "2024-10-01"}, trigger["state"])

    def test_source_extraction_handles_fence_without_accepting_prose(self) -> None:
        fenced = f"Here is the module:\n```python\n{self.SAFE_SOURCE}```"
        self.assertEqual(self.SAFE_SOURCE.strip(), v2.extract_python_source(fenced).strip())

    def test_unsafe_import_is_rejected(self) -> None:
        unsafe = "import os\nSTATE = {}\ndef check_constraints(current_time):\n return []\n"
        with self.assertRaisesRegex(v2.GeneratedCodeError, "import not allowed"):
            v2.validate_generated_source(unsafe)

    def test_dynamic_code_and_dunder_access_are_rejected(self) -> None:
        dynamic = "STATE = {}\ndef check_constraints(current_time):\n return eval('[]')\n"
        with self.assertRaisesRegex(v2.GeneratedCodeError, "call is not allowed"):
            v2.validate_generated_source(dynamic)
        reflective = "STATE = {}\ndef check_constraints(current_time):\n return STATE.__class__\n"
        with self.assertRaisesRegex(v2.GeneratedCodeError, "attribute is not allowed"):
            v2.validate_generated_source(reflective)

    def test_wall_clock_and_unbounded_while_are_rejected(self) -> None:
        clock = (
            "from datetime import date\nSTATE = {}\n"
            "def check_constraints(current_time):\n return [date.today()]\n"
        )
        with self.assertRaisesRegex(v2.GeneratedCodeError, "attribute is not allowed"):
            v2.validate_generated_source(clock)
        loop = "STATE = {}\ndef check_constraints(current_time):\n while True:\n  pass\n"
        with self.assertRaisesRegex(v2.GeneratedCodeError, "While is not allowed"):
            v2.validate_generated_source(loop)

    def test_sandbox_rejects_invalid_alert_shape(self) -> None:
        invalid = "STATE = {}\ndef check_constraints(current_time):\n return ['not a dict']\n"
        v2.validate_generated_source(invalid)
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "candidate.py"
            source_path.write_text(invalid, encoding="utf-8")
            with self.assertRaisesRegex(v2.GeneratedCodeError, "sandbox exited"):
                v2.execute_generated_source(source_path, "2024-01-01")


class StatisticsTests(unittest.TestCase):
    def test_wilson_and_exact_mcnemar(self) -> None:
        interval = v2.wilson_interval(9, 10)
        self.assertLess(interval[0], 0.9)
        self.assertGreater(interval[1], 0.9)
        self.assertEqual(1.0, v2.exact_mcnemar_p(0, 0))
        self.assertLess(v2.exact_mcnemar_p(8, 0), 0.05)


if __name__ == "__main__":
    unittest.main()
