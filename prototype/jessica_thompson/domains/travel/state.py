from datetime import date
from .schema import PassportInfo, Trip, SeatPreference, TravelProfile

passport = PassportInfo(
    number="AB1234567",
    country="US",
    issue_date=date(2015, 2, 18),
    expiry_date=date(2025, 2, 18),
    full_name="Jessica Marie Thompson",
)

trips = [
    Trip(
        destination="Tokyo",
        country="JP",
        departure_date=date(2025, 1, 15),
        return_date=date(2025, 1, 25),
        flight_number="JAL-9823",
        is_international=True,
        duration_hours=11.5,
        notes="Business trip, meetings in Shibuya",
    ),
    Trip(
        destination="Mexico City",
        country="MX",
        departure_date=date(2025, 3, 10),
        return_date=date(2025, 3, 17),
        flight_number="AA-4561",
        is_international=True,
        duration_hours=4.5,
        notes="Vacation with James",
    ),
]

travel_profile = TravelProfile(
    seat_preferences=[
        SeatPreference(
            preference="window",
            condition="Japan routes, always",
        ),
        SeatPreference(
            preference="aisle",
            condition="flights > 6 hours",
        ),
        SeatPreference(
            preference="window",
            condition="flights <= 6 hours (default)",
        ),
    ],
    frequent_flyer_programs=["JAL Mileage Bank", "AAdvantage"],
    preferred_airlines=["JAL", "American Airlines"],
    meal_preference="no peanuts",
)
