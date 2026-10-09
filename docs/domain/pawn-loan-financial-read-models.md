---
status: active
owner: project
updated: 2026-10-08
tags: [loans, pawn-loan, balance, obligations, exposure, risk]
related:
  - ../adr/2026-08-11-loans-product-obligation-and-risk-architecture.md
  - ../implementation/pawn-loan-interest-calculation.md
---

# PawnLoan Financial Read Models

IP-03 adds the minimal loan-closed-position/1 admission basis. It is an ordinary
CLOSED PawnLoan whose unavailable original principal/date/rate/tenure/product
remain unknown, with no calculation or monitoring policy invented. The sole
zero checkpoint establishes debt/exposure at the accepted as_of date; earlier
positions, lifetime cash and collected interest are unavailable. The event date
does not assert an unknown closure or handover date. Accepted returned custody
and unknown custody remain distinct. No financial servicing or reopening of this
position-only record is enabled. Native/direct/paper and active continuation
retain their existing contracts. See [IP-03](../implementation/loan-position-import-ip03.md).

Individual and bulk completed closures share canonical full settlement and the
recorded-history-closure/1 basis. Financial closure does not by itself prove
physical cash or customer return. Unspecified returns retain PAPER_CLOSED and
last-known storage; confirmed returns retain their actual date without inventing
a time. Batch totals sum independent settlements rather than asserting a combined
current payment. Concessions retain separate interest-loss evidence and authority.
Previously complete book coverage is carried through a reconciled completed
closure; a prior Rokkad-only future-capture claim is not carried forward. Existing
records and older paper-closure/1 batches retain their evidence and retry meaning.
See the [closing decision](../adr/2026-10-08-unified-closing-and-completed-recording.md).

LC-05 adds a verified terminal position: an ordinary CLOSED loan with its original
agreement and a sole zero-valued opening at verified closure. At/after closure its
debt and exposure are zero; before closure financial positions and earlier cash
totals remain unavailable. No fictional payout, receipt, settlement or complete
history is supplied. Unknown handover is separate from zero debt. See the
[bounded evidence contract](../contracts/bounded-loan-evidence-lc05.md).

Explicit opening paper allocations retain actual fee amounts and staff item
principal splits. Replay checks them against posted allocations. Precisely timed
review/5 checkpoints permit evidenced later same-day actions; review/1–4 remain
end-of-day. These extend evidence completeness, not the shared monthly agreement
or current payment priority.

LC-03 settlement preparation shares these continuation facts across full release,
renew-now and current auction recovery. Previews include completed eligible modern
monthly charges; atomic commands recognize them once before settlement. Paired
terminal catch-up and recorded/opening recognition retain their source-specific
correction rules. Completed native charges remain owed after settlement reversal.
Legacy contracts retain explicit completed-period finalization. Frozen schedule
capacity limits allocation, not the actual debt collected after maturity. Interest
rounding does not restrict policy/2 cash to whole rupees. A completed paper renewal
records agreed facts; renewing now still requires current successor approval.

The common Loans directory can also display retained historical closed claims,
clearly labelled and linked to source details. These cards are not operational
financial origins and do not enter balances, collections, exposure or risk totals.
Unknown settlement and physical handover remain unknown. Reconciled financial
admission creates an ordinary loan; its source card is then replaced in the
directory, while immutable evidence remains. See the
[browsing decision](../adr/2026-10-05-unified-loan-browsing-with-retained-evidence.md).

## Shared monthly interest contract: owner clarification, 5 October

Direct, backdated paper and imported entry use the same agreed interest boundary.
A loan dated 5 April with the first month paid upfront has no second-month charge
through 5 May; that charge starts on 6 May. Anchor subsequent boundaries to the
original loan date with individual short-month clamping. Rounding follows the
standing economic policy captured for the agreement. Entry channel and later
policy edits do not change these terms.

