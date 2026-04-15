from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Allergy:
    allergen: str
    severity: str  # "mild", "moderate", "severe", "life-threatening"
    reaction: str
    drug_class: Optional[str] = None  # for drug allergies, the broader class


@dataclass
class Medication:
    name: str
    dosage: str
    frequency: str
    prescriber: str
    start_date: date
    drug_class: Optional[str] = None
    notes: str = ""


@dataclass
class MedicalProfile:
    blood_type: str
    allergies: list[Allergy] = field(default_factory=list)
    current_medications: list[Medication] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    primary_care_physician: str = ""
    emergency_contact: str = ""
