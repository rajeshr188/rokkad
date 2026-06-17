---
status: active
owner: project
updated: 2026-06-17
tags: [implementation, girvi, services]
related: [../domain/girvi.md, ../flows/girvi-loan-lifecycle.md, ../plans/active.md]
---

# Girvi Services

Girvi command/use-case services should own lifecycle operations that are too large or risky for views/models.

## Use Cases

- Loan creation and approval.
- Disbursal.
- Repayment.
- Release.
- Renewal.
- Split/merge.
- Auction and sale.
- Undo/reversal.
- Custody and repledge workflows.

## Guidelines

- Views coordinate request/response only.
- Models hold state and invariants, not accounting orchestration.
- Accounting effects go through DEA facade/services.
- Results should be explicit and previewable where user confirmation is needed.

Archived service and lifecycle sources are preserved in [archive/girvi](../archive/girvi/).
