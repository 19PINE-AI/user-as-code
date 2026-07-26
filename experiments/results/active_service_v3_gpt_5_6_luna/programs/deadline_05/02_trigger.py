from datetime import date

STATE = {'constraints': [{'active_from': '2024-10-25',
                  'active_until': '2024-11-01',
                  'deadline': '2024-11-01',
                  'deadline_anchor': '2024-10-02',
                  'deadline_offset_days': 30,
                  'id': 'espresso_machine_return_window',
                  'message_template': 'The $400 espresso machine bought from Williams-Sonoma on '
                                      'October 2 has a 30-day return window. The user needs to '
                                      'decide whether to return it while addressing the weak milk '
                                      'frother by {deadline}; {days_remaining} days remaining.',
                  'severity': 'warning',
                  'type': 'deadline'}],
 'memory': {'current_session_timestamp': '2024-10-29',
            'purchase': {'amount_usd': 400,
                         'decision_plan': 'Give it another week or two and decide whether to '
                                          'return it.',
                         'item': 'espresso machine',
                         'purchase_date': '2024-10-02',
                         'retailer': 'Williams-Sonoma',
                         'return_policy_duration_days': 30,
                         'user_description': 'The milk frother is kind of weak.'},
            'requests': [{'date': '2024-10-29', 'request': "What's the weather like today?"}]}}


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
