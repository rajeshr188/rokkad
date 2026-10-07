---
status: implemented
owner: project
updated: 2026-10-07
tags: [loans, servicing, monitoring, compatibility, verification]
related: [../plans/loan-origination-completion.md, loan-settlement-continuation.md, loan-interest-contract-ld01a.md]
---

# LO-04: common servicing and explicit legacy disposition

## Supported behavior

Direct lending, completed-paper admission, complete-history/4 import and reviewed
opening/4 admission establish the same ordinary PawnLoan. Equivalent supported
flexible monthly agreements continue through the existing repayment, release,
renewal, auction and risk services. Opening continuation starts at its reviewed
checkpoint; the initial payment counters and original payout remain unknown where
they were not supplied. There is no financial conversion or new posting engine.

The four-path tests actually approve/disburse, record paper history, stage/preview/
commit history/4 and preview/commit an opening. They compare single/multiple items,
captured paise/whole-rupee interest, first-month advance, subsequent reductions,
collection/forecast amounts, closure, supported linked renewal/auction and coupled
reversals. LO-04 adds mixed GOLD 2% / SILVER 4% examples, paper receipts applied to
every origination path, and principal paid before versus on the charge boundary.

For an original 5 April loan, the upfront first month covers through 5 May. The next
charge starts 6 May. Principal paid on 5 May affects that charge; principal paid on
6 May affects the following month's charge. Interest rounds per item per period at
the captured policy quantum; receipts and principal keep paise in either case.

Receipt purpose is separate from origination source. Recording an already-received
paper payment uses its actual date, checked source and staff-supplied item principal
split after interest. A current receipt retains highest-rate-first allocation,
including on paper/imported/opening loans. An outstanding fee requires the actual
paper fee component, including explicit zero. Neither purpose can insert a payment
before later financial/custody activity or silently reinterpret a stale review.

## Demonstrated corrections

1. The ordinary paper receipt writer already accepted an item split omitting zero
   amounts. The opening replay reader required all item keys, so a valid posted
   receipt subsequently made collection, monitoring and portable reads fail.
   The reader now accepts only loan-owned supplied keys whose amounts exactly sum
   to principal paid. Omitted keys mean zero; complete persisted allocation lines
   must still agree, including zero lines. Foreign zero keys, missing lines,
   over-allocation and changed totals remain rejected. Original evidence is retained.
2. The inventory now exposes the servicing contract's captured timing and rounding,
   including earlier reviewed AGGREGATE/HALF_EVEN opening terms. Regression checks
   verify that these remain distinct from shared HALF_UP contracts. The existing
   servicing reader, calculation and posted amounts are unchanged. The inventory's
   collection quantum now comes from that reader; the retained policy quantum is
   shown separately, because older reviewed openings can legitimately differ.
3. The read-only interest inventory classified contract versions but did not expose
   current continuation failure, including a reversed native monthly charge. It
   now reports dated continuation status/blocker, captured timing/rounding and a
   disposition separately from compatibility status. SUPPORTED means the
   continuation read succeeded; it does not grant action permission, attest books
   or supply valuation. The command still emits JSON and changes no financial row.

No new migrations or evidence schemas are required. Published evidence shapes,
signed review contracts and source-specific reversal dependencies remain intact.

## Legacy disposition

| Saved evidence | Continued treatment | Explicit disposition |
| --- | --- | --- |
| Native policy/2, recorded-anniversary/3, reviewed opening/3-5 | Shared monthly timing and captured quantum where the supported agreement permits it | Continue captured contract; retain action-specific checks |
| Native policy/1 or unitemized event fold | Frozen native periods/amounts; legacy daily risk projection is not collectible interest | Keep frozen terms; any adoption needs a supported explicit review/correction |
| Recorded-anniversary/1-2 | Charge on the original anniversary; /1 aggregate versus /2 item-rounded paise | Keep accepted evidence or use existing reviewed contract correction, compensation and replay |
| Earlier collection opening | Reviewed day-after-anniversary baseline and aggregate whole-rupee half-even rounding | Keep reviewed terms/checkpoint; do not replace them with current setup |
| Opening with future advance exceeding a reduced charge | Existing over-coverage guard prevents an invented refund or redistribution | Hold the affected action and reconcile advance evidence explicitly; no automatic carry/refund is added |
| Native monthly recognition reversed | Retained immutable charge row cannot be reused or silently skipped | Hold continuation; broader re-recognition/correction integration remains unavailable |
| Terminal position / retained archive | Browsable verified terminal position or source claim; absent receipts remain absent | Preserve position/source; no automatic reconstruction or origination |
| Missing/conflicting/unsupported origin or policy | Explicitly unavailable calculation | Hold and review source evidence; no native fallback |

Paper-history corrections retain their dedicated review because cumulative receipts
depend on earlier allocations. Generic reversal is not a substitute. Current linked
renewal reversals correct both loans/custody; auction reversals retain recovery
coupling. Independent completed paper closure/new issuance does not acquire an
invented predecessor or physical cash/return claim.

The native reversed-charge hold is a known integration limit, not resolved by
LO-04. This slice exposes it and tests its disposition. It does not claim universal
arbitrary agreement support or automatic correction of old contracts.

## Monitoring and staff controls

Recorded event debt, collectible eligible interest and future exposure are distinct.
Current calculation can work while books or collateral value are incomplete.
Risk assessment freshness, valuation availability, transaction completeness and
calculation support remain separate disclosures for every origination source.

Use **Loan health → Refresh**, or **Refresh up to 50 due assessments**, after relevant changes. A calculation
refresh does not make old evidence fresh. Enter an applicable current metal quote
in **Rates** when required by the valuation method, or open the item's authorized
**Reassess / history** action to record a genuine current appraisal. Refresh the
assessment afterward. This does not manufacture an original appraisal or approval.

Use the loan's transaction-review action to check the books through an
actual date. Only confirm completeness after comparing source transactions. The
optional future Rokkad-only choice requires an active supported loan checked through
today. Continuing paper capture keeps dated book checks. Reappraisal does not
confirm books; book review does not restore missing valuation. Notices and auction
retain their existing communication, coverage, custody and operational prerequisites.
See the [staff flow](../flows/unified-loan-recording.md) and
[health guide](../flows/loan-health-monitoring.md).

Operators can run `check_loan_interest_contracts --workspace-id ID` under the
restricted runtime settings. Review both `status` and `continuation_status`, then
`disposition` and blockers. This is a selected-Workspace source report, not approval
to collect or convert. LO-05 must compare representative actual records/staff use.

## Verification and rollout

Verification uses the existing private isolated QA container and dedicated
`test_rokkad_ld04_20261005` database with `django_project.settings.test`. Generated
scenarios establish technical behavior, not source-book or staff acceptance.
Production records, D01623, customer communications and media remain unchanged.
Final test/check results are recorded in [Status](../STATUS.md).

The 112-check broad run passed 110; two new portable-read cases used an artificial
clock earlier than source recording timestamps. The 84-check affected run passed
82 with those same two fixture errors. Correcting the test recording clock leaves
all seven new cases passing (24.301s), including the two failures. No application
calculation changed to accommodate those fixtures. Existing matrix, settlement,
checkpoint, compensation and recovery cases passed in the broader runs and were
not repeated after the final test-only fix. Django checks, document links and
supported-app import boundaries pass. The full repository suite/CI is LO-06.

LO-05 real-source/staff acceptance and LO-06 exact candidate CI, actual media
recovery and measured capacity remain subsequent release gates. Earlier candidate
verification does not certify this changed code.
