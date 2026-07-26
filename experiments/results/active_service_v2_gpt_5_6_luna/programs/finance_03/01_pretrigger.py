from datetime import date

STATE = {
    "subscriptions": {
        "adobe_creative_cloud": {
            "status": "cancelled",
            "cancelled_on": "2024-08-22",
            "effective_end_of_billing_cycle": "2024-09-15"
        }
    }
}

def check_constraints(current_time):
    current = date.fromisoformat(current_time)
    effective_date = date.fromisoformat(
        STATE["subscriptions"]["adobe_creative_cloud"]["effective_end_of_billing_cycle"]
    )
    days_until_effective = (effective_date - current).days

    if 0 <= days_until_effective <= 7:
        return [{
            "severity": "info",
            "type": "deadline",
            "message": (
                "Adobe Creative Cloud cancellation takes effect at the end of "
                "the billing cycle on 2024-09-15."
            )
        }]

    return []
