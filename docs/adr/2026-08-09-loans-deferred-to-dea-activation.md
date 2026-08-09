---
status: proposed
owner: project
updated: 2026-08-09
tags: [loans, accounting, dea, deferred, activation, reconciliation]
related:
  - 2026-08-08-operational-accounting-integration-deferral.md
  - ../domain/accounting.md
  - ../constitution.md
---

# ADR: Loans Deferred-To-DEA Activation

Date: 2026-08-09
Status: Proposed

## Context

Loans always records immutable business events and durable accounting outboxes.
The audited workspace preference `accounting__integration_mode` controls what
happens next:

- `DEFERRED` records the source event and leaves its intact outbox `PENDING`.
  It does not run DEA readiness or claim that a voucher was posted.
- `DEA` checks accounting prerequisites, sends new events through DEA's public
  facade, stores voucher/journal references, and blocks dependent financial
  actions when required delivery is unresolved.

Changing the preference from `DEFERRED` to `DEA` is not an activation process.
Existing pending events are not automatically scheduled for replay, and they
would become accounting blockers without an explicit historical disposition.
The current retry command also applies to `FAILED`, not untouched `PENDING`,
outboxes. Therefore a workspace with deferred history must not be switched by
preference alone.

## Proposed Decision

Use an **opening-position cutover** as the default activation model. Do not
replay every historical event unless a later regulatory requirement explicitly
demands complete historical vouchers.

At an agreed cutover date, Loans will derive each active loan's canonical
principal, capitalized principal, interest, fees, and Party position from its
immutable event fold. DEA will receive one source-linked, idempotent activation
opening per active loan. Events after the captured watermark will then use the
normal DEA delivery contract.

Closed loans before the cutover remain explainable Loans history but do not
receive fabricated historical vouchers. A disposable development tenant may
instead be recreated and started directly in `DEA`; that is a clean start, not
an activation or migration strategy.

This ADR remains proposed. It documents the recommended path but does not
authorize replay, opening postings, preference changes, or production cutover.

## Required Activation Evidence

An activation run must be workspace-scoped and persist:

- run identity, actor, creation time, cutover date, and state;
- the exact Loans event/outbox watermark included in the opening;
- a frozen per-loan balance and Party projection with deterministic fingerprint;
- selected accounting periods, ledgers, mappings, and policy versions;
- each DEA opening voucher/journal reference and delivery result;
- reconciliation totals and every discrepancy;
- Owner confirmation, failure, reversal, and retry evidence.

Pre-cutover `PENDING` outboxes must not be changed to `POSTED`, because no
individual DEA voucher exists for them. An append-only activation-coverage row
must link each covered outbox to the accepted opening position. After
activation, readiness may treat a pending outbox as resolved only when that
exact outbox is covered by the confirmed activation. UI and reports must label
it **Covered by DEA opening**, never posted.

## Activation Workflow

1. **Start and lock** — the Owner starts an activation run. Loans temporarily
   blocks new financial commands for that workspace while the watermark and
   opening are established.
2. **Preflight DEA** — verify the open activation period, cash and loan-control
   ledgers, interest/fee ledgers where required, Party borrower mappings, and
   absence of unresolved `FAILED`, `PROCESSING`, or missing outbox evidence.
3. **Capture watermark** — freeze the cutover date and exact set of Loans
   events/outboxes included. Later events cannot enter the opening silently.
4. **Preview opening** — show per-loan and workspace totals, proposed DEA
   accounts, accounting recognition, and discrepancies without posting.
5. **Owner confirmation** — require an explicit confirmation and reason. A
   changed preview fingerprint invalidates the confirmation.
6. **Post idempotently** — send source-linked activation openings through a
   versioned DEA facade contract. Never create vouchers or journals directly.
7. **Reconcile** — compare Loans principal, interest, fees, Party totals, and
   the DEA loan-control balances. Any unexplained difference fails activation.
8. **Cover deferred outboxes** — append the exact coverage links for included
   pending events only after their opening voucher reconciles.
9. **Enable DEA** — confirm the run and change the audited workspace preference
   to `DEA`. Post-watermark events then use normal readiness and delivery.
10. **Unlock** — resume financial commands only after confirmation.

## Failure, Retry, And Rollback

- Before any opening is posted, failure leaves the workspace in `DEFERRED` and
  can be retried from a fresh preview.
- Delivery uses deterministic idempotency, so retry returns the original DEA
  effect rather than creating a duplicate.
- A partially posted run remains locked and resumable. It cannot silently flip
  the workspace to `DEA`.
- Rejecting a posted opening requires an explicit DEA reversal and an
  append-only activation reversal record. Vouchers, journals, source events,
  outboxes, and coverage evidence are never deleted or rewritten.
- After ordinary post-cutover DEA events exist, returning to `DEFERRED` is a
  separate controlled decision requiring reconciliation; it is not a casual
  preference toggle.

## Accounting Shape To Decide Before Implementation

The opening contract must identify the balancing account appropriate to the
workspace and cutover policy. At minimum it must separately preserve:

- original loan principal receivable;
- capitalized-interest principal receivable;
- accrued interest receivable when the frozen loan policy uses accrual
  recognition;
- outstanding fees where applicable;
- borrower/Party subledger attribution;
- the corresponding audited activation clearing, opening-equity, or migration
  balance account selected by accounting policy.

Cash already disbursed or collected before cutover must not be posted again.
The opening represents the position at cutover, not a reconstruction of past
cash movement.

## Rejected Default: Full Historical Replay

Replaying every deferred event would retain event-by-event historical vouchers,
but it introduces closed-period decisions, historical account mapping, long
dependency chains, greater reconciliation risk, and possible duplication of
opening or legacy accounting. It remains an opt-in future policy only when the
business or regulator requires it and a separate accepted design defines its
period and mapping rules.

## Implementation Slices

1. Activation run, frozen preview, watermark, and workspace command lock.
2. DEA readiness and source-linked activation-opening contract.
3. Idempotent per-loan posting and append-only outbox coverage.
4. Reconciliation report and Owner confirmation.
5. Audited mode switch, resume/retry, reversal, and rollback controls.
6. Tenant, concurrency, partial-failure, idempotency, and end-to-end tests.

## Acceptance Criteria

- Switching a workspace with deferred history cannot occur through an
  unguarded preference change.
- Preview is read-only and repeatable for the same watermark.
- Concurrent financial activity cannot escape or enter a frozen opening.
- Each active loan and Party reconciles exactly to DEA control balances.
- Covered deferred outboxes remain truthfully non-posted and source-linked.
- Repeated delivery cannot duplicate a voucher or journal entry.
- Failure never leaves a workspace silently half-enabled.
- Corrections use reversal/compensation; no posted or source evidence mutates.
