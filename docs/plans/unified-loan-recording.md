---
status: active
owner: project
updated: 2026-10-03
tags: [loans, paper-entry, portability, delivery]
---

# Deliver unified loan recording

The owner selected [one Loans workflow](../flows/unified-loan-recording.md) for
actions performed now and actions recorded afterward. The
[ADR](../adr/2026-10-02-unified-loan-recording.md) is accepted. On 2 October the
owner authorized implementation. Work is incremental; completed local slices and
remaining scope are tracked below. Production changes and archive conversions
are separate from local implementation.

## Tracking

## UR-23: finish the familiar New loan presentation

Authorized 3 October after the owner identified the duplicate series chooser and
prominent mode buttons. **Complete locally:** the ordinary Series field applies
the configured purpose, a compact Entry/Change control allows an exception, and
switching retains common facts plus purpose-specific details. The duplicate chooser
and prominent navigation are removed. Read-only changes never post a loan, retain
a stale signed review or waive direct approval/valuation. Financial UR-19–22 remains
the completed foundation; the two appropriate backend validators are retained.

142 affected tests pass in 78.846s, including native draft save/validation and
paper admission regressions. Actual desktop/mobile/no-JavaScript checks confirm
single-series routing, fact retention, editor reinitialization and signed review;
desktop admits P-0056. JavaScript retains selected photographs across switches.
The direct browser preflight continues to reject an earlier-date metal-priced
decision; existing saved PDF hashes match. Without JavaScript, files need explicit
reselection after a purpose change, with a visible explanation. Candidate 8078 is
`rokkad:entry-refined-20261003-a80e473e`, with 1,529 runtime files matched, schema
0057 unchanged and existing loan rows/file bytes unchanged during update.
Real staff/paper/hardware and hosted release acceptance remain pending. See the
[candidate evidence](../implementation/joint-loan-candidate-20261003.md).

## Shared multi-item entry authorized (3 October)

The owner authorized a shared loan-entry experience with a standing entry-purpose
default at Workspace/license/series scope and an explicit per-action override.
Preserve all direct origination checks and existing frozen contracts. Every actual
paper collateral row has its own principal: no total-only origination or invented
historical allocation is needed. For paper principal receipts, staff specify the
item split; interest remains calculated from actual dated item agreements.

| Slice | Scope | State |
|---|---|---|
| UR-19 | Multi-item recorded origination and anniversary interest; staff-directed paper principal receipts | Complete locally |
| UR-20 | Multi-item closure, correction and servicing integration with immutable item evidence | Complete locally |
| UR-21 | Shared collateral editor and creation-purpose navigation; scoped standing default with per-action override | Complete locally |
| UR-22 | Native/paper regressions, scope/retry checks and browser acceptance; update local release evidence | Complete locally |

UR-19–22 are complete locally. Verification passes 502 regressions (445.006s)
and 105 overlapping final receipt/draft checks (61.683s). Actual desktop/mobile
admission and later receipt/closure, no-JavaScript add/review and exact saved-PDF
checks pass. That checkpoint used `rokkad:shared-entry-20261003-d91d4ea3`
through migration 0057, with verified database/media backups and all existing loan
rows/file hashes unchanged during update. Production and the 8077 pilot are
unchanged. See the [candidate evidence](../implementation/joint-loan-candidate-20261003.md).
Optional already-completed linked paper renewal remains the older single-group
shortcut; multi-item paper agreements are entered independently. Ordinary Renew
performed now supports multi-item recorded sources with current approval.
Real paper/staff/hardware and hosted production acceptance remain release work.

Do not default or infer a paper receipt's principal split from direct entry's
highest-rate-first rule. Existing recorded-anniversary/1 loans keep their original
calculation semantics; itemized agreements need explicit versioned evidence.

## Routine entry simplification agreed (3 October)

The owner tried the local form and accepted standing-term defaults with explicit
exceptions, automatic proceeds and lighter completeness presentation for ordinary
entry/payment/closure/monitoring. Imported and Lakshmi paper-origin loans primarily
use Flexible Partial Payment. Lakshmi's standard tenure is confirmed as 12 months.
UR-15–18 are complete locally and included in the updated fictional candidate on
8078. Production is unchanged. Broader exceptional profiles are deferred
until actual business cases establish their rules.

