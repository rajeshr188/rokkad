---
status: active
owner: project
updated: 2026-09-09
tags: [authorization, loans, audit, permissions]
related:
  - ../plans/saas-access-media-and-onboarding.md
  - ../architecture/control-plane-contracts.md
---

# Action-permission review and incremental fixes

## What this document represents

This is a living permission audit and implementation tracker. It records findings,
completed fixes, remaining reviews and their validation evidence. It is not simply
a pending-task list, and it is not a claim that the entire application has been
security-certified.

Read the disposition column for current status. The baseline column describes what
was observed before fixes; it does not describe today's behavior for completed rows.
AP-01 through AP-06 have bounded fixes/reviews described below;
AP-07 through AP-09 preserve existing protections and further review obligations.
The broader media/onboarding/scope backlog lives in the linked delivery register.

## Boundary and coverage

This work concerns which actions a member can perform, not which licenses they
can see. Organization-wide access remains. Optional license/branch scope is last
and requires a fresh owner review and explicit approval before implementation.

The first pass inspected Loans web adapters, selected lifecycle/media/report
services, WorkspaceAccess, and Party, Rates and Notify v2 view decorators/access
mappings. It is a source review, not a complete security certification. Full
service/job/command coverage and role preset decisions remain open. Stable findings
below prevent the first small correction from being mistaken for completion.

## Findings and disposition

| ID | Surface / observed baseline | Disposition |
| --- | --- | --- |
| AP-01 | Draft split, cancel/reopen and photo append had only Loans data.view access at HTTP entry | Implemented: edit required; split additionally requires create; matching detail-page controls gated |
| AP-02 | Repayment, full/partial release, accrual and capitalization HTTP entries use data.view | Implemented: four explicit servicing permissions at HTTP and public command boundaries, with matching controls; unsupported partial release remains closed |
| AP-03 | Loan notice create/retry use data.view; Notify's direct send path maps send to data.edit | Implemented customer-notice slice: create/manual retry require data.edit in HTTP/services; Notify send control aligned. Operational/job review remains AP-05 |
| AP-04 | Loan report export and Party statement export use data.view | Implemented report/statement exports: report.export required; screens remain viewable. Other document/artifact paths remain in broader review |
| AP-05 | Several domain functions accept actor for attribution without independently requiring the action | Reviewed by service/job family below; lifecycle/document entrypoint fixes implemented. Draft/photo command fixes are now implemented; funding and setup command fixes are implemented; operational alert and Party command gaps are also fixed; effective-role semantics remain tracked |
| AP-06 | WorkspaceAccess unions role-name defaults and Role.permissions | Implemented: local stored grants, forced RLS, Owner editor, capability-based delegation and invitation fingerprint checks; fixed template identities retained |
| AP-07 | Loan approval/disbursal HTTP actions are explicit; renewal checks both inside its adapter; owner combined workflow also checks ownership/actions | Preserve; add to complete action matrix rather than inferring unrestricted service authorization |
| AP-08 | Storage/physical verification are owner-only; reversal/auction/funding/setup adapters generally require settings administration | Review granularity and service checks separately; do not broaden these privileges during cleanup |
| AP-09 | Party write paths use create/edit; Rates paths use create/edit/delete; Notify send/edit differs from view | Positive baseline at inspected HTTP entries; cross-app exports, API/class views, jobs and indirect paths still need complete coverage |

## First implementation slice (AP-01)

Uses existing permissions with no new role presets, database schema, or scope filters:

| Action | Required HTTP permissions |
| --- | --- |
| Create a draft | data.view + data.create (existing) |
| Correct a draft | data.view + data.edit (existing) |
| Split a draft into a new loan | data.view + data.edit + data.create |
| Cancel a draft or return an approved loan to draft | data.view + data.edit; lifecycle rules still determine eligibility |
| Append collateral photograph | data.view + data.edit |
| Delete a draft photograph | data.view + data.edit (existing); service and database guards preserve evidence |

