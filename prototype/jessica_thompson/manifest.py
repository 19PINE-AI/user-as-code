"""
manifest.py — Compact index for the Jessica Thompson user project.

This file is always loaded into the agent's context window.
It provides a quick map of all domains, their schemas, and any
active alerts so the agent knows what data is available and what
needs attention without loading every state file.
"""

DOMAINS = {
    "identity": {
        "path": "domains/identity",
        "schemas": ["PersonalInfo", "ContactInfo"],
        "summary": "Jessica Thompson, DOB 1988-03-15, San Francisco CA",
    },
    "travel": {
        "path": "domains/travel",
        "schemas": ["Trip", "PassportInfo", "SeatPreference", "TravelProfile"],
        "summary": "Passport AB1234567 (exp 2025-02-18), 2 upcoming trips",
    },
    "finance": {
        "path": "domains/finance",
        "schemas": ["Account", "WireTransfer"],
        "summary": "Chase checking, Schwab investment; 1 pending wire ($15k)",
    },
    "vehicles": {
        "path": "domains/vehicles",
        "schemas": ["Vehicle", "MaintenanceSchedule"],
        "summary": "2020 Honda Accord (service due), 2023 Tesla Model 3",
    },
    "health": {
        "path": "domains/health",
        "schemas": ["MedicalProfile", "Allergy", "Medication"],
        "summary": "Allergies: peanuts, penicillin. Rx: cetirizine, amoxicillin",
    },
    "family": {
        "path": "domains/family",
        "schemas": ["FamilyMember", "Relationship"],
        "summary": "Husband James, daughter Sarah (8), mother Patricia",
    },
}

# Active alerts are populated by running constraints (see runner.py).
# This list is updated after each constraint check cycle.
ACTIVE_ALERTS: list[dict] = []
