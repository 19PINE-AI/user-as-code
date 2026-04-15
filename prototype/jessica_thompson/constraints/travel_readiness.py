"""
Travel-readiness constraint.

Checks that the user's passport has at least 180 days of validity
remaining before the departure date of every international trip.
Many countries enforce a 6-month passport validity rule.
"""

import importlib
import sys
from datetime import timedelta
from pathlib import Path


def check(project_path: str) -> list[dict]:
    """Return alerts for any trip where passport validity is insufficient."""
    alerts: list[dict] = []

    project = Path(project_path)
    sys.path.insert(0, str(project.parent))

    try:
        # Dynamically load travel state
        spec_state = importlib.util.spec_from_file_location(
            "travel_state", project / "domains" / "travel" / "state.py"
        )
        travel_state = importlib.util.module_from_spec(spec_state)

        # Need schema available for state to import from
        spec_schema = importlib.util.spec_from_file_location(
            "travel_schema", project / "domains" / "travel" / "schema.py"
        )
        travel_schema = importlib.util.module_from_spec(spec_schema)
        sys.modules["travel_schema"] = travel_schema
        spec_schema.loader.exec_module(travel_schema)

        # Patch the relative import: state.py does `from .schema import ...`
        # We handle this by making a temporary package structure.
        pkg_name = "domains.travel"
        pkg_parts = pkg_name.split(".")

        # Create domains package if needed
        if "domains" not in sys.modules:
            import types
            domains_pkg = types.ModuleType("domains")
            domains_pkg.__path__ = [str(project / "domains")]
            domains_pkg.__package__ = "domains"
            sys.modules["domains"] = domains_pkg

        if pkg_name not in sys.modules:
            import types
            travel_pkg = types.ModuleType(pkg_name)
            travel_pkg.__path__ = [str(project / "domains" / "travel")]
            travel_pkg.__package__ = pkg_name
            sys.modules[pkg_name] = travel_pkg

        # Register schema under the package so `from .schema import ...` works
        sys.modules[f"{pkg_name}.schema"] = travel_schema

        spec_state = importlib.util.spec_from_file_location(
            f"{pkg_name}.state",
            project / "domains" / "travel" / "state.py",
            submodule_search_locations=[],
        )
        travel_state = importlib.util.module_from_spec(spec_state)
        travel_state.__package__ = pkg_name
        spec_state.loader.exec_module(travel_state)

        passport = travel_state.passport
        trips = travel_state.trips
        min_validity = timedelta(days=180)

        for trip in trips:
            if not trip.is_international:
                continue

            days_remaining = (passport.expiry_date - trip.departure_date).days
            if days_remaining < 180:
                alerts.append({
                    "severity": "critical",
                    "source": "travel_readiness",
                    "domain": "travel",
                    "message": (
                        f"Passport {passport.number} expires {passport.expiry_date.isoformat()} "
                        f"-- only {days_remaining} days before {trip.destination} trip "
                        f"on {trip.departure_date.isoformat()} (requires 180-day validity). "
                        f"Flight {trip.flight_number} is at risk."
                    ),
                })
    finally:
        sys.path.pop(0)

    return alerts
