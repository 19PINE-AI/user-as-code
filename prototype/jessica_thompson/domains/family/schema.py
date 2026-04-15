from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class Relationship(Enum):
    SPOUSE = "spouse"
    CHILD = "child"
    PARENT = "parent"
    SIBLING = "sibling"


@dataclass
class FamilyMember:
    first_name: str
    last_name: str
    relationship: Relationship
    date_of_birth: Optional[date] = None
    notes: str = ""
    medical_notes: list[str] = field(default_factory=list)
