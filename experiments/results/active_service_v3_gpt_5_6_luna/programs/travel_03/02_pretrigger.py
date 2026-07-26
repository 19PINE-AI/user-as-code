from datetime import date

STATE = {'constraints': [],
 'memory': {'paris_trip': {'croissants_opinion': 'the croissants were unreal',
                           'destination': 'Paris',
                           'duration': 'one week',
                           'experience': 'amazing',
                           'returned_on': '2024-11-05',
                           'status': 'returned'},
            'schengen_visa': {'entry_type': 'single-entry',
                              'status': 'came through',
                              'valid_from': '2024-10-01',
                              'valid_until': '2024-12-31'}}}


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
