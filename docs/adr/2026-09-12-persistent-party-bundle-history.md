---
status: accepted
owner: project
updated: 2026-09-12
tags: [adr, portability, history, rls]
---

# Persistent Party bundle history and reopenable reviews

The owner authorized the recommended follow-up to
[atomic Party bundle commit](2026-09-12-atomic-party-bundle-commit.md). Add one
Workspace-owned ImportBundle table containing a public UUID, source namespace and
SHA-256, staging actor/time and six nullable, typed one-to-one batch references.
Null means that profile was empty. The record stores immutable source/group evidence;
it does not copy private row values, ZIP bytes, approval tokens or mutable progress.
No business exchange schema or dependency changes.

## Ownership and immutability

Migration 0010 enables forced RLS through the existing tenancy operation and adds
the model-specific migration gate. There are now 108 registered Workspace-owned
models, including nine portability infrastructure tables. Direct non-null Workspace
ownership, ordinary protected foreign keys and unique per-profile batch references
prevent reusing a batch in another history record. A SQL insert guard checks each
batch's Workspace, exact profile, JSONL source type and namespace; source batch
metadata was already immutable. The guard also validates the checksum. Every update
or delete of the history record is rejected. Migration reversal refuses retained
history instead of silently dropping it. Future retention/erasure needs its own policy.

Staging creates batches, their previews, audit evidence and history in the same
transaction. Failure creating history rolls back the staged set. Empty uploads still
receive a history entry; repeated uploads are separate attempts with separate groups.
The compatibility staging service still returns its ordered profile/batch list.
Progress is derived from fresh linked batch states: Empty, Awaiting review, Completed,
Cancelled or Partly finished. No independent state machine can drift from individual
commit/cancellation or aggregate completion.

## Older imports

The owner-only migration backfills earlier exact staging audit records. It requires
all six profile keys, a valid namespace/checksum, a retained actor/Workspace and
matching retained batches. Recover original audit timestamp/actor. Already recovered
groups are skipped; contradictory overlapping membership, missing, foreign or malformed
evidence is skipped rather than guessed. Migration output reports recovered and
unverifiable counts without exposing private values. Individual batches remain
available even when group evidence cannot be recovered. The migration establishes
and restores transaction-local Workspace context during the scoped backfill.
No arbitrary individual uploads are inferred to belong to a bundle.

## Reopening and approval

Import Party data now includes paginated Bundle history (20 attempts per page),
with stage date, source namespace and live progress. Each record has a stable
Workspace-qualified URL. The current import/read permissions, membership, ACTIVE
lifecycle and commercial middleware still apply. Knowing a UUID grants no access;
foreign and missing records fail closed, and responses remain no-store.

Opening a saved record generates a fresh short-lived signed receipt from its
immutable membership. The receipt also names the history UUID, and bundle services
check its members against the stored record. Old receipt-only links still work
until their original expiry. New upload receipts link to the stable saved page.
GET does not create batches, change membership or extend an existing approval.

Combined approval still expires after one hour and belongs to the operator and
Workspace. Reopening requires a new preview and approval. A confirmation posted to
a saved page must also belong to that history record. Existing stale-input/destination
checks, all-or-nothing commits and permission-checked replay are unchanged. Completed
and cancelled histories stay readable; partially finished bundles continue through
individual profiles. The saved page does not undo earlier commits or revive cancelled
batches. No ZIP file or receipt storage is needed to reopen a verified saved group.

The recommended cancellation follow-up is now implemented; see the
[cancellation decision](2026-09-12-party-bundle-cancellation.md). Preset transfer/deletion, full archives, KYC files, Loans and
physical erasure remain deferred. Loans restoration/opening-position semantics
still need separate executable contracts.
