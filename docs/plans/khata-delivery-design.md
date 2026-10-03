---
status: active
owner: loans
updated: 2026-10-01
tags: [loans, khata, architecture, delivery, planning]
related: [khata-agreements.md, khata-screen-review.md, ../adr/2026-10-01-khata-agreement-design.md, ../architecture/control-plane-contracts.md]
---

# Khata implementation design and delivery sequence

The owner explicitly authorized the local foundation/calculator slice after
confirming D1-D5 and rounds 10-11. That first backend slice is implemented and
tested; see the [checkpoint](../implementation/khata-foundation.md). Operational
screens and production activation remain pending. The subsequent
[opening slice](../implementation/khata-opening.md) adds custody, approval,
photos, valuations, policies and staged withdrawals. The subsequent
[collection slice](../implementation/khata-interest-collection.md) adds frozen
monthly charges and oldest-due receipts. The
[agreement-change slice](../implementation/khata-agreement-changes.md) adds approved
limit/rate activation and financial reductions. The
[custody/settlement slice](../implementation/khata-custody-settlement.md) adds grouped
exchanges, reduction returns, closing partial interest, financial settlement and
actual handover completion. The [correction slice](../implementation/khata-corrections.md)
adds bounded whole receipt compensation and unhanded exchange cancellation;
unsupported correction types and integration remain pending.

The [concrete technical design](../architecture/khata-technical-design.md) now
provides candidate fields/constraints, separate numbering, lifecycle and permission
mapping, the KHATA-1 calculation contract, transaction/handover safeguards and
test cases. The checklist below remains open until its implementation or final
review is complete; writing the specification does not satisfy runtime gates.

## First-release scope and implementation checklist

Owner-confirmed scope, consolidated through discussion round 11:

| Included | Explicitly outside the first release |
| --- | --- |
| New khatas, all recorded collateral, approved terms and first actual withdrawal | Historical digital/paper-account imports or silently carried opening debt |
| Workspace-owned khata series, independent or optionally licence-associated; KH00001 is the default example | Reusing/resetting ordinary-loan sequences or changing a series' licence association after its first account number |
| Existing authorised loan approvers approve opening and limit/rate revisions | Additional owner-only approval for these actions |
| Today-dated routine operations, repeated withdrawals, deposits and same-metal grouped exchanges | Unrestricted backdating; earlier transactions need a separately reviewed workflow |
| Confirmed simple interest, periodic collection, D1-D5, reductions/returns and full settlement | Added charges, penalties, compound interest, advance/excess payment credit handling |
| Private media, receipts/history, integrated summaries, correction safeguards and native-data recovery | Funding/repledging or using ordinary-loan workflows as substitutes |

Paper khatas may exist, but the owner selected starting new agreements rather
than importing their history. New terms and recording collateral are supported;
they do not prove fresh cash was handed out. The first withdrawal must record
actual new money. If someone later needs existing paper principal carried into
Rokkad, that is a separate opening-balance requirement, not permission to fake a
new payout or bypass the confirmed initial scope. Recording the same physical
collateral also requires actual custody evidence, not an invented new receipt.

Consolidated engineering checklist. Foundation progress is recorded separately;
the full-release items remain open until their entire boundary is complete:

- [x] Add three foundation records, forced RLS/parent guards, registry coverage
  and immutable draft/agreement evidence.
- [x] Add both series modes, atomic permanent numbering, idempotent draft services,
  association freeze and attributed cancellation.
- [x] Implement and test the pure KHATA-1 calculator and draw-position helpers.
- [x] Add immutable receipt/photo/approval/withdrawal sources, current valuation,
  owner policy revisions, first-payout activation and canonical opening balances.
- [x] Finalize completed monthly charges and exact segments; receive partial
  interest against oldest dues with immutable allocations, receipt-aware balances,
  permissions, atomic retries/concurrency and restricted-role guards.
- [x] Activate approved limit/rate changes with exact interest splits and formal
  principal reductions, preserving anniversaries, prior charges and non-revolving
  entitlement.
