---
status: discovery
owner: loans
updated: 2026-10-01
tags: [loans, khata, scenarios, planning]
related: [../adr/2026-10-01-khata-agreement-design.md, future-work.md, ../domain/loans-mixed-metal-origination.md]
---

# Khata agreements: living requirements and scenario plan

## Scope and decision record

The owner authorized the first local foundation/calculator slice after round 11.
That backend slice is implemented; full servicing and production activation remain
pending. See the [checkpoint](../implementation/khata-foundation.md).
The next [opening backend slice](../implementation/khata-opening.md) is also
implemented locally: received collateral, photos, approval and staged withdrawals.
The [interest collection slice](../implementation/khata-interest-collection.md)
adds completed monthly charges and oldest-due receipts with immutable allocations.
The [agreement-change slice](../implementation/khata-agreement-changes.md) adds
approved term activation and principal repayment within a formal reduction;
outgoing custody and settlement are now implemented in the
[custody/settlement checkpoint](../implementation/khata-custody-settlement.md).
The [correction checkpoint](../implementation/khata-corrections.md) adds whole
receipt compensation and unhanded exchange cancellation with dependency checks.
Unsupported correction coverage, operational screens/documents, shared summaries
and recovery remain pending; no production activation.
The scenario inventory still includes undelivered servicing and integration.
This is the working scenario inventory, not a claim that every case is resolved.

The [proposed ADR](../adr/2026-10-01-khata-agreement-design.md) holds the confirmed
business rules and proposed architecture. Update both when later answers change
the contract. Keep recommendations distinct from confirmed decisions.

The [technical design](../architecture/khata-technical-design.md) translates these
decisions into candidate records, commands, permissions and test cases. Annual
leap-day handling, same-day revisions and other identified technical edges remain
proposals; this design checkpoint adds no new owner-confirmed business decisions.

**1 October 2026, discussion round 1:** Owner confirmed staged collateral-backed
withdrawals; interest on the full agreed limit from the first withdrawal;
monthly/annual interest payments; agreed limit increases and reductions through
agreement renewal; no revolving partial-repayment/redraw cycle; and substitution
based on at least equivalent valuation, irrespective of weight. An increase from
INR 1 crore to INR 1.5 crore changes the interest base from its agreed effective
change. Mid-period calculation was open in this round; round 2 below resolves
the split and refines the original strict-equivalence requirement.

**1 October 2026, discussion round 2:** Owner confirmed old-limit interest before
an increase's effective date and new-limit interest from that date; collateral
coverage for actual withdrawals at the agreed LTV; partial principal repayment
only during formal reduction/renewal; and the same current approved rates for
both sides of an exchange. Value-short exchanges warn and proceed by default.
The workspace owner may choose strict at-least-equivalent value enforcement.
Borrowers may make up shortfalls with later collateral. Monthly or annual
payment is selected at agreement time, with interest paid at period end, in
arrears. Calendar boundaries, quoted rate units and day-count rules remain open.

**1 October 2026, discussion round 3:** Monthly and annual due dates use the
agreement anniversary: 10 October to 10 November, or to 10 October next year.
An annual payer closing after four months owes only four months of interest.
For exchanges, use one workspace-owner choice: allow with a warning/flag even
if incoming value is short or the account exceeds agreed LTV, or disallow when
either check fails. Keep shortfall handling simple; no separate top-up deadline
workflow for now. The owner also chooses warn or block for overdue interest.
Affected overdue actions and its default remain open. The user asked for a
clearer explanation of rate units; round 4 below resolves that question.

**1 October 2026, discussion round 4:** Staff always enter the agreed rate as a
monthly percentage in the initial version. Monthly or annual payment remains
independent. The owner explicitly rejected interpreting annual payment as an
annual rate. Choosing monthly/annual rate units at entry is deferred to a future
extension, not part of the initial implementation scope.

**1 October 2026, discussion round 5:** Owner selected simple interest, actual
days for part-month closure after a full first-month minimum, and collection
of that minimum at month end rather than upfront. Short months clamp to their
last day and later dates restore the original anniversary. Overdue block mode
blocks withdrawals and exchanges, while payments, deposits and settlement remain
available. Limit changes/renewals keep the khata number and payment anniversary,
append an agreement revision and require repayment of principal above a reduced
limit. First-month collection for annual payers and early closure before the
first due date need clarification; neither was silently decided here.

