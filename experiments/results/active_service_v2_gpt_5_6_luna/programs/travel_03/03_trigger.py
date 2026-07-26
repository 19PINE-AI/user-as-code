from datetime import date

STATE = {
    "schengen_visa": {
        "type": "single-entry",
        "valid_from": "2024-10-01",
        "valid_until": "2024-12-31"
    },
    "completed_trip": {
        "destination": "Paris",
        "returned_on": "2024-11-05",
        "duration": "one week"
    },
    "tentative_trip": {
        "destination": "Berlin",
        "start_date": "2024-12-28",
        "end_date": "2025-01-02",
        "occasion": "New Year's Eve",
        "status": "considering"
    }
}


def check_constraints(current_time):
    today = date.fromisoformat(current_time)
    alerts = []

    trip = STATE["tentative_trip"]
    visa = STATE["schengen_visa"]
    trip_start = date.fromisoformat(trip["start_date"])
    trip_end = date.fromisoformat(trip["end_date"])
    visa_end = date.fromisoformat(visa["valid_until"])
    session_date = date(2024, 12, 1)

    if (
        today >= session_date
        and today <= trip_end
        and trip_start <= trip_end
        and trip_end > visa_end
    ):
        alerts.append({
            "severity": "warning",
            "type": "visa_validity_conflict",
            "message": (
                "The tentative Berlin trip is dated December 28, 2024 to "
                "January 2, 2025, but the Schengen visa is valid only through "
                "December 31, 2024."
            )
        })

    return alerts
