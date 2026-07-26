"""Integrity tests for the regression-tuned Active Service v3 runner."""
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
import run_active_service_v3 as v3


class FakeGenerator:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)

    def generate(self, system_prompt: str, user_prompt: str) -> dict:
        del system_prompt, user_prompt
        return {
            "text": self.responses.pop(0),
            "latency_seconds": 0.0,
            "usage": {"requests": 1},
        }


def encoded(value: dict) -> str:
    return json.dumps(value)


class RunnerTests(unittest.TestCase):
    def test_prompt_contains_no_frozen_rubric_or_expected_alert(self) -> None:
        protocol = v2.load_protocol()
        scenarios = v2.load_scenario_map(
            v2.ROOT / protocol["source_suite"]["path"]
        )
        for scenario_id in protocol["eligible_ids"]:
            scenario = scenarios[scenario_id]
            sessions = v2.scenario_sessions(scenario)
            for index, session in enumerate(sessions):
                prompt = v3.IR_UPDATE_TEMPLATE.format(
                    timestamp=session["timestamp"],
                    history=v2.render_history(sessions[: index + 1]),
                )
                self.assertNotIn(scenario["expected_alert"]["message"], prompt)
                self.assertNotIn(scenario["trigger_session"]["description"], prompt)

    def test_structural_failure_is_retried_with_feedback(self) -> None:
        valid = {"state": {"fact": "kept"}, "constraints": []}
        generator = FakeGenerator(["not json", encoded(valid)])
        ir, attempts = v3.generate_valid_ir(generator, "2024-01-01", "history")
        self.assertEqual(valid, ir)
        self.assertEqual(2, len(attempts))
        self.assertIn("error", attempts[0])
        self.assertEqual(valid, attempts[1]["ir"])

    def test_case_has_no_prealert_then_passes_trigger(self) -> None:
        dormant = {
            "state": {"limit": 3000},
            "constraints": [],
        }
        active = {
            "state": {"limit": 3000, "proposal": 4200},
            "constraints": [
                {
                    "id": "card_limit_conflict",
                    "severity": "high",
                    "type": "financial_conflict",
                    "message_template": (
                        "$4,200 exceeds the $3,000 corporate card limit, creating a conflict. "
                        "Obtain VP approval or use an alternative payment."
                    ),
                    "active_from": "2025-01-15",
                    "active_until": None,
                    "deadline": None,
                    "deadline_anchor": None,
                    "deadline_offset_days": None,
                }
            ],
        }
        sessions = [
            {"session_id": "1", "timestamp": "2024-07-10", "user_text": "limit"},
            {"session_id": "2", "timestamp": "2025-01-15", "user_text": "proposal"},
        ]
        rubric = {
            "required": {
                "cost": [r"\$?4[,]?200"],
                "limit": [r"\$?3[,]?000"],
                "comparison": ["exceed"],
                "resolution": ["VP approval", "alternative payment"],
            }
        }
        generator = FakeGenerator([encoded(dormant), encoded(active)])
        with tempfile.TemporaryDirectory() as directory:
            result = v3.run_uac_case(
                "finance_test",
                sessions,
                rubric,
                generator,
                Path(directory),
            )
        self.assertTrue(result["passed"])
        self.assertEqual(0, result["pretrigger_alert_count"])


class FinalArtifactTests(unittest.TestCase):
    def test_checked_in_full_regression_replays_to_seventeen(self) -> None:
        import validate_active_service_v3 as validator

        result_dir = (
            v2.ROOT
            / "experiments"
            / "results"
            / "active_service_v3_gpt_5_6_luna"
        )
        if not result_dir.is_dir():
            self.skipTest("final v3 result artifact is not present")
        report = validator.validate_result_dir(result_dir)
        self.assertEqual(17, report["case_count"])
        self.assertEqual(17, report["passed"])


if __name__ == "__main__":
    unittest.main()