LD-01A implements this calendar and captured-policy rounding for new versioned
contracts. The older profile behavior below remains historical implementation evidence. Preserve
actual recorded amounts, opening cutover baselines and issued documents. Correct
affected posted amounts through supported compensating actions. Charge eligibility,
recorded recognition and remaining unpaid interest stay separate read concepts.
See the [plan](../plans/unified-loan-domain-correction.md).

## LD-06 servicing and future capture

Renewal and current auction use common factual prerequisites, with existing
operation-specific approval, statutory and custody controls. Reviewed openings use
`opening-auctions/1` for exact full recovery and coupled catch-up/reversal. Opening
renewal retains its existing preview-plus-catch-up arithmetic. Unsupported correction
graphs remain held; accepted financial evidence and issued bytes are unchanged.

An explicit per-loan complete review through today can select future Rokkad-only
capture. This is a future operating choice, separate from original source and
checked-through history. Existing and fresh ordinary book reviews default to
paper/mixed. The original prefix and agreement remain exact; supported current
activity can maintain coverage, while paper facts/history corrections require review.
Original LTV can remain unknown while current monitoring uses fresh eligible
appraisal/prices and verified current debt. Coverage cannot substitute for valuation.
Current notices freeze checked and current fingerprints and recheck amount/date/risk
at dispatch. See [LD-06](../implementation/servicing-operations-ld06.md).

## Current read implementation

LD-04 adds review/4 opening checkpoints with reduced remaining item principal,
explicit current-period bases and separate cumulative/current recognized/unpaid
interest. Current/future advance coverage is source evidence assigned to actual
periods. The cutover position is recorded debt with zero catch-up; subsequent
periods use remaining item principal, captured policy rounding and the original
anniversary. No original charge history is guessed from today's remaining balance.
Original maturity/grace stays unchanged. Read models and supported receipt/release
writers share that continuation; reversal restores it. Earlier transactions remain
unavailable and transaction coverage/current valuation require their own evidence.
Older review/2 and /3 retain their frozen meanings and unchanged-principal admission.
See [LD-04](../implementation/reduced-principal-opening-ld04.md).

LD-02 adds common factual eligibility for REPAYMENT/FULL_RELEASE and CURRENT/PAPER
purpose, independent of origin. Commands retain their existing authorization,
locking, signed source review and atomic posting. Shared native monthly bullet
contracts support reviewed completed receipts; legacy recorded snapshots without
an anniversary profile keep their original event-fold current collection behavior.
No fallback invents interest terms for paper continuation. Full-release previews
include unposted eligible completed charges without writing; commit recognizes
them before settlement and pairs only current-period catch-up with reversal.
Full settlement leaves no retained exposure and needs no current valuation;
partial release still requires its valuation/LTV checks. Completed paper activity
requires explicit coverage review even on a native-origin loan. Coverage describes
the checked book, separately from calculable debt and current valuation.
See [LD-02 implementation](../implementation/loan-servicing-eligibility-ld02.md).

LC-01 adds `selectors/continuation.py` as the common read boundary for repayment /
notice positions and exposure (therefore collateral/risk inputs). It resolves the
frozen contract and actual reporting date, reads recorded debt, and describes the
eligible native-period, recorded-cumulative or opening-checkpoint interest through
existing calculators. The recognition plan retains adapter evidence and periods;
writers must recompute under their existing authority, locks and atomic commands.
Legacy daily forecasts remain exposure-only and do not enter collection amounts.
Opening collections retain after-cutover chronology/schedule checks; closed opening
notices retain recorded debt. Coverage and valuation are independent of supported
arithmetic. Native/recorded maturity forecast dispatch and specialized action writers
remain for later slices. See the
[inventory](../implementation/loan-continuation-inventory.md).

LC-02 consolidates supported monthly bullet/flexible remaining-obligation forecasts
through this boundary. The reporting date fixes recorded debt and known activity;
the forecast horizon extends charges to maturity (or the reporting date if overdue).
Later database receipts are excluded from earlier forecasts. Shared-policy openings
continue their checkpoint with later known reductions and actual advance coverage.
Original schedule rows remain immutable allocation capacity; earlier opening profiles
retain their established schedule view. Forecasts are not current collection quotes.

