from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Account:
    institution: str
    account_type: str  # "checking", "savings", "investment", etc.
    account_label: str  # user-friendly name
    last_four: str
    is_primary: bool = False


@dataclass
class WireTransfer:
    """A pending or completed wire transfer instruction."""
    amount: float
    currency: str
    recipient_name: str
    destination_institution: str
    destination_account_last_four: str
    purpose: str
    requested_by: str  # who asked the agent to set this up
    requested_date: date
    status: str = "pending"  # "pending", "confirmed", "sent", "cancelled"
    source_account_label: Optional[str] = None
    notes: Optional[str] = None
