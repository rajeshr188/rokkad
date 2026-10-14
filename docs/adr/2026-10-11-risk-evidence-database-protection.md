---
status: accepted
owner: loans
updated: 2026-10-11
tags: [monitoring, risk, database, immutability, rls]
---

# ADR: Risk evidence database protection

MR-04 of the [combined plan](../plans/combined-loan-monitoring-20261011.md)
enforces the existing risk evidence contract below Python model methods.
It follows [confirmed recovery](2026-10-11-risk-integrity-and-confirmed-recovery.md)
without introducing another assessment or servicing lifecycle.

## Decision

- Risk events are append-only under PostgreSQL: UPDATE, including no-op/bulk
  updates, and DELETE are rejected. Runtime receives no TRUNCATE or table-owner
  privileges. Instance-level validation remains an additional application check.
- Composite foreign keys enforce snapshot-to-loan Workspace ownership,
  event-to-snapshot Workspace/loan identity, and alert source/recovery event
  Workspace/loan identity. They also protect against parent reassignment.
- Snapshots remain mutable current projections, but their ID, Workspace and loan
  cannot be reassigned. Alerts remain mutable work items for severity and
  resolution, but their ID, Workspace, loan, original source event and kind stay
  fixed. Risk events continue pointing to the live snapshot, not a newly invented
  immutable history of every assessment field.
- A risk-linked borrower notice must retain both its alert and that alert's exact
  source event for the same Workspace/loan. Those source links cannot be replaced
  or detached afterward. Ordinary notices with neither risk pointer and existing
  routing updates retain their contracts. This creates no communication intent.
- Retained invalid links require explicit review. The owner-only read-only
  preflight and the migration run the same fixed checks. The migration rejects
  violations before installing guards; it does not reassign, delete or fabricate
  evidence. Constraint installation also validates existing rows atomically.
- Previously resolved alerts without a cure event remain unchanged and are
  reported separately as legacy gaps. New references, when present, must be
  correct; this upgrade does not invent missing past recovery evidence.

Forced RLS remains enabled on the existing registered tables. No new tenant table,
runtime RLS bypass, privilege elevation in a trigger or financial posting is added.
Preflight requires a PostgreSQL owner migration role with explicit RLS bypass so
an empty runtime view cannot be mistaken for a clean global inventory.

## Delivery

Migration 0072 adds target uniqueness, one paired-pointer check, five composite
foreign keys and four narrow triggers. Apply only through owner-only migration
settings. Before the coordinated release, run `check_risk_evidence` with those
settings on the intended database and retain its count-only report. Review any
failure explicitly; a passing local rehearsal does not establish live cleanliness.
The schema reversal removes these guards without changing retained rows; it
requires the owner role and would restore the former protection gap.

See [MR-04 implementation and validation](../implementation/risk-evidence-guards-mr04.md).
