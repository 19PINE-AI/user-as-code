from datetime import date
from .schema import Account, WireTransfer

accounts = [
    Account(
        institution="Chase",
        account_type="checking",
        account_label="Chase Primary Checking",
        last_four="4892",
        is_primary=True,
    ),
    Account(
        institution="Charles Schwab",
        account_type="investment",
        account_label="Schwab Brokerage",
        last_four="7731",
        is_primary=False,
    ),
]

# Conflicting wire transfer instructions from two family members
pending_transfers = [
    WireTransfer(
        amount=15000.00,
        currency="USD",
        recipient_name="Patricia Williams",
        destination_institution="Bank of America",
        destination_account_last_four="3310",
        purpose="Gift to mother",
        requested_by="Patricia Williams (mother)",
        requested_date=date(2025, 1, 8),
        status="pending",
        source_account_label="Chase Primary Checking",
        notes="Mom called and asked Jessica to send to her BofA account",
    ),
    WireTransfer(
        amount=15000.00,
        currency="USD",
        recipient_name="Patricia Williams",
        destination_institution="Wells Fargo",
        destination_account_last_four="6654",
        purpose="Gift to mother",
        requested_by="James Thompson (husband)",
        requested_date=date(2025, 1, 9),
        status="pending",
        source_account_label="Chase Primary Checking",
        notes="James said Patricia's account is at Wells Fargo, not BofA",
    ),
]
