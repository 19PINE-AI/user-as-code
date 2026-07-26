from datetime import date

STATE = {'constraints': [{'active_from': '2024-11-18',
                  'active_until': None,
                  'deadline': None,
                  'deadline_anchor': None,
                  'deadline_offset_days': None,
                  'id': 'sydney_trip_before_visa_validity',
                  'message_template': 'There is a conflict between your planned Sydney flight on '
                                      'November 25, 2024 and your Australian visa validity period '
                                      'of December 1, 2024 through May 31, 2025: the flight occurs '
                                      'before the visa becomes valid. Move the flight to December '
                                      '1 or later, or obtain a visa valid for November 25, 2024, '
                                      'before booking hotels and travel.',
                  'severity': 'high',
                  'type': 'plan_outside_validity_window'}],
 'memory': {'current_session_timestamp': '2024-11-18',
            'history': [{'facts': {'action': 'Applied for an Australian visa',
                                   'application_date': '2024-10-30',
                                   'source': 'The agent said the visa will be valid during this '
                                             'period.',
                                   'validity_end': '2025-05-31',
                                   'validity_start': '2024-12-01'},
                         'session_date': '2024-10-30',
                         'session_number': 4},
                        {'facts': {'flight_date': '2024-11-25',
                                   'flight_status': 'Found cheap flights',
                                   'plan_change': 'Wants to head to Sydney early',
                                   'request': 'Help finding hotels'},
                         'session_date': '2024-11-18',
                         'session_number': 7}]}}


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
