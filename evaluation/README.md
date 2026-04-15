# Active Service Evaluation Protocol

This directory contains an evaluation protocol for **Active Service** -- the ability of a memory system to generate unsolicited alerts based on logical constraints over stored personal state.

## What is Active Service?

Active Service goes beyond passive retrieval. Rather than waiting for the user to ask relevant questions, the system proactively detects conflicts, risks, and approaching deadlines by performing computation over facts distributed across multiple conversation sessions. This capability is fundamentally impossible with similarity-based retrieval alone, because the alerts require date arithmetic, constraint checking, pharmacological knowledge, financial rule application, and cross-domain reasoning.

## Evaluation File

**`active_service_scenarios.json`** contains 40 evaluation scenarios across 5 categories (8 each):

| Category | Tests |
|---|---|
| **Travel Document Validity** | Passport expiration, visa validity windows, transit visa requirements, Schengen stay limits, name mismatches, blank page requirements |
| **Drug Interactions & Health Safety** | MAOI/SSRI interactions, allergy cross-reactivity, food-drug interactions, weight-based dosing, teratogenic medications, activity contraindications |
| **Financial Authorization Conflicts** | Conflicting instructions, authorization limits, cancelled service charges, insurance lapses, closed account payments, wash sale violations |
| **Scheduling Conflicts** | Meeting overlaps, double bookings, family commitment conflicts, resource unavailability, logistics timing, vacation conflicts |
| **Warranty/Deadline/Expiration** | Warranty expiry with unresolved issues, tax deadlines, lease renewal notices, return windows, license expiration, promotional rate expiry |

## Scenario Structure

Each scenario includes:

- **sessions**: Realistic multi-session conversations where facts are mentioned naturally
- **trigger_session**: The session that should cause the system to generate an alert
- **expected_alert**: The correct alert with severity, type, message, and the computation required
- **why_retrieval_fails**: Explanation of why similarity-based retrieval cannot solve this scenario

## Scoring Dimensions

1. **Alert Generated** -- Did the system produce an unsolicited alert? (binary)
2. **Severity Correct** -- Was the severity level appropriate? (critical / warning / info)
3. **Timing Correct** -- Was the alert triggered at the right session? (binary)
4. **Reasoning Correct** -- Did the alert include correct computation or logic? (binary)
5. **Message Actionable** -- Was the alert message actionable and specific? (1-5 scale)