| ID | Implementation order | Acceptance |
| --- | --- | --- |
| UR-15 | Resolve standing terms from existing series/license/Workspace selectors, the original agreement date and metal. Prefer an unambiguous eligible Flexible Partial Payment version. Add the missing configurable standard tenure at the existing setup boundary. Resolve current monitoring separately. | Applicable rate, deductions, tenor and monitoring are displayed without repeated entry; supported actual exceptions and missing historical digital setup remain recordable; existing contracts keep their saved terms. |
| UR-16 | Simplify paper entry and ordinary receipt/closure presentation: transaction facts, calculated agreement summary, collapsed exceptions and optional already-recorded paper activity. | Server recalculates and binds final review; principal/proceeds/actual cash remain distinct; no renewal ancestry prerequisite or guessed physical return; two-decimal money, duplicates, scope and chronology remain enforced. |
| UR-17 | Make routine monitoring/reporting useful from entered records while separating transaction confirmation, optional checked-through evidence and known missing activity. | No daily per-loan certification for ordinary viewing; known exposure totals display with provisional/unavailable counts; last transaction date does not claim book completeness; reminder/auction gates retain explicit coverage checks. |
| UR-18 | Verify the simplified paths and update the local candidate/release record. | Scoped policy/default/date/exception tests, receipt/closure accounting and retry tests, monitoring/reminder boundaries, desktop/mobile/no-JS and native JCL/JSK regression checks pass before release preparation. |

Keep existing immutable loan snapshots/events and services. A default is resolved
and frozen for the individual agreement; later setup changes never reprice it.
If several eligible product versions exist, use an explicit selection instead of
an arbitrary choice. A missing dated digital policy does not justify inventing
historical prices or refusing supported actual paper terms. Existing fee resolution
is Workspace/license scoped; do not invent series fee overrides. The paper profile
supports simple FULL_MONTH, one collateral group and zero/one advance month with
an identified deducted document charge; unsupported configured rules must be
explained rather than silently converted or omitted.

Ordinary confirmation covers the transaction being recorded. Any claim that all
paper activity is entered through a date requires an actual scoped attestation;
book-progress notes alone cannot confer it. Displayed risk/exposure uses entered
records with its limits visible. This pass preserves reminder/auction protections.
Standard-tenure values are business setup, not assumed from an illustrative example.

**Completion evidence:** 422 final regressions pass in 369.684 seconds; the 156-case
affected rerun overlaps that selection. It covers new defaults/date/exception/retry
cases, native lending, total-only receipts and closure, known linked renewal,
corrections, monitoring/reminder/auction boundaries, both recovery families and
tenant isolation. Actual desktop/mobile/no-JavaScript entry and signed review pass;
browser-posted receipt/closure figures and provisional exposure reconcile under the
restricted runtime role. Existing joint-loan navigation, saved PDF hashes and viewer
restrictions pass. 1,519 runtime files match the scoped image; migration 0056,
owner refusal and restricted startup pass. Prior image/container and verified
physical database/media backups are retained. See the
[candidate update](../implementation/joint-loan-candidate-20261003.md).

## Completion programme authorized (3 October)

The owner authorized the remaining recommendations in this order. Completion
requires verified behavior and explicit release evidence, not just implemented
forms. Staff acceptance requires real representative paper records; automated
fixtures cannot stand in for that business sign-off.

| ID | Ordered scope | State |
| --- | --- | --- |
| UR-08 | Entry usability: optional paper closing number with labelled system number; later handover confirmation; book/day backlog checkpoints; batch transaction reviews; archive closure with unknown handover | Implemented locally; domain/HTTP/browser/PDF, 745 broad regressions and 147 overlapping boundary tests passed; real-record acceptance/rollout pending |
| UR-09 | Common amendments: original date/principal/rate, successor terms and settlement date/custody; immutable corrections with dependency review | Implemented locally; original/successor terms, native forward dependencies, single closure facts and paired custody dates verified; no arbitrary physical reversal; real-record acceptance/rollout pending |
| UR-10 | Ordinary renewal of imported opening loans, preserving opening obligations and current successor approval | Implemented locally; current/paper successors, approval, paired reversal and reduced-principal checks passed; real-record acceptance/rollout pending |
| UR-11 | Versioned restorable recorded-origin export, including identities, corrections, renewals, coverage and custody evidence | Native original-identity archive implemented with exact rows, file bytes and financial/coverage/custody reconciliation; ordinary download and offline restore verified; cross-Workspace remapping is a separate unsupported importer |
| UR-12 | Recorded-origin auction/recovery through ordinary services and agreed collection balances | Implemented locally; completeness/statutory gates, agreed debt, disposal, exact retry, paired reversal and archive recovery verified in 125 integration tests |
| UR-13 | Additional actual paper profiles established from representative evidence; no assumed waivers, capitalization or item-allocation rules | Deferred by owner until actual business cases arise; supported baseline remains available |
| UR-14 | Representative acceptance, release checks, migration/rollout and operational verification | Local migration, regression, UI/PDF and recovery checks complete for the implemented profile; real Lakshmi records and rollout target requested; staff acceptance and rollout pending |

