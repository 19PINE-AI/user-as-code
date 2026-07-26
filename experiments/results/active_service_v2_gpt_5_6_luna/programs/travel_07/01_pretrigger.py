from datetime import date

STATE = {
    "visa": {
        "country": "Australia",
        "status": "applied",
        "application_date": "2024-10-30",
        "valid_from": "2024-12-01",
        "valid_until": "2025-05-31",
        "source": "agent-stated"
    }
}

def check_constraints(current_time):
    date.fromisoformat(current_time)

    visa = STATE["visa"]
    valid_from = date.fromisoformat(visa["valid_from"])
    valid_until = date.fromisoformat(visa["valid_until"])

    if valid_from > valid_until:
        return [{
            "severity": "high",
            "type": "invalid_date_window",
            "message": "The stated Australian visa validity window is invalid because its start date is after its end date."
        }]

    return []
