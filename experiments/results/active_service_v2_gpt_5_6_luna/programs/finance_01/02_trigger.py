from datetime import date

STATE = {
    "trust_account": {
        "restriction": {
            "prohibited_action": "money leaving the family trust account",
            "start_date": "2024-09-01",
            "end_date": "2024-09-30",
            "source": "dad",
            "wording": "under no circumstances should any money leave the family trust account this month"
        }
    },
    "transfer_request": {
        "requested_by": "mom",
        "amount": 5000,
        "currency": "USD",
        "purpose": "kitchen renovation",
        "destination_account_last4": "4477",
        "destination_bank": "Chase",
        "source_account": "family trust account",
        "request_date": "2024-09-05",
        "status": "requested"
    }
}


def check_constraints(current_time):
    current = date.fromisoformat(current_time)
    restriction_start = date.fromisoformat(
        STATE["trust_account"]["restriction"]["start_date"]
    )
    restriction_end = date.fromisoformat(
        STATE["trust_account"]["restriction"]["end_date"]
    )

    if restriction_start <= current <= restriction_end:
        return [{
            "severity": "high",
            "type": "conflict",
            "message": (
                "The requested $5,000 transfer from the family trust account to "
                "Chase account ending in 4477 conflicts with the instruction that "
                "no money leave the trust account during September 2024."
            )
        }]

    return []
