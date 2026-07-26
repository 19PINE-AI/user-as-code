STATE = {
    "family": {
        "Emma": {
            "achievement": "Got the lead role in her school play"
        }
    },
    "commitments": [
        {
            "person": "Emma",
            "commitment": "Be in the front row for her school play performance",
            "date": "2024-12-12",
            "time": "18:00"
        }
    ],
    "events": [
        {
            "name": "Emma's school play performance",
            "date": "2024-12-12",
            "time": "18:00"
        },
        {
            "name": "Client meeting in New York",
            "location": "New York",
            "travel_start": "2024-12-11",
            "travel_end": "2024-12-13"
        }
    ],
    "requests": [
        {
            "request": "Find hotels near Midtown",
            "associated_event": "Client meeting in New York",
            "location": "Midtown"
        }
    ]
}


def check_constraints(current_time):
    current = __import__("datetime").date.fromisoformat(current_time)
    alerts = []

    performance = __import__("datetime").date.fromisoformat("2024-12-12")
    if current <= performance and (performance - current).days <= 7:
        alerts.append({
            "severity": "info",
            "type": "upcoming_commitment",
            "message": "Emma's school play performance is on 2024-12-12 at 18:00, and you promised to be in the front row."
        })

    return alerts
