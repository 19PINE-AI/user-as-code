from datetime import date

STATE = {'constraints': [{'active_from': '2024-11-28',
                  'active_until': None,
                  'deadline': None,
                  'deadline_anchor': None,
                  'deadline_offset_days': None,
                  'id': 'vacation_plumber_conflict',
                  'message_template': 'Conflict: the Costa Rica vacation runs from December 20, '
                                      '2024 through January 3, 2025, while the plumber is '
                                      'scheduled to fix the upstairs bathroom on December 27, '
                                      '2024, from 10:00 AM to 2:00 PM. The plumber said this is '
                                      'the only available time and you told him it works, but the '
                                      'appointment occurs during the vacation; reschedule the '
                                      'plumber or change the vacation plans.',
                  'severity': 'high',
                  'type': 'scheduling_conflict'}],
 'memory': {'plumber_appointment': {'availability': 'only available during this time',
                                    'date': '2024-12-27',
                                    'end_time': '14:00',
                                    'service_provider': 'plumber',
                                    'start_time': '10:00',
                                    'task': 'fix the upstairs bathroom',
                                    'user_confirmed': True},
            'user_request': {'date': '2024-11-28',
                             'request': 'help remember the plumber appointment'},
            'vacation': {'destination': 'Costa Rica',
                         'duration_description': 'two weeks',
                         'end_date': '2025-01-03',
                         'purpose': 'unplug',
                         'start_date': '2024-12-20'}}}


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
