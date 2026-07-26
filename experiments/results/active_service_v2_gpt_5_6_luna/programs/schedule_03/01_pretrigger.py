from datetime import date

STATE = {
    "family": {
        "Emma": {
            "achievement": "got the lead role in her school play"
        }
    },
    "events": [
        {
            "name": "Emma's school play performance",
            "date": "2024-12-12",
            "time": "18:00",
            "commitment": "Be in the front row"
        }
    ]
}

def check_constraints(current_time):
    current = date.fromisoformat(current_time)
    alerts = []

    for event in STATE["events"]:
        event_date = date.fromisoformat(event["date"])
        days_until = (event_date - current).days

        if days_until < 0:
            continue

        if 0 <= days_until <= 7:
            alerts.append({
                "severity": "info",
                "type": "deadline",
                "message": (
                    f"{event['name']} is on {event['date']} at {event['time']}; "
                    f"commitment: {event['commitment']}."
                )
            })

    return alerts
