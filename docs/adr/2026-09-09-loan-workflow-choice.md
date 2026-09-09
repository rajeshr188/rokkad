---
status: accepted
owner: project
updated: 2026-09-09
tags: [loans, workflow, authorization]
---

# One loan lifecycle, two operator workflows

Workspace owners may select SIMPLE (owner review and disburse) or EXTENDED
(separate approval and disbursal). The Company control-plane row stores this
operational preference; the default is EXTENDED for existing and new Workspaces.
Membership changes never switch the preference. Owner changes are audited through
PreferenceAuditLog and serialized against combined confirmations using the
Workspace row lock. No loans are migrated or states rewritten when switching.

SIMPLE offers an owner-only review page for drafts. Confirmation invokes the
existing approval and disbursal services within one outer transaction and loan
lock. Both evidence records remain. Failure rolls back approval; a repeated
confirmation for an already active loan returns the existing disbursal. A
timestamp-signed review token binds the Workspace, loan, persisted input, and
resolved economics. Changed/expired reviews require another review. GET never
approves or disburses. Printing remains a separate action after success.

The shared WorkspaceAccess policy now recognizes loan.approve and loan.disburse.
Owner and Admin defaults include both; custom roles may hold either independently.
Draft create/edit endpoints require data.create/data.edit in addition to view
access. Generic data.view alone no longer authorizes approval or disbursal.
The combined shortcut requires owner authority and both operational permissions.
Renewal also requires both because it approves and activates a successor internally.
This is a deliberate tightening for staff previously admitted by data.view.

Already approved loans can be separately disbursed in either workflow. Extended
mode denies the combined shortcut. It does not enforce different people as maker,
approver, and disburser; such separation requires a future explicit policy.
The underlying draft/approved/active lifecycle, snapshots, schedules, and existing
correction services are unchanged and remain independent of future accounting.