- [x] Add typed exchange/reduction reservations, same-metal valuation/policy
  guards and actual handovers; reserved items cannot back further borrowing.
- [x] Collect full closing debt, including annual unbilled/partial interest,
  preserve the first-month minimum, stop interest separately from custody, and
  close only after actual handovers, with isolation/retry/concurrency guards.
- [x] Add bounded administrator/capability-checked correction sources for whole
  receipts and unhanded exchanges, immutable history, active membership reuse,
  dependency refusals and restricted-role/retry/concurrency verification.

- [ ] Finalize explicit khata schema, state/hand-over mapping and versioned
  calculation contract from the confirmed rules; resolve the annual leap-day edge.
- [ ] Implement workspace-owned numbering for both independent and associated
  series, association freeze, and existing approval authority.
  Keep payout/receipt/custody permissions checked independently of approval.
- [ ] Review implemented current-date/valuation and bounded correction contracts,
  unsupported earlier-entry/complex corrections and their pilot acceptance.
- [ ] Add workspace ownership, parent consistency, forced RLS, immutable evidence,
  registry coverage and an additive owner-only migration plan.
- [ ] Implement the pure calculator, entitlement and canonical balance selectors.
- [ ] Implement all opening/servicing/revision/reduction/settlement commands,
  including retry/concurrency guards and pending physical handover completion.
- [ ] Add reviewed UI, private media and document contracts; extend shared summaries
  without changing ordinary-loan contributions or borrowing their economics.
- [ ] Prove native khata backup/export/restore scope. Historical import remains
  excluded; ordinary history import must not accidentally accept a khata payload.
- [ ] Run focused and existing flexible-loan regression/isolation checks, review
  fictional statements/receipts, then prepare a named pilot and recovery plan.

Foundation completion does not satisfy the full-release boxes above. Resolve the
remaining technical boundaries before their workflows are enabled; do not launch
a partial servicing system. Local implementation does not enable production.

## Recommended boundary

Add khata-specific records and workflows inside the existing Loans app. Keep
the same workspace navigation, Party identity and operational reporting. Do not
build another app, a general lending framework or a new accounting subsystem.

Ordinary PawnLoan is not an interchangeable storage container for khata:

| Existing evidence | Implication for khata |
| --- | --- |
| [Pawn disbursal](../../apps/tenant_apps/loans/services/pawn_disbursal.py) returns the existing result for an ACTIVE loan and rejects another unreversed disbursal. | Repeated khata withdrawals need their own source-event workflow. Do not weaken the ordinary duplicate-disbursal guard. |
| [Collateral and accrual models](../../apps/tenant_apps/loans/models/core.py) connect item principal allocations and interest lines to PawnLoan. | Khata interest uses the agreed limit/rate while collateral changes. Do not create artificial per-item principal to make it fit. |
| [Obligation models](../../apps/tenant_apps/loans/models/obligations.py) require a PawnLoan schedule and maturity date. | Open-ended khata needs recurring dated interest obligations without a fictitious principal maturity. |
| [Media models](../../apps/tenant_apps/loans/models/media.py) link photos and labels to PawnCollateralItem. | Reuse rendering/storage services only where compatible; photo ownership, labels and custody require explicit khata relationships. |
| [Document models](../../apps/tenant_apps/loans/models/documents.py) retain existing loan document contracts. | Reuse layout/PDF primitives, but introduce explicit khata payload/issue support; do not pass a khata ID as a PawnLoan ID. |
| [Loan access](../../apps/tenant_apps/loans/access.py) resolves WorkspaceAccess and has action/setup/owner boundaries. | Use the same authority and action system; resolve each action for the actual workspace. No separate khata role system. |

Recommendation: introduce a small set of explicit Django models/services scoped
to khata. Final model names and table grouping follow the approved contract.
Avoid generic foreign keys and broad refactoring of all existing loan models.
The proposed boundary must be accepted in the ADR before schema work begins.

## Existing flexible-loan compatibility requirement

The owner specifically requires existing flexible lending in JCL, JSK and
Lakshmi to remain unchanged. "Within Loans" means a distinct khata offering in
the same application area, using the same borrower identity and workspace access.
It does not mean reusing or replacing the flexible product or converting loans.

