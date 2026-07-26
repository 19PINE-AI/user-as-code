from datetime import date

STATE = {
    "purchases": [
        {
            "item": "espresso machine",
            "seller": "Williams-Sonoma",
            "price_usd": 400,
            "purchase_date": "2024-10-02",
            "return_window_days": 30,
            "concern": "milk frother is kind of weak",
            "decision_status": "undecided",
            "stated_decision_timing": "another week or two"
        }
    ]
}

def check_constraints(current_time):
    current_date = date.fromisoformat(current_time)
    alerts = []

    for purchase in STATE["purchases"]:
        if purchase["decision_status"] != "undecided":
            continue

        purchase_date = date.fromisoformat(purchase["purchase_date"])
        return_deadline = purchase_date.fromordinal(
            purchase_date.toordinal() + purchase["return_window_days"]
        )
        days_until_deadline = (return_deadline - current_date).days

        if days_until_deadline < 0:
            alerts.append({
                "severity": "critical",
                "type": "return_window_expired",
                "message": (
                    f"The {purchase['item']} return window at {purchase['seller']} "
                    f"ended on {return_deadline.isoformat()}, and the purchase is still undecided."
                )
            })
        elif days_until_deadline <= 7:
            alerts.append({
                "severity": "warning",
                "type": "return_deadline_approaching",
                "message": (
                    f"The {purchase['item']} return window at {purchase['seller']} "
                    f"ends on {return_deadline.isoformat()}; the purchase is still undecided."
                )
            })

    return alerts
