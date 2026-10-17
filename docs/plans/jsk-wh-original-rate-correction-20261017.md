---
status: correction-preparation
owner: loans
updated: 2026-10-17
tags: [loans, corrections, legacy, interest, review]
related: [../implementation/jsk-wh-interest-verification-20261016.md, ../contracts/loan-agreement-correction-v1.md]
---

# JSK WH original-rate correction: confirmed basis and preparation

The owner confirms 1.1% monthly was intended from each original date. The earlier
17 October instruction selected paper/payment-record review with uncertain
balances held. The owner subsequently clarifies that all WH loans originated on
paper at 1.1%, with the first month's interest paid upfront; 2% was inherited
from the Workspace default during migration. The owner also confirms no later
transaction on the 685 imported, now-active loans under discussion.
The owner initially selected "Keep this proposal to 685", then explicitly
superseded that limit: "actually fix all active loans carrying wrong 2 % rate in
wh series of jsk". The current scope is all 826 active affected loans: 824 imports
and two native policy-1 agreements. The owner separately confirms 1.1% at
disbursal for WH02145 and WH02146 in response to the original-net-proceeds review;
retain their saved document charges and correct the original advance/proceeds,
without recording a new cash movement.

This is the business basis for preparing their correction; do not require
individual paper records merely to reconfirm those stated facts. Retained 2%
source rows establish what was imported, not the actual paper agreement. This
latest all-active fix request authorizes the scoped production correction after
compatible release, recovery and rehearsal checks.
This is an original-terms correction, not a later concession. Use the ordinary
shared agreement/checkpoint correction boundary; do not add a JSK-specific loan
type, correction screen or alternative balance calculator.

## Frozen read-only review

At 23:37:30 UTC on 16 October (05:07:30 IST, 17 October), restricted production
runtime repeats the JSK/WH active gold-at-2% selection inside repeatable-read,
read-only SQL. The role is neither superuser nor RLS bypass. No correction
preview, write, repricing, refund or monitoring-policy change is executed.

The cohort remains 826 loans: 824 opening/2 and two native policy-1 contracts.
685 openings have nonzero unpaid interest. All 824 frozen opening documents say
`first_month_paid=True`; this is retained evidence to review, not proof of the
amount of cash collected. No new financial event kinds appear in this selection.
Zero opening interest on the remaining 139 is not automatic evidence that an
original-rate correction needs no payment/advance reconciliation.

The owner explicitly approves the scoped production-to-local review list after
automatic review initially rejects the export for missing payload/destination
consent. It is saved privately at
`.tmp/jsk-wh-correction-review-20261017/cohort.private.json`: loan numbers/IDs,
contract/upfront flags, hold reasons and source hashes only; no borrower/contact
details or monetary amounts. The aggregate-only `summary.json` and read-only
helper remain adjacent. Cohort digest:
`99f1f86fb1da61bb3cb6899b4193b55f0c31c254426d29810955c3c21137d57a`.

Every row is held with `application_allowed=False`. Hashes identify this review
snapshot; they are not confirmation tokens or proof that every funding/custody
dependency was checked. Ordinary locked services must re-evaluate the full graph
and current activity before any later application.
These are private proposal flags, not operational holds on loans or collections.
The frozen flags predate the owner's subsequent clarification above.

## Remaining reconciliation

The fresh all-active check at 00:18:30 UTC selects every active WH loan with an
item or header rate of 2%, independently of metal: exactly 826, all with gold items
at 2%. All have a sole financial origin and no connected funding, renewal, auction
or out-of-vault collateral. The 685 nonzero-interest imports retain identical
membership and hashes. Another 139 imports have zero opening interest but require
rate correction for later continuation. All 824 pure opening recalculations pass.
The two native records retain original licence revisions, one advance period,
no accruals and simple/full-month policy 1 at quantum 0.01.

Use the owner's confirmed original rate and first-month payment basis, together
with retained principal, original/cutover dates and payment evidence, to prepare
old/new positions. Preserve the paid first month as covered at 1.1%; the erroneous
2% imported rate does not establish that cash was collected at 2%. The absence of
post-migration transactions alone does not establish all pre-migration payments.
Seek additional paper/payment evidence only for a concrete contradiction or a
missing fact needed to determine unpaid interest. Leave that uncertain component
unchanged rather than infer a payment or apply a blanket hold to the whole cohort.
Retain the original source's 2% rows and the owner's clarification separately.
Do not scale saved interest by 1.1/2 or infer receipts from the difference between
recognized and unpaid interest.

For opening/2, retain its inclusive original-anniversary, original-principal,
aggregate HALF_EVEN whole-rupee rule. The first-month-paid premise is part of
this published profile. If the paper review contradicts it, hold the loan for a
separately supported evidence contract; changing the flag or promoting the
profile to current monthly rules would change its economic meaning.

For the two native loans, establish actual payout, deducted fees and advance
interest separately from the corrected agreement. Preserve policy-1 calendar,
rounding and period behavior. A change to monthly rate cannot establish a new
payout, refund, extra paid period or customer credit. Any unreconciled cash or
advance difference stays held for explicit supported treatment.

## Compatibility implementation and release sequence

1. Prepare a reviewed old/new checkpoint proposal for each evidence-complete loan.
   Show which interest was recognized, unpaid, paid or advanced; do not create
   missing pre-cutover transactions. Keep uncertain loans out of the apply set.
2. Extend existing audited services for retained opening/2 and unserviced native
   policy-1 semantics. Serviced policy-1 agreements still require connected review.
   The prior opening writer required
   /4 or /5; merely removing the guard is invalid because the continuation shapes
   differ. The implementation now distinguishes aggregate carry facts, preserves
   the retained validator/rule, reuses the typed form and signed write boundary,
   and versions the portable correction graph as servicing bundle 8. Native policy
   1 retains its existing period calculator/calendar, actual reviewed original
   proceeds and immutable approval; it is not promoted to policy 2.
3. Test synthetic anniversary/rounding cases, first-month coverage, zero/nonzero
   checkpoint interest, actual cash preservation, source immutability, authorization,
   stale review, exactly-once retry, RLS and newly connected history rejection.
   Verify canonical reads, documents, reports and portable correction recovery.
   Preserve published old profile meanings and version any expanded wire contract.
4. Rehearse the evidence-complete selection on an authorized isolated copy, with
   old/new positions and explicit holds. Compare unchanged financial results at
   the old rate before accepting corrected-rate differences. This is separate from
   enabling compatibility or deploying code.
5. Present a concrete correction proposal with its exact selection, source state,
   financial effects and exceptions. The owner's later all-active fix request now
   authorizes this scoped apply, using verified backups and locked/idempotent services.
   Changed financial evidence invalidates risk; valuation/monitoring policy stays
   independent. Recheck new activity and verify postconditions before refresh.

The completed preparation includes the confirmed expanded selection, all 824 pure
old/new calculations and local service/reader support. The final 49-case correction
selection passes; earlier overlapping selections pass 100 servicing and 213
portability cases. See the [implementation record](../implementation/aggregate-checkpoint-corrections-20261017.md).
No financial correction or compatibility deployment has been performed. The owner
has now requested the actual all-active correction and confirmed the two native
advance/proceeds basis. Compatible release and isolated production-data rehearsal
must precede application; a pure proposal is not a service confirmation token.