Risk V6 carries calculation support, financial-history start and principal-history
basis. For openings, the existing `original_principal` compatibility field means
principal brought forward at cutover; `principal_repaid` means payments since that
checkpoint. Neither asserts original cash advanced or total earlier repayments.
Presentation/export labels retain this limitation. Assessment freshness, transaction
coverage, eligible valuation and calculation support are separate dimensions.
Refreshing cannot certify absent paper activity or repair stale valuation. Recorded
reports retain their recorded-balance basis and show saved assessment quality
separately; repayment previews show supported collection amounts.

LD-01 centralizes read-side servicing selection in
`selectors/servicing_contract.py`. Repayment preview, reminder balance and repayment
form context share the same supported position while retaining native posted debt,
recorded anniversary recognition and opening catch-up. The read-only contract
exposes original/cutover dates and saved rounding/calendar conventions; optional
coverage metadata uses the existing checked-through selector. That read-only checkpoint changed no financial writer or interest formula. LD-01A
now adds the shared calculation contract: native-monthly-policy/2, recorded-anniversary/3
and reviewed opening/3. Native monthly repayment recognizes eligible interest
atomically; risk, collection previews and notices use the shared eligible charge.
Posted recognition remains independently visible. Active native simple/full-month
flexible/single-payment bullet forecasts now use the same eligible calculation with
knowledge capped at the reporting date, subtracting advance once and applying
principal reductions to the correct following period. Raw original schedules remain
immutable allocation capacity. Old contracts require reviewed correction rather
than automatic reinterpretation. Unsupported profiles and conflicting/missing
operational origins are explicit errors. See the
[implementation](../implementation/loan-servicing-contract-ld01.md).

The earlier itemized recorded contract uses `recorded-anniversary/2`: principal is the exact
sum of actual item amounts, and each anniversary charge is the sum of item-rounded
interest on the applicable item balances/rates. A principal payment on an
anniversary still changes the following anniversary's base in this implementation;
The corrected /3 contract instead starts the charge the day after that anniversary;
a payment on the covered anniversary changes that next charge, while a payment on
the new charge day changes the following charge. The loan-level
effective rate is display data. Existing `recorded-anniversary/1` evidence retains
its previous aggregate calculation; adding entry defaults never rewrites contracts.
Paper receipts may freeze `STAFF_SPECIFIED` item principal allocation and retain
the exact confirmed split in recording evidence. The tranche reader checks its
membership, amounts and source against immutable allocation lines. Native ordinary
payments keep `HIGHEST_MONTHLY_RATE_FIRST`. Corrections must retain or explicitly
review affected item splits; no later principal allocation is silently invented.

**Current local completion slices (3 October):** original and recorded-successor
term corrections compensate/replay canonical debt while retaining earlier policy,
disbursal and opening-line revisions. Current settlement projections read active
replacement events. Dated custody revisions explicitly supersede earlier facts;
later handover is an actual appended movement and changes no settlement. Imported
openings renew without inventing pre-cutover history; current successors still
require current approval. Recorded-origin current auction uses agreed anniversary
debt and complete transaction coverage, stops collection at recovery and resumes
after coupled reversal. Native recovery retains those exact identities and reviews
alongside file bytes; it does not remap them into a new Workspace. Earlier dated
checkpoints below describe their then-current boundaries. See the current
[operator guide](../flows/paper-first-operator-and-release.md).

