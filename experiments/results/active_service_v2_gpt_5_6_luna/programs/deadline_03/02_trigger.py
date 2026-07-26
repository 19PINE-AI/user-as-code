from datetime import date, timedelta

STATE = {
    "lease": {
        "expiration_date": "2025-01-31",
        "renewal_notice_days": 60,
        "notice_deadline": "2024-12-02",
        "auto_conversion_if_no_renewal": "month-to-month at a higher rate",
        "user_wants_to_renew": True,
        "user_wants_to_negotiate_renewal_terms": True
    },
    "user_context": {
        "as_of": "2024-11-25",
        "reported_busy_with_holidays": True
    }
}

def check_constraints(current_time):
    current = date.fromisoformat(current_time)
    deadline = date.fromisoformat(STATE["lease"]["notice_deadline"])
    days_until_deadline = (deadline - current).days
    alerts = []

    if STATE["lease"]["user_wants_to_renew"] and STATE["lease"]["user_wants_to_negotiate_renewal_terms"]:
        if 0 <= days_until_deadline <= 7:
            alerts.append({
                "severity": "warning",
                "type": "deadline",
                "message": "Renewal notice and negotiation are due by 2024-12-02, which is within seven days."
            })
        elif days_until_deadline < 0:
            alerts.append({
                "severity": "critical",
                "type": "missed_deadline",
                "message": "The 2024-12-02 renewal-notice deadline has passed, and no renewal notice is recorded."
            })

    return alerts
