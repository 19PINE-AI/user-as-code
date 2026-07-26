from datetime import date

STATE = {'constraints': [],
 'memory': {'current_session_date': '2024-08-22',
            'subscriptions': {'Adobe Creative Cloud': {'billing_cycle_ends': '2024-09-15',
                                                       'cancellation_effective': '2024-09-15',
                                                       'cancellation_reason': 'price increases',
                                                       'cancelled_on': '2024-08-22',
                                                       'status': 'cancelled'}}}}


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
