from datetime import date

STATE = {
    "recorded_at": "2024-10-28",
    "reservations": [
        {
            "occasion": "anniversary",
            "venue": "Chez Laurent",
            "date": "2024-11-15",
            "declared_weekday": "Saturday",
            "time": "19:00",
            "status": "reserved",
            "description": "special dinner"
        }
    ]
}


def check_constraints(current_time):
    now = date.fromisoformat(current_time)
    alerts = []

    for reservation in STATE["reservations"]:
        recorded_at = date.fromisoformat(STATE["recorded_at"])
        reservation_date = date.fromisoformat(reservation["date"])

        if now < recorded_at:
            continue

        actual_weekday = reservation_date.strftime("%A")
        if actual_weekday != reservation["declared_weekday"]:
            alerts.append({
                "severity": "warning",
                "type": "date_conflict",
                "message": (
                    f"The anniversary reservation at {reservation['venue']} is recorded "
                    f"for {reservation['date']}, which is a {actual_weekday}, not "
                    f"{reservation['declared_weekday']}."
                )
            })

    return alerts
