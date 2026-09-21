---
status: active
owner: project
updated: 2026-09-12
tags: [loans, portability, legacy, reconciliation]
---

# Legacy source reconciliation worksheet

The representative worksheet is prepared for the owner-selected `jcl` source.
It helps settle the actual agreed calculation and balance evidence before the
[opening contract](../contracts/loan-opening-position-mvp.md) gains financial writes.
It does not change any source selection, validate real opening balances or activate
servicing. The [offline opening validator](../contracts/loan-opening-review-v1.md)
continues to hold missing financial information for review.

## Reproduce the source comparison

The existing bounded offline command now accepts an explicit comparison date and
timezone alongside opening preparation:

```powershell
.venv314\Scripts\python.exe manage.py preview_legacy_dump `
  --dump rokkaddb_prod_full_2026-04-10.dump `
  --pg-restore "C:\Program Files\PostgreSQL\17\bin\pg_restore.exe" `
  --source-schema jcl `
  --source-namespace 6ca968d6-2647-4dbb-8e39-24f0c1a12ed6 `
  --propose-skip-incomplete-collateral --prepare-openings `
  --reconciliation-as-of 2026-04-09 `
  --reconciliation-timezone Asia/Kolkata `
  --output-dir .tmp/legacy-reconciliation-jcl-next `
  --settings django_project.settings.dev
