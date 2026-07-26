from datetime import date

STATE = {
    "airbnb": {
        "listing_created": "2024-09-01",
        "booking": {
            "arrival": "2024-11-15",
            "departure": "2024-11-20",
            "status": "booked"
        }
    },
    "new_house": {
        "closing_date": "2024-11-10",
        "movers": {
            "start_date": "2024-11-14",
            "end_date": "2024-11-15"
        }
    }
}


def check_constraints(current_time):
    current = date.fromisoformat(current_time)
    alerts = []

    closing = date.fromisoformat(STATE["new_house"]["closing_date"])
    days_until_closing = (closing - current).days
    if 0 <= days_until_closing <= 7:
        alerts.append({
            "severity": "info",
            "type": "deadline_approaching",
            "message": "House closing is on 2024-11-10, which is within seven days."
        })

    guest_arrival = date.fromisoformat(STATE["airbnb"]["booking"]["arrival"])
    guest_departure = date.fromisoformat(STATE["airbnb"]["booking"]["departure"])
    movers_start = date.fromisoformat(STATE["new_house"]["movers"]["start_date"])
    movers_end = date.fromisoformat(STATE["new_house"]["movers"]["end_date"])

    overlap_start = max(guest_arrival, movers_start)
    overlap_end = min(guest_departure, movers_end)

    if overlap_start <= overlap_end and current <= overlap_end:
        alerts.append({
            "severity": "warning",
            "type": "schedule_conflict",
            "message": "The Airbnb guest stay from 2024-11-15 through 2024-11-20 overlaps the movers' dates of 2024-11-14 through 2024-11-15 on 2024-11-15."
        })

    return alerts
