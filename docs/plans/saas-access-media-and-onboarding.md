---
status: active
owner: project
updated: 2026-09-09
tags: [saas, permissions, private-media, onboarding, licenses]
related:
  - ../adr/2026-09-09-organization-tenant-and-license-access.md
  - ../architecture/control-plane-contracts.md
  - ../STATUS.md
---

# SaaS access, private media and business onboarding

## Scope and accepted direction

Preserve the organization/Workspace tenant, PostgreSQL forced RLS, Membership and
WorkspaceAccess. The owner wants every concern below delivered individually and
incrementally without omissions. This document records the agreed direction and
implementation backlog; it does not claim runtime enforcement has changed.

Organization-wide borrower profiles remain shared subject to permissions. License
scope is an optional owner-configurable future feature, not a universal access rule.
The owner requires a fresh review and explicit approval before implementing it, at
the end of the incremental work. Current organization-wide loan access remains in
place. Role presets below are proposals; exact future scope semantics remain open.

## Delivery register

| ID | Work item | Status | Dependency / completion evidence |
| --- | --- | --- | --- |
| TEN-01 | Confirm organization tenant and optional scope direction | Decision accepted | Linked ADR; scope deferred for fresh owner approval |
| ACT-01 | Inventory actual action authorization and agree role matrix | Route audit in progress | See action-permission audit; service/job and role matrix follow-up tracked |
| ACT-02 | Close action-permission gaps | AP-01 through AP-04 and AP-05 lifecycle/document fixes implemented; draft/photo, funding and setup commands also fixed; operational alert/Party commands also fixed; AP-06a reviewed; local stored grants, Owner editor and invitation safeguards implemented | Server checks plus positive/negative role tests |
| MED-01 | Audit media and artifact access, including deployment | Application inventory complete; external deployment verification deferred | See [media inventory](../implementation/private-media-access.md); development-only environment |
| MED-02 | Close private-media gaps | Application fixes verified (157 tests); external deployment gate open | Authorized Party routes, raw business-media denial, private response caching and upload-widget fixes |
| ONB-01 | Simplify business setup and singleton selections | Implemented and verified through existing setup pages (249 broad + 1 focused tests) | [Business setup flow](../flows/business-setup.md); persisted readiness, optional team and visible single-option defaults |
| SCP-01 | Review optional owner-configurable scope, then implement only if approved | Deferred; explicit approval required | Last phase after action, media and onboarding work; new design review and owner approval |
| SCP-02 | Check indirect disclosures for approved scope modes | Deferred with SCP-01 | Borrower views, reports, search, PDFs and notifications scoped |
| GATE-01 | Integrated acceptance and update operational docs | Pending affected slices | Tests, permission examples and deployment evidence |

Recommended implementation order: ACT-01/ACT-02, MED-01/MED-02, ONB-01, then
SCP-01/SCP-02. The media inventory may be reviewed alongside the action inventory.
Deployment-dependent verification remains separately open if application work is
complete. Do not mark an entire concern done based solely on a narrower code change.

## ACT: actions before license scope

See the [action-permission review](../implementation/action-permission-review.md)
for AP-01 through AP-09 findings, the first draft/photo slice and remaining work.

Observed baseline: loan approval/disbursal have dedicated action checks and draft
create/edit have data.create/data.edit checks. Repayment and full/partial release
views use the general Loans workspace decorator, which checks data.view. This is
a concrete review target; historical control-plane conformance does not establish
fine-grained financial authorization. Inventory the complete path before closing
an issue, including service guards and alternative adapters.

Required inventory:

- Borrower view, create, shared-profile edit, photo operations and export.
- Loan view, create, edit, cancel/reopen, approve, disburse, repay, full/partial
  release, renew, adjustments/accruals/capitalization, reverse and auction actions.
- Collateral photo append/delete, storage movement and verification actions.
- Document preview, issuance/printing, downloads, reports and exports.
- Notifications: view, compose/send, retry and provider administration.
- Workspace, license, series, product, economic setup, team, roles and billing.
- Web, HTMX, direct POST, service, import and background-job entrypoints.

Use the existing permission registry and WorkspaceAccess rather than introducing
another authorization framework. Review effective permissions, including the current
combination of role defaults and assigned permissions, so the UI's role settings
match actual authority. A hidden button must not be the enforcement boundary.

### Proposed role presets for discussion

| Role | Shared borrower profiles | Loan actions within granted scope | Business administration |
| --- | --- | --- | --- |
| Owner | View/create/edit | All permitted lifecycle operations across organization | Ownership, team, setup and billing |
| Administrator | View/create/edit | Broad operations; reversals explicitly controlled | Delegated team/setup; billing only if granted; no ownership transfer |
| Loan operator | View/create; profile edit separately granted | Create/correct drafts; no approval/disbursal by default | None |
| Approver | View | Review/approve; no disbursal by default | None |
| Cashier | View | Disburse, repay; collateral release permission separately granted | None |
| Viewer/auditor | View | Read only; exports separately granted | None |

Roles are action bundles; scope is a separate assignment. Confirm exact presets,
who may return collateral, who may reverse transactions, shared-profile editing,
and bulk export privileges before changing defaults. Different people as creator,
approver and disburser is a separate optional rule: the existing extended workflow
does not enforce distinct actors. The simple owner workflow must continue to work.

