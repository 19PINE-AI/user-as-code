from datetime import date

STATE = {'constraints': [{'active_from': '2024-12-01',
                  'active_until': None,
                  'deadline': None,
                  'deadline_anchor': None,
                  'deadline_offset_days': None,
                  'id': 'schengen_single_entry_used',
                  'message_template': "The proposed Berlin New Year's Eve trip from December 28, "
                                      '2024 to January 2, 2025 conflicts with your single-entry '
                                      'Schengen visa because your completed week in Paris used the '
                                      "visa's one permitted entry. You cannot use that visa for "
                                      'Berlin; you need a new visa or a changed plan.',
                  'severity': 'high',
                  'type': 'credential_exhausted'},
                 {'active_from': '2024-12-01',
                  'active_until': None,
                  'deadline': None,
                  'deadline_anchor': None,
                  'deadline_offset_days': None,
                  'id': 'schengen_validity_window',
                  'message_template': "The proposed Berlin New Year's Eve trip from December 28, "
                                      "2024 to January 2, 2025 conflicts with your Schengen visa's "
                                      'validity window of October 1 through December 31, 2024 '
                                      'because January 1 and January 2, 2025 occur after the visa '
                                      'expires. You need a visa valid for the full trip or a '
                                      'changed plan.',
                  'severity': 'high',
                  'type': 'plan_outside_validity_window'}],
 'memory': {'current_session_timestamp': '2024-12-01',
            'history': [{'facts': [{'entry_type': 'single-entry',
                                    'status': 'came through',
                                    'type': 'visa',
                                    'valid_from': '2024-10-01',
                                    'valid_until': '2024-12-31',
                                    'visa_type': 'Schengen visa'}],
                         'session_date': '2024-09-20',
                         'session_number': 3},
                        {'facts': [{'destination': 'Paris',
                                    'duration': 'one week',
                                    'experience': 'amazing',
                                    'food_preference_or_observation': 'The croissants were unreal.',
                                    'return_status': 'just got back',
                                    'status': 'completed',
                                    'type': 'trip'}],
                         'session_date': '2024-11-05',
                         'session_number': 6},
                        {'facts': [{'date_range_end': '2025-01-02',
                                    'date_range_start': '2024-12-28',
                                    'destination': 'Berlin',
                                    'occasion': "New Year's Eve",
                                    'status': 'tentative',
                                    'type': 'travel_plan',
                                    'wording': 'Maybe December 28 to January 2'}],
                         'session_date': '2024-12-01',
                         'session_number': 10}]}}


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
