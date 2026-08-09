---
status: accepted
owner: project
updated: 2026-08-07
tags: [adr, accounting, periods, bootstrap, k7]
related: [../plans/standalone-accounting-k7-production-boundary.md, ../constitution.md]
---

# ADR: Standalone Accounting Period and Bootstrap Policy

## Decision

- Only Admin/Owner actors with `accounting_period_manage` may bootstrap or
  transition periods through the authenticated facade.
- Allowed transitions are Open to Adjustment-only/Closed, Adjustment-only to
  Closed, and Closed to Adjustment-only/Locked. Locked is terminal.
- Reopening requires a reason. Every transition retains immutable actor,
  timestamp, prior state, next state, and reason evidence.
- PostgreSQL requires the latest transition evidence to match every state
  change, preventing direct ORM bypass or reuse of stale evidence.
- The MVP bootstrap is repeatable and exact: one workspace organization, one
  primary INR book, one supplied period, and only Cash, Accounts Receivable,
  and Sales posting ledgers. Existing conflicting configuration fails closed.

## Consequences

This clears K7.3 without adding chart configurators, UI, tax, inventory, or
runtime source integration. DEA remains production authority.