- Do not change current flexible product versions, workspace/licence/series
  economics, existing approval/disbursal snapshots, repayments, interest,
  collateral, account numbers or issued documents.
- Ordinary new flexible loans must continue to resolve their current rules.
  In particular, do not apply khata's monthly-only input, simple interest,
  first-month floor or exchange controls to ordinary loans.
- Shared borrower/directory/dashboard changes must preserve ordinary-loan
  contributions exactly, then add labelled actual khata balances once. Shared
  infrastructure does not mean shared calculation rules.
- Build baseline fixtures for each workspace's flexible policies, including
  JSK WH's approved started-week treatment, plus ordinary approval, disbursal,
  repayments, release/renewal and exact reprints. Compare before/after results.
  Also test borrowers with both account kinds and verify number-space isolation.
- Review additive migrations for unintended existing-row/product changes and
  verify policy/snapshot/document preservation in the candidate release.

This is a release requirement, not a claim that future code is already verified.
The first slice changes only the khata foundation and model registry integration.
No ordinary-loan workflow or production data changes accompany it.

## Records and their responsibilities

The groups below describe required facts, not a commitment to one table per row.

| Record group | Essential facts and constraints |
| --- | --- |
| Account | Workspace, Party, khata series with optional same-workspace licence association, stable account number, opening date/anniversary, lifecycle, current revision reference. No fixed maturity. No unsupported principal before a withdrawal. |
| Agreement revisions | Effective date and ordering, limit, monthly rate with explicit unit, payment frequency, LTV, calculation contract, prior revision, actor/reason and agreement evidence. Completed revisions are immutable. |
| Operational policy revisions | Owner's exchange and overdue warn/block choices, effective change and actor. Operations use current policy and record which version they applied. Contractual economics remain agreement evidence. |
| Financial events | Withdrawals, interest charges/payments, principal paid on reductions/settlement, compensating corrections and source links. Actual principal comes from advances less principal settlement. |
| Interest periods and allocations | Monthly calculation segments and their source revisions, monthly/annual due grouping, paid allocations and remaining dues. Unique period identities prevent duplicate charges. Unpaid interest never becomes principal. |
| Collateral and valuation | Stable item identity, metal, quantity/weights/purity, photos, original facts and later dated valuation evidence. No forced allocation of the agreed limit across items. |
| Custody and exchanges | Received/returned items, same-metal groups, storage movement, linked incoming/outgoing events, warnings, before/after coverage, actor/time and handover evidence. Completed exchanges preserve old items. |
| Documents and audit | Agreement/revision, payout, payment, exchange and settlement receipts; immutable bytes/hash and source links. Statements are separate dated reports. |

All workspace-owned rows need direct non-null ownership, matching parent
ownership constraints, forced RLS, registry coverage and restricted-role tests.
Protect completed evidence against direct update/delete, not only form editing.
Use ordinary relational constraints and explicit compensating workflows.

## Calculation contract

Create a pure khata calculator before mutating workflows. It accepts the opening
anchor, effective agreement revisions, period/settlement date and prior immutable
evidence. It returns explainable segments, period totals and due grouping.

Confirmed: monthly rate units, simple interest, limit-based calculation, a full
first-month floor, anniversary periods, actual-period day fractions, dated rate
and limit changes, and no automatic principal maturity. Monthly calculation and
annual collection remain distinct.

Confirmed D1 defines day boundaries/rounding and D2 the one-time opening minimum
across revisions. Routine operations are today-dated; annual leap-day handling
and compensating correction mechanics still need specification. A later contract
version must preserve historic interpretation.

Persist completed charges once per unique period. Quotes for incomplete periods
are read-only. Generate overdue views as of a requested date, including periods
that elapsed without someone visiting the account; do not make delinquency depend
on a user opening the page. Finalization must be idempotent, with a bounded
catch-up operation using the same calculator. Job scheduling is implementation
detail, not permission to silently send customer notifications.

