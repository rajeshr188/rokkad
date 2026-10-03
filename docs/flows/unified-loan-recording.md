---
status: accepted-design
owner: project
updated: 2026-10-03
tags: [loans, paper-entry, workflow, historical-evidence, risk]
---

# Record business when it happens or enter it afterward

The current local UR-08–12 completion slices and remaining real-record/release
checks are documented in the [operator and acceptance guide](paper-first-operator-and-release.md).
Earlier dated slices below preserve their original checkpoint boundaries.

The owner accepted this direction and authorized implementation on 2 October 2026.
The numbered sections describe the overall target, not a claim that every path is live.
See the [decision](../adr/2026-10-02-unified-loan-recording.md) and
[delivery plan](../plans/unified-loan-recording.md).

## Current routine paper workflow (UR-07, local)

1. Choose **New loan → Already completed on paper**. Record this loan's original
   number, date, agreed terms and collateral. Deducted advance interest and document
   charge determine its proceeds; confirm physical cash only when known.
2. Add known dated total receipts. Choose outstanding or financially closed. A
   closing settlement does not require identifying a later loan or claiming customer
   handover. Review the reconciled figures and confirm the paper record was checked.
3. Find the admitted loan in the ordinary active/closed lists. Later paper receipts
   and paper closure are available from its detail page. Recheck transaction coverage
   as more paper activity becomes available; monitoring distinguishes provisional data.
4. If an entered active loan is actually renewed through Rokkad, use ordinary **Renew**
   for approval now. If a known linked renewal already happened on paper, choose
   **Record a completed paper renewal**, enter its date/number/terms and actual net cash.
   Retained jewellery transfers to the successor without inventing a customer return.
5. Print a recorded contract or current interest position. These identify entered
   paper facts and current coverage without claiming contemporaneous digital approval.

Unknown earlier/later renewal relationships are not required. The older initial
chain-entry option below remains optional. See the
[clarification](../adr/2026-10-03-independent-paper-loans-and-renewal.md).
Deployment and remaining recovery/portability work are tracked separately.

## First local implementation: existing opening-loan receipts

UR-01 extends **Record repayment** for loans carried forward with a supported
reviewed opening. Production deployment is pending; see the
[implementation checkpoint](../implementation/unified-loan-recording.md).

1. Open the existing loan's repayment screen and select **Record a paper receipt**.
2. Enter the total received, actual receipt date and a receipt or book/page
   reference that distinguishes this payment within the loan.
3. Choose **Preview allocation**. Review the interest and principal split calculated
   at the actual date, then confirm the money was already received.
4. Choose **Record repayment**. Loan history retains the paper reference and actual
   date separately from who entered it and when. Exact retries do not record cash twice.

This initial slice accepts dates after the opening checkpoint with no later
recorded financial activity. Outstanding fees and principal reductions across
multiple principal-bearing items require further agreed rules; interest-only
receipts can cover multiple items. A repayment retains collateral and does not
close the loan. Archive admission remains a later tracked slice.

## UR-03 local entry: complete never-entered paper history

Open **Loans ? Record paper history**, or **New loan ? Already completed on paper**.
Select the existing borrower, original series and matching contract, then enter the
original number, actual date, principal, rate, tenure, cash paid and collateral.
Choose the current monitoring basis separately. No original digital quote, appraisal,
approval or uploaded scan is required; retain a distinct paper book/page reference.

Enter every receipt, carry-forward renewal and full return in actual date/order.
Amount-only receipts allocate agreed interest first, then principal. Confirm the
full-month anniversary rule and the date through which the history is complete.
Preview shows cash, derived allocations, carried principal, final loan/custody states
and any advancement of live numbering counters. Confirmation commits all rows
atomically; an invalid final row leaves no partial active loan. A matching retry
opens the existing result.

Each renewed source becomes closed and links to the next numbered loan. The review
shows principal carried, gross advance, new principal and actual cash in both
directions. Select collateral stayed held or actually returned and repledged. A final
reconciled full return creates an ordinary closed loan. Ordinary details show the
source and completeness cutoff separately from entry time and current coverage.

