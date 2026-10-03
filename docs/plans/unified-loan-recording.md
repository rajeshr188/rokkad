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
| UR-13 | Additional actual paper profiles established from representative evidence; no assumed waivers, capitalization or item-allocation rules | Awaiting business examples; supported baseline remains available |
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