**Independent paper recording (3 October):** each supported paper loan can enter
ordinary active/closed records without reconstructing a predecessor. Contract
proceeds after advance interest/document charge are distinct from confirmed physical
cash. A closing settlement can clear debt while customer handover remains unknown
(`PAPER_CLOSED`); custody uncertainty is reported separately as a warning. This is
not collateral available to a new unrelated lending decision. A known subsequent
renewal reconciles old settlement, successor deductions and actual net cash, with
retained collateral linked to the successor. Current approval applies when the new
decision happens now. Original paper terms govern collection, while current prices
and transaction completeness govern monitoring. See the
[decision](../adr/2026-10-03-independent-paper-loans-and-renewal.md).

PawnLoan uses layered read models. They answer different questions and must not
be collapsed into one mutable total.

**Unified recording, implementation in progress (2 October):** the
[unified recording decision](../adr/2026-10-02-unified-loan-recording.md) will admit
supported delayed paper histories through the same canonical records. Actual
contract terms govern debt; original valuation evidence and current collateral
monitoring remain separate. Total-only receipts retain their source amount and
separately derived allocation. Financial-history availability and scoped paper
entry completeness must remain visible independently of current price freshness.
UR-01 records supported dated paper receipts on existing opening loans. UR-02
adds a local recorded-origination storage/read-model foundation; ordinary admission
of never-entered histories remains pending. See the
[implementation boundaries](../implementation/unified-loan-recording.md).

A recorded payout uses the ordinary `DISBURSAL` event and immutable disbursal
snapshot, with basis `RECORDED` and no approval snapshot. Original principal, net
cash, deductions and explicit agreed interest rules reconcile independently of
old digital prices. Its recorded-contract policy distinguishes those interest
rules from a separately identified monitoring choice. Ordinary balance/tranche
readers consume the original dated event; current coverage uses current eligible
prices/appraisals and may remain unknown. Recording timestamps do not move the
financial date. The initial no-fee simple-interest storage profile does not select
Lakshmi's contract automatically or certify complete paper entry.

Active imported opening loans expose a read-only interest explanation on the
detail page. Elapsed calendar months/days are separate from chargeable months:
the first month is paid upfront and subsequent charges increase the day after
the original monthly anniversary, with short-month clamping. The existing
collection calculator sums item monthly interest, multiplies by chargeable months
and rounds once. The screen separates cumulative calculated charges from unpaid
interest brought forward at import and additional charges since import; the month
count alone does not establish unpaid debt. Closed loans omit this live breakdown.

## Recorded balance

`get_pawn_loan_balance` folds finalized immutable loan accounting events through
the requested as-of date. It is authoritative for recorded:

- principal outstanding;
- interest outstanding;
- fees outstanding;
- payments and reversals;
- accounting-delivery readiness.

The identity is `recorded:event-fold-v1`. Projected interest and future schedule
amounts never enter this balance.

The migration-opening read foundation recognizes one `MIGRATION_OPENING` with
frozen reconciled cutover evidence. It adds `opening_principal`, `opening_interest`
and `opening_fees` separately from disbursed/accrued/paid totals. Subsequent event
folding starts from those amounts. `financial_history_from` identifies the cutover;
an earlier query raises an unavailable-history error rather than returning zero.
Mixed disbursal/renewal origins and servicing on or before cutover are rejected.
Maturity comes from the reviewed original terms, not a fresh migration tenure.
For the owner's jcl import, the explicit 2026-09-12 instruction supplies a migration
maturity of original loan date plus three calendar months where maturity was not
recorded; recorded terms take precedence. This date feeds the same obligation and
delinquency readers. The owner instruction is retained separately from source facts
and does not change anniversary interest, cutover balances or original billing dates.
Item-principal readers start from frozen remaining principal and respect the
requested date when a later repayment reversal exists. Opening amounts are not
cash lending or receipts in reports. Version 2 collection checkpoints now project
the additional cumulative baseline after cutover into exposure, separately from
recorded debt; native daily projection is not used for these openings. Version 1
does not select that rule. Opening projection now recognizes the dedicated
full-release catch-up, settlement and coupled reversal. It validates their pairing,
stops projecting during closed intervals and resumes after reversal. The ordinary
event fold includes posted catch-up interest and cash/concession separately.
Item-principal reads consume full-release closing lines with date-aware reversal.
Other later financial events, native monthly interest and generic posting remain
blocked for this origin.

