from datetime import date

STATE = {'constraints': [{'active_from': '2024-11-25',
                  'active_until': None,
                  'deadline': None,
                  'deadline_anchor': None,
                  'deadline_offset_days': None,
                  'id': 'new_york_trip_emma_play_conflict',
                  'message_template': 'There is a conflict between your New York trip for your '
                                      "boss's client meeting, with travel from December 11 through "
                                      "December 13, and Emma's school play performance on December "
                                      '12 at 6:00 PM, where you promised to be in the front row. '
                                      'The trip overlaps the performance, so you cannot keep both '
                                      'the New York travel schedule and your promise to attend the '
                                      'performance without changing one of them.',
                  'severity': 'high',
                  'type': 'schedule_conflict'}],
 'memory': {'emma': {'achievement': 'got the lead role in her school play',
                     'commitment': 'user promised Emma they would be in the front row',
                     'performance_date': '2024-12-12',
                     'performance_time': '6:00 PM',
                     'relationship': 'daughter or child'},
            'new_york_client_meeting': {'accommodation_preference': 'hotel near Midtown',
                                        'purpose': 'client meeting',
                                        'requested_by': 'boss',
                                        'travel_outbound_date': '2024-12-11',
                                        'travel_return_date': '2024-12-13'}}}


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
