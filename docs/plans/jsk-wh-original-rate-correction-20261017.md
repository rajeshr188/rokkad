---
status: evidence-review
owner: loans
updated: 2026-10-17
tags: [loans, corrections, legacy, interest, review]
related: [../implementation/jsk-wh-interest-verification-20261016.md, ../contracts/loan-agreement-correction-v1.md]
---

# JSK WH original-rate correction: evidence before application

The owner confirms 1.1% monthly was intended from each original date, and on
17 October selects paper/payment-record review with uncertain balances held.
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

## Paper/payment evidence to establish

For each reviewed loan, bind the paper/source reference and reviewer to its
original terms, original and cutover dates, principal/item identities, first-month
payment evidence, later interest payments and accepted unpaid checkpoint.
Record unknown facts as unknown. Retain the original source's 2% rows and the
owner's clarification separately. Do not scale saved interest by 1.1/2 or infer
receipts from the difference between recognized and unpaid interest.

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

## Compatibility implementation after evidence review

1. Prepare a reviewed old/new checkpoint proposal for each evidence-complete loan.
   Show which interest was recognized, unpaid, paid or advanced; do not create
   missing pre-cutover transactions. Keep uncertain loans out of the apply set.
2. Extend existing audited services for retained opening/2 and native policy-1
   semantics. Today's opening writer requires /4 or /5; native agreement correction
   requires policy 2. Removing these guards alone is invalid: the implementations
   consume different continuation shapes and calculation/advance rules.
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
   financial effects and exceptions. Only a separately authorized production apply
   may use verified backups and locked/idempotent ordinary correction services.
   Changed financial evidence invalidates risk; valuation/monitoring policy stays
   independent. Recheck new activity and verify postconditions before refresh.

The current completed slice is cohort identification and evidence-review preparation.
No financial correction or compatibility deployment has been performed. The next
input is verified paper/payment evidence, not another broad rate-field update.
