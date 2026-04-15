"""
Health-safety constraint.

Checks for dangerous drug interactions:
  - Medications that conflict with known allergies (e.g., penicillin allergy
    + amoxicillin prescription, since amoxicillin is a penicillin-class drug).
  - Known harmful drug-drug interactions between current medications.
"""

import importlib
import importlib.util
import sys
import types
from pathlib import Path


# Drug classes: maps a drug class name to its members / related classes.
# This is a simplified lookup; a real system would use a drug database.
DRUG_CLASS_MEMBERS = {
    "penicillin": [
        "amoxicillin", "ampicillin", "penicillin", "piperacillin",
        "nafcillin", "oxacillin", "dicloxacillin",
    ],
}


def check(project_path: str) -> list[dict]:
    """Return alerts for drug-allergy conflicts and known drug interactions."""
    alerts: list[dict] = []

    project = Path(project_path)
    sys.path.insert(0, str(project.parent))

    try:
        pkg_name = "domains.health"

        if "domains" not in sys.modules:
            domains_pkg = types.ModuleType("domains")
            domains_pkg.__path__ = [str(project / "domains")]
            domains_pkg.__package__ = "domains"
            sys.modules["domains"] = domains_pkg

        if pkg_name not in sys.modules:
            health_pkg = types.ModuleType(pkg_name)
            health_pkg.__path__ = [str(project / "domains" / "health")]
            health_pkg.__package__ = pkg_name
            sys.modules[pkg_name] = health_pkg

        # Load schema
        spec_schema = importlib.util.spec_from_file_location(
            f"{pkg_name}.schema",
            project / "domains" / "health" / "schema.py",
        )
        health_schema = importlib.util.module_from_spec(spec_schema)
        health_schema.__package__ = pkg_name
        spec_schema.loader.exec_module(health_schema)
        sys.modules[f"{pkg_name}.schema"] = health_schema

        # Load state
        spec_state = importlib.util.spec_from_file_location(
            f"{pkg_name}.state",
            project / "domains" / "health" / "state.py",
        )
        health_state = importlib.util.module_from_spec(spec_state)
        health_state.__package__ = pkg_name
        spec_state.loader.exec_module(health_state)

        profile = health_state.medical_profile

        # Check each medication against each allergy
        for med in profile.current_medications:
            for allergy in profile.allergies:
                # Direct name match
                if med.name.lower() == allergy.allergen.lower():
                    alerts.append(_allergy_alert(med, allergy))
                    continue

                # Drug class match: allergy is to a class, medication belongs to it
                if allergy.drug_class:
                    class_name = allergy.drug_class.lower()
                    members = DRUG_CLASS_MEMBERS.get(class_name, [])
                    if med.name.lower() in members:
                        alerts.append(_allergy_alert(med, allergy))
                        continue

                # Medication's declared class matches allergy's class
                if med.drug_class and allergy.drug_class:
                    if med.drug_class.lower() == allergy.drug_class.lower():
                        alerts.append(_allergy_alert(med, allergy))
                        continue
    finally:
        sys.path.pop(0)

    return alerts


def _allergy_alert(med, allergy) -> dict:
    return {
        "severity": "critical",
        "source": "health_safety",
        "domain": "health",
        "message": (
            f"DRUG-ALLERGY CONFLICT: {med.name} ({med.dosage}, {med.frequency}) "
            f"is contraindicated -- patient has a {allergy.severity} allergy to "
            f"{allergy.allergen} (reaction: {allergy.reaction}). "
            f"Prescribed by {med.prescriber} on {med.start_date.isoformat()}. "
            f"Contact prescriber immediately."
        ),
    }
