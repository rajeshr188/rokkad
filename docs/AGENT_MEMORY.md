---
status: active
owner: project
updated: 2026-08-10
tags: [agents, context, architecture]
related: [README.md, STATUS.md, constitution.md, domain/accounting.md, implementation/dependency-policy.md]
---

# Agent Memory

Loans usability UP2.1 bounds the primary PawnLoan worklist at 25 rows and uses
a dedicated tenant-aware `django-filter` FilterSet. Apply workspace scope to
the base queryset first; also bind license and Series filter choices to that
workspace. Search, state, license, Series, and inclusive loan-date filters must
compose, and pagination must retain the active query string. The remaining UP2
order is issued documents, storage/verification, then notices/diagnostics.

Loans usability UP1 adds capture-first collateral media without changing the
evidence model: mobile inputs request the rear camera, desktop browsers can use
an in-page webcam dialog, and all captures submit through existing validated,
immutable photo services. `docs/plans/loans-usability-and-url-consistency.md`
tracks UP2 pagination/contextual django-filter work and UP3 canonical URL
migration. Current `/w/<slug>/loans`, `/loans/internal`, and `/loans/setup`
planes are inconsistent; several workspace-slug loan detail/report aliases
still call Girvi directly. URL cleanup requires an ADR, feature-aware aliases,
and safe compatibility handling rather than a mass rename.

P12 was accepted by the workspace Owner on 2026-08-10. All twelve Loans
capability scenarios are accepted. LPD7.1-LPD7.4 are implemented: physical
print profiles are immutable tenant evidence resolved by `Series -> Workspace
-> built-in`; all embedded legacy compositions have compatibility contracts;
and new configurable ticket issues render logical Original/Terms/Duplicate/D3
surfaces before profile-owned A5/A4 packaging. Exact stored official issues are
returned before current profile resolution. New issues record immutable
profile identity/hash/source; Owner/Admin has audited
`?print_profile=legacy` recovery and runtime never falls back silently. Pair
validation and integrity diagnostics reject profiles the resolved layout cannot
supply. Owner/Admin profile lifecycle, scoped assignment, resolved preview/test
print, and immutable issued-document evidence are exposed under Loans setup;
assignment itself rejects incompatible current layout/profile pairs. Migrations
`loans.0037` and `0038` are applied across all six local tenants, and `jcl1`
has zero findings. Only the physical printer matrix remains open; embedded
composition must stay readable for compatibility.

New document-layout authoring uses schema v3. It stores logical loan-ticket
surface backgrounds separately and rejects embedded `copy_mode`/`sheet`
physical packaging; schema-v3 tickets must render through an explicit print
profile. Visual and advanced authoring cannot downgrade a new schema-v3 draft.
Existing schema-v1/v2 layouts keep their embedded composition and explicit
audited legacy recovery indefinitely.

Under P12, ordinary workspace members may perform the
normal PawnLoan lifecycle but must be rejected before administrator-only
auction/correction identifiers are resolved. Setup and corrections permit
Owner/Admin; manual storage and physical verification remain Owner-only for
the pilot. The sole global override is `is_platform_admin`, and it must agree
at HTTP, service, and UI boundaries. Unknown and foreign-workspace identifiers
must be indistinguishable `404` outcomes for an otherwise authorized user.
Collateral item scans may open their workspace-owned loan for Members, but
verification preselection is Owner-only.

P11 requires all report screens and CSV/XLSX/PDF exports to
use the same tenant-scoped canonical selector. Daily activity and Party
statements retain original and compensating events with correction links and
honest delivery state. Party transaction history must not include an event
after the selected as-of date. Required documents remain typed immutable
projections; the report hub only routes operators to them and never recalculates
or mutates their evidence.

P10 corrections are administrator-only, reason-required, immutable, and
strictly newest-first. In `DEA`, only a `POSTED` source may be reversed and DEA
must receive the compensation. In `DEFERRED`, only an intact `PENDING` source
may receive a `PENDING` compensating source event; it must carry no fabricated
DEA voucher or journal identity. Never domain-only reverse an already-posted
source after the mode changes to deferred. Loan detail and preflight must expose
the original, compensation, reason, actor, resulting balance/custody, and honest
delivery disposition.

P9's operator screen must expose frozen/observed/pending
and blocker counts, keep completion unavailable until all expected items are
observed, and show expected versus observed location plus immutable resolution
and alert evidence. A verification discrepancy uses the stable request key
`verification-discrepancy:<observation id>`; repeated clicks must not create
duplicate alerts. Only failed Notify jobs expose Retry. Preserve the ownership
boundary: Loans freezes notice
intent, source balance, recipient and schedule; Notify v2 owns templates,
delivery jobs, attempts and provider state. The current report may route an
operator to a preselected interest-due/overdue notice, but the service must
recheck eligibility and confirmation must freeze current facts. Historical
reports must not present their old balance as a current send instruction.
Loan detail is the audit/retry surface and shows both Loans and Notify identity,
snapshotted due components, attempt count, failure and provider evidence.

P7 permits Top-up Renewal from an active source with zero outstanding
principal when the top-up produces a positive collateral-backed successor.
Validate `source outstanding - principal paid + top-up > 0`; do not test
`principal paid >= source outstanding` independently because that incorrectly
rejects the zero-balance top-up case. Pay and Renew with a zero successor still
belongs to Full Release.

P7 software execution and Owner acceptance are complete.
`preview_pawn_loan_renewal_plan` is the tenant-scoped, non-writing
exact preflight: it includes source dues, successor principal/monthly interest,
fresh advance interest and deducted fees, collateral counts, and net cash
direction. The UI must submit its fingerprint, and the atomic command must
recalculate and reject stale economics. Renewal freezes the current successor
policy rather than cloning the source policy. Settlement preserves source
dues, principal delta, successor advance interest, and successor fees as
separate gross accounting facts. Successor opening evidence feeds itemized
accruals so prepaid interest is consumed once. Cash recognition credits income;
accrual recognition credits Unearned Revenue until accrual. Renewal documents,
reconciliation, and composite reversal include the full economics. Migration
`loans.0036` is applied to all local schemas.

P6 full release was accepted by the workspace Owner on 2026-08-10. P7 release
and renew is active. Preserve the accepted boundary: close the source contract,
return omitted items, carry retained item identity/photo/storage lineage,
accept photographed additional collateral, and activate exactly one newly
numbered successor with fresh item economics and immutable closing/opening
evidence. The pilot still needs an operator-readable exact preview and must
present its legal output as the renewal agreement; do not weaken composite
newest-first reversal or turn renewal into an in-place edit.

P6 preview hotfix: `assert_pawn_loan_financial_actions_allowed` defaults to a
locking read for mutation commands, while read-only release and repayment
previews explicitly pass `lock=False`. Do not reintroduce `select_for_update`
into GET/preview paths. `preview_pawn_loan_full_release(11)` was verified in
the real `jcl1` tenant outside an atomic block and returned settlement 5100
with release-day catch-up 100. Focused release and repayment tests pass.

P6 full-release software execution is complete. Use
`preview_pawn_loan_full_release` for the operator quote: it is tenant-scoped,
performs no writes, includes release-day partial-period catch-up, and shares
the canonical calculation boundary with confirmation. The release UI lists
every returned collateral item and requires an explicit exact-settlement plus
physical-handoff acknowledgement. Confirmation reports the actual release,
closure, returned-item count, and accounting delivery state. Active
configurable release/Form H layouts without both customer and authorized-staff
signature evidence are document-integrity findings. Existing domain behavior
still enforces completed-period accrual, immutable accounting and
item-principal closure evidence, all-item return/storage removal, loan closure,
no partial collateral release, and strict newest-first compensating reversal.
Eight focused tests plus Django and migration-drift checks pass. P6 still needs
Owner browser/document acceptance; do not activate P7 until that acceptance.

P5 accrual and repayment was accepted by the workspace Owner on 2026-08-10.
P6 full release is active. A full release must use the canonical current-date
settlement/readiness calculation, finalize required catch-up interest, append
immutable accounting plus item-principal closure evidence, return and remove
every remaining collateral item from storage, produce the required signed
release/Form H document, close the loan, and remain reversible only under the
strict newest-first compensating rule.

P5 accrual/repayment software execution is complete. `preview_pawn_loan_repayment`
is a tenant-scoped, current-date, no-write application service that uses the
same canonical allocation functions as confirmation. Never turn preview into
a temporary event or duplicate the arithmetic in views/templates. Accrual
preview and finalized loan detail expose immutable item principal/rate,
calculated interest, advance offset, and newly due rows. Repayment preview
shows fees → overdue interest → current interest → principal and
highest-rate-first item-principal impact. Confirmation remains the sole event,
outbox, and allocation-line write boundary and reports its actual delivery
state. Loan detail links to the receipt and Party statement. Twenty-five focused tests
pass; P5 was accepted by the Owner on 2026-08-10 and P6 is active.

P4 hierarchical storage was accepted by the workspace Owner on 2026-08-10.
P5 accrual and repayment is active. Preserve current-date-only repayment,
fees → overdue interest → current interest → principal priority, and
highest-monthly-rate-first item-principal reduction. The missing pilot surface
is operator preview/readability, not new financial authority: expose itemized
accrual calculations and repayment allocation before confirmation, then prove
the immutable event, receipt, accounting disposition, and Party statement.

P4 hierarchical-storage software execution is complete. Owner item-label scans
and the Place/Transfer action select an in-vault item in a workspace-scoped
browser session; scanning a Box/Slot destination then opens the same transfer
form preselected. The session is only navigation state, is revalidated against
tenant/custody, and is cleared on success; immutable movements and the guarded
current-location projection remain domain truth. Loan detail now exposes the
movement ledger. The 8-test collateral media/storage/verification gate passes.
P4 was accepted by the Owner on 2026-08-10 and P5 is active.

P1 regulatory setup is accepted by the workspace Owner as of 2026-08-09 under ADR
`2026-08-09-loans-effective-dated-calculation-policy.md` and domain reference
`loans-regulatory-setup-and-policy.md`. Effective-dated workspace/license
economic policy now owns calculation method, part-month slab, capitalization,
cash/accrual recognition, valuation/LTV, advance interest, and rounding.
Approval freezes those values and disbursal rehydrates its immutable
`LoanPolicySnapshot` from approval evidence. Girvi's license/series outcomes are
classified: license/series and independent numbering are `PORT`; immutable
license revisions and bounded sequence exhaustion are `REPLACE`; loan-count and
loan-amount auto-deactivation thresholds are `RETIRE for MVP`. Focused gates
pass. P2 mixed-metal origination and disbursal was accepted by the workspace
Owner on 2026-08-09. Loans models each collateral item as a principal/rate tranche,
requires draft photographs, enforces item LTV, freezes approval evidence, and
snapshots gross principal, advance-interest/fee deductions, net cash, and
tranches at disbursal. The draft preview exposes per-item rate, value, LTV
limit, and interest, and LTV failures attach to the offending item without
consuming a number. Do not restore a mutable loan-level interest rate as
authority. The accepted walkthrough includes the number visibility and
deferred-accounting lifecycle corrections.
P2 walkthrough feedback requires number clarity on the draft itself: create
shows non-consuming next-number previews for selectable series, while a saved
draft shows its permanently allocated official number.

Loans lifecycle readiness is accounting-mode aware. In `DEFERRED`, intact
`PENDING` outboxes are expected source evidence and must not block servicing or
be described as posted; missing, `FAILED`, or `PROCESSING` evidence still
blocks. In `DEA`, every non-posted outbox blocks dependent financial actions.
Future activation is proposed in ADR
`2026-08-09-loans-deferred-to-dea-activation.md`: prefer a frozen,
Owner-confirmed opening-position cutover with append-only coverage for included
pending outboxes, followed by exact reconciliation and only then the audited
mode switch. This is not accepted or implemented. Never treat a preference
toggle as replay, mutate covered outboxes to `POSTED`, or fabricate historical
cash vouchers.

Loans is the selected target loan platform under accepted ADR
`2026-08-09-girvi-capability-extraction-into-loans.md`. Girvi is now a temporary
business-rule and operator-capability reference, not a competing destination.
Do not copy Girvi models, routes, statuses, mutable totals, or migration history
into Loans. Extract each rule/outcome, classify it `PORT`, `REPLACE`, `RETIRE`,
or `DEFER`, implement it through Loans' services, immutable evidence, selectors,
custody, tenant, correction, and outbound-accounting boundaries, then prove it
with the corresponding P1-P12 Loans acceptance scenario. Girvi still owns and
services all Girvi-created records; no transfer, synchronization, dual write,
origination shutdown, or deletion is authorized before a separate retirement
ADR. P3 physical identity was accepted by the workspace Owner on 2026-08-09
after its software and physical print/scan gates. The next acceptance gate is
P4 hierarchical storage placement and transfer.
P3 must reject active configurable ticket assignments that omit either copy or
the borrower/customer plus authorized staff signature roles on each front.
Fixed tickets already satisfy those rules. Collateral labels use immutable item
UUID identity and must retain their exact tenant scan target and PDF hash.
The complete 59-test P3 software gate passes and the Owner accepted the physical
ticket, label, signature-area, and scan outcome.

The previously dirty accounting/Girvi/Loans work is now organized into four
dependency-ordered runtime commits: `0e847b2` (guarded standalone accounting
successor and audited preferences), `9ca47c9` (Loans workspace-controlled DEA
deferral), `cc7fc38` (Girvi deferred events plus immutable TakenLoan repayment
evidence), and `7c74d07` (development-only retirement of obsolete Girvi data
transforms). Missing workspace context always resolves to `DEFERRED`. Loans
itemized tests must freeze real economic/rate policy and opening-tranche
evidence; do not weaken the production fail-closed check. Itemized accrual after
capitalization remains blocked until capitalized principal has immutable item
attribution, although repayment of the separately classified capitalized amount
is supported. Girvi outbox and repayment replay now reject a reused key when
economic details differ. Exact checkpoint `ab399e2` passes the final sequential
preflight: 40 accounting kernel/projection, 4 clean-database concurrency, 33
accounting facade/UI, 59 Loans, and 64 Girvi tests; system/diff/migration-drift,
fresh tenant migration, and `jcl1` document-integrity gates also pass. The
validated pre-pilot archive is `backup/pre_parity_ab399e2_20260809.dump` with
SHA-256 `0B0974621C61579C74272494FF843E8D98176D983857D52CDBF83A879E08A950`.

Loans OP5 notice coverage is complete under accepted ADR
`2026-08-09-loans-operational-notice-intents.md`. Existing PawnLoan intents
cover repayment, interest due, overdue, release confirmation, and auction.
Migration `loans.0033` adds immutable Owner-addressed operational intents for
license expiry and completed physical-verification discrepancies. Loans owns
intent/source/recipient/payload evidence; Notify v2 alone owns delivery state.
The shared tenant scheduler and source-local retry controls cover both streams.
OP6 essential reports and regulatory documents are the final parity blocker.

Loans OP4 physical verification is complete under accepted ADR
`2026-08-09-loans-physical-verification-evidence.md`. Owner-only sessions freeze
in-vault items and expected locations for a Vault/subtree; found, missing,
misplaced, and unexpected observations are immutable. Completion requires all
expected items. Separate immutable resolution may correct location, confirm a
find, record lost-item market value/negotiated cash settlement, or classify
damage. Unresolved discrepancies block transfer, release, renewal, and funding
pledge. Damage remains blocked pending future policy. OP5 notices and OP6
essential reports/documents are next.

Loans OP3 hierarchical storage is complete under accepted ADR
`2026-08-09-loans-hierarchical-collateral-storage.md`. Storage enforces Branch
→ Vault → Cabinet → Box → optional Slot, with tenant-unique codes, stable QR
identity, optional capacity, immutable movement evidence, and a guarded single
current-location projection. Manual placement/transfer is Owner-only for the
pilot. Null in-vault location is visibly awaiting placement. Release, auction,
renewal, and renewal reversal maintain location evidence without accounting.
OP4 physical verification is next.

Loans OP2 collateral identity/media/labels is complete under accepted ADR
`2026-08-09-loans-collateral-identity-media-and-labels.md`. Collateral has an
immutable UUID identity; draft edits preserve rows; approval requires at least
one append-only JPEG/PNG evidence row per item and freezes its hash. Retained
renewal items inherit explicit predecessor media evidence and added items need
fresh media. Audited label preview/print contains loan, item, Party, description,
weight, and tenant-scoped QR navigation. OP3 hierarchical storage is next.

Loans OP1 regulatory-license operations are complete under accepted ADR
`2026-08-08-loans-license-regulatory-evidence.md`. `LoanLicense` is the
workspace-scoped current projection; issue, amendment, and renewal append
immutable `LoanLicenseRevision` evidence with validated supporting documents.
Every new PawnLoan captures the exact license revision at draft creation so a
later renewal cannot rewrite the legal identity of an existing loan. The setup
UI exposes revision history, secure evidence downloads, readiness/expiry
status, and the license-register PDF. External expiry delivery remains OP5;
OP2 collateral photographs and labels are the next pilot-blocking slice.

Girvi and Loans coexist temporarily under accepted ADR
`2026-08-09-girvi-capability-extraction-into-loans.md`. Loans is the target;
Girvi is the capability reference. Keep strict source ownership and no transfer,
synchronization, mirroring, or dual write. Loans must pass operational
parity for regulatory operations, collateral photos/labels, hierarchical
storage, physical verification, required notices, reports, statements, and
documents. Run the twelve scenarios as Loans acceptance gates, consulting
Girvi only to extract mature rules and expected outcomes. Bulk actions are useful but do
not block the first parity pilot. Retirement still requires operator evidence
and a separate accepted ADR.

For the parity pilot, collateral photographs are mandatory at PawnLoan draft
capture and must block approval when required evidence is absent. The MVP label
contains loan number, item identifier, item description, Party, weight, and a
QR code. Only legally or operationally necessary reports and regulatory forms
block the pilot; broad Girvi report parity does not. The owner will compare
Girvi and Loans primarily by architecture clarity, document clarity, readable
domain workflow, and ease of operation.

The parity pilot's required reports are active loans, daily disbursal and
repayment, interest due, overdue, release/renewal, storage inventory, license
expiry, and Party statement. Required forms are loan ticket, repayment receipt,
release memo/Form H, renewal agreement, notices, and license register. Every
collateral item needs at least one draft photograph. QR opens the owning loan by
default and may select the item inside release, verification, or storage
transfer flows. Missing or misplaced verification status blocks release,
renewal, repledging, and storage transfer until an administrator records
resolution evidence.

Post-approval collateral photos are append-only; prior photos cannot be
replaced or deleted. Each item projects exactly one current storage location,
and transfer scans both item and destination QR. Verification may cover a whole
vault or selected location subtree. Administrator discrepancy resolution may
correct custody/location or classify loss/damage without changing the original
observation. Loan tickets and releases require customer/staff signatures; loan
tickets require original and duplicate copies.

For the first operational parity pilot, only the workspace Owner may transfer
stored collateral or conduct physical verification. Lost collateral requires
cash-settlement compensation before its discrepancy and workflow blockers can
be cleared. Current market value is the basis, and negotiation determines the
final amount; required evidence is still undecided. Damaged-collateral release
policy is explicitly deferred. Loan-ticket Original and Duplicate
copies share one document number and verification identity. Signatures may be
handwritten or digitally captured. Storage uses the required unskippable path
Branch -> Vault -> Cabinet -> Box -> optional Slot. Initial placement may occur
after disbursement and must remain visibly awaiting placement. A Custodian role
may receive transfer and verification permissions after the pilot.

