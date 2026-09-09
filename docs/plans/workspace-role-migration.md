---
status: implemented
owner: project
updated: 2026-09-09
tags: [plan, authorization, migration, rls]
related:
  - ../adr/2026-09-09-workspace-owned-roles-and-stored-grants.md
  - ../implementation/action-permission-review.md
  - saas-access-media-and-onboarding.md
---

# Workspace role migration delivery

The owner confirmed development-only data and authorized the simpler implementation.
The [accepted ADR](../adr/2026-09-09-workspace-owned-roles-and-stored-grants.md) replaces
the earlier staged-production proposal. Optional license scope remains separate.

## Implemented

- WorkspaceRole and WorkspaceRoleGrant hold local grant sets with forced RLS,
  non-null ownership, registry coverage, uniqueness and database scope/identity guards.
- Membership/invitation template references preserve global resolution and ownership
  identity. Runtime action checks read stored Workspace grants only.
- Defaults seed once; subsequent bootstrap calls do not reset owner edits. Global
  templates are read-only in admin and are not a live permission editor.
- Owner-only Team permission editing has revision checks and before/after audit.
  Admin, Member and Viewer can have different grants in different Workspaces.
- Invitations validate actual capability subsets and protected actions, then recheck
  current inviter authority and a grant fingerprint at acceptance. Used invitations
  cannot restore removed members. Canonical ownership safeguards remain.
- Retired Girvi/DEA/accounting permissions are removed. Party contact aliases remain
  supported; deleting only data.edit does not remove contact.edit authority.

## Local migration evidence

Migrations orgs.0008 and orgs.0009 were applied through owner-only migration settings.
The 7 Workspaces and 7 memberships remain; there are 28 local default-role records.
There were no pending invitations to reissue. The old role sequence was behind its
explicit seeded IDs; the migration advances it safely before adding the missing
Viewer template. No loan or borrower data was deleted.

Use normal restricted runtime settings for web and workers. Do not rerun an old
code version to undo owner edits: the former default union could restore access.
A future production rollout requires its own deployment/backup rehearsal; this
local development change does not establish production migration evidence.

## Inventory command

`python manage.py role_migration_preflight` emits deterministic JSON in a PostgreSQL
repeatable-read/read-only transaction and does not send or mutate anything. Version 2
includes actual local grant sets/revisions in local_roles, alongside global template
metadata in roles. Template defaults are not current member authority. It includes
inactive Workspaces, historical invitation IDs/status, unused templates and diagnostic
findings. Role labels and identifiers are internal operational metadata; emails,
usernames, tokens and borrower data are excluded.

Source and grant hashes detect changes; they are not signatures or cutover approval.
Retired/unknown and sensitive-grant findings are review heuristics. The initial
pre-migration snapshot found retired codes in 3 roles; after cleanup the local
inventory has no findings. Diagnostics do not replace HTTP/service/RLS tests.

## Remaining separate work

Private borrower/document media delivery and simpler business onboarding are next in
the SaaS delivery register. Arbitrary owner-created role labels/presets are not part
of this fixed-template editor; add them only for a concrete need. Optional license
scope stays last and requires fresh review and explicit owner approval.