The loan detail page uses the same edit/create checks for correction, cancellation,
return-to-draft, splitting and photo upload controls. Owner/Admin/Member action
bundles are unchanged. A user with edit but no create can append a photograph but
cannot create a new loan by splitting. Viewer access to loan detail remains intact.

Tests cover forged GET/POST denial for a Viewer, no resulting loan/photo/audit
changes, a positive editor-only photo upload, denial of editor-only splitting,
and the existing media/draft UI regression suite. Validation result is recorded
in STATUS.md. AP-02 is addressed separately below. Neither slice makes every Loans
route read-only for viewers or completes service authorization work in AP-05.

## Second implementation slice (AP-02)

Every operation below requires data.view plus the listed action, at both HTTP and
public service entrypoints. Access is reconstructed from the loan's Workspace and
explicit actor before idempotent replay or writes. Missing actors and removed
members cannot execute commands. Existing RLS and lifecycle guards remain in force.

| Operation | Action |
| --- | --- |
| Record repayment | loan.repay |
| Settle and fully release collateral | loan.release |
| Finalize an interest period | loan.accrue |
| Capitalize eligible interest | loan.capitalize |
| Release and renew | loan.release + loan.approve + loan.disburse |

Owner and Admin defaults retain these operations. Member, Viewer and custom roles
need explicit grants; generic data.view/data.edit does not grant servicing powers.
Django permission codenames use underscores, e.g. loan_repay. Migration orgs.0007
creates assignable permission records. At the earlier AP-02 checkpoint, role-name defaults still combined with
stored grants; AP-06 later removed that runtime union. Previously, removing a stored grant did not remove a
built-in default. New operator/cashier presets have not been introduced.

Full release includes its required settlement and catch-up interest as one atomic
operation; it does not need separate repayment or accrual grants. Renewal includes
its internal catch-up calculation, approval and disbursal. Capitalization still
requires an eligible compound policy and finalized boundary accrual; permission
alone cannot bypass those rules. Unsupported partial release remains unavailable.

Loan detail and dashboard links use effective action permissions. Capitalization
has its own control independent of accrual permission. Tests cover denied HTTP and
direct commands, absent actors, removed membership, independent delegated grants,
revocation before replay, unchanged financial records on denial and existing lending
regressions. The final validation result is recorded in STATUS.md.

## Third implementation slice (AP-03/AP-04)

| Operation | Required permissions |
| --- | --- |
| Create a customer loan notice or manually retry one | data.view + data.edit |
| Send a Notify digital batch | Existing data.edit rule retained; button now matches it |
| Export loan reports or borrower loan statements as CSV/XLSX/PDF | data.view + report.export |
| Read loan reports or borrower loan statements on screen | data.view |

Existing Owner/Admin/Member defaults contain data.edit and report.export; Viewer
has neither. Custom roles can receive either grant independently. Generic data.export
is not substituted for report.export: these are financial report exports, while
Party's separate contact-data export keeps its existing policy. No new permission
records, role defaults or migrations are required.

Customer-notice creation rechecks the actor before request-key replay. Manual retry
has an actor-authorized service wrapper. The internal dispatcher remains usable by
on-commit delivery and the scheduler for an already-created immutable notice/job;
it is not a user entrypoint and must not be wired directly to a new public route.
Auction and approved risk communication composition pass their actor through the
same notice creation check. There is no implicit actor=None bypass.

This slice does not redefine operational owner-alert permissions, revoke previously
queued notices when a creator loses membership, or change low-level Notify delivery
services. Those service/job policies remain in AP-05. Official loan documents,
license-register PDFs and Notify artifacts need their own viewing/printing/export
review; this report-export fix does not claim to close every download path.

Tests cover read-only screen access, denial of every report/statement export format,
independent export/edit grants, authorized retry delegation without provider sends,
actor denial before replay and unchanged notice/job counts. STATUS.md records the
completed test run.

## Fourth implementation slice: service/job and document boundary review (AP-05)

