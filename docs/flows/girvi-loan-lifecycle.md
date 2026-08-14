---
status: active
owner: project
updated: 2026-06-17
tags: [flows, girvi, lifecycle]
related: [../domain/girvi.md, ../flows/dea-posting-flow.md, ../plans/active.md]
---

# Girvi Loan Lifecycle

Girvi lifecycle behavior should be described using one canonical language across code and UI.

## Core Lifecycle

1. Draft loan is captured with borrower/lender and collateral.
2. Collateral is valued using configured commodity rates.
3. Loan is approved or rejected.
4. Loan is disbursed and accounting is posted through DEA.
5. Interest accrues or is collected according to loan rules.
6. Loan may be renewed, repaid, released, repledged, auctioned, sold, or undone through explicit commands.
7. Each accounting-impacting lifecycle event should be idempotent.

Archived lifecycle sources are preserved in [archive/girvi](../archive/girvi/).
