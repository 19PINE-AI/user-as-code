from datetime import date
from .schema import MedicalProfile, Allergy, Medication

medical_profile = MedicalProfile(
    blood_type="A+",
    allergies=[
        Allergy(
            allergen="Peanuts",
            severity="severe",
            reaction="Anaphylaxis",
        ),
        Allergy(
            allergen="Penicillin",
            severity="moderate",
            reaction="Rash and hives",
            drug_class="penicillin",
        ),
    ],
    current_medications=[
        Medication(
            name="Cetirizine",
            dosage="10mg",
            frequency="once daily",
            prescriber="Dr. Emily Park",
            start_date=date(2024, 3, 1),
            drug_class="antihistamine",
            notes="For seasonal allergies",
        ),
        Medication(
            name="Amoxicillin",
            dosage="500mg",
            frequency="three times daily",
            prescriber="Dr. Robert Chen",
            start_date=date(2025, 1, 10),
            drug_class="penicillin",
            notes="Prescribed for sinus infection; 10-day course",
        ),
    ],
    conditions=["Seasonal allergies"],
    primary_care_physician="Dr. Emily Park",
    emergency_contact="James Thompson (husband) +1-415-555-0198",
)
