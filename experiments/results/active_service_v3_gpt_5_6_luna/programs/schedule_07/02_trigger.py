from datetime import date

STATE = {'constraints': [{'active_from': '2024-09-20',
                  'active_until': None,
                  'deadline': None,
                  'deadline_anchor': None,
                  'deadline_offset_days': None,
                  'id': 'wedding_marathon_run_conflict',
                  'message_template': "There is a conflict between Jake's wedding weekend, which "
                                      'requires you to attend as a groomsman from the rehearsal '
                                      'dinner on Friday October 25 through brunch on Sunday '
                                      "October 27, and your marathon training plan's critical "
                                      '20-mile longest training run scheduled for Saturday October '
                                      '26. You cannot both be present for the full wedding weekend '
                                      'and complete the 20-mile run as scheduled, so you must '
                                      'resolve the conflict by changing the run or arranging an '
                                      'alternative to part of the wedding commitment.',
                  'severity': 'high',
                  'type': 'schedule_conflict'}],
 'memory': {'commitments': [{'attendance_requirement': 'be there the whole weekend',
                             'brunch': {'date': '2024-10-27',
                                        'time': 'brunch',
                                        'weekday': 'Sunday'},
                             'date': '2024-10-26',
                             'event': 'wedding',
                             'person': 'Jake',
                             'rehearsal_dinner': {'date': '2024-10-25',
                                                  'time': 'night',
                                                  'weekday': 'Friday'},
                             'role': 'groomsman',
                             'wedding_ceremony_or_reception': {'date': '2024-10-26',
                                                               'weekday': 'Saturday'},
                             'weekday': 'Saturday'},
                            {'activity': 'marathon training plan',
                             'goal': 'December marathon',
                             'longest_training_run': {'can_skip': False,
                                                      'date': '2024-10-26',
                                                      'distance_miles': 20,
                                                      'importance': 'critical workout',
                                                      'weekday': 'Saturday'},
                             'start_date': '2024-09-20'}],
            'current_session_date': '2024-09-20'}}


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
