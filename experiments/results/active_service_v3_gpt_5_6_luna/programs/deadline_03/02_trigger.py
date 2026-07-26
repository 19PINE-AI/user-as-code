from datetime import date

STATE = {'constraints': [{'active_from': '2024-11-25',
                  'active_until': '2024-12-02',
                  'deadline': '2024-12-02',
                  'deadline_anchor': '2025-01-31',
                  'deadline_offset_days': -60,
                  'id': 'apartment_lease_renewal_notice_deadline',
                  'message_template': 'Your apartment lease expires on January 31, 2025, and the '
                                      "landlord requires 60 days' notice if you want to renew. You "
                                      'definitely want to negotiate the renewal terms, so give the '
                                      'landlord notice and begin the renewal negotiation by '
                                      '{deadline}; {days_remaining} days remaining. If you miss '
                                      'the notice requirement, the lease auto-converts to '
                                      'month-to-month at a higher rate.',
                  'severity': 'warning',
                  'type': 'deadline'}],
 'memory': {'apartment_lease': {'consequence_if_no_renewal_notice': 'The lease auto-converts to '
                                                                    'month-to-month at a higher '
                                                                    'rate.',
                                'expires': '2025-01-31',
                                'landlord_notice_requirement': {'action': 'give notice if renewing',
                                                                'notice_period_days': 60},
                                'property': "user's apartment",
                                'user_intention': 'The user definitely wants to negotiate the '
                                                  'renewal terms.'},
            'current_session': {'context': 'The user is busy with the holidays and cannot think '
                                           'straight.',
                                'date': '2024-11-25'}}}


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