The initial profile supports one collateral group, no fees/concessions, zero or one
original advance month. UR-03A adds explicit renewal funding: carry remaining
principal with reduction/top-up, or actual full principal repayment and a fresh
advance. Enter the new agreed principal, total cash received, actual cash paid,
old interest deducted from the advance (explicit zero when none), and independent
collateral handling. Actual return/repledge needs the recipient. New-loan advance
interest, fees, concessions, different collateral and capitalization remain outside
this profile. A same-day return/repledge concerns the same collateral group.

For old principal 10,000, interest 200 and new principal 12,000:

| Paper facts | Cash received | Cash paid | Old interest offset | Principal carried | Gross advance |
| --- | ---: | ---: | ---: | ---: | ---: |
| Carry, interest received separately | 200 | 2,000 | 0 | 10,000 | 2,000 |
| Carry, interest deducted from advance | 0 | 1,800 | 200 | 10,000 | 2,000 |
| Actual full repayment and fresh advance | 10,200 | 12,000 | 0 | 0 | 12,000 |

All produce the same new principal and net cash, but different actual cash history.
Do not select a method merely to make net totals match. Retaining collateral alone
does not determine either principal or cash handling.
A receipt on the
anniversary affects the following month; month-end anniversaries clamp to that
month's last day. The same boundary applies to closure at maturity. Every operator
must confirm these exact terms; this is not an assumed universal paper rule.
Further renewal after admission, dependent corrections and archive conversions
remain pending. Current receipts/full return are supported; automatic notices and
auction recovery stay unavailable until completeness integration is complete.

## 1. One workflow, two meanings of an action

JCL and JSK normally use Rokkad while lending. Lakshmi sometimes lends, collects
and closes on paper, then enters those facts later. Both are legitimate workflows.
Lakshmi's clarified backlog starts on **24 September 2026**, and includes later
transactions and closures, not just untouched outstanding loans.

The ordinary loan-entry screen should establish **Has the money already been
paid?** The same distinction applies to receiving a payment, renewal and closure.
An event from earlier today is also a completed action being recorded. Staff may
switch between these approaches on one loan as the business requires.

| Question | Perform the action now | Record an action already performed |
| --- | --- | --- |
| What is Rokkad doing? | Supporting a decision and its execution | Recording a business fact |
| Which terms apply? | Terms approved for this advance | Terms actually agreed with the borrower |
| Which valuation matters? | Evidence required before authorizing this advance | Retained original evidence when known; separate current monitoring |
| What date describes the cash? | Actual payout/receipt date | Actual earlier payout/receipt date |
| Who is identified? | Actor carrying out the action | Current recorder, with original actor separately when known |

Recording a past payout must not instruct staff to pay again, change the loan date
to today, produce an apparent new cash movement today, or imply historical Rokkad
approval. A document generated today must preserve its real generation time and
clearly distinguish the original business dates and paper references.

## 2. Preserve the contract; separate the valuation evidence

Three sets of information answer different questions:

- **Agreed contract:** original principal, item allocations where needed, agreed
  interest rates, accrual convention, rounding, minimum periods, upfront amounts,
  tenure, fees and later agreed changes. These determine debt and settlement.
- **Original lending evidence:** the prices, appraisal, LTV and approval known at
  issuance. These explain the original decision. Preserve supplied evidence and
  identify its source and when it was recorded; absence stays explicit.
- **Current monitoring:** present eligible collateral, current price/appraisal,
  freshness, monitoring limits and current outstanding exposure. These assess risk
  now without rewriting the contract or the original lending decision.

Historical metal prices generally do not determine subsequent interest or cash
allocation. Original contractual interest rules do. A new digital policy created
today must not be presented as a policy that governed a paper transaction then.
Supported recorded terms need a reproducible calculation basis even when no
matching digital policy existed on the original day.

An appraisal-only origination policy uses an assigned collateral value rather
than a metal-price calculation. For example, an appraisal of INR 100,000 with an
80% lending limit permits INR 80,000 under that policy. It still needs an appraisal,
item details and the applicable limit. A lower-of-market-and-appraisal policy needs
both values. Switching policy merely to bypass a historical price requirement
does not solve delayed entry; the recording purpose must be represented explicitly.

## 3. Capture facts and review the timeline in the existing screens

