---
status: accepted
owner: project
updated: 2026-09-09
tags: [adr, authorization, workspace, roles]
related:
  - 2026-08-17-workspace-authorization-contract.md
  - 2026-08-17-workspace-ownership-authority.md
  - ../plans/workspace-role-migration.md
---

# Workspace-owned roles and stored grants

## Context and development simplification

The owner confirmed all current data is experimental development data and authorized
implementation. We replaced the earlier production-style staged proposal with a
small migration that preserves the existing Workspace and membership records.
The organization remains the SaaS tenant. Optional license scope is not part of this
change and still requires the separately agreed final review and approval.

Previously, globally shared Role permissions were combined with role-name defaults
on every access check. Clearing a stored grant could not revoke a default, and
changing a global role affected unrelated businesses.

## Decision

Keep Role as a fixed global template/identity for Owner, Admin, Member and Viewer,
and for existing legacy custom-role references. It is read-only in Django admin.
Membership and CompanyInvitation keep their template FK; that FK supplies identity
and labels, not live grants. This avoids rewriting control-plane ownership and
pre-RLS membership queries merely to change grant storage.

WorkspaceRole owns one (Workspace, template) pair, with a revision for stale-edit
protection. WorkspaceRoleGrant stores a permission FK plus its direct Workspace and
WorkspaceRole FKs. Both tables have non-null ownership, forced RLS, explicit registry
coverage and unique keys. SQL guards prevent grant/role Workspace mismatches and
changing a WorkspaceRole's identity. A user in two businesses receives the grants
of each business's distinct local pair.

WorkspaceAccess loads only stored local grants, using an explicit bounded
workspace_context after resolving the global membership. It never seeds during a
read, consults profile preferences or unions template defaults back into live access.
The compatibility helper derives its codes from WorkspaceAccess. Unknown catalog
codes fail closed. No explicit deny set or per-member override was added.

Membership creation initializes local default roles once; repeat seeding does not
overwrite grants. A legacy custom template is copied only when explicitly initialized
for that Workspace. Template changes do not update existing local grants. There is
no owner UI for creating/renaming global templates or introducing new role presets.

## Ownership and delegation

Company.owner remains canonical, with the existing mirrored Owner membership and
ownership-transfer safeguards. The Owner's local permission set cannot be edited
through the role service. Non-owner actors never receive workspace.transfer from
ordinary stored grants. Existing Owner-only member removal, role assignment,
billing and physical custody rules remain independent of ordinary action grants.

Only the current member Owner or an explicit platform override may edit local role
grants. Edits lock the local role, reject stale revisions, validate known codes and
audit before/after grants and affected member count. The editor is under Team and
changes one Workspace at a time. It exposes current delegated app actions, not
unimplemented own-record restrictions or an apparent way to assign ownership.

Invitation choices and service validation use the same policy. Non-owner inviters
need team.invite; target grants must be a subset of their own, with no protected
administrative capabilities. Labels cannot make a powerful custom role safe. The
Owner can invite local non-Owner roles, subject to normal invitation permission and
capacity checks. Ownership is assigned only by transfer.

New invitations record the normalized grant fingerprint. Acceptance locks the
invitation and target local role, rechecks verified recipient/current inviter
authority and rejects changed fingerprints. Existing accepted invitations remain
idempotent while membership exists; they cannot restore a removed membership.
Queued business notices keep their separately authorized delivery policy.

## Migration and limits

orgs.0008 copies current supported template/default grants into local records,
removes retired Girvi/DEA/accounting permission rows, and adds the RLS tables and
invitation fingerprint. Contact codenames are retained because Party uses them.
Pending pre-fingerprint invitations are revoked for reissue; the local inventory
had none. orgs.0009 protects local role identity. No Workspace, member or loan
records are deleted by these migrations.

This is a development cutover, not a production rollout recipe. Existing global
custom templates remain bootstrap metadata; arbitrary owner-defined role creation
and renaming are not implemented. Reverting to the old resolver after local edits
could regrant revoked access: use a forward fix instead of a silent legacy fallback.
Any future delegated administrative action needs explicit classification and tests.