Review scope: Loans service families and management commands, their web callers,
Notify delivery/webhook and artifact routes. The table distinguishes an authorization
check from Workspace/RLS scoping: a service can be tenant-safe and still lack an
actor permission check. This is a source/call-site review, not exhaustive adversarial
coverage of every Party/Rates/Notify service or operator deployment.

| ID | Entry boundary | Finding / current disposition |
| --- | --- | --- |
| AP-05a | approve_pawn_loan, disburse_pawn_loan, reopen_pawn_loan, cancel_pawn_loan | Fixed: explicit approve/disburse/edit checks inside commands, before transition or disbursal replay; view grant also required |
| AP-05b | issue_configurable_document | Fixed: Workspace must match loan, actor must have data.view before cached issue lookup or rendering; fixed/legacy recovery additionally requires workspace.settings.manage |
| AP-05c | repayment, full release, interest, renewal, customer notice commands | Covered by prior slices; renewal/notice composition retains required actor grants |
| AP-05d | create/update draft, split, setup transfer, append photograph | Fixed: create requires create; update/setup transfer/photo changes require edit; split requires both, all with view. Initial photos and renewal use authorized internal composition |
| AP-05e | funding_loans commands | Fixed: all 14 public commands require workspace.settings.manage before allocation, state checks, replay or persistence; saved activation and servicing helpers pass actor explicitly |
| AP-05f | product/economic/license/series/layout/print-profile configuration | Fixed: configuration writes require workspace.settings.manage in the active workspace; operator product bootstrap uses an explicit internal seed function |
| AP-05g | storage and physical verification | Inspected services enforce Owner authority; internal custody removal during authorized release/auction is composition, not a new owner-only requirement |
| AP-05h | reversal and auction | Inspected command services already require administration; preserve immutable correction and lifecycle checks |
| AP-05i | operational owner alerts and manual retry | Fixed: license-expiry creation and manual retry require setup administration; verification-discrepancy creation requires Owner authority. Scheduled dispatch remains internal |
| AP-05j | low-level event_recording, document issue persistence and renderers | Internal primitives; inspected event-recording production callers are command services, not web adapters. Do not expose them directly as actor-authorized commands. Layout mutation methods remain AP-05f |
| AP-05k | Notify dispatch_job / dispatch_batch_jobs | Internal delivery primitives; web batch-send has data.edit. Review future callers rather than introducing an actor=None bypass in public commands |
| AP-05l | Party merge and portal-access lifecycle services | Fixed: merge requires either existing Party edit alias and matching Workspace; portal lifecycle requires setup administration, checks supplied Workspace agreement, and locks/reloads before transition |
| AP-05m | Rates | Inspected writes stay in create/edit/delete-authorized views; cross-app facade supplies reads. No standalone Rates worker/service mutation path found in this pass |

### Jobs and operator commands

- `dispatch_pawn_loan_notices` processes existing queued intent/job records in an
  active Workspace context. It now requires `--workspace-id`, checks ACTIVE at
  entry, opens/clears its own context and bounds `--limit` to 1–1000. It is an
  operator command, not a public member action. Product bootstrap likewise requires
  an explicit active Workspace; read-only document integrity can inspect inactive
  Workspaces for recovery. See [operator commands](loans-operator-commands.md).
  A user's manual retry must call the actor-authorized wrapper. Revoking membership
  does not currently cancel an already-queued business notice; changing that policy
  requires a separate decision, not silently disabling scheduled delivery.
- `reassess_pawn_loans` requires an explicit Workspace id, establishes context and
  refreshes derived risk projections in bounded batches. It does not approve,
  disburse or collect money. Command execution permissions belong to deployment;
  this source review does not verify who has shell access in production.
- Product/Party-role seed commands are bootstrap/operator entrypoints. Readiness and
  document-integrity commands inspect configuration/evidence. They must run under
  the documented restricted runtime role and correct Workspace context; migrations
  alone use owner settings.
