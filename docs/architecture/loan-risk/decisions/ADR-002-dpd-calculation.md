---
status: proposed
owner: loans
updated: 2026-08-11
tags: [decision-brief, loans, obligations, dpd]
related: [../concepts/repayment-obligations.md, ../concepts/delinquency-dpd.md]
---

# ADR-002: DPD Calculation

## Status

Proposed decision brief. Contractual interest cadence remains an open business
decision.

## Context

Current overdue is maturity-based and cannot explain partial or multiple dues.
Risk monitoring needs deterministic oldest unpaid due date and DPD without
overloading `PawnLoan.state`.

## Proposed decision

- Persist immutable contractual obligations and immutable allocations.
- Derive DPD from the oldest unpaid obligation due before the as-of date.
- An obligation due today has zero DPD.
- Derive satisfied, outstanding, overdue, and buckets; do not store mutable
  truth flags.
- Generate obligations from the frozen ProductVersion for the four approved
  repayment structures; finalize their exact cadence before implementation.
- Preserve current notice/auction authority until a separate accepted ADR
  adopts obligation-based eligibility.

## Consequences

Partial payments, historical assessment, bucket transitions, and cures become
explainable. Repayment, release, renewal, auction, waiver, and reversal services
must append obligation allocations transactionally.