**1 October 2026, discussion round 6:** Owner accepted recommendations 1-4:
annual payers' first-month minimum is included in the annual bill; closure before
month one ends collects the full minimum at closure; actual-day fractions use
actual days between monthly anniversaries, with dated splits for reductions as
well as increases; and changed workspace warn/block policies apply to subsequent
operations on existing khatas. Completed transactions remain unchanged. There is
no fixed maturity: the account continues until borrower settlement. The last
recommendation did not settle exact day inclusion/exclusion or rounding, so
those details in the walkthrough remain explicitly proposed.

**1 October 2026, discussion round 7:** Owner accepted warn as the overdue
default, with overdue beginning the day after the due date; grouped exchanges
are allowed. Replacement must be the same metal, with no gold/silver substitution.
The owner is unsure about standalone excess returns but confirms returns during
reduction and settlement. Initial scope therefore proposes no standalone return
action. Newly agreed monthly rates may change through dated agreement revisions,
preserving prior calculations. Reduction-return mechanics below are proposals,
not an assumed approval of a new coverage exception.

**1 October 2026, discussion round 8:** Owner confirmed a mandatory retained-LTV
check for collateral returns during reduction. Remaining eligible collateral
must cover the actual principal after repayment at the agreed LTV. Exchange
warning mode cannot override a failed reduction-return coverage check.

**1 October 2026, discussion round 9:** Owner explicitly accepted all five
screen-review decisions D1-D5: day boundaries and monthly paise rounding; one-time
opening minimum across revisions; non-replenishing drawing entitlement; oldest-due
interest allocation with advance/excess payments deferred; and clearance of due
interest before reduction returns while unbilled interest stays on schedule.
The owner also requires existing flexible products and loans in JCL, JSK and
Lakshmi to remain unchanged. Khata is a distinct offering in the same Loans area;
it does not replace or convert their existing products. Architecture remains
proposed and this confirmation is not an instruction to implement.

**1 October 2026, discussion round 10:** Owner accepted a separate khata series;
existing authorised loan approvers can approve opening and limit/rate changes.
There are no existing digital khatas to import. Paper accounts may exist, but
customers will start new khatas with agreed terms and record the collateral;
no historical-import feature is required. Routine entries use today's business
date; earlier entries need a separately reviewed workflow. Additional charges,
penalties and funding/repledging remain outside the first release. Recording
collateral alone never creates a payout; paper-era money must not be labelled
as newly paid cash. Architecture/detail work and implementation remain separate.

**1 October 2026, discussion round 11:** Owner accepted both independent and
licence-associated khata series. The workspace owns each series and its counter;
licence is optional and must belong to the same workspace when selected. Khata
numbers remain unique across the workspace, irrespective of licence. Freeze the
association, including none, after the first issued account number. Changing it
later requires a new series with a distinct prefix; old numbers and evidence stay
intact. Both modes retain agreed khata terms, permissions and collateral rules.
Documents capture lender identity without requiring licence display fields;
reports include independent accounts and a "No licence associated" filter.
This supersedes the earlier mandatory-licence design, not ordinary-loan setup.

## Amounts the account must distinguish

| Term | Meaning |
| --- | --- |
| Agreed limit | Maximum agreed borrowing amount in the effective agreement |
| Total principal advanced | Gross principal actually advanced across withdrawals; show cash deductions separately if supported |
| Principal outstanding | Actual advances less recognized principal settlement; never the unused limit |
| Unused drawing entitlement | Remaining contractual entitlement; repayments do not automatically replenish it |
| Collateral-backed availability | Additional actual withdrawal supported by held collateral at the agreed LTV; the undrawn limit itself needs no collateral |
| Drawable now | Amount permitted by both entitlement and coverage, subject to operational restrictions |
| Interest base | Full effective agreed limit once the first withdrawal starts the agreement |
| Interest accrued / due / paid | Separate financial facts with dates and revision evidence |
| Collateral value | Supported assessed value of items currently held; retain valuation dates and sources |
| Exchange shortfall | Outgoing value less incoming value when positive, at the same current approved rates; not cash debt |
| Account coverage shortfall | Actual principal above the amount held collateral supports at the agreed LTV; separate from exchange shortfall |

