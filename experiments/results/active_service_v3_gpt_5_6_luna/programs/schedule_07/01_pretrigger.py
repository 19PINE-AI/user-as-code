from datetime import date

STATE = {'constraints': [],
 'memory': {'best_friend': {'attendance_requirement': 'must be there the whole weekend',
                            'event': 'wedding',
                            'name': 'Jake',
                            'schedule': {'brunch': {'date': '2024-10-27', 'time': 'Sunday'},
                                         'rehearsal_dinner': {'date': '2024-10-25',
                                                              'time': 'Friday night'},
                                         'wedding': {'date': '2024-10-26', 'time': 'Saturday'}},
                            'user_role': 'groomsman',
                            'wedding_date': '2024-10-26'},
            'current_session_timestamp': '2024-08-15'}}


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
