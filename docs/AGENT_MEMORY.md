---
status: active
owner: project
updated: 2026-09-24
tags: [agents, context, architecture]
---

# Agent Memory

Stable project understanding only. Delivery evidence belongs in [Status](STATUS.md),
selected work in [the hardening plan](plans/project-hardening.md), and shelved ideas
in [Future work](plans/future-work.md). Prior notes, including superseded decisions,
are preserved in [the historical snapshot](archive/context/2026-09-09/AGENT_MEMORY.md).

## Product and tenant foundation

Commercial expiry now uses the separate `workspace_activity` policy: seven days
of normal-access grace from natural trial/paid-term expiry, then reviewed read-only
routes and exports. Platform administrators can append dated full/read-only access
decisions or return to normal policy; the latest decision wins and older grants
never revive. This does not rewrite purchased terms, invent payments, or bypass
membership, role permissions, suspension, archive or RLS. New checkout is disabled
by default until provider acceptance. Servicing-only access is deferred: repayments
and releases are still writes. See the
[access decision](adr/2026-09-24-subscription-access-continuity.md),
[operator guide](domain/subscriptions.md), and Status for release evidence.

Customer Workspace creation now prepares four standard DRAFT loan products in the
same transaction, through both control-plane creation services and explicit RLS
context. Owners/setup administrators review and enable only their chosen versions;
automatic preparation never activates products or changes terms on existing loans.
The manual seed button is removed. The explicit idempotent operator command remains
for existing Workspace rollout/recovery; direct import/operator Company creation
does not imply customer onboarding. See the [decision](adr/2026-09-24-automatic-draft-loan-products.md)
and Status for validation/deployment evidence.

