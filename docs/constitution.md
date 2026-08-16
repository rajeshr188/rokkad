---
status: active
owner: project
updated: 2026-06-17
tags: [constitution, architecture, loans]
related: [AGENT_MEMORY.md, adr/2026-08-16-retire-accounting.md]
---

# Constitution

These are the non-negotiable principles for Rokkad.

1. Loans is an operational lending system, not a general-ledger accounting system.
2. Completed loan lifecycle actions produce immutable Loans-owned evidence.
3. Corrections happen through explicit compensating or reversal events; completed
   disbursals, repayments, accruals, releases, renewals, and auctions are not
   edited in place.
4. Outstanding principal, interest, fees, settlements, and collateral state are
   derived only from canonical Loans records and frozen event evidence.
5. Every material balance change must remain traceable to its originating loan
   action and actor.
6. Party is the canonical counterparty identity for Loans.
7. Workspace/tenant isolation must be preserved.
8. Notification delivery is downstream of Loans-owned notice intent and never
   determines loan state.
9. Rates supply reference evidence; Loans freezes applicable values used by a
   completed calculation where reproducibility requires it.
10. Architecture decisions that change these principles require an ADR.
