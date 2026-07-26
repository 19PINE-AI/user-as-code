from datetime import date

STATE = {'constraints': [{'active_from': '2024-11-02',
                  'active_until': '2024-11-09',
                  'deadline': '2024-11-09',
                  'deadline_anchor': '2024-10-25',
                  'deadline_offset_days': 15,
                  'id': 'home_inspection_contingency_deadline',
                  'message_template': 'The accepted house purchase agreement requires the user to '
                                      'complete the home inspection and respond within the 15-day '
                                      'home inspection contingency by {deadline}; {days_remaining} '
                                      'days remaining. If the inspection is not completed and the '
                                      'user does not respond within that period, the user waives '
                                      'the right to back out of the house purchase.',
                  'severity': 'high',
                  'type': 'unresolved_deadline'}],
 'memory': {'current_session_timestamp': '2024-11-06',
            'history': [{'facts': ["The user's offer on the house was accepted.",
                                   'The purchase agreement gives the user a 15-day home inspection '
                                   'contingency starting on 2024-10-25.',
                                   'The user must get the home inspection done and respond within '
                                   'that 15-day period or waive the right to back out of the house '
                                   'purchase.'],
                         'session_date': '2024-10-25',
                         'session_number': 4},
                        {'facts': ['The home inspector cannot come until 2024-11-07.',
                                   'The user asked whether the inspection timing was too late and '
                                   'what would happen if the inspector found something.'],
                         'session_date': '2024-10-30',
                         'session_number': 5},
                        {'facts': ['The user is stressed about the house purchase.',
                                   'The user asked for relaxation techniques.'],
                         'session_date': '2024-11-06',
                         'session_number': 6}]}}


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
