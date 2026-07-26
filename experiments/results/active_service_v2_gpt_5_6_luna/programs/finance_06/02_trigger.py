from datetime import date

STATE = {
    "facts": {
        "pregnant": True,
        "due_month": 3,
        "due_year": None,
    },
    "preferences_and_commitments": [
        {
            "statement": "We're going to need to be more conservative with our money",
            "established": "2024-08-10",
        },
        {
            "statement": "No more risky investments",
            "established": "2024-08-10",
        },
    ],
    "proposed_actions": [
        {
            "asset_description": "small-cap biotech stock",
            "amount": 15000,
            "risk_description": "Super volatile",
            "status": "proposed",
            "established": "2024-11-05",
        }
    ],
}

def check_constraints(current_time):
    current_date = date.fromisoformat(current_time)
    alerts = []

    proposed_investment = STATE["proposed_actions"][0]
    proposal_date = date.fromisoformat(proposed_investment["established"])

    if current_date >= proposal_date:
        alerts.append({
            "severity": "high",
            "type": "conflict",
            "message": (
                "The proposed $15,000 investment in a super-volatile small-cap "
                "biotech stock conflicts with the explicit preference for no more "
                "risky investments."
            ),
        })

    return alerts