Acceptance: viewers cannot mutate by forged requests; each grant permits only its
intended action; owner-only actions remain owner-only; role/member removal is
revalidated; denied actions produce no financial or collateral changes. Preserve
transactionality, audit, idempotency and lifecycle guards.

## MED: protect files beyond RLS

Observed baseline: collateral photos use an authorized Workspace loan/photo route.
Borrower profile images use FileField storage URLs in Party and Loans templates.
Their privacy depends on how media is served. Do not label a URL private merely
because its containing page requires login, or declare a deployment vulnerability
without checking actual serving behavior.

Inventory borrower photos, collateral photos, license evidence, imported files,
layout backgrounds/assets, generated PDFs, exports and notification attachments.
Record storage location, every delivery route, access checks, URL lifetime and any
public media alias/CDN cache. Test direct URLs as anonymous users, another workspace's
member, a removed member, and an authorized viewer. Future scope tests also include
a member without the loan's license assignment.

Choose the simplest supported private delivery: authorized application responses,
private internal server delivery, or short-lived signed private-storage URLs after
authorization. Ensure no public origin path bypasses the chosen route. Signed URLs
remain usable until expiry unless separately revoked; document that revocation limit.
Avoid caching protected content across users/workspaces. Do not log signed secrets.
Keep storage credentials private, and retain transaction-safe/shared-file cleanup.

Borrower profile-photo access follows shared organization borrower-view permission.
Collateral and loan documents follow their loan's license scope. KYC/evidence and
bulk download privileges need explicit classification rather than assumptions from
profile visibility. Record application tests and production serving verification
separately; the existing manual phone/printer deferral is unrelated to media privacy.

## ONB: evolve the current setup journey

Current evidence:

- `apps/orgs/views.py:workspace_create` already uses the control-plane creation
  service, then redirects to `workspace_slug_settings_setup`.
- `apps/onboarding/services/setup_checklist.py` composes general setup progress.
- `apps/tenant_apps/loans/selectors/setup.py` checks license, numbering, economics
  and an active loan product; origination also requires an active borrower.
- General progress currently includes team invitations, which can make a sole
  owner's setup look unfinished even when lending is ready.

Therefore this needs an incremental UX change, not a replacement tenancy system:

1. Present **Set up your business**, using the existing workspace-creation service.
2. Continue in the created workspace with one resumable sequence: business details,
   real license/evidence, numbering series, reviewed economics and loan product,
   then first borrower/loan. Persist completed steps through existing services.
3. Review existing defaults (gold 2% monthly, silver 4%, fixed INR 10 document fee)
   before saving. Explain monthly periods, deducted fees and effective dates.
   Defaults do not silently replace existing policies or imply terms were accepted.
4. Distinguish required lending readiness from optional team invitations, advanced
   printing, notifications and other general setup. A sole owner need not add staff.
5. Preselect a sole eligible license/series and, where unambiguous, product. Derive
   eligibility from current workspace, permissions and loan date; include future
   license assignments. Show the selection; preserve user-entered values on errors.
   With multiple valid choices, use an explicit valid preference or ask the operator.
6. Keep the owner workflow choice explicit; adding staff must not silently change it.
7. Provide a visible Setup path after completion; permit resume after reload/logout
   without duplicate workspaces, licenses, series or policies.

Acceptance: fresh owner reaches a valid first loan; one-license owner avoids
repeated selections; multi-license choices remain clear; existing businesses are
not reset; invalid dates/expired licenses are still rejected; defaults and selection
never bypass server validation, entitlements or membership checks.

## SCP: optional scope, last and subject to explicit owner approval

Do not implement license/branch scoping now. After action permissions, private media
and onboarding are addressed, return to the owner with a concrete design covering:

- Whether to enable scope and which modes the owner can choose; organization-wide
  behavior must remain available. No universal assigned-license rule is accepted.
- Shared borrower profiles and how their financial tabs/aggregates behave in each mode.
- Which records each role can see and act upon; no assumption of creator-only access.
- Existing-member migration, explicit all-license versus selected-license grants,
  empty selections, new licenses, expired licenses, and owner authority.
- Turning restrictions on/off, changing assignments, audit, effective timing and
  in-flight/background operations. Changes must not rewrite loan ownership/history.
- Every indirect surface: photos/PDFs, collateral, releases, reports/exports, search,
  borrower statements, notifications and cross-license renewals/splits/transfers.
- Whether database defense is needed for intra-workspace restrictions; current
  workspace RLS does not implement staff-level license scope.

Only after the owner's explicit approval may implementation begin. Record that
approval and the exact reviewed behavior before schema, permission, query or UI
changes. Test both organization-wide and approved restricted modes. These review
criteria are not authorization to implement any assignment model now.

## Tracking discipline

Update each ID with findings, implementation, test evidence, deployment evidence
where relevant, and remaining decisions. Link status updates here. Keep the accepted
ADR distinct from proposals and completed implementation. Do not lose this backlog
when an individual UI or security slice is committed.

## AP-06 implementation checkpoint

The [role migration delivery record](workspace-role-migration.md) documents the
implemented development-only cutover: local stored grants, forced RLS, Owner editor
and invitation safeguards, with fixed global template identities retained.
Media privacy and onboarding remain pending; optional license scope keeps its
separate final review and approval gate.