Record the actual loan number, licence/series, matched borrower, dates, collateral,
principal, agreed terms, deductions and net payout to the extent required by the
supported calculation profile. Preserve a source book/page/ticket reference and
current staff confirmation. Retain scans or other supplied evidence; a scan is
not a universal requirement and does not by itself establish financial correctness.

Keep the actual business date separate from the system recording timestamp.
Date-only paper records remain date-only; do not invent a historical time or
attribute the original action to today's recorder. When order within a day affects
the balance, resolve and record that order explicitly.

For a never-entered loan with subsequent activity, prepare the original advance
and all known payments, term changes, renewals and closure in a reviewable draft.
Show the resulting balance and collateral state before one atomic admission.
Renewals need their predecessor/successor relationship and actual settlement/new
advance components; they are not a date change on an existing loan. A draft must
not contribute active debt, send collection reminders or appear as completed cash.

This preparation is within Loans. Staff should not need to author an import file
or use a separate historical archive simply because entry is late. Existing
supported import adapters may share the same domain services.

## 4. Lakshmi's total-only receipts

Lakshmi's paper receipt supplies the **total amount received**. On 2 October the
owner confirmed the normal allocation in this no-fee example:

| Immediately before payment | Amount |
| --- | ---: |
| Principal outstanding | INR 10,000 |
| Interest due under agreed terms at actual payment date | INR 200 |
| Paper receipt total | INR 2,000 |
| Calculated interest allocation | INR 200 |
| Calculated principal allocation | INR 1,800 |
| Principal after payment | INR 8,200 |

Do not require staff to supply a split that was never written on paper. Preserve
the receipt total and reference as supplied facts, and separately preserve the
derived split, rule, inputs and review. Calculate interest as of the actual payment
date using the actual terms and earlier reconciled events, not today's date or
today's interest policy. Subsequent calculations use the reduced principal under
the agreed rules.

The current repayment allocator applies fees, overdue interest, current interest
and then principal. Reuse compatible calculation logic; the owner's answer confirms
interest before principal in the example, not every existing fee or item allocation
rule. Fee priority, exceptional payment purposes, multi-item reductions, overpayments
and concessions need explicit supported semantics before those cases are admitted.

If the total is less than interest due, the supported interest-first rule leaves
principal unchanged and the remaining interest unpaid. An unexplained difference
at a claimed closure must not become a fabricated concession or receipt. Show the
discrepancy and obtain the actual agreed adjustment or correct the underlying terms.
Missing terms that make the split indeterminate keep the timeline in review.

## 5. Keep the rules that protect balances and identity

Admission must reconcile amounts, chronology, supported calculations and current
state. Preserve paper numbering without creating a second operational identity or
silently rewinding the current number sequence. Check source identities and receipt
references as well as number collisions, including across existing imports and
archive snapshots. Signed review, authorization rechecks, locking, atomic writes
and retry safety remain necessary.

Entering a late transaction into an already serviced loan is harder than admitting
a never-entered timeline: an earlier principal payment can change later interest,
allocations or closure. Preview the affected events and require a supported explicit
correction/reconciliation path. Never silently alter completed event evidence or
issued documents. A genuinely new advance still requires current approval even
when its predecessor was recorded from paper.

Financial settlement does not prove physical collateral return. Record each actual
fact and apply the ordinary lifecycle rules to derive the resulting state.

### Reviewed correction of an active paper contract

An administrator opens **Review paper history correction** from the ordinary loan
detail or repayment screen. Select a missing receipt, replacement of a mistaken
receipt, or void of an entry that did not happen. A void is not a refund. For a
replacement, enter all corrected paper facts and the reason; other receipts keep
their original totals and source references. For a void, leave new-receipt fields
blank. Choose an explicit same-day order when needed.

Preview shows each existing dependency, compensations, old/new cash facts,
principal/interest allocations and the resulting current balance. Confirm only
after checking the complete affected paper history. Changed or expired reviews
require another preview; repeat submission returns the existing correction.
Historical balances then show the corrected business dates, while original events
and the present correction remain visible in the loan audit. Receipt documents and
reports identify the correction rather than instructing another collection.

The supported boundary is receipts and anniversary interest on an active admitted
paper contract with one held collateral group. The same rule applies to receipts
after a paper renewal on its active successor. A closed or renewed source instead
shows its closure/renewal dependencies and blocks posting: changing the settlement,
successor agreement or custody needs a broader reconciliation, still pending.
The original records-complete-through date does not advance with this correction.