Loans configurable documents have an in-app Owner/Admin starter guide at
`/loans/setup/documents/guide/`, linked from the layout list, plus the canonical
operator guide at `docs/flows/loans-document-layout-operator-guide.md`. Normal
staff do not configure layouts: they keep using the existing loan/event PDF
actions, which resolve Series -> License -> Workspace -> fixed renderer.
Rich composition is sequenced as Flow schema v2, flow containers, page/table
regions, safe formatting, visual flow editing, then a separately validated
absolute-overlay renderer and editor. Schema v1 remains supported unchanged;
schema v2 currently permits only `FLOW` with bounded margins and theme tokens.
Flow v2 also supports recursively validated `section`, `columns`, and
`field_grid` containers. Column widths must total 100%, nesting is limited to
three levels, nested assets participate in revision validation/hashing, and
page breaks cannot be nested.
Flow v2 tables may select payload column indexes with custom labels,
percentage widths, alignment, repeated headings, and constrained variants.
Bounded header/footer regions repeat compact blocks on every page and reserve
body space; invalid indexes, unsupported region blocks, and overflow fail
closed.
Flow v2 values support allow-listed case, ISO-date, and decimal formatting;
declarative PRESENT/EMPTY/EQUALS/NOT_EQUALS conditions over registered scalar
bindings; and WRAP/SHRINK/ERROR character-overflow policies. Mandatory fields,
tables, and verification require an unconditional occurrence, preventing
conditional removal of regulatory evidence.
Owner/Admin users can visually edit Flow schema-v2 drafts at the revision's
`designer/` route. It changes the same JSON via `update_draft`, supports
page/theme settings and common top-level block operations, and links directly
to preview/test print. Advanced JSON remains required for deep nested and
specialized properties; published revisions cannot enter the editor.
Schema-v2 `ABSOLUTE_OVERLAY` is now a separate renderer for existing forms. It
requires a background key and uses whole-mm rectangles from the page top-left.
It supports bounded title/field/image/QR/verification/signature/table blocks,
formatting, conditions, copies, and duplex; Flow containers/page regions and
automatic pagination are invalid. Geometry or content overflow fails closed.
Owner/Admin absolute-overlay drafts expose a visual editor with an authenticated
first-page background raster, proportional rectangles, drag-to-update X/Y,
exact numeric/property forms, supported block add/remove, settings, preview,
and test print. It persists only through the same validated JSON revision
service; advanced JSON still owns specialized and back-page properties.
Loan-ticket-only overlay sheet composition currently treats A5 Original front,
Original Terms, Duplicate front, and Duplicate D3 as logical surfaces before
output imposition. Eight embedded layout presets sequence A5 pages or impose
left/right pairs on A4 landscape. Blocks have Both/Original/Duplicate scope;
each front copy independently requires all mandatory evidence, and every
required surface asset fails closed. Printer duplex flip-edge behavior is
deliberately outside the PDF contract.

Accepted ADR `2026-08-09-loans-logical-layout-and-print-profile-separation.md`
defines the target extraction: layouts retain logical copy identity, content,
backgrounds, signatures, and mandatory evidence; immutable workspace print
profiles own physical copy bundles, paper, imposition, page order,
simplex/duplex, orientation, scaling, and printer guidance. Issues must snapshot
the resolved profile revision/hash and exact PDF bytes. LPD7.1 implements the
validated contracts, immutable profile revisions, assignment, and resolver;
issue provenance and renderer composition are still pending. Existing
published layouts and embedded `copy_mode`/`sheet` settings remain authoritative
and renderable until deterministic migration and parity checks pass.

This document stores durable project context for AI agents. The root [AGENTS.md](../AGENTS.md) defines the operating rules; this file explains what the system is and how to reason about it.

Girvi and Loans are temporarily independent products under accepted ADR
`2026-08-08-temporary-girvi-loans-coexistence-and-parity-selection.md`. Both may
originate new records. Girvi exclusively owns every Girvi-created record and
Loans exclusively owns every Loans-created record for the full lifecycle; do
not copy, transfer, synchronize, or dual-write records between them. Both post
through DEA only when the audited workspace `accounting__integration_mode` is
explicitly `DEA`. The default `DEFERRED` mode preserves Loans source events and
outboxes as `PENDING`, skips automatic delivery and DEA readiness, and never
claims those events are posted. Existing DEA history remains authoritative and
untouched. Do not replay deferred events without a separate reconciled
activation design. Girvi `GivenLoan` disbursal and `TakenLoan` activation use
versioned outbox contracts in `DEFERRED` mode and bypass DEA account resolution
and voucher creation; `DEA` mode is unchanged. `TakenLoan` repayment now owns
immutable `LoanRepayment` evidence, uses it for idempotency and settlement,
retains only unlinked historical DEA vouchers in compatibility totals, and
emits a pending `TAKEN_LOAN_REPAYMENT` event in deferred mode. Its reversal
contract is a separate exact compensating row; update/delete is database-
blocked. Do not generalize this behavior to `GivenLoan` repayment, release,
accrual, recovery, renewal, write-off, or reversal delivery yet. Real DEA
TakenLoan posting currently fails in its existing rules because
`DualLedgerLine.currency` is omitted. The current
`loan__new_module_enabled` setting is transitional
default-route behavior and must not be interpreted as an ownership cutover.
Optional combined reporting must be read-only and source-labelled.

Girvi destructive cleanup completed on branch `dea-kiss` on 2026-08-08.
`GivenLoan` and `TakenLoan` are the only runtime loan models in
`girvi.models.loan`; deprecated `Loan`/`LoanPayment` classes and resources are
deleted by migration state `girvi.0029`, while active `LoanChangeLog` lives in
`girvi.models.audit`. Runtime managers are canonical in `girvi.managers` and an
AST guard rejects transitional/legacy model imports. Lifecycle status and
transition aliases are removed. The Girvi/Loans unified-read, comparison, and
coexistence-readiness surfaces are retired under ADR
`2026-08-08-girvi-canonical-cleanup-and-coexistence-retirement.md`. Notify uses
generic `NotificationItem` links only. Fresh tenant migration replay, the
64-test cross-app gate, focused lifecycle/import suites, Django checks, and
migration drift checks pass. The full `apps.tenant_apps.girvi.tests` package is
a valid tenant-aware gate: database-backed series guardrail tests use isolated
tenant schemas, and all 409 tests pass. Wave 4's destructive reset runbook exists
but has not been executed.

Future Girvi implementation is proposed as a destructive in-place operational-
core rebuild under ADR `2026-08-08-girvi-operational-core-rebuild.md` and plan
`girvi-operational-core-rebuild.md`. Keep the `girvi` app/product identity and
Girvi/Loans independence, but replace current internals with explicit
`CustomerLoan` and `FundingLoan` aggregates, Party-only counterparties,
immutable operational evidence, projected balances/custody, and application
handlers. Narrow cross-app access to facades before replacing the 33-step
Girvi migration chain with a clean baseline. The complete operational lifecycle
must pass with a null accounting adapter before any accounting outbox is added.
This direction remains proposed until the owner confirms the scope-decision
table and destructive reset; do not begin the schema replacement before then.

The active direction is Girvi capability extraction into Loans under ADR
`2026-08-09-girvi-capability-extraction-into-loans.md` and plan
`loans-girvi-consolidation-fit-gap.md`; the Girvi rebuild is on hold as fallback.
Strict independent ownership remains authoritative during temporary
coexistence. A later accepted retirement ADR must authorize Girvi shutdown and
record treatment. FundingLoan Gate A passes 15 pure tests covering immutable
terms, lifecycle, simple monthly interest, repayment allocation, event-folded
balance, multi-PawnLoan pledge/return LTV, settlement-plus-custody closure, and
exact newest-first financial/custody correction. It has no ORM/accounting
dependency and leaves runtime support false. Gate B must begin with reviewed
persistence, constraints, commands/repositories, concurrency, and a null
accounting adapter before any model or migration. Do not delete Girvi
schema/routes, transfer rows, change module flags, or connect funding accounting
during this evaluation.

FundingLoan Gate B persistence/application design is accepted at
`docs/implementation/funding-loan-gate-b-persistence-design.md`. It requires a
separate operational event table, immutable terms/pledge/return/custody
evidence, a partial unique active pledge per Pawn collateral item, database
cross-workspace/source and append-only guards, deterministic lock order, and
null outbound adapters. Schema slice 1 completed on 2026-08-08 in additive
tenant migrations `loans.0019` and `loans.0020`: eight FundingLoan persistence
models, funding sources on the shared custody stream, active-pledge uniqueness,
and reversible PostgreSQL lifecycle/immutability/source/custody guards. Eight
focused database tests, fresh tenant replay, and auction/renewal custody
regressions pass. Application slices 2-3 now provide transaction-scoped locked
numbering, draft/cancel, atomic multi-PawnLoan activation, canonical request
replay, event-backed interest/fee/repayment, settlement, LTV-safe return, and
financial-plus-custody closure through null outbound delivery. Concurrent
double pledge has one winner, outbound failure rolls back all operational
evidence, and bounded numbering issues its maximum once via migration
`loans.0021`. Gate B corrections are complete through additive tenant
migrations `loans.0022`-`loans.0025`: exact newest-first financial reversal,
immutable pledge/return reversal evidence, exact inverse custody provenance,
atomic pledge-membership/custody compensation, and corrected re-return.
PostgreSQL guards enforce immutable evidence, source agreement, exact/latest
inversion, and one unreversed return per pledge item. The final 40-test
FundingLoan gate plus one legacy custody regression passes. Gate C should start
with read-only selectors and integrity findings before any write surface. That
read-only foundation is now complete in `loans.selectors.funding_loans`:
tenant-scoped immutable summaries/details fold balances only from FundingLoan
events; detail includes terms, lender, source collateral, and combined
financial/custody correction timeline; integrity checks report sequence,
activation, event-fold, custody projection/timeline, and closed-state
discrepancies without mutation. The full 40-test FundingLoan suite passes. Next
an unlinked Owner/Admin-only read console and detail page were added under Loans
setup. They render selector output only, expose no write controls, deny ordinary
members, return not found for unknown/cross-workspace identifiers, and preserve
`FUNDING_LOAN_RUNTIME_SUPPORTED = False`. The unlinked Owner/Admin draft and
lender-capture flow is now complete: it selects only active Party lenders,
delegates creation and numbering to `CreateFundingLoanDraft`, records the real
actor, and redirects to read detail. Invalid/inactive choices consume no
sequence. Draft completion is also complete through tenant migration
`loans.0026`: mutable pre-activation terms and collateral choices remain
separate from immutable activation evidence; eligible choices are active,
appraised, in-vault Pawn collateral without an active funding pledge; the
existing funding policy validates terms and LTV before save; detail shows
readiness; and cancellation records immutable reason/actor evidence. Draft and
cancelled loans with no events project zero balances. Controlled Owner/Admin
activation is complete: exact `ACTIVATE` confirmation invokes
`ActivateSavedFundingLoanDraft`, which locks and revalidates saved inputs through
the existing activation service, creates immutable terms/event/pledge/custody
evidence, and deletes mutable inputs only after success. Stale inputs roll back
without losing the proposal. Hidden Owner/Admin repayment capture now delegates
to `record_funding_repayment`; a form UUID preserves exact browser replay,
overpayments create no evidence, actor identity is stored, and allocation stays
fees then interest then principal. Funding detail projects reversal-aware
component effects and running balances solely from immutable FundingLoan events.
Hidden settlement review and controlled collateral return are complete. The UI
starts review only when the event-derived total due is zero, distinguishes
financial settlement from custody completion, and exposes active collateral
returns only in `SETTLEMENT_PENDING`. The existing return service remains
authoritative for locking, LTV, active pledge membership, exact replay, custody
evidence, and actor capture. Runtime remains false. Controlled closure is
complete. `begin_funding_settlement` now enforces zero
balance inside the locked service rather than relying on UI visibility. Closure
requires exact `CLOSE` confirmation and delegates to `close_funding_loan`, which
recomputes financial/custody readiness, records the actor, and replays terminal
state idempotently; closed detail exposes no servicing controls. Runtime remains
false. Gate C is complete. Hidden correction controls expose selector-approved
latest financial, eligible return, and whole-pledge targets; POSTs require a
reason/effective date/request key and delegate immutable compensation, exact
replay, actor evidence, ordering, and custody checks to the existing services.
Fixed, non-persisted FundingLoan preview PDFs cover agreement/handoff,
repayment receipt, return receipt, and event-derived statement with source-
linked verification IDs and `Operational accounting: Not posted`. They do not
create document issues or extend configurable layouts. The tenant workflow
proves correction replay/projection, all four PDFs, settlement, return, and
closure. Keep runtime support false and leave public navigation, Girvi changes,
accounting delivery, and persisted/configurable FundingLoan documents deferred
unless a later gate explicitly authorizes them.

Gate D is authorized with essentials-only parity. FundingLoan's current hidden
Owner/Admin core is ready for a controlled pilot, but Loans cannot yet win
retirement approval. Blocking capabilities are versioned license evidence and
renewal/expiry operations; mandatory draft photos plus append-only later media,
audited labels and QR; hierarchical Branch/Vault/Cabinet/Box/optional Slot
storage; immutable physical verification/discrepancy resolution; and only the
confirmed notices, reports, and regulatory forms in the parity pilot plan.
Bulk workflows, broad archive parity, split/merge, and mutable historical
correction do not block the first pilot. The minimum reconciliation pack must
cover source identity, financial and custody/location folds, documents,
permissions/tenant isolation, actual deferred-or-posted accounting disposition,
exceptions/replay/corrections, and backup/restore hashes. Unexplained money,
custody, tenant, required-document, or reconciliation differences disqualify a
candidate. Run identical scored scenarios in both applications; one product
must eventually retire, but only a later accepted ADR may name the winner,
stop loser origination, define remaining-record treatment/rollback, or
authorize destructive cleanup. Implement OP1 regulatory operations next; do
not enable FundingLoan runtime, navigation, or accounting as part of OP1.

Fresh migration replay intentionally skips three retired Girvi data operations:
RepledgedLoanItem custody copying, legacy Loan copying into GivenLoan/TakenLoan,
and LoanPayment archival into draft DEA vouchers. Their migration nodes and all
schema operations remain for graph compatibility; already-applied databases are
unchanged. Do not restore these conversions unless legacy-data preservation is
explicitly reauthorized.

Standalone accounting architecture proof K0 began on 2026-08-07 under proposed
ADR `2026-08-07-standalone-accounting-transaction-kernel.md` and active plan
`standalone-accounting-kernel-proof.md`. The supplied *Ledger - Double Entry*
schema is being evaluated as a new accounting ontology, not copied literally.
The proof package is `apps.tenant_apps.accounting` and must remain unregistered,
model-free, migration-free, URL-free, and disconnected from current DEA until
the architecture gate passes. Its initial pure kernel treats each positive
monetary transaction as exactly one ledger-to-ledger or
ledger-to-external-account atomic pair; external accounts are genuine sides
with frozen classification versions, compound events are ordered batches, and
reversal creates opposite transactions in reverse order. Current DEA remains
the runtime authority. Do not mark the ADR accepted or introduce persistence
until K1-K3 prove financial reports without double-counting, external-account
reconciliation, historical classification stability, period/idempotency rules,
and transaction/base currency behavior.

Standalone accounting proof K1 is complete. Its executable corpus covers cash
sale, credit sale, partially allocated customer receipt, supplier purchase and
payment, loan disbursal, split principal/interest/fee repayment, an explicit
many-sided atomic batch, and whole-batch reversal. All scenarios balance when
internal-ledger and external-account sides are counted once; none creates a
duplicate GL control posting. `AccountSettlement` and `OpenItemAllocation` are
non-financial explanation over an existing account transaction and must never
materialize money. They reject over-allocation and cross-account allocation.
The K1 fold is only a test oracle. K2 production projections must be implemented
independently and compared with it; do not reuse the oracle as reporting code.

Standalone accounting proof K2 is complete. The independent
`accounting.domain.projections` layer produces exactly two conventional lines
per atomic transaction, separate internal/external balances, a combined trial
balance, P&L, and a balance sheet with current-period result. External account
effects enter financial statements through their frozen classification exactly
once; they do not require duplicate GL control postings. Classification
reconciliation defines `external detail + direct internal reporting-ledger
activity = trial-balance row`, and later classification versions do not alter
older transactions. Whole-batch reversal neutralizes all projections. This
clears the primary reporting objection to the proposed ontology, but the ADR
must remain proposed until K3 proves voucher authorization, book-scoped
idempotency, periods, currency provenance, corrections, and source/rule identity.

Standalone accounting proof K3 and the formal architecture gate passed on
2026-08-07 with all 40 K0-K3 tests passing. The pure posting layer requires
immutable authorization, retains source-event and posting-rule versions in its
fingerprint, makes idempotency book-scoped, returns exact replays, rejects key
reuse with changed economics, enforces period policy, validates transaction-to-
base conversion and rate source, and models correction as original plus new
reversal plus new replacement. ADR
`2026-08-07-standalone-accounting-transaction-kernel.md` is accepted for
persistence design. This does not change current runtime ownership: DEA remains
authoritative, while `apps.tenant_apps.accounting` remains unregistered and has
no models, migrations, routes, or integrations. K4 must design the persistence
mapping and app skeleton before any tenant schema is introduced; later tenant
migrations use `migrate_schemas`.

Standalone accounting K4 is complete. `apps.tenant_apps.accounting.apps` now
defines import-safe `AccountingConfig` with label `standalone_accounting`, but
the app remains absent from `TENANT_APPS`/`INSTALLED_APPS` and still has no
models, migrations, URLs, admin, or integrations. The accepted persistence
mapping is `docs/implementation/standalone-accounting-persistence-design.md`.
It uses one `AccountingTransaction` row lifecycle: editable as authorized
voucher intent, then immutable when a one-to-one posting batch is created; no
second posted transaction table is allowed. A transaction has exactly one
deferred-constraint-enforced ledger or account subtype. Explicit accounting
organization/book ownership avoids workspace-model dependency. PostgreSQL
constraints/triggers must enforce subtype exclusivity, posted immutability,
ledger cycles/leaves/debit-credit permissions, cross-table book agreement, and
protected classification versions. K5.1 must introduce only organization/book,
period, and ledger master models, review the tenant migration, then use
`migrate_schemas`; external accounts and monetary transactions remain later
slices.

Standalone accounting K5.1 is complete. `AccountingConfig` is now registered
in `TENANT_APPS`. Tenant migration `standalone_accounting.0001_initial` contains
only `AccountingOrganization`, organization-scoped `AccountingBook`,
non-overlapping `AccountingPeriod`, and hierarchical `Ledger`. It deliberately
uses `external_tenant_key` rather than a workspace FK. Period overlap is
database-enforced with `btree_gist` and an inclusive daterange exclusion per
book. A PostgreSQL trigger enforces same-book/intermediate parents, prevents
cycles, and blocks children under posting ledgers even when model validation is
bypassed. All 52 focused tests pass; tenant/public isolation is covered. The
migration was applied with `migrate_schemas --tenant` and verified in `jcl1`,
`jsk`, and `test`; no accounting master rows were seeded. Current DEA remains
the only runtime accounting authority. K5.2 may add external accounts and
immutable effective-dated classifications only; vouchers and monetary
transactions remain out of scope until that boundary passes.