Reviewed remaining obligations can now be materialized against the opening using
the existing immutable schedule tables. Original due dates/maturity are preserved;
the opening source date controls when the schedule becomes available. Historical
payments are not fabricated as allocations. Exposure requires this linked schedule;
the delinquency selector uses reviewed original grace rather than the product
default. See the [v2 contract](../contracts/loan-opening-review-v2.md). These services
do not authenticate a source or create an opening import.

## Contractual obligation state

`calculate_obligation_state_as_of` folds the one active repayment-schedule
version, its obligations, allocations, termination evidence, and reversals. It
is authoritative for:

- contractual principal and interest remaining;
- amounts due on or before the as-of date;
- amounts overdue strictly before the as-of date;
- the unpaid rows used to calculate DPD;
- schedule and allocation integrity findings.

The single-schedule selector fetches obligations and date-filtered allocations
in two queries and passes them to the same fold. It does not retain a cross-date
cache; reversal allocations remain filtered by their source effective date.

Fees are not scheduled obligations in the current contract and remain recorded
balance components. An over-allocated obligation is reported and excluded from
aggregate obligation amounts; it is never silently clamped into a valid row.

An opening's UNVERIFIED old valuation stays in source evidence, not in an approved
appraisal or cached current value. Existing valuation readers therefore report
missing appraisal/current LTV until actual dated evidence is recorded. This does
not make confirmed debt unknown: full settlement can return all opening collateral
without valuing it, because no secured exposure remains. Native and partial-release
valuation checks continue to apply. Inactive legacy licence references retain
unknown validity for grouping/reporting and do not authorize new lending.

## Economic exposure

`get_pawn_loan_exposure` composes, but does not replace, the first two models:

```text
recorded total due = recorded principal + recorded interest + recorded fees
total economic exposure = recorded total due + labelled unfinalized interest preview
maturity payoff = contractual remaining principal + contractual remaining interest
                  + recorded fees
```

For bullet/flexible contracts, LTV uses maturity payoff. For amortizing
contracts, LTV uses total economic exposure. Exposure records its calculation,
schedule, and product-contract provenance and reports a variance if contractual
remaining principal disagrees with recorded principal outstanding.

## Delinquency and risk

Delinquency consumes the same canonical unpaid obligation rows used by exposure.
The contractual due date determines DPD; operational grace affects workflow but
does not move that date. The older balance-level overdue flag remains a
reconciliation comparison only.

Live risk consumes exposure, delinquency, collateral valuation, and monitoring
policy. Persisted risk snapshots copy those results and their identities; they
must never recompute money independently. The active portfolio includes loans
without projections. Current means a successful current-contract projection for
today; missing/outdated/error assessments do not contribute to claimed complete
portfolio monetary totals. Unknown collateral coverage is a separate dimension.
Coverage exposure, headroom and shortfall are copied from the valuation/LTV selector.
A refresh reuses its scoped, same-date exposure, delinquency and collateral
results between layers; public reads can still calculate these independently.
Closed loans retain financial/history reads but stop live health calculations.
See [Loan health](../flows/loan-health-monitoring.md).

Current collateral valuation applies the effective monitoring policy's inclusive
quote/appraisal age limits. It retains displayed reference amounts but reports
unknown eligible coverage when evidence required by the loan's frozen valuation
method is stale or missing. Reviewed active-loan appraisals append immutable
versions, retain their reference context, and invalidate saved risk assessments.
See [collateral reassessment](../flows/collateral-reassessment.md). These monitoring
limits do not become origination or settlement rules implicitly.

## Workflow use

Party and borrower-portal outstanding summaries sum canonical recorded balances
across all of the borrower's active loans before limiting displayed history rows.
The default 20-row display is not a monetary aggregation limit. Draft/approved
records remain visible in the open-loan group without inventing posted balances.
Party shows a truncation notice when more open loans exist than are displayed.

