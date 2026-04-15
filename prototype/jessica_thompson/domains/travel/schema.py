from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class PassportInfo:
    number: str
    country: str
    issue_date: date
    expiry_date: date
    full_name: str


@dataclass
class SeatPreference:
    """Seat preference rule with optional conditions."""
    preference: str  # "aisle" or "window"
    condition: Optional[str] = None  # human-readable condition description

    def __str__(self) -> str:
        if self.condition:
            return f"{self.preference} ({self.condition})"
        return self.preference


@dataclass
class Trip:
    destination: str
    country: str
    departure_date: date
    return_date: date
    flight_number: str
    is_international: bool
    duration_hours: float = 0.0
    notes: str = ""


@dataclass
class TravelProfile:
    seat_preferences: list[SeatPreference] = field(default_factory=list)
    frequent_flyer_programs: list[str] = field(default_factory=list)
    preferred_airlines: list[str] = field(default_factory=list)
    meal_preference: str = "standard"
