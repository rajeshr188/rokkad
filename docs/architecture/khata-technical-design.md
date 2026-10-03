---
status: proposed
owner: loans
updated: 2026-10-01
tags: [loans, khata, schema, workflows, authorization, verification]
related: [../adr/2026-10-01-khata-agreement-design.md, ../plans/khata-delivery-design.md, ../plans/khata-agreements.md, control-plane-contracts.md]
---

# Khata technical design

The first foundation/calculator slice is implemented locally; see the
[implementation checkpoint](../implementation/khata-foundation.md) for its exact
boundary and tests. The full design below is a target, not a claim of complete
servicing support. The [ADR](../adr/2026-10-01-khata-agreement-design.md) records
confirmed rules and the owner's implementation instruction. No production activation.

The [opening slice](../implementation/khata-opening.md) now adds source operations,
owner policies, received items, valuations and photos. Accounts can be APPROVED
or ACTIVE through source operations. Proposals remain immutable on save; edits
append successors and approval is separate evidence. Further servicing is pending.
Opening/current-payout valuations use the existing same-day Rates contract. The
full proposed model inventory below still includes undelivered servicing records.

The [collection slice](../implementation/khata-interest-collection.md) now implements
completed monthly periods, exact segments and oldest-due interest allocations.
Balances use saved charges and actual receipts; annual due dates remain annual.
Revision activation, closing partial periods and compensation are not enabled by
this slice. Their SQL/source guards must be extended together with those commands.

The [agreement-change slice](../implementation/khata-agreement-changes.md) now
extends those guards for activated revisions, split segments and principal
repayments during formal reductions. Approval and activation remain separate
operations; pending proposals do not supply live terms. Custody returns, closing
partial periods and settlement are now implemented by the
[custody/settlement slice](../implementation/khata-custody-settlement.md).
The [correction slice](../implementation/khata-corrections.md) implements whole
receipt compensation and unhanded exchange cancellation with immutable sources,
administration/capability checks and conservative dependencies. Other correction
types remain undelivered. The [integration checkpoint](../implementation/khata-integration.md)
now implements shared summaries, read-only register/detail and source-preserved
private documents under the [integration ADR](../adr/2026-10-01-khata-summaries-and-documents.md).
The [operator/recovery slice](../implementation/khata-operator-and-recovery.md)
delivers supported command forms, private photos and native recovery. The
[label/release review](../implementation/khata-release-review-20261002.md) adds
private held-item labels and a read-only software assessment. Statutory/default
operations remain unsupported, with explicit named-pilot acceptance gates.
Production activation remains pending.

## Boundary and files

Keep all khata code in `apps/tenant_apps/loans`. Introduce explicit modules:

| Layer | Planned location | Responsibility |
| --- | --- | --- |
| Models | `models/khata.py` | Khata-owned records, constraints and projections |
| Domain | `domain/khata.py` | Pure interest periods, segments, minimum and entitlement calculations |
| Commands | `services/khata_accounts.py`, `khata_servicing.py`, `khata_collateral.py` | Approval/opening/revisions, money/settlement, physical custody/exchanges |
| Selectors | `selectors/khata.py` | Canonical balances, dues, entitlement, eligibility and list rows |
| Web | `web/khata_forms.py`, `web/khata_views.py`, `templates/loans/khata/` | Validated inputs and operator presentation; no money arithmetic |
| Documents | `services/khata_documents.py` | Typed payloads and immutable issues using compatible renderer primitives |
| Tests | `tests/test_khata_*.py` | Calculation, commands, isolation, integration and preservation |

These are modules, not new service frameworks. Reuse Party identity,
optional `LoanLicense`/licence revisions, `WorkspaceAccess`, `workspace_context`, private
storage and pure rendering helpers. Do not attach khatas to `PawnLoan` or create
fake `PawnCollateralItem` rows. Current pawn tables, product versions, financial
snapshots, interest policies and numbering rows are not backfilled or converted.

## Proposed schema

All new concrete tables have a direct non-null `workspace` FK, database parent
ownership guards, forced RLS and registry coverage. FK deletion is protected for
financial/custody evidence. Money is `Decimal(18,2)`; weights retain the current
supported gram precision; rates and LTV use fixed decimal precision, never float.
Use public UUIDs for browser identifiers and ordinary internal primary keys.

