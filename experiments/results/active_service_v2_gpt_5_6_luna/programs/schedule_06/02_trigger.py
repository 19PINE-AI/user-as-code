STATE = {
    "travel": {
        "destination": "Costa Rica",
        "start_date": "2024-12-20",
        "end_date": "2025-01-03",
        "status": "booked"
    },
    "appointments": [
        {
            "type": "plumbing repair",
            "location": "upstairs bathroom",
            "date": "2024-12-27",
            "start_time": "10:00",
            "end_time": "14:00",
            "status": "confirmed",
            "user_accepted": True
        }
    ]
}


def check_constraints(current_time):
    today = datetime.date.fromisoformat(current_time)
    alerts = []

    travel = STATE["travel"]
    appointment = STATE["appointments"][0]

    travel_start = datetime.date.fromisoformat(travel["start_date"])
    travel_end = datetime.date.fromisoformat(travel["end_date"])
    appointment_date = datetime.date.fromisoformat(appointment["date"])

    if (
        appointment["status"] == "confirmed"
        and travel["status"] == "booked"
        and travel_start <= appointment_date <= travel_end
        and today <= appointment_date
    ):
        alerts.append({
            "severity": "warning",
            "type": "scheduling_conflict",
            "message": (
                "The confirmed upstairs bathroom plumbing appointment on "
                "2024-12-27 from 10:00 to 14:00 overlaps with the booked "
                "Costa Rica trip from 2024-12-20 through 2025-01-03."
            )
        })

    return alerts