- WhatsApp callbacks use Workspace-specific credentials, HMAC verification and
  configured provider phone identity. They are provider-authenticated delivery
  updates, not staff commands; requiring member login would break callbacks.

### Document access policy and reviewed routes

| Document surface | Current policy / outcome |
| --- | --- |
| Individual loan ticket, repayment receipt, release/renewal memo, KFS and auction PDF | data.view remains sufficient; source lookup is Workspace scoped. These project existing loan evidence, not new loan authority |
| Configurable official document generation/reprint | Same view policy, now checked inside its application service; recovery overrides require administration |
| Collateral label preview/print/reprint | Existing view-authorized route retained, with matching direct service check; it appends label evidence. Do not describe Viewer as producing zero audit rows |
| Document issue archive, setup previews, funding PDFs and license register | Existing setup administration boundary retained; not widened to ordinary report viewers |
| Loan reports and borrower statement export | report.export, as implemented in AP-04 |
| Individual Notify artifact | Existing data.view retained; authorized application FileResponse route |
| Notify batch artifact ZIP | Fixed: data.view + data.export before batch/file lookup; button follows the export grant |

Opening some official PDFs persists a frozen rendition or access/label evidence.
Read access therefore does not mean zero writes; it does not grant permission to
change principal, approve, disburse or release collateral. This slice preserves
existing issuance/reprint behavior and does not introduce a new document-role preset.

Application download authorization does not secure a file served directly by the
web server or storage bucket. Private-media deployment review (MED-01/MED-02) remains
required for borrower photos, document artifacts and other storage URLs. No license
scope filters or assignments were added.

## Fifth implementation slice: draft and collateral commands (AP-05d)

| Public command | Required actions, including data.view |
| --- | --- |
| create_pawn_draft / create_pawn_draft_with_photos | data.create |
| update_pawn_draft / update_pawn_draft_with_photos | data.edit |
| split_pawn_draft | data.edit + data.create |
| transfer_expired_draft_setup | data.edit; matching HTTP check and detail control |
| append_collateral_photo / delete_draft_collateral_photo | data.edit |
| inherit_collateral_photos | data.edit for source and successor Workspace |
| render_collateral_label | data.view; preview/print evidence behavior retained |

Authorization happens before number allocation or persistence. Existing active
Workspace validation and forced RLS remain; missing actors or removed membership
cannot execute public commands. Splitting does not derive create authority from
edit permission, or vice versa. Setup transfer still requires unavailable license
setup and all existing transition/number rules.

Initial photographs belong to authorized draft creation: a create-only user can
create a draft with photos, but cannot later append/delete photographs or edit it.
Draft save-with-photos still rolls back the loan, allocated number and written files
when a later photo fails. Internal `_create_pawn_draft`, `_append_collateral_photo`
and `_inherit_collateral_photos` are used only by authorized command composition;
they are not exported from the service facade or exposed by routes.

Renewal retains release+approve+disburse authority, including successor creation and
inherited/additional photos. It does not gain a new data.create/data.edit requirement.
No boolean bypass switch or actor=None authorization exception was introduced.
Tests cover create-only photos, edit-only changes, single-grant split denial,
missing/removed actors, unchanged numbers and photo counts, lifecycle regression,
file rollback and renewal under its exact existing grants.

## Sixth implementation slice: funding command authorization (AP-05e)

All 14 public commands in funding_loans.py now enforce the existing funding HTTP
permission, workspace.settings.manage: create/cancel/save draft, direct/saved
activation, interest accrual, fee assessment, repayment, financial reversal,
settlement, collateral return, pledge/return reversal and closure.

The creation path checks authorization before allocating a funding number. Other
commands pass actor explicitly to the common Workspace/loan-loading boundary, which
checks administration before state validation, replay, event loading and writes.
An omitted actor, removed member or revoked custom grant cannot retrieve a successful
replay or execute a new command. Existing expected/active Workspace checks and RLS
remain in place.

