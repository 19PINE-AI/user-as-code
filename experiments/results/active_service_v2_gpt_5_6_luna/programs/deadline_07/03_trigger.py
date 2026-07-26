import datetime

STATE = {
    "house_purchase": {
        "offer_accepted": True,
        "offer_accepted_date": "2024-10-25",
        "purchase_agreement": {
            "home_inspection_contingency": {
                "duration_days": 15,
                "start_date": "2024-10-25",
                "requirement": "Inspection must be completed and a response provided within the contingency period.",
                "consequence_if_not_completed_and_responded_in_time": "The right to back out is waived."
            }
        },
        "inspection": {
            "inspector_available_no_earlier_than": "2024-11-07",
            "completion_status_as_of": "2024-10-30",
            "completion_status": "not completed"
        }
    },
    "user_state": {
        "reported_stress_about_house_purchase": True,
        "reported_date": "2024-11-06"
    }
}


def check_constraints(current_time):
    current = datetime.date.fromisoformat(current_time)
    contingency = STATE["house_purchase"]["purchase_agreement"]["home_inspection_contingency"]
    start = datetime.date.fromisoformat(contingency["start_date"])
    deadline = start + datetime.timedelta(days=contingency["duration_days"])
    alerts = []

    if current <= deadline and deadline - current <= datetime.timedelta(days=7):
        inspector_date = datetime.date.fromisoformat(
            STATE["house_purchase"]["inspection"]["inspector_available_no_earlier_than"]
        )
        message = (
            f"The 15-day home inspection contingency period ends on {deadline.isoformat()}. "
            "The inspection and response are not documented as complete; if they are not "
            "completed within that period, the stated right to back out is waived."
        )
        if current >= datetime.date.fromisoformat("2024-10-30"):
            message += (
                f" The inspector cannot come before {inspector_date.isoformat()}, "
                "leaving only the remaining portion of the contingency period."
            )
        alerts.append({
            "severity": "warning",
            "type": "deadline",
            "message": message
        })

    return alerts