## 6. Risk monitoring remains available

Outstanding admitted loans participate in ordinary balances, due dates, delinquency
and current collateral risk. The existing implementation couples valuation method
and LTV inputs to origination snapshots; delayed entry needs an explicit monitoring
basis without inventing an original approval. UR-02 stores the separate monitoring choice in the recorded contract snapshot.

Current quotes/appraisals and actual eligible held items supply collateral coverage.
Unknown or stale valuation produces unknown coverage while known debt remains
visible. Missing original appraisal does not prevent obtaining a current appraisal.
Closed loans do not inflate active lending exposure.

Because paper business can continue before entry, record an explicit, scoped
**Paper records entered through [date]** confirmation. Do not infer completeness
from the newest receipt or from today's quote. Reports should expose the cutoff
and scope; reminder eligibility must account for unentered activity. Loan-level
completeness cannot imply that every new loan in the Workspace has been entered.

## 7. Where the loan belongs

| Evidence available | Intended outcome |
| --- | --- |
| Complete supported original history; still outstanding | Ordinary active loan with actual history |
| Complete supported original history; settled and required closure facts reconciled | Ordinary closed loan with actual history |
| Reliable outstanding checkpoint, incomplete earlier transactions | Supported reviewed opening, with earlier history explicitly unavailable |
| Source says closed but transactions/terms cannot establish closure | Retained archive evidence; no invented operational history |
| Material contradiction or unsupported calculation | Pending review with a specific explanation |

**Existing historical archive records can qualify for ordinary closed loans.**
This requires reconciliation and a supported admission path, not merely changing
their status. The old system's mutable loan amount may not be original principal;
a release flag does not supply missing cash amounts or concessions. An import audit
that established faithful retention did not certify every loan's full chronology.

Keep each immutable archive snapshot and its media, add a reviewed link to the
admitted operational loan, and make navigation work in both directions. Admission
must guard the underlying source loan across all snapshots and existing Loans
origins. Reports count each financial event once and use its actual business date;
archive retention and admission are not two separate loans or new lending today.
Bulk eligibility and exact counts require a read-only evidence review first.

## 8. What changes in the architecture

### Correcting a receipt before renewal or closure

Open **Review paper history correction** from the ordinary loan. Enter the missing,
replacement or voided receipt facts. If the loan was renewed or fully closed, also
enter actual cash received, cash paid out, old-interest offset (zero for closure)
and the source confirming those figures. Confirm that the recorded date, numbers,
successor agreement and collateral handover remain correct.

Preview compares original and corrected receipt splits and settlement cash, and
shows linked loans with their balances and custody. A mismatch reports actual and
required amounts; check the paper facts rather than change them just to pass a check.
Successor principal/terms are retained. A receipt correction does not constitute a
new payout, refund or collateral return.

Confirming posts compensation and corrected financial events atomically. Original
documents and custody evidence remain accessible. Screens and regenerated settlement
memos show current financial particulars and their correction source. Later activity
on a linked successor requires a fresh review. Original completeness dates are not
advanced. Contract/custody changes, concessions and partial releases need broader
reconciliation and remain blocked by this command.

For a release in a batch, the loan correction link opens **Review batch history
correction**. Check every member, select the receipts requiring correction and
enter actual closure cash for each changed loan. Leave supported unchanged loans
unselected. Enter the actual combined collection and the source confirming it.
Preview shows each revised allocation and all members' previous/current collection;
confirmation records the entire correction atomically. Any mismatch must be
resolved from source facts. Membership, dates, payer and physical handover remain
as originally recorded. Batch history/detail show the reviewed total alongside
the original; individual release documents identify the correction and batch.

### Admitting a reconciled historical closed loan

Open the retained Historical loan and choose **Review admission to ordinary Loans**.
The usual paper-history entry opens with known source fields filled. Check the raw
archive details and attachments, supply original agreed terms and missing facts,
and identify the supporting records. For each archived payment, retain its source
ID as the transaction reference and explicitly select receipt or final closure.
Enter actual cash and the actual collateral-return recipient; never enter a balance
adjustment merely to force reconciliation. Existing Party mappings must agree.

