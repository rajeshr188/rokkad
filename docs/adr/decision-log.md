---
status: accepted
owner: project
updated: 2026-06-17
tags: [adr]
related: []
---

# Decision Log

This is the live index of architecture decisions in docs/decisions.

## Entries

| Date | ADR File | Status | Owners | Affected Apps | Supersedes | Notes |
|---|---|---|---|---|---|---|
| 2026-05-01 | PLATFORM_ADMIN_OVERRIDE_POLICY.md | Accepted | Platform Architecture, Security, Tenant Framework | orgs, auth, tenant middleware | - | Platform override policy is superuser-only.
| 2026-05-01 | SIDEBAR_NAVIGATION_SOURCE_OF_TRUTH.md | Accepted | UI Architecture, Tenant Framework | templates, navigation, workspace UI | - | Template sidebar is active source of truth.
| 2026-05-03 | 2026-05-03_GIRVI_BUSINESSDOC_DECOUPLING.md | Accepted | Girvi Team, DEA Team, Platform Architecture | girvi, dea | - | Synchronous facade chosen over event-driven for financial posting. Facade implemented in dea/facade.py.
| 2026-05-03 | 2026-05-03_LOAN_DISBURSED_AND_RELEASED_EVENT_CONTRACT_ACCEPTANCE.md | Accepted | Girvi Team, DEA Team, Notify_v2 Team, Platform Architecture | girvi, dea, notify_v2 | - | Accepts v1 contracts for loan.disbursed and loan.released.
| 2026-05-03 | 2026-05-03_BUSINESSDOC_INHERITANCE_ANALYSIS.md | Accepted | Platform Architecture, Girvi, DEA | girvi, dea | - | BusinessDoc inheritance from girvi is wrong; BaseLoan/Loan/LoanPayment to be decoupled. PaymentVoucher/JournalEntryVoucher correctly inherit it.
| 2026-05-03 | (inline) DEA_FACADE_BOUNDARY | Accepted | Platform Architecture | girvi, contact, sales, purchase, dea | - | dea/facade.py is the only cross-app import point into DEA. girvi, contact, sales, purchase all migrated. 25 violations remain (tracked by scripts/check_dea_boundary.py).

## Maintenance Rules

1. Add every new ADR here in the same PR.
2. Update status transitions (Proposed -> Accepted, etc.) promptly.
3. If superseded, update both old and new entries.
4. Keep one-line notes concise and factual.