```

`reconciliation.json` is written before the overall COMPLETE marker. It records
source namespace/schema, archive and exclusion-selection fingerprints, the inspected
commit, explicit comparison timestamp assumptions, sample reasons and exact source
loan/item/payment/release records. It is `legacy-reconciliation-worksheet/1`, not a
canonical import profile. Every sample remains `import_ready: false`; reviewed
principal, interest, fees, rule and evidence start null.

The command emits JSON for reproducible comparison. The first pilot additionally
has a locally generated Excel workbook at
`outputs/legacy-reconciliation-jcl-20260912/jcl-reconciliation.xlsx`:

- **Owner review:** six decisions and nine active examples plus one released control,
  with amber cells for owner responses, evidence and proposed reviewed balances.
- **Comparison:** inspectable formulas for the two gross-interest expressions,
  their difference, due expressions and stored-payment component diagnostics.
- **Source:** original numbers/IDs, dates, amounts, tenure, individual items and
  payments. Source sums join on exact loan source IDs, not printed loan numbers.

The Excel workbook is an operator review artifact, not an upload template; no XLSX
round-trip into opening documents or approval is implemented. Its date-derived
month/day inputs are a fixed comparison snapshot. Amount formulas recalculate;
regenerate the command output for another date, rather than editing timestamps
and assuming frozen month counts update. Blank reviewed balances remain unknown.
The application command does not depend on the spreadsheet authoring runtime.
Private worksheets and source artifacts have local ignore rules and must not be
committed. There is no database access, SQL execution or production write.

## Calculation meaning

Expressions were transcribed from commit
`c9fb81bc70adafa1d942721d642bfb2b38953f41`, not imported or executed as legacy code:

| Expression | Inputs and arithmetic |
| --- | --- |
| Model gross interest | UTC-aware `relativedelta` completed calendar months times stored loan monthly money, rounded to whole currency with Python Decimal half-even semantics (`models/loan.py:201-212`) |
| Report gross interest | Whole elapsed days, then `ceil(days / 30.44) - 1`, times stored monthly money, whole-currency numeric half-away-from-zero rounding (`managers.py:100-135`) |
| Model due comparison | Item principal sum plus model gross interest minus **all stored payment amounts**, following `get_loanamount`, `total` and `due` (`models/loan.py:154-164,233-238`) |
| Report due comparison | Stored loan principal plus report gross interest, without payment deduction (`managers.py:135`) |
| Component diagnostics | Item principal minus stored principal payments; model gross interest minus stored interest payments. These are review arithmetic, not approved outstanding balances. |

The comparison is through the selected date's end in the supplied business timezone,
converted to UTC for the inspected timestamp arithmetic. A released control uses
its release timestamp, or the comparison timestamp if earlier. It is never a retained
active candidate. Stored payment totals deliberately include all stored rows to show
the old due expression; payments after the comparison are counted separately in
JSON. This is not a reconstruction of which rows existed at an earlier date.

The report divisor is reproduced with exact Decimal `30.44`; PostgreSQL execution
and deployed SQL type coercions have not been certified. Whole-day extraction,
month ends, leap days, ties and the negative report result on an origination day
must not be silently normalized into today's Loans policy. Agreement between the
two expressions does not prove either is contractually correct. Source snapshot,
code deployment and missing payments remain separate evidence questions.

## Pilot findings at the illustrative date

The initial comparison uses **9 April 2026, Asia/Kolkata** (the day before the dump
filename date) solely to make differences concrete. The filename does not establish
actual snapshot coverage. Neither this date nor a final cutover has been approved.

- All 2,448 retained active loans have **zero payment rows** in this dump. There is
  no active `jcl` payment example anywhere in the source; absence of rows does not
  prove there were no receipts, waivers, advance coverage or external records.
- The gross-interest expressions differ on 99 retained active loans at this instant.
  This is a date-specific expression comparison, not 99 newly identified bad loans.
- Ten unique samples cover the source mismatch, largest expression difference,
  Gold/Silver/Bronze, multiple items with different rates, day 29–31 billing dates,
  oldest/newest loans and largest principal. Overlapping reasons share one example.
  The tenth is a released payment control outside active migration.
- For `R06845`, monthly source money 1,800 and 30 completed calendar months produce
  model gross interest 54,000. The report's 913 days produce 30 rounded-up months,
  then subtract one month: 52,200. Difference: 1,800. No value is selected as the
  agreed rule merely because it is higher/lower.
- For `R07743`, stored loan principal is 21,216 versus item principal 20,400, and
  loan monthly interest is zero versus item monthly interest 408. Both conflicts
  belong to one source-error loan. Its zero gross-interest comparison is not a
  reviewed zero-interest agreement. Reconcile original evidence; do not auto-repair.
- Released control `R02725` has stored payment 18,540, split into principal 9,000
  and interest 9,540. At its release timestamp the model due comparison is zero;
  the report due expression remains 18,540 because it does not deduct payments.
  This illustrates the expression difference and does not certify complete history.

## Owner responses received (2026-09-12)

Read the saved workbook's `Owner review!D9:E14` and `G19:K28` without modifying
the workbook. The owner explicitly supplied these responses; blank evidence and
per-loan balance cells remain blank. The wording below is preserved verbatim.

| Cell / topic | Owner response | Established meaning and remaining boundary |
| --- | --- | --- |
| D9 / Interest rule | month starts from the loan date to next month same date,so if loan date is 10 jan 2026 then month ends at 10 feb, | Monthly boundaries follow the loan-date anniversary, with the first month completed on the next month's same date. This does not select the 30.44-day report approximation. Partial-month collection, month-end dates and rounding remain unspecified. |
| D10 / Payment coverage | no receipts/waivers don’t exist anywhere else,if a loan has a release means it was paid and closed | Owner states there are no separately held receipts/waivers and that a source release means paid and closed. Preserve this owner-attested closure meaning even without a payment row. It does not provide an exact missing settlement split or manufacture complete history. |
| D11 / Rehearsal cutover | I don’t understand this | No cutover date or balance basis approved. Explain the handover date in ordinary language; the April dump remains trial input. |
| D12 / Maturity and grace | ok | Acknowledges preserving original due terms; supplies no concrete maturity/grace values. Do not turn a zero source tenure into a new three-month term. |
| D13 / Collateral weights | bronze is a new kind of metal we missed | Bronze is a distinct required source metal, not an approved silent OTHER mapping. Its handling needs a bounded Loans/Rates review; gross/net weight meaning remains unanswered. |
| D14 / Exceptions | ok | Acknowledges holding/reconciling R07743. No corrected amount or evidence was supplied. |

The monthly anniversary answer must be kept precise: January 10 to February 10.
It does not authorize recognizing a completed month on February 9 merely because
an internal period interval is stored with an inclusive February 9 end. The
opening validator's period representation is not yet an implemented servicing
policy; align actual recognition timing with the agreed anniversary in later work.

For the pilot, absence of active payment rows plus the owner's statement is useful
coverage evidence. Principal/item conflicts, advance coverage, recognized interest,
fees and date-specific balances still require reconciliation; do not fill every
blank financial field with zero. The owner need not populate technical JSON or
understand all workbook terminology. Ask one concrete business example at a time.

### First-month collection clarified in chat (2026-09-12)

For the example of a 10,000 loan at 2% monthly, issued January 10 and released
January 20, the owner answered verbatim:

> for 10000 we collect 200 as interest and 10 as document charge at disbursal and when released on jan 2o we collect only 10000

This establishes 200 first-month interest and 10 document charge collected at
disbursal, then principal-only collection of 10,000 at January 20 release. The
first-month interest is not charged again at that release. The example provides
no prorated first-month refund. It does not establish subsequent partial-month
treatment, month-end anniversaries, rounding or the rules for every source loan.
The 2% rate and 10 charge are this example's values, not new global defaults.

Absence of stored LoanPayment rows is compatible with upfront interest/charges
being collected. Do not interpret it as proof that no money was ever collected.
Migration must preserve the already-paid first-month coverage and settled document
charge without fabricating old repayment events or importing them as unpaid interest/
fees. The owner has not specified whether 10,000 is handed over and 210 collected
separately, or 210 is deducted and net cash of 9,790 handed over. Net cash remains
unconfirmed; principal in the example remains 10,000.

### February 20 release clarified in chat (2026-09-12)

Asked how much would be collected at February 20 release for the same January 10
loan, the owner answered verbatim: **10200**.

This establishes collection of 10,000 principal plus 200 additional interest at
that release. Together with the upfront 200 interest and 10 document charge,
total interest collected across this example is 400 and the document charge is
collected once. The additional interest is not a daily-prorated fraction at February
20. It does not yet establish the first date on which that additional 200 becomes
payable, any boundary-day grace, or treatment of all possible partial periods.
Ask for the first release date that would require 10,200 before selecting a generic
started-month rule or adopting an existing legacy calculation expression.

### First additional-interest date clarified in chat (2026-09-12)

Asked for the first release date requiring 10,200 rather than 10,000 on the
January 10 loan, the owner answered verbatim: **feb 11**.

The upfront first-month interest therefore covers release through February 10
inclusive. February 11 requires the full additional 200, consistent with the
February 20 example. No additional document charge is part of either example.
Preserve this date boundary; neither charging the additional amount on February
10 nor delaying it until the next completed month matches the supplied cases.
Short-month anniversaries and subsequent boundaries still need explicit examples.
These are collection rules, not yet implemented accrual-recognition instructions.

### January 31 short-month boundary clarified in chat (2026-09-12)

Asked when additional monthly interest first becomes payable for a January 31,
2026 loan, the owner answered verbatim: **march 1**.

First-month upfront coverage therefore includes February 28, 2026, with the next
full month's interest payable from March 1. This establishes the first short-month
boundary. It does not distinguish subsequent anniversaries calculated from the
original January 31 date from dates carried forward from the shortened February
boundary. Clarify the next additional monthly charge before choosing between those
period-construction rules. No loan date or billing schedule is changed by this note.

### Original anniversary restored after February (2026-09-12)

Asked for the first release date requiring 10,400 instead of 10,200 for the same
January 31 loan, the owner answered verbatim: **april 1**.

The confirmed examples now distinguish the calendar construction: calculate each
monthly boundary from the original loan date, shorten to the month's last day
when needed, and restore the original day in a later month that has it. Do not
carry February 28 forward as a permanent anniversary. For this example, release
through February 28 requires 10,000, March 1 through March 31 requires 10,200,
and April 1 first requires 10,400. The initial 200 interest and 10 document charge
were separately collected at disbursal and are not collected again in these sums.

Collection increases on the day after the inclusive anniversary boundary. A future
named rule must implement that boundary explicitly; merely selecting the offline
validator's existing ORIGINAL_ANNIVERSARY descriptor does not establish matching
recognition/collection timing. Upfront fee/interest cash handling and monetary
rounding remain separate unanswered questions. These examples cover an unchanged
principal and do not specify a partial-principal-repayment workflow.

### Net cash handover confirmed (2026-09-12)

Asked how much cash is handed over on the 10,000 loan after collecting the 200
interest and 10 document charge, the owner answered verbatim: **9890**.

The owner immediately corrected that answer verbatim: **i meant 9790 sorry**.
This resolves the discrepancy: 10,000 minus 200 interest minus 10 document charge
equals 9,790 cash handed over. Both charges are deducted at disbursal in this
example. Principal remains 10,000; the net cash is not the principal balance.
The earlier 9,890 was corrected by the owner, not automatically repaired. These
amounts do not become global defaults or fabricated source disbursal/payment rows.

### Source weight meaning confirmed (2026-09-12)

Asked whether the old app's recorded item weight includes stones and other
non-metal parts, the owner answered verbatim: **yes**.

The owner subsequently corrected that answer verbatim:

> oops i meant the weight recorded was nett weight with out stones or other parts

The correction supersedes the earlier gross-weight interpretation. The supplied
legacy weight is **net item weight, excluding stones and other non-metal parts**.
Preserve it as net weight for the selected legacy source; do not deduct stones
again. This does not mean 100% pure-metal weight: source purity is a separate
input. Gross weight and removed non-metal weight remain unknown; do not invent
either or copy net into gross without evidence. The offline candidate adapter
has not yet been changed to apply this source-specific mapping. No source numeric
value or existing workbook was changed during this clarification.

### Interest rounding examples received (2026-09-12)

The owner gave the following answers in chat:

| Question | Verbatim answer |
| --- | --- |
| Amount collected for calculated interest of 148.20 and 148.50 | 148 |
| Amount collected for calculated interest of 148.80 | 149 |
| Amount collected for calculated interest of 149.50 | 150 |

Interpreting the first response as applying to both amounts, these examples match
nearest-whole-rupee rounding with exact half-rupee ties to the even rupee
(`ROUND_HALF_EVEN`): 148.20 -> 148, 148.50 -> 148, 148.80 -> 149, 149.50 -> 150.
This matches the inspected legacy model's Decimal `round()` behavior. Preserve the
examples explicitly in the pilot rule's acceptance cases; do not replace them with
always-up, truncation or half-up rounding. The examples establish an amount-rounding
rule, not the stage of aggregation across items/months or fractional payment handling.
Review those calculation details against source behavior in the bounded implementation.

## Acceptance and next step

The previous worksheet checkpoint passed 53 focused database-prohibited tests, including eight new source-comparison
tests for month ends, timestamp boundaries, rounding differences, negative report
results, selection/source preservation, explicit released controls and command output.
The workbook was recalculated, every sampled interest result and item-principal sum
compared to independent Python results, and source-change/zero-input checks restored.
Formula-error scan found none; all three sheets were rendered and visually reviewed.
Native Microsoft Excel execution was not tested. These checks validate the worksheet,
not the underlying financial agreements.

The owner responses now establish original-date anniversaries, short-month clamping,
restoration after February and collection increases after the inclusive boundary.
Net cash handover is confirmed at 9,790, and the corrected source weight meaning
is net weight excluding stones/non-metal parts. Rounding examples match nearest
whole rupees with half-even ties. The **bounded named legacy-rule calculation and
its acceptance tests**, with source-specific net-weight preparation, are now
implemented as described below. This is preparation work, not financial activation.
Gross-weight availability remains a separate migration evidence question. Explain the
eventual handover date without requiring
the owner to choose a final production date for this rehearsal. Establish the
remaining rehearsal balance basis and
resolve the exceptional record, original due terms, weights and remaining custody/
valuation evidence. Implement only the agreed named rule and opening evidence path;
do not grow a generic formula engine or resume optional Party history filtering.

## Implemented owner-rule preparation (2026-09-12)

This section records the version 1 checkpoint. The subsequent owner clarification
and current version 2 behavior are described in the next section.

`loans/services/legacy_interest.py` owns the pure collection rule
`original-anniversary-upfront-inclusive/1`. It counts original-date monthly
anniversaries strictly before the business comparison date. The first month is
paid upfront. Each short month clamps independently; the original day returns in
later months. The result supplies additional months, illustrative additional
interest and the next collection increase date. It does not post events, calculate
accounting revenue, populate an opening or alter current Loans servicing.

`round_rupees` implements the four owner examples with Decimal HALF_EVEN.
Because the owner has not specified aggregation timing, monetary collection
calculation accepts only whole-rupee monthly charges. In the adapter, every item
must independently have a whole-rupee charge matching its principal times rate;
fractional charges are held even if their sum is integral. This permits multiple
whole-rupee items without choosing an unconfirmed rounding stage. Payment rows,
source errors and unsupported dates/amounts prevent a monetary illustration.
Calculations assume unchanged original principal, first-month coverage paid and
no later collections; those assumptions are displayed and do not certify balances.
Dates are converted to the explicitly supplied business timezone before applying
anniversaries. Inputs are bounded, with dates limited to a 100-year review span.

`--owner-profile jcl-owner/1` is an explicit opt-in on the existing offline preview.
It requires reconciliation date/timezone and the existing opening/selection flags.
It accepts only namespace `6ca968d6-2647-4dbb-8e39-24f0c1a12ed6`, tenant `jcl`.
It copies structured item weight into candidate **net** weight, preserves purity,
and records `owner-clarifications-2026-09-12:jcl-net-weight` as evidence.
Gross remains null; the profile does not invent stones, valuation, custody or
remaining principal. Other sources retain the generic unknown-weight behavior.

The existing `reconciliation.json` retains both old source expressions and adds
separate `owner_rule_diagnostics` for all retained active loans. A new
`owner-rule-review.html` lists the collection illustrations and holds, links to
opening evidence review and clearly identifies the rehearsal assumptions.
Every diagnostic remains `import_ready: false`; reviewed openings stay empty.
Both report files are written before the preview COMPLETE marker. The owner-edited
Excel workbook is neither regenerated nor changed.

The April 9, 2026 / Asia-Kolkata rehearsal produced:

- 2,448 retained active candidates: 1,700 calculated illustrations, 747 held for
  fractional aggregation and one held for existing source errors (R07743).
- 2,470 source weights mapped to net; 2,470 gross weights still unknown and seven
  Bronze items still unmapped.
- All 54,713 source records, summary and proposed-exclusion files byte-identical
  to the preceding rehearsal. No source repair or selection change.
- 66 focused database-prohibited tests passed, covering owner examples, inclusive
  boundaries, leap years, restored dates, decimal-context independence, invalid
  inputs, aggregation holds, timezone conversion, source isolation, opt-in mapping,
  command integration and escaping source values in the HTML report.

At that checkpoint, the next question was fractional aggregation (rounding
each month's 148.50 gives 296 over two months; rounding the combined 297 gives
297). Item aggregation is a separate question. Then complete the opening evidence
basis, including gross-weight availability, Bronze support, original due terms,
R07743 and custody/valuation, before implementing the financial opening and
post-cutover servicing path. The generic opening-review continuation format still
does not implement the newly confirmed inclusive collection timing.

## Negotiated collections and version 2 (2026-09-12)

The owner answered the aggregation question:

> it doesnt matter we collect 300 sometimes and 290 sometimes and customer may fall short 50 rupees also we consider as interest lost no big deal now proceed

This resolves fractional rounding as a blocker for preparation. It establishes
negotiated collections and accepted interest loss, not an exact historical
rounding algorithm or a fixed tolerance. Do not ask the same aggregation question
again. See the [decision](../adr/2026-09-12-legacy-collection-estimates-and-concessions.md).

The new explicit `--owner-profile jcl-owner/2` keeps the same source scope,
anniversary dates and net-weight mapping. Loans' `aggregate_collection_interest`
uses calculation identity `original-anniversary-upfront-inclusive/2`: sum the
unrounded monthly item charges, multiply by additional months, then round the
total once to whole rupees with HALF_EVEN. This baseline was chosen for consistent
rehearsal estimates under the owner's instruction to proceed; it is not presented
as evidence of the cash received on a past release. For two additional months at
148.50, the estimate is 297. The calculator also returns unrounded monthly interest,
unrounded total, rounding adjustment and the exact rounding basis.

Every diagnostic exposes separate `collection_evidence` fields for actual interest
collected and interest lost. Both remain null because this preparation has no
verified amounts to put there. It does not invent a 7-rupee loss, a 3-rupee excess
or a 50-rupee waiver from the owner's general examples. Source mismatches, stored
payments requiring review and unrecognized charges still cause holds. Version 1
continues to reject fractional charges and remains selectable.

The same April 9, 2026 / Asia-Kolkata rehearsal now yields **2,447 calculated
illustrations out of 2,448 retained active loans**, with R07743 alone held for
source errors. The previous 1,700 whole-rupee results are unchanged. All source
records, summary, exclusions and opening candidates are byte-identical to the
previous report; actual collection/loss fields are unknown for every row and no
row is import-ready. The owner-edited workbook remains untouched.

72 focused database-prohibited tests pass. Added coverage verifies aggregate
rounding across months/items, original date and whole-rupee compatibility,
invalid values and oversized totals, source scope, preserved error/payment holds,
unknown collections/losses, explicit version compatibility and command/report
integration. The report displays its aggregate-rounding baseline and separate
negotiated collections prominently.

Next work is the pilot opening/evidence and servicing path, with original due
terms, gross-weight availability, Bronze support, R07743 and custody/valuation
still unresolved. The subsequent authorized implementation now supports accepted
interest loss for single-loan native full release, with explicit immutable
concession evidence and tested balance/settlement, reversal and isolation behavior.
This does not create migration openings. See the
[first-import plan](../plans/first-legacy-import.md) for the remaining work before
the first active pilot and the separate limited-evidence released-record path.
