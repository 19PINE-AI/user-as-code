from datetime import date

STATE = {'constraints': [{'active_from': '2024-11-25',
                  'active_until': '2024-12-02',
                  'deadline': '2024-12-02',
                  'deadline_anchor': '2025-01-31',
                  'deadline_offset_days': -60,
                  'id': 'lease_renewal_notice_deadline',
                  'message_template': 'The apartment lease expires on January 31, 2025, and the '
                                      'landlord requires 60 days notice if you want to renew. You '
                                      'want to negotiate the renewal terms; provide the renewal '
                                      'notice by {deadline}, with {days_remaining} days remaining, '
                                      'or the lease will auto-convert to month-to-month at a '
                                      'higher rate.',
                  'severity': 'warning',
                  'type': 'deadline'}],
 'memory': {'current_session_timestamp': '2024-08-20',
            'history': [{'facts': {'apartment_lease_expires': '2025-01-31',
                                   'if_no_renewal_notice': 'Lease auto-converts to month-to-month '
                                                           'at a higher rate',
                                   'landlord_requires_notice_days_for_renewal': 60,
                                   'user_intends_to': 'Negotiate the renewal terms'},
                         'session_date': '2024-08-20',
                         'session_number': 4}]}}


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
