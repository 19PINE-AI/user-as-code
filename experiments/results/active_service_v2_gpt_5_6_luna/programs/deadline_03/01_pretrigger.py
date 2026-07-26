from datetime import date, timedelta

STATE = {
    "lease": {
        "expiration_date": "2025-01-31",
        "notice_required_days": 60,
        "renewal_intent": True,
        "renewal_goal": "negotiate renewal terms",
        "landlord_consequence_without_notice": "lease auto-converts to month-to-month at a higher rate",
    }
}


def check_constraints(current_time):
    current_date = date.fromisoformat(current_time)
    expiration_date = date.fromisoformat(STATE["lease"]["expiration_date"])
    notice_deadline = expiration_date - timedelta(
        days=STATE["lease"]["notice_required_days"]
    )

    if not STATE["lease"]["renewal_intent"]:
        return []

    days_until_deadline = (notice_deadline - current_date).days

    if days_until_deadline < 0:
        return [{
            "severity": "critical",
            "type": "missed_deadline",
            "message": (
                f"The {STATE['lease']['notice_required_days']}-day renewal notice "
                f"deadline was {notice_deadline.isoformat()}; without notice, the "
                "lease may auto-convert to month-to-month at a higher rate."
            ),
        }]

    if days_until_deadline <= 7:
        return [{
            "severity": "warning",
            "type": "upcoming_deadline",
            "message": (
                f"Renewal notice is due by {notice_deadline.isoformat()} "
                f"({days_until_deadline} days away) because you want to negotiate "
                "renewal terms."
            ),
        }]

    return []
