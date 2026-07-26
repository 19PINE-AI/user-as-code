from datetime import date

STATE = {'constraints': [{'active_from': '2024-11-02',
                  'active_until': '2024-11-09',
                  'deadline': '2024-11-09',
                  'deadline_anchor': '2024-10-25',
                  'deadline_offset_days': 15,
                  'id': 'home_inspection_contingency_deadline',
                  'message_template': "The accepted house offer's home inspection contingency "
                                      'requires the home inspection and your response within 15 '
                                      'days starting October 25, 2024. Complete the inspection and '
                                      'respond by {deadline}; {days_remaining} days remaining, or '
                                      'you waive the right to back out.',
                  'severity': 'warning',
                  'type': 'deadline'}],
 'memory': {'current_session_date': '2024-10-30',
            'home_inspector': {'availability_date': '2024-11-07',
                               'cannot_come_before': '2024-11-07'},
            'house_offer_status': 'accepted',
            'purchase_agreement': {'home_inspection_contingency': {'consequence_if_actions_not_completed': 'the '
                                                                                                           'buyer '
                                                                                                           'waives '
                                                                                                           'the '
                                                                                                           'right '
                                                                                                           'to '
                                                                                                           'back '
                                                                                                           'out',
                                                                   'duration_days': 15,
                                                                   'required_actions': ['complete '
                                                                                        'the home '
                                                                                        'inspection',
                                                                                        'respond '
                                                                                        'within '
                                                                                        'the '
                                                                                        'contingency '
                                                                                        'period'],
                                                                   'start_date': '2024-10-25'}},
            'user_questions': ['Whether the home inspection appointment on November 7 is too late '
                               'for the 15-day home inspection contingency',
                               'What happens if the home inspector finds something']}}


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
