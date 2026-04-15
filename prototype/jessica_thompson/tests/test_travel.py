"""Tests for the travel_readiness constraint."""

import sys
from pathlib import Path

# Ensure the project root is on the path
PROJECT_PATH = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(Path(PROJECT_PATH).parent))


def _fresh_check():
    """Run the travel readiness check with a clean module cache."""
    # Clear cached domain modules to ensure fresh loads
    to_remove = [k for k in sys.modules if k.startswith("domains")]
    for k in to_remove:
        del sys.modules[k]

    from jessica_thompson.constraints.travel_readiness import check
    return check(PROJECT_PATH)


class TestTravelReadiness:
    def test_passport_expiry_alerts_exist(self):
        """Jessica's passport expires 2025-02-18.  Both trips should trigger."""
        alerts = _fresh_check()
        assert len(alerts) > 0, "Expected at least one passport-expiry alert"

    def test_tokyo_trip_flagged(self):
        """Tokyo trip (Jan 15) is only 34 days before passport expiry."""
        alerts = _fresh_check()
        tokyo_alerts = [a for a in alerts if "Tokyo" in a["message"]]
        assert len(tokyo_alerts) == 1
        assert tokyo_alerts[0]["severity"] == "critical"

    def test_mexico_trip_flagged(self):
        """Mexico City trip (Mar 10) is AFTER passport expiry -- must flag."""
        alerts = _fresh_check()
        mexico_alerts = [a for a in alerts if "Mexico" in a["message"]]
        assert len(mexico_alerts) == 1
        assert mexico_alerts[0]["severity"] == "critical"

    def test_alert_contains_flight_number(self):
        alerts = _fresh_check()
        for alert in alerts:
            assert "JAL" in alert["message"] or "AA" in alert["message"]

    def test_alert_source_is_correct(self):
        alerts = _fresh_check()
        for alert in alerts:
            assert alert["source"] == "travel_readiness"
