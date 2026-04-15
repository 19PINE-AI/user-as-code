from datetime import date
from .schema import Vehicle, MaintenanceSchedule

vehicles = [
    Vehicle(
        year=2020,
        make="Honda",
        model="Accord",
        color="Lunar Silver Metallic",
        vin="1HGCV1F34LA012345",
        license_plate="8ABC123",
        current_mileage=47200,
        maintenance_schedule=[
            MaintenanceSchedule(
                service_type="Oil change and tire rotation",
                due_date=date(2025, 1, 17),  # this Friday
                mileage_due=48000,
                provider="SF Honda Service Center",
                notes="Service due this Friday; booked for 9:00 AM",
            ),
        ],
    ),
    Vehicle(
        year=2023,
        make="Tesla",
        model="Model 3",
        color="Pearl White Multi-Coat",
        vin="5YJ3E1EA1PF123456",
        license_plate="ELEC789",
        current_mileage=12400,
        maintenance_schedule=[
            MaintenanceSchedule(
                service_type="Annual inspection",
                due_date=date(2025, 6, 1),
                provider="Tesla Service Center, San Francisco",
            ),
        ],
    ),
]