For an unchanged agreement without principal settlements, unused entitlement is
the limit less total advances. Do not use limit minus outstanding as a general
formula: that would silently create revolving credit. Reductions and renewals
use the confirmed D3 rule: add agreed limit increases to unused entitlement and
subtract decreases down to zero; principal repayment alone never restores it.

Illustration only, with no fees or deductions and a hypothetical 1% monthly rate:

| Step | Limit | Principal outstanding | Interest base | Charge for a complete month at these terms |
| --- | --- | --- | --- | --- |
| Prepare agreement, no withdrawal | INR 1 crore | INR 0 | Not started | INR 0 |
| First withdrawal of INR 20 lakh | INR 1 crore | INR 20 lakh | INR 1 crore | INR 1 lakh |
| Further withdrawal of INR 30 lakh | INR 1 crore | INR 50 lakh | INR 1 crore | INR 1 lakh |
| Accepted collateral exchange, no cash | INR 1 crore | INR 50 lakh | INR 1 crore | INR 1 lakh |
| Further withdrawal of INR 50 lakh | INR 1 crore | INR 1 crore | INR 1 crore | INR 1 lakh |
| Agreed increase by INR 50 lakh, no new withdrawal yet | INR 1.5 crore | INR 1 crore | INR 1.5 crore | INR 1.5 lakh |
| Withdraw INR 10 lakh under the increased agreement | INR 1.5 crore | INR 1.1 crore | INR 1.5 crore | INR 1.5 lakh |

Actual-day fractions use actual days between monthly anniversaries. Include
start/effective day and exclude next anniversary/closure day. Sum exact segments
per monthly period and round once to paise using half-up; annual bills sum months.
A mid-period increase must split old/new limit segments at its
effective date, with no overlap or skipped day. Due dates follow the agreement
anniversary, clamping to the last valid day in short months and restoring the
original day afterward. Annual leap-day handling still needs an explicit rule.

## Confirmed monthly rate entry and period boundaries

Rate units answer how much interest is charged for a unit of time. Payment
frequency answers when the borrower pays it. The initial rate-entry convention
is always a monthly percentage; payment frequency remains a separate choice.

Illustration only: for an unchanged INR 1 crore limit with simple interest,
1% per month produces INR 1 lakh for a complete month. Monthly payment collects
INR 1 lakh each monthly anniversary. Annual payment collects INR 12 lakh on the
annual anniversary. A rate quoted as 12% per year gives the same whole-year
amount under this simple example. Closing after four complete months would
collect INR 4 lakh, less interest already paid. Simple interest is now confirmed;
the actual-period denominator, boundary days and rounding are confirmed in D1.
The annual-rate comparison
explains the distinction; annual-rate input is outside initial scope.

Confirmed interface: "Interest rate (% per month)" plus a separate "Pay interest"
choice of Monthly or Annually. No rate-unit selector in the initial version.
Agreement evidence and issued documents must retain the monthly unit explicitly.
Annual payment must never turn 1% per month into 1% per year. A future annual-rate
input must preserve earlier agreements' meaning and use its own explicit unit.

Payment periods start with the first withdrawal. No calendar month-end or
financial year-end schedule is implied. Annual payment is not a full-year minimum
charge. A full first-month minimum is confirmed. Monthly payers pay at the first
monthly anniversary; annual payers include it in the annual bill. Closure before
month one ends collects the full minimum at closure. Later broken months use
actual days over actual days between monthly anniversaries. Annual leap-day
handling remains open. D2 fixes the minimum once per account from opening limit
and rate; charge the greater of that minimum and actual first-month segmented
interest. Withdrawals, exchanges and agreement revisions never restart it.

## Fictional walkthrough for review

This example uses monthly payment, simple interest at 1% per month, an initial
INR 1 crore limit and 80% LTV. Every withdrawal has enough accepted collateral.
No fees, penalties or unpaid earlier dues are assumed. The account retains one
number, KH-EXAMPLE, and its payment anniversary on the 10th.

