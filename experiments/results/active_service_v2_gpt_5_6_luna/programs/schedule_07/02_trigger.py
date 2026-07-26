from datetime import date

STATE = {
    "facts": {
        "best_friend": "Jake",
        "marathon": {
            "month": "December 2024",
            "training_plan_started": "2024-09-20"
        }
    },
    "commitments": [
        {
            "name": "Jake's wedding weekend",
            "role": "groomsman",
            "dates": {
                "rehearsal_dinner": "2024-10-25",
                "wedding": "2024-10-26",
                "brunch": "2024-10-27"
            },
            "attendance_requirement": "must be there the whole weekend"
        },
        {
            "name": "Marathon training long run",
            "date": "2024-10-26",
            "distance_miles": 20,
            "importance": "critical workout",
            "skip_allowed": False
        }
    ]
}


def check_constraints(current_time):
    current = date.fromisoformat(current_time)
    wedding_day = date(2024, 10, 26)
    wedding_weekend_start = date(2024, 10, 25)
    wedding_weekend_end = date(2024, 10, 27)

    if (
        current <= wedding_day
        and wedding_weekend_start <= wedding_day <= wedding_weekend_end
    ):
        return [{
            "severity": "high",
            "type": "schedule_conflict",
            "message": (
                "Jake's wedding weekend requires groomsman attendance from Friday "
                "October 25 through Sunday October 27, while the critical 20-mile "
                "marathon training run is scheduled for Saturday October 26 and "
                "cannot be skipped."
            )
        }]

    return [] 񟿿
