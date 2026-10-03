---
status: accepted
owner: project
updated: 2026-10-02
tags: [loans, paper-entry, origination, history, risk]
---

# One Loans workflow for actions performed now and recorded afterward

The [3 October clarification](2026-10-03-independent-paper-loans-and-renewal.md)
makes independent paper-loan entry the primary workflow. Unknown renewal ancestry
is not required; known subsequent renewals use ordinary servicing.

## Context and decision

JCL and JSK generally decide, pay and print through Rokkad at the time of business.
Lakshmi also conducts business on paper and enters it later. Its backlog from
24 September 2026 includes subsequent payments, renewals and closures. The owner
accepts both operating models and selected support within the existing Loans
workflow, backed by the same canonical financial records.

This is the accepted overall design. Implementation was subsequently authorized
on 2 October and begins with the [dated receipt slice](../implementation/unified-loan-recording.md)
on existing opening loans; broader admission and data conversion remain pending.
The [workflow](../flows/unified-loan-recording.md) explains the business rules;
the [delivery plan](../plans/unified-loan-recording.md) tracks each slice.

## Recording versus authorizing

Each action distinguishes **perform now** from **record an action already
performed**, including actions performed earlier today. This is an action-level
choice, not a permanent Workspace or loan type. Both paths use Loans-owned domain
services, events, balances, Party identity, authorization and Workspace isolation.

Real-time lending continues to validate the proposed advance against applicable
origination policy, appraisal, prices and LTV. Recording an earlier advance
preserves its actual contract, amounts, dates and source. It does not claim that
Rokkad approved that advance or substitute today's terms for the original terms.
Missing contemporaneous digital quotes, policies or appraisals alone must not
prevent admission of an otherwise supported financial history. Recorded exceptions
and missing evidence remain visible; recording is not a compliance certification.

Separate three responsibilities: the agreed contract governs debt; original
valuation/approval evidence explains the lending decision; current monitoring
assesses present exposure and collateral. Freeze inputs and calculation versions
actually used. Never manufacture an original policy, price, approval or appraisal.
Retain actual business dates, their precision, recording actor/time and source
references separately. Unknown original actors and times remain unknown.

## Financial and source integrity

Validate actual cash, principal, agreed calculation terms, chronological events,
receipt allocation, explicit concessions and financial/custody transitions.
Missing inputs needed to derive debt require resolution, not invented defaults.
An attachment is not universally compulsory: proportionate source references and
staff confirmation can support entry; relevant evidence is retained when supplied.
Current access control and tenant isolation remain mandatory.

Lakshmi records only the total received on its paper receipt. The owner confirmed
that, with INR 10,000 principal and INR 200 interest due, INR 2,000 received pays
INR 200 interest and reduces principal by INR 1,800. Store the total as the paper
fact and the split as a calculation using agreed terms, actual payment date and
the supported allocation rule. The example does not establish fee priority,
special payment instructions, concessions or overpayment treatment.

A never-entered loan with a complete, supported timeline may be admitted through
ordinary screens as active or closed after reconciliation. Prepare its events in
draft and commit the reviewed timeline atomically; do not temporarily expose an
incorrect active balance or trigger historical notifications. A reliable opening
checkpoint remains appropriate when earlier detailed transactions are unavailable.
Existing completed events remain immutable. A newly discovered earlier transaction
requires dependency review and explicit supported correction, not silent insertion
that changes later completed calculations.

## Archived loans

An archived loan may qualify for an ordinary closed loan when its original terms,
financial history and closure/custody facts can be reconciled under a supported
profile. Existing archive acceptance or a source status of closed is insufficient.
Missing original valuation alone is not a reason to refuse financial admission.
No claim is made that every retained JCL/JSK/Lakshmi snapshot can qualify.

Preserve the immutable archive, source documents and media. Add an explicit,
auditable admission relationship to the operational loan; never replace the
archive JSON. Guard the underlying source-loan identity across multiple snapshots,
opening imports, complete-history imports and prior manual admission. A retry must
not create another loan, receipt or cash movement. Browsers and reports must expose
the relationship without double counting the source and admitted loan.

## Monitoring and consequences

An admitted outstanding loan joins ordinary balance, delinquency and collateral
monitoring. Assign an explicit current monitoring basis without portraying it as
the original lending policy. Missing or stale current valuation means unknown
coverage, not zero collateral or zero debt. Financial settlement and physical
return remain separately evidenced; ordinary closed loans leave active exposure.

Paper entry requires visible transaction completeness: an explicit scoped
confirmation of records entered through a date, separate from quote/appraisal
freshness. Reports and reminder eligibility must respect that boundary.

Extend existing models/services with the smallest coherent change. This decision
does not introduce a second financial ledger, generic policy engine or blanket
validation bypass. Exact schema, supported calculation profiles and correction
boundaries require implementation design and tests.

### Initial shared storage decision (UR-02, 2 October)

