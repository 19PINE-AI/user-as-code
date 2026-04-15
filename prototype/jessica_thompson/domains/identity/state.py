from datetime import date
from .schema import PersonalInfo, ContactInfo

personal_info = PersonalInfo(
    first_name="Jessica",
    last_name="Thompson",
    date_of_birth=date(1988, 3, 15),
    gender="Female",
    nationality="US",
)

contact_info = ContactInfo(
    email="jessica.thompson@gmail.com",
    phone="+1-415-555-0142",
    address_line1="2847 Divisadero St",
    city="San Francisco",
    state="CA",
    zip_code="94123",
    country="US",
)