Preview checks all snapshots of that source, original facts and calculated debt.
Conflicts stay unresolved until the evidence is reconciled. Confirming records the
history and source link atomically. A supported reconciled history becomes an
ordinary closed loan. Historical list/detail and ordinary loan detail link to each
other; source documents/media remain accessible. Already admitted sources link to
their existing loan. This first archive profile covers one closed loan without a
renewal chain. Owner/import authority and the corresponding loan actions apply.

### Shared core

Keep the current Loans core and extend its supported entry paths. Separate
origination decision validation from validation of recorded facts; represent actual
dates and source provenance; reconcile drafts through canonical calculation and
posting services; connect qualified archive evidence; expose transaction completeness
alongside valuation freshness. Preserve existing behavior for ordinary real-time
loans and existing imported openings while adding explicitly supported profiles.

History preservation means recording what happened, when it happened, who entered
it and subsequent corrections. It must not require every historic fact to have
already existed digitally. The current implementation restriction is the coupling
of past-fact recording to contemporaneous digital approval evidence; removing only
a price check would leave contract, replay, numbering and monitoring gaps unresolved.


## Check later paper activity before relying on reminders

From ordinary loan detail select **Check paper transactions**. Review the paper
book and receipts, enter the checked-through date and source reference, and choose
whether all activity is entered or some remains missing/unresolved. Preview the
loan activity, confirm, then refresh Loan health. For today this describes activity
checked up to the review; later digital entries require rechecking. For migrated
openings it covers the checkpoint onward, not missing pre-checkpoint receipts.

Debt and collateral monitoring remain visible while paper records are incomplete,
with a provisional warning. A fresh metal price does not confirm the paper books,
and checking the books does not provide a fresh valuation. Closed loans leave
active exposure and their coverage does not expire merely because another day ends.

After complete coverage and risk refresh, use Loan health's reviewed repayment or
overdue reminder. Consent and delivery settings still apply. A changed receipt,
withdrawn consent, newer paper review or date rollover can block a queued intent
before delivery. Recheck/reassess and prepare a fresh message; the obsolete intent
is retained. Checking records alone never sends a message. Ordinary subsequent
renewal and recorded contract/interest-position copies are implemented locally.
UR-11/12 now supply original-identity native recovery and current recorded-origin
auction locally; release acceptance remains pending in the
[plan](../plans/unified-loan-recording.md). Native recovery preserves the complete
ordinary-Loans graph and file bytes in a matching database. It is distinct from
cross-Workspace portable JSONL admission.

## Paper-book progress and later corrections

From the Loans list use **Paper-book progress** to record a book, day, last page
and progress note. A checkpoint tracks entry work, not a verified loan balance or
proof that every paper loan has been entered. **Review selected loans together**
accepts up to 50 unambiguous numbers and retains each loan's own checked-through
confirmation. An unresolved loan keeps monitoring provisional.

A paper closing number is optional. If none was recorded, Rokkad assigns a system
recording number and labels it as such. A paper-only financial closure can retain
unknown customer handover. Later use **Confirm customer handover** with actual
date, recipient and supporting reference. Financial closure stays unchanged and
the previously issued release copy remains accessible.

An administrator can **Correct original paper terms** after checking the source.
Review original date/principal/rate, corrected proceeds, replayed receipts and any
affected settlement. For a recorded renewal successor, also enter its predecessor's
actual settlement cash and confirm its custody/numbering facts. Rokkad compensates
old calculations and retains revised contract/opening evidence. A paired date
change restates dated custody evidence; it does not perform another handover.
An unchanged approved successor remains governed by its original approval.

For one paper closure, **Correct paper closing facts** reviews an erroneous date,
reconciled settlement and confirmed return recipient. Its confirmed/unspecified
custody basis remains unchanged. Newly available handover evidence uses handover
confirmation. Shared-batch date/custody changes and arbitrary custody reversals
require a wider profile. Recheck transaction coverage after any financial correction.

Imported opening loans can also use ordinary **Renew**. For a decision performed
now, select a current contract version for the successor and satisfy current
approval. For a known completed paper renewal, select the version matching its
actual agreement and enter actual dated terms/net cash. The imported checkpoint
and its original coverage remain intact; neither path reconstructs earlier history.
