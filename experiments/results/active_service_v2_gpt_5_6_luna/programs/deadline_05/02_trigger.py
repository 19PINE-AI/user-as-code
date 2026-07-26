from datetime import date, timedelta

STATE = {
    "purchases": [
        {
            "item": "espresso machine",
            "price_usd": 400,
            "seller": "Williams-Sonoma",
            "purchase_date": "2024-10-02",
            "return_window_days": 30,
            "return_deadline": "2024-11-01",
            "concern": "The milk frother is kind of weak.",
            "decision_status": "undecided",
            "intended_decision_timing": "Give it another week or two before deciding."
        }
    ]
}

def check_constraints(current_time):
    current = date.fromisoformat(current_time)
    alerts = []

    for purchase in STATE["purchases"]:
        deadline = date.fromisoformat(purchase["return_deadline"])
        days_remaining = (deadline - current).days

        if days_remaining < 0:
            alerts.append({
                "severity": "high",
                "type": "expired_deadline",
                "message": (
                    f"The {purchase['item']} return window for the ${purchase['price_usd']} "
                    f"purchase from {purchase['seller']} expired on "
                    f"{purchase['return_deadline']}."
                )
            })
        elif days_remaining <= 7:
            alerts.append({
                "severity": "warning",
                "type": "upcoming_deadline",
                "message": (
                    f"The {purchase['item']} return window for the ${purchase['price_usd']} "
                    f"purchase from {purchase['seller']} ends on "
                    f"{purchase['return_deadline']} ({days_remaining} days remaining)."
                )
            })

    return alerts