This deliberately matches loans_setup_required rather than adding data.view or
pawn-loan repayment/release grants. Owner/Admin defaults already contain the action;
a custom role with workspace_settings alone can execute the funding lifecycle.
Member/Viewer and ordinary pawn-loan servicing authority do not imply funding
administration. AP-06 later replaced the runtime role-default union with stored local grants.

Saved-draft activation passes its actor into activation; event/custody persistence
and outbound adapters remain internal composition. No new permissions, role presets,
background actor bypasses, schema, accounting integration or license scope were added.

Tests exercise every command with Member/Viewer, omitted and removed actors,
unchanged loan/number/event/pledge/custody evidence on denial, activation/repayment
replay after grant revocation, and a complete delegated-administrator lifecycle.
Existing rollback, collateral-LTV, exact reversal and double-pledge concurrency
checks remain part of the regression gate.

## Setup service administration implemented (AP-05f)

The following public configuration commands now require workspace.settings.manage
and matching active Workspace context, preserving the existing setup HTTP policy:

| Family | Commands covered |
| --- | --- |
| License and series | Create/update/renew/activate/expire license; create/update/toggle series; configured-series composition and number-sequence configuration |
| Economics | Complete configuration, economic policy, metal interest and fee policy creation |
| Products | User-triggered default seeding, draft version creation, activation and retirement |
| Documents | Layout/profile creation, revision cloning/editing/publishing/retirement/assignment; layout asset upload |
| Monitoring and communication | Monitoring policy creation and communication policy update |

Checks precede mutation, file writes and successful idempotent replay. Omitted or
removed actors cannot use public commands. A delegated role with workspace_settings
can administer setup without an additional data.view grant, matching current HTTP
access. Owner/Admin defaults and existing domain validation remain unchanged.

The product seed management command invokes explicit internal
_seed_default_loan_products; web-triggered seeding uses the authorized public wrapper.
Trusted test/bootstrap composition can use the internal function. This is not a
public actor=None bypass. Read-only resolvers and document persistence primitives
retain their existing internal contracts.

Regression coverage includes denied setup writes, license/series mutations,
layout/profile mutations and file writes, revoked seed/activation replay, delegated
settings-only access and operator bootstrap. Existing setup, document, lending and
number-allocation suites remain the regression gate.

## Operational alerts and Party services implemented (AP-05i/AP-05l)

| Command | Service policy |
| --- | --- |
| create_license_expiry_notice | workspace.settings.manage before eligibility checks, job creation or replay |
| create_verification_discrepancy_notice | Existing Owner action (workspace.transfer), matching physical-verification HTTP policy |
| retry_operational_notice | workspace.settings.manage; HTTP retry now calls this actor-authorized wrapper |
| merge_parties | contact.edit OR data.edit, matching Party HTTP semantics; source/target must share the active Workspace |
| activate/suspend/revoke_portal_access | workspace.settings.manage; active Workspace and explicit/request Workspace must agree with the grant |

Operational recipients remain the Workspace Owner. Admins can retry an existing
verification notice under the existing retry route policy; creating its intent
remains Owner-only. The internal dispatcher and due-notice worker process existing
queued intent without a browser actor, consistent with customer-notice delivery.
Membership removal blocks new commands/retries but does not cancel queued notices.

Portal lifecycle services had no production external callers in this review. They
now use the existing Party administration action; a borrower portal grant itself
never supplies staff authority. Transitions lock/reload the persisted grant and
keep audit plus state changes in one transaction, preventing stale-instance
reactivation after revocation. No portal-management UI or new role grants were added.
Merge continues archiving the source and preserving existing conflict checks.

Reviewed cross-app call sites: Notify batch send remains edit-authorized before
its internal dispatcher; provider callbacks keep their separate authenticated
boundary. Rates/RateSource writes stay behind create/edit/delete route checks;
the loan Rates facade supplies reads. Party role seeding remains operator bootstrap.
Risk alert synchronization remains derived projection work; borrower-risk notice
creation delegates to the already-authorized customer notice service. These are
bounded source findings, not a claim that arbitrary future callers are authorized.

