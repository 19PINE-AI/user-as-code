from datetime import date

STATE = {
    "subscriptions": {
        "Adobe Creative Cloud": {
            "cancelled_on": "2024-08-22",
            "cancellation_effective_on": "2024-09-15",
            "reason": "price increases"
        }
    },
    "charges": [
        {
            "merchant": "Adobe",
            "amount": 59.99,
            "date": "2025-01-15",
            "statement_context": "credit card statement"
        }
    ]
}

def check_constraints(current_time):
    current = date.fromisoformat(current_time)
    alerts = []

    adobe = STATE["subscriptions"]["Adobe Creative Cloud"]
    for charge in STATE["charges"]:
        charge_date = date.fromisoformat(charge["date"])
        effective_date = date.fromisoformat(adobe["cancellation_effective_on"])

        if (
            charge["merchant"] == "Adobe"
            and charge_date <= current
            and charge_date > effective_date
        ):
            alerts.append({
                "severity": "warning",
                "type": "post_cancellation_charge",
                "message": (
                    f"Adobe charged ${charge['amount']:.2f} on {charge['date']} "
                    f"after the Creative Cloud cancellation became effective on "
                    f"{adobe['cancellation_effective_on']}."
                )
            })

    return alerts