Prorate by actual elapsed days divided by days between the original monthly
anniversaries, as confirmed. Include the effective start day and exclude the next
anniversary or closure day; round the summed monthly charge to paise using half-up.
These boundary-day and rounding choices are now confirmed through D1.

| Date | Action | Result |
| --- | --- | --- |
| 10 October 2026 | First withdrawal INR 20 lakh | Actual principal INR 20 lakh; interest starts on the full INR 1 crore limit |
| 20 October / 5 November | Further withdrawals INR 30 lakh / INR 50 lakh | Actual principal reaches INR 1 crore; interest base stays INR 1 crore |
| 10 November | First monthly interest paid | INR 1 lakh; no upfront deduction and no principal change |
| 25 November | Agree limit increase to INR 1.5 crore | New revision; actual principal stays INR 1 crore until another payout; next due date stays 10 December |
| 26 November | Exchange outgoing value INR 30 lakh for incoming value INR 28 lakh | Warn mode permits INR 2 lakh value shortfall; strict mode blocks. Interest and principal do not change |
| 1 December | Deposit enough collateral and withdraw INR 20 lakh | Actual principal INR 1.2 crore; limit and interest base remain INR 1.5 crore |
| 10 December | Pay November-December interest | INR 1 lakh x 15/30 + INR 1.5 lakh x 15/30 = INR 1.25 lakh under the illustrated boundary-day convention |
| 10 December | Formally reduce limit to INR 1.1 crore; repay INR 10 lakh principal | Actual principal and limit both INR 1.1 crore; new agreement revision, same account and anniversary |
| 20 December | Close account and return held collateral through settlement | INR 1.1 crore principal plus INR 1.1 lakh x 10/31 = INR 35,483.87 interest; prior dues assumed paid |

The reduced-limit example applies the lower limit from its effective date,
consistent with the owner's confirmed symmetric treatment of increases/reductions.
For the exchange, for example, total held value of INR 150 lakh becomes INR 148
lakh after the exchange. That still supports INR 118.4 lakh at 80% LTV, covering
the then INR 100 lakh principal. Before the later INR 20 lakh withdrawal, a further
INR 2 lakh of accepted collateral restores total value to INR 150 lakh, supporting
INR 120 lakh principal. If resulting LTV failed during an exchange, warn mode
would still allow it; that permission does not extend to the cash withdrawal.

Annual-payment comparison: at an unchanged INR 1 crore limit and 1% monthly,
twelve full months total INR 12 lakh, and four full months total INR 4 lakh.
No interest-on-interest applies. The annual bill includes month one; no separate
month-one collection is due. Any earlier settlement/payment must be credited so
the first-month minimum is never charged twice. With an unchanged limit and rate,
closure within the first month collects INR 1 lakh minimum interest at closure.

The account has no fixed maturity. Continuing to another annual anniversary
does not require a new account or make all principal automatically overdue.
Interest obligations continue until settlement; default/enforcement rules still
need their own design and are not inferred from open-ended duration.

## Reduction returns and settlement

The owner confirmed that borrowers can take collateral back during a reduction
or settlement. A standalone return of excess collateral has not been selected.
Keep the initial experience within those two operations, alongside the already
confirmed same-metal exchange workflow.

Proposed reduction preview with the confirmed coverage rule:

1. Enter the new agreed limit and effective date; retain the account number and
   payment anniversary. Show the old/new interest bases and dated calculation.
2. Show actual principal outstanding and any principal repayment required to
   bring it down to the new limit. A limit reduction above actual principal need
   not invent a repayment. Display interest dues separately.
3. Let staff select whole held collateral items for return. Revalue retained
   items using approved current valuation evidence and show remaining coverage.
4. Require retained eligible value x agreed LTV to cover the actual principal
   remaining after repayment. Block a return that fails this check, including
   when exchanges use warning mode. This mandatory coverage rule is confirmed.
5. Review the revision, actual repayment, item selection and custody readiness
   together. Confirm monetary and agreement evidence with linked return records;
   actual physical handover must be separately recorded and retry-safe.

