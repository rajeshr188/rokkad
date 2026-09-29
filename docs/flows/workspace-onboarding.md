---
status: active
owner: project
updated: 2026-09-29
tags: [flows, workspace, onboarding, invitations]
related: [../architecture/control-plane-contracts.md, business-setup.md]
---

# Workspace onboarding

Account introduction and branch readiness are separate. Rokkad uses a shared
PostgreSQL schema with forced Workspace RLS; onboarding does not create a tenant
schema or seed retired accounting/DEA modules.

On 29 September, automatic invitation and account verification/reset dispatch was
enabled, up to ten messages per run approximately a minute apart. The two account
delivery/link rehearsals and subsequent scheduled-run checks passed. Invitation creation/acceptance does not start a
subscription or grant commercial access. Public trial signup remains disabled;
the owner-selected [30-day offer](../plans/public-workspace-trial.md) is prepared
separately from the private billing catalog. New Workspaces currently need an
administrator access decision before ordinary business use. Existing Workspaces
retain their current access. Verified Google sign-in and verified email/password
identities can use the invitation acceptance flow. Verification/reset hooks now
queue through the monitored SES worker despite the shared in-memory default backend.
The local browser journey passed with captured mail; production trial Plan 3 is
prepared but unassigned, unpublished and not activated.

## New owner

1. Sign in and complete the profile step.
2. Create a Workspace through the existing control-plane service. It creates the
   owner relationship and Membership; a profile preference is navigation only.
3. When the reviewed public trial is configured and enabled, a newly created
   Workspace routes to the 30-day/six-member offer. The verified owner explicitly
   accepts; each owner account gets one public trial Workspace and creation alone
   starts no trial. Expiry or transferring the first Workspace does not restore
   that allowance. Successful acceptance returns to team
   setup. This routing is implemented locally and not yet enabled in production.
   Optionally invite staff. Pending invitations reserve seats; concurrent changes
   cannot exceed capacity. Existing service authorization and role rules apply.
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

On both add and edit, select front/rear camera, choose **Use camera**, allow browser
access, then **Take photo**. Review the preview and use the camera again to retake,
or discard the new photo. Selecting an image file also previews it. **Save customer**
uploads the selected image; preview alone changes no saved record. Camera access
needs HTTPS (localhost is supported for development); file upload is the fallback.
Edit shows the existing photo through its authorized private URL.

On the customer record, review addresses and identity evidence, then choose
**Start loan for this customer**. The draft opens with that customer selected when
branch prerequisites are met. Otherwise the screen identifies the next required
setup step. Owners can review branch setup; staff follow the existing access gates.
Imported history does not need to be recreated to configure new lending.

The customer form and quick guide use English/Hindi copy and responsive layouts.
Other onboarding step forms and the full setup checklist still need the broader
bilingual/task-based redesign. Automated tests are not physical-device or novice
operator acceptance. See [implementation evidence](../implementation/accessible-directory-redesign.md).
