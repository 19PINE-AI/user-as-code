import datetime

STATE = {
    "home_purchase": {
        "offer_accepted": True,
        "purchase_agreement": {
            "inspection_contingency": {
                "start_date": "2024-10-25",
                "duration_days": 15,
                "required_actions": [
                    "complete the home inspection",
                    "respond within the contingency period"
                ],
                "consequence_if_not_completed_and_responded": "waive the right to back out"
            }
        }
    }
}

def check_constraints(current_time):
    current = datetime.date.fromisoformat(current_time)
    contingency = STATE["home_purchase"]["purchase_agreement"]["inspection_contingency"]
    start = datetime.date.fromisoformat(contingency["start_date"])
    deadline = start + datetime.timedelta(days=contingency["duration_days"])
    days_remaining = (deadline - current).days

    if 0 <= days_remaining <= 7:
        return [{
            "severity": "warning",
            "type": "deadline",
            "message": (
                "The 15-day home inspection contingency period ends on "
                f"{deadline.isoformat()}. The inspection must be completed and "
                "a response provided by then to preserve the right to back out."
            )
        }]

    return []
