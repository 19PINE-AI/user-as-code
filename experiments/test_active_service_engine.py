"""Unit tests for the validated Active Service constraint engine."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

import active_service_engine as engine
import run_active_service_v2 as v2


class ConstraintIRTests(unittest.TestCase):
    DEADLINE_IR = {
        "state": {
            "purchase": "espresso machine",
            "return_deadline": "2024-11-01",
        },
        "constraints": [
            {
                "id": "espresso_return_deadline",
                "severity": "warning",
                "type": "deadline",
                "message_template": (
                    "The espresso machine return deadline is {deadline}, "
                    "which is {days_remaining} days away. Initiate the return."
                ),
                "active_from": None,
                "active_until": None,
                "deadline": None,
                "deadline_anchor": "2024-10-02",
                "deadline_offset_days": 30,
            }
        ],
    }

    def test_extracts_fenced_json(self) -> None:
        response = 'Result:\n```json\n{"state": {}, "constraints": []}\n```'
        self.assertEqual(
            {"state": {}, "constraints": []},
            engine.extract_json_object(response),
        )

    def test_rejects_invalid_dates_and_placeholders(self) -> None:
        invalid = {
            "state": {},
            "constraints": [
                {
                    "id": "bad_deadline",
                    "severity": "warning",
                    "type": "deadline",
                    "message_template": "Due in {hours_remaining}",
                    "active_from": "2024-02-30",
                    "active_until": None,
                    "deadline": None,
                    "deadline_anchor": None,
                    "deadline_offset_days": None,
                }
            ],
        }
        with self.assertRaises(engine.ConstraintIRError):
            engine.validate_constraint_ir(invalid)

    def test_deadline_countdown_requires_days_unit(self) -> None:
        invalid = {
            "state": {},
            "constraints": [
                {
                    "id": "missing_countdown_unit",
                    "severity": "warning",
                    "type": "deadline",
                    "message_template": "Due {deadline}; {days_remaining} remain.",
                    "active_from": None,
                    "active_until": None,
                    "deadline": "2024-11-09",
                    "deadline_anchor": None,
                    "deadline_offset_days": None,
                }
            ],
        }
        with self.assertRaisesRegex(engine.ConstraintIRError, "word days"):
            engine.validate_constraint_ir(invalid)

    def test_compiled_deadline_is_dormant_then_dynamic(self) -> None:
        source = engine.compile_constraint_module(self.DEADLINE_IR)
        v2.validate_generated_source(source)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "compiled.py"
            path.write_text(source, encoding="utf-8")
            dormant = v2.execute_generated_source(path, "2024-10-24")
            active = v2.execute_generated_source(path, "2024-10-29")
            expired = v2.execute_generated_source(path, "2024-11-02")
        self.assertEqual([], dormant["alerts"])
        self.assertEqual([], expired["alerts"])
        self.assertEqual(1, len(active["alerts"]))
        self.assertIn("3 days away", active["alerts"][0]["message"])

    def test_compiled_direct_conflict_remains_active(self) -> None:
        ir = {
            "state": {"limit": 3000, "proposal": 4200},
            "constraints": [
                {
                    "id": "card_limit_conflict",
                    "severity": "high",
                    "type": "financial_conflict",
                    "message_template": (
                        "$4,200 exceeds the explicit $3,000 limit, creating a conflict."
                    ),
                    "active_from": "2025-01-15",
                    "active_until": None,
                    "deadline": None,
                    "deadline_anchor": None,
                    "deadline_offset_days": None,
                }
            ],
        }
        source = engine.compile_constraint_module(ir)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "compiled.py"
            path.write_text(source, encoding="utf-8")
            before = v2.execute_generated_source(path, "2025-01-14")
            after = v2.execute_generated_source(path, "2025-02-01")
        self.assertEqual([], before["alerts"])
        self.assertEqual(1, len(after["alerts"]))

    def test_direct_message_requires_explicit_conflict(self) -> None:
        invalid = {
            "state": {},
            "constraints": [
                {
                    "id": "vague_overlap",
                    "severity": "warning",
                    "type": "event_overlap",
                    "message_template": "The two events overlap and need a resolution.",
                    "active_from": "2024-10-01",
                    "active_until": None,
                    "deadline": None,
                    "deadline_anchor": None,
                    "deadline_offset_days": None,
                }
            ],
        }
        with self.assertRaisesRegex(engine.ConstraintIRError, "explicitly say conflict"):
            engine.validate_constraint_ir(invalid)


if __name__ == "__main__":
    unittest.main()
