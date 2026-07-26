from datetime import date

STATE = {
    "visa": {
        "country": "Australia",
        "applied_on": "2024-10-30",
        "valid_from": "2024-12-01",
        "valid_until": "2025-05-31",
        "source": "agent"
    },
    "travel_plan": {
        "destination": "Sydney",
        "flight_date": "2024-11-25",
        "status": "planned",
        "found_cheap_flights": True
    },
    "request": {
        "help_find_hotels": True,
        "requested_on": "2024-11-18"
    }
}


def check_constraints(current_time):
    current = date.fromisoformat(current_time)
    flight_date = date.fromisoformat(STATE["travel_plan"]["flight_date"])
    visa_start = date.fromisoformat(STATE["visa"]["valid_from"])
    visa_end = date.fromisoformat(STATE["visa"]["valid_until"])

    alerts = []

    if (
        STATE["travel_plan"]["status"] == "planned"
        and current <= flight_date
        and flight_date < visa_start
    ):
        alerts.append({
            "severity": "high",
            "type": "date_conflict",
            "message": (
                "The planned Sydney flight is on 2024-11-25, but the Australian "
                "visa is stated to be valid starting 2024-12-01."
            )
        })

    if current > visa_end and current <= flight_date:
        alerts.append({
            "severity": "high",
            "type": "invalid_date_window",
            "message": (
                "The planned Sydney flight is after the stated end of the "
                "Australian visa validity window."
            )
        })

    return alerts