## Stored Workspace roles implemented (AP-06)

After the owner confirmed development-only data, the implementation was simplified
to local grant profiles with existing template identities. See the
[accepted role ADR](../adr/2026-09-09-workspace-owned-roles-and-stored-grants.md)
and [delivery record](../plans/workspace-role-migration.md).

| Concern | Current implementation |
| --- | --- |
| Shared global grants | Role is bootstrap/template metadata only. Each WorkspaceRole has its own grant rows; runtime never unions defaults. |
| Revocation | Removing Admin/Member/Viewer grants denies subsequent action checks in that Workspace. Alias alternatives and combined workflow prerequisites still apply. |
| Owner editor | Team > Manage role permissions; Owner/platform-only, audited, revision-checked; fixed role names; Owner permissions protected. |
| Isolation | Direct non-null Workspace ownership, forced RLS and registry coverage on both tables; SQL rejects mismatched grant scopes and role identity changes. |
| Delegation | Non-owner invite targets require capability subset and no protected administrative actions, regardless of name. Owner-only role-change rules remain. |
| Invitations | Stored fingerprint and current inviter authority rechecked at acceptance under locks. Used invitations do not recreate removed membership. |
| Cleanup | Retired Girvi/DEA/accounting codes removed; contact aliases retained for Party. |
| Initialization | Default grants materialized once. Re-seeding does not overwrite local edits. Template admin is read-only. |

Membership and invitation template references keep global control-plane resolution
working without unscoped local-role joins; grant reads enter explicit Workspace
context after membership resolution. Current data and membership records remain.
The local development migration is not evidence of a production rollout. Custom
role-name creation is not part of this fixed-template permission editor.

The previous global-union finding remains historical context for AP-06. The earlier
production-style staged proposal is superseded by the accepted development design;
there is no pending requirement to implement that larger migration framework.

## Next bounded slices

Private media application fixes (MED-01/MED-02) are verified; see
[the inventory and external deployment gate](private-media-access.md). Business onboarding is also implemented; see [the flow](../flows/business-setup.md). Reversal, auction,
setup, storage and low-level event composition are not claimed complete by AP-02.
Private-media review and business onboarding remain separate tracked concerns.
Optional license scope remains last and requires fresh owner approval.

## Source references

- [Loans access helpers](../../apps/tenant_apps/loans/access.py)
- [Draft/photo actions](../../apps/tenant_apps/loans/web/pawn_draft_actions.py)
- [Financial actions](../../apps/tenant_apps/loans/web/pawn_financial_actions.py)
- [Release actions](../../apps/tenant_apps/loans/web/pawn_release_actions.py)
- [Notice actions](../../apps/tenant_apps/loans/web/pawn_notice_actions.py)
- [Report/export actions](../../apps/tenant_apps/loans/web/reports.py)
- [Workspace access](../../apps/orgs/access.py)
- [Notify access mapping](../../apps/tenant_apps/notify_v2/access.py)

## Billing recovery follow-through (2026-09-09)

Invoice reconciliation requires matching Workspace context and canonical current
owner/Membership (or existing platform override), before provider I/O and again
under the Company lock before application. The CLI requires explicit Workspace,
actor, invoice, payment and reason and defaults to check-only. Signed refund events
use verified provider GET evidence and the same locked refund recorder. The new
PaymentRefund table is global billing-control-plane evidence reached only through
a scoped Invoice/Payment; no business-app RLS boundary is replaced. See
[recovery flow and limitations](../flows/subscription-checkout.md#recover-a-known-payment-or-refund).

Final billing decisions also require current canonical ownership and matching
Workspace context under the Company lock. The submitted subscription revision must
match before a new decision. Ending refunded access is limited to the latest
started current term; newer/future terms cannot be cancelled. Stale-payment returns
require verified full refund coverage and never activate a contract. BillingResolution
is immutable global control-plane evidence. See [review actions](../flows/subscription-checkout.md#resolve-a-billing-review).
