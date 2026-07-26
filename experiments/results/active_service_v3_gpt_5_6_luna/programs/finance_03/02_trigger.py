from datetime import date

STATE = {'constraints': [{'active_from': '2025-01-20',
                  'active_until': None,
                  'deadline': None,
                  'deadline_anchor': None,
                  'deadline_offset_days': None,
                  'id': 'adobe_charge_after_cancellation',
                  'message_template': 'There is a conflict between the Adobe Creative Cloud '
                                      'subscription cancellation and the Adobe charge: you '
                                      'cancelled Adobe Creative Cloud on 2024-08-22, with '
                                      'cancellation effective at the end of the billing cycle on '
                                      '2024-09-15, but your credit card statement shows a $59.99 '
                                      'Adobe charge on 2025-01-15. The charge occurred after '
                                      'cancellation, so you should review or dispute it with Adobe '
                                      'and your credit card issuer if it was not authorized.',
                  'severity': 'high',
                  'type': 'charge_after_cancellation'}],
 'memory': {'preferences': [{'preference': 'does not want continued price increases',
                             'subject': 'Adobe Creative Cloud'}],
            'sessions': [{'date': '2024-08-22',
                          'facts': {'subscription': {'action': 'cancelled',
                                                     'cancelled_on': '2024-08-22',
                                                     'effective_end_of_billing_cycle': '2024-09-15',
                                                     'service': 'Adobe Creative Cloud',
                                                     'status': 'cancelled_effective_2024-09-15'},
                                    'user_comment': "So done with Adobe's price increases."},
                          'session_number': 5},
                         {'date': '2025-01-20',
                          'facts': {'credit_card_statement': {'amount': 59.99,
                                                              'charge_date': '2025-01-15',
                                                              'currency': 'USD',
                                                              'merchant': 'Adobe'},
                                    'user_question': 'Why was there an Adobe charge when the Adobe '
                                                     'Creative Cloud subscription was supposed to '
                                                     'have been cancelled?'},
                          'session_number': 13}],
            'subscriptions': [{'cancellation_effective_date': '2024-09-15',
                               'cancellation_effective_reason': 'end of billing cycle',
                               'cancelled_on': '2024-08-22',
                               'service': 'Adobe Creative Cloud',
                               'status': 'cancelled'}],
            'transactions': [{'amount': 59.99,
                              'charge_date': '2025-01-15',
                              'currency': 'USD',
                              'merchant': 'Adobe',
                              'source': 'credit card statement'}]}}


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
