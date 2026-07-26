from datetime import date

STATE = {'constraints': [{'active_from': '2024-10-10',
                  'active_until': None,
                  'deadline': None,
                  'deadline_anchor': None,
                  'deadline_offset_days': None,
                  'id': 'airbnb_movers_date_conflict',
                  'message_template': "There is a conflict between the Airbnb guest's booked stay "
                                      'in the spare bedroom from 2024-11-15 through 2024-11-20 and '
                                      "the movers' scheduled move of everything on 2024-11-14 "
                                      'through 2024-11-15. The Airbnb guest arrives on 2024-11-15 '
                                      'while the movers are scheduled to work that day, so you '
                                      'need to resolve the overlap by changing the guest booking '
                                      "or the movers' schedule.",
                  'severity': 'high',
                  'type': 'schedule_conflict'}],
 'memory': {'airbnb_listing': {'first_booking': {'arrival_date': '2024-11-15',
                                                 'departure_date': '2024-11-20',
                                                 'guest': 'guest',
                                                 'stay_dates_inclusive': '2024-11-15 through '
                                                                         '2024-11-20'},
                               'property': 'spare bedroom',
                               'status': 'listed'},
            'current_session_timestamp': '2024-10-10',
            'new_house': {'closing_date': '2024-11-10',
                          'movers': {'purpose': 'move everything',
                                     'scheduled_dates': '2024-11-14 through 2024-11-15'},
                          'status': 'bought'}}}


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
