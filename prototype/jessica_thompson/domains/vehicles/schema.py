from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class MaintenanceSchedule:
    service_type: str  # "oil change", "tire rotation", "inspection", etc.
    due_date: date
    mileage_due: Optional[int] = None
    provider: Optional[str] = None
    notes: str = ""


@dataclass
class Vehicle:
    year: int
    make: str
    model: str
    color: str
    vin: str
    license_plate: str
    current_mileage: int
    maintenance_schedule: list[MaintenanceSchedule] = field(default_factory=list)