Illustration: a fully drawn INR 1 crore khata holds collateral worth INR 1.5 crore
at 80% LTV. Reducing the limit to INR 80 lakh requires INR 20 lakh principal
repayment. Retained collateral must be worth at least INR 1 crore under the
confirmed rule. Staff can select items worth up to INR 50 lakh for return, provided
the retained items pass the coverage check. This is a value ceiling, not an
instruction to cut an item or to pay its value in cash. Interest dues are separate.
Interest afterward uses the reduced INR 80 lakh limit from the effective date.

At full settlement, collect actual principal and applicable interest, cancel
unused entitlement and return all eligible held items. Ordinary custody/readiness
checks still apply. No retained-loan LTV is needed once debt is fully settled.
Clear due/overdue interest before a reduction return, as confirmed in D5.
Not-yet-due accrued interest stays on its existing schedule. Full settlement
collects all applicable interest. The exchange overdue policy does not waive D5.

## Exchange policy and shortfall follow-up

Confirmed default: show a passive warning/flag and let staff continue when
incoming value is below outgoing value or resulting account LTV exceeds the
agreed LTV. The owner may choose disallow mode, which requires at least equivalent
incoming value and compliance with account LTV. Keep this a single exchange
policy. Equal weight or exact equality of values is never required. Both values
use the same current approved rates, with purity and measurements reflected.

One-for-many and many-for-one exchanges are allowed. Compare aggregate values
within the same metal and retain each item's identity. Gold must replace gold;
silver must replace silver. Warning mode allows value/LTV shortfalls but never
cross-metal substitution. Mixed-metal operations must not net a gold deficit
against a silver surplus; review separate same-metal groups.

Proposed example: outgoing collateral is worth INR 10 lakh and incoming
collateral INR 9 lakh. Warning mode allows the exchange with a visible INR 1 lakh
exchange shortfall; strict mode blocks it until sufficient collateral is added.
This does not create INR 1 lakh of cash debt or alter interest. The account may
still meet LTV if it had excess coverage; the two shortfalls are not interchangeable.

Proposed evidence: retain original values, actor, date and policy mode; show the
shortfall and current coverage without hiding them. Later collateral deposits
remain allowed. The owner requested simple warn-or-disallow handling for now;
promised top-up dates, reminders, dedicated tracking and partial-cure allocation
are deferred. Do not erase historical facts when prices move. No owner approval
step per exchange is implied by warning mode. Missing/invalid valuation or
missing physical collateral is not automatically covered by this known-value
shortfall permission.

Further withdrawals must still satisfy the agreed LTV for actual principal after
the payout, as well as unused entitlement. The exchange exception does not waive
that rule. For exchanges, warning mode explicitly permits an LTV breach,
including an existing coverage shortfall; disallow mode blocks a noncompliant
result. Independent custody, identity and authorization requirements remain.

Overdue-interest policy is a separate owner-selected warn/block choice. Block
mode prevents additional advances and exchanges, while allowing receipt of
payments, collateral top-ups and valid settlement. That scope is confirmed.
Default to warn. Unpaid interest becomes overdue the day after its due date,
with no implicit grace period. Independent restrictions
still apply: a warning for overdue interest does not waive withdrawal LTV.

## Proposed operator journey

1. Prepare borrower, khata series (optional licence association), limit, monthly rate, payment frequency,
   coverage rules and agreement evidence. No fixed maturity date is required.
2. Review/approve terms and initial collateral. Record the first actual
   withdrawal and agreement start together. Failed payout recording must not
   leave an active interest start without its source withdrawal.
3. Show account totals, interest dues, current collateral and a dated activity
   history. Later withdrawals each have their own receipt and authorization.
4. Receive/appraise additional collateral before authorizing another withdrawal.
   A deposit alone creates neither a payout nor a higher limit.
5. For an exchange, select outgoing items and record incoming items. Show values
   on the agreed comparable basis, resulting coverage and custody readiness.
   Apply warning mode by default or the owner's strict mode. Record actual
   receipt and return separately, with linked exchange and shortfall evidence.
6. For a limit change, preview old/new terms and their effective date. Confirm
   borrower agreement and authorized approval. Preserve the earlier revision,
   same khata number and anniversary. Settle principal above any reduced limit.
7. Collect monthly or annual interest in arrears against dated dues. A payment does not by itself
   release collateral, renew terms or create drawing capacity.
