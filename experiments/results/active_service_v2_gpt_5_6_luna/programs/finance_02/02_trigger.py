from datetime import date

STATE = {
    "corporate_card": {
        "per_transaction_limit": 3000,
        "currency": "USD",
        "above_limit_requires": "VP approval",
        "user_preference": "Avoid the VP approval process"
    },
    "team_offsite": {
        "venue_day_quote": 4200,
        "currency": "USD",
        "requested_payment_method": "corporate card",
        "request_date": "2025-01-15"
    }
}

def check_constraints(current_time):
    current_date = date.fromisoformat(current_time)
    request_date = date.fromisoformat(STATE["team_offsite"]["request_date"])

    if current_date < request_date:
        return []

    quote = STATE["team_offsite"]["venue_day_quote"]
    limit = STATE["corporate_card"]["per_transaction_limit"]

    if quote > limit:
        return [{
            "severity": "high",
            "type": "constraint_conflict",
            "message": (
                "The venue's $4,200 quote exceeds the corporate card's "
                "$3,000 per-transaction limit. VP approval is required, "
                "which conflicts with the preference to avoid that process."
            )
        }]

    return []
