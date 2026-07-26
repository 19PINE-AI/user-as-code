from datetime import date

STATE = {'constraints': [],
 'memory': {'australian_visa': {'application_date': '2024-10-30',
                                'valid_from': '2024-12-01',
                                'valid_through': '2025-05-31',
                                'validity_source': 'The agent said the visa will be valid starting '
                                                   'December 1, 2024 through May 31, 2025.'},
            'current_session_date': '2024-10-30'}}


def check_constraints(current_time):
    current = date.fromisoformat(current_time)
    alerts = []
    for constraint in STATE["constraints"]:
        active_from = date.fromisoformat(constraint["active_from"])
        active_until_text = constraint["active_until"]
        active_until = date.fromisoformat(active_until_text) if active_until_text else None
        if current < active_from or (active_until is not None and current > active_until):
            continue
        message = constraint["message_template"]
        deadline_text = constraint["deadline"]
        if deadline_text:
            remaining = (date.fromisoformat(deadline_text) - current).days
            message = message.replace("{days_remaining}", str(remaining))
            message = message.replace("{deadline}", deadline_text)
        alerts.append({
            "severity": constraint["severity"],
            "type": constraint["type"],
            "message": message,
        })
    return alerts
