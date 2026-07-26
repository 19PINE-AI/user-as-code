from datetime import date

STATE = {
    "board_meeting": {
        "recurrence": "every Tuesday",
        "start_time": "14:00",
        "end_time": "16:00",
        "importance": "absolutely cannot miss"
    },
    "proposed_flight": {
        "destination": "Chicago",
        "departure_date": "2025-01-21",
        "departure_time": "14:30",
        "status": "not booked"
    }
}

def check_constraints(current_time):
    current_date = date.fromisoformat(current_time)
    flight_date = date.fromisoformat(STATE["proposed_flight"]["departure_date"])

    if (
        STATE["proposed_flight"]["status"] == "not booked"
        and current_date <= flight_date
        and flight_date.weekday() == 1
    ):
        return [{
            "severity": "high",
            "type": "conflict",
            "message": "The proposed Chicago flight departs Tuesday, January 21 at 2:30 PM, overlapping the Tuesday board meeting from 2:00 PM to about 4:00 PM, which you said you absolutely cannot miss."
        }]

    return []