Every completed operation captures actor, recorded timestamp and business date.
Mutable projections have an optimistic version counter. Immutable evidence cannot
be updated or deleted through SQL under the runtime role; Python validation alone
is insufficient. Draft-only fields may change until their specified freeze point.

| Model | Fields beyond common ownership/audit fields | Keys and freeze rules |
| --- | --- | --- |
| `KhataSeries` | optional licence FK, code, prefix, width, next account number, maximum, active | Direct workspace ownership; unique workspace/code and dedicated prefix within workspace. Non-null licence must match workspace. Counter locked during allocation. Licence association, including null, frozen after first issued account number. No `LoanNumberSequence` rows reused. |
| `KhataAccount` | series, Party, formatted number, lifecycle, opened_on, settled_on, current agreement, next operation sequence, projection version | Unique workspace/number; series/Party/agreements must match workspace/account. Number immutable once allocated; opened_on only set by first payout. No maturity. |
| `KhataAgreementRevision` | account, revision number, proposed effective date, limit, monthly rate, frequency, LTV, contract version, lender identity, reason, request identity/hash | Unique account/revision. Saved proposals immutable; edits append a successor. Monthly rate unit is explicit in the field/contract. Approval and activation will be separate source operations, never edits to terms. Initial opening evidence will record the original minimum base. |
| `KhataPolicyRevision` | sequential workspace revision, exchange WARN/BLOCK, overdue WARN/BLOCK, actor/time | Unique workspace/revision; immutable. Resolve latest under workspace lock; no row means the confirmed WARN/WARN defaults. |
| `KhataOperation` | account sequence, kind, business date, request UUID, request hash, agreement/policy references, principal delta, entitlement delta, interest payment amount, evidence, optional reversal-of, optional parent operation | Unique account/sequence and workspace/request UUID; immutable. A repeated UUID with different input fails. No arbitrary balance-setting operation. |
| `KhataInterestPeriod` | account, monthly index, period start/end, due date, calculation version, originating operation, calculated charge, minimum adjustment, final charge, evidence/hash | Unique account/index/version. Immutable. Reversal/supersession references are on new operations; originals retain their bytes and values. |
| `KhataInterestSegment` | period, sequence, effective start/end, agreement, limit, rate, integer elapsed/period days, exact numerator/denominator | Unique period/sequence; immutable source evidence for every sum. No floating-point or rounded intermediate fraction as authority. |
| `KhataInterestAllocation` | receipt/settlement operation, period, amount, optional correction source | Unique operation/period allocation; immutable. Same account/workspace. Allocation cannot exceed unpaid charge or receipt amount. |
| `KhataCollateralItem` | account, public identity, metal, description, quantity, gross/net weight, purity, accepted operation, current custody/storage projection, reserved-by operation FK, projection version | Draft facts editable before receipt/acceptance; accepted facts retained. Reappraisal adds evidence rather than editing weights/purity historically. Reservation must belong to this account/workspace and is rebuilt from operation evidence. No principal allocation field. |
| `KhataCollateralValuation` | item, valuation date, rate reference/evidence, eligible value, method inputs, appraiser/actor, source operation | Append-only. Preserve price date, weight/purity inputs and selected value. Operations reference exact valuation rows. |
| `KhataCollateralMovement` | item, operation, movement kind, source/destination custody/storage, physical timestamp, recipient/reference | Immutable actual movements. One item cannot be received/returned twice from the same custody state. Parent operation links exchange/reduction/settlement. |
| `KhataCollateralSelection` (implemented) | operation, item, IN/OUT role | Direct Workspace ownership, same-account parent guards, immutable membership and unique active item/role. Compensated history is retained. OUT reserves the item; typed HANDOVER operation records actual return. This replaces the separate movement-table candidate for the delivered custody workflow. |
| `KhataCollateralPhoto` | item, private file, hash, size, media type, actor, source operation where accepted | Retained evidence with registered file ownership; approval/receipt binds exact accepted photo when workspace policy requires it. |
| `KhataDocumentIssue` | account, source operation/agreement, optional item, kind, payload hash/version, layout/profile hashes, private PDF, PDF hash, actor/time | Immutable issued bytes and source links. Requests to reprint return saved bytes; dated statements get their own issue identity. |