8. At closure, settle the required actual principal and interest, cancel
   unused entitlement and record return of all eligible held items. Exact final
   interest and default outcomes remain discussion items.

Screen names and revision display conventions remain proposals. Existing loan
approvers approve opening and limit/rate changes; no owner-only approval is added.
The same khata number and payment anniversary through revisions are confirmed.

## Scenario inventory

**Confirmed** means the owner settled the business outcome. **Proposed** means
a recommended control. **Open** means an answer is needed. Mixed rows state both.

| ID | Scenario | Outcome or decision needed | State |
| --- | --- | --- | --- |
| K01 | Terms prepared; no withdrawal | No interest starts. Decide approval expiry and cancellation of undrawn agreements. | Confirmed / Open |
| K02 | First withdrawal is much less than the limit | Interest begins on the whole limit. Preserve actual payout separately. | Confirmed |
| K03 | More collateral arrives, with no request for money | Record custody; no automatic withdrawal or limit change. | Proposed |
| K04 | Further withdrawal within the limit | Held collateral must cover actual principal after withdrawal at the agreed LTV, within unused entitlement. The undrawn limit needs no coverage. | Confirmed |
| K05 | Limit exhausted or requested withdrawal exceeds it | Require agreed increase before extra payout; no automatic overdraft. Decide whether increases before exhaustion are allowed. | Confirmed / Open |
| K06 | Limit rises from INR 1 crore to INR 1.5 crore | New interest base is INR 1.5 crore from the effective change, even before new money is taken. Principal changes only on payout. | Confirmed |
| K07 | Increase takes effect partway through a billing period | Old limit before effective date; new limit from that date; confirmed D1 actual-period days and rounding. Same number and anniversary. Corrections to previously finalized/paid periods remain design work. | Confirmed / Open |
| K08 | Limit is reduced but remains above actual principal | Agreement revision preserves number/anniversary; dated split applies. Subtract the decrease from unused entitlement down to zero; repayment never independently restores it. | Confirmed |
| K09 | Requested reduced limit is below principal outstanding | Require repayment of the difference through reduction/renewal; retain actual payment evidence, same khata number and anniversary. | Confirmed |
| K10 | Borrower offers a partial principal payment without renewal | Require formal reduction/renewal for a partial principal payment. No automatic redraw entitlement. | Confirmed |
| K11 | Monthly versus annual interest | Monthly percentage, simple interest, anniversary dues. Annual bill includes the first-month minimum without a separate first-month bill. Short months clamp then restore the original day. Annual leap-day handling remains open. | Confirmed / Open |
| K12 | Early closure, including within the first month/year | One-time opening minimum under D2; use higher actual interest when applicable. Later actual-period fractions use D1 boundaries/rounding. Annual payer closing after four months pays four months. | Confirmed |
| K13 | Interest payment is missed or partly paid | Default warn; overdue next day. Owner can block withdrawals/exchanges, not payments, deposits or settlement. No capitalization; partial payments allocate oldest-due-first under D4. Advance/excess payments, added fees and penalties are outside initial scope. | Confirmed |
| K14 | Lower-weight, higher-purity replacement is worth at least as much | Weight alone must not reject exchange. Compare both sides at current approved rates. Account-LTV failure follows the same owner exchange warn/disallow policy. | Confirmed |
| K15 | Replacement has equal weight but lower value | Default: passive warning and continue, with later collateral top-up allowed. Owner-selected strict mode: block until at least equivalent value. | Confirmed |
| K16 | One item replaced by several, or several by one | Allow grouped exchanges using aggregate current value within the same metal; retain every item identity and movement. | Confirmed |
| K17 | Replacement is worth more than outgoing items | No automatic cash payout, limit increase or interest change. Decide whether improved coverage permits a separate withdrawal within unused entitlement. | Proposed / Open |
| K18 | Original and replacement appraisals use different dates or metal rates | Revalue both sides at the same current approved rates; retain original historic appraisals separately. | Confirmed |
| K19 | Gold is offered for silver | Reject cross-metal substitution even in warning mode. Replacement must be the same metal. | Confirmed |
| K20 | Market value falls after a compliant withdrawal | Keep the agreed interest base and actual debt. Decide revaluation, top-up requests, shortfall controls and any release restrictions. | Open |
| K21 | Equivalent replacement arrives but the account is already undercovered | Warn mode permits the exchange and shows the coverage shortfall. Disallow mode blocks until resulting coverage meets agreed LTV. | Confirmed |
| K22 | Incoming items fail appraisal or never arrive | No completed exchange or outgoing handover. Record rejected/temporary custody and its return if relevant. | Proposed |
| K23 | Incoming items accepted but outgoing handover fails | Keep both items' actual custody states and a pending handover. Retry without duplicate payout or movement. | Proposed |
| K24 | Outgoing item is funded/repledged, missing, sealed or disputed | Funding/repledging is excluded from first release. Missing/disputed/unavailable items still require custody readiness; do not pretend an item has been handed back. | Confirmed / Proposed |
| K25 | Customer wants collateral back without substitution | Reduction return requires mandatory actual-principal LTV and clearance of due/overdue interest. Unbilled interest stays on schedule. Exchange warnings waive neither check. Settlement returns allowed; standalone excess return not selected. | Confirmed |
| K26 | Full settlement before all of the limit was drawn | Principal to settle is actual outstanding, not unused entitlement. Decide final interest; close entitlement and record physical return. | Confirmed / Open |
| K27 | Another monthly/annual anniversary arrives | No fixed maturity; continue until borrower settlement. Interest becomes due by selected frequency; no automatic principal maturity, fresh drawing entitlement or erased arrears. | Confirmed |
| K28 | Renewal while prior interest is unpaid or prepaid | Decide settlement/credit carry-forward and whether arrears block renewal. Preserve period and revision attribution. | Open |
| K29 | Same submission retried, or two staff withdraw/exchange at once | Exactly-once result; lock/recheck entitlement, valuation version and item availability at confirmation. | Proposed |
| K30 | Backdated withdrawal, exchange or limit amendment | Routine first-release operations use today's business date. Earlier transactions require separate review; no unrestricted backdating or silent rewrite of finalized interest/custody. | Confirmed |
| K31 | Incorrect payout, payment, amendment or exchange needs correction | Whole interest receipts and unhanded exchanges have bounded local compensation with immutable source links and dependency checks. Payout/amendment/settlement/physical-return and complex correction remain unsupported; never invent cash or item return. | Implemented locally / limited |
| K32 | Licence expires, staff access changes, or workspace is restricted | Apply established action boundaries. Decide khata classification for later draws and amendments; no general bypass. | Open |
| K33 | Default, enforcement or auction | Define eligibility, affected items, valuation/allocation and proceeds/shortfall treatment before enabling it for khata. | Open |
| K34 | Existing khata must be imported/exported/restored | Historical/paper import excluded; users start new agreements and record collateral. Native exact-identity disaster recovery is implemented locally with versioned source/media evidence and reconciliation; do not route through ordinary-loan import. Real recovery rehearsal remains a pilot gate. | Confirmed / Implemented locally |
| K35 | Borrower brings collateral later to cure an allowed exchange shortfall | Allow later top-up. Keep initial policy to warn/disallow; dedicated top-up deadlines, reminders and allocation workflow deferred. Deposit valuation/evidence still needs design. | Confirmed / Open |
| K36 | Owner changes warning/strict setting while agreements or exchange previews exist | Current workspace policies govern subsequent operations on existing khatas; completed transactions remain intact. Record applied policy; proposed implementation must recheck stale previews. | Confirmed / Proposed |
| K37 | Several value-short exchanges accumulate | Apply owner's warn/disallow exchange policy to the resulting account coverage. Retain movement history and visible shortfall; no separate overdue-top-up gate in initial scope. | Confirmed / Proposed |
| K38 | Borrower and lender agree a new monthly rate | Append a dated agreement revision; use the new rate from its effective date and preserve earlier calculations, account number and anniversary. | Confirmed |
| K39 | Workspace opens khata without a licence record | Use an independent workspace-owned series and its own counter. All workspace, approval and collateral requirements still apply. | Confirmed |
| K40 | Independent and associated series coexist | Each series owns its counter; khata numbers are unique across the workspace. Reject a foreign-workspace licence. Ordinary counters remain untouched. | Confirmed |
| K41 | Staff changes licence association after an account number was issued | Reject adding, removing or replacing the association, including after cancellation. Create a new series with a distinct prefix; keep existing numbers and evidence. | Confirmed |
| K42 | Reports/documents contain independent khatas | Include both modes in workspace totals; expose no-licence filtering; preserve lender identity/address and omit inapplicable licence details. | Confirmed |

