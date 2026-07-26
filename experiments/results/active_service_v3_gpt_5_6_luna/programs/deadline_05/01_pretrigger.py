from datetime import date

STATE = {'constraints': [{'active_from': '2024-10-25',
                  'active_until': '2024-11-01',
                  'deadline': '2024-11-01',
                  'deadline_anchor': '2024-10-02',
                  'deadline_offset_days': 30,
                  'id': 'espresso_machine_return_deadline',
                  'message_template': 'The return decision for the $400 espresso machine bought '
                                      'from Williams-Sonoma on October 2 is unresolved because the '
                                      'milk frother is kind of weak. The Williams-Sonoma return '
                                      'window ends on {deadline}; {days_remaining} days remaining '
                                      'to decide whether to return the espresso machine.',
                  'severity': 'warning',
                  'type': 'unresolved_deadline'}],
 'memory': {'current_session_date': '2024-10-08',
            'purchase': {'amount_usd': 400,
                         'concern': 'The milk frother is kind of weak',
                         'decision_intent': 'Use the machine another week or two, then decide '
                                            'whether to return it',
                         'item': 'espresso machine',
                         'purchase_date': '2024-10-02',
                         'return_decision_status': 'undecided',
                         'return_policy_duration_days': 30,
                         'seller': 'Williams-Sonoma'}}}


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