Model names are concrete candidates. Avoid extra tables unless a required query,
foreign-key guarantee or lifecycle needs them. `KhataOperation.evidence` is a
versioned schema for operation-specific snapshots, not arbitrary unvalidated JSON.
Core amounts, source links and identities remain typed columns.

The custody slice uses `KhataCollateralSelection` as a directly owned, guarded
through table with operation/item/IN-or-OUT membership. OUT reservations are
immutable; active memberships are unique per item/role, with compensated history
retained. Active IN membership cannot be reused. Actual returns
are `HANDOVER` operations with typed item and parent links rather than a separate
movement table. Custody and eligibility derive from receipts, selections and
actual handovers. JSON snapshots are checked against those typed children.

Closing period evidence adds nullable `charged_through`: null means the original
full monthly interval; a date from start through end records the closing partial
interval, including a same-day minimum with no elapsed segments. A SETTLE source
stores principal and interest separately, linked allocations and outgoing
reservations. `settled_on` and lifecycle projections derive from source operations.

### Checks and projections

- Positive agreed limit; monthly rate nonnegative; `0 < LTV <= 1`. Validate any
  supported upper rate precision/range consistently with existing decimal inputs.
- Net weight positive and at most gross weight, positive quantity, valid purity
  and supported metal; exact photo policy checked at acceptance, not draft save.
- Restrict operation kind/delta combinations. Withdrawal increases principal and
  reduces entitlement equally. Interest payment changes neither. Deposit/exchange
  changes neither. Limit increase changes entitlement but never principal.
- Principal repayment occurs only in reduction/settlement or a compensating
  correction. A reduction operation carries required repayment and revised terms.
- Rebuild principal from financial deltas; rebuild remaining entitlement from
  its opening allocation and later deltas. Reject negative results under lock.
- Balances and custody can have cached projections for efficient lists. Reconcile
  them against immutable source evidence; caches are not an alternate truth.
- Enforce cross-account and cross-workspace links at database level. Guard the
  account's current-agreement pointer against another account's revision.

## Separate numbering

Use workspace-owned `KhataSeries` with an optional licence association rather
than adding a khata flag to `LoanSeries`. The owner confirmed both independent
and licence-associated series in round 11. This adds a dedicated counter and
leaves ordinary sequences and issued loan numbers unchanged. A workspace can
create an independent series without having any licence records.

The hierarchy is Workspace -> KhataSeries -> KhataAccount. A licence is an
optional same-workspace reference, never the owner or counter scope. Enforce
unique khata numbers across the entire workspace, not separately per licence
or null-licence group. Different workspaces may each issue KH00001.

Freeze the licence association (including none) at first account-number allocation,
which the proposed draft flow performs on first valid save. Cancellation does not
unfreeze it. A later association change uses a new series with a distinct prefix;
existing accounts keep their series, numbers and agreement evidence. Guard the
freeze in the database and serialize setup edits with number allocation. Do not
silently attach a licence to existing independent accounts or reset a counter.

Default presentation is `KH00001`. Prefix/width/ceiling are setup data, not a
hard-coded promise that KH is free in every workspace. Validate collisions with
existing displayed ordinary numbers during setup/allocation; all object routing
also carries account kind and UUID. Reject conflicting prefixes instead of
renaming old loans. No counter is created or enabled by an automatic data migration.

Allocate a number atomically when saving the first valid khata draft, matching the
existing draft-numbering convention. Preview is read-only. Cancelled numbers are
never reused. Revision labels are `KH00001 / revision 2`; transactions use the
account's monotonic operation sequence, not new loan numbers. A counter at its
ceiling blocks only new khatas in that series, not servicing existing accounts.

## Lifecycle and authority

Proposed account states:

