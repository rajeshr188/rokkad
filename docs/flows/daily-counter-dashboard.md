---
status: active
owner: project
updated: 2026-09-08
tags: [dashboard, counter, loans, workspace]
related: [first-loan-setup.md, ../domain/pawn-loan-financial-read-models.md]
---

# Daily counter dashboard

The explicit Workspace dashboard opens daily work for users with `data.view`.
It defaults to the first nonempty queue in this order: overdue, due today,
awaiting disbursal, drafts, schedule review. Every queue's count remains visible.
Selecting a queue opens its oldest items first, 20 loans per page.

| Queue | Source | Next action |
|---|---|---|
| Drafts to review | Current DRAFT loans | Open loan to continue or review |
| Awaiting disbursal | Current APPROVED loans | Review the existing disbursal form |
| Payments due today | Unpaid schedule obligations dated today | Open repayment form |
| Overdue payments | Unpaid schedule obligations dated before today | Open repayment form |
| Schedule needs review | Missing/empty active schedule or allocation findings | Review loan evidence |

Payment queues cover ACTIVE loans only. The same loan may appear in both payment
queues for different unpaid obligations. Canonical schedule selection and
allocation folding respect effective dates, terminations, and reversals. Fully
paid obligations and future obligations do not enter today's queues. Schedule
amounts contain principal and contractual interest, not unscheduled fees or a
payoff quote; the existing repayment flow determines collection behavior.

Search opens the existing loan list using borrower name, Party code, or loan
number. Borrower browsing and New loan stay prominent. Setup remains available
to authorized administrators below counter work and in Settings.

The view checks the explicit Workspace access policy before invoking the queue
selector. The selector also checks the active database Workspace context and
filters Workspace-owned rows. It performs no mutations. Destination forms retain
their existing authorization, lifecycle, validation, and CSRF requirements.

Current counts require reading the Workspace's draft, approved, and active loans
and active repayment schedules. Pagination limits display, not this calculation;
large-portfolio query optimization can be addressed separately with measured data.
