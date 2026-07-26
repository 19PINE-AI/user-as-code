from datetime import date

STATE = {'constraints': [{'active_from': '2024-10-02',
                  'active_until': None,
                  'deadline': None,
                  'deadline_anchor': None,
                  'deadline_offset_days': None,
                  'id': 'wells_fargo_rent_autopay_closure_conflict',
                  'message_template': 'There is a conflict between closing the Wells Fargo '
                                      'checking account next week and the $1,500 monthly rent '
                                      'payment set to autopay from that Wells Fargo checking '
                                      'account on the 1st of each month. If the account is closed '
                                      'before the rent payment is moved to the new Schwab account, '
                                      'the $1,500 rent payment may not process; move or cancel the '
                                      'Wells Fargo autopay before closing the account.',
                  'severity': 'high',
                  'type': 'direct_conflict'}],
 'memory': {'accounts': {'Schwab account': {'intended_use': 'Receive everything moved from the '
                                                            'Wells Fargo checking account',
                                            'status': 'New account'},
                         'Wells Fargo checking account': {'reason_for_closure': 'Fed up with Wells '
                                                                                'Fargo fees',
                                                          'status': 'Planned for closure next week '
                                                                    'from 2024-09-18'}},
            'current_session_timestamp': '2024-10-02',
            'history': [{'facts': {'account': 'Wells Fargo checking account',
                                   'financial_transition': 'Move everything to the new Schwab '
                                                           'account',
                                   'planned_action': 'Close the Wells Fargo checking account next '
                                                     'week',
                                   'reason': 'Fed up with Wells Fargo fees'},
                         'session_date': '2024-09-18',
                         'session_number': 6},
                        {'facts': {'recurring_payment': {'amount': 1500,
                                                         'currency': 'USD',
                                                         'due_schedule': 'The 1st of each month',
                                                         'payment_method': 'Autopay',
                                                         'purpose': 'Rent',
                                                         'source_account': 'Wells Fargo checking '
                                                                           'account'}},
                         'session_date': '2024-10-02',
                         'session_number': 9}],
            'recurring_payments': [{'amount': 1500,
                                    'currency': 'USD',
                                    'due_schedule': 'The 1st of each month',
                                    'method': 'Autopay',
                                    'name': 'Rent',
                                    'source_account': 'Wells Fargo checking account'}]}}


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
