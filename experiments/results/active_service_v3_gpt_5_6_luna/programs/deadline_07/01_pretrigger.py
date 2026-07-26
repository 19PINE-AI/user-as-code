from datetime import date

STATE = {'constraints': [{'active_from': '2024-11-02',
                  'active_until': '2024-11-09',
                  'deadline': '2024-11-09',
                  'deadline_anchor': '2024-10-25',
                  'deadline_offset_days': 15,
                  'id': 'home_inspection_contingency_deadline',
                  'message_template': 'The accepted house purchase agreement requires you to get '
                                      'the home inspection done and respond within the 15-day home '
                                      'inspection contingency starting October 25, 2024. '
                                      '{days_remaining} days remaining until {deadline}; if you do '
                                      'not complete both actions within that period, you waive the '
                                      'right to back out of the purchase.',
                  'severity': 'high',
                  'type': 'unresolved_deadline'}],
 'memory': {'current_session_timestamp': '2024-10-25',
            'house_offer': 'Our offer on the house was accepted on 2024-10-25.',
            'purchase_agreement': {'home_inspection_contingency': {'consequence_if_not_completed': 'The '
                                                                                                   'right '
                                                                                                   'to '
                                                                                                   'back '
                                                                                                   'out '
                                                                                                   'of '
                                                                                                   'the '
                                                                                                   'purchase '
                                                                                                   'is '
                                                                                                   'waived.',
                                                                   'duration_days': 15,
                                                                   'required_actions': ['get the '
                                                                                        'home '
                                                                                        'inspection '
                                                                                        'done',
                                                                                        'respond '
                                                                                        'within '
                                                                                        'the '
                                                                                        '15-day '
                                                                                        'period'],
                                                                   'starts_on': '2024-10-25'}}}}


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