Extend existing immutable snapshots rather than introduce another origin table or
financial ledger. `LoanPolicySnapshot.basis` distinguishes an origination policy
from recorded contractual rules with a separately identified monitoring selection.
`PawnLoanDisbursalSnapshot.basis` distinguishes an approved decision from a recorded
payout. Approval remains mandatory for the approved basis and must be absent for
the recorded basis. Existing rows retain their previous meaning through defaults.

The recorded disbursal and its ordinary DISBURSAL event retain matching
`recorded-origination/1` evidence: source reference, actual date with DAY precision,
unknown or explicitly supplied original actor, original terms and collateral,
and monitoring selection/date/reason. Normal creation actor/time record the present
entry. Interest fields describe the agreed contract; valuation method and LTV
fields describe the explicitly selected monitoring basis, not retrospective
approval. No original quote, digital policy or digital appraisal is invented.

This is a storage and reader foundation, not authorization to admit a loan through
raw model creation. The future ordinary admission command must reconcile the
whole history, check authority, numbering, source identity, custody and duplicate
attempts atomically. Until supported, approval-based ticket/export and payout
reversal paths explicitly refuse recorded origins. Normal servicing readers use
the same financial records; full entry/completeness/reminder integration remains
required before enabling paper-origin admission.

For future implementation, this decision supersedes the assumption in the
[26 September earlier-payout ADR](2026-09-26-earlier-payout-and-daily-price-confirmation.md)
that recording always requires digital origination evidence to have existed on
the actual day. Its deployed restrictions still apply until replaced and verified.
It extends the [historical archive ADR](2026-09-13-historical-closed-loan-archive.md)
with a planned admission relationship; immutable retention remains in force.

### Atomic admission and anniversary reads (UR-03, 2 October)

Use one ordinary form and a signed review of a rolled-back admission calculation,
then repeat and commit the reconciled aggregate atomically. Reuse existing loan,
event, schedule, release and renewal records. Record original numbering with locked
counter reservation; do not silently consume a second new loan number for paper.

The owner confirmed next-anniversary principal reductions and principal carry into
a new numbered loan while collateral remains held. The bounded profile explicitly
confirms full-month charging on the anniversary itself; it does not change existing
opening/native calculations. Store cumulative anniversary recognition as immutable
ordinary interest events. Read actual variable-principal due/maturity amounts from
the same history, retaining the original schedule as immutable contractual evidence
and allocation capacity. Future projections cannot consume later as-of transactions.

This local slice blocks unsupported dependent corrections, further renewal, notices,
auctions and exports until the remaining unified-recording stages support them.
Completeness confirmation applies to the entered history through its stated date,
not the entire Workspace or unentered later paper business. See the
[implemented profile and limitations](../implementation/unified-loan-recording.md).

### Renewal principal clarification after the initial UR-03 slice

The owner's retained-collateral answer did not prohibit additional lending on
renewal. The customer may retain the outstanding principal, repay part of it or
take a top-up. New principal equals old outstanding principal less principal paid
plus the additional advance, under the new agreed terms. Carry and additional
advance must remain distinct from actual cash movements and interest settlement.
No interest capitalization is implied by this clarification.

The initial zero-top-up paper writer is therefore incomplete for the agreed scope.
Extend the existing renewal records and ordinary entry/review in UR-03A, preserving
custody links and explicit receipt/payout or offset evidence. The owner subsequently
accepted both actual principal repayment/fresh advance and carried principal.
Separate interest receipt and interest offset from the advance are supported facts,
not Workspace-wide alternatives. Collateral custody is independent of funding.
This changes the supported workflow scope, not the immutable financial architecture.

### Explicit renewal cash and custody (UR-03A)

Reuse PawnLoanRenewal and its canonical settlement/opening events. Freeze versioned
`recorded-renewal-cash/1` evidence in both events and the immutable renewal snapshot.
For carry, principal paid is max(old minus new, zero), advance is max(new minus old,
zero); for full principal repayment/fresh advance they are old and new respectively.
Carry is old principal minus principal paid. Required cash received equals principal
paid plus old interest minus explicit offset; cash paid equals advance minus offset.
Offset cannot exceed either old interest or the advance. No implicit concession,
capitalization, new-contract interest deduction or fictitious gross cash is allowed.

The successor opens once through RENEWAL_OPENING; an extra DISBURSAL would double
count debt. The existing top_up_amount column represents the gross advance in this
profile, including the full fresh advance on redraw; readers label it accordingly.
Same physical collateral retains predecessor identity. When held, source custody
transfers; when actually returned/repledged, dated renewal custody events record
source IN_VAULT to WITH_CUSTOMER and successor WITH_CUSTOMER to IN_VAULT. Preserve
the recorded return recipient, original date precision and unknown original actor.
Different collateral or a separate later repledge remains outside this entry profile.
Financial settlement interest includes the offset; it is not all physical cash.