The owner explicitly requested preserving guided customer-facing legacy migration
as future work. [FW-007](plans/future-work.md#fw-007-guided-customer-facing-legacy-migration)
tracks the gap between existing staged imports/operator-prepared loan migrations
and a supported end-to-end customer journey. It is unscheduled future work, not
authorization to implement it now or a claim that arbitrary-source import exists.
The owner clarified two onboarding cases: new lending in a new series with old
paper loans left outside, and new lending alongside gradual manual/Excel migration
of existing paper loans. FW-007 records both, including existing-borrower matching,
separate historical admission and explicit financial handover/coverage boundaries.

The owner requested borrower-specific loan discovery and more informative reports.
Loans now support a dedicated borrower name/code/phone filter and exact scoped Party
filter, including inactive borrowers. Customer/loan pages and statement search link
to that borrower's full loan list. Reports add active totals by licence and series,
collateral by metal/custody, and maturity bands, with charts and full exports.
The subsequent Loans by year report groups all operational loan states by original
loan-date calendar year, with current state counts and canonical active principal.
Creation/import timestamps and archive-only historical records are not its basis.
Grouped money must use canonical balances; current active membership is distinct
from the balance date. Collateral values here are recorded approved appraisals,
not current market/coverage values. Keep missing appraisal/gross-weight counts
visible; never promote unverified migration valuations. Maturity bands are not
contractual instalment DPD. See Status for deployment and verification evidence.

The subsequent staff workflow review deployed `rokkad:rehearsal-staff-ui-20260924`:
dashboard search/queues precede analytics, payment receipts have a visible section
with reversed evidence labelled, and customer mutation controls follow canonical
edit permission. Reader/editor/collector hosted probes passed with temporary access
rolled back; 55 targeted tests passed. No financial transactions were submitted on
rehearsal. The reports increment subsequently deployed
`rokkad:rehearsal-report-pages-v3-20260924`: selected reports paginate 50 source
records before fetching evidence, and borrower statements are searchable. Preserve
as-of dates, source links and complete Workspace summaries/downloads; pagination
must never truncate exports. Integrity pages cover only their displayed loan batch.
Migration-opening events are valid origins alongside disbursal and renewal; invalid
balance evidence must still raise findings. Twenty targeted tests and hosted/browser
checks passed. HTTP success is not staff usability acceptance. See Status and the
readiness review for scope and evidence.

On September 24 the owner accepted the preferences/navigation review and
subsequent dependency cleanup. Rehearsal image
`rokkad:rehearsal-prefs-retired-20260924` removes dynamic-preferences and unused
persisting-theory, replaces package model bases with plain Django raw-data
models, and retires registries/services/forms. Compatibility migration 0003 adopts
old global/user tables or creates them on fresh installs; preserve their values,
audit history and user deletion relationship. No current lending workflow uses
these retained values. Fresh-install and populated-clone migrations passed, with
five preference/audit tables and 87 loan/party tables unchanged on upgrade.
Legacy preference bookmarks remain authorized read-only guidance; POST rejected.
Reports, Historical loans and Release batches are visible outside Settings.
Loan details group secondary evidence into disclosures and show the loan date
and separately labelled creation/import timestamp beneath the heading. New loan
number previews follow the selected series without allocating a number. Technical
checks and browser checks passed; broader staff usability acceptance remains open.
Backup and detailed evidence stay on the server, never in the OneDrive checkout.
See [the decision](adr/2026-09-24-retire-preference-editing-surfaces.md),
[feature map](flows/workspace-feature-map.md) and [Status](STATUS.md).

On September 23 the owner confirmed that imported loans must support both
interest-only payments and partial principal repayments before cutover. The owner confirmed that
principal reductions change interest from the next original monthly anniversary
for all three branches; retain the current period's already-earned interest.
The dedicated repayment path now implements this with `opening-payments/1`
evidence, atomic collection catch-up, ordinary fees/interest/principal allocation,
and highest-rate-item principal reductions. The inclusive original calendar still
charges the day after each anniversary. Reversal compensates payment and catch-up
together; debt-free loans remain active until explicit collateral return/release.
General event posting, periodic accrual, renewal and auction remain guarded.
Payment histories use `loan-opening-export/2`, with frozen item-allocation rows
and financial-service replay on restore; histories without payments retain v1.
See the [payment decision](adr/2026-09-23-opening-partial-payments.md). Current opening
servicing requires dates strictly after the opening date; plan an overnight
boundary unless that contract is deliberately extended. See the
[cutover runbook](implementation/linode-production-cutover.md).

The owner subsequently reported completing the imported-loan practice run with
everything working well. Treat that workflow as accepted, not as a pending repeat
approval. Practice transactions are not production data. The next cutover task is
binding media admission to the exact production database, storage and source.
That command contract is now implemented with `linode-media-target/1` and a
checksummed `linode-media-plan/2` production header; rehearsal retains its original
format. A changed destination/source requires replanning. See the
[target-binding decision](adr/2026-09-23-production-media-target-binding.md).
The separate Linode is now created for hosted cutover rehearsal. Release
`a9f793fc` is built there; PostgreSQL 16.15 hosts the newly migrated
`rokkad_cutover_rehearsal` database, with separate owner/runtime credentials in
private host files and restricted-role/RLS checks passed. HTTPS now serves
`rehearsal.rokkad.com`; the app uses the existing `prod_r2` settings through a
read-only host rehearsal wrapper, secure isolated cookies, rehearsal banner and
in-memory email. The owner explicitly approved temporary R2 credential transfer
for this rehearsal only. Its separate prefix is
`media/application/production/hosted-rehearsal-20260923`; do not reuse it for final
production. The delegated administrator is `rehearsal-admin` with an unverified
placeholder email; its generated password stays in the host's private
`~/deploy/rehearsal/admin-login.json`. Login/storage probes and local schema-stage
backup/restore passed. Hosted business data is now admitted and fully reconciled
under the restricted runtime role and ordinary `hosted-import-owner` memberships.
All three Workspaces have Admin Memberships for `rehearsal-admin`. The owner supplied
`backup_20260923_115257.sql`; its exact snapshot is inspected and privately staged
on the host. New source review and owner-answer evidence are separate from the
September 21 package. For this snapshot, JCL RA00554 and C07517 remain outstanding
despite inactive source customers; do not extend the earlier 190 owner-confirmed
closures to them. JCL RA00549 and JSK WH02133 are unused/cancelled, with no invented
closure or operational loan. Lakshmi D01234 is a duplicate-entry correction:
use original principal 11,500 and one item from its original date, not a repayment.
The September 23 classification is 6,368 outstanding, 39,162 closed-history and
three unused/cancelled records. All 8,634 customers and their prepared contacts and
addresses are imported. Populated-data RLS, 19 rolled-back servicing samples,
29 real HTTPS pages and a separate backup restoration passed; all 160 restored
table content hashes matched. Database admission/reconciliation took 99.2 minutes,
excluding offline preparation and media. See Status for checksums/evidence.
Hosted media now has 28,347 references attached using 29,489 private application
copies. After the owner authorized the incremental source check/copy, all 55
remaining newer references were found on the old Linode, preserved directly in
private R2 and attached to rehearsal (JCL 27, JSK 9, Lakshmi 19). Fifteen private
access probes, an identical 55-receipt retry and 252 unchanged business-data
fingerprints passed. Of attached references, 25,054 are known blank source images,
including 53 of the 55 newly copied files. Older missing files and unverified
shared candidates remain excluded. Only the 55 paths received a fresh source
check; do not call this a fresh complete media capture. Payments/releases require
dates after the September 23 opening.

The subsequent authorized exception review rechecked all 3,614 remaining exact
branch paths read-only; all are still missing. They affect 102 active collateral,
3,507 historical and five customer-photo references. Of 1,149 unverified shared
candidates, 1,144 are known blank images; the other five are unverified customer
photos. Leave candidates unattached without ownership evidence. Detailed exception
reports stay on the rehearsal server in `media-exceptions-20260923/`.
The owner wants printing obvious immediately after approval. Approved/active
loan details now show a prominent Print loan ticket action below the heading,
using the existing eligibility flag and ordinary PDF route. Other states retain
their existing document section. The template-only rehearsal image is now
`rokkad:rehearsal-ticket-button-20260923`; include this template in final release.

Full identical retries of both media plans recognized all 28,292 receipts and
created nothing. Completed reports and the post-media database backup are retained
on the rehearsal host. This is verified reuse of preserved media, not final
production cutover or a fresh live-filesystem capture.
Durable production credentials, operational off-server recovery policy, media
completion and the final frozen-snapshot cutover remain pending. Do not promote
practice data or change live routing based on this rehearsal.

Keep the post-media rehearsal backup on the server: the owner explicitly chose
this after automatic review rejected a full database export into the OneDrive
workspace. Detailed media/reference reports also stay on the host after that
export was rejected. Local docs may record aggregate verification results; do
not retry those sensitive exports without explicit new authorization.

For hosted JCL new-lending practice the owner chose a separate synthetic TEST
licence instead of making the final-cutover attestation while production remains
live. Hosted licence 5 and series 13 use `TEST-JCL-L-`/`TEST-JCL-R-` numbering;
flexible product version 6 is active. Sample licence-scoped policies use 2%
monthly gold/silver interest, 80% appraisal LTV and one month upfront. This is
practice configuration, not confirmed production terms or legal licence evidence.
Imported licences/counters remain unchanged. No verification bypass was added.

Accepted layout bundles are now imported on the hosted rehearsal: JCL layout
revision 3/profile 2 published only on TEST series 13; JSK layout revision
4/profile 3 are unassigned drafts. Hashes match the saved accepted exports,
including JCL's four background assets. The pre-existing JCL `test` draft remains
unchanged. Synthetic previews passed; actual practice-loan printing and physical
printer alignment are separate checks. Never copy these destination IDs into
production assignments.

Hosted JCL TEST series now uses layout revision 5/version 2, superseding revision
3 only for that series: amount-in-words uses SHRINK and automatic leading in its
unchanged frame after the 18,600 practice loan exposed overflow. Full-text preview
passed; earlier published evidence is preserved. Re-export this correction before
future deployment; the original September 23 bundle predates it.

The owner prefers ₹ instead of INR on tickets. `INR_SYMBOL` is an opt-in layout
value format with an embedded Unicode font; monetary payloads remain unchanged.
Hosted JCL TEST uses revision 6/version 3 (including the amount-in-words fix);
JSK draft revision 4 also formats principal with ₹. The rehearsal web image is
`rokkad:rehearsal-rupee-20260923`, a derived image with this display change.
Issued PDFs retain their original bytes. Refresh exported bundles before future
rollout; do not redeploy the older image with the newer layout format.

The owner wants absent borrower photos to leave blank space on tickets rather
than block issuance. Use the existing optional-photo setting; do not fabricate
identity photos or suppress unreadable-selected-media failures. Hosted JCL TEST
now uses revision 7/version 4 and JSK draft revision 4 has this setting on all
borrower-photo frames. Actual JCL loan 19105 passed official-mode rendering with
recorded ABSENT/optional evidence. Collateral-photo rules were not changed.

The owner explicitly requires these corrected JCL/JSK templates to work out of
the box at production cutover. Latest private transfer bundle is
`outputs/server-rehearsal-20260923/cutover-templates-final-20260923/`; earlier
exports are superseded. Use `scripts/install_cutover_ticket_templates.py` with
an explicitly bound destination JSON and restricted runtime role. It pairs each
branch's layout and paper profile as Workspace defaults, validates every series
and rejects conflicting overrides. On rehearsal JCL 7/2 and JSK 4/3 are both
published defaults; JSK is no longer an unassigned draft. Default-profile previews
pass for both branches. Retry and wrong-target rejection checks passed. Include
INR_SYMBOL support in the production release. Do not transfer TEST data or copy
rehearsal identity bindings. Final production installation remains a cutover step.

The owner authorized a design-first ticket-template experiment on
`feature/ticket-template-designer`, isolated in its own worktree from baseline
`8b0e1ba3` on `rls-mvp`. Follow [the bounded plan](plans/ticket-template-designer.md).
Use template/frame authoring concepts over the existing Loans document pipeline;
do not add a parallel legacy renderer or Girvi dependencies. JCL plain-paper and
JSK preprinted A5 are acceptance examples of one client-configurable editor.
Preserve historical issues and tenant isolation. Runtime work requires a separate
database/media location; Git isolation alone does not protect rehearsal data.
Owner acceptance precedes merge. The feature now implements opt-in v4 ticket
overlays: optional backgrounds, value-only/custom-label fields, 0.1 mm geometry,
text padding and explicit line spacing. Profile v2 distinguishes plain paper from
preprinted stock: backgrounds are guides only for the latter, visible exclusively
in labelled design previews. Official output and print previews omit them.
V4 first issues use payload v2: authorized Party contact facts and selected private
photos are captured in immutable `LoanDocumentIssue.source_snapshot`; approval
economics and approved collateral/photo evidence remain authoritative. A loan
row lock serializes first prints. Reprints use saved artifacts before rebuilding
facts or fetching media. Old issue snapshots remain null; dynamic images and
customer values never enter layout packs. Migrations 0016/0017 are now applied
to local `rokkad_shared_dev` and `rokkad_baseline_rehearsal_linode_20260921`, after
verified backups; pre-existing Loans/Party rows were preserved. Literal mapped JCL/JSK frame candidates
remain non-activatable pending reviewed static-stock declarations and artwork review.
V4 visible business coverage is now separate from internal audit fields: identifiers,
fingerprints and verification text are optional on paper, while the full payload
and issue evidence remain required. Owners/Admins use Issued documents > Evidence;
the loan print panel links to its ticket history. Evidence shows retained capture
values and media hashes; verified artifact reads reject missing/mismatching bytes.
Reviewed static-stock declarations are still needed for literal JCL/JSK candidates.
The owner wants a timestamp on paper: new v4 starters and JCL/JSK candidates print
`document.generated_at` as a small Generated footer on both copies. Capture the
instant once with the issue's source snapshot, display the app timezone and UTC
offset, and preserve that timestamp on exact-artifact reprints.
Existing creation defaults and v1/v2/v3 contracts remain unchanged. The isolated
test launcher pins a local test database and worktree-local filesystem media;
it does not start a feature web server. See the plan for the command and limits.
The separately provisioned browser sandbox now uses port 8082, database
`rokkad_ticket_template_sandbox`, a dedicated restricted login, separate cookies
and worktree-local media. Its workspace `jcl-template-sandbox-sample-only` has
synthetic data only; it is not the existing JCL migration rehearsal. The reviewed
JCL configuration is saved there as draft revision 1 with all four backgrounds.
Keep credentials and local assets under ignored `outputs/ticket-template-sandbox/`.
Use the sandbox settings/launcher for further isolated experiments. The merged
editor is also available in the accepted rehearsal after the rollout below.
The owner accepted JCL's reviewed sandbox workflow. JSK now has a separate
synthetic workspace `jsk-template-sandbox-sample-only`, draft revision 2 and
PREPRINTED A5 Original/Duplicate profile 4, using the same sandbox login. The
owner requested `Jai Sri Krishna` from licence business details and confirmed
both signature areas already exist on each stock copy. Loan rate/tenure remain
approved loan facts. JSK has no guide artwork; added heading/term positions and
collision corrections have accepted digital previews; physical alignment remains
unverified, with its merge gate explicitly waived by the owner.
On September 23 the owner clarified that JSK's business name, address and contact
are already preprinted too. Omit those frames from JSK output, preserving stored
licence details and the licence-number frame. The editor now offers an explicit
v4 `business_name_preprinted` confirmation for both copies; it requires a
PREPRINTED profile, defaults false without changing old canonical hashes, and
does not waive internal source evidence or other required fields. Rehearsal JSK
uses layout revision id 4 (version 2) with existing profile 2 on TEST series 14.
Published revision 2 and issued TEST ticket 3 remain unchanged; use revision 4's
marked preview to inspect the corrected design. The calibration builder matches
the correction. No change to JCL's printed business heading.
For excessive collateral text the owner's final choice is wrapping plus smaller
font within the existing frame, NOT additional ticket sheets. Both sandbox
drafts use SHRINK with automatic leading for collateral descriptions; JSK's
summary label does too. Preserve complete text and the existing 6 pt floor.
The owner also requests no monthly interest rate on JSK paper, matching JCL.
JSK's draft and calibration builder omit those frames and explicitly set
`require_interest_rate=False`; approved rates remain required internal evidence.
The owner has accepted both JCL and the final JSK digital previews. This is not
physical-printer acceptance or permission to activate production templates.
The paired Use this template action is implemented: review a local paper profile
and Workspace/Series scope, then atomically publish/assign both using existing
services. Preserve override precedence, reject stale draft hashes and check all
effective pairs. Failed activation rolls back publication/assignment/audit; repeat
submissions are idempotent and paired activations serialize on the Workspace.
On September 22 the owner explicitly accepted the print previews, waived physical
printing as a merge prerequisite, and authorized merging into `rls-mvp`. Do not
reintroduce that approval gate. Record physical alignment as untested, not passed.
The fast-forward merge completed at `e2fae88d`; the original checkout is on
`rls-mvp`, with the isolated feature worktree and pre-feature checkpoint retained.
Existing issued PDFs and source snapshots remain unchanged. On September 23 the
owner authorized local rollout: migrations are applied to development/rehearsal;
accepted JCL/JSK templates and profiles were installed in
`rehearsal-jcl-20260921` (layout/profile 1/1) and `rehearsal-jsk-20260921` (2/2).
They are now published and assigned through Use this template only to the TEST
series (JCL 13, JSK 14). Workspace defaults and imported-series resolution remain
unchanged. This is rehearsal activation, not production activation.
JCL's four R2 assets and the two existing issued PDFs are checksum-verified.
The imported JCL draft allows long identifiers/business headers to shrink within
unchanged frames; the accepted sandbox source stays intact. The owner confirmed
JCL's business details: `J Champalal`, No. 58, Main Road, Lathif Sahib Street,
RN Palayam, Vellore 632001; contact 7598260045. These are now saved through an
audited amendment on the synthetic JCL practice licence only. Both preview headers
fit. The owner corrected the initially supplied No. 56 to No. 58, matching the
Original background's door number; no door-number artwork correction is needed.
JSK's confirmed details are `Jai Sri Krishna`, No. 155, Azad Road, Thorapadi,
Vellore 632001; contact 9489481436. Retain these for licence setup; they have not
been applied to JSK's unverified imported licence. Real imported licence printed
name/address fields remain blank. Imported
licences are unverified legacy references, so do not bypass verification to amend
them or enable lending. JSK now has
owner-authorized practice licence 6 (`TEST-JSK`), series 14 and approved sample
loan 18859 (`TEST-JSK-L-00001`), created through ordinary services. The licence
has the confirmed business details; customer, photos, collateral, appraisal and
validity are explicitly synthetic. No disbursal was made. The normal printing
route has issued JSK TEST ticket 3 with payload-v2 source evidence, layout/profile
2/2 and SERIES scope; repeated printing returns identical bytes. JCL's existing
ticket is issue 2 (source PawnLoan 18858); issue 1 is the KFS schedule. Both old
artifacts remain unchanged, including the ordinary JCL ticket reprint after
activation. To see JCL's new layout use its marked preview or a new eligible
practice loan; existing issued tickets intentionally retain their saved PDFs.
Practice calculation/rate policies are licence-scoped; the ordinary default
product catalog was seeded, with its flexible version activated. Existing import
records/counters are unchanged. JSK's published weight frames wrap/shrink with
automatic leading in the same geometry, preserving full stored precision and
the 6 pt floor. Both A5 rehearsal preview pages pass. Port 8081 runs the merged
`rls-mvp` code. Keep these TEST records out of production migration.
The owner wants a larger licence-sourced business name and address above JCL's
borrower row. `LoanLicense.business_name/business_address` are distinct from its
internal staff label; ordinary amendments and renewals retain them in immutable
licence revisions. V4 fields `license.business_name/business_address` capture
the current licence's display details at first issue, preserving exact reprints.
Never infer these values from workspace names, customer addresses or background
artwork. Blank bound values explain themselves in previews and block new issues.
JCL's heading has the business name alone on the first line, an editable literal
`Pawn Brokers` on the second, followed by the licence address/contact block.
Keep those separate frames; do not automatically strip words from stored names.
The owner requested replacing JCL's fixed three-month artwork text with approved
`loan.tenure`, and deferring printed interest for now. The original-front proof
uses a separately cleaned background; source artwork and issued PDFs stay intact.
Do not add an interest frame to this preview without revisiting that preference.
The owner subsequently approved per-copy signature choices: movable frames,
confirmed background areas, or confirmed preprinted-paper areas. V4 declarations
bind the selected background key/hash; changed artwork requires reconfirmation
before publication/rendering. Profile stock mode must match the declaration.
The v4 `require_interest_rate` flag defaults true; explicit false now permits the
owner-requested omission on JCL while the full approved payload retains the rate.
Old schemas, canonical hashes and stored reprints remain unchanged. See the
[signature choice ADR](adr/2026-09-22-ticket-signature-area-choices.md).
The [frame mapping contract](implementation/ticket-template-frame-mapping.md)
captures all 35 selected JCL/JSK frames and the chosen additive schema/evidence
changes. Preserve explicit differences in quantity, legacy live value and license
name; do not claim visual parity from coordinate conversion. Use existing approved
photo evidence and snapshot Party display data only at first document issue.

Owner/team forms use ordinary explicit POST actions and the existing audited
control-plane services. Invitation and role choices come from role policy; role
names are stored identities, not translated permission promises. Workspace-local
grants remain authoritative. Working alone does not require inviting staff.

Rates and Notify list searches share the `reference-results` native partial/HTMX
contract with normal GET fallbacks, strict fragment headers and no-store responses.
Rates corrections/withdrawals remain service-backed history. Notification review
must distinguish dispatch, printed/posted handling and provider delivery evidence;
connection readiness is not proof of receipt. See the accessible directory delivery
notes for browser and test coverage rather than treating it as operator acceptance.

Rokkad is operational pawn-lending SaaS. Supported business apps are Party, Loans,
Rates and Notify v2. General-ledger accounting/DEA, Girvi, Contact, Product and legacy
Notify are retired. Do not restore their imports or product promises. Preserve
intentional legacy redirects, 410 responses, migrations and Party `contact.*`
permission aliases until separately reviewed.

Workspace (`orgs.Company`) is the SaaS tenant; licenses and series live inside it.
PostgreSQL shared-schema forced RLS isolates directly Workspace-owned business rows.
`workspace_context()` owns transaction-local RLS context. Request identity comes
from an explicit Workspace URL/domain; `request.workspace` is authoritative.
Profile Workspace is navigation preference only. Domain/path disagreement fails
closed for everyone. Do not require Clear Workspace to manage teams or accounts.

Membership is the ordinary user/Workspace relationship. `Company.owner_id` is
canonical ownership, mirrored by Owner Membership. Runtime role grants are
Workspace-local (`WorkspaceRole`/`WorkspaceRoleGrant`); global Role identities remain
templates. Defaults seed once, never overwrite local edits. Membership, action
permissions, lifecycle, billing, entitlements and RLS are separate checks. Read
[control-plane contracts](architecture/control-plane-contracts.md) before changes.

## Production migration boundary

Imported license continuation is explicit and audited (September 22 ADR). For a
matching legal license, final-source numbering review plus actual validity/document
evidence can append a VERIFICATION revision and activate the same license/series.
Old loans retain LEGACY_REFERENCE revisions and cannot be disbursed again. Ordinary
activation still rejects unverified references. Finish imports before verification;
the service records an attestation, not independent proof of source freeze. The
imported rehearsal licenses remain inactive; never fabricate real validity or
counter review. Owner-authorized manual practice uses a separate clearly synthetic
JCL test license/series added September 22, with TEST-prefixed loan/release numbers.
Its document and dates are test fixtures, never production licensing evidence.

The owner reprioritized a thorough accessibility, onboarding and daily-workflow
redesign before cutover on September 22. Staff need desktop, tablet and phone
support in English and Hindi. Follow [the UX plan](plans/project-wide-ux-revamp.md),
building on the counter shell. Keep the old app live and the accepted rehearsal
intact; defer final source freeze and switch until redesigned journeys are accepted.
The separately provisioned Linode now supports hosted rehearsal preparation.
CPU/RAM sizing recommendations remain provisional until measured.
The owner selected Django 6 native template partials with HTMX and the latest stable
Bootstrap for implementation. Use progressive ordinary Django views/forms and
existing domain services; no extra partial-template package or SPA framework.
The first native-partial directory slice pins Bootstrap 5.3.8 in the active shell.
Fragment headers never grant access; full-page/history fallbacks, private responses,
keyboard focus and English/Hindi are part of each flow's contract. See
[the frontend decision](adr/2026-09-22-native-template-partials-ui.md).
Loan directory principal is the value recorded at creation/import, not a live
balance or guaranteed original advance. Invalid search filters must not silently
broaden results. Loan servicing shortcuts follow existing state/permissions and
imported-opening limitations; financial authority remains in the commands.
Branch setup highlights the first unfinished existing selector check. It must not
equate checklist availability with evidence verification or new-lending authority.
License/series form examples never allocate or reserve numbers; failed numbering
configuration must retain input while the existing atomic service rolls back changes.
Customer writes stay ordinary CSRF-protected submissions. Native partials share
field/error rendering; failed forms retain text, link errors to controls and explain
file reselection. Account introduction progress/preferences never imply branch
lending readiness or grant permissions.
Customer create/edit camera frames become ordinary multipart photo files; preview
does not persist anything. Existing private media authorization remains authoritative.
Customer identity evidence and the customer-to-draft handoff do not imply verified
identity or lending readiness; branch preflight and domain services still decide.
Loan review distinguishes current draft estimates from frozen approved payment
amounts. The read-only approved-disbursal preview shares the command's frozen
economics parser; templates never recalculate deductions. Printing availability
follows approval/schedule evidence, and a loan ticket is not proof of payment.
Full-release quote `fees_and_interest_settlement` already includes release-day
catch-up interest; UI must identify that component as included, never add it again.
Collection forms distinguish recorded repayment dues from current full settlement,
and optional interest concessions retain the existing administration permission.

Linode production at `4312573fa2dca9f8bea3abd1ab84aadb5bd1e1cd` is a historical
ancestor of `rls-mvp`, but runs the former `django-tenants` schema-per-Company
deployment. Treat JCL, JSK and Lakshmi Pawn Brokers as a read-only source-to-RLS
conversion, never an in-place database upgrade or old-database restore. The local
portability baseline and Loans import migrations are committed in `a3e0e2b8`, but
are not a deployed migration tool. Rehearsal results are not proof that Linode data
was imported. Follow [the production migration design](architecture/production-tenants-to-rls-migration.md): inventory a fresh custom dump, build exact per-schema adapters,
reconcile with owner gates, then cut over from a final frozen snapshot.

The legacy source remains live while discovery and rehearsal proceed. A discovery
archive is never an incremental-import base: rehearse in isolation, freeze legacy
writes for cutover, take one final complete archive, then build the production RLS
destination from that snapshot. The 2026-09-21 discovery inventory and its
future-dated JCL loan hold are recorded in
[the Linode discovery report](implementation/linode-production-discovery-20260921.md).
On September 22 the owner selected a separate Linode server for the new production
deployment; it was subsequently provisioned for hosted rehearsal. Prepare it independently, keeping
the old source live until a scheduled all-writer freeze. Follow
[the cutover runbook](implementation/linode-production-cutover.md); the old system
is a simple fallback only before new-system business writes begin. The explicit
`prod_r2` settings are available but not deployed; they require a separate durable
production application prefix and runtime credentials, never the rehearsal token.
The owner confirmed production photographs/documents are stored on the same Linode
server filesystem, not in Cloudflare R2. Capture a separate filesystem media backup
with paths, checksums and source-record associations alongside the final database
snapshot. Do not infer source storage from current development settings or assume
file contents are in pg_dump. Read-only SSH inventory subsequently verified the
live root and schema folders; this is not a frozen cutover snapshot.
The owner selected Cloudflare R2 for destination media and supplied
`root@rokkad.com` with `/var/www/rokkad/media` as the source location. SSH verified
that root, the deployed historical commit and tenant-relative media settings.
Transfer directly from Linode
to private R2 storage; a download to the owner's computer is not required. Keep
Workspace-authorized application delivery and preserve source schema/record
associations. Ordinary development/production storage has not been switched to R2;
the isolated rehearsal uses explicit private R2 opt-in settings.
See [the media migration plan](plans/linode-media-to-r2.md) for pending work.
The live inventory matches 28,224 of 31,838 discovery photo references. Missing
branch-path references include 102 operational-loan photos, 3,507 closed-loan
photos and five customer photos. Older shared folders contain 1,149 exact-path
candidates, but their source-tenant association is unproven; never auto-attach
them by filename. The owner explicitly approved creation of private
`rokkad-production-media`; the bucket exists with public access disabled. The
owner also approved the bucket-only Object Read & Write migration token
`rokkad-media-migration-20260921`, expiring after one week; creation succeeded.
The owner saved the credentials and authenticated access succeeded. All 31,405
inventoried branch files and 1,149 separately labelled recovery candidates are now
preserved and read-back hash-verified in private R2, with 13 verified evidence files.
The bounded attachment implementation now uses immutable source receipts,
separate application objects, explicit legacy collateral provenance and immutable
closed-history media sidecars. Its operator command is rehearsal-only; execution
and verification are tracked in [the attachment runbook](implementation/linode-media-attachments.md).
Many source image files are uniform grey placeholders. Byte/hash verification is
not proof of a usable photograph; confirmed blank fingerprints are labelled in
the application and never establish photographic or appraisal evidence.
Also retain the distinction between 102
active-photo references whose branch files are missing and 203 active collateral
items with no recorded photo reference. Preserved originals must not become mutable
Party FileField objects: photo removal/cleanup could delete them. Use separate
application copies through authorized attachment services. See the
[preservation decision](adr/2026-09-21-legacy-media-preservation-and-application-copies.md).
The old local R2 endpoint points to another account and must not be reused. Temporary
SSH key access works and must be revoked after migration; credentials remain local.
The snapshot-bound `linode_migration` operator command captures accepted inputs,
rebinds them into clean Workspaces through existing services, and reconciles the
result. Its source comparison never approves a changed archive; fresh production
data needs new preparation. See [the replay runbook](implementation/linode-reviewed-replay.md).
Each fresh target database also needs explicit grants for the existing restricted
runtime login. `scripts/provision_runtime_role.py` keeps creation fail-closed and
requires `ROKKAD_RUNTIME_GRANT_EXISTING=1` to grant a verified restricted existing
role without changing its password or ownership.

The Linode Party preparation adapter emits chunked canonical JSONL under a strict
`legacy:<installation-uuid-without-hyphens>:<schema>` source system. The Party
staging service accepts this only for JSONL and retains it as the source identity;
it does not treat legacy documents as native Rokkad exports. Preparation remains
review-only until ordinary staged-batch approval and commit occur.

Legacy Party contact/address `party_external_id` must be the deterministic UUID
emitted as the master document's `id`: that is the external ID persisted by
canonical JSONL staging. Raw `contact_customer:<pk>` references remain provenance,
not parent lookup keys. Keep the installation namespace stable across snapshots.
Completed-batch retries are idempotent; they do not establish that re-uploading a
fresh snapshot can bypass conflict review after local or child-derived changes.
The Loans opening boundary preserves raw customer references in its frozen review
while resolving either existing raw Party bindings or the canonical deterministic
UUID from the same source namespace/schema. Conflicting bindings fail closed;
this compatibility does not change the generic Party child resolver.
The opening staging service and operator command accept an optional versioned
`source_profile`, re-extract its correction ledger, and freeze the profile in
signed source evidence. The separately confirmed `linode-owner/1` profile extends
the reviewed source interpretation to the three named Linode schemas through
registered versioned profiles; the older JCL owner profiles remain JCL-only.

On 2026-09-21 the owner answered "same rules as jcl" when asked about JSK/Lakshmi
interest, first-month payment, later collections and missing-tenure treatment.
`linode-owner-terms/1` records shared anniversary/upfront interest and the
three-month missing-tenure fallback for the exact three Linode source profiles.
Keep valid recorded tenure; hold payment-bearing cases for reconciliation. This
interest/maturity confirmation alone does not prove weight interpretation,
custody, current balances/fees or a production cutover date. The owner subsequently
answered "Yes, net weight in both" for JSK and Lakshmi. `linode-owner/1` therefore
maps stored weight to net weight with a new explicit evidence reference and shares
the confirmed terms. Gross weight remains unknown, and custody/balances still
require separate evidence. Versioned staging selects this profile; profile-less
older staging preserves its JCL-only behavior.
The owner also confirmed rehearsal branch custody for unreleased loans apart from
the report's flagged exceptions. Scope that custody attestation to unflagged
candidates; do not clear payment, inactive-borrower or source/collateral holds.
The owner subsequently answered "no fees are unpaid,proceed". The isolated
September 21 rehearsal therefore uses zero fees, unchanged principal and the
confirmed interest rule for the 6,254 unflagged, payment-free candidates. Its
September 21 opening date is a rehearsal checkpoint, not a production cutover.
At that checkpoint 210 flagged active loans remained held. Closed loans belong in
source-evidence retention, not the operational opening path. The subsequent owner
decisions below resolve this snapshot's holds without changing that boundary.

For `linode-owner/1` only, collapse runs of description line breaks/tabs to a
space; retain exact raw descriptions, row hashes and explicit before/after
transformations in signed staging evidence. Do not permit arbitrary description
edits or loosen control-character validation. Zero-interest openings need only
their principal obligation: omit empty schedule rows. Document validation rejects
all-zero obligations before database preview, matching the existing writer and
database constraint. Never revise an already accepted opening to repair a
preparation error; checkpointed admission resumes only against identical accepted
documents and source fingerprints.
The owner subsequently confirmed inactive customers have no outstanding loans,
instructed exclusion of the 14 loans' payment rows, retained ten matching addresses
as distinct, and confirmed custody/outstanding status for the remaining payment
cohort. Exactly one payment loan overlaps the 190 inactive-customer loans: **13**
payment-bearing loans remain open, despite the earlier question incorrectly saying
12. Preserve that counting correction and the verbatim answer in the decision record.
Payments remain in source evidence; they are excluded from calculations, not deleted.
The 190 owner-reported closures retain unknown release dates and create no settlement.

The owner corrected six specific JSK/Lakshmi purity values to 100%, conditional on
no supporting release record (verified absent), and identified JSK WH01223 as unused
or cancelled. New `linode-jsk/2` and `linode-lakshmi/2` profiles contain those exact
source-row corrections under ledger `/2`; `/1` profiles remain reproducible. Never
cap arbitrary purity values. WH01223 stays in retained exclusion evidence without
an operational loan or invented closure. Distinct-address decisions bind exact
canonical row, parent and matching destination addresses; source IDs/default
conflicts still block, and decisions cannot become reusable presets. Payment
exclusions bind the exact archive, loan and every raw payment row to signed review.

The current three-Workspace rehearsal has 6,273 operational openings, 39,133 closed
evidence records and one unused/cancelled exclusion: all 45,407 source IDs, no
unresolved loan holds. All 18,848 prepared Party records are admitted. See the
[owner-decision record](implementation/linode-owner-decisions-20260921.md) for proof
and private report paths. Separate rehearsal browser access is now configured at
`127.0.0.1:8081`, using opt-in `baseline_rehearsal_web` settings and an ordinary
`migration-rehearsal-owner` login. Private credentials/branch links are in
`outputs/linode-rehearsal-access-20260921/access.html`; never commit those credentials.
The account's old superuser/staff flags were removed; real owner Memberships and
local trials through October 5 supply browser access. Separate cookies, local
media/cache/email and the rehearsal banner keep this browser instance distinguishable.
The launch script binds loopback only. See the [access guide](flows/linode-rehearsal-access.md).
The owner subsequently reported "all reviewed and looks great,whats next?", accepting
the presented browser rehearsal. Do not repeat that review or treat it as acceptance
of untested servicing/new-lending workflows or authorization to freeze live writes.
Next prepare a repeatable cutover package and clean-target release rehearsal, with
media, production access/setup and required servicing checked before scheduling the
final frozen snapshot. A new Migration Center UI is not a prerequisite. This remains
separate from jcl-13 and production; a fresh frozen archive,
retained Party preparation decisions, required servicing/setup/access/media and
clean-build acceptance remain necessary. Ordinary partial repayment remains guarded.

## Business rules to preserve

For the seven-loan jcl rehearsal, the owner confirmed on 2026-09-17 that all
calculated interest after the upfront first month remains unpaid. The earlier
jcl-13 zero-unpaid-interest simulation is not a balance-matching baseline. Preserve
its immutable origins and C07432's subsequent release; use an isolated corrected
rehearsal. The owner subsequently authorized the full eligible cohort in test
Workspace 10 using this interest premise, retaining the seven samples and holding
payment-history, inactive-borrower and validation failures. This is not a live
migration. Do not generalize the premise to the held payment-history cases.

Opening export v1 owns its row names, types and nullable values in
`loans/services/opening_contract.py`, independently of model metadata. Keep the
published row definition and old synthetic archives compatible; model refactors
must adapt writers/exporters without changing v1. Financial graph reconciliation
and admission remain separate. See the
[wire-contract decision](adr/2026-09-13-frozen-opening-wire-contract.md).

Portability validation categories are reporting metadata, not admission policy.
Opening document reconciliation never certifies operational readiness; its separate
readiness checks remain NOT_EVALUATED. History errors preserve original messages
and blocking behavior while reporting malformed data, missing evidence, historical
inconsistency or operational readiness. Historical-only acceptance uses the separate
closed-evidence archive; classification alone never authorizes financial admission.
See the [classification decision](adr/2026-09-13-portability-validation-classification.md).

`loan-closed-evidence/1` retains source-reported closed loans in immutable,
Workspace-owned HistoricalLoanEvidence, with separate LoanArchiveBatch staging.
Unknown borrower/payment/collateral facts and contradictory claims can be retained
after explicit owner review without creating PawnLoan, Party or financial/custody
rows. Identical document retries reuse a snapshot; changed evidence appends another.
Browse requires data.view; export additionally data.export. Acceptance reuses the
owner import/setup gate. See the
[archive decision](adr/2026-09-13-historical-closed-loan-archive.md).

The jcl source licence field was decorative and its validity dates were not
recorded, per the owner (2026-09-12). Preserve its source label separately from
verified destination licence evidence; do not invent validity dates or repeatedly
ask for dates the old system never stored. For C00121, custody at the April 9
rehearsal is confirmed and grace is three days. The dumped valuation is old, not
an approved current appraisal; its date/current value remain unknown. The current
opening path now represents these explicitly. Inactive legacy licence references
retain null validity and cannot authorize new lending; optional opening setup
evidence selects that mapping. V2 UNVERIFIED valuation claims create no appraisal
or current LTV. Full settlement can return all opening collateral without using
unknown values; native/partial-release valuation checks remain. Export/restore
preserve these claims and any later first appraisal. See the
[unknown-evidence decision](adr/2026-09-12-legacy-opening-unknown-evidence.md).

For the jcl migration, the owner's latest instruction (2026-09-12) is to preserve
recorded maturity terms and use three calendar months from the original loan date
when maturity is missing. This supersedes the proposed no-fixed-date implementation.
C00121 therefore uses 2025-01-10 from its 2024-10-10 loan date. Retain the owner's
migration instruction separately from source facts; do not claim a newly supplied
date was historically recorded. Source tenure zero uses the explicit scoped owner
evidence reference; positive recorded tenure is preserved, invalid values held.
The chosen maturity participates in overdue reporting while interest keeps its
original billing anchor. See the [first-import plan](plans/first-legacy-import.md).

Loans opening v2 has an owner-authorized per-loan preview/commit command. It freezes
reviewed source/setup evidence and uses HistoricalLoanImport for shared identity
with complete history. Legacy identities include source schema; older raw-key
complete bindings remain recognized without edits. Preview rolls back all business
rows; exact-input retry never resets subsequent servicing. This is a domain
building block, not proof of source claims or production approval. Source adapter/
selection approval, missing due terms and an actual reconciled pilot remain activation gates.
See the [opening commit decision](adr/2026-09-12-authorized-opening-commit.md).
The jcl one-loan adapter now re-extracts the dump, verifies the selected source
facts and stages immutable evidence for owner browser approval. LoanHistoryBatch
has separate immutable complete-history/opening profiles; source_sha256 identifies
the inner Loans commit document and signed approval covers the complete source
wrapper plus preview. No real source activation follows automatically. The operator
prepares technical review inputs; users do not author JSON. See the
[staging decision](adr/2026-09-12-legacy-opening-staging.md).
Opening downloads use `loan-opening-export/1`, retaining the reviewed origin,
available source verification and supported servicing with earlier history declared
unavailable. A dedicated owner/operator restore now rebuilds the supported graph
through dated Loans calculations and reconciles it before commit. Public live
commands retain current-date behavior; no production clock patch or live-number
allocation is used for restore. New exports advertise restore support; old files
with the same format remain readable. Original actor/time/reference claims stay in
immutable `references.restore`; destination actors and IDs are newly bound.
An identical restore retry never resets later servicing; a different restore or an
existing ordinary opening conflicts under the shared financial-origin identity.
Complete-history upload stays separate. See the
[restore decision](adr/2026-09-12-opening-restore-reconciliation.md).

Loans owns lifecycle services and immutable disbursal, repayment, release, renewal,
auction, custody and document evidence. Correct completed work through explicit
compensating/reversal actions. Rates supplies reference values; Loans freezes used
values. Party owns borrower identity. Notify delivery never determines loan state.
See [the constitution](constitution.md) and [dependency policy](implementation/dependency-policy.md).

Authorization precedes mutation and idempotent replay. Public actor-less business
commands are denied; internal bootstrap/delivery helpers are not staff APIs.
Servicing requires explicit repay/release/accrue/capitalize grants; renewal composes
release+approve+disburse. Setup/funding administration uses workspace settings
permission. Export/document permissions are recorded in the
[action-permission review](implementation/action-permission-review.md).

`Company.loan_workflow` defaults to EXTENDED. Owners can choose SIMPLE for atomic
review/approval and disbursal while retaining both evidence records. Adding staff
never changes this mode. Use plain labels: Dashboard, New loan, Loans. "Counter"
is historical workflow shorthand, not mandatory product language. See
[workflow choice](flows/loan-workflow-choice.md) and [business setup](flows/business-setup.md).

Setup is resumable and stays accessible after completion. Select a sole usable
series/product only on unbound new forms; preserve submitted/explicit values and
fixed edit choices. Gold 2% monthly, silver 4% monthly and INR 10 document charge
are editable setup form defaults, not automatic persisted policies.

Multiple-loan release groups at most 20 current-date full releases atomically.
One payer funds settlement; each loan records its own verified collector. Signed
quotes expire after ten minutes. Reversals and original loan evidence remain
canonical. See [multiple-loan release](flows/multiple-loan-release.md).

Official document issues retain exact bytes and immutable published layout/assets.
Reprints retain the original issue; fixed-renderer recovery is explicitly authorized
and audited. See [layout/print guide](flows/loans-document-layout-operator-guide.md).
Physical phone/camera and printer acceptance remains deferred.

## Private media and cache

Party/KYC and collateral media use authorized Workspace routes; templates/widgets
must not expose business storage URLs. Reviewed private responses disable caching.
Draft-only photo deletion preserves shared renewal file lineage. Development raw
media permits only company logos and personal profile pictures; deployment bucket,
proxy/CDN privacy still needs acceptance. See [private media](implementation/private-media-access.md).

Rates has no request cache middleware or cache-writing signal. Loans reads its
Workspace facade from PostgreSQL. Redis is optional via CACHE_URL; local memory is
the default display cache. Borrower autocomplete uses signed tokens and rebuilds its
authorized queryset, without cache-stored widgets. See [cache configuration](implementation/cache-configuration.md).

## Billing and operations

Billing is global control-plane data linked to Workspace subscriptions; browser
billing actions require canonical owner/Membership or the existing platform override.
Frozen checkout/order/amount/currency evidence precedes verified captured-payment
activation. Paid access ends at end_date through the shared effective policy; reads
do not rewrite stored status. Old payment replay cannot restore expired access.

Refunds and final review decisions are immutable. Full refunds await owner decisions;
ending access is restricted to the latest current started term. Known stale payments
can be closed after verified full return without granting old terms. No refund
issuance or guessed orphan-contract restoration. See [billing flow](flows/subscription-checkout.md).

Web/workers use restricted DB credentials. Migrate only with
`python manage.py migrate --settings django_project.settings.migration`.
Tests use `--settings django_project.settings.test`; adversarial RLS DML must run
under a restricted role. New Workspace-owned tables require direct non-null
ownership, forced RLS, registry coverage and isolation tests. Container/CI runtime
startup checks role/RLS and pending migrations; it never migrates. See
[container/CI guide](implementation/container-and-ci.md) and
[testing guide](implementation/testing-and-migrations.md).

Loans operator seed/integrity/notice commands require `--workspace-id` and own their
context. Seeding/dispatch require ACTIVE; read-only integrity supports recovery.
See [operator commands](implementation/loans-operator-commands.md).

## Owner constraints and current direction

The owner requested a deep Loans/portability audit with documentation only and
explicit review before implementation. The [audit](architecture/loans-portability-audit.md)
distinguishes current operational invariants, source historical assertions and
portable contracts. It recommends separate historical acceptance and operational
admission, preserving existing Loans states/financial/RLS guards. Its target and
follow-up plan are proposals, not accepted implementation decisions. The audit
flagged the generic financial model importer as an integrity/action-authorization
exposure. The owner subsequently authorized slice 0A (2026-09-13): all Loans
models are denied by the generic import form, request handler and resource factory;
generic import requires current data.view/data.import/workspace.settings.manage
grants, matching Workspace context and ACTIVE lifecycle. Export behavior remains
separate. See the [containment decision](adr/2026-09-13-generic-loans-import-containment.md).
Historical acceptance and later admission architecture remain proposed.

The earlier dump was for testing. The owner supplied the current dump on
2026-09-12 at `C:\Users\rajes\backup_20260912_224652.sql` (custom PostgreSQL format,
SHA-256 `e33f78f3fb96e8c23a029f9b933492e02e2a2af7b27e0cf20686b178fe91a27f`).
Use the same installation namespace and jcl source identities across snapshots.
The new source has 2,463 unreleased loans and records C00121 released on 2025-01-21;
do not overwrite the earlier active pilot or invent a settlement. Five unfinished
old-source Party batches were cancelled with their artifacts preserved. Old balance
assumptions, candidate lists and number floors are superseded by the new comparison,
not by inferred financial approval. The owner authorized a fresh isolated rehearsal:
Workspace 10, `test-jcl-current-20260912`, created through the normal Workspace
creation service. This is not a selected live destination or approved cutover.
Its active-cohort preparation now has 1,093 source-linked Parties, 755 contacts,
1,104 addresses and 2,463 unapproved loan proposals, with no financial loans.
Two conflicting source default-address flags were retained in provenance while
leaving the destination default unset. See the private preparation report and Status.
The owner explicitly kept all 11 payment-bearing unreleased loans on hold until
checked. Their full-principal payments marked with release do not establish a
missing release's date or custody. Do not ask about the old 2024
freshness gap again. See the [first-import plan](plans/first-legacy-import.md).

The owner authorised the complete jcl preview, then active-batch preparation in
test Workspace 9. Preparation now includes saved legacy licence/series setup,
forward-only historical number reservations, five Party review batches and 2,446
loan proposals. Financial cohort commit remains unapproved. The ordinary Party
importer flags duplicate names even for distinct source IDs (769 old staged rows).
The new batch-specific reviewed-name command preserves source records and borrower
links without renaming or merging. It binds canonical source values, exact existing
name-match IDs and a reason to the ordinary preview/commit digest; stronger identity
conflicts remain blocked. It is not proof of distinct physical people and is not a
reusable preset. See the [decision](adr/2026-09-12-reviewed-party-name-collisions.md).
The owner also wants familiar series numbering to continue for new lending.
Reserved counters include all source loans, even released/held/skipped records;
imports preserve their own readable numbers without consuming new ones. C now
has prefix C/width 5/next 123. Legacy-reference series still cannot originate loans;
verified licence/active product and coordinated successor ranges are separate
pending setup. Do not claim numbering reservation activates lending or reassign
historical licence evidence. See the [first-import plan](plans/first-legacy-import.md).

The preview retains the incomplete-collateral exclusion rule without inventing an
age cutoff. Missing optional related-person names can be left unset in conversion
proposals while retaining raw labels; unfamiliar relationship meanings remain
held. Source IDs, original readable numbers and the existing C00121 binding must
survive future cohort processing. Cohort confirmations must not be inferred from
the single-pilot balance/custody answer.

The owner accepted C00121 as recognisable and approved the proposed monitoring
thresholds for the isolated test Workspace only (2026-09-12). Do not ask again.
Current-rate valuation at import is the owner's proposed next improvement; retain
historical source values separately and distinguish metal estimates from reviewed
appraisals. The confirmed test gold buying and selling quote is INR 15,500/g for 24K/100%.
The current appraisal service supports explicitly labelled RATE_BASED reviews
with a checked quote ID, price freshness and exact weight/purity calculation.
C00121 now has that current appraisal without rewriting its imported evidence.
See [rate-based appraisal](adr/2026-09-12-rate-based-collateral-appraisal.md).

The owner clarified that the legacy dump is a one-time migration source, not a
reason to turn portability into a separate loan product. Finish the recognisable,
operational C00121 pilot before bulk conversion or additional portability features.
Readable destination numbers can be explicitly proposed in opening setup; source
identity remains separate. Opening pages must offer supported collection commands
and explain missing evidence without suggesting unsupported native servicing.
See [pilot readiness](adr/2026-09-12-opening-pilot-operational-readiness.md).


The owner requested a first-class customer data portability architecture, with
analysis/planning first and no automatic later-phase implementation. The
[proposal](architecture/data-portability.md), [contract draft](contracts/rokkad-data-v1.md)
and [plan](plans/data-portability.md) distinguish exchange schema from persistence,
historical Loans evidence from today's operations, and partial exports from full
archives. The owner subsequently authorized the Party master slice: bounded
CSV/JSONL staging, mapping, preview, atomic create/no-op commit and partial canonical
export now live in data_portability. Five directly scoped models retain identities,
source aliases and immutable completed-row provenance; JSON issues remain on rows.
Shared Party creation keeps current forms/number allocation. Missing context and
actor permissions fail closed. See the [operator guide](flows/party-master-portability.md).
Generic data-tools remain unchanged under the owner's narrowed instruction and
must not be reused as the new pipeline; their security/allowlist review remains open.
The owner then authorized contact methods and addresses: separate child profiles
reuse staging/preview/commit/export, require exact parent source references and
Party edit permission, and retain child aliases plus deletion tombstones. Native
primary/default rules and summary synchronization remain in Party services.
Source verification claims remain provenance and do not set local verification.
The owner subsequently authorized identifiers without documents: party-identifier/1
reuses child staging/identity with native per-type uniqueness, masked values and
expiry dates. Source verification/timestamps stay provenance; metadata-bearing
identifier export fails explicitly. No local verification or Party tax-summary
updates are inferred. Party roles were subsequently authorized: party-role/1 requires
explicit source-key to active destination-type mapping for CSV/JSONL, binds the
selected definition to preview approval, and preserves native role uniqueness and
history. It does not create Party role definitions or staff permissions.
Party relationships were subsequently authorized: party-relationship/1 resolves
both explicit master references, binds and locks both endpoints, and preserves
native directional uniqueness/self-link rules. Typed identities retain both Party
identities and deletion tombstones; moved endpoints fail replay/export.
Reusable CSV mapping presets were subsequently authorized: immutable Workspace
versions copy exact mapping/default/rule configuration into matching profile/source/
header batches, then generate a fresh preview. Saving changed configurations appends
versions; earlier versions and batch approvals remain independent. Source identity,
role-type validation and commit authorization remain unchanged. Preset defaults are
private configuration, potentially containing customer data; no cross-Workspace
preset transfer or deletion is implemented. See the [preset decision](adr/2026-09-12-csv-mapping-presets.md).
Bounded XLSX input was subsequently authorized and now reuses the same pipeline
for all six Party profiles. It accepts one visible plain-values worksheet, validates
ZIP/XML limits and actual cell coordinates, and rejects formulas, external links,
hidden data and ambiguous Excel formats. Dates/precision-sensitive identifiers use
text. CSV/XLSX share source identity and matching preset semantics; canonical JSONL
schemas stay unchanged. See the [XLSX decision](adr/2026-09-12-bounded-xlsx-input.md).
The bounded six-profile `party-bundle/1` ZIP export is implemented with a manifest,
checksums and frozen schemas from one lock-stabilized snapshot. Company and bounded
Party/type/child row locks protect consistency; busy sources fail with a retry
message. This remains PARTIAL, excluding Loans and complete Workspace archives.
See the [bundle decision](adr/2026-09-12-party-export-bundle.md). ZIP validation and
atomic staging into ordinary per-profile previews are now implemented, with strict
member/schema/hash/count/reference checks and no automatic business writes. A
Workspace-bound signed receipt lists previews; master must be committed before
child revalidation and explicit role-type mapping. See the
[staging decision](adr/2026-09-12-party-bundle-staging.md). Combined dependency-aware
review and atomic commit are now implemented: existing commands run in a rolled-back
savepoint for preview, then confirmation repeats and compares the approved plan.
Only database effects/on_commit callbacks are safe in this simulated command path;
no external inline side effects may be added. Signed operator/Workspace approval
expires in one hour; immutable completed summaries retain the aggregate hash for
permission-checked replay. See the [atomic decision](adr/2026-09-12-atomic-party-bundle-commit.md).
Persistent bundle history is now implemented in ImportBundle: immutable direct
Workspace ownership and six typed nullable batch references, forced RLS and SQL
membership guards. Migration 0010 recovers older groups only from verified staging
audit evidence. Stable saved pages generate fresh membership-checked receipts;
one-hour approval expiry and operator/Workspace binding remain unchanged. Progress
is derived from batch states. See the [history decision](adr/2026-09-12-persistent-party-bundle-history.md).
Saved bundle cancellation now requires explicit confirmation and current import
access, locks the Workspace and member batches, and atomically cancels only current
READY/NEEDS_MAPPING members. Completed evidence and immutable history remain;
cancelled staged raw/canonical values and issues are cleared, while mappings and
source/audit metadata remain. No-op replay still requires access. See the
[cancellation decision](adr/2026-09-12-party-bundle-cancellation.md).
The optional history progress filter is shelved as
[FW-006](plans/future-work.md#fw-006-party-bundle-history-progress-filter).
The owner authorized the bounded Loans contract review, now recorded in the
[contract](contracts/loan-history-mvp.md) and [decision](adr/2026-09-12-loans-complete-history-mvp.md).
Selected scope is flexible partial-payment complete history with ACTIVE or full-release
CLOSED outcomes. Current-date commands cannot serve as historical replay APIs.
The missing evidence guards found during review are addressed by Loans migration
0008 across fifteen append-only tables. UPDATE/DELETE (including actor clearing)
are denied; INSERT verifies owned references and direct/parent-derived loan scope.
Mutable loan/collateral state is unchanged. See the
[guard decision](adr/2026-09-12-loans-history-evidence-guards.md).
Historical setup preparation is now available from Loans setup and Party imports.
It is an owner-authorized read-only check of original licence/date, compatible
product terms and deterministic historical number candidates. No mapping is saved,
no number is reserved and no financial import occurs. See the
[preparation flow](flows/loans-import-preparation.md). Canonical JSONL now supplies the complete-history
staging/reconciliation, explicit atomic command and export path. See the
[wire contract](contracts/loan-history-jsonl.md), [operator flow](flows/loans-history-import.md)
and [decision](adr/2026-09-12-loans-canonical-history-import.md). Loans owns immutable
source provenance and historical financial/custody writes; portability owns batches
and signed confirmation. Both new tables have direct Workspace ownership and forced
RLS. One complete loan per file supports simple-interest flexible active and fully
released history. Preview rolls back business rows; confirmed commit rechecks all
scoped mappings and native calculations. Current-date live commands are not replayed.
Loans direction includes both active and historical loans: lifecycle state is
separate from evidence completeness. Complete-history active loans do not require
an opening-position import; missing-history cutover semantics remain separately
undelivered. See the [Loans clarification](plans/data-portability.md#loans-scope-clarification-2026-09-12).
Party portability MVP feature scope is closed. History filtering is optional and
deferred. See the scope boundary
in [the delivery plan](plans/data-portability.md#mvp-scope-closeout-2026-09-12).
The owner clarified the actual initial source priorities: migrate the previous
schema-per-tenant Django production dump first, then simple customer/licence/series/
loan/release Excel registers. These need source adapters, not user-authored JSONL.
Complete history, active opening positions and limited-evidence released records
are distinct capabilities; the latter two are not implemented. The owner supplied
`tenants_workspace` commit `c9fb81bc70adafa1d942721d642bfb2b38953f41`; its read-only
review confirms optional release payments and differing calculation paths, while
its model state differs from the dump. Source loan `interest` is monthly money in
the inspected calculation path, whereas item `interestrate` is a percentage.
Preserve stored evidence and reconcile before choosing opening balances; do not
execute legacy save methods or recreate retired apps. A bounded offline
`preview_legacy_dump` command is now implemented in data_portability and exercised
against owner-selected `jcl`. It reads no destination database, uses pg_restore only
for listing/text extraction, requires an explicit source schema and stable source
namespace, and produces ignored local HTML/JSON/JSONL review artifacts. These are
not canonical import packages or accepted source bindings. All records remain not
import-ready; missing-evidence contracts and explicit destination mapping precede
financial writes. See [preview guide](flows/legacy-dump-preview.md),
[source review](implementation/legacy-dump-source-review.md) and
[actual source priorities](plans/data-portability.md#actual-source-priorities-2026-09-12).
No automatic
later-phase implementation is authorized. Opening-position Loans has a design
contract but no executable import; physical erasure remains undesigned at executable
contract level. No accounting restoration or retention period is authorized.

The owner selected preserving existing billing dates/agreed interest rules for
retained active loans. Do not reset periods or silently adopt the current interest
basis. The [opening contract draft](contracts/loan-opening-position-mvp.md) requires
approved cutover balances, remaining due obligations and original-period carry;
financial implementation remains pending. The owner tentatively suggested skipping
incomplete collateral. The preview's opt-in proposal preserves whole source graphs,
has no age cutoff and grants no import/deletion authority. It does not classify
missing payments, non-Gold/Silver metal mappings or missing photos as incomplete
collateral by themselves. Final source selection remains part of financial review.

`loan-opening-review/1` now provides offline Loans-owned document reconciliation,
fed by `preview_legacy_dump --prepare-openings` and rechecked by
`validate_loan_openings`. The source adapter leaves unknown balances/weights/due
terms/continuation empty. Passing document arithmetic never authenticates source
claims, resolves destination authorization or permits import; `import_ready` stays
false. See [review contract](contracts/loan-opening-review-v1.md). The internal
`loan-opening-evidence/1` envelope now freezes reconciled review and item mappings
on a `MIGRATION_OPENING` event. Balance/tranche readers support cutover amounts,
keep them separate from new lending and reject earlier historical queries.
The existing immutable, forced-RLS event table permits only one opening per loan;
readers reject mixed origins. This is a read foundation, not source authentication
or an importer. Generic financial posting and native accrual remain blocked for
opening loans; dedicated full release and its coupled reversal are now supported.
The explicit
[v2 checkpoint](contracts/loan-opening-review-v2.md) now supports inclusive original
anniversary collection previews for unchanged item principal. It subtracts the
reviewed cumulative baseline through cutover, not merely opening unpaid interest,
so covered amounts and aggregate rounding are preserved. Exposure uses this rule
instead of native daily projection. Owner-authorized remaining-obligation persistence
uses existing immutable schedule/obligation tables with original dates and strict
retry comparison; the delinquency selector reads reviewed grace. Full release posts
only the additional collection interest in the same transaction as the receipt,
concession, original-schedule termination and custody return. Reversal restores
all of them together. Projection and item-principal reads respect closed intervals
and later reversal. Cash interest beyond the original schedule is explicit in the
release payload, without invented due dates. Partial repayments, native monthly
accrual/capitalization, renewals and auctions remain unsupported for this origin.
Actual source approval, legacy evidence gaps, opening commit, truthful export and
cutover remain pending. See the [servicing decision](adr/2026-09-12-opening-full-release-servicing.md).
Users should not author JSON records.

The offline dump preview also supports an explicit comparison date/timezone and
representative source reconciliation JSON. The [worksheet](implementation/legacy-reconciliation-worksheet.md)
compares inspected legacy expressions without adopting either as an agreed rule.
Released payment examples are controls outside active migration. The generated Excel
worksheet captures owner review only; it is not an opening upload/approval contract.

The owner's saved worksheet answers specify monthly loan-date anniversaries
(January 10 to February 10), no separate receipts/waivers elsewhere, and release
meaning paid and closed. Preserve that closure attestation without inventing missing
payment amounts or complete historical events. The owner subsequently clarified
that a 10,000 loan at 2% issued Jan 10 has 200 interest plus 10 document charge
collected at disbursal, and Jan 20 release collects only 10,000 principal. Preserve
that already-paid first-month coverage and fee; missing payment rows do not mean
no upfront collections. For the same loan released Feb 20, the owner specified
10,200 collected at release: principal plus 200 additional interest, with the
upfront interest/fee already paid. The owner confirmed Feb 11 is the first release
date requiring 10,200: first-month coverage includes Feb 10; the full additional
200 is payable from Feb 11. Preserve that boundary without charging on Feb 10 or
waiting until the next completed month. For a Jan 31, 2026 loan, the owner confirmed
the first additional monthly charge starts March 1, so upfront coverage includes
Feb 28; the owner confirmed April 1 is the first release date requiring 10,400.
Use original-date monthly anniversaries, clamped to month-end when necessary and
restored afterward: do not permanently carry February 28 forward. Collection
increases the day after the inclusive anniversary. The offline validator's period
descriptor alone does not implement this servicing timing. Do not infer
batch-wide amounts or refunds. The owner corrected the initial 9,890 cash answer
to 9,790: the 200 upfront interest and 10 document charge are deducted from the
10,000 loan in this example. Net cash is 9,790 and principal remains 10,000.
The correction is owner-supplied, not a source-data repair. Rounding responses were
148 for the paired 148.20/148.50 question, 149 for 148.80, and 150 for 149.50.
Interpreting the first answer as covering both, these match nearest-whole-rupee
HALF_EVEN, consistent with the old Decimal round(). Preserve these cases; do not
infer per-item/per-period aggregation or fractional-payment rules from those
examples alone. The owner subsequently clarified that they may collect 300 or
290 and accept a 50-rupee shortfall as interest lost; exact fractional rounding
should not block preparation. Use a deterministic rehearsal baseline (sum item
monthly charges, multiply by additional months, HALF_EVEN-round once), distinct
from actual negotiated collections. This is not an automatic 50-rupee tolerance
or principal waiver. Missing receipts/losses remain unknown, including for closed
legacy loans. Single-loan full release now supports explicit interest concessions:
cash plus concession equals total due, principal/capitalized principal/fees stay
fully collectible, and positive concessions require a reason plus existing
Workspace administration and release permissions. Immutable release event values
carry interest paid and interest conceded separately; ordinary reversal restores
both and replay checks all submitted details. The form, release detail and memo
show the concession. No additional table or migration; `loan-history/1` explicitly
rejects concession histories. Batch release, partial repayment and renewal have
no concession extension. Operational migration import and remaining legacy mapping remain pending;
see the [first-import plan](plans/first-legacy-import.md) and
[collection decision](adr/2026-09-12-legacy-collection-estimates-and-concessions.md).
Bronze is a distinct supported Loans metal; no silent OTHER mapping is approved. The owner corrected the initial weight answer: legacy item weight is
NET weight excluding stones/non-metal parts. This supersedes the earlier gross
interpretation. Do not deduct stones again or equate net weight with pure-metal
weight; source purity is separate. Gross weight remains unknown and must not be
invented by copying net weight. The explicit `jcl-owner/1` offline profile now maps
source weight to candidate net weight with the owner evidence reference, restricted
to namespace `6ca968d6-2647-4dbb-8e39-24f0c1a12ed6` and tenant `jcl`; generic
preparation still leaves both weights unknown. Loans owns the pure
`original-anniversary-upfront-inclusive/1` collection calculator. It supports
unchanged principal and whole-rupee monthly charges; version 1 retains its
fractional hold. Explicit `jcl-owner/2` uses calculation version 2 for aggregate
rounding, preserving unrounded values and separate unknown collection/loss fields.
The April 9 rehearsal now yields 2,447 collection illustrations and one source-error
hold among 2,448 active candidates. The earlier 1,700 results remain unchanged.
These are not accounting accruals, certified opening balances or
servicing activation. Opening review v2 and the destination model now retain all
2,470 gross weights as unknown, with required net/purity/evidence; seven Bronze
items map explicitly. Native draft forms and approval still require gross weight
(`blank=False`); known weights retain their SQL positivity/order checks. Explicit
`jcl-owner/2` emits v2 review candidates, leaving financial/destination approval
pending. See the [collateral decision](adr/2026-09-12-legacy-collateral-evidence.md).
Brief "ok" answers
do not supply missing maturity/grace or corrected R07743 balances. Explain technical
terms and obtain remaining rules through concrete business examples. See the
[recorded responses](implementation/legacy-reconciliation-worksheet.md#owner-responses-received-2026-09-12).

The owner approved the bilingual Rokkad / रोक्कड़ logo with forest teal, gold,
and ivory. Shared product branding lives in `components/brand.html` and
`static/images/brand/`; preserve Workspace and issued-document identities.
See [branding](implementation/branding.md).

Development data is experimental; do not infer permission to alter production.
Public env examples contain placeholders only; never print or commit secrets.
The owner confirmed the historical OAuth credential was rotated/deleted; sanitization
was published with the access/media checkpoint. Historical Git cleanup is separate.

FW-001 optional owner-configurable license scope remains shelved pending fresh
review and explicit approval. Do not infer assigned-license or creator-only access.
FW-002 Razorpay setup/test-mode acceptance is shelved because setup has not started.
Do not request provider keys or run provider setup during other work. Acceptance is
still required before real paid onboarding. Neither item resumes from "proceed" on
unrelated cleanup.

R08/R09/R10 cleanup is complete: current docs are separated from history, tour
choices use current product names and preserve old saved answers, and six unused
schema-tenancy settings are removed. The tracked-source AST import guard replaces
the DEA facade guard; migrations/archives and intentional compatibility remain.
R13 removed four unused packages (Viewflow, Slick Reporting, activity-stream and
extensions) and 14 unreachable legacy templates; compatibility routes remain.
See [reachability evidence](implementation/dependency-template-cleanup.md).
Dashboard payment queues explicitly warn when schedule-review loans are excluded.
The unused exported monetary summary reports unavailable totals as None with a
count/completeness flag and requires matching Workspace context.
The business dashboard now uses a separate overview selector: customer/active-loan
counts, current recorded principal/interest, and period-filtered ordinary issues,
new-loan net cash and separate renewal counts. It reuses the canonical event fold
with batched reads, without monitoring refresh. Invalid evidence makes whole money
totals unavailable. Period controls affect activity only; customer/portfolio cards
remain current. See [dashboard definitions](flows/business-dashboard.md).
Dashboard schedule reads are batched per Workspace/date and share the canonical
termination predicate and obligation fold; no persistent cache.
All 136 canonical Loans routes use named workspace_loans adapters. Templates,
redirects, HTMX targets, checklist and borrower-history links explicitly carry the
Workspace. Old mapped-domain routes and named aliases remain available. The old
Loans dispatcher name is only a URL-building compatibility fallback that rejects
unknown paths; it never dispatches views or rewrites responses. New collateral and
storage labels encode scoped QR URLs; old mapped-domain scan links remain valid.
See [routing migration](implementation/loans-workspace-routing.md).
The two Loans setup-link failures were incomplete fixtures: readiness correctly
checks numbering before economics and borrowers. Fixtures now cover each stage.
The Loans views portion of R12 is complete: views.py is a compatibility import
file; feature handlers live in web/. Shared preview assets and loan read helpers
have small dedicated modules. Preserve decorated public imports and scoped routes;
feature modules must not import views.py. Test mocks patch the owning module.
See [module map](implementation/loans-view-organization.md). No business rules changed.
The orgs views portion of R12 is also complete: views.py contains compatibility
imports; account/preferences, slug adapters, workspace settings, role editing,
team/invitations, lifecycle and navigation have dedicated web modules. Shared
access helpers retain the existing policy. All retirement aliases remain; two
unrouted/uncalled backup view classes were removed. See the
[orgs module map](implementation/orgs-view-organization.md). Feature modules must
not import the facade. Model/form/renewal-service review remains separate; avoid
splits solely for size, speculative abstractions and blanket package upgrades.
Document layout, overlay, asset and print-profile forms now live in
loans/web/document_forms.py. loans/forms.py retains their public class imports;
document handlers use the owning module. Preserve fields, validation and scoped
assignment querysets when organizing other form families.
License creation, renewal and series setup forms live in loans/web/license_forms.py;
forms.py preserves their public imports and license_setup.py uses the owning module.
Economic, fee and monitoring setup forms live in loans/web/economic_forms.py;
forms.py preserves their public imports and economic_setup.py uses the owning module.
Form organization preserves policy scope choices, Workspace filtering and starter
defaults; calculations and persistence remain in existing services.
The eight funding forms live in loans/web/funding_forms.py; forms.py preserves
their public imports and funding read/action handlers use the owning module.
Keep eligible collateral, lender selection, confirmation words and request keys
unchanged during organization work; funding services still own lifecycle changes.
The five storage/physical-verification forms live in loans/web/custody_forms.py;
forms.py preserves their public imports and custody handlers use the owning module.
Preserve Workspace/location filtering and resolution inputs. Intake and lifecycle
forms and their shared formsets remain together pending a concrete need to move them.
Rates/appraisal review now drives the next increments. Lending setup shows actual
usable quotes; a source alone is not quote readiness. New/edit loan price preflight
uses the selected series/policy/date/metals and preserves the current form/files
when missing quotes require a Rates detour. Gold-only and appraisal-only loans
must not require unrelated quotes. Commands retain final validation. Quote ages
are displayed. The owner selected same-day quotes at new-loan approval on
2026-09-12, for methods that consume Rates. Approval/disbursal enforcement and
frozen quote provenance are implemented locally. The first version uses today's
loan/disbursal dates as the recommended implementation assumption; historical
entry has no separately confirmed owner contract. Appraisal-only dates stay
unchanged. Changed/stale or missing legacy market evidence requires reapproval;
completed replay preserves evidence after authorization. See the
[decision](adr/2026-09-12-origination-quote-freshness.md) and
[origination review](implementation/origination-rate-freshness-review.md).
Do not silently change approved economics or reuse monitoring-age limits. Complete
monitoring and worker capacity are described below; see
[review](implementation/rates-appraisal-monitoring-review.md).
Rates quotes are immutable evidence: operator effective time is distinct from entry
time, corrections/withdrawals append actor/reason-linked records, and referenced
sources cannot be deleted. Source snapshots preserve recorded metadata. Use the
authorized Rates commands, not model updates or admin edits. Loans selects the
latest applicable INR pure-metal buying price per gram across sources with explicit
effective/recorded/ID ordering; `24k` remains the compatible pure-metal key, labelled
Pure metal for gold and silver. Historical lookups use current corrected knowledge;
completed loan evidence remains frozen. See [quote decision](adr/2026-09-11-rate-quote-evidence.md).
Current collateral monitoring enforces the effective monitoring policy's quote and
appraisal age limits, inclusively by local calendar date (zero means same-day).
Only evidence required by the frozen valuation method blocks coverage; stale or
missing required evidence is unknown. Active held collateral can receive a new
current-time appraisal through the authorized reassessment service, requiring
data.view/data.edit/loan.approve, method/reference/reason and the reviewed version.
It appends immutable evidence with quote context and marks its risk snapshot stale
within the transaction. Original loan/draft evidence stays unchanged; history is
readable with data.view. See [reassessment](flows/collateral-reassessment.md).

Loan health starts from all active Workspace loans, including unassessed ones.
Only today's successful V3 projection is current; reads derive outdated status.
V3 copies canonical projected interest, recorded total due and integrity findings
into existing assessment provenance for dashboard financial-health totals. Old
contracts need one ordinary bounded refresh, without a schema migration. Financial
and collateral coverage completeness are checked separately; unknown coverage can
coexist with usable financial evidence. Per-loan shortfalls are summed without
offsetting surplus on other loans. See the
[dashboard evidence decision](adr/2026-09-12-dashboard-assessment-financial-evidence.md).
Unknown collateral coverage is separate from assessment freshness and payment
performance. Missing current monetary assessments make whole-portfolio totals
unavailable. Source invalidation stays inside its RLS transaction; existing ERROR
projections remain errors (and retry candidates) until a successful refresh.
Monitoring policies amend through immutable, actor/reason-linked successors;
old values/end dates remain unchanged, same-scope precedence uses effective date
then version. Amendments cannot be backdated; original loan terms stay frozen.
The existing reassessment command supports explicit-Workspace bounded repeated
passes, oldest attempts first, under the restricted runtime role and ACTIVE
lifecycle. Optional Compose wiring does not itself start a worker. See
[loan health](flows/loan-health-monitoring.md) and
[monitoring decision](adr/2026-09-11-complete-loan-monitoring.md).

Launch sizing supplied by the owner: 30-100 loans processed per organization/day,
3,000-10,000 active loans per organization, and at least 100 organizations. The
worker is not capacity-validated for this
300,000-1,000,000-active-loan baseline. Correctness tests are not load acceptance.
Prioritize the [capacity review](implementation/rates-appraisal-monitoring-review.md#launch-capacity-requirements-and-review-2026-09-11)
before production claims or simply increasing batch sizes. Closed-loan monitoring
cleanup is implemented; realistic multi-Workspace load acceptance remains open.
The owner shelved further large-scale monitoring tests until better representative
hardware is available (FW-004). Do not automatically restart long local runs.
The one-hour target remains unproven; preserve measured findings for resumption.
See [the shelved work](plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity).

Closed loans keep their financial and monitoring evidence, but leave live health
calculations, source invalidation, active alert lists and background assessment.
Refresh rechecks state under the loan lock, including its error path. Reversing a
release to ACTIVE invalidates the saved assessment and resumes normal selection.

The monitoring command owns per-loan transactions through `risk_jobs`; it must not
run inside a caller's transaction/context. Candidate selection is bounded and
advisory; each loan is rechecked/locked through calculation and commit. Explicit
Workspace IDs receive round-robin turns. Successful rounds use a short busy pause;
empty/error-only rounds use the longer repeat interval. No Redis/queue or tenant
enumeration is introduced. See [worker turns](adr/2026-09-11-monitoring-worker-turns.md).

Single-schedule obligation reads now prefetch date-filtered allocations in two
queries and use the existing fold. Keep reversal effective-date filtering and
integrity findings unchanged. Mixed benchmarks are synthetic evidence, not a
production distribution or launch SLA.

Owner-selected monitoring launch acceptance target: all affected active loans
receive an updated health assessment within one hour of a metal-price change.
This is a target to load-test, not an established SLA. Closed loans are excluded;
individual authorized refresh remains available. Full-platform capacity remains
unproven until the 100-Workspace workload meets this target alongside servicing.

Health reassessment follows source changes and daily date rollover; worker polling
is not an hourly recalculation requirement for already-current loans. Operational
performance uses oldest unpaid contractual obligation DPD, with default Watch >=1
and Substandard >=90, independently of collateral coverage. This is not a formal
regulatory NPA engine; lender-specific classification/cure/reporting review is
captured as FW-003, unscheduled and not authorized by the capacity task. See
[the explanation](flows/loan-health-monitoring.md#payment-performance-and-the-npa-distinction).