Standalone accounting K5.2 is complete. Tenant migration
`standalone_accounting.0002_externalaccount_externalaccountclassification_and_more`
adds `ExternalAccount` and `ExternalAccountClassification`. External accounts
belong to a book, carry an adapter `party_key`, and separate accounting purpose;
they do not FK to Rokkad Party. Classification ranges cannot overlap. Their
reporting ledger must be a same-book posting ledger whose reporting class and
normal side match. Database triggers prohibit deletion and all core mutation;
the sole allowed update closes an open range once. The atomic append service
locks versions, closes the current range immediately before its successor, and
the selector fails unless exactly one version covers the posting date. All 57
focused tests pass. Migration/table verification passed in `jcl1`, `jsk`, and
`test`, with no seeded accounts. K5.3 may add voucher headers and draft atomic
transaction base/exclusive subtypes only; posting batches/runtime posting remain
K5.4.

Standalone accounting K5.3 is complete. Tenant migration
`standalone_accounting.0003_voucher_accountingtransaction_accounttransaction_and_more`
adds voucher headers, a shared positive monetary `AccountingTransaction`, and
exclusive `LedgerTransaction`/`AccountTransaction` subtypes. Deferred database
constraints require exactly one matching subtype. Immediate guards enforce
same-book posting sides, book currency conversion, effective frozen external
classification, and authorized-intent immutability even through bulk SQL paths.
Draft services construct complete pairs atomically and authorization freezes
intent without posting it. All 63 focused tests pass; migration and four-table
verification passed in `jcl1`, `jsk`, and `test`, with no seeded rows. DEA is
still the sole runtime accounting authority. K5.4 may add one-to-one posting
batches and an atomic posting repository/service, but not runtime cutover.

Standalone accounting K5.4 is complete. Tenant migration
`standalone_accounting.0004_transactionbatch_and_more` adds `POSTED` vouchers
and a one-to-one immutable `TransactionBatch`. The canonical service locks an
authorized voucher and its unique covering period, enforces open versus
adjustment-only purpose, fingerprints frozen source/rule/economic/
classification facts, and creates the posted state plus batch atomically.
Deferred PostgreSQL cardinality prevents a posted voucher without exactly one
batch or a batch on a non-posted voucher. Posted intent and batches reject
update/delete bypasses; exact repeated posting returns the original evidence.
All 67 focused tests pass and migration/table verification passed in `jcl1`,
`jsk`, and `test`, with no seeded rows. DEA remains production authority and no
runtime callers use the successor. K5.5 may implement append-only reversal and
correction with exact opposite/reverse-order verification.

Standalone accounting K5.5 is complete. Tenant migration
`standalone_accounting.0005_transactionbatch_reversal_reason_and_more` adds
mandatory reversal reason and a PostgreSQL exact-reversal trigger. The service
locks the original posted batch and creates a new adjustment voucher whose
transactions are the exact reverse-order opposite: ledger sides swap; account
internal side swaps while account, ledger, money, currency provenance, and the
original frozen classification FK remain identical. It authorizes and posts
that evidence atomically. One original permits one reversal; same-idempotency
replay returns it, a distinct second reversal fails, and reversal-of-reversal is
prohibited. Correction composes reversal plus an authorized replacement under
one correction group without changing the original. All 71 focused tests pass;
migration and trigger verification passed in `jcl1`, `jsk`, and `test`, with no
seeded rows. DEA remains production authority. K5.6 may persist open items and
non-financial allocations over posted account transactions.

Standalone accounting K5.6 is complete. Tenant migration
`standalone_accounting.0006_openitem_openitemallocation_and_more` adds immutable
`OpenItem` and `OpenItemAllocation`. An open item is one-to-one with a posted
account transaction and freezes its book, external account, transaction/base
money, and optional due date. Allocation is explanatory only: it points to a
posted opposite-side settlement on the same book/account/currencies and never
creates an `AccountingTransaction`. The canonical service locks settlement and
open-item capacities; database triggers independently reject cross-boundary or
over-capacity inserts and all update/delete bypasses. Outstanding is derived
from original minus allocated values. All 74 focused tests pass; migration,
both tables, and both triggers are verified in `jcl1`, `jsk`, and `test`, with
no seeded rows. K5.7 must add compensating allocation evidence for reversed
settlements rather than editing/deleting original allocations, then proceed to
persisted reporting projections. DEA remains production authority.

Standalone accounting K5.7 is complete and is an explicit MVP integrity slice,
not feature expansion. Migration
`standalone_accounting.0007_openitemallocation_reversal_of_and_more` adds one
nullable one-to-one `reversal_of` link. Reversing a posted settlement now also
creates exact compensating allocation rows against the corresponding reversed
account transaction in the same atomic operation. Original rows never change;
outstanding derives from original allocation totals minus compensations. Model
and PostgreSQL rules verify item, transaction/base money, currencies, and
financial reversal lineage. All 75 focused tests pass; migration, column, and
trigger verification passed in `jcl1`, `jsk`, and `test`, with no seeded rows.
Do not expand this into allocation strategies, UI, aging caches, runtime wiring,
or cutover. K5.8 should implement only read-only ORM projections needed for the
persisted MVP kernel, without another writable accounting representation.

Standalone accounting K5.8 completes the persisted MVP kernel proof. It adds
no model or migration. Read-only ORM selectors load posted vouchers for one
book/date range, adapt their frozen facts to the proven K2 pure contracts, and
project conventional journal lines, separate internal/external balances,
balanced trial balance, P&L, balance sheet with current-period result, and
classification reconciliation. Draft/authorized vouchers are excluded and no
reporting balance is stored. A persisted credit-sale plus receipt scenario
passes every report/reconciliation expectation without changing transaction
row count; all 76 focused tests pass. Pause feature expansion here. The next
stage is a K6 MVP readiness review that chooses the smallest safe pilot or stops;
do not infer UI, tax, bank feeds, budgets, consolidation, recurring entries,
allocation strategies, caches, data migration, runtime wiring, or cutover. DEA
remains production authority.

Standalone accounting K6 readiness decision: GO only for an isolated synthetic
non-production acceptance pilot; NO-GO for production posting/shadow traffic,
DEA replacement, or data migration. The kernel has 76 passing focused tests,
all seven migrations verified in `jcl1`, `jsk`, and `test`, no public-schema
tables, and no local successor data. Production blockers are: authenticated
tenant-bound facade and permissions/trusted time; durable actor evidence and
voucher-number policy; controlled period lifecycle; deterministic bootstrap;
one idempotent source adapter; operational diagnostics; migration/backup/
restore rehearsal; separate-connection concurrency tests; and accountant
sign-off. The authoritative review and smallest synthetic pilot are in
`docs/plans/standalone-accounting-mvp-readiness.md`. Do not implement broad UI,
tax, bank, allocation strategy, reporting cache, legacy migration, or cutover
work under K6. The next permitted implementation is only the isolated pilot
bootstrap/harness; a production boundary requires a separately approved K7.

The owner accepted the recommended K6 defaults without further interview. ADR
`2026-08-07-standalone-accounting-pilot-policy.md` fixes a correctness-first,
synthetic-only sales/receipts pilot, permits the dedicated tenant owner to
create/authorize/post only in sandbox, and chooses independent book/year
voucher numbers with separate source identity. The guarded idempotent command
`run_accounting_acceptance_pilot` requires `DEBUG`, an existing
`accounting_pilot_*` schema, explicit `--confirm-synthetic`, and that tenant's
owner ID. It creates a deterministic five-voucher sale/receipt/reversal/
correction cycle and verifies reports/reconciliation. All 77 accounting tests
pass. On 2026-08-07, the normal onboarding path created the disposable
`accounting_pilot_mvp` tenant and the harness ran twice with identical balanced
evidence and no change to DEA beyond its standard seed baseline. Automated
sandbox execution and idempotent replay therefore pass; owner/accountant review
and sign-off remain outstanding. Do not open K7 or production integration before
that review.

The internal accountant-style K6 review accepted the synthetic accounting with
one presentation observation: the INR 600 receipt needed to expose INR 400
allocated and INR 200 unapplied separately. The read-only
`posted_unapplied_settlements` projection now provides that evidence, the live
pilot reports it, and all 77 tests pass. K7 production-boundary work may begin;
this is not production approval. Independent owner/professional acceptance and
the other K6 gates still precede any production authority or DEA replacement.

Standalone accounting K7.1 is complete. `accounting.facade` is the required
future production mutation boundary: it verifies active authentication, exact
tenant schema/workspace context, workspace permissions, and accounting-book
tenant identity; supplies server timestamps; separates authorizer from poster;
and prevents the original poster from approving a reversal. Member prepares;
Admin/Owner authorizes, posts, and reverses. Persisted evidence is reloaded to
prevent stale-object bypass. Low-level services remain internal, and no route or
runtime caller exists. K7.2 must add durable actor snapshots/created-by evidence
and atomic annual voucher numbering before runtime integration.

Standalone accounting K7.2 is complete. Vouchers now retain immutable creator
and authorizer ID plus identity snapshots, posting batches retain poster ID plus
snapshot, and database constraints/triggers protect the evidence. Facade-created
vouchers ignore caller-supplied numbers and atomically allocate
`BOOK-YEAR-NNNNNN` using the containing accounting period's start year and a
locked per-book/year sequence. Direct proof services preserve compatibility with
explicit pilot numbers. Tenant migrations `0008`/`0009` backfilled the pilot and
are applied to all four local tenant schemas with zero missing actor evidence.
All 82 accounting tests and the live pilot pass. Separate-connection race proof
remains K7.5; K7.3 is controlled periods and deterministic bootstrap.

Standalone accounting K7.3 is complete. `accounting_period_manage` is limited
to Admin/Owner through the facade. Periods transition Open -> Adjustment-only or
Closed, Adjustment-only -> Closed, and Closed -> Adjustment-only or Locked;
reopen requires a reason and Locked is terminal. Immutable transition rows store
actor snapshots and time, while PostgreSQL requires the latest evidence for a
status update. The idempotent bootstrap creates only WORKSPACE organization,
PRIMARY INR book, a caller-specified period, and Cash/Accounts Receivable/Sales
ledgers, failing closed on conflicts. Migrations `0010`/`0011` are on all local
tenant schemas and all 84 accounting tests pass. K7.4 is one narrow source adapter.

Standalone accounting K7.4 is complete. `SalesReceiptEventV1` is the sole MVP
runtime DTO and supports only INR CASH_SALE, CREDIT_SALE, and CUSTOMER_RECEIPT.
The adapter resolves accounting configuration internally and calls the
authenticated facade with separate maker/authorizer/poster. A canonical payload
hash permits exact replay, rejects changed-payload source reuse, rolls back all
partial accounting on failure, and preserves FAILED attempt/error evidence.
Posted delivery/source identity is database-immutable. Migration `0012` is on
all local tenants with no seeded rows; all 87 accounting tests pass. K7.5 is
integrity diagnostics, real separate-connection races, and recovery rehearsal.

Standalone accounting K7.5 engineering assurance is complete. The tenant-only
`check_accounting_integrity` command is read-only and fails on posting/subtype,
fingerprint, actor, report, classification, allocation, or delivery findings.
Four ThreadPoolExecutor tests use separate database connections/tenant contexts
to race identical delivery, changed payload, reversal, and allocation capacity.
The `accounting_pilot_mvp` schema was dumped and restored to a temporary schema;
all 16 accounting table counts and diagnostics matched, and the clone was
removed. The operations runbook is canonical. K7.6 remains independent UAT and
explicit go/no-go; DEA is still production authority.

Standalone accounting K7.6 engineering evidence is complete. The source
adapter now creates credit-sale open items and receipt allocations inside its
atomic authenticated delivery, and the accountant evidence command presents
voucher actors, journal/reports, external balances, open items, allocated and
unapplied receipts, reversal lineage, deliveries, and diagnostics. Fresh tenant
`accounting_pilot_k7_uat` passed the real adapter scenario with distinct maker,
authorizer, and poster: four deliveries, five posted vouchers, zero report
differences, INR 600 invoice outstanding, INR 400 allocated plus INR 200
unapplied, and zero integrity findings. The owner accepted the evidence on
2026-08-07, stated that an independent
accountant is unavailable, knowingly waived professional review, and authorized
moving ahead only with the tested sales/receipts MVP. Treat this as owner risk
acceptance, not accountant endorsement. K7 is a conditional GO to prepare one
off-by-default narrow caller. Do not migrate data, add other adapters, or
displace DEA; target-tenant readiness verification and explicit enablement are
still required before the caller becomes authoritative.

Standalone accounting K8.1 activation safety is complete. Central audited
workspace preference `accounting__successor_enabled` defaults false. Only an
actor with accounting period-management permission in the matching tenant can
change it, and enablement fails closed without exactly one tenant-bound PRIMARY
book, active CASH/ACCOUNTS_RECEIVABLE/SALES ledgers, an open period, and clean
integrity diagnostics. `accounting_pilot_k7_uat` is ready with zero blockers
but remains disabled. K8.2 is the immediate first visual slice: tenant-scoped
dashboard, sales/receipt entry, voucher evidence, journal, trial balance, P&L,
and balance sheet, with mutations only through the facade/source adapter.

Standalone accounting K8.2a is complete. Tenant URL `/accounting/` renders an
authenticated read-only dashboard with activation readiness, headline evidence,
and recent posted vouchers; `/accounting/reports/` renders trial balance, P&L,
balance sheet, and open items; voucher detail renders durable maker/authorizer/
poster/source evidence and conventional journal lines. These screens remain
available for inspection while the activation flag is off and outsiders are
rejected. K8.2b must model three genuine user actions for source entry,
authorization, and posting; never select users behind the scenes or attribute
actions to people who did not perform them.

Standalone accounting K8.2b is complete for the visual MVP. With the audited
activation flag on, `/accounting/transactions/create/` creates cash-sale,
credit-sale, or customer-receipt drafts through the facade; voucher detail
offers state-appropriate POST-only authorize and post actions; and posted
receipts expose explicit single-open-item allocation. The maker cannot authorize
their voucher and the authorizer cannot post it. Credit-sale posting plus open
item creation is one outer atomic facade operation. A three-client tenant test
proves Member creation, rejected maker approval, Admin authorization, Owner
posting, and persisted open-item evidence. K8.3 must run this visually in the
pilot tenant and rerun diagnostics/evidence before any real target enablement.

Standalone accounting visual setup now handles ordinary tenants with no
successor configuration. The dashboard exposes `/accounting/setup/` only to an
actor with `accounting_period_manage`; its validated period form calls the
authenticated idempotent bootstrap for the tenant-bound PRIMARY INR book and
CASH/ACCOUNTS_RECEIVABLE/SALES ledgers. Setup deliberately leaves activation
off and does not import DEA data. Never instruct owners to use shell bootstrap
for this normal state.

Owner/Admin users can explicitly manage the successor write gate at
`/accounting/activation/`. The page shows current readiness and narrow-scope
warnings, requires `ENABLE ACCOUNTING` to turn writes on, and uses the audited
fail-closed feature service. Turning it off is immediate and does not alter
posted data. Enabling this gate permits standalone UI writes only; it is not a
DEA cutover or historical-data migration.

The standalone accounting visual MVP defaults to audited `OWNER` workflow
mode. The real workspace Owner may confirm once; dedicated facade logic records
that Owner truthfully as creator, authorizer, and poster while preserving
draft/authorized/posted lifecycle and immutability. This is an explicit
segregation-of-duties waiver in the amended authorization ADR, never actor
impersonation. `TEAM` retains separate actions. Entry can create a missing
Party and its standalone customer-receivable/classification inline. Migration
`0013` adds a protected Party FK and uniqueness by book/Party/purpose; it is
applied in all five local tenant schemas. Pre-link synthetic external accounts
may remain null, but every new visual customer account must link to the tenant
Party. Keep this KISS flow and add no configuration without a concrete owner
task.

Standalone accounting visual reversal is implemented. Never offer “unpost”:
posted voucher detail links to a reversal form requiring date, reason, and
typed `REVERSE`. In OWNER mode a dedicated facade truthfully permits the actual
Owner to reverse their own original; TEAM mode uses the different-user facade
rule. Original and opposite vouchers remain linked. A reversed invoice open
item reads as zero and cannot receive allocations; an allocated invoice must
have its receipts reversed first. Verification is temporarily blocked at
Django import by unrelated user-owned Girvi edits whose `loan.py` imports the
removed `LoanManager`; do not modify those changes as part of accounting work.

## Project Identity

Rokkad is a tenant-aware SaaS mini ERP for small businesses, especially jewellery, pawn/loan, commodity, inventory, and future commerce workflows.

Accounting is the central source of truth. Loans, inventory, future sales/purchase documents, and commodity transactions are business documents that produce accounting, stock, and commodity ledger effects.

The product must feel document-centric, not module-centric.

## Core Mental Model

Business Event
-> Source Document
-> Posting Engine
-> Voucher
-> Journal Entry
-> Financial Ledger
-> Inventory Ledger
-> Commodity Ledger
-> Reports

Users should create business documents, not manual journal entries.

## Core Modules

- Accounting
- Loans / Girvi
- Inventory
- Future sales/commerce
- Future purchase/procurement
- Commodity management
- Workspace management
- Subscription management
- Authorization
- Onboarding
- Customer portal
- Notifications

## Design Principles

1. Accounting is central.
2. Business documents create vouchers.
3. Vouchers post journal entries.
4. Journal entries are immutable.
5. Corrections happen through reversals.
6. Every accounting entry must link back to its source document.
7. Commodity is tracked as inventory/position, not as normal currency.
8. Multitenancy uses workspace/tenant isolation.
9. UI should follow business workflows, not database tables.
10. Normal users work with documents; accountants can inspect vouchers, journal entries, and ledgers.

## Important Domain Concepts

Loans rewrite Phase 7 status: E7.1 notice intent/delivery integration, E7.2
PawnLoan auction/recovery, and E7.3 PawnLoan renewal are implemented. Renewal
uses an immutable close-old/open-new aggregate, explicit collateral lineage,
net DEA settlement, operational successor opening, and composite reversal.
Auction completion is deliberately
limited to exact canonical-debt recovery; shortfall write-off and
borrower-surplus distribution require future explicit accounting documents.
Auction collateral uses immutable snapshots and custody events, and correction
uses administrator-only compensating reversal rather than mutation.

