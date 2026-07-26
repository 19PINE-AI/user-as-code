import calendar
from datetime import date, time

STATE = {
    "reservations": [
        {
            "occasion": "anniversary",
            "venue": "Chez Laurent",
            "date": "2024-11-15",
            "time": "19:00",
            "stated_weekday": "Saturday",
            "booked_on": "2024-10-28"
        },
        {
            "occasion": "dinner with college roommate",
            "venue": "Steakhouse 55",
            "date": "2024-11-15",
            "time": "19:30",
            "booked_on": "2024-11-10"
        }
    ]
}

def check_constraints(current_time):
    current_date = date.fromisoformat(current_time)
    alerts = []

    for reservation in STATE["reservations"]:
        reservation_date = date.fromisoformat(reservation["date"])
        if reservation_date < current_date:
            continue

        actual_weekday = calendar.day_name[reservation_date.weekday()]
        stated_weekday = reservation.get("stated_weekday")
        if stated_weekday and stated_weekday != actual_weekday:
            alerts.append({
                "severity": "high",
                "type": "invalid_date_window",
                "message": (
                    f"{reservation['occasion'].capitalize()} reservation at "
                    f"{reservation['venue']} is recorded for {stated_weekday}, "
                    f"{reservation['date']}, but {reservation['date']} is a "
                    f"{actual_weekday}."
                )
            })

    reservations = [
        r for r in STATE["reservations"]
        if date.fromisoformat(r["date"]) >= current_date
    ]

    for index, first in enumerate(reservations):
        for second in reservations[index + 1:]:
            if first["date"] != second["date"]:
                continue

            first_time = time.fromisoformat(first["time"])
            second_time = time.fromisoformat(second["time"])
            if first_time == second_time or abs(
                (
                    first_time.hour * 60
                    + first_time.minute
                    - second_time.hour * 60
                    - second_time.minute
                )
            ) < 60:
                alerts.append({
                    "severity": "high",
                    "type": "scheduling_conflict",
                    "message": (
                        f"Two dinner reservations are booked on {first['date']}: "
                        f"{first['venue']} at {first['time']} and "
                        f"{second['venue']} at {second['time']}."
                    )
                })

    return alerts
