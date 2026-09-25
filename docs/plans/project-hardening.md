---
status: active
owner: project
updated: 2026-09-25
tags: [plans, saas, hardening]
related: [../architecture/2026-09-09-project-review.md, future-work.md]
---

# Incremental project hardening

The owner approved proceeding with the recommendations. Deliver bounded checkpoints
in the order below; the [review](../architecture/2026-09-09-project-review.md) holds
the evidence and acceptance criteria. This plan does not reactivate FW-001 license
scoping or authorize production deployment.

| Increment | Findings | Status |
| --- | --- | --- |
| Reproducible foundation | R01/R02 and R06 runtime-role gate | Implemented; validation recorded in STATUS |
| Operational commands | R05 | Implemented; validation recorded in STATUS |
| Paid billing correctness | R03/R04 | Checkout binding, replay, invoice and webhook repair implemented; expiry implemented; known-payment/refund recovery implemented; owner review decisions implemented; provider acceptance shelved as FW-002 |
| Current docs/product/residue cleanup | R08/R09/R10, verified R13 | R08/R09/R10/R13 complete; bounded removal evidence linked below |
| Routing, dashboard and module organization | R07/R11/R12 | R07 and R11 complete locally; Loans views portion of R12 complete; orgs workspace/role settings extracted; team/invitations extracted; orgs views complete including account/preferences and slug adapters; broader model/form/renewal review separate |
| Production operations acceptance | Remaining R06 | Final import and approved lending/staff setup complete; real retained operations at the temporary hostname; operator review, independent recovery and later live-domain switch remain |

Foundation implementation and operator commands are documented in
[Containers and CI](../implementation/container-and-ci.md) and
[Loans operator commands](../implementation/loans-operator-commands.md). Existing migrations,
action grants, protected files and historical compatibility routes remain intact.

## Current delivery priority

The current application release is `713e0b64` at `rehearsal.rokkad.com`, serving
the retained production database. Recent completed work includes paper closure
entry, corrected disbursal attempts, Tabs/Classic loan details, same-day policy
revisions, collateral quantities/authorized interest overrides, camera selection
and Indian monetary display. See [Status](../STATUS.md) for exact migration,
image, validation and backup evidence.

Remaining priorities are the owner/staff operational review, conditional second
Lakshmi account verification, original licence-document upload, backup retention
and separately approved off-server recovery, bounded receipt/Hindi review, and
the later explicitly approved live-domain switch. Preserve all new transactions;
do not rebuild this database from the old snapshot. Provider acceptance remains
deferred and checkout disabled.

### Completed cutover and lending checkpoints

The evidence below records each rollout at its date, not current sequence values.