PawnLoan collateral economics were clarified on 2026-08-05 in ADR
`2026-08-05-pawn-loan-collateral-tranche-economics.md`: each collateral item
owns allocated principal and a frozen metal-specific monthly rate; loan totals
are sums, item allocation cannot exceed valuation times LTV, and gross
principal is distinct from net cash after configurable advance interest and
fees. E7.3A.1 provides the tested database-free calculation contract, and
E7.3A.2 adds effective-dated tenant configuration plus nullable collateral
allocation/rate provenance in `loans.0012`. Policy resolution is explicitly
license-over-workspace and date-aware. E7.3A.3 makes that configuration
operable and switches browser draft/approval to required item allocations,
resolved metal rates, current metal/appraisal valuation, per-item LTV, derived
aggregate terms, no-write preview, and provenance-rich approval snapshots.
Legacy internal commands with no allocations remain readable without invented
facts until their later lifecycle slices are converted. E7.3A.4 adds immutable
disbursal evidence linked to approval, policy, and accounting source event.
DEA now preserves gross borrower principal while crediting only net cash plus
the exact advance-interest and deducted-fee destinations; cash accounting
recognizes withheld interest immediately, while accrual accounting credits
Unearned Revenue. Legacy allocation-null approvals retain the aggregate
compatibility contract and receive no fabricated snapshot. A dedicated
versioned appraisal aggregate (appraiser, time, method, notes, media/tests,
approval, and reappraisal) is deferred explicitly to roadmap E7.6A; until then,
staff appraisal values are frozen in approval and disbursal evidence.

E7.3A.5 adds immutable `PawnLoanInterestAccrualLine` rows for every new
itemized accrual, including release/auction/renewal catch-up periods. The line
freezes principal base, item rate, period fraction, high-precision and rounded
interest, advance interest applied, and newly due interest. Advance interest
is a per-item monetary balance: cash-basis finalization does not charge a
covered period again, while accrual-basis finalization debits Unearned Revenue
and credits income without a borrower receivable for the covered portion.
Legacy aggregate loans retain their earlier behavior. Itemized accrual fails
closed after any unexplained aggregate principal change; never distribute that
change by guessing.

E7.3A.6 adds immutable `PawnLoanRepaymentAllocationLine` evidence for the
original-principal portion of each repayment. Allocation is deterministic:
highest frozen collateral monthly rate first, then collateral ID. Lines record
order, frozen rate, balance before, principal applied, and balance after, and
their sum must reconcile to the event's original-principal split. Capitalized
interest remains separately classified and is not assigned to collateral.
Item-level accrual bases are reconstructed from the disbursal snapshot and
active repayment lines; reversing a repayment restores prior bases by excluding
the reversed event, never by editing its lines. Any gap, discontinuity,
misordering, or aggregate mismatch fails closed. Receipts expose the immutable
allocation trail. Release and renewal evidence is described below; auction
still needs equivalent item-level lifecycle evidence before it may alter these
bases.

E7.3A.7.2 adds `PawnLoanPrincipalClosingLine` and
`PawnLoanPrincipalOpeningLine` in tenant migration `loans.0016`. New itemized
full releases and renewal settlements freeze each source item's remaining
principal to zero in rate-descending deterministic order. Explicit
release-and-renew successors freeze fresh item principal/rate and optional
predecessor lineage on their operational opening event; tranche reconstruction
and later accruals use those active opening lines when no disbursal snapshot
exists. Reversed opening events are excluded rather than mutated. Do not invent
lines for legacy aggregate loans. Explicit renewal fails closed if capitalized
interest would be carried because that amount has no successor-item attribution.

E7.3A.7.3 completes the MVP read/correction boundary around that evidence.
Composite renewal reversal must derive each source item's restore state from
its immutable renewal custody event; it cannot assume every source item was
retained. Reconciliation treats renewal-backed customer returns as valid and
raises explicit missing/mismatch issues when itemized release or renewal
opening/closing lines do not reconcile to their event and collateral. Reports
list release-and-renew source/successor contracts, and verification PDFs expose
item settlement plus retained, returned, additional, and successor-opening
facts. Reversal never deletes or changes principal evidence; active balance
folds exclude the reversed opening event.

Auction item-principal evidence is deliberately deferred as roadmap slice
E7.3A.8 because auction is outside the initial limited MVP pilot. Do not remove
or silently absorb this work. Before enabling Loans auction operations,
E7.3A.8 must define deterministic proceeds allocation, persist immutable item
recovery lines, reconcile them to pre-auction tranches and the aggregate event,
support compensating reversal, expose the evidence in reports/PDFs, and cover
tenant/accounting/custody boundaries. Legacy aggregate auctions must remain
readable without fabricated item rows.

ADR `2026-08-05-pawn-loan-release-and-renew-only.md` supersedes support for new
same-loan partial collateral release. The supported boundaries are partial
repayment without custody change, full settlement/release/closure, and release
and renew into a newly numbered successor containing selected retained and
optional additional collateral. The old partial-release HTTP and service
boundaries fail closed; historical immutable partial releases remain readable
and reversible. Renewal must create fresh item allocation, rate, valuation/LTV,
fee, advance-interest, approval, lineage, custody, and opening evidence rather
than mutating the source contract.

The release-and-renew command/UI accepts an explicit collateral plan. Retained
source items are copied first with fresh allocated principal and `renewed_from`
lineage; omitted source items move to customer custody; optional additional
collateral follows with no predecessor. Successor allocations must exactly
equal calculated successor principal, and normal draft/approval economics
resolve current metal rates and per-item valuation/LTV atomically. Payloads and
snapshots identify retained, returned, and additional items. Legacy aggregate
service calls retain the old all-item compatibility path only for existing
development coverage; the browser never uses it. Composite reversal now
restores mixed returned/retained/additional source custody from each immutable
renewal custody event.

Use a generic party model where possible:

- Customer
- Supplier
- Broker
- Employee

A party can have multiple roles.

Use source documents:

- Sale
- Purchase
- Loan
- Receipt
- Payment
- Expense
- Stock Adjustment
- Commodity Contract
- Commodity Settlement

Do not make accounting models depend directly on UI forms. UI creates documents; posting rules create vouchers and journal entries.

Girvi document numbering uses `GirviNumberSequence` rows as locked allocation state, but runtime preview/allocation must still check existing document IDs and skip stale sequence values. A create screen must show the next available ID for the selected series, while save-time allocation remains the authority.

Girvi custody transitions own custody-field persistence. `LoanItem`'s normal post-approval edit guard must remain intact, but release/repledge/return operations must use the custody-only persistence path so an in-memory custody change cannot be mistaken for a database handoff.

Girvi final release settlement must fail on selector or accrual-query errors. `SELECTOR_COMPATIBILITY` is reserved for the explicit no-posted-accrual-rows case and must remain visible in reconciliation.

The side-by-side Loans app uses explicit `PawnLoan` and future `FundingLoan` concepts rather than a single over-generic `Loan` model. These are Loans-owned aggregates; they do not replace or absorb Girvi `GivenLoan` or `TakenLoan` records.

The Loans app is PawnLoan-first. A regulatory license belongs to one workspace and owns multiple bounded pawn-loan/release numbering series; official loan numbers allocate at draft creation and never recycle. Loan economics and policy are snapshotted at disbursal, loan events use a durable idempotent DEA outbox, posted corrections use strict reverse-order administrator reversals, and closure requires both zero balance and completed collateral return. Girvi and Loans may both originate records and each remains exclusive write owner of the records it creates.

The historical Loans execution order is the `E0-E7` plan in `docs/plans/loans-rewrite-roadmap.md`; its replacement/cutover objective is superseded by `docs/adr/2026-08-08-girvi-loans-permanent-independent-coexistence.md`. The older numbered capability list is reference material only. FundingLoan remains a future vertical slice and must not be introduced as a partial runtime model.

The durable Girvi-versus-Loans architecture explanation and feature-parity register lives in `docs/apps/loans/architecture-and-girvi-parity.md`. Operational parity is now a required evidence gate for selecting one application and retiring the other; it does not predetermine the winner.

Historical Loans E6.1-E6.5 work implemented and piloted temporary unified reads, comparison, cutover readiness, and default routing in disposable workspace `jcl1`. Cleanup checkpoint `01c99f6` retired the unified-read, comparison, and coexistence-readiness implementation. The remaining `loan__new_module_enabled` setting may choose the canonical landing route only; it does not block Girvi origination, transfer ownership, or disable either app. Replace it with independent module-availability settings and a default-module preference before treating the configuration as final product policy.

Loans rewrite E7.1 is complete. `PawnLoanNotice` owns tenant-scoped, idempotent
notice intent, schedule, recipient snapshot, financial payload snapshot, and
Notify event/job references for repayment reminders, interest-due notices,
overdue notices, and release confirmations. Notify v2 exclusively owns
templates, provider execution, attempt logs, sent/failed state, external
references, and errors; Loans joins that state through
`selectors.notices` and must not add a duplicate sent flag. Immediate work is
dispatched after commit and scheduled work uses tenant command
`dispatch_pawn_loan_notices`. Auction notices remain prohibited until the E7.2
auction/recovery aggregate exists.

Loans rewrite Phases 1-5 are implemented and the 134-test tenant-aware MVP gate passes with real DEA fixtures. The registered tenant app has pure PawnLoan vocabulary/policy contracts and tenant models for regulatory setup, locked numbering, PawnLoan/collateral, disbursal policy snapshots, audit history, versioned approval snapshots, durable accounting-event/outbox delivery, immutable monthly interest accrual rows, and explicit one-to-one reversal source links. Licenses and loans carry explicit workspace ownership and reject workspace values that do not match the active tenant; borrowers link directly to tenant `party.Party`. License/series setup goes through tenant-only services, issuance eligibility fails for inactive or expired setup, and sequence configuration changes are public-workspace audited. Pawn-loan and release number allocation uses non-consuming preview plus atomic sequence-row locking; committed numbers never recycle and exhaustion requires another series. Owner/Admin users can complete regulatory license and series setup through tenant-only `/loans/setup/` routes, including readiness and non-consuming previews, without admin-site access. PawnLoan draft creation/editing is service-owned and atomic: it resolves an active tenant Party, validates matching license/series plus all economics/collateral before writing, allocates the official number inside creation, and records creation or before/after draft edits. Feature-hidden `/loans/internal/` screens let workspace members create, correct, approve, reopen, transfer unavailable-license setup, cancel, disburse, repay, accrue/capitalize, and fully or partially release new-app loans while remaining absent from primary navigation. The state-aware detail recommends the next action and exposes balances, custody, setup/accounting blockers, retry, and administrator-only reversal; partial release uses preview-before-confirmation. Owner/Admin users can resolve the borrower-receivable blocker directly from disbursement: one atomic, idempotent, audited setup service composes Party's compatibility Customer bridge with DEA's public account resolver to create or reuse the dedicated `BORROWER / BORROWER_LOAN_RECEIVABLE` mapping without posting accounting. The internal reports surface portfolio balances, accruals, repayments, releases, custody, posting health, and categorized source-to-DEA reconciliation. Loans consumes voucher/journal evidence only through a read-only DEA public facade; findings cover missing, failed, duplicate, mismatched, unbalanced, and impossible lifecycle/accounting states. Essential PDFs are source-linked: the loan ticket renders frozen approval data and refuses drafts, repayment receipts render event splits, and release memos render immutable release headers and collateral snapshots; all carry deterministic verification IDs plus accounting/reversal status, and operational release events without an outbox render accounting as not required. Owner/Admin operations diagnostics expose outbox failures and retry, stale claims, sequence readiness, accounting prerequisites, reversals, and audit evidence without shell or database access; the linked runbook covers tenant deployment, hidden enablement, rollback, reconciliation, and support. Approval freezes a deterministic append-only snapshot; reopening and cancellation require audited reasons; reapproval appends a new version. E3.1 source intent and outbox rows commit atomically with deterministic idempotency/fingerprints; delivery runs post-commit through an injected adapter seam, failures are durable, and Owner/Admin retry is available. E3.2 provides deterministic DEA payload contracts for all MVP PawnLoan event types and resolves the borrower receivable only through the public DEA facade. E3.3 adds a DEA-facade-backed readiness selector for the effective-date open period, CASH funding ledger, loan and borrower control ledgers, borrower receivable, interest income, and conditional fee income; it returns setup links and fails closed for disbursal while keeping drafting available. E3.4 activates approved PawnLoans through one atomic disbursal command that snapshots policy and records/audits deterministic source intent; its default adapter posts a source-linked, balanced DEA voucher and borrower attribution through the public facade, repeated delivery is idempotent, and unresolved delivery blocks later financial actions. E3.5 centralizes event-derived principal, interest, fees, total due, overdue, financial settlement, collateral-aware closure readiness, and accounting-delivery blockers, including reversal inversion and fail-closed history validation. E3.6 records current-date repayment splits in strict fees/overdue-interest/current-interest/principal order, rejects overpayment, uses caller request keys for duplicate-submit safety, atomically records source intent/outbox/audit data, blocks dependent events until posting succeeds, and posts source-linked DEA receipts without changing collateral custody. E3.7 previews full and slab-based partial monthly interest at high precision, finalizes immutable currency-rounded completed-period rows idempotently, stops compound schedules at configured capitalization boundaries, and records explicit capitalization events. Accrual accounting posts receivable/income and capitalization reclassification through DEA; cash accounting keeps those events operational and routes later capitalized-interest collection to interest income without corrupting principal control. E3.8 makes disbursal, repayment, accrual, and capitalization reversals administrator-only and reason-required, enforces strict newest-first order, records immutable compensating domain events, and delegates posted accounting reversal through DEA's public facade. E4.1 adds tenant-scoped valuation and release-readiness reads: calculated metal value uses the as-of 24K buying rate times net weight times purity, appraisal and lower-of-both policies fail closed on missing inputs, and partial-release minimum settlement clears fees/interest before reducing principal to the retained-collateral LTV ceiling. E4.2 persists immutable release headers, item valuation evidence, and custody history; its atomic full-release command requires finalized completed accruals, atomically records release-day partial-period interest, requires exact settlement, and posts through durable DEA accrual/release outboxes, returns every item, and closes only after custody is complete. E4.3 extends the release aggregate to selected collateral: it accepts only the calculated minimum after release-day catch-up interest, settles fees/interest before LTV-required principal, persists selected/retained valuation evidence, moves only selected vault items, derives partial return from mixed custody, and keeps the loan active. A finalized rounded partial period rebases the next accrual window to the following day. E4.4 records administrator-only, reason-required, newest-first release reversal without mutating the original release: linked DEA compensation reverses the settlement and paired catch-up accrual, custody restores only from a compatible physical state, full release reopens to active, partial release stays active, and logically reversed catch-up rows no longer rebase future accruals. FundingLoan remains unimplemented; `jcl1` now uses Loans for development origination, while any production cutover remains gated by E6.4 readiness.

## Accounting Architecture

Other domains should not bypass DEA for ledger effects.

Business documents are not ledger entries. Posting converts business intent into `Voucher`, `VoucherLine`, and `JournalEntry`.

Use immutable journal entries.

If a posted document changes:

1. Reverse the previous journal entry.
2. Create a new corrected journal entry.

Do not edit posted journal lines in place.

Use a posting engine:

- `PostingContext`
- `PostingRuleRegistry`
- `PostingRule`
- `PostingBundle`
- `Voucher`
- `VoucherLine`
- `JournalEntry`
- `LedgerLine`
- `AccountLine`

Each document should expose `get_economic_payload()` or equivalent structured data for fingerprinting and idempotency.

## Architecture Rules