Track remaining drawing entitlement independently from principal outstanding.
D3 defines its update at limit amendments. Collateral-backed availability can
be zero while unused entitlement remains positive. Annual bills and borrower
totals must never treat unused entitlement as cash advanced or debt outstanding.

## Mutating workflow pattern

Each command should receive the actual workspace, authorized actor, source data
and stable retry identity. Resolve authority, lock the account and affected rows,
check that reviewed versions are still current, recompute eligibility, append
the source evidence and return the completed operation identity. Retry returns
that same operation, not a second payment, number or movement.

| Operation | Required result |
| --- | --- |
| Open and first withdrawal | Approved terms, accepted initial collateral, real payout evidence and opening interest anchor agree. No active interest clock without its source withdrawal. |
| Later withdrawal | Within unused entitlement and post-payout actual-principal LTV; also obey overdue block mode. Recheck under lock so simultaneous requests cannot overspend. |
| Exchange | Same-metal grouping and physical readiness are mandatory. Current warning policy can permit value/LTV shortfalls; capture them, never convert them to cash debt. |
| Rate/limit revision | New effective agreement evidence, unchanged number/anniversary, dated calculation segments. A limit change itself does not pay cash. |
| Reduction with return | Record required principal repayment and validate retained collateral against post-repayment principal. A failed coverage check blocks the return even in exchange warning mode. Clear due/overdue interest under confirmed D5, retaining unbilled accrued interest on schedule. |
| Interest receipt | Date/amount/payment evidence and oldest-due-first allocations under confirmed D4; no implicit principal reduction. Advance/excess payments are deferred initially. |
| Settlement | Actual principal and applicable interest settled, unused entitlement ends, all actual custody outcomes recorded. A failure to hand over collateral stays visible. |
| Correction | Link a compensating event, identify later dependent operations, preserve original evidence and refuse an unsafe partial reversal. |

An atomic database transaction cannot prove money physically changed hands or
items were physically returned. Record those facts explicitly. A payment can be
recorded while handover remains pending; the UI must not label everything fully
closed prematurely. Design repeatable completion of pending custody steps.

Do not add hidden owner approval to warning-mode exchange. Conversely, warning
mode does not bypass permissions, workspace availability, same-metal matching,
actual custody or mandatory withdrawal/reduction-return coverage.

## Integration work required for a usable release

| Surface | Acceptance expectation |
| --- | --- |
| Party detail and borrower outstanding | Include actual khata principal and appropriate interest totals once, with a clear khata label and link. Exclude unused limits. |
| Loans list and dashboard | Explicit account kind, distinct financial totals, overdue-interest count, paginated lists, no artificial maturity alerts. Preserve existing loan selectors. |
| Collateral directory and private media | Include khata item ownership, held/returned state, labels, storage and authorized photo access. Register retained files with storage inventory. |
| Licence/series and numbering | Workspace-owned independent and licence-associated khata series are confirmed. Allocate unique khata numbers across the workspace; freeze association after first issued account number. Finalize collision-proof allocation before migration; never alter ordinary-loan counters or assume an unused sequence. |
| Documents | Agreement, revisions, withdrawal/interest receipts, exchange/reduction-return and settlement evidence; exact reprints and fictional long-text PDF checks. |
| Notifications | Existing Loans-owned intent and Notify delivery boundaries; no automatic mail/SMS/WhatsApp activation in this project. |
| Export/restore | Versioned native khata evidence covering revisions, principal, entitlement, dues, allocations, photos/documents and custody. Prove restore scope; historical/paper import is excluded and ordinary-loan import does not support khata. |
| Statutory/default/funding operations | Funding/repledging is outside first release. Map statutory/default boundaries explicitly or show unsupported. Never route through pawn auctions or renewals merely because an ID exists. |

## Phased delivery after decisions and implementation authorization