The JSK unnamed-series defect is corrected in deployed release `c55932cd`:
blank prefixes are supported and preserved, and an audited forward-only correction
continued at **06703** at correction time, with WH then unchanged at WH02145. Focused tests, clone
allocation, deployed form previews and preservation checks pass. Review every
active series during future cutover acceptance; never reimport the operational
database to repair configuration. See
[correction evidence](../STATUS.md#jsk-unnamed-series-continuation-corrected-2026-09-25).

Release `660571b9` also provides read-only reconstructed ticket previews for imported
opening loans and prefix-based new-loan picker labels. The final deployed pages/PDFs
pass checks in all three branches. See
[preview evidence](../STATUS.md#imported-loan-ticket-preview-and-familiar-series-labels-2026-09-25).

Release `55a6e0eb` adds the approved printable imported copy with a small provenance
footer while retaining the marked preview. All three branches and nine active-series
samples pass; no financial or numbering changes occur. See
[copy evidence](../STATUS.md#printable-imported-loan-copies-2026-09-25).

Release `a5a38bb9` corrects native ticket approval-evidence loss when photo fields
are present. All 73 focused tests and actual C07548 issue/reprint checks pass.
Shared display changes must include rich-photo native issuance UI coverage. See
[fix evidence](../STATUS.md#native-ticket-photo-evidence-regression-2026-09-25).

Release `e5822c02` adds licence proprietor capture and bold precision text.
JCL's reviewed layout emphasizes the business name/principal and uses the source
proprietor for each licence. Saved official issues retain original bytes. See
[header evidence](../STATUS.md#jcl-ticket-header-and-amount-emphasis-2026-09-25).

The [dependency refresh](../implementation/dependency-refresh-20260924.md) clears the
earlier candidate's known Python advisories, fixes upgraded Select2 borrower search,
passes 1,911 regressions and fresh/restored runtime checks, and is deployed to rehearsal.
The [operational acceptance pass](../implementation/rehearsal-acceptance-20260924.md)
now proves latest-backup restoration, three-branch payment/release/reversal flows
and staff permission checks on a disposable restored copy. The approved Google
configuration/subject is now installed in the clean production target, and local
OAuth initiation plus runtime/RLS checks pass. Source `9ab5e4bd` configures explicit
single-Caddy client-IP trust. The complete September 24 package is imported and
reconciled, all preserved media attached, and local backup recovery verified.
Release `d078db38` adds owner-attested licence continuation with original documents
pending. The owner-approved JSK policies and September 25 metal references are
applied to all three branches after clone approval/printing/disbursal checks.
That setup operation preserved imported customer/financial rows and counters. A fresh backup
restored with all 161 tables matching. The owner subsequently authorized real
retained business use at `rehearsal.rokkad.com` for one or two days before changing
the live domain, and reconfirmed the source freeze. Production now serves that
temporary hostname with verified HTTPS and hourly server-only backups; old practice
web is stopped. The owner-approved Google OAuth addition is saved and actual login
verified Owner access to all three production Workspaces. Next: the owner's
one-to-two-day operational review and independent recovery. Approved staff access
and Shankar's Lakshmi ownership are applied; individual staff first sign-ins and
the second Lakshmi account's conditional Google verification remain.
Live-domain DNS remains unchanged and its later switch still needs approval.
Preserve all new transactions across that switch. The owner requires the old site's
configuration/services to stay unchanged. Recent Hindi labels and receipt/memo visual
acceptance remain bounded review items.

## Completed review increments and deferred provider work

The owner shelved Razorpay setup/provider testing as
[FW-002](future-work.md#fw-002-razorpay-setup-and-provider-test-mode-acceptance).
No Razorpay setup is needed for the remaining review cleanup. Earlier increments:

1. R08 completed: current index, dependency/testing policy and context rewritten;
   original context retained in linked archives. Current-entry link check runs in CI.
2. R09/R10 completed: current tour choices preserve historical answers; removed six
   definition-only settings and replaced the DEA guard with tracked-source AST checks.
3. R13 completed: four unused direct packages and 14 unreachable templates removed;
   [reachability and retention evidence](../implementation/dependency-template-cleanup.md).
4. R11 visibility, batching and [query measurements](../implementation/dashboard-reliability.md) complete.
   R07 is complete: all 136 canonical Loans routes use direct Workspace adapters;
   all URL generation is scoped and response rewriting is removed. Old mapped-domain
   routes and named aliases remain compatible. The Loans views portion of R12 is
   complete: all handlers live in focused web modules, with public imports retained.
   See [module map](../implementation/loans-view-organization.md). Broader R12
   orgs workspace/role settings and access helpers are now extracted. Team and
   invitations are also extracted; orgs view organization is now complete, including account/preferences and slug adapters; see the [orgs module map](../implementation/orgs-view-organization.md).
   The remaining-module review below selects the next bounded increment.

## Remaining R12 module review

Reviewed after publishing orgs checkpoint `38eb1e3`; no application code changed
during this review. File size is supporting context, not a reason by itself to split.

| Candidate | Evidence and recommendation |
| --- | --- |
| Loans forms | `forms.py` mixes document layout/overlay/print-profile editing, license setup, funding, pawn intake, custody and lifecycle inputs. Its first 13 classes form a coherent document-editing group (lines 36–414), with an internal print-profile inheritance relationship. Extract this group first into a focused web form module, retaining public imports from `loans.forms`. |
| Core models | `models/core.py` mixes numbering/economic policies, loan/collateral records, immutable evidence, releases, auctions and renewals. The existing model package already separates other features. Defer moving these classes until a concrete change benefits from it; preserve Django model identity, relationships, constraints, default-callable paths and public imports, with no generated schema migration for organization alone. |
| Renewal service | `services/pawn_renewals.py` contains previews, atomic execution/reversal, fingerprints and shared validation. Execution and reversal depend on row locking, replay handling, custody evidence and compensating events. Keep the transaction orchestration together for now; a later preview/helper extraction needs explicit dependency mapping and renewal/reversal regression coverage. |

The document form increment is implemented locally: 13 classes now live in
`web/document_forms.py`; `forms.py` retains public imports and the two document
setup handlers use the owning module. All 50 form class bodies remain unchanged.
The three license/series setup forms are also extracted into `web/license_forms.py`
with compatible public imports and unchanged class bodies. License setup handlers
use the owning module. Next: verify publication CI and review remaining form
families before choosing another extraction.
Core model and renewal-service moves remain deferred.

### Remaining form families reviewed after 16be7149

This review changes documentation only. The remaining 34 classes do not all need
separate files. Prioritize coherent workflows over file size.

| Group | Finding and priority |
| --- | --- |
| Economic setup (3 forms) | `PawnEconomicConfigurationForm`, `PawnFeePolicyForm` and `LoanMonitoringPolicyForm` are used together by `web/economic_setup.py`. Implemented locally in `web/economic_forms.py`, preserving public imports, business-default versus license policy selection, Workspace-filtered choices, monitoring instance defaults, gold/silver 2%/4% interest and INR 10 fee defaults. |
| Funding (8 forms) | Extracted locally to `web/funding_forms.py`; `web/funding.py` and `web/funding_actions.py` use the owning module and public imports remain compatible. Preserved eligible-collateral selection, active pledge exclusion, confirmation words, request keys and return choices. This is existing lender-funding functionality, not permission to restore retired accounting. |
| Storage/physical verification (5 forms) | Extracted locally into `web/custody_forms.py`; custody views/actions use the owning module with compatible public imports. Preserved Workspace and location-level filtering and existing resolution inputs. |
| Product setup (1 form) | A small standalone model form. No priority to create a file solely for this class. |
| Pawn intake and lifecycle | Keep together for now. Intake has local number-preview imports and bound/edit/single-option behavior; draft and renewal handlers share collateral formsets. Reversal/reason forms serve several action families. A future move must map these shared dependencies and preserve formset identity and constructor behavior. |

Economic extraction completed with unchanged class bodies and compatible public
aliases: 69 economic-default, setup UI, economic-policy, pawn-economics and scoped
route tests passed. Economic forms are published as `7c043eb0`. The eight funding forms
are published in `fdb5e97f` with unchanged class bodies and compatible public
imports. The five storage/physical-verification forms are also published in `fdb5e97f`;
all 31 class bodies and three formset definitions from the preceding checkpoint
remain unchanged. Next: verify publication CI for the validated form changes.
Keep persistence, calculations and action authorization in
their existing services. No new permission scope or financial rule is authorized
by this organization work.

Each form increment must preserve fields, validation, widgets, constructor
arguments and public class identities. Inspect callers and mock targets, compare
class bodies, then run existing document-layout/print-profile and affected web
tests plus import checks. Do not introduce a generic form framework or change
document behavior as part of the move. Remaining form families can follow only
where they offer similarly coherent boundaries.



[Checkout flow and limitations](../flows/subscription-checkout.md) and
[decision](../adr/2026-09-09-workspace-checkout-evidence.md) describe completed billing
implementation. FW-002 remains an acceptance requirement before real paid onboarding,
not a blocker to this cleanup. Truly orphan/legacy contracts remain support cases;
no guessed contract restoration. No production deployment is authorized.