Initial renewal-chain reconstruction remains optional and deprioritized. Progress
checkpoints are operational evidence only; they do not certify a loan's balances
or imply that every paper loan has been entered. Handover confirmation must append
custody evidence without changing a financial closure or inventing another loan.

The native [recovery decision](../adr/2026-10-03-ordinary-loan-native-recovery.md)
defines UR-11's restoration contract explicitly. Original actors/timestamps and all
connected ordinary-Loans relationships survive without replaying a fictional new
payout. Existing portable JSONL contracts retain their narrower scope. See the
[operator and acceptance guide](../flows/paper-first-operator-and-release.md) for
current entry, correction, renewal, monitoring, recovery and rollout procedures.
The programme is not complete until the real-record and release evidence exists.

## Existing delivery checkpoints

**Owner clarification (3 October):** one paper loan at a time is the primary
workflow. Staff need not reconstruct an unknown renewal sequence. Once entered,
an active paper loan can use ordinary Renew for a new decision or a known already
completed renewal. See the [superseding decision](../adr/2026-10-03-independent-paper-loans-and-renewal.md).
Historical chain reconstruction and its broader amendments are deprioritized;
they are not daily paper-entry prerequisites. Earlier checkpoints below describe
their original delivered profiles.

| ID | Deliverable | State / completion evidence |
| --- | --- | --- |
| UR-01 | Existing opening loan: record a dated total-only paper receipt through ordinary Repayment, with signed allocation review and source reference | Implemented and verified locally; [163 regressions and browser evidence](../implementation/unified-loan-recording.md); deployment pending |
| UR-02 | Record original contract and payout without invented contemporaneous digital approval; separate monitoring basis | Storage/read-model foundation implemented and verified locally; 309 regressions plus 2 published-contract checks; ordinary admission is UR-03 |
| UR-03 | Never-entered loan: review and atomically admit supported payments, renewal and closure history | Initial bounded implementation verified locally; 508 regressions plus 171 final document/UI/history checks; clarified renewal scope requires UR-03A; deployment pending |
| UR-03A | Paper renewal with customer-selected principal reduction, unchanged carry or top-up; reconcile actual cash and interest settlement | Implemented and verified locally: carry/top-up or full principal repayment/fresh advance, explicit cash/offset and independent custody; 522 regressions plus 126 final checks; deployment pending |
| UR-04 | Late transactions affecting already recorded later activity: dependency review and supported corrections | Receipt/accrual, unchanged-agreement renewal/full-return and whole-batch receipt correction verified locally; batch extension passed 87 regressions plus 105 final integration checks. Broader contract/custody/date amendments remain open; deployment pending |
| UR-05 | Reconciled archive admission, source links and duplicate guards across import/manual routes | Initial single-closed-loan profile verified locally: 335 regressions plus 86 final checks. Renewal-chain source admission remains pending; migration 0042/deployment pending |
| UR-06 | Transaction completeness, current risk monitoring, reports, documents, portability and reminder integration across all supported origins | In progress: scoped transaction reviews, provisional monitoring/reports and guarded borrower reminders verified locally (358 regressions, 143 final checks). UR-07 adds recorded contract/interest-position documents and routine recorded-origin renewal. Restorable portability, auction recovery and imported-opening renewal remain pending |
| UR-07 | Independent paper opening/closure, deducted document charge, recorded contract/interest position, ordinary subsequent renewal now or already completed | Implemented and verified locally: 508 broad regressions plus 98 native/reversal, 154 document/coverage, 90 settlement/register and 15 final routine checks; desktop/mobile/no-JavaScript and PDF review passed. No mandatory predecessor reconstruction. Migration 0045/deployment pending |

