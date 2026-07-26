from datetime import date

STATE = {'constraints': [{'active_from': '2024-10-20',
                  'active_until': None,
                  'deadline': None,
                  'deadline_anchor': None,
                  'deadline_offset_days': None,
                  'id': 'car_service_airport_pickup_conflict',
                  'message_template': 'The car major service on Monday, November 4, conflicts with '
                                      'driving to the airport to pick up your parents when their '
                                      'flight lands at 2 PM. The mechanic requires the car from '
                                      'the 8 AM drop-off until after 5 PM, so the car will not be '
                                      'available for the airport pickup; arrange alternative '
                                      'transportation or reschedule the car service or pickup.',
                  'severity': 'high',
                  'type': 'schedule_conflict'}],
 'memory': {'current_session_timestamp': '2024-10-20',
            'history': [{'facts': {'car_major_service': {'date': '2024-11-04',
                                                         'drop_off_time': '08:00',
                                                         'duration': 'full day',
                                                         'pickup_time': 'after 17:00',
                                                         'service_provider': 'mechanic',
                                                         'weekday': 'Monday'}},
                         'session_date': '2024-10-05',
                         'session_number': 4},
                        {'facts': {'airport_pickup': {'date': '2024-11-04',
                                                      'flight_landing_time': '14:00',
                                                      'people': 'parents',
                                                      'purpose': 'drive to the airport to pick up '
                                                                 'parents'}},
                         'session_date': '2024-10-20',
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
