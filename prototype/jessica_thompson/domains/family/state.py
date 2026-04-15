from datetime import date
from .schema import FamilyMember, Relationship

family_members = [
    FamilyMember(
        first_name="James",
        last_name="Thompson",
        relationship=Relationship.SPOUSE,
        date_of_birth=date(1986, 7, 22),
        notes="Works as a software engineer at Stripe",
    ),
    FamilyMember(
        first_name="Sarah",
        last_name="Thompson",
        relationship=Relationship.CHILD,
        date_of_birth=date(2016, 11, 3),
        notes="8 years old, attends Presidio Hill School (3rd grade)",
        medical_notes=["Eczema - uses CeraVe moisturizer and hydrocortisone cream"],
    ),
    FamilyMember(
        first_name="Patricia",
        last_name="Williams",
        relationship=Relationship.PARENT,
        date_of_birth=date(1960, 5, 14),
        notes="Jessica's mother, lives in Portland, OR",
    ),
]
