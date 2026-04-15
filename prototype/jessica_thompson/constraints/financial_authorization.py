"""
Financial-authorization constraint.

Detects conflicting wire transfer instructions -- for example, when two
different family members give the agent different destination accounts
for the same transfer.
"""

import importlib
import importlib.util
import sys
import types
from pathlib import Path


def check(project_path: str) -> list[dict]:
    """Return alerts for conflicting or suspicious wire transfer instructions."""
    alerts: list[dict] = []

    project = Path(project_path)
    sys.path.insert(0, str(project.parent))

    try:
        pkg_name = "domains.finance"

        # Set up package structure for relative imports
        if "domains" not in sys.modules:
            domains_pkg = types.ModuleType("domains")
            domains_pkg.__path__ = [str(project / "domains")]
            domains_pkg.__package__ = "domains"
            sys.modules["domains"] = domains_pkg

        if pkg_name not in sys.modules:
            finance_pkg = types.ModuleType(pkg_name)
            finance_pkg.__path__ = [str(project / "domains" / "finance")]
            finance_pkg.__package__ = pkg_name
            sys.modules[pkg_name] = finance_pkg

        # Load schema
        spec_schema = importlib.util.spec_from_file_location(
            f"{pkg_name}.schema",
            project / "domains" / "finance" / "schema.py",
        )
        finance_schema = importlib.util.module_from_spec(spec_schema)
        finance_schema.__package__ = pkg_name
        spec_schema.loader.exec_module(finance_schema)
        sys.modules[f"{pkg_name}.schema"] = finance_schema

        # Load state
        spec_state = importlib.util.spec_from_file_location(
            f"{pkg_name}.state",
            project / "domains" / "finance" / "state.py",
        )
        finance_state = importlib.util.module_from_spec(spec_state)
        finance_state.__package__ = pkg_name
        spec_state.loader.exec_module(finance_state)

        pending = finance_state.pending_transfers

        # Group pending transfers by (recipient_name, amount, purpose)
        groups: dict[tuple, list] = {}
        for transfer in pending:
            if transfer.status != "pending":
                continue
            key = (transfer.recipient_name, transfer.amount, transfer.purpose)
            groups.setdefault(key, []).append(transfer)

        for key, transfers in groups.items():
            if len(transfers) < 2:
                continue

            # Check for conflicting destination institutions or accounts
            destinations = {
                (t.destination_institution, t.destination_account_last_four)
                for t in transfers
            }
            if len(destinations) > 1:
                requesters = [t.requested_by for t in transfers]
                dest_descriptions = [
                    f"{t.destination_institution} (****{t.destination_account_last_four}) "
                    f"per {t.requested_by}"
                    for t in transfers
                ]
                alerts.append({
                    "severity": "critical",
                    "source": "financial_authorization",
                    "domain": "finance",
                    "message": (
                        f"CONFLICTING wire transfer instructions for "
                        f"${transfers[0].amount:,.2f} to {transfers[0].recipient_name}: "
                        + " vs. ".join(dest_descriptions)
                        + ". Verify correct destination with the account holder before sending."
                    ),
                })
    finally:
        sys.path.pop(0)

    return alerts
