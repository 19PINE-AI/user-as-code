from datetime import date

STATE = {'constraints': [{'active_from': '2024-09-06',
                  'active_until': None,
                  'deadline': None,
                  'deadline_anchor': None,
                  'deadline_offset_days': None,
                  'id': 'trust_transfer_conflict',
                  'message_template': "There is a conflict between mom's request on 2024-09-05 to "
                                      'wire $5,000 from the family trust account to her '
                                      "kitchen-renovation contractor's Chase account ending in "
                                      "4477 and dad's 2024-09-06 instruction that under no "
                                      'circumstances should any money leave the family trust '
                                      'account this month while he restructures something with the '
                                      'accountant. Do not make the $5,000 wire unless the '
                                      'conflicting instructions are resolved.',
                  'severity': 'critical',
                  'type': 'direct_conflict'}],
 'memory': {'current_session_timestamp': '2024-09-06',
            'history': [{'facts': [{'action': 'asked the user to wire',
                                    'amount': '$5,000',
                                    'destination_account': 'account ending in 4477 at Chase',
                                    'person': 'mom',
                                    'purpose': 'kitchen renovation',
                                    'recipient': 'her contractor',
                                    'source_account': 'family trust account'}],
                         'session_date': '2024-09-05',
                         'session_number': 3},
                        {'facts': [{'action': 'called the user',
                                    'instruction': 'under no circumstances should any money leave '
                                                   'the family trust account this month',
                                    'person': 'dad',
                                    'reason': 'He is restructuring something with the accountant'}],
                         'session_date': '2024-09-06',
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
