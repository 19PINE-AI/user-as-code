from datetime import date, timedelta

STATE = {
    "accounts": {
        "wells_fargo_checking": {
            "status": "planned_for_closure",
            "closure_statement_date": "2024-09-18",
            "planned_closure_window": {
                "start": "2024-09-23",
                "end": "2024-09-29"
            }
        },
        "schwab": {
            "role": "replacement_account",
            "transfer_intent": "move_everything_from_wells_fargo"
        }
    },
    "recurring_payments": [
        {
            "name": "rent",
            "amount": 1500,
            "currency": "USD",
            "autopay_account": "wells_fargo_checking",
            "due_day_of_month": 1
        }
    ],
    "preferences": {
        "avoid_wells_fargo_fees": True
    }
}


def check_constraints(current_time):
    current = date.fromisoformat(current_time)
    alerts = []

    for payment in STATE["recurring_payments"]:
        account = STATE["accounts"].get(payment["autopay_account"], {})
        closure_end = account.get("planned_closure_window", {}).get("end")

        if (
            account.get("status") == "planned_for_closure"
            and closure_end
            and current > date.fromisoformat(closure_end)
            and payment["due_day_of_month"] == 1
        ):
            alerts.append({
                "severity": "warning",
                "type": "payment_account_conflict",
                "message": (
                    f'{payment["name"].capitalize()} autopay of '
                    f'${payment["amount"]:,.2f} is scheduled from '
                    f'{payment["autopay_account"]}, which was planned for closure '
                    f'before the recurring payment date.'
                )
            })

    return alerts if current >= date(2024, 10, 1) else []
