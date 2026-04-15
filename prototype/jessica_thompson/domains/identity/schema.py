from dataclasses import dataclass
from datetime import date


@dataclass
class PersonalInfo:
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str
    nationality: str


@dataclass
class ContactInfo:
    email: str
    phone: str
    address_line1: str
    city: str
    state: str
    zip_code: str
    country: str
