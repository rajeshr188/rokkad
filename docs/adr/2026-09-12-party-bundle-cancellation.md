---
status: accepted
owner: project
updated: 2026-09-12
tags: [portability, party, cancellation, audit]
---

# Atomic cancellation of unfinished Party bundle profiles

## Context

[Saved bundle history](2026-09-12-persistent-party-bundle-history.md) fixes group
membership and retains live progress. Operators need to abandon remaining staged
work without individually opening six profiles or changing completed evidence.

## Decision

The saved review page offers an explicit, CSRF-protected confirmation to cancel
all members currently in READY or NEEDS_MAPPING. The service requires current
Workspace context, membership, ACTIVE lifecycle and import/view permissions before
any result, including a no-op replay. Request middleware also enforces commercial
access. It locks the Workspace, rechecks access, then locks member batches in PK
order, matching the aggregate commit lock order. It reads current states under
those locks; completed and already cancelled members are skipped.

An outer transaction calls the existing single-batch cancellation command for each
unfinished member. Raw/canonical staged values and row issues are cleared; approval
digests are removed and states become CANCELLED. No Party business rows are changed.
Mapping/defaults, headers, source identifiers/checksums, row metadata, immutable
bundle membership and completed evidence remain. This is cancellation, not full
erasure. Changed groups receive one aggregate audit with bundle and cancelled/
completed batch UUIDs, without staged values. No-op replay creates no extra audit.
A late command or audit failure rolls back all changes.

Concurrent aggregate commit and cancellation serialize: commit first leaves all
completed; cancellation first makes the old approval unusable. Individual commits
are protected by batch locks and completed states are always preserved. No new
model, migration, dependency or cross-Workspace operation is introduced.

## Operator outcome and next work

The saved page redirects to live progress after success; no unfinished members
means no cancellation button. Empty history remains normal until ZIP staging or
verified legacy recovery; individual flat-file imports do not create a group.

The history-filter recommendation was deferred at the owner's MVP closeout.
No further portability feature slice is queued; see the
[scope boundary](../plans/data-portability.md#mvp-scope-closeout-2026-09-12). Preset transfer/deletion, full archives, KYC, Loans and physical
erasure remain deferred.
