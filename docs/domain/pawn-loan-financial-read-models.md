---
status: active
owner: project
updated: 2026-09-12
tags: [loans, pawn-loan, balance, obligations, exposure, risk]
related:
  - ../adr/2026-08-11-loans-product-obligation-and-risk-architecture.md
  - ../implementation/pawn-loan-interest-calculation.md
---

# PawnLoan Financial Read Models

PawnLoan uses layered read models. They answer different questions and must not
be collapsed into one mutable total.

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
openings or concessions for ordinary repayments, renewal or batch release. See the
[decision](../adr/2026-09-12-legacy-collection-estimates-and-concessions.md).
