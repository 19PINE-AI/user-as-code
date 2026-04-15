"""Tests for cross-domain constraints (finance, health)."""

import sys
from pathlib import Path

PROJECT_PATH = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(Path(PROJECT_PATH).parent))


def _fresh_check(constraint_module_name: str):
    """Run a constraint check with a clean module cache."""
    to_remove = [k for k in sys.modules if k.startswith("domains")]
    for k in to_remove:
        del sys.modules[k]

    if constraint_module_name == "financial_authorization":
        from jessica_thompson.constraints.financial_authorization import check
    elif constraint_module_name == "health_safety":
        from jessica_thompson.constraints.health_safety import check
    else:
        raise ValueError(f"Unknown constraint: {constraint_module_name}")
    return check(PROJECT_PATH)


class TestFinancialAuthorization:
    def test_conflicting_wire_transfer_detected(self):
        """Patricia's $15k transfer has conflicting destination instructions."""
        alerts = _fresh_check("financial_authorization")
        assert len(alerts) >= 1, "Expected at least one financial conflict alert"

    def test_conflict_mentions_both_banks(self):
        alerts = _fresh_check("financial_authorization")
        wire_alerts = [a for a in alerts if "Patricia" in a["message"]]
        assert len(wire_alerts) == 1
        msg = wire_alerts[0]["message"]
        assert "Bank of America" in msg
        assert "Wells Fargo" in msg

    def test_conflict_severity_is_critical(self):
        alerts = _fresh_check("financial_authorization")
        for alert in alerts:
            assert alert["severity"] == "critical"

    def test_conflict_source(self):
        alerts = _fresh_check("financial_authorization")
        for alert in alerts:
            assert alert["source"] == "financial_authorization"


class TestHealthSafety:
    def test_penicillin_allergy_amoxicillin_conflict(self):
        """Amoxicillin is a penicillin-class drug; Jessica is allergic."""
        alerts = _fresh_check("health_safety")
        amox_alerts = [a for a in alerts if "Amoxicillin" in a["message"]]
        assert len(amox_alerts) >= 1, "Expected amoxicillin-penicillin allergy alert"

    def test_cetirizine_does_not_trigger(self):
        """Cetirizine (antihistamine) should NOT conflict with any allergy."""
        alerts = _fresh_check("health_safety")
        cet_alerts = [a for a in alerts if "Cetirizine" in a["message"]]
        assert len(cet_alerts) == 0, "Cetirizine should not trigger an alert"

    def test_alert_mentions_prescriber(self):
        alerts = _fresh_check("health_safety")
        amox_alerts = [a for a in alerts if "Amoxicillin" in a["message"]]
        assert "Dr. Robert Chen" in amox_alerts[0]["message"]

    def test_health_alert_severity(self):
        alerts = _fresh_check("health_safety")
        for alert in alerts:
            assert alert["severity"] == "critical"

    def test_health_alert_source(self):
        alerts = _fresh_check("health_safety")
        for alert in alerts:
            assert alert["source"] == "health_safety"
