from datetime import date

STATE = {'constraints': [{'active_from': '2024-11-05',
                  'active_until': None,
                  'deadline': None,
                  'deadline_anchor': None,
                  'deadline_offset_days': None,
                  'id': 'risky_biotech_investment_conflict',
                  'message_template': 'There is a conflict between your stated preference on '
                                      '2024-08-10 to be more conservative with money during your '
                                      'pregnancy and make no more risky investments, and your '
                                      '2024-11-05 proposal to put $15,000 into a super-volatile '
                                      'small-cap biotech stock based on a hot tip from your buddy '
                                      'at work. Proceeding would violate your stated '
                                      'no-risky-investments preference; do not make this '
                                      'investment unless you revise that preference.',
                  'severity': 'high',
                  'type': 'direct_conflict'}],
 'memory': {'current_session_timestamp': '2024-11-05',
            'financial_preference': {'preference': 'Be more conservative with money during the '
                                                   'pregnancy.',
                                     'prohibited_action': 'No more risky investments.',
                                     'stated_on': '2024-08-10'},
            'investment_proposal': {'amount': 15000,
                                    'asset': 'A small-cap biotech stock',
                                    'currency': 'USD',
                                    'potential_return_description': 'Could 10x',
                                    'risk_description': 'Super volatile',
                                    'source': 'A buddy at work gave the user a hot tip.',
                                    'stated_on': '2024-11-05',
                                    'status': 'The user wants to invest the $15,000; no completion '
                                              'was stated.'},
            'pregnancy': {'due': 'March', 'stated_on': '2024-08-10', 'status': 'pregnant'}}}


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
