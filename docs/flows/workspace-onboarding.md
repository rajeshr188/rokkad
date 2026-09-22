---
status: active
owner: project
updated: 2026-09-22
tags: [flows, workspace, onboarding, invitations]
related: [../architecture/control-plane-contracts.md, business-setup.md]
---

# Workspace onboarding

Account introduction and branch readiness are separate. Rokkad uses a shared
PostgreSQL schema with forced Workspace RLS; onboarding does not create a tenant
schema or seed retired accounting/DEA modules.

## New owner

1. Sign in and complete the profile step.
2. Create a Workspace through the existing control-plane service. It creates the
   owner relationship and Membership; a profile preference is navigation only.
3. Optionally invite staff. Existing service authorization and role rules apply.
4. Read the quick customer-visit guide. Optional role/feature preferences are
   onboarding answers, not permissions. Skip remains available.
5. Completion resolves the preferred accessible Workspace and redirects to its
   setup page; without one, it goes to the Workspace list. The completion page
   template is not the active completion destination.
6. Complete the actual [business setup](business-setup.md) prerequisites. Account
   progress, a saved customer and the introductory guide do not authorize lending.
   Loan preflight and domain services remain authoritative for each operation.

## Existing branch or invited staff

Use the existing Workspace or invitation entry path. The introduction links to
My Workspaces, so migrated operators are not instructed to create another branch.
Membership and action permissions determine available operations. An introductory
role preference never grants access. This UI increment does not change invitation
acceptance, onboarding routing or existing progress persistence.

Owners manage elevated roles. Other staff remain limited by their granted access;
last-owner protections and control-plane service checks remain in force.

## Customer entry

Search existing customers by name, phone or code before adding another record.
The add/edit page shows identity/contact details first and retains all existing
Party fields under More details. That section opens for editing and after a failed
submission. A generated code is still available by leaving the code blank.

Saving uses the existing Party create service/update path and redirects to the
customer record, where addresses, identifiers and documents can be added. It does
not verify identity or create/approve a loan. Invalid submissions keep entered
text and display an error summary linking to the relevant fields. A new file must
be selected again after an error; the page explains this browser limitation.

The customer form and quick guide use English/Hindi copy and responsive layouts.
Other onboarding step forms and the full setup checklist still need the broader
bilingual/task-based redesign. Automated tests are not physical-device or novice
operator acceptance. See [implementation evidence](../implementation/accessible-directory-redesign.md).
