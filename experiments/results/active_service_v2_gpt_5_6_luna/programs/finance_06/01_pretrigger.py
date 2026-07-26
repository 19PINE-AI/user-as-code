from datetime import datetime

STATE = {
    "pregnancy": {
        "status": "pregnant",
        "due_month": 3,
        "due_year": None,
    },
    "financial_constraints": {
        "risky_investments": "prohibited",
        "reason": "be more conservative with money during pregnancy",
    },
}


def check_constraints(current_time):
    datetime.strptime(current_time, "%Y-%m-%d")
    return []