| State | Allowed transition or work | Evidence |
| --- | --- | --- |
| DRAFT | Edit, approve, cancel | No interest or principal; held draft collateral must be accounted for on cancellation |
| APPROVED | First withdrawal, return to draft/reapprove, cancel | Approved revision frozen; no interest start until cash payout |
| ACTIVE | Deposit, withdraw, exchange, receive interest, change agreement, reduce, settle | Every completed action has its own operation |
| SETTLED_RETURN_PENDING | Complete return of held items; review an eligible correction | Financial settlement complete and interest stopped, but actual handover remains |
| CLOSED | Read/reprint/export and eligible reviewed correction | Zero monetary balance, entitlement ended, all return obligations completed |
| CANCELLED | Read retained draft/cancellation evidence | No committed financial opening; cancellation is not ordinary deletion |

Settlement can move directly from ACTIVE to CLOSED when cash and actual handover
are both recorded. Paying money alone does not prove custody. `settled_on`, not
the last item handover date, ends interest. Overdue and undercovered are independent
flags, never account lifecycle states. A reduced account remains ACTIVE.

An approved revision has an intended date. Activation requires it to match today's
business date and the reviewed account version. A stale approved proposal must be
reviewed again as new evidence, not edited in place or silently backdated. For a
first payout on a later date, approve a new revision with current collateral/rates.

### Proposed action mapping

Use the actual existing codes from `apps/orgs/access.py` and
`services/action_access.py`. Require `data.view` and all listed actions; business
writes also pass existing workspace lifecycle/commercial-write checks. The user's
existing approver choice does not automatically confer payout or receipt rights.

| Action | Existing capability |
| --- | --- |
| View account, balances and receipts | `data.view` |
| Draft account | `data.create` |
| Edit draft, prepare revised terms, deposit/appraise collateral | `data.edit` |
| Approve opening or limit/rate proposal | `loan.approve` |
| First/later withdrawal | `loan.disburse` |
| Interest receipt or principal repayment | `loan.repay` |
| Exchange / actual collateral handover | `loan.release`; incoming receipt/appraisal also requires `data.edit` |
| Apply reduction with repayment/return | Approval evidence from `loan.approve`; executing money requires `loan.repay`, returning items requires `loan.release` |
| Full settlement | `loan.repay` for money and `loan.release` for handover; support authorized completion of separate steps |
| Export | `data.export` |
| Series/configuration | Existing `workspace.settings.manage` boundary |
| Change the two owner policies | Existing owner-action boundary; preserve audited platform override rules |
| Compensating correction | Existing administrator boundary plus affected operation capabilities; reason required |

Do not grant permissions by role-name string or turn all approvers into owners.
Use the existing owner helper/action contract for owner-only policy selection.
Every service authorizes independently of HTTP, so jobs/commands cannot bypass it.
Exact permission combinations are implementation mapping, not new permissions
granted to current users by this document.

## Date and interest contract: KHATA-1

Use the server's configured business local date, as existing loan services do.
Routine commands accept today only; a submitted earlier/future date fails with a
clear message. A stale preview crossing midnight requires refreshed review.
Record timestamps in the usual timezone-aware format. Finalizing an elapsed
period is not a backdated cash transaction: preserve the period dates and today's
recorded timestamp separately.

Monthly boundaries derive from the original first-withdrawal date, never from
the previous clamped boundary. A 31 January start yields February's last day,
31 March, 30 April. Proposed annual leap-day convention: clamp to 28 February in
non-leap years and restore 29 February in leap years. This matches the monthly
anchor principle but remains an explicitly identified edge for review.

For each monthly interval `[A, B)`, split at activated rate/limit changes. For
each segment `[s, e)`, exact charge is:

`limit * monthly_percentage / 100 * days(e - s) / days(B - A)`.

Include the effective/start day and exclude the next boundary/closure day. Sum
exact rational segment amounts, then round the period once to paise, half-up.
Represent exact values with integer numerators/denominators derived from decimal
inputs, using standard-library rational arithmetic; never binary floats. Annual
dues sum finalized rounded monthly charges, not an unrounded annual recomputation.

The one-time first-month floor is opening limit times opening monthly rate.
Charge `max(opening_floor, actual_first_month_charge)` including early closure;
same-day closure still owes the floor. Later revisions do not restart it. For
later partial periods, charge only the actual-period fraction. For a full annual
cycle, monthly periods 0-11 share due date A12, periods 12-23 share A24, etc.
No intermediate month becomes overdue on an annual account.