UR-07 supplies the agreed routine paper workflow for supported recorded anniversary
contracts: independent entry, later receipts, dated closure, and subsequent linked
renewal, including new advance interest and document charge. Its recorded closure
may leave physical cash/customer handover unspecified. Contract copies and current
interest-position documents are implemented. UR-06's remaining recorded-origin
restorable exports, auction recovery and imported-opening renewal remain distinct;
the full original adaptation plan is not claimed complete.

UR-01 reuses the existing reviewed opening collection calculator and repayment
writer. It supports dates strictly after the opening checkpoint and not before
recorded financial activity, including earlier today. Initial paper allocation
supports no outstanding fees and a single principal-bearing collateral item when
principal is reduced; broader fee/item rules remain explicit follow-up. Interest-only
receipts can use the existing multi-item calculation. Native real-time repayments
remain unchanged. This slice does not admit never-entered loans, claim complete
paper books, close loans or convert archives.

UR-02 adds explicit recorded-contract and recorded-payout bases to the existing
immutable policy/disbursal snapshots. A recorded payout has no approval FK and
retains versioned source/contract evidence in its ordinary DISBURSAL event. Current
monitoring selection is identified separately. Initial storage supports explicit
simple monthly terms, two-decimal currency, no fees and zero or one advance month.
UR-03 now exposes ordinary New loan ? Already completed on paper, with a signed
review of the complete timeline before one atomic admission. No saved incomplete
loan is exposed as active during preparation; invalid forms retain entered values.

The owner confirmed that a principal reduction changes interest from the next loan
anniversary, and renewal carries principal into a new numbered loan while collateral
remains held. The initial entry profile requires explicit confirmation of the precise
full-month boundary, including payments on an anniversary. It supports one collateral
group, at most 30 transactions/five renewals and ten years of entered history; no
fees, concessions, top-ups or renewed advance deductions. This describes the initial
implementation, not the full agreed renewal scope. Unsupported arrangements
require a wider profile, never silent recalculation to today's lending decision.

UR-04/UR-05 deliver bounded later-event corrections and single-closed-loan archive
admission, with broader amendments pending. UR-06 delivered scoped completeness,
provisional monitoring/reporting and guarded repayment reminders. UR-07 adds routine
subsequent renewal and recorded document coverage. Restorable portability,
imported-opening renewal and auction recovery remain open.

## Confirmed scope

Support ongoing paper-first operation and Lakshmi's mixed backlog from 24 September
2026, including subsequent payments, renewals and closures. Use ordinary loan and
transaction records. Permit qualified archive evidence to support admission as an
ordinary closed loan, while retaining and linking its immutable source.

Lakshmi receipts contain only total received. The owner confirmed INR 2,000 against
INR 200 interest and INR 10,000 principal allocates INR 200 to interest and INR 1,800
to principal. Preserve source total and derived allocation separately. Do not treat
this answer as confirmation of all fee, exceptional payment or item-allocation rules.

### Clarified renewal scope and UR-03A

The owner clarified that a customer may pay interest and reduce principal or request
a top-up when renewing. Keeping collateral held answers the custody question only.
New principal must reconcile as:

`old outstanding principal - principal repaid + additional advance`.

UR-03 already handles unchanged/reduced principal. Extend the same renewal command,
review and source records to support additional advances; the core renewal model
already has principal-paid, top-up and successor-principal fields. Preserve the
new agreed rate/tenure and the old-to-new collateral links. Both separate interest
receipt and deduction from an advance are accepted, as is actual full principal
repayment followed by a fresh advance. Choose per transaction; both custody held
and actual return/repledge are independently valid. Preserve actual cash in both
directions and the interest offset; never infer capitalization from net cash.

Review must show old principal, principal paid, carry, top-up, new principal,
interest settled and actual cash received/paid or offset. Update the event evidence,
retry binding, reports, memos and monitoring so carried debt is never reported as
fresh cash and an actual top-up is never omitted. A paper renewal records the
already agreed facts; a renewal performed now still applies the relevant current
approval checks. Verify reduction, unchanged carry, top-up, supported settlement
methods, next-loan interest, duplicates and atomic rollback before declaring the
clarified scope supported. Complete this extension before UR-04.

## Delivery sequence

