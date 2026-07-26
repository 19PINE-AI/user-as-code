from datetime import date, timedelta

STATE = {
    "house_offer": {
        "status": "accepted",
        "accepted_date": "2024-10-25"
    },
    "home_inspection_contingency": {
        "duration_days": 15,
        "start_date": "2024-10-25",
        "deadline_date": "2024-11-09",
        "required_actions": [
            "complete the home inspection",
            "respond within the contingency period"
        ],
        "consequence_if_not_completed_in_period": "waive the right to back out"
    },
    "home_inspection": {
        "inspector_available_date": "2024-11-07",
        "status": "not yet completed"
    }
}


def check_constraints(current_time):
    current = date.fromisoformat(current_time)
    alerts = []

    contingency = STATE["home_inspection_contingency"]
    inspection = STATE["home_inspection"]
    deadline = date.fromisoformat(contingency["deadline_date"])
    inspection_date = date.fromisoformat(inspection["inspector_available_date"])

    if inspection_date > deadline:
        alerts.append({
            "severity": "high",
            "type": "date_conflict",
            "message": (
                "The available home inspection date "
                f"({inspection_date.isoformat()}) is after the inspection contingency "
                f"deadline ({deadline.isoformat()})."
            )
        })

    days_until_deadline = (deadline - current).days
    if 0 <= days_until_deadline <= 7:
        alerts.append({
            "severity": "warning",
            "type": "deadline_approaching",
            "message": (
                f"The home inspection contingency deadline is "
                f"{deadline.isoformat()}, {days_until_deadline} day(s) away. "
                "The inspection and response must be completed within the stated period."
            )
        })

    return alerts