Proposed same-day revision ordering: store each approved activation, but the last
activated revision for that effective date supplies that day's terms. Opening
minimum retains the actual opening revision. Disallow activation that would
reinterpret an already finalized segment without the correction workflow. This
is a visible date-granularity convention, not an unrecorded intraday approximation.

Completed monthly periods are finalized once. At annual settlement before the
anniversary, finalize the closing partial period and collect all unpaid charges,
even though annual due dates have not arrived. At reduction returns, collect only
due/overdue interest; unbilled accrued charges remain on their original schedule.

### Entitlement and availability

Maintain `U`, unused entitlement, independently from outstanding principal `P`:

- Opening at first payout `W` under limit `L`: `P = W`, `U = L - W`.
- Further withdrawal `W`: `P += W`, `U -= W`; require `W <= U` before mutation.
- Limit change `old_L -> new_L`: `U = max(0, U + new_L - old_L)`.
- Any principal repayment changes P only, never independently increases U.
- Settlement ends U. A rate-only revision changes neither P nor U.

For a common agreed LTV `q`, accepted held value `V`, available additional backing
is `max(0, floor_to_paise(V * q) - P)`. Drawable amount is the lesser of that
backing and U, subject to authorization/overdue/custody restrictions. A warning
exchange can make coverage deficient; it cannot make a later payout eligible.

## Command transaction and handover design

Use explicit service commands: create/edit/approve, first/later withdrawal,
deposit, exchange preview/confirm, interest receipt, agreement activation,
reduction preview/confirm, settlement quote/confirm, handover and correction.
All writes use the actual workspace and actor, request UUID and request hash.

Common sequence:

1. Enter validated workspace context; authorize and check write availability.
2. Follow one lock order across commands: workspace policy/sequence owner when
   relevant, then account, affected revision/period rows and items in stable
   primary-key order. Policy changes and number allocation use the same order.
3. Resolve retry UUID first; an identical completed request returns its original
   result. Different payload under that UUID fails without side effects.
4. Compare reviewed version/hash, date, policy and valuation evidence with current
   state. Refresh stale previews rather than silently changing accepted figures.
5. Recompute principal, entitlement, interest allocations and eligible custody.
6. Append immutable operation and related rows, then update projections together.
7. Commit before handing out generated documents. PDF failure allows retry of
   issuance for the existing operation, not repetition of money/custody actions.

For exchange, accept incoming items first. The confirmation reserves selected
outgoing items for this exchange and records accepted replacement/valuation facts.
Actual return is a linked handover operation. Until it completes, show both actual
held items but exclude reserved outgoing items from drawable-value calculations;
otherwise pending handover could incorrectly support another withdrawal. Prevent
reuse of reserved items in another exchange/reduction. Cancelling a pending
exchange requires explicit incoming-return/reservation-release evidence.

For reduction, approve terms and preview both the principal payment and retained
coverage. Confirm the actual payment and revision atomically; reserve outgoing
items and record handover separately if necessary. Once reserved, they no longer
support new draws. Hard retained-LTV and due-interest checks apply regardless of
the exchange warning setting. Settlement likewise stops financial accrual but
retains pending return obligations until actual handover.

The local implementation rechecks due interest and current retained cover for an
active reduction handover. Committed exchange handovers retain their source
authorization after later policy changes; financially settled handovers need no
reappraisal for zero debt. Reservation cancellation/compensation is still a release
gate beyond the supported unhanded cancellation described below, never an edit
or deletion of accepted custody evidence.

Required photos, valuation and storage must be available and authorised before
receipt; optional photo policy must not become a mandatory-photo gate. Freeze
same current approved price basis for incoming/outgoing same-metal groups.
Reject unknown prices rather than substituting zero; value-short warning is for
known shortfalls, not missing evidence. A proposed freshness check requires a
current business-date quote for cash/return eligibility; this must align with
the selected valuation-source contract before implementation.

### Corrections, not edits