| Stage | Concrete output | Completion gate |
| --- | --- | --- |
| 0. Design closure | Confirmed D1-D5 and first-release scope; finalize schema, permission/sequence mapping, edge cases, document inventory and supported/deferred scenarios | Accepted architecture and concrete technical design; separate instruction to implement |
| 1. Evidence and calculator | Additive models, migration/RLS/immutability, pure calculator and test fixtures | Restricted-role isolation, exact interest boundaries, entitlement and historic-evidence tests pass |
| 2. Complete servicing workflows | Opening, repeated withdrawals, interest receipt, exchange, limit/rate revision, reduction/return, settlement and supported corrections | End-to-end fictional accounts and concurrency/retry cases pass; no stranded debt/custody states |
| 3. Operator interface and integration | Reviewed screens, borrower/dashboard totals, private media, documents, export/restore and accessible error states | UI/financial reconciliation, exact reprints, restore and ordinary-loan regressions pass |
| 4. Named workspace pilot | Backup, additive owner-only migration, verified candidate, restricted runtime, monitored reviewed activation | Owner accepts the named pilot and operational examples; no automatic broad enablement |

These are development stages, not separately usable production releases. Do not
enable creation of real khatas after stage 1 while settlement/corrections are
missing. No schedule or delivery-date promise is made before design closure.

## Verification and release safeguards

Use the existing `django_project.settings.test` suite and ordinary Django tests.
Cover the accepted outcomes in K01-K42 plus unauthorized actions, cross-workspace
foreign keys and direct restricted-role DML. Existing four-product, ticket,
ordinary renewal/release, Party summary and history import tests remain relevant.

Compare every transition's principal, entitlement, interest, item ownership and
custody before/after. No UI-only test can substitute for these invariants. Include
stale policy/price reviews, two simultaneous payouts, repeated callbacks/forms,
rollback after mid-command failure and pending physical handover completion.

Before production: verify baseline, candidate build, migration plan, registry and
RLS checks, complete database/private-media backup and documented recovery path.
Run migrations only with owner-only migration settings. Web/workers use restricted
roles. Do not change mail workers or billing authorization as a side effect.

After real khata evidence exists, do not roll back to code that cannot read or
service it. Disable new origination if needed while preserving servicing, then
use a reviewed compatible rollback or forward correction. No destructive schema
rollback or re-import of existing ordinary loans is planned.

## Current review boundary

D1-D5 are now explicitly accepted. The owner also requested clarification of the
Loans boundary and protection of existing flexible lending. That compatibility
requirement is explicit above. Foundation architecture has been selected for
implementation; full servicing and integration still have review/release gates.
Round 10 confirms separate series, existing authorised approvers, new accounts
without historical import, today-dated routine entries and excluded charges/funding.
Round 11 adds both independent and licence-associated series. The owner then
authorized foundation implementation. Remaining work is approval/custody/financial
commands, integration and the explicitly recorded unresolved edges, without
reopening those selected business choices.


## Local integration checkpoint (1 October)

Subsequent owner instructions implemented the servicing/custody/settlement and
bounded correction backend. The latest instruction also delivers borrower,
dashboard/portal summaries, read-only register/detail and preserved private
source documents. See [the integration checkpoint](../implementation/khata-integration.md).
The subsequent [operator/recovery checkpoint](../implementation/khata-operator-and-recovery.md)
delivers supported command forms, private photo access and exact-identity native
backup/restore. The [2 October label/release review](../implementation/khata-release-review-20261002.md)
adds private collateral labels and read-only software assessment, with explicit
unsupported statutory/default boundaries. Stage 3's candidate/release verification
and stage 4's named/hardware/recovery/manual acceptance remain open. Unsupported
corrections remain explicit; no pilot is activated by these local checkpoints.
The owner then selected a new test workspace and 100 x 60 mm labels. The
[test candidate checkpoint](../implementation/khata-test-candidate-20261002.md)
adds local source freezing and full fictional database/media recovery rehearsal.
The [Linux image and persistent local pilot checkpoint](../implementation/khata-image-pilot-20261002.md)
verifies the frozen image, restricted runtime, 372 Linux regressions and a new
fictional test workspace on localhost. Remote CI, hosted test workspace, hardware
and owner/operator acceptance remain open; existing production workspaces stay
outside this rehearsal.