Licence/series active totals aggregate the canonical recorded balance fold, including
repayments and reversals. Membership in these reports uses current ACTIVE state;
the selected date applies to recorded balances, not historical lifecycle membership.
Unavailable balances contribute to loan and error counts but not monetary totals.
Maturity bands measure days after the balance reader's maturity date; they are not
contractual instalment DPD or a replacement for the delinquency selector.

Loans by year groups all operational loan records by the original `loan_date`
calendar year, not their creation/import timestamp. Counts distinguish current
active, closed, cancelled and draft/approved states. Money is canonical active
principal at the selected report date, with unavailable balances counted separately.
Archive-only historical evidence is excluded. This is a current cohort view, not a
historical year-end snapshot. Charts combine years older than the latest twelve;
tables and exports retain every year.

Collateral-by-metal reports cover current active-loan items in vault or with a
funding lender. Gross/net weights are grams. Value means the latest approved
appraisal effective on or before the selected date, not market value or eligible
coverage. Unverified migration valuations do not become approved appraisals.
Missing gross weights/appraisals are counted explicitly and excluded from sums.
Released/transferred collateral is excluded to avoid double counting retained
source items after renewal. Charts format the same totals used by tables/exports.

Report integrity checks recognise disbursal, renewal-opening and migration-opening
events as valid financial origins. An imported opening must not require an invented
historical disbursal. Accepting its origin does not bypass canonical balance
validation: malformed or inconsistent opening evidence still produces a balance
derivation finding. Paginated integrity pages describe only the loans checked on
that page; full portfolio summaries retain complete findings.

Reviewed opening v2 can now be committed through the Loans-owned opening service.
It creates one financial origin, remaining obligations and migration-labelled
appraisals atomically; no historical lending or receipts are reconstructed.
`HistoricalLoanImport` shares source-identity uniqueness between complete history
and opening evidence. A retry returns the original import result without resetting
later balances. See the [commit decision](../adr/2026-09-12-authorized-opening-commit.md).

- repayment allocation and financial settlement use recorded balance;
- release combines recorded settlement with canonical collateral valuation;
- renewal settles recorded source balances and separately prices the successor;
- reports label recorded amounts, contractual dues, and projections distinctly;
- monitoring and risk use exposure and contractual delinquency.

## Legacy negotiated collections

The migration owner clarified that actual interest collections may differ from
calculated interest, with accepted shortfalls treated as interest lost. Preserve
calculated interest, cash collected and an accepted concession as separate facts.
Unknown historical receipts do not imply zero collections or a known loss. A
legacy closure attestation is not evidence that the full theoretical interest was
collected. No fixed tolerance or automatic principal reduction follows from this.

The offline `jcl-owner/2` profile uses aggregate HALF_EVEN rounding only as a
rehearsal estimate. It never changes recorded balance or grants live settlement
permission. Single-loan full release now records an explicitly authorized concession
in immutable release-event `values.interest_concession`, with its reason in the
release payload and actor on the event. `interest_paid` represents cash;
`interest_conceded` represents interest forgone. Outstanding interest subtracts
both; the existing release reversal restores both components. Cash still covers
all principal (including capitalized interest) and fees. Obligation allocations
record cash only; the full-release schedule termination closes the remaining
obligations with the concession traceable to the same source event. The whole
release and its correction remain atomic. This does not implement active migration
openings or concessions for ordinary repayments, renewal or current combined batch release.
Completed-recording batches support authorized interest concessions through the
same canonical full-release writer. See the
[decision](../adr/2026-09-12-legacy-collection-estimates-and-concessions.md).

## Recorded paper anniversary contracts