The [bounded correction ADR](../adr/2026-10-01-khata-bounded-corrections.md) now
implements whole receipt compensation and unhanded exchange cancellation under
CORRECT sources. Other sources are refused. Later uncorrected account operations
and pending correction returns are conservatively treated as dependencies.
Original rows remain immutable; active membership uniqueness replaces historical
item/role uniqueness so released originals can be legitimately used again.

Restrict corrections to authorised administrators with a reason and explicit
source operation. Preview every affected charge/allocation, revision and custody
dependency. A source with later dependent events cannot be reversed in isolation.
Unwind eligible dependencies newest-first or refuse with their identifiers.

Reversal appends opposite financial effects and linked replacement evidence;
it never deletes the source or rewrites issued PDFs. Physical custody needs
actual return/receipt confirmation; a database reversal is not a physical move.
Printed receipts remain historical and are shown as corrected with the new source
link. No generic "set balance" or hidden opening amount is offered.

Earlier cash-recording/import remains unsupported in first release. Legitimate
correction of a recorded operation is a separate workflow; do not backdate a
routine request to avoid dependency checks. Full complex historical correction
coverage must be bounded and tested before real account creation is enabled.

## Integration, documents and queries

All khata endpoints sit under the explicit workspace Loans path with their own
account-kind route. Shared selectors compose typed pawn and khata summary rows;
they do not UNION unlike financial columns and assume matching semantics.

Account summaries expose P, U, limit, accrued interest, due/overdue interest,
current collateral value, drawable amount and policy flags as separate fields.
Party totals add actual khata debt once, preserving ordinary loan contributions.
Always label sanctioned/unused amounts separately from borrower outstanding.
Include both independent and associated series in workspace totals and exports;
licence filters offer "No licence associated" without inner-join omissions.

Provide versioned typed payloads and immutable document issues for opening
agreement, agreement revision, withdrawal, interest payment, exchange, reduction
return, full settlement and dated statement. Item labels reference khata/item
identity and authenticated routes. Use private-file registry/inventory coverage
and exact saved reprints. No public borrower PDFs or external messaging introduced.

Capture lender name/address explicitly in agreement and document evidence; an
independent series cannot depend on licence display fields. Associated series may
prefill from the selected licence, with the reviewed identity frozen in evidence.
Snapshot the applicable licence revision when associated and explicit absence
otherwise. Omit inapplicable licence fields without substituting a dummy number.

Export native khata source events, revisions, periods/segments, allocations and
custody/media/document evidence with a versioned manifest. Restore must reconcile
P, U, interest and held/reserved items. This is distinct from importing old paper
accounts, which remains excluded. Do not route payloads through pawn history/2.

Licence-specific eligibility checks apply only to associated series. Independent
series still require workspace availability, action permissions, approved khata
terms and collateral checks. Neither mode inherits ordinary-loan licence interest
or LTV policies; the approved khata agreement supplies those terms.
For associated series, licence expiry follows a conservative proposed mapping:
deny new accounts, new cash and limit increases; allow valid collection/deposit/reduction/settlement
under existing workspace availability. Classify other risk-increasing changes
explicitly. This mapping and statutory/default operations remain release-review
items; do not silently claim ordinary pawn auction support for khata.

## Migrations and implementation slices

1. Add the new model module, explicit new-table ownership/RLS/immutability guards
   and registry migration gates together. No existing workspace is auto-enabled.
2. Add calculator and account selectors, tested against the confirmed examples.
3. Add numbered drafts, approval and full servicing commands with compensation
   and pending custody. Do not expose real creation with only opening implemented.
4. Add screens, integrated summaries, private documents and native recovery.
5. Verify migrations, restricted runtime, existing flexible-loan preservation,
   candidate build and a separately reviewed named workspace pilot.

Use owner-only migration settings; runtime web/workers stay restricted. New model
creation and database guards must land in the same migration release. Do not
disable current forced RLS or change current product rows to introduce khata.

## Concrete test inventory

The full inventory below remains a release plan. Foundation tests now cover the
calculator, numbering, draft evidence, isolation and concurrency; see the checkpoint
for executed coverage. Use existing Django test settings; property
examples and fixtures supplement source-level assertions rather than mirror them.

