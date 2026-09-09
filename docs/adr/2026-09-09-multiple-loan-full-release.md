---
status: accepted
owner: project
updated: 2026-09-09
tags: [loans, releases, custody, batches]
related: [2026-08-05-pawn-loan-release-and-renew-only.md, ../flows/multiple-loan-release.md]
---

# Multiple-loan full release

The owner approved grouping exact full releases, including different borrowers and
different collectors within one batch. Use one payer for the recorded total and one
collector per loan. Default the collector to that loan's borrower; another collector
requires a name, relationship and the operator's authorization confirmation.

Keep each loan, settlement event, release number, item return, schedule termination
and subsequent reversal under its existing Loans domain rules. A batch is an immutable
grouping of those releases, not another repayment, merged debt or accounting journal.

Use the existing current-date full-release quote and command. Require data.view and
loan.release at the command boundary, including retries. All loans must belong to the
explicit active Workspace. Multiple licenses within it remain permitted under current
access; optional license scoping remains shelved as FW-001.

Preview without writes. Sign the per-loan amounts and revisions, expire new submissions
after ten minutes and require fresh confirmation after a date or record change. Lock
loans in ascending ID order. Complete a maximum of 20 loans in one transaction, so
any failure rolls back all settlements, numbers, custody changes and batch evidence.
A unique Workspace/request key makes identical retries return the original batch;
changed details under a used key are rejected.

The operator confirms the exact payment total and verifies each collector and item
handover readiness. Database atomicity does not make physical handovers atomic.
Absent collectors must be removed before completion. Paid-now/collect-later, mixed
partial repayment, split collectors within a loan, renewals and batch reversals are
outside this version. Existing individual compensating reversals remain available;
the original batch amount stays historical and reversed lines are labelled.

Two directly Workspace-owned tables store the batch and per-release collector
snapshots. Forced RLS, immutable SQL guards, reference-scope checks and deferred
total reconciliation protect this evidence. Individual receipt projections include
that loan's collector details; no combined document or notification is automatically
sent to other borrowers. Existing custom layouts can opt into the new field keys.
