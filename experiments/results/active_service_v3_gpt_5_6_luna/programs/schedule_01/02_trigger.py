from datetime import date

STATE = {'constraints': [{'active_from': '2025-01-14',
                  'active_until': None,
                  'deadline': None,
                  'deadline_anchor': None,
                  'deadline_offset_days': None,
                  'id': 'board_meeting_chicago_flight_conflict',
                  'message_template': 'The proposed Chicago flight departing Tuesday January 21, '
                                      '2025 at 2:30 PM conflicts with your board meeting every '
                                      'Tuesday from 2:00 PM until about 4:00 PM, which you '
                                      'absolutely cannot miss. Booking this flight would overlap '
                                      'the board meeting; choose a different departure or resolve '
                                      'the conflict before booking.',
                  'severity': 'high',
                  'type': 'schedule_conflict'}],
 'memory': {'board_meeting': {'cannot_miss': True,
                              'end_time': 'about 4:00 PM',
                              'frequency': 'every Tuesday',
                              'start_time': '2:00 PM'},
            'chicago_fare': {'departure_date': '2025-01-21',
                             'departure_time': '2:30 PM',
                             'departure_weekday': 'Tuesday',
                             'destination': 'Chicago',
                             'status': 'found; not yet booked',
                             'user_action_requested': 'Should I book it?'},
            'session_timestamp': '2025-01-14'}}


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