| Group | Cases and required evidence |
| --- | --- |
| CALC-01 | INR 1 crore at 1%: INR 1 lakh per full month; INR 12 lakh annual total; four-month annual closure INR 4 lakh less paid amounts |
| CALC-02 | After minimum, 10/31 period at INR 1 lakh monthly gives INR 32,258.06; same-day first closure still charges INR 1 lakh |
| CALC-03 | 30-day first period, 15 days at INR 1 crore then INR 1.5 crore: full period INR 1.25 lakh; closure five days after change charges INR 1 lakh floor over INR 75,000 actual |
| CALC-04 | 31 January clamping/restoration; leap-year boundaries; no double-counted boundary day; annual due grouping; two same-day activations |
| CALC-05 | Round monthly exact sums once; annual total equals sum of issued monthly charges; no interest on unpaid interest |
| ENT-01 | Limit 100 lakh/drawn 60 lakh -> reduce to 80 lakh leaves U20 lakh; fully drawn -> repay20/reduce80 leaves U0; rate-only edit leaves U unchanged |
| FLOW-01 | First payout only activates once; deposit alone pays nothing; repeated and concurrent payouts respect U and LTV |
| FLOW-02 | Warn/block known exchange shortfalls; reject cross-metal in both modes; grouped identities retained; pending outgoing items cannot back another draw |
| FLOW-03 | Reduction return blocked for failed retained LTV or due interest; annual unbilled interest remains scheduled; repayment does not restore U |
| FLOW-04 | Oldest-due allocation; reject excess/advance payments; default next-day overdue; block only intended actions, not collection/deposit/settlement |
| FLOW-05 | Financial settlement stops interest while return pending; close only after handover; partial failure/retry never duplicates payment or item movement |
| AUTH-01 | Approver without disburse permission can approve but cannot pay out; sender workspace/request mismatch denied; owner policy cannot be changed by ordinary approver |
| RLS-01 | Cross-workspace read/write, forged parent FKs, unset context, raw UPDATE/DELETE of immutable rows, and context cleanup under the restricted role |
| RACE-01 | Same/different payload retry UUIDs; simultaneous last available draw; stale price/policy/revision; cancellation vs handover; midnight rollover |
| CORR-01 | Newest-first dependencies, protected original PDFs, physical custody not fabricated, correct restored P/U/dues and retry behaviour |
| DOC-01 | Agreement/payment units explicit, full address/description fitting, receipt source links, private files, exact reprints, native export/restore reconciliation |
| COMPAT-01 | JCL/JSK/Lakshmi flexible-policy fixtures unchanged, including JSK WH weeks; ordinary new originations, payments, releases/renewals and issued PDFs unchanged |
| COMPAT-02 | Borrower with both types counted once each; unused khata limit excluded; ordinary series counters unchanged; no khata rows in pawn-only actions |
| SERIES-01 | Independent opening without any licence records; associated opening with same-workspace licence; reject foreign-workspace licence even through raw SQL |
| SERIES-02 | Workspace-wide number uniqueness across both modes; different workspaces can each use KH00001; concurrent allocations do not duplicate numbers |
| SERIES-03 | Reject adding/removing/replacing licence after first account number, including cancelled drafts; setup-edit/allocation race; new series preserves old numbers/evidence |
| SERIES-04 | Both modes included once in totals/exports; no-licence filter; lender identity present on independent documents; associated eligibility gates do not leak to independent series |

## Review disposition

Foundation, servicing/custody, bounded corrections and summary/document integration
are implemented locally. The [operator/recovery checkpoint](../implementation/khata-operator-and-recovery.md)
also delivers full supported command forms, private photos and trusted exact-identity
native recovery. Remaining explicit technical review
items are the proposed annual leap-day/same-day revision conventions, exact
valuation freshness source, correction coverage, licence/default boundary and
statutory document boundaries and broader correction/import requirements. Native
recovery schema is versioned separately from pawn history and does not support
edited financial imports or workspace clones. These do not reopen confirmed business choices.
Keep unsupported operations unavailable; do not promise all 42 scenarios are
implemented merely because this specification exists.