UR-04's first supported boundary is an active admitted anniversary contract with one
collateral group. Add, replace or void a receipt through signed review, compensate
the existing collection events and replay preserved receipt totals in actual order.
The review compares allocations and current balances and lists unsupported lifecycle
dependencies. See the [correction decision](../adr/2026-10-02-recorded-receipt-corrections.md).
The [settlement extension](../adr/2026-10-02-recorded-settlement-corrections.md)
reconciles revised actual cash across an unchanged renewal agreement or single-loan
full return. It preserves successor terms and custody and binds forward activity
to signed review. The batch extension reviews all members and reconciles actual
combined collection atomically, preserving original batch and handovers. Remaining
UR-04 scope includes amendments to contract/custody facts and settlement dates; these are explicit blockers,
not capabilities of the delivered receipt/settlement correction command.

1. **Resolve supported contract profiles and boundaries.** Inspect representative
   paper terms, repayment/renewal/closure examples and retained archive evidence
   read-only. Map exact interest, upfront deductions, rounding, partial periods,
   fee priority, item allocations, waivers and overpayment treatment. Establish
   which facts are known, derived, missing or contradictory. Reuse existing
   profiles when their behavior matches; do not silently force a different rule.
2. **Extend shared services and evidence.** Design actual-date/recorded-time
   semantics, recorded contract basis, current monitoring basis, source identity
   binding and typed action purpose. Audit models, readers, commands, forms,
   documents, exports and tests. Keep ordinary Django patterns and existing
   canonical calculations. New Workspace-owned tables, if necessary, require
   direct ownership, forced RLS, registry coverage and isolation tests together.
3. **Deliver ordinary manual entry and reviewed timeline admission.** Extend
   existing screens to prepare the advance and supported subsequent events,
   preview amount-only receipt splits, reconcile financial/custody state and
   admit atomically. Preserve numbering, source references, actual actors when
   known and date precision. Include an explicit refusal for unsupported cases.
4. **Handle ongoing late servicing and archive admission.** Define the supported
   dependency/correction boundary for already posted later events. Add immutable
   archive-to-loan links and source-level duplicate guards across all import/manual
   routes. Start with reconciled examples; do not bulk-convert source-closed claims.
5. **Integrate monitoring, reports and operational readiness.** Make current
   coverage and transaction completeness independent, exclude closed exposure,
   avoid duplicate cash/new-lending counts, preserve portable provenance and
   generated-document meaning, and gate downstream reminder intent appropriately.

These are slices of the same workflow, not a separate paper-loan module. Do not
announce support for a profile until its calculations, servicing, reporting and
correction boundaries are verified. Other active workstreams remain separately
tracked in [Active work](active.md).

## Required verification

- Real-time lending retains its approval, daily-price, appraisal and LTV behavior.
- Earlier-today and earlier-date recording preserve business dates, recording
  timestamps and unknown original actors; missing digital original quotes/policies
  alone do not block a supported timeline.
- Total-only receipts reproduce the confirmed example; partial interest, multiple
  payments, same-day ordering, fees, item allocations and explicit concessions
  either calculate under supported rules or refuse clearly.
- Active, renewed and already-closed histories reconcile atomically, with distinct
  actual cash and physical custody; retries/concurrent attempts create no duplicates.
- A missing old transaction affecting later events cannot silently rewrite them.
- Multiple archive snapshots, opening/history imports and manual entry cannot
  admit the same source loan twice; original evidence/media/export remain intact.
- Balances, as-of reads, reports, current valuation, completeness labels and
  reminder intent agree; no historical admission emits an unintended live action.
- Existing imported opening and native loan regressions pass, together with
  authorization, lifecycle and restricted-role Workspace isolation checks.

Use repository test settings and meaningful domain/boundary tests, then verify
ordinary desktop/mobile review, errors and retry behavior. Update delivery evidence
in Status and the implemented guides without presenting this accepted design as
already deployed.


## UR-06 completeness and communication slice (3 October)

The [transaction coverage decision](../adr/2026-10-03-loan-transaction-completeness.md)
implements immutable per-loan confirmations and incomplete-record reports through
ordinary loan detail. Current debt/risk stays visible with provisional labels;
portfolio totals respect missing paper activity. Reports and borrower statement
exports carry the same status/date. Reviewed repayment/overdue reminders use the
agreed collection balance and revalidate at Notify's provider boundary.

This checkpoint did not complete UR-06. UR-07 subsequently supplies recorded contract
and charged-interest position documents and routine recorded-origin renewal.
A versioned restorable export retaining origins, correction/renewal chains, source
identities and review evidence, imported-opening renewal and auction recovery remain
pending with their existing guards. Local migrations 0043/0044/0045 and deployment
are pending.