- Other apps should import DEA through `apps.tenant_apps.dea.facade`.
- Tenancy architecture review is documented in `docs/implementation/tenancy-architecture-audit-rls-vs-django-tenants.md`: Rokkad should not attempt a big-bang RLS conversion now. The preferred direction is a hybrid migration path that keeps `django-tenants` running while adding explicit workspace ownership, separating workspace slug from `Company.schema_name`, and preparing tenant-owned models, constraints, reports, jobs, and isolation tests for a later shared-schema PostgreSQL RLS cutover.
- Other apps should import Girvi cross-domain reads through `apps.tenant_apps.girvi.facade` or selectors.
- Girvi lifecycle work should prefer command/use-case services over model methods or large view logic.
- Girvi runtime lifecycle is canonicalized: `GivenLoan` uses `LoanLifecycleState`, legacy loan statuses/actions are compatibility aliases, and `TakenLoan` uses a smaller dedicated lifecycle.
- Girvi app analysis docs live under `docs/apps/girvi/` and should be updated when Girvi models, workflows, UI routes, services, or lifecycle behavior change.
- Contacts should not directly know Girvi internals for loan summary data.
- Tenant seed/setup failures should surface as actionable setup messages, not silent zero values.
- Posting logic belongs in DEA posting services/rules, not views or templates.
- Current Girvi borrower/lender posting paths resolve DEA subledger accounts by party role and purpose (`BORROWER_LOAN_RECEIVABLE`, `LENDER_LOAN_PAYABLE`) instead of reading `Customer.account` directly.
- Current DEA sales/purchase invoice posting paths resolve customer/supplier accounts by party role and purpose (`CUSTOMER_RECEIVABLE`, `SUPPLIER_PAYABLE`) instead of direct `Customer.account` reads.
- Experimental operational `sales`, `purchase`, and `approval` tenant apps were removed from runtime on 2026-06-19. DEA `SalesInvoiceVoucher` and `PurchaseInvoiceVoucher` remain accounting documents; future commerce/procurement apps must be rebuilt around commodity, inventory, settlement, and DEA posting boundaries rather than gold/silver-as-currency balances.
- Party has a tenant UI at `/party/` for list/search/filter, create/edit, detail tabs, role add/end, read-only contact/address/KYC data, DEA party account mapping visibility, and linked customer loan activity.
- Centralized preference architecture has started in `apps.configuration` and is planned in `docs/plans/centralized-preferences-architecture-plan.md`: new code should use `PreferenceService` instead of raw dynamic-preferences managers. `WorkspacePreferenceModel`/`workspace_preferences_registry` are additive, `dynamic_preferences.users` is installed for UI-only user preferences, and existing Girvi `CompanyPreferences` remains a compatibility facade for legacy `Loan__...` and `Interest_Rate__...` keys. That facade delegates legacy registry resolution to `PreferenceService.get_workspace_from_registry(...)`; current Girvi runtime preference reads use `apps.tenant_apps.girvi.service_modules.preferences` instead of importing `CompanyPreferences` directly. Canonical workspace settings preferences render the central registry, the legacy Girvi preference page remains reachable, `migrate_preferences_to_workspace --dry-run` inventories old Girvi rows, and `--apply` writes explicit legacy Girvi mappings to central lowercase `loan__...` keys. Phase 6 snapshot coverage has started for Girvi loan item interest rates and disbursal deduction components; Phase 10 compatibility retirement still waits for broader snapshot/migration evidence.
- Party profile data is editable from Party detail: single profile photo, contact methods, addresses, identifiers, and documents can be maintained directly before Phase 9 operational foreign-key migration work.
- Party profile photos can be maintained from Party detail by either choosing an image file or capturing an image from the device camera.
- Party contact forms validate phone/mobile/WhatsApp through `django-phonenumber-field` with region `IN`, store phone numbers in E.164 format, and Party relationships are maintained from the Party detail Relationships tab.
- Party stores textual relation identity directly on `Party` through `relation_label` and `relation_name` for values like `S/o Kumar`; structured `PartyRelationship` remains for links to saved Party records.
- Party duplicate merge is service-backed and conservative: source parties are archived, non-conflicting profile children and DEA mappings are moved, and merges stop on legacy-customer, identifier, or active DEA mapping conflicts.
- Party list has filtered CSV/XLSX export for Owner/Admin users. The first version is intentionally flat: Party identity fields, contact summary, active roles, and legacy customer linkage; child profile tables remain separate.
- Party Phase 9 uses nullable shadow FKs on operational documents first. Current prioritized shadow links include Girvi borrower/lender loans, DEA sales/purchase invoice vouchers, legacy notifications, and Notify v2 recipients; DEA account resolution prefers explicit Party links and falls back to Customer. Approval is intentionally skipped until that workflow becomes a priority again.
- Party Phase 10 read-only portal MVP is live in tenant URLConf under `/portal/...`. `PartyPortalAccess` links an authenticated user to a tenant Party without workspace membership, `resolve_portal_identity()` requires an active grant and active Party, and portal selectors/pages expose only Party-filtered dashboard, loan, invoice, payment, document, and statement summaries. Portal selector/render tests use real tenant Girvi loan, invoice, and payment fixtures to guard cross-party isolation. MVP portal domain strategy is tenant-path only; branded portal subdomains/public entrypoints wait until real portal usage and the invitation/customer-auth lifecycle are stable. Existing grants use service-owned activate, suspend, and revoke transitions with public workspace audit events.
- Party detail loan history now uses a Girvi facade read model that aggregates active/closed Given/Taken loans plus payment, notice, and collateral summaries for both Party-linked and legacy bridged-customer records.
- Girvi given-loan creation is Party-first while still compatibility-safe: users select an active Party, the create path ensures a legacy `Customer` bridge as needed, and `GivenLoan.borrower` plus `GivenLoan.borrower_party` are both populated.
- Party codes are tenant-local stable identifiers. Normal creation auto-generates sequential `P-000001` style codes when blank; manual/custom codes remain supported for imports and legacy bridge records.
- Girvi TakenLoan amount, weight, current-value, and item-interest read models should use `RepledgeHistory` plus linked `LoanItem` data; `RepledgedLoanItem` is retained only as readable legacy/import compatibility data.
- Refactored Girvi interest query annotations use `calculated_*` names to avoid shadowing read-only model properties such as `loan_amount`, `total_interest`, and `total_due`.
- Girvi transition registries should keep canonical state/UI/form metadata as primary. Legacy transition metadata belongs only in explicit compatibility registries while aliases remain accepted for old URLs/imported values.
- Girvi active list/detail/transition UI should render canonical lifecycle labels through lifecycle display helpers rather than raw persisted status values.
- Girvi transition matrix tests derive canonical transition source/target states from `flows.py`; adding or changing a canonical `GivenLoanFlow` or `TakenLoanFlow` transition should update registry state metadata in the same change.
- Girvi operational endpoints now use centralized permission gates in `views/access.py` (`girvi_permission_required`, `GirviPermissionRequiredMixin`) so create/edit/delete, transition/disbursal, repayment, release mutation, and report routes are not merely login-guarded.
- Girvi customer notice communication now standardizes on notify_v2 batch dispatch: bulk and single-loan notice entrypoints map reminder/auction notice codes to notify_v2 events/channels, and the legacy bulk notice URL is retained only as an alias to the same notify_v2 workflow.
- Girvi MVP document/PDF generation now has a shared `GirviDocumentService` entry point in `service_modules/printing.py`; existing loan ticket and release Form H endpoints call that service, and a new permission-gated repayment receipt PDF route (`girvi_payment_receipt_pdf`) is exposed from loan detail payment rows.
- Girvi safe-operations admin surface now includes a permission-gated Operations Console (`girvi_operations_console`) that centralizes posting/outbox health, controlled retry for failed outbox rows, series/rate setup checks, and recent `LoanChangeLog` audit events.
- Girvi essential report coverage now includes a dedicated permission-gated Operational Controls report (`loan_operational_controls_report`) with outstanding aging, collateral custody, release-readiness, and rate-exception sections; the additional per-retry audit-log emission follow-up is intentionally deferred.
- Girvi policy centralization now covers key workflow guardrails in `policies.py`: release eligibility (`assert_can_create_release`), repayment permission (`assert_can_record_repayment`), and transition readiness (`assert_loan_transition_allowed`), and these checks are used directly by release, repayment, and transition views.
- Girvi view-thinning for Phase 3 now includes release-create orchestration extraction: release preview/submit business flow is centralized in `service_modules/release_workflow.py`, while `views/release.py` handles HTTP/form/messaging concerns.
- Girvi view-thinning for Phase 3 now also includes repayment and transition helper extraction: repayment preview/form-initial/message emission now lives in `service_modules/repayment_workflow.py`, and transition name/form/policy resolution now lives in `service_modules/transition_workflow.py`.
- Girvi view-thinning for Phase 3 now includes custody helper extraction: release-check checklist reads, release-with-return gate/effect orchestration, and release-custody API payload construction now live in `service_modules/custody_workflow.py`, with `views/custody_views.py` focused on request/response messaging.
- Girvi view-thinning for Phase 3 custody flows now also includes taken-loan collateral-return and single-item lender-return execution: `return_taken_loan_collateral` and `return_item_from_lender` delegate mutation orchestration to `service_modules/custody_workflow.py` and keep view-level handling to HTTP/messaging.
- Girvi transition command cleanup now extracts disbursal and recovery side-effect orchestration into `service_modules/transition_side_effects.py`, and custody repledge create request parsing/execution now lives in `service_modules/repledge_workflow.py`.
- Girvi forms-to-workflow cleanup for Phase 3 has started: `LoanItemStorageBoxForm` keeps input validation only, while range-assignment/save side effects moved to `service_modules/storagebox_workflow.py` and are invoked by `views/storagebox.py`.
- Girvi forms-to-workflow cleanup now also covers release forms: `BaseReleaseFormSet.clean()` delegates duplicate/stale release-row workflow checks to `service_modules/release_form_validation.py`, and `ReleaseForm.save()` override was removed to keep the form validation-focused.
- Girvi release-form cleanup now also delegates single-form business checks to `service_modules/release_form_validation.py`: `ReleaseForm.clean_loan()` and `ReleaseForm.clean_release_amount()` no longer embed release state/due-cap logic directly.
- Girvi forms-to-workflow cleanup now also covers repayment forms: `GivenLoanRepaymentForm.clean()` and `TakenLoanRepaymentForm.clean()` delegate settlement/split validation checks to `service_modules/repayment_form_validation.py`.
- Girvi forms-to-workflow cleanup now also covers loan-item forms: `LoanItemForm.clean()` and `InitialLoanItemForm.clean()` delegate collateral-value and initial-row required/default checks to `service_modules/loan_item_form_validation.py`.
- Girvi Phase 3 task 27 is now complete for current MVP view paths: create/release/repayment/transition/custody/repledge orchestration lives in workflow/service modules (including `loan_workflow.py` for create-preview parsing and update persistence), and views are primarily HTTP/message coordinators.
- Girvi Phase 3 task 28 is now complete for current MVP form paths: release, repayment, loan-item, and loan/create/renew/storage-box business validations are delegated to form-validation service modules, while forms remain binding/input-shape oriented.
- Girvi Phase 3 task 29 is complete for current MVP read paths: operations-console report summaries are built by `build_operations_console_read_model`; repledge-history report query/filter/count payload is built by `build_repledge_history_read_model`; item-custody API payload is built by `build_item_custody_status_payload`; dashboard aggregate/count context is built by `build_girvi_dashboard_read_model`; and reconciliation/operational-controls report context shaping is built by selector context helpers before render.
- Girvi Phase 3 task 30 is complete for current MVP scope: statement verification read calculations moved to selectors with compatibility delegators, and `models/loan_refactored.py` high-usage read-only calculations (Given/Taken loan amounts, interest amounts, weight summaries, item descriptions, current values, total payment splits, interest due/accrual/receivable, last accrual date) now delegate to selector helpers.
- Girvi Phase 3 task 31 is complete: runtime `LoanChangeLog` consumers use package-level model imports, migration compatibility helper `migrate_old_loan_to_new_structure` imports `OldLoan` from `models.legacy`, architecture tests restrict direct `models.loan`/`models.legacy` imports to explicit compatibility seams, only `management/commands/missingcol.py` may import deprecated legacy loan models in command surfaces, runtime modules are guarded from importing legacy manual commands (`do`, `missingcol`), and legacy command lifecycle policy is documented in `docs/implementation/girvi-legacy-command-lifecycle.md`.
- Girvi Phase 3 task 34 is complete: runtime notify integration in key Girvi workflows now routes through `integrations/notification_adapter` (with lazy imports to avoid app-load cycles), key boundary views/selectors/transitions no longer directly import notify/contact model modules, and AST guard tests enforce that boundary for `selectors.py`, `views/loan.py`, `views/notice.py`, `views/prints.py`, and `transitions/commands.py`.
- Current Girvi-to-DEA synchronous posting/read integration should go through `apps.tenant_apps.girvi.integrations.dea_adapter`; `service_modules.posting_adapter` exists only as a compatibility import path.
- Girvi refactored loan model payment methods are compatibility wrappers only; voucher creation logic belongs in `service_modules.payment_voucher_creation` and the DEA adapter boundary.
- Girvi P3 adapter cleanup is complete for refactored runtime paths. Deprecated `models/loan.py` may still import DEA directly until P5 legacy model containment.
- Girvi loan detail display data belongs in selectors/read models. Current detail metrics, storage position lookup, interest reporting, release CTA metadata, and action-readiness data are built by `apps.tenant_apps.girvi.selectors` and consumed by thin view rendering.
- Girvi loan detail action-readiness uses `build_given_loan_action_readiness` to show the primary next action, settlement state, collateral state, accounting journal presence, and timeline event count before the full tabbed detail surface.
- Girvi repayment use cases belong in `service_modules.repayment`: GivenLoan receipt catch-up accrual, repayment payload shaping, DEA posting delegation, TakenLoan repayment posting, and result messages should stay out of `views.loanpayment`.
- Girvi repayment UI capture presets belong in `service_modules.repayment_workflow` and should be derived from the shared repayment preview. Given/Taken repayment screens expose exact-settlement, interest-only, and principal-only presets while service success messages report total, principal, interest, and remaining outstanding.
- Girvi release UI readiness belongs in `service_modules.release_workflow`: `build_flow_context` is the shared read model for release pages and custody-check pages, covering settlement, custody, recipient, Form H document expectation, and accounting-posting expectation while `submit` remains the guarded mutation path.
- Girvi release-time settlement interest is implemented with persisted release snapshots: repayment/release previews may keep using selector-computed `loan_interest_due()` as an operational quote, while final release execution runs catch-up accrual through the release date, snapshots settlement values on `Release`, uses eligible posted `LoanInterestAccrual` rows minus paid interest when available, and falls back to selector compatibility when accrual-row authority is not safe for that loan. Release can collect/post the final settlement receipt itself before completing closure; generic closure without settlement remains blocked.
- Girvi non-cash closure must use explicit settlement adjustment document paths. Current `SettlementAdjustmentService` names write-off, interest waiver, settlement discount, auction shortfall write-off, and admin correction as fail-closed categories until each has a source document, audit/approval path, and DEA posting implementation.
- Girvi generated document numbers belong to `GirviNumberSequence` rows scoped by series and document kind. Previews must be non-consuming, allocation must lock the sequence row, missing sequence rows should self-initialize from existing document IDs, Series detail exposes sequence status/sync, existing manual IDs stay supported with cross-table uniqueness checks, and blank repayment references must use service-owned `REPAYMENT-*` idempotency markers instead of direct model payment creation.
- Party-centric Girvi loan history belongs behind `apps.tenant_apps.girvi.facade.get_party_loan_history_summary`; Party views/templates should consume that read model for active/closed loans, outstanding split, payment totals, notices, collateral, repayment shortcuts, and release/Form H document links instead of importing Girvi models directly.
- Girvi-to-DEA accounting readiness belongs in `apps.tenant_apps.girvi.integrations.dea_adapter`: it owns posting event contract versioning, event type/rule metadata, idempotency keys, source-document economic payload extraction, posting-status reads, and reversal delegation. Runtime Girvi code should not import DEA internals directly.
- Girvi bulk merge/delete use cases belong in `service_modules.bulk_operations`: selection parsing, guard validation, merge orchestration, delete orchestration, and structured operation errors should stay out of `views.loan`.
- Deprecated Girvi `Loan` / `LoanPayment` must not be imported from `apps.tenant_apps.girvi.models`; use `apps.tenant_apps.girvi.models.legacy` only for explicit historical compatibility surfaces. Runtime code should use `GivenLoan`, `TakenLoan`, and DEA `PaymentVoucher` paths.
- Girvi legacy payment import/export is intentionally labelled as `LegacyLoanPaymentResource`; `LoanPaymentResource` is only a compatibility alias for old import/export callers.
- DEA posting fingerprints must be based on stable economic payloads, not voucher row ids, timestamps, statuses, or display metadata. Current DEA idempotency coverage expects duplicate posting of the same voucher or same source-document payload to return existing accounting effects, while changed economic payloads reverse the previous voucher and create a corrected posting.
- DEA voucher reversal workflow belongs in `apps.tenant_apps.dea.services.reversal.reverse_posted_voucher()`. `DjangoPostingEngine.reverse_voucher()` and `apps.tenant_apps.dea.views.voucher.reverse_voucher()` delegate to that service; new callers should use it directly so duplicate reversals are idempotent and reversal audit details stay centralized.
- DEA voucher posting workflow belongs behind `apps.tenant_apps.dea.posting.commands.PostVoucherCommand`. `apps.tenant_apps.dea.views.voucher.post_voucher()` delegates to that command; rule-backed voucher types continue through `DjangoPostingEngine`, while manual stored-line voucher types without registered rules use the command's controlled `materialize_journal_from_voucher_lines()` fallback.
- DEA Phase 3 commodity accounting is accepted as a side-by-side layer, not a financial currency extension. Future commodity work should model `Commodity`/`Metal`, `CommodityAccount`, immutable `CommodityMovement`, `ExposureLine`, and `RateFixing` separately from `MoneyField`, `LedgerTransaction`, `AccountTransaction`, and financial trial balance.
- DEA commodity schema planning is in `docs/implementation/dea-commodity-model-schema.md`; it should be kept current as Phase 3 model slices land.
- DEA now has the first commodity model foundation: `Commodity` and `CommodityAccount` with tenant migration `0033`, admin registration, exports, monetary-code guard validation, and party-obligation account validation.
- DEA default commodity setup now exists through `apps.tenant_apps.dea.services.commodity_seed.seed_default_commodities()` and the `seed_dea_commodities` command. It creates/repairs tenant-local `GOLD` and `SILVER` records idempotently.
- DEA now has immutable `CommodityMovement` with tenant migration `0034`, source/voucher links, explicit commodity quantity fields, from/to commodity accounts, monetary valuation currency validation, idempotency/reversal links, read-only admin diagnostics, and tests.
- DEA now has `ExposureLine`, `RateFixing`, and `RateFixingAllocation` foundations with tenant migration `0035`, admin diagnostics, quantity/status/currency validation, and fixing allocation guardrails.
- DEA now has a side-by-side commodity posting service skeleton in `apps.tenant_apps.dea.services.commodity_posting`, with structured payloads and deterministic source/economic-payload idempotency keys for `CommodityMovement` and `ExposureLine` creation.
- DEA now has commodity position selectors in `apps.tenant_apps.dea.selectors.commodity` that compute movement-derived balances by account, party, location, fixed status, and as-of date with reversal offsets.
- DEA MVP commodity valuation policy is documented in `docs/implementation/dea-commodity-valuation-policy.md`: valuation is reporting-only, defaults to INR, uses rates as market inputs, reports missing rates explicitly, and defers `ValuationSnapshot`, unrealized gain/loss, and financial journal effects.
- DEA now has valuation read-model foundation: `rates.facade.get_latest_commodity_valuation_rate()` and `dea.services.valuation` value commodity position rows and exposure lines with buying/selling side policy, missing/unsupported statuses, and no financial transaction side effects. The next safe DEA commodity slice is Phase 4 fixed purchase backend MVP; keep it command/service focused and avoid UI redesign, broad purchase-module work, snapshots, and unrealized gain/loss accounting.
- DEA Phase 4 fixed purchase backend MVP now exists in `apps.tenant_apps.dea.services.fixed_purchase`: fixed purchases create INR-only financial voucher/journal/account effects through `PostVoucherCommand(DjangoPostingEngine())` and a separate fixed `CommodityMovement` atomically. The service is idempotent by source plus economic payload, rejects changed payloads for the same source until correction/reversal is implemented, and keeps commodity quantity out of financial currency paths. The next safe DEA slice is unfixed purchase backend MVP: commodity receipt plus open purchase exposure with no false final monetary payable.
- DEA Phase 4 unfixed purchase backend MVP now exists in `apps.tenant_apps.dea.services.unfixed_purchase`: unfixed purchases create a posted commodity-intent voucher, immutable `CommodityMovement`, and open purchase `ExposureLine` without `JournalEntry`, `LedgerTransaction`, `AccountTransaction`, or `VoucherLine` rows. Final monetary AP must wait for rate fixing. The next safe DEA slice is rate fixing backend MVP: fix open exposure quantity, record `RateFixing`, and create monetary payable through financial posting.
- DEA Phase 4 purchase and sale rate fixing backend MVP now exists in `apps.tenant_apps.dea.services.rate_fixing`: `post_purchase_rate_fixing()` fixes purchase exposure into monetary supplier payable, and `post_sale_rate_fixing()` fixes sale exposure into monetary customer receivable/revenue. Both paths record `RateFixing`/`RateFixingAllocation`, post financial effects through `PostVoucherCommand(DjangoPostingEngine())`, and reduce or close exposure atomically.
- DEA Phase 4 fixed sale backend MVP now exists in `apps.tenant_apps.dea.services.fixed_sale`: fixed sales create INR-only receivable/revenue financial effects through `PostVoucherCommand(DjangoPostingEngine())` and a separate outgoing `CommodityMovement` from the owned/vault commodity account. The service is idempotent by source plus economic payload and keeps metal quantity out of financial currency paths. The next safe DEA slice is unfixed sale backend MVP: commodity issue plus open sale exposure with no false final monetary receivable/revenue before rate fixing.
- DEA Phase 4 unfixed sale backend MVP now exists in `apps.tenant_apps.dea.services.unfixed_sale`: unfixed sales create a posted commodity-intent voucher, outgoing `CommodityMovement`, and open sale `ExposureLine` without `JournalEntry`, `LedgerTransaction`, `AccountTransaction`, or `VoucherLine` rows. Final monetary AR/revenue waits for `post_sale_rate_fixing()`.
- DEA Phase 4 receipt/payment backend settlement MVP now exists in `apps.tenant_apps.dea.services.monetary_settlement`: customer receipts and supplier payments create `PaymentVoucher` records and financial voucher lines through `PostVoucherCommand(DjangoPostingEngine())`. Normal cash/bank settlement is monetary-only and must not create `CommodityMovement`, `ExposureLine`, or `RateFixing` rows.
- DEA Phase 4 karigar issue/receipt backend MVP now exists in `apps.tenant_apps.dea.services.karigar`: karigar issue and receipt create posted commodity-intent vouchers plus immutable `CommodityMovement` rows only. Issue moves metal from owned/vault to karigar custody; receipt moves metal from karigar custody back to owned/vault. It must not create financial journal/account rows, exposure lines, or rate fixings.
- DEA Phase 4/5 metal balance report backend MVP now exists in `apps.tenant_apps.dea.services.metal_balance_report`: `build_metal_balance_report()` wraps commodity position selectors into account rows, commodity totals, and fixed-status totals by commodity account, party, location, fixed status, and as-of date. It uses decimal metal quantities only, excludes synthetic adjustment/loss-gain offset accounts from default totals, and creates no financial rows.
- DEA Phase 4 financial trial balance hardening with commodity records present is complete for the current backend boundary: `ReportsService.trial_balance()` is covered against commodity movements, open exposures, standalone rate-fixing rows, and metal balance report reads affecting financial totals.
- DEA Phase 5 exposure report backend MVP now exists in `apps.tenant_apps.dea.services.exposure_report`: `build_exposure_report()` returns open/partially fixed exposure rows and totals by commodity/side/status from `ExposureLine`, with party, commodity, side, status, as-of, and optional reporting-only valuation support. It creates no financial rows and does not introduce valuation snapshots.
- DEA Phase 5 party account and ledger statement boundary hardening is complete: period close, ledger audit, and account audit are covered so monetary `LedgerStatement`/`AccountStatement` rows remain separate from commodity movements/exposures, which belong in metal/exposure reports. `Balance.get()` now aliases existing currency lookup and `Balance.__str__()` uses an explicit locale so existing audit paths work.
- DEA Phase 5 valuation report hardening is complete: `apps.tenant_apps.dea.services.valuation_report` combines metal balance positions and exposure rows into a read-only valuation report with status totals, explicit missing/unsupported-rate states, and no financial transaction or snapshot side effects.
- DEA Phase 6 first read-only commodity report UI slice is complete: `apps.tenant_apps.dea.views.commodity_reports` exposes metal balance, exposure, and valuation report pages from backend read models, links them from the DEA reports hub, and keeps the slice free of posting/editing workflows.
- DEA Phase 6 commodity report navigation polish is complete: the workspace sidebar and both DEA dashboard variants expose read-only commodity report links under existing accounting visibility. The next safe DEA slice is business-event UI design scaffolding only; do not wire mutation/posting screens until document states, preview behavior, permissions, and correction paths are designed.
- DEA Phase 6 business-event UI scaffold is complete: `/dea/business-events/` is GET-only, lists planned purchase/sale/rate-fixing/settlement/karigar workflows, links only to existing read-only reports, and keeps mutation/posting forms disabled. The next safe DEA slice is to define the business-event form and preview contract before wiring any POST screens to backend services.
- DEA Phase 6 business-event form/preview contract is documented in `docs/implementation/dea-business-event-form-preview-contract.md`. Future event UI should follow the pattern GET form -> read-only preview -> explicit confirm POST, keep preview side-effect free, and wire services only after preview/permission/idempotency behavior is tested. The next safe DEA slice is a fixed-purchase preview-only screen with confirm posting disabled.
- DEA Phase 6 fixed-purchase preview-only screen is complete: `/dea/business-events/fixed-purchase/` collects business facts, validates INR and commodity-account matching, renders side-effect-free accounting/commodity/exposure/inventory impact from `apps.tenant_apps.dea.services.business_event_preview`, and rejects/keeps disabled confirm posting. The next safe DEA slice is a minimal fixed-purchase business-event draft/source boundary before any confirm POST can call posting services.
- DEA Phase 6 fixed-purchase source-draft boundary is complete: `BusinessEventDraft` with tenant migration `0036` stores fixed-purchase source references, event dates, normalized economic payloads, preview payloads, and payload hashes. Fixed-purchase preview POST creates/updates that draft only; confirm posting remains disabled.
- DEA Phase 6 fixed-purchase posting-readiness gate is complete: the preview page now renders a read-only checklist for saved source, preview status, payload hash, open accounting period, authenticated actor, account/ledger/commodity-account mappings, and absence of an existing posted fixed-purchase voucher. It still does not call posting services or create accounting/commodity rows.
- DEA Phase 6 fixed-purchase confirm handoff service is complete: `apps.tenant_apps.dea.services.business_event_posting.confirm_fixed_purchase_draft()` locks the previewed `BusinessEventDraft`, rejects stale previews/readiness blockers, maps the normalized payload into `FixedPurchasePostingPayload`, and calls `post_fixed_purchase()` idempotently.
- DEA Phase 6 fixed-purchase confirm endpoint/result surface is complete: `/dea/business-events/fixed-purchase/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, calls the handoff service, treats duplicate submits as existing success, and redirects to `/dea/business-events/fixed-purchase/<draft_id>/`, which shows business facts, posting status, voucher/journal links, ledger/account rows, and commodity movement rows. The next safe DEA slice is fixed-purchase stale/error UX hardening and draft list/navigation before cloning the pattern to unfixed purchase.
- DEA Phase 6 fixed-purchase stale/error UX and navigation hardening is complete: the business-events dashboard lists recent fixed-purchase drafts/results with posted/not-posted state, and blocked fixed-purchase detail pages link users back to re-preview. The next safe DEA slice is an unfixed-purchase preview-only screen that mirrors the fixed-purchase contract while keeping final monetary payable out of preview/posting until rate fixing.
- DEA Phase 6 unfixed-purchase preview-only screen is complete: `/dea/business-events/unfixed-purchase/` collects supplier party, metal weights/purity, commodity accounts, rate basis, and reporting valuation context; persists an `UNFIXED_PURCHASE` preview draft; and renders read-only commodity receipt plus open purchase exposure impact with no voucher, journal, ledger, account, movement, exposure, rate-fixing, or payment rows. The next safe DEA slice is an unfixed-purchase readiness/detail/navigation gate before enabling any confirm posting.
- DEA Phase 6 unfixed-purchase readiness/detail/navigation gate is complete: unfixed previews now show a read-only readiness checklist, `/dea/business-events/unfixed-purchase/<draft_id>/` shows draft facts, posting status, readiness, commodity impact, and exposure impact, and the business-events dashboard lists recent unfixed-purchase drafts. Confirm posting remains disabled. The next safe DEA slice is an unfixed-purchase confirm handoff service that locks a previewed draft and maps it to `UnfixedPurchasePostingPayload` without adding the UI confirm endpoint yet.
- DEA Phase 6 unfixed-purchase confirm endpoint/result surface is complete: `/dea/business-events/unfixed-purchase/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, calls `confirm_unfixed_purchase_draft()`, treats duplicate submits idempotently, and redirects to `/dea/business-events/unfixed-purchase/<draft_id>/`, which shows the posted commodity-intent voucher, commodity movement, and open exposure rows while still creating no financial journal, ledger, account, voucher-line, payment, or rate-fixing rows.
- DEA Phase 6 purchase rate-fixing preview/readiness screen is complete: `/dea/business-events/purchase-rate-fixing/` selects an open purchase `ExposureLine`, captures fixing date/weight/rate and monetary account/ledger targets, renders side-effect-free monetary payable and exposure-reduction impact, and keeps confirm posting disabled. Tests prove preview creates no new voucher, voucher-line, journal, ledger/account transaction, commodity movement, exposure, rate-fixing, or payment rows.
- DEA Phase 6 purchase rate-fixing source-draft boundary is complete: `BusinessEventDraft.EventType.PURCHASE_RATE_FIXING` with tenant migration `0038` stores rate-fixing source references, fixing dates, normalized economic payloads, preview payloads, and payload hashes. The purchase rate-fixing preview POST creates/updates only that draft/source row and renders a draft-based readiness checklist.
- DEA Phase 6 purchase rate-fixing confirm endpoint/result surface is complete: `/dea/business-events/purchase-rate-fixing/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, calls `confirm_purchase_rate_fixing_draft()`, treats duplicate submits idempotently, and redirects to `/dea/business-events/purchase-rate-fixing/<draft_id>/`, which shows business facts, posting status, rate fixing, voucher/journal links, ledger/account rows, exposure allocation, and no physical commodity movement.
- DEA Phase 6 sale rate-fixing confirm endpoint/result surface is complete: `/dea/business-events/sale-rate-fixing/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, calls `confirm_sale_rate_fixing_draft()`, treats duplicate submits idempotently, and redirects to `/dea/business-events/sale-rate-fixing/<draft_id>/`, which shows rate-fixing, voucher, journal, ledger/account, and exposure-allocation details without physical commodity movement.
- DEA Phase 6 receipt/payment preview-only screen is complete: `/dea/business-events/settlement/` captures customer receipt or supplier payment facts, persists only `CUSTOMER_RECEIPT` / `SUPPLIER_PAYMENT` `BusinessEventDraft` rows, and renders read-only cash/bank, party-account, payment, and commodity/no-commodity impact. Confirm posting remains disabled; tests prove preview creates no voucher, payment voucher, voucher-line, journal, ledger/account transaction, commodity movement, exposure, or rate-fixing rows.
- DEA Phase 6 receipt/payment detail/readiness/navigation gate is complete: `/dea/business-events/settlement/<draft_id>/` shows saved settlement draft facts, posting readiness, accounting impact, payment impact, and explicit no-commodity impact while keeping confirm posting disabled. The business-events dashboard links recent receipt/payment drafts to this detail page.
- DEA Phase 6 receipt/payment confirm handoff service is complete: `confirm_monetary_settlement_draft()` row-locks a previewed `CUSTOMER_RECEIPT` / `SUPPLIER_PAYMENT` draft, rejects stale payload/readiness blockers, maps normalized payload into `CustomerReceiptPayload` or `SupplierPaymentPayload`, and delegates to `post_customer_receipt()` / `post_supplier_payment()` idempotently.
- DEA Phase 6 receipt/payment confirm endpoint/result surface is complete: `/dea/business-events/settlement/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, calls `confirm_monetary_settlement_draft()`, treats duplicate submits idempotently, and redirects to `/dea/business-events/settlement/<draft_id>/`, which shows payment voucher, voucher, journal, ledger/account rows, payment impact, and explicit no-commodity impact.
- DEA Phase 6 karigar issue/receipt preview screens are complete: `/dea/business-events/karigar/` captures issue or receipt custody facts, persists `KARIGAR_ISSUE` / `KARIGAR_RECEIPT` drafts, renders readiness, and shows commodity-only custody impact. Confirm posting remains disabled and no financial, exposure, rate-fixing, or payment rows are created by preview.
- DEA Phase 6 karigar confirm handoff service is complete: `confirm_karigar_movement_draft()` row-locks previewed karigar drafts, rejects stale/readiness-blocked payloads, maps to `KarigarIssuePayload` / `KarigarReceiptPayload`, and delegates to karigar posting idempotently. Tests prove duplicate submit safety and that the service creates one commodity-intent voucher plus one custody `CommodityMovement` with no financial, exposure, rate-fixing, or payment rows.
- DEA Phase 6 karigar confirm endpoint/result surface is complete: `/dea/business-events/karigar/<draft_id>/confirm/` is POST-only and owner/admin/accountant-gated, calls `confirm_karigar_movement_draft()`, handles duplicate submits idempotently, rejects member-role users, and shows the posted commodity-intent voucher plus custody `CommodityMovement` on the karigar detail page.
- DEA Phase 6 completion checkpoint is complete in `docs/implementation/dea-phase-6-business-event-checkpoint.md`. It records the current financial/commodity/exposure/rate-fixing/payment impact matrix for business events, focused verification results, remaining MVP gaps, and the recommendation to start Phase 7 with a cleanup readiness audit.
- DEA Phase 7 cleanup readiness audit has started in `docs/implementation/dea-phase-7-cleanup-readiness-audit.md`. Legacy/accountant DEA surfaces are classified before deletion, direct posting paths are inventoried, and `test_phase7_cleanup_readiness.py` guards key accountant route resolution plus absence of runtime imports from `posting/legacy_direct_write_engine.py`.
- DEA Phase 7 expense-post characterization is complete. `views/expense.py::post_expense_voucher()` is covered for direct-payment idempotency, duplicate journal prevention, and closed-period no-materialization before any route cleanup or facade refactor.
- DEA Phase 7 dead voucher-helper cleanup is complete. `views/voucher.py` no longer defines the old direct materialization helpers; voucher post/reverse remain routed through `PostVoucherCommand(DjangoPostingEngine())` and `reverse_posted_voucher()`, and `test_phase7_cleanup_readiness.py` guards against helper reintroduction.
- DEA Phase 7 accountant permission hardening has a shared helper in `apps.tenant_apps.dea.views.access`. Voucher hub, generic voucher CRUD/post/reverse, payment voucher CRUD, expense voucher CRUD/post, manual journal voucher CRUD, and opening-balance endpoints now require platform staff/superuser, workspace owner, or workspace role `Owner`, `Admin`, or `Accountant`.

## Multi-tenant SaaS Assumptions

The app is workspace-based.

A user can:

- own multiple workspaces
- belong to multiple workspaces
- switch workspace from navbar

Workspace features:

- members
- roles
- invitations
- subscription
- settings

All business data belongs to a workspace/tenant context.

Migration execution should respect the `django-tenants` split: tenant app changes use `migrate_schemas`, and shared app changes use `migrate_schemas --shared`.

## UX Memory

The home dashboard should be action-first:

- Create Sale
- Create Purchase
- Create Loan
- Receive Payment
- Make Payment
- Stock Adjustment
- Commodity Settlement

Every source document should follow a consistent page pattern:

- Overview
- Payments / Settlements
- Inventory Impact
- Commodity Impact
- Accounting Impact
- Attachments
- History / Timeline

Prefer timelines and activity feeds over isolated reports.

The current SaaS UI information architecture audit lives at [ui/saas_information_architecture_audit.md](ui/saas_information_architecture_audit.md). It records the target separation between public/platform pages, authenticated global workspace management, tenant ERP, workspace settings/admin, and a future customer/member portal. Future UI route/template work should use that document as the baseline and proceed incrementally with compatibility aliases.

Phase 2 route/template standardization has begun with compatibility-only naming: `django_project.shared_urlpatterns` now defines service/public/auth/global route groups and keeps the old aggregate export, while templates can extend intent-specific base aliases (`base_public.html`, `base_auth.html`, `base_global.html`, `base_tenant.html`, `base_workspace_settings.html`, `base_customer_portal.html`). Do not remove legacy route inclusion or old layout files until route coverage and redirects are tested.

Phase 2.2 route intent cleanup keeps effective URLs unchanged but makes ownership explicit: `django_project.urls` is the active public-schema URLConf, `django_project.tenant_urls.TENANT_ERP_URLPATTERNS` groups tenant ERP prefixes, and `django_project.public_urls` is a legacy parity URLConf. Route boundary tests live in `django_project/test_route_intent.py`. The next safe SaaS IA slice is Phase 2.3 template layout cleanup, not navigation redesign or route moves.

Phase 2.3 template layout cleanup moved clear first-party layout stragglers to intent aliases without changing URLs or navigation. `django_project/test_template_layout_intent.py` guards low-level layout usage and alias block contracts. Remaining direct `layouts/base.html` usage should stay limited to infrastructure wrappers (`base_public`, `base_auth`, `base_customer_portal`, low-level layout files, allauth/slick wrappers, and legacy `_base`). The next safe slice is Phase 2.4 workspace settings layout separation.

Phase 2.4 workspace settings layout separation moved clear workspace-admin/settings templates to `base_workspace_settings.html` and added no-op `workspace_settings_sidebar` include points in `layouts/management.html`. This does not change URLs or visible navigation. The next safe slice is Phase 2.5 shell render smoke tests before any navigation/sidebar visual changes.

Phase 2.5 shell render smoke tests live in `django_project/test_shell_render_smoke.py` and render synthetic children for the public, auth, global, workspace-settings, and tenant shell aliases. These tests should be kept green before Phase 3 navigation/sidebar changes. The next safe slice is route/template inventory documentation or a similarly non-behavioral cleanup checkpoint.

Phase 2.6 route/template inventory documentation lives in `docs/ui/route_template_inventory.md`. It records current URLConf ownership, route-family ownership, shell aliases, known mixed boundaries, and guard tests. The next safe SaaS IA work is Phase 3 navigation and workspace switcher planning while keeping compatibility routes in place.

Phase 3.1 navigation and workspace switcher planning lives in `docs/ui/navigation_workspace_switcher_plan.md`. The accepted sidebar ADRs still apply: `templates/components/navigation/sidebar.html` remains the live tenant sidebar source of truth, `django_project/navigation.py` is future-only, and the next safe SaaS IA slice is to replace the inline topbar workspace dropdown with the reusable `components/navigation/workspace_switcher.html` partial while preserving current route behavior.

Phase 3.2 workspace switcher reuse is complete: `templates/components/navigation/main_nav.html` includes `components/navigation/workspace_switcher.html` with `workspace_switcher_variant="navbar"`, and the partial keeps its standalone mode for other surfaces. Authenticated global and tenant shell smoke tests cover switcher rendering. The next safe SaaS IA slice is Phase 3.3 settings sidebar extraction into `components/navigation/workspace_settings_sidebar.html`, starting with desktop links before mobile duplication cleanup.

Phase 3.3 desktop settings-sidebar extraction is complete: `templates/layouts/management.html` delegates desktop workspace settings/team/invitation links to `components/navigation/workspace_settings_sidebar.html` with `workspace_settings_sidebar_variant="desktop"`. The mobile management offcanvas intentionally still has inline duplicate links. The next safe SaaS IA slice is Phase 3.4 to add a mobile variant to the same partial and remove the mobile duplicate links.

Phase 3.4 mobile settings-sidebar extraction is complete: `templates/layouts/management.html` delegates mobile workspace settings/team/invitation links to `components/navigation/workspace_settings_sidebar.html` with `workspace_settings_sidebar_variant="mobile"`. The next safe SaaS IA slice is Phase 3.5 account-management sidebar extraction for the remaining duplicated account links in the management shell.

Phase 3.5 account-management sidebar extraction is complete: `templates/layouts/management.html` delegates desktop and mobile account links to `components/navigation/account_sidebar.html` with `account_sidebar_variant="desktop"` or `"mobile"`. The next safe SaaS IA slice is Phase 3.6 workspace-manager sidebar extraction for the remaining duplicated `My Workspaces` and `New Workspace` links.

Phase 3.6 workspace-manager sidebar extraction is complete: `templates/layouts/management.html` delegates desktop and mobile `My Workspaces` / `New Workspace` links to `components/navigation/workspace_manager_sidebar.html` with desktop/mobile variants. The next safe SaaS IA slice is Phase 3.7 management shell wording cleanup and final navigation partial inventory before moving to visual polish.

Phase 3.7 management shell cleanup is complete: `templates/layouts/management.html` has clean ASCII shell comments, obsolete duplicate-sidebar wording is removed, and `docs/ui/navigation_workspace_switcher_plan.md` records the final management navigation partial inventory. The next safe SaaS IA slice is Phase 3.8 management-shell compatibility review before visual polish.

Phase 3.8 management-shell compatibility review is complete: `django_project/test_shell_render_smoke.py` renders an authenticated owner management shell and asserts key labels plus route targets still resolve after partialization. The next safe SaaS IA slice is Phase 3.9 visual-polish checklist for the global/settings management shell before CSS/layout changes.

Phase 3.9 management shell visual-polish checklist lives at `docs/ui/management_shell_visual_polish_checklist.md`. It defines compatibility constraints, visual review criteria, and the Phase 3.10 recommendation before CSS/layout-density changes. The next safe SaaS IA slice is Phase 3.10 first management-shell visual polish pass with route names, labels, partial ownership, and permission behavior preserved.

Phase 3.10 first management-shell visual polish pass is complete: `layouts/management.html` uses restrained neutral control-plane styling, management sidebar partials share `mgmt-nav-link`, mobile links have active-state parity with desktop, and offcanvas styling moved away from inline purple treatments. The next safe SaaS IA slice is Phase 3.11 browser/screenshot review for desktop/mobile overflow and spacing.

Phase 3.11 rendered management-shell review is complete: the generated management shell HTML showed the control-plane shell was constrained by the default `container-lg mt-4` wrapper. `layouts/base.html` now provides a backward-compatible `main_wrapper_class` block, and `layouts/management.html` overrides it with `container-fluid p-0 mt-0`. Local Chrome headless screenshot attempts did not create files in this environment, so the next safe SaaS IA slice is Phase 3.12 reproducible browser/live-server visual smoke setup before more visual polish.

Phase 3.12 reproducible management-shell visual smoke coverage is complete: `django_project/test_management_shell_visual_smoke.py` renders an authenticated owner management shell and guards the full-width wrapper, desktop/mobile management nav classes, active states, and control-plane route safety without new browser dependencies. The next safe SaaS IA slice is Phase 3.13 management-shell CSS extraction to a dedicated static stylesheet without behavior changes.

Phase 3.13 management-shell CSS extraction is complete: `static/css/management.css` owns the management shell styles, `layouts/management.html` loads it through `{% static %}`, and `mgmt_extra_css` remains available. Synthetic shell smoke rendering now overrides staticfiles storage to avoid stale collected-manifest failures for newly added static assets. The next safe SaaS IA slice is Phase 3.14 static asset readiness checks for the new stylesheet.

Phase 3.14 static asset readiness is complete: `findstatic css/management.css --verbosity 2` finds the management stylesheet in project static files, `collectstatic --dry-run --noinput --verbosity 1` succeeds and includes `css/management.css`, and `test_management_shell_visual_smoke.py` guards staticfiles discovery. The next safe SaaS IA slice is Phase 3.15 final Phase 3 navigation/management-shell review and commit preparation.

Phase 3.15 final Phase 3 navigation/management-shell review is complete in `docs/ui/phase3_navigation_management_shell_review.md`. The review confirms route names, labels, permissions, and partial ownership are preserved, records verification commands, and recommends one phase-level commit before starting Phase 4 invitation/team flow cleanup.

Phase 4.1 invitation/team flow cleanup has started with documentation and guard tests only. `docs/ui/invitation_team_flow_cleanup_plan.md` maps incoming invitations as a global account surface, sent invitations/team members as workspace settings surfaces, and records current URL compatibility constraints before any route aliases or behavior changes. `django_project/test_invitation_team_flow_intent.py` guards current route names/paths, shell intent, and the known unbased invite-success template gap.

Phase 4.2 route-intent cleanup is complete without URL breakage: `apps.orgs.urls` now groups workspace manager, account invitation, workspace invitation, team member, and account profile route lists explicitly, then aggregates them in the same compatibility order. `django_project/test_invitation_team_flow_intent.py` guards the grouping and effective route order. The next safe slice is Phase 4.3 copy/heading clarification for incoming versus sent invitations, including existing mojibake cleanup, while keeping route names and form actions unchanged.

Phase 4.3 copy/heading clarification is complete without route or form-action changes. Received invitations are labelled "Invitations for You", sent workspace invitations are labelled "Sent Workspace Invitations", team invite copy consistently says team member/workspace invitation, and known invitation/team mojibake has focused guard coverage. The next safe slice is Phase 4.4 workspace-scoped redirect cleanup, especially the unbased invite-success page and sent-invitation return path.

Phase 4.4 workspace-scoped redirect cleanup is complete without removing compatibility URLs. `team_invite` now redirects to `team_invite_success` with `workspace_id` query context, `invite_success` uses the workspace settings shell and links back to sent invitations in the same workspace context, `team_invitations_list` honors explicit `workspace_id` query context with access checks, and invitation revoke redirects back to the revoked invitation's workspace sent-list context. The next safe slice is Phase 4.5 accept/decline characterization for direct django-invitations accept links versus the custom orgs accept/decline flow.

Phase 4.5 accept/decline characterization is complete. The direct `team_accept_invitation` route still uses `invitations.views.AcceptInvite`; with current settings it confirms on GET, accepts before signup, and redirects to `account_signup`. The `invite_accepted` signal can create membership or pending invitation intent, but it does not select active workspace, emit orgs audit, or redirect to workspace dashboard. The custom `team_invitations` POST flow remains the product-complete path through `control_plane.accept_invitation`. The next safe slice is Phase 4.6 authorization coverage for invite, revoke, role change, remove member, self-leave, and selected-workspace fallback.

Phase 4.6 authorization coverage is complete. `InvitationTeamAuthorizationTests` covers invite access checks, invite role-grant policy enforcement, unauthorized revoke denial, team remove/change-role workspace gates, sole-owner self-leave blocking, and selected-workspace sent-invitation fallback requiring `team_invite`. The next safe slice is to decide Phase 4.7 scope: either add canonical compatibility aliases for account/settings routes or first wrap the direct invitation accept URL with an orgs-owned adapter now that authorization characterization is in place.

Phase 4.7 direct invitation accept adapter is complete. The existing `team_accept_invitation` route path/name now points to `apps.orgs.views.team_accept_invitation`: authenticated matching users use the orgs control-plane accept path, active workspace selection, and workspace-dashboard redirect; unauthenticated users still fall back to `invitations.views.AcceptInvite`; authenticated email mismatches fail closed. Canonical route aliases are deferred until after the Phase 4 set is reviewed and committed. The next safe step is Phase 4 final review and phase-level commit preparation.

Phase 4 final review is complete in `docs/ui/phase4_invitation_team_flow_review.md`. It records compatibility preservation, authorization coverage, verification commands, and deferred canonical route aliases. After commit, the next safe SaaS IA work is either canonical route aliases for account/settings routes or Phase 5 broader authorization cleanup.

Canonical route aliases are phase-reviewed in `docs/ui/canonical_route_aliases_phase_review.md`. Additive aliases now expose `/app/`, `/app/workspaces/`, `/app/workspaces/new/`, `/app/invitations/`, `/app/memberships/`, and `/workspace/<id>/settings/...` paths for workspace settings/team/invitations while preserving existing `/orgs/...` routes and names. `django_project/test_route_intent.py` guards alias resolution and legacy route stability. Management navigation now uses `app_workspaces`, `app_workspace_create`, `app_invitations`, `workspace_settings_home`, `workspace_settings_preferences`, `workspace_settings_team`, `workspace_settings_invite`, and `workspace_settings_invitations` while keeping old route names as active-state compatibility. Workspace-scoped sent-invitation returns now use `workspace_settings_invitations` for invite POST success, invite-success back links, and revoke returns.

Phase 5.1 authorization cleanup is documented in `docs/ui/authorization_cleanup_inventory.md` with guard tests in `django_project/test_authorization_surface_intent.py`. The baseline maps public, global authenticated, workspace settings, tenant ERP, and future customer/member portal authorization surfaces; guards the route-plane split; and records known login-only tenant app gaps before behavior changes. Phase 5.2 added canonical settings path extraction to `SecureWorkspaceMiddleware`, so `/workspace/<id>/settings/...` aliases now participate in path workspace resolution alongside legacy `/orgs/workspace/<id>/...` and `/orgs/company/<id>/...` paths. Phase 5.3 added middleware workspace-required coverage for every current tenant ERP prefix, including `party`, `data-tools`, and `notify-v2`. Phase 5.4 added `apps.tenant_apps.party.access` with Party workspace, permission, action, decorator, and CBV mixin helpers plus focused helper tests. Phase 5.5 converted Party list/detail to the Party view action guard and Party export to the Party export action permission. Phase 5.6 converted Party create/customer-convert to the Party create action guard and Party update to the Party edit action guard. Phase 5.7 converted Party profile-photo, contact-method, and address mutations to the Party edit action guard. Phase 5.8 converted Party identifier, document, and relationship mutations to the Party edit action guard. Phase 5.9 converted Party role add/end and duplicate merge to the Party edit action guard. Phase 5 Party authorization review is documented in `docs/ui/phase5_party_authorization_review.md`. Broad Contact authorization cleanup is intentionally skipped because Party is replacing Contact. Phase 5.10 added `apps.tenant_apps.product.access` with Product workspace, permission, action, decorator, and CBV mixin helpers backed by generic data permissions, and converted product/product type/generated product/variant/product variant catalog paths to Product action guards. Phase 5.11 converted Product stock list/detail/search, transaction/statement lists, split/merge/delete, stock-in/stock-out, physical audit, opening balance import, and import template paths to Product action guards; `stock_select` now reads `?q=` safely for the current route. Phase 5.12 converted Product pricing, price override, image, and attribute views to Product action guards. Phase 5.13 added Rates and Notify shared access helpers and converted rate/rate-source, legacy Notify, and Notify v2 user-facing routes to action guards while keeping the external WhatsApp webhook public. Phase 5.14 closes SaaS IA authorization cleanup for current Party, Product, Rates, Notify, and utility data-tool route groups. DEA/Girvi remain separate domain-specific permission tracks, and the next safe slice is a Phase 5 review/commit checkpoint before Phase 6 onboarding.

Phase 6 onboarding is phase-reviewed in `docs/ui/phase6_onboarding_review.md`. The completed scope includes onboarding inventory, read-only workspace setup checklist service, dashboard checklist card, workspace settings setup page, completion redirects to setup, onboarding workspace creation through orgs control-plane, onboarding team invitations through orgs control-plane, and user-specific setup completion/dismiss state through `WorkspaceSetupState`. Existing `/onboarding/...` URLs remain compatibility entrypoints, setup remains advisory/non-blocking, and the new setup-state migration is shared/control-plane data. The next safe action is to commit Phase 6 as a single phase-level commit, then start Phase 7 modern fintech UI polish.

Phase 7.1 modern fintech UI polish planning is complete in `docs/ui/phase7_modern_fintech_ui_polish_plan.md`, with guard tests in `django_project/test_phase7_ui_polish_intent.py`. Phase 7 starts with management/workspace setup surfaces and keeps routes, permissions, middleware, schemas, and advisory setup behavior unchanged. The next safe SaaS IA slice is Phase 7.2: add a small management/setup visual vocabulary to `static/css/management.css` and apply it to `templates/company/workspace_setup.html` only.

Phase 7.2 workspace setup visual vocabulary is complete: `static/css/management.css` owns setup hero, progress, task, action, and status classes, and `templates/company/workspace_setup.html` uses them without changing canonical setup-state forms, checklist links, settings-shell ownership, or advisory behavior. The next safe SaaS IA slice is Phase 7.3: polish the workspace dashboard setup card using the new vocabulary where practical, while preserving dashboard visibility and dismiss behavior.

Phase 7.3 dashboard setup-card polish is complete: `templates/company/workspace_dashboard.html` loads `css/management.css` and uses the setup hero, progress, task, action, and status classes while preserving `setup_state.should_show_dashboard_card`, canonical setup navigation, dismiss POST behavior, and checklist action URLs. The next safe SaaS IA slice is Phase 7.4: extract repeated setup checklist markup into a shared partial only if behavior remains exactly unchanged.

Route-map clarification: SaaS IA Phase 2 is complete for route/template intent standardization, not for the full target `/w/<workspace_slug>/...` route map in the IA audit. Current canonical control-plane aliases are `/app/...` and `/workspace/<id>/settings/...`; `/w/<workspace_slug>/...` should be a separate future alias/redirect phase. Preferences visibility is now explicit for `Owner`, `Admin`, and platform `Superuser` users through `workspace_settings_preferences`.

Phase 7.4 setup checklist task partial extraction is complete: `templates/components/setup/setup_checklist_task.html` owns repeated setup task/status/action markup, and both `workspace_setup.html` and `workspace_dashboard.html` include it with page-specific heading/id context. The next safe SaaS IA slice is Phase 7.5: review and polish the global workspace selector/workspace-list surface without changing route behavior or membership checks.

Phase 7.5 global workspace selector polish is complete: `templates/company/workspace_home.html` now reads as a workspace manager with summary tiles, active workspace state, canonical create/invitations/settings links, and preserved `workspace_select` switching plus invitation accept/decline POST behavior. The next safe SaaS IA slice is Phase 7.6: public/auth page polish planning and guard tests before visual changes.

Phase 7.6 public/auth route-template inventory and guard tests are complete: `docs/ui/phase7_public_auth_polish_plan.md` records current public pages, allauth paths, django-invitations entrypoints, shell ownership, missing pricing/short-auth aliases, and missing public templates. `django_project/test_phase7_public_auth_intent.py` guards that inventory. The next safe SaaS IA slice is Phase 7.7: first public/auth visual polish pass while preserving current allauth/social-auth/invitation behavior.

Phase 7.7 first public/auth visual polish pass is complete: `static/css/public.css` owns shared public/auth styling, `base_public.html` and `base_auth.html` load it with full-width shell wrappers, `templates/pages/home.html` now presents a product-specific SaaS ERP funnel without inline CSS or remote placeholder imagery, and login/signup/password-reset pages share an auth panel/card layout while preserving allauth/social-auth behavior. The next safe SaaS IA slice is Phase 7.8: render-review public/auth pages and make only focused overflow/spacing fixes if needed.

Phase 7.8 public/auth render review is complete: render smoke coverage now exercises `/`, `/accounts/login/`, `/accounts/signup/`, and `/accounts/password/reset/`. Auth pages no longer crash when a Google client id exists but no django-allauth `SocialApp` is configured; `google_oauth_context` exposes `GOOGLE_OAUTH_ENABLED`, and login/signup templates conditionally render Google auth CTAs. The next safe SaaS IA slice is Phase 7.9: tenant ERP dashboard/navigation density polish without changing business workflows.

Phase 7.9 tenant ERP dashboard/navigation density polish is complete: `static/css/workspace.css` owns tenant shell/sidebar/dashboard classes, `base_tenant.html` loads it, tenant layout/sidebar inline style blocks are removed, and `templates/company/workspace_dashboard.html` uses denser page-header, stat-grid, and quick-action classes while preserving existing routes, permission conditions, setup-card behavior, tenant isolation, and posting workflows.

Phase 7.10 first-pass UI polish review is complete in `docs/ui/phase7_modern_fintech_ui_polish_review.md`. Phase 7 should be treated as UI infrastructure and surface cleanup, not the final high-fidelity fintech redesign. Deeper visual redesign, pricing/short-auth/invitation aliases, missing public templates, and the full `/w/<workspace_slug>/...` target route-map rollout remain separate future work. The next safe SaaS IA action is to commit Phase 7, then start Phase 8 regression consolidation.

Phase 8.1 regression consolidation planning is complete in `docs/ui/phase8_regression_consolidation_plan.md`, with guard coverage in `django_project/test_phase8_regression_consolidation_intent.py`. Phase 8 is a no-runtime-change guardrail phase before pricing/auth aliases, missing public templates, `/w/<workspace_slug>/...`, or deeper redesign work. The next safe SaaS IA slice is Phase 8.2: route boundary regression tests for current aliases, legacy URLs, and intentionally absent future aliases.

Phase 8.2 route boundary regression is complete in `django_project/test_route_intent.py`. Coverage now guards current canonical aliases in both public and tenant URLConfs, legacy allauth/invitation/orgs paths, representative tenant ERP paths, public URLConf tenant exclusion, and intentionally absent future aliases (`/pricing/`, short auth aliases, `/invitations/accept/<key>`, `/w/<workspace_slug>/...`). The next safe SaaS IA slice is Phase 8.3: template/shell regression tests for base-template ownership and static stylesheet contracts.

Phase 8.3 template/shell regression is complete in `django_project/test_template_layout_intent.py`. Coverage now guards shell alias ownership, public/auth `css/public.css`, tenant `css/workspace.css`, extracted management/workspace shell no-inline-style contracts, and known root `layouts/base.html` / `main_nav.html` inline style debt. The next safe SaaS IA slice is Phase 8.4: public/auth render and compatibility tests, including missing-template documentation.

Phase 8.4 public/auth render and compatibility regression is complete in `django_project/test_phase7_public_auth_render_smoke.py`. Coverage now guards renderable public pages, allauth login/signup/password-reset rendering, Google OAuth CTA gating, current allauth route names, current django-invitations `/invitations/accept-invite/<key>` compatibility, invalid invite fail-closed behavior, and documented missing public templates. The next safe SaaS IA slice is Phase 8.5: workspace switching, setup, and onboarding regression tests.

Phase 8.5 workspace/setup/onboarding regression is complete in `django_project/test_onboarding_phase6_intent.py`. Coverage now guards canonical and legacy workspace setup routes, canonical setup-state form targets, membership-safe workspace switching before selected-workspace mutation, safe `next` handling, `WORKSPACE_SWITCH` audit logging, and the presence of focused onboarding runtime regression files.

Phase 8.6 invitation/team regression is complete in `django_project/test_invitation_team_flow_intent.py`. Coverage now guards the presence of focused runtime tests for invite permissions, role-grant policy, revoke denial, team remove/change-role gates, sole-owner self-leave, sent-invitation workspace context, and direct accept adapter behavior; it also guards orgs view/control-plane ownership for accept/revoke/member mutation policy and audit actions.

Phase 8.7 authorization regression is complete in `django_project/test_authorization_surface_intent.py`. Coverage now guards exact tenant ERP prefix coverage, middleware workspace-required coverage, Party/Product/Rates/Notify/utility data-tool guards, Contact's documented legacy gap, the intentionally public Notify v2 webhook, and DEA/Girvi as separate domain-specific permission tracks.

Phase 8.8 regression closeout is complete in `docs/ui/phase8_regression_consolidation_review.md`. The review records completed guard coverage, deferred scope, compatibility findings, verification commands, expected test log noise, and the tests/documentation-only commit boundary. The next safe SaaS IA action is to commit the Phase 8 set, then start a follow-on alias/template phase for `/pricing/`, missing public templates, short auth aliases, `/invitations/accept/<key>`, and the full `/w/<workspace_slug>/...` route-map rollout.

Phase 9.1 public/auth alias-template rollout planning is complete in `docs/ui/public_auth_alias_template_rollout_plan.md`, with guard coverage in `django_project/test_public_auth_alias_template_rollout_intent.py`. Runtime behavior is unchanged: `/pricing/`, short auth aliases, `/invitations/accept/<key>`, missing public templates, and `/w/<workspace_slug>/...` remain deferred. The next safe SaaS IA slice is Phase 9.2: add `/pricing/` and the missing public templates without changing auth aliases or invitation aliases yet.

Phase 9.2 pricing and missing public templates are implemented. `/pricing/` now resolves through `PricingPageView`, and `templates/pages/pricing.html`, `tenant.html`, `cancellation_and_refund.html`, `contact.html`, `help.html`, and `faq.html` render through `base_public.html`. Short auth aliases, `/invitations/accept/<key>`, and `/w/<workspace_slug>/...` remain deferred. The next safe SaaS IA slice is Phase 9.3: add short auth aliases while preserving `/accounts/...` compatibility paths.

Phase 9.3 short auth aliases are implemented. `/login/`, `/signup/`, and `/password/reset/` redirect to the existing allauth `/accounts/...` implementation paths while preserving query strings. `/invitations/accept/<key>` and `/w/<workspace_slug>/...` remain deferred. The next safe SaaS IA slice is Phase 9.4: add the public invitation accept alias to the orgs-owned adapter.

Phase 9.4 public invitation accept alias is implemented. `/invitations/accept/<key>` now resolves as `public_invitation_accept` to the orgs-owned `team_accept_invitation` adapter while the django-invitations `/invitations/accept-invite/<key>` compatibility path remains available. The next safe SaaS IA slice is Phase 9.5: public/auth alias rollout review and commit preparation before the separate `/w/<workspace_slug>/...` route-map phase.

Phase 9.5 public/auth alias-template rollout review is complete in `docs/ui/public_auth_alias_template_rollout_review.md`. The review records completed pricing/templates/auth/invitation aliases, compatibility findings, verification commands, and the commit boundary. The next safe SaaS IA action is to commit this phase, then start separate `/w/<workspace_slug>/...` route-map planning before slug routes are added.

Phase 10.1 workspace slug route-map planning is complete in `docs/ui/workspace_slug_route_map_plan.md`, with guard coverage in `django_project/test_workspace_slug_route_map_intent.py`. Runtime behavior is unchanged and `/w/<workspace_slug>/...` routes remain intentionally absent. The next safe slice is Phase 10.2: choose the slug source, conservatively using `Company.schema_name` as a compatibility slug unless a dedicated immutable `Company.slug` is justified.

Phase 10.2 slug source decision is complete. `/w/<workspace_slug>/...` will initially use `Company.schema_name` as a compatibility slug, with no shared-schema migration in this phase. Do not expose schema names as editable branded slugs yet; defer a dedicated immutable `Company.slug` until rename/branding requirements are clear. The next safe slice is Phase 10.3: add middleware slug extraction by `schema_name` while keeping URL routes absent.

Phase 10.3 middleware slug extraction is complete. `SecureWorkspaceMiddleware` can extract future `/w/<workspace_slug>/...` path candidates through `WORKSPACE_SLUG_PATTERNS` and resolve them by `Company.schema_name`, while ignoring the public schema slug. URL routes are still absent. The next safe slice is Phase 10.4: add minimal slug aliases for workspace dashboard and settings.

Phase 10.4 minimal workspace slug aliases are live. `CANONICAL_WORKSPACE_SLUG_URLPATTERNS` exposes `/w/<workspace_slug>/`, `/w/<workspace_slug>/settings/`, `/settings/preferences/`, `/settings/team/`, and `/settings/invitations/` as redirect aliases to existing id-based dashboard/settings views. Tenant ERP section aliases remain absent. The next safe slice is Phase 10.5: add Party, Girvi loans, Product/inventory, and DEA accounting aliases, skipping Contact.

Phase 10.5 tenant ERP section aliases are live for stable module entrypoints: `/w/<workspace_slug>/parties/` redirects to Party, `/loans/` to Girvi, `/inventory/` to Product, and `/accounting/` to DEA. `/w/<workspace_slug>/contact/` remains absent because Party replaces Contact. Operations, sales, purchase, commodity, and reports remain absent until product targets are selected. The next safe slice is Phase 10.6: move selected navigation links to slug aliases where workspace schema context is reliable.

Phase 10.6 selected navigation cutover is complete. Tenant sidebar dashboard, Parties, Girvi, and Product links now target slug aliases, and workspace settings sidebar home/preferences/team/sent-invitations links use slug aliases where `ew.schema_name` is present. Setup, invite member, subscription, reports, business events, commodity, accounting tools, rates, notifications, and data tools remain on existing routes until dedicated aliases are introduced. The next safe slice is Phase 10.7 review/verification and phase-level commit.

Phase 10.7 workspace slug route-map review is complete in `docs/ui/workspace_slug_route_map_review.md`. The phase added the first live `/w/<workspace_slug>/...` aliases, kept compatibility URLs available, and deferred remaining operations/sales/purchase/commodity/reports/settings-detail/portal routes. After commit, choose targets for remaining slug routes or start customer/member portal IA.

Phase 11.1 deferred workspace slug target selection is complete in `docs/ui/workspace_slug_deferred_targets_plan.md`. Operations, sales, and purchase target `dea_business_events_dashboard` because the old sales/purchase runtime apps were removed; commodity targets `dea_commodity_list`; reports targets `dea_reports_hub`; profile, billing, and accounting target `workspace_update`, `subscriptions:dashboard`, and `dea_chart_of_accounts`; roles and numbering are interim targets (`workspace_settings_team`, `girvi:girvi_series_list`); modules and security should stay absent until real workspace-owned screens exist. Phase 11.2 should implement only the safe redirect aliases before the interim or new-screen settings work.

Phase 11.2 safe deferred workspace slug aliases are implemented. Operations/sales/purchase redirect to `dea_business_events_dashboard`, commodity redirects to `dea_commodity_list`, reports redirects to `dea_reports_hub`, settings/profile redirects to `workspace_update`, settings/billing selects the workspace then redirects to `subscriptions:dashboard`, and settings/accounting redirects to `dea_chart_of_accounts`. Contact plus settings roles/modules/numbering/security remain absent until separate decisions.

Phase 11.3 interim workspace settings slug aliases are implemented. Settings/roles redirects to `workspace_settings_team`; settings/numbering redirects to `girvi:girvi_series_list`. Settings/modules and settings/security remain absent until real workspace-owned modules and security/audit screens are designed.

Phase 11.4 workspace modules/security settings screens are implemented. `workspace_settings_modules` renders a read-only installed-module map, `workspace_settings_security` renders workspace audit/security activity from `AuditLog`, and slug aliases redirect to these workspace-owned pages. Do not redirect workspace security to account-level allauth/security settings.

Phase 11 final review is complete in `docs/ui/workspace_slug_phase11_review.md`. The target `/w/<workspace_slug>/...` tenant and workspace-settings route map is live except Contact, intentionally skipped for Party, and the customer/member portal route map, which should be the next separate IA phase.

Phase 12.1 customer/member portal planning is complete in `docs/ui/customer_portal_phase12_plan.md`; the later Party Phase 10 runtime slice now supersedes its route-absent checkpoint.

Phase 12.2 customer/member portal identity design is complete in `docs/ui/customer_portal_identity_phase12.md`. Use Party as the portal customer identity, backed by explicit tenant `PartyPortalAccess`. Do not infer access from email/phone alone. `apps.tenant_apps.party.portal_access.resolve_portal_identity()` now resolves active grants for live tenant portal routes.

Phase 12.3 customer/member portal selector contracts are implemented in `docs/ui/customer_portal_selector_contracts_phase12.md`. `apps.tenant_apps.party.portal_selectors` validates `PortalIdentity` first and then returns Party-filtered dashboard, loan, invoice, payment, document, and statement summaries.

Phase 12.4 customer/member portal shell/navigation is complete in `docs/ui/customer_portal_shell_phase12.md`. `base_customer_portal.html` owns a portal-only topbar, identity display, enabled tenant portal nav, `portal_content`, and `css/customer_portal.css`; it does not include tenant ERP, workspace-admin, or public marketing navigation. Tenant `/portal/...` routes are live, and public `/portal/...` remains absent.

Phase 13.1 tenant route canonicalization baseline is complete in `docs/ui/tenant_route_canonicalization_phase13_plan.md`. Important correction: the tenant `/w/<workspace_slug>/...` route-map aliases from the SaaS IA target are available, but they are not full canonical replacements. Legacy tenant roots such as `/dea/`, `/party/`, `/girvi/`, and `/product/` remain active, and many slug entrypoints still redirect to them. Phase 13.2 should convert remaining visible sidebar/dashboard top-level tenant links to existing slug aliases while keeping legacy roots active.

Phase 12 customer/member portal closeout in `docs/ui/customer_portal_phase12_review.md` is superseded by Party Phase 10 read-only portal runtime access. Tenant `/portal/...` routes now require active `PartyPortalAccess`, database-backed identity lookup, implemented Party-scoped selectors, and cross-party denial tests. Do not add portal mutation routes without a separate design/test slice.

Phase 13.2 tenant visible entry-link canonicalization is complete. Tenant sidebar Business Events, Financial Reports, and Commodity Master now target `workspace_slug_operations`, `workspace_slug_reports`, and `workspace_slug_commodity`; the workspace dashboard DEA Dashboard quick action targets `workspace_slug_accounting`. Legacy `/dea/`, `/party/`, `/girvi/`, `/product/`, and other tenant roots remain active. Phase 13.3 should direct-render slug entry wrappers one low-risk module at a time.

Phase 13.3 tenant route direct-rendering is complete for the low-risk top-level entrypoint set. `/w/<workspace_slug>/parties/`, `/inventory/`, `/loans/`, and `/accounting/` preserve the slug URL and delegate to existing Party list, Product home, Girvi dashboard, and DEA home views. DEA operations/sales/purchase/commodity/reports and deep app routes remain compatibility redirects or legacy routes until Phase 13.4 planning.

Phase 13.4 tenant deep-link canonicalization planning is complete in `docs/ui/tenant_deep_link_canonicalization_phase13_4_plan.md`. Do not remount nested tenant app URLConfs under `/w/<workspace_slug>/...` yet. The recommended deep-link order is Party, Product/Inventory, Rates, Notify/Notify V2, Data Tools, Girvi, then DEA. Phase 13.5a should start with Party read-only deep aliases as redirects first.

Phase 13 is complete in `docs/ui/tenant_route_canonicalization_phase13_review.md`. Party read-only deep aliases now exist as redirects for create, detail, edit, and merge. Nested Party mutation aliases remain absent. The next route-canonicalization phase should start with Party direct-render deep aliases and internal link migration before moving to Product/Inventory, Rates, Notify, Data Tools, Girvi, and DEA.

Phase 14.1 starts the next route-canonicalization phase in `docs/ui/tenant_party_deep_link_canonicalization_phase14.md`. Party read-only deep aliases for create, detail, edit, and merge now direct-render existing Party views under `/w/<workspace_slug>/parties/...`; Party internal links, successful form redirects, nested mutation routes, and legacy-root removal remain separate follow-up work.

Phase 14.2 low-risk deep-link canonicalization is complete. Visible Party GET links now prefer slug routes when `user_workspace` exists, and read-only aliases are live for Product/Inventory products, stock, stock audit, transactions, statements; Rates and rate sources; Notify notifications and notice groups; and Data Tools export. Product/Rates/Notify/Data Tools mutation routes, nested Party mutations, Party success redirects, Girvi, DEA, and legacy-root cleanup remain follow-up work.

Phase 15 compressed Girvi/Loans route canonicalization is complete in `docs/ui/tenant_girvi_route_canonicalization_phase15.md`. Read-only loan list/detail/tab/PDF/report aliases are live under `/w/<workspace_slug>/loans/...`; loan create/update/delete, repayment, release, custody, lifecycle transition, operations-console retry, document/template/storage mutations, DEA, and legacy-root cleanup remain follow-up work.

Phase 16 compressed DEA/Accounting route canonicalization is complete in `docs/ui/tenant_dea_route_canonicalization_phase16.md`. Top-level operations/sales/purchase/commodity/reports slug aliases direct-render existing DEA views, and read-only aliases are live for accounting chart/accounts/ledgers/transactions/reports/vouchers/payments/expenses/journal-entry-vouchers/periods/reconciliation/commodity details. DEA posting, business-event confirm, period mutation, reconciliation import/match, opening balance, commodity setup, and legacy-root cleanup remain follow-up work.

Phase 17 legacy-root compatibility closeout is complete in `docs/ui/tenant_legacy_root_compatibility_phase17.md`. Legacy roots (`/party/`, `/product/`, `/girvi/`, `/dea/`, `/rates/`, `/notify/`, `/notify-v2/`, `/data-tools/`) remain active compatibility routes. The compressed SaaS IA route-canonicalization work is complete; remaining route work should be module-specific POST/HTMX/success-redirect migration or customer portal runtime access, not a blanket legacy-root redirect.

## Navigation Memory

Main sidebar direction:

- Home
- Activities
- Parties
  - Customers
  - Suppliers
- Operations
  - Sales
  - Purchases
  - Loans
  - Receipts
  - Payments
  - Commodity
- Inventory
- Accounting
- Reports
- Settings

## Tech Preferences

Backend:

- Django
- PostgreSQL
- HTMX
- Bootstrap 5
- `django-template-partials` where useful

Prefer server-rendered UI with HTMX partial updates. Avoid heavy SPA complexity unless clearly necessary.

## Current Active Work

Loans configurable printing follows
`docs/plans/loans-configurable-documents-plan.md`. LPD0/LPD1 are complete:
accepted ADR `2026-08-06-loans-versioned-configurable-documents.md` requires
exact artifact retention for official issues, and all six document paths now
project source facts into immutable schema-versioned `DocumentPayload` fields
and sections with allow-listed binding keys before fixed rendering. Keep fixed
PDFs as the safe fallback; future layouts are Loans-owned immutable published
revisions with workspace/license/series assignment. Do not import Girvi's
`LoanTemplate`, `TemplateFrame`, or model-aware renderer. LPD2, the
database-free constrained layout schema/renderer, is next; schema/editor work
comes later.

LPD2 is complete in `loans.documents.layouts`, `assets`, and
`loans.documents.renderers`: strict schema-v1 validation, mandatory per-kind
bindings, starter ticket/release layouts, canonical hashes, non-official
preview marking, pagination, and copy/duplex rendering are implemented without
models. Tenant-bound validated PNG/JPEG/PDF inputs, image/logo and QR blocks,
PDF/image backgrounds, asset hash evidence, and bundled Tamil Unicode font
coverage complete LPD2A. Missing/corrupt/duplicate/cross-workspace assets fail
closed. LPD3 tenant revision/assignment/issue models and atomic publication
services are next.

LPD3 is complete in tenant migrations `loans.0017` and `loans.0018`.
`LoanDocumentLayout`, immutable `LoanDocumentLayoutRevision`, revision-bound
`LoanDocumentAsset`, scoped `LoanDocumentLayoutAssignment`, and immutable
exact-byte `LoanDocumentIssue` evidence are live in all local schemas. Atomic
services own revision allocation/publication, assets, assignment replacement,
specificity resolution, retirement, idempotent official issue, and linked
regeneration with public workspace audits. Database partial uniqueness guards
active scoped assignments and official source issues. LPD4 loan-ticket pilot
UI is next.

LPD4 loan-ticket pilot is complete. Owner/Admin routes under
`/loans/setup/documents/` own starter creation, schema-v1 draft editing,
validated assets, preview/test print, clone, publish, scoped assignment, and
retirement. The existing ticket URL resolves published layouts and returns an
immutable exact-byte official issue; reprints retain the original issue even
after defaults change. `?renderer=fixed` is the explicit administrator-only,
audited recovery path. LPD5 subsequently extended this facade to repayment,
release, renewal, and auction documents without weakening each kind's
mandatory field registry.

LPD5 is complete. All six current Loans PDFs—ticket, repayment receipt,
release, auction notice, auction recovery, and renewal—support versioned
starter/custom layouts, specificity resolution, immutable official issues,
and audited fixed recovery through their existing URLs. Each document keeps
its own mandatory registry and immutable projection/eligibility boundary.
LPD6 then took on operational diagnostics, artifact/asset integrity checks,
sanitized layout-pack portability, and representative printer acceptance.

LPD6 engineering is complete: setup diagnostics and tenant command
`check_loan_document_integrity --fail-on-findings` verify layout, asset, issue,
scope, and lineage integrity; `jcl1` currently has zero findings. Sanitized
layout ZIP export/import contains only schema-v1 JSON and hashed validated
assets and imports only as an unassigned draft. The physical printer matrix in
`docs/implementation/loans-configurable-document-operations.md` is the sole
remaining LPD6 acceptance gate and requires a real operator; do not infer it
from automated or on-screen PDF checks.

The active design track is Girvi event-driven DEA posting. See [plans/active](plans/active.md) and the archived full spec at [GIRVI_EVENT_DRIVEN_DEA_POSTING_SPEC](archive/girvi/GIRVI_EVENT_DRIVEN_DEA_POSTING_SPEC.md).

DEA Phase 7 cleanup readiness audit has started, expense-post characterization is complete, dead voucher helper definitions have been removed, and the first accountant permission boundary hardening is complete. The next recommended DEA slice is navigation cleanup: normal staff should be guided to business events and reports, while accountant/admin users retain manual voucher, payment, expense, journal, opening-balance, period, and diagnostic routes.

Loans operational parity OP6 is complete. All eight pilot report/statement projections use the canonical PawnLoan selector/balance fold, and CSV/XLSX/PDF exports only format those results. The Loans Party statement combines current positions with immutable PawnLoan events and excludes Girvi rows. Fixed loan-ticket recovery produces Original and Duplicate signed pages with one verification identity; configurable pilot layouts must select their existing Original/Duplicate composition. The next Loans step is the operator parity pilot, not another report-count parity build.

LPD7.1 adds print-profile models, tenant migration `loans.0037`, validated
schema-v1 contracts, immutable publication, audited assignment, and `Series ->
Workspace -> built-in` resolution. LPD7.2 adds exact compatibility contracts
for all eight sheet modes and the older sequential A4/A5/Letter copy modes,
plus migration `loans.0038` for immutable issue profile name/version/hash/source
evidence and profile-aware integrity diagnostics. New configurable ticket
issues initially recorded the `LEGACY_LAYOUT` profile actually used;
historical issues were not backfilled. LPD7.3 now makes resolved profiles the
default physical packaging authority for new configurable ticket issues,
while embedded `copy_mode`/`sheet` remains readable through explicit audited
compatibility recovery. Active loan-ticket profile assignment must include
Original and Duplicate, resolved pairs must be compatible, and the real
physical printer matrix remains an operator gate. LPD7.4 exposes the existing
contracts through Owner/Admin list/create/edit/clone/publish/assign/retire and
resolved preview/test-print screens. Assignment validates every affected
Series before changing workspace or Series scope. The issued-document ledger
shows immutable layout/profile provenance and returns exact stored PDF bytes.
The subsequent new-authoring cleanup adds layout schema v3 with neutral logical
surfaces, removes physical composition controls from new Flow/overlay drafts,
and preserves schema-v1/v2 compatibility without mutation.

Operator parity-pilot preparation is documented in `docs/implementation/loans-girvi-operator-parity-pilot.md`. `jcl1` starts with 8 Loans PawnLoans and 8 Girvi GivenLoans, explicit `DEFERRED` accounting, zero document-integrity findings, and no Loans storage hierarchy, verification session, or operational notice. The official clock is stopped while accounting/Girvi runtime work is uncommitted. A combined 191-test preflight did not complete within ten minutes and exposed a stale implicit-DEA test; its focused scenario passes when DEA is explicit. DEA/Loans/Girvi migration drift checks are clean. Do not claim a cross-product pass until smaller suites finish on a reproducible checkpoint.

## Documentation Memory

- Canonical docs live under `docs/`.
- Historical source docs live under `docs/archive/`.
- Accepted architecture decisions live under `docs/adr/`.
- Every markdown file under `docs/` should start with frontmatter.
- Every doc should link back to `README.md` where practical for navigation.