The explicitly confirmed UR-03 profile charges the earlier principal for the current
full month; a reduction affects the next loan anniversary. Current collection and
economic exposure use cumulative agreed charges less advance interest, recognized
interest and settled amounts. UR-03A renewals freeze cash received, cash paid,
principal carry, gross advance and old-interest offset separately. Canonical
settlement interest includes the offset; physical cash is read from the cash
evidence, not inferred from settled debt. A full principal repayment/fresh advance
has zero carry even when its net cash matches a carried-principal renewal.
An ordinary closed/renewed source leaves current exposure, while as-of reads before
settlement retain its debt.

For these bullet/flexible contracts only, obligation reads retain the original
maturity but project remaining interest from actual principal history instead of
reusing the original fixed-principal schedule total. Calculations at a historical
as-of date cannot use later receipts. Raw schedule allocation capacity is separate
from this variable debt projection. Current monitoring selection and price freshness
remain independent of the recorded-through paper-history date. See
[UR-03 implementation](../implementation/unified-loan-recording.md) for exact charging
boundaries, supported fields and pending completeness/recovery integration.

UR-04 receipt corrections add same-business-date compensation and chronological
replacement events. Date-based balance/exposure queries therefore represent the
restated business history; creation timestamps preserve when the correction was
recorded. Receipt totals remain the actual cash facts, while interest and principal
allocations are recalculated. Original events and allocations stay immutable with
linked reversal evidence. Reported correction movements must not be interpreted as
fresh cash collection/refund. The
[settlement extension](../adr/2026-10-02-recorded-settlement-corrections.md) permits
reconciliation through an unchanged renewal agreement or full return. The corrected
source principal/interest and actual settlement cash can differ from original entry;
successor principal and terms cannot be silently recalculated. Original release and
renewal documents retain their initial figures; operational financial presentation
uses the linked active replacement event with correction provenance. The source
remains closed, no custody movement is repeated and successor monitoring continues
from its unchanged agreement and events. Unsupported contract/custody amendments
remain blocked. Combined release-batch receipt corrections require a whole-batch
review: every member participates, revised settlements reconcile to actual total
collection, and all changes post together. Retained original batch/line amounts are
audit evidence; operational batch views and reconciliation CSV use shared current
settlement projections and label corrections. A financial restatement does not
repeat the physical handover or represent newly received money.

UR-05 can admit a fully reconciled, supported closed archive loan through that same
recorded-contract writer. A HistoricalLoanImport source claim links the retained
archive snapshot to its ordinary closed loan. Archive records remain evidence and
never contribute balances or cash totals; admitted events contribute once at their
actual dates, with zero current exposure after closure. Unknown archive facts are
not zero facts: staff supply original contract, cash and return evidence for review.


## Transaction coverage and provisional monitoring

LoanTransactionReview confirms entered records through a date for one loan and
one financial fingerprint. It can explicitly report incomplete records. New paper
entry confirms its transaction facts; an optional complete-book claim records a
review for each member. Under paper/mixed capture, subsequent activity/correction
invalidates an existing review. An explicit reviewed Rokkad-only transition can
retain coverage for supported current actions, as described above; paper facts or
historical corrections require a fresh review. Routine entry, receipts and closure
need no daily whole-book attestation.
An opening loan's review begins at its accepted checkpoint and makes no
claim to reconstruct older receipts. Date rollover affects active paper/mixed coverage; a closed
loan only needs coverage through its final activity. The current read represents
restated knowledge, not what staff knew at a historical date.

Risk snapshot V5 freezes transaction provenance separately from valuation evidence.
Missing/stale paper coverage preserves individual calculated exposure and risk with
a provisional explanation. Dashboard/portfolio show usable known calculated totals
with provisional and unavailable counts; completeness remains explicitly false
until all included loans have suitable coverage. Report rows and borrower statement
exports include coverage status and date. Supported reviewed reminders use the
agreed collection amount, including unrecognized collection interest; they require
current confirmation and are rechecked before a provider attempt. See the
[decision](../adr/2026-10-03-loan-transaction-completeness.md).
