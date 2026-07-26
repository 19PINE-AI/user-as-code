from datetime import date

STATE = {
    "car_service": {
        "date": "2024-11-04",
        "drop_off": "08:00",
        "pickup": "after 17:00",
        "duration": "full day",
        "established_on": "2024-10-05"
    },
    "airport_pickup": {
        "date": "2024-11-04",
        "flight_lands": "14:00",
        "passengers": "parents",
        "needs_drive": True,
        "established_on": "2024-10-20"
    }
}


def check_constraints(current_time):
    current = date.fromisoformat(current_time)
    service = STATE["car_service"]
    pickup = STATE["airport_pickup"]
    service_date = date.fromisoformat(service["date"])
    pickup_date = date.fromisoformat(pickup["date"])
    service_recorded = date.fromisoformat(service["established_on"])
    pickup_recorded = date.fromisoformat(pickup["established_on"])

    if (
        service_recorded <= current
        and pickup_recorded <= current
        and service_date == pickup_date
        and current <= service_date
        and pickup["needs_drive"]
    ):
        return [{
            "severity": "high",
            "type": "scheduling_conflict",
            "message": (
                "The car is unavailable for its full-day major service on "
                "2024-11-04 from 08:00 until after 17:00, but you need to "
                "drive to the airport that day for your parents' 14:00 arrival."
            )
        }]

    return []
