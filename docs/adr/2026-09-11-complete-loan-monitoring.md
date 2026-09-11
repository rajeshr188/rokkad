---
status: accepted
owner: loans
updated: 2026-09-11
tags: [monitoring, policy, evidence, rls]
---

# ADR: Complete monitoring and immutable policy amendments

The owner approved increment 4 of the
[Rates/appraisal review](../implementation/rates-appraisal-monitoring-review.md).
This extends the [freshness decision](2026-09-11-collateral-freshness-and-reappraisal.md).

## Decision

- The portfolio starts from every ACTIVE PawnLoan in the explicit Workspace and
  left-joins its saved assessment. No snapshot means UNASSESSED. Closed loans leave
  this active portfolio; their loan records and evidence remain available.
- A current assessment must have status CURRENT, today's local as-of date and the
  current projection contract. A past or future date, changed source evidence or
  older projection contract is outdated. Reads derive this status without updating
  saved evidence. ERROR remains a separately visible failed attempt.
- Current assessment does not mean adequate collateral. Required stale/missing
  evidence produces unknown coverage even after a successful calculation. Show
  repayment performance, overdue/DPD and collateral coverage separately. Copy
  coverage exposure, LTV, shortfall/headroom and per-item evidence dates/blockers
  from the authoritative selectors into projection provenance; do not recalculate
  money in templates or allocate loan debt equally across items.
- Monetary portfolio totals are unavailable if any active loan lacks a current,
  successful monetary assessment. Do not silently sum a subset as the whole
  portfolio. Current assessments with unknown collateral can still provide valid
  monetary totals; unknown coverage has its own count. Severity/product breakdowns
  cover current assessments only.
- Source signals invalidate projections inside the source transaction, while its
  transaction-local RLS context still exists. Rollback restores both source and
  projection state. Existing ERROR rows remain failed/retry candidates until a
  successful assessment; a first failure has no successful fingerprint to mark
  stale. Do not defer this database update to on_commit outside context.
- Reuse the existing explicit-Workspace reassessment command. Optional repeated
  passes recompute the local date, own a new Workspace context each time and select
  a bounded batch, using skip-locked loan rows. Unassessed loans precede the oldest
  attempted projections; errors move to the back after an attempt so they cannot
  monopolize a batch. UI refresh remains capped at 50, command maximum 1000.
- The repeating worker is an internal projection job, uses restricted runtime
  credentials, requires ACTIVE Workspace lifecycle and creates only projections,
  immutable risk transitions and internal alerts. It never originates loan events,
  appraisals, market quotes, auctions or borrower messages. Existing outbound
  communication still requires its separately authorized preview/confirmation,
  with a current-date projection prerequisite.
- Use the existing command/process deployment approach. The optional Compose
  monitoring profile runs one explicitly selected Workspace every five minutes,
  50 loans per pass, through the same role/migration startup checks as web.
  No queue framework, Redis requirement, database scheduler table or implicit
  enumeration of tenants is introduced. Deployment operators must enable it and
  monitor errors/backlog; adding a profile does not start a running scheduler.

## Monitoring policy amendments

Earlier policies remain immutable, including their stored effective_until. An
explicit successor supersedes an open-ended policy from the successor's
`effective_from`, without rewriting an earlier row. The authorized setup service
locks the Workspace, requires the reviewed latest predecessor, preserves hidden
custody/severity settings, assigns the next scope version and records actor/reason.
Amendments start today or later, never before the predecessor's start. A second
submission against the old version is rejected. Same-day reviewed corrections
are allowed and the later version applies for that calendar date.

Resolution still prefers a license override over the Workspace default. Within a
scope it selects the latest effective start and version; legitimate overlaps must
be members of an explicit predecessor chain. For dates before a successor starts,
the earlier policy remains effective. Historical reads use current corrected
knowledge for that date, while previously saved assessment provenance identifies
its original immutable policy. This does not change frozen loan economics or
introduce license-scoped staff permissions.

PostgreSQL rejects policy UPDATE/DELETE, wrong-Workspace license/predecessor links,
unrelated overlapping periods and branching predecessors. Existing legacy policy
values and possibly unknown authors remain intact. Recorded authors are protected
from deletion. Finite legacy policy periods remain supported for resolution; this
amendment UI targets the open-ended policies created by ordinary setup.

## Rollout and validation

Loans migration 0007 adds predecessor/reason and guards, protects policy authors
and marks existing saved assessments outdated for the V2 projection contract.
It creates no tenant-owned table or new grants. Apply it through owner-only
migration settings; web and workers remain restricted.

Tests cover all-active coverage, unknown versus outdated, date rollover, missing
financial totals, fair bounded retries, same-day policy changes, scope and actor
checks, committed/rolled-back invalidation under RLS, competing policy edits and
batches, and migration preservation. See [Status](../STATUS.md) for run evidence.
