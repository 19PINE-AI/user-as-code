from datetime import date

STATE = {'constraints': [{'active_from': '2024-11-10',
                  'active_until': None,
                  'deadline': None,
                  'deadline_anchor': None,
                  'deadline_offset_days': None,
                  'id': 'anniversary_roommate_dinner_conflict',
                  'message_template': 'There is a conflict between your anniversary dinner at Chez '
                                      'Laurent on November 15 at 7:00 PM and your booked dinner '
                                      'with your college roommate at Steakhouse 55 on November 15 '
                                      'at 7:30 PM. The reservations overlap in practical timing, '
                                      'so you need to reschedule or cancel one dinner.',
                  'severity': 'high',
                  'type': 'schedule_conflict'}],
 'memory': {'college_roommate': {'relationship': 'college roommate',
                                 'session_number': 7,
                                 'source_session': '2024-11-10',
                                 'status': 'in town briefly'},
            'current_session_timestamp': '2024-11-10',
            'dinner_reservation': {'date': '2024-11-15',
                                   'importance': 'special',
                                   'occasion': 'anniversary',
                                   'session_number': 5,
                                   'source_session': '2024-10-28',
                                   'stated_weekday': 'Saturday',
                                   'time': '7:00 PM',
                                   'venue': 'Chez Laurent'},
            'roommate_dinner_reservation': {'date': '2024-11-15',
                                            'purpose': 'catch up with college roommate',
                                            'session_number': 7,
                                            'source_session': '2024-11-10',
                                            'status': 'booked',
                                            'time': '7:30 PM',
                                            'venue': 'Steakhouse 55'}}}


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
