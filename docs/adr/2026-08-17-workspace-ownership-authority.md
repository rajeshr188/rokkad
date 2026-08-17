---
status: accepted
owner: project
updated: 2026-08-17
tags: [adr, workspace, ownership, membership]
related:
  - ../architecture/control-plane-contracts.md
  - platform-admin-override-policy.md
---

# Workspace Ownership Authority

## Status

Accepted.

## Context

Ownership is represented by `Company.owner`, Memberships using the Owner role,
and `CompanyOwnership`. Runtime code overwhelmingly reads `Company.owner`;
creation writes it and creates an Owner Membership. Last-owner rules instead
count Owner Memberships. `CompanyOwnership.transfer_ownership()` is not atomic,
does not update `Company.owner`, and its `(user, company)` uniqueness cannot
record repeated tenures. `Company.owner` also currently cascades user deletion.

## Decision

`Company.owner_id` is the sole authoritative answer to “who owns this
Workspace?” Every persisting Workspace has exactly one owner.

The owner must have the Workspace's single mirrored Owner Membership. That
Membership supplies permissions but is derived from the authoritative FK;
other members cannot hold the semantic Owner role.

Phase 2 introduces one atomic, row-locked
`transfer_workspace_ownership()` command. It requires an existing target
Membership, current-owner or audited platform-admin authority, a reason, and an
explicit non-owner role for the previous owner. It updates the FK and both
Membership roles together and appends an `OWNERSHIP_TRANSFER` audit event.

Owner user deletion is protected until transfer. `CompanyOwnership` is retired
as live state after reconciliation; audit events retain transfer history.

## Alternatives considered

1. Owner Membership is canonical. Rejected because multiple matching rows are
   easy to create, “exactly one” needs conditional constraints tied to a mutable
   global role name, and dominant callers already use `Company.owner`.
2. `CompanyOwnership` is canonical. Rejected because the current model permits
   multiple active owners, cannot represent repeated tenure, and complicates
   ordinary owner queries.
3. Keep all three equal authorities. Rejected because drift is inevitable and
   transfer has no single commit point.

## Consequences

Owner queries and foreign-key integrity stay simple. Owner Membership remains
compatible with existing permission flows but becomes an enforced mirror.
Transfer history moves to the audit stream. The owner FK deletion policy and
existing inconsistent rows require a migration.

## Migration implications

Phase 2 audits all three representations, reconciles each Workspace to
`Company.owner_id`, enforces one matching Owner Membership, changes owner
deletion to `PROTECT`, adds the transfer command and concurrency tests, then
removes `CompanyOwnership` and direct role/owner authorization shortcuts.