## Next discussion round

Reduction-return LTV is confirmed as a mandatory check. Do not reopen that choice
or apply exchange warning exceptions to it. The owner selected screen/calculation
review next. The [screen review](khata-screen-review.md) now proposes eight screen
areas and five concrete choices: date boundaries/rounding, first-month
minimum across revisions, unused entitlement, interest allocation and due-interest
clearance for reduction returns. All five are now explicitly confirmed in round 9.
Use that review alongside the remaining decision inventory. No implementation begins
merely because the routine business rules are largely captured.
The next planning step has prepared the [delivery design](khata-delivery-design.md):
repository evidence, record responsibilities, transaction boundaries, integrations,
four implementation/pilot stages after design closure, and verification/recovery.
D1-D5 are confirmed; architecture and implementation authorization remain separate.

Round 10 settles separate series, existing approver authority, new accounts only,
today-dated routine entries and excluded charges/funding. The
[delivery scope and checklist](khata-delivery-design.md#first-release-scope-and-implementation-checklist)
consolidates these decisions. Remaining detail work covers annual leap-day dates,
concrete schema/sequence mapping, document contracts, compensating corrections,
default handling and native export/restore. Regression preservation of existing flexible loans in the three
named workspaces is an explicit delivery requirement, not an already passed test.
Unanswered questions remain open; examples are not implicit approval.

## System impact to review before choosing implementation

- **Product and calculation:** separate khata contract from ordinary tranche
  economics. Define rate precedence and permitted agreed-rate overrides.
  Freeze rate units, frequency, day count and agreement revision. Ordinary
  rules are not automatically khata rules. Simple interest, full first-month
  minimum and later actual-day treatment are now explicitly chosen for khata.
- **Financial evidence:** advances create principal; limit amendments do not.
  Interest accrual, due dates, payments and settlement remain distinct. Avoid
  duplicate charges at revision boundaries. No general-ledger subsystem.
- **Custody:** original item history, photos, labels, storage and linked exchange
  receipts remain traceable. Database success cannot establish physical handover.
- **Read models:** borrower totals show actual debt; separate sanctioned limits
  and undrawn commitments. Due reports, statements, risk and dashboards must not
  count the limit as payout or the unused amount as principal overdue. Track
  collateral shortfalls separately from monetary dues; a passive warning must
  not make an undercovered account appear fully covered.
- **Documents:** define agreement, revision consent, withdrawal receipt, exchange
  receipt and statement contents. Preserve exact issued bytes and revision links.
  Determine numbering, licence records and applicable form mapping before rollout;
  this planning record does not certify legal treatment of the proposed contract.
- **Security and operations:** reuse action authorization and tenant boundaries.
  Any new workspace-owned tables need direct ownership, forced RLS, registry
  coverage and adversarial isolation checks. Design concurrency and idempotence.
- **Portability:** include agreement revisions, movements, dues and evidence in
  export/restore design. Preserve ordinary product and import contracts unchanged.

## Readiness and eventual delivery gates

1. Resolve calculation examples and scenario outcomes with the owner. Record
   explicit deferrals and their blocked actions; no hidden policy defaults.
2. Review the specific schema/service proposal, account numbering, lifecycle,
   document samples and compatibility boundaries. Accept or revise the ADR.
3. Foundation/calculator implementation was explicitly authorized after round 11.
   Track delivered scope separately from the complete product and pilot gates.
4. When authorized, build a coherent fictional end-to-end path: opening, staged
   draws, periodic dues, exchange, limit increase/reduction and closure. Extend
   tests from the agreed matrix, including month ends, leap years, annual periods,
   same-day changes, stale quotes, retries, concurrency and compensation.
5. Verify tenant isolation, ordinary-loan regressions, document accuracy and
   export/restore before a named workspace pilot. Define migration, rollout and
   recovery evidence before any production activation.
