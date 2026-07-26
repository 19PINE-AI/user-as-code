from datetime import date, timedelta

STATE = {
    "accounts": {
        "wells_fargo_checking": {
            "status": "open",
            "planned_action": "close",
            "planned_window_start": "2024-09-23",
            "planned_window_end": "2024-09-29",
            "destination_for_moved_funds": "Schwab"
        },
        "schwab": {
            "status": "new",
            "role": "replacement_account"
        }
    },
    "commitments": [
        {
            "action": "move everything from Wells Fargo checking to Schwab",
            "window_start": "2024-09-23",
            "window_end": "2024-09-29"
        },
        {
            "action": "close Wells Fargo checking account",
            "window_start": "2024-09-23",
            "window_end": "2024-09-29"
        }
    ],
    "preferences": {
        "dislikes": [
            {
                "subject": "Wells Fargo fees"
            }
        ]
    }
}


def check_constraints(current_time):
    current = date.fromisoformat(current_time)
    alerts = []

    closure_start = date.fromisoformat(
        STATE["accounts"]["wells_fargo_checking"]["planned_window_start"]
    )
    closure_end = date.fromisoformat(
        STATE["accounts"]["wells_fargo_checking"]["planned_window_end"]
    )

    if closure_start <= current <= closure_end:
        alerts.append({
            "severity": "reminder",
            "type": "deadline",
            "message": "The planned window to move everything from Wells Fargo checking to Schwab and close the Wells Fargo checking account is underway."
        })
    elif current < closure_start and closure_start - current <= timedelta(days=7):
        alerts.append({
            "severity": "reminder",
            "type": "deadline",
            "message": "The planned window to move everything from Wells Fargo checking to Schwab and close the Wells Fargo checking account begins within seven days."
        })

    return alerts
