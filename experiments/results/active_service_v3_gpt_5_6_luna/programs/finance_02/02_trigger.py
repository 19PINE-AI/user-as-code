from datetime import date

STATE = {'constraints': [{'active_from': '2025-01-15',
                  'active_until': None,
                  'deadline': None,
                  'deadline_anchor': None,
                  'deadline_offset_days': None,
                  'id': 'team_offsite_card_limit_conflict',
                  'message_template': "There is a conflict between the team offsite venue's $4,200 "
                                      "day quote and your corporate card's $3,000 per-transaction "
                                      'limit: the proposed charge exceeds the limit by $1,200. A '
                                      'charge above $3,000 requires VP approval, and you stated '
                                      'that you do not want to deal with that process, so use '
                                      'another payment method or obtain your approval preference '
                                      'before booking.',
                  'severity': 'high',
                  'type': 'proposal_over_limit'}],
 'memory': {'corporate_card': {'per_transaction_limit_usd': 3000,
                               'transactions_above_limit_require_vp_approval': True,
                               'user_does_not_want_to_deal_with_vp_approval_process': True},
            'current_session_timestamp': '2025-01-15',
            'history_sessions': [{'date': '2024-07-10', 'session_number': 1},
                                 {'date': '2025-01-15', 'session_number': 12}],
            'team_offsite': {'purpose': 'team offsite',
                             'quote_period': 'day',
                             'requested_payment_method': 'corporate card',
                             'venue_quote_usd': 4200}}}


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
