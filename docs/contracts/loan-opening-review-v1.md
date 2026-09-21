---
status: active
owner: project
updated: 2026-09-12
tags: [loans, portability, opening-position, review]
---

# Offline opening review document v1

`loan-opening-review/1` is an implemented **technical review format**, not an
opening import package. It operationalizes the arithmetic and missing-information
checks from the [financial contract draft](loan-opening-position-mvp.md).
The separate [v2 checkpoint](loan-opening-review-v2.md) supports inclusive original
anniversary collection continuation; it does not reinterpret v1's period fields.
The dump adapter generates these records; customers do not need to author JSON.
No destination database is read and no financial event, approval, loan or mapping
is written. The existing `loan-history/1` import remains unchanged.

## Operator workflow

Use `preview_legacy_dump` with both `--propose-skip-incomplete-collateral` and
`--prepare-openings`; see the [source preview guide](../flows/legacy-dump-preview.md).
Only retained, unreleased loans become candidates. Every original source row stays
in `records.jsonl`, including all proposed excluded and released loan graphs.
Original IDs, numbers, timestamps, item descriptions, quantities, supported metal
labels, purity, original allocated principal and item rates are copied as source
claims. Missing balances, gross/net interpretation, custody, valuation, original
due terms, continuation and destination IDs remain null. A stored amount or absent
payment is never converted into a verified outstanding balance or zero fees.

Each fresh report directory contains:

- `opening-candidates.jsonl`: one review document per retained active source loan.
- `opening-results.jsonl`: every loan's field issues and available arithmetic.
- `opening-summary.json`: issue occurrences and unique loan counts by review group.
- `opening-review.html`: readable counts and the first 200 issue occurrences.
- `.gitignore`: keeps private source artifacts out of ordinary Git additions.
- `COMPLETE`: written last; incomplete output must not be treated as a completed report.

After an operator prepares reviewed evidence, run:

```powershell
.venv314\Scripts\python.exe manage.py validate_loan_openings `
  --input .tmp/reviewed-openings.jsonl `
  --output-dir .tmp/opening-reconciliation-next `
  --settings django_project.settings.dev
```

The command writes a new report and a copy of the reviewed input; it never overwrites
an existing report. A successful process means the report was produced, not that
the loans passed. Inspect `document_reconciled`, `loans_with_issues` and per-loan
issues. `import_ready` is **always false**, even for a fully reconciled document.

## Shape and bounds

UTF-8 JSONL, one complete object per line. No header, empty lines, duplicate JSON
keys, nonfinite values or extra/missing object fields. A missing review group may
be null and will receive a required-information issue. Maximum 64 MiB per file,
64 KiB per line including its newline, 5,000 loans, 20 collateral items/bases per
loan and 240 remaining obligations. Identity duplicates and mixed source tenant,
namespace, archive, selection, destination Workspace or cutover fail the batch.
An unknown destination/cutover may remain null in an unfinished candidate.

Every object uses exactly the following fields. References are bounded, nonempty
text (normally up to 255 characters), and dates use `YYYY-MM-DD`. Monetary inputs
are nonnegative decimal **strings**, up to 12 integer digits and two decimal places;
no exponent notation, signs or JSON numbers. Rates allow six decimal places,
weights/purity four. No automatic rounding or coercion of reviewed money occurs.
These deliberately bounded review limits do not replace destination model checks.

| Group | Exact fields and review meaning |
| --- | --- |
| Root | `profile`, `source`, `cutover`, `mapping`, `balances`, `terms`, `collateral`, `obligations`, `continuation`, `review_reference` |
| `source` | `namespace`, `schema`, `loan_id`, `number`, `loan_timestamp`, `borrower_id`, `item_ids`, `archive_sha256`, `selection_sha256`, `loan_sha256`, `state`, `excluded`, `errors` |
| `cutover` | `date`, `timezone`, `evidence_reference`; business date through which source activity is included; named IANA timezone; not future |
| `mapping` | `workspace_id`, `borrower_id`, `borrower_source_system`, `borrower_external_id`, `licence_revision_id`, `series_id`, `product_version_id`, `evidence_reference`; destination IDs are positive integers, not queried |
| `balances` | `principal`, `interest`, `fees`, `evidence_reference`; P positive, I/F nonnegative and explicitly reviewed |
| `terms` | `original_date`, `maturity_date`, `grace_days`, `billing_anchor`, `rule_id`, `period_rule`, `interest_basis`, `partial_rule`, `partial_cutoff_days`, `partial_lower_fraction`, `rounding_scope`, `rounding_mode`, `interest_quantum`, `evidence_reference` |
| Each `collateral` item | `id`, `description`, `quantity`, `metal`, `gross_weight`, `net_weight`, `purity`, `original_principal`, `remaining_principal`, `monthly_rate`, `weight_reference`, `custody_reference`, `valuation` |
| Each item `valuation` | `amount`, `date`, `evidence_reference`; positive migration assessment dated no later than cutover, not a fabricated original appraisal |
| Each `obligations` row | `id`, `due`, `principal`, `interest`, `recognized_interest`, `evidence_reference`; total interest may include future projection; recognized interest is the unpaid recognized portion |
| `continuation` | `period_number`, `period_start`, `period_end`, `bases`, `recognized_interest`, `recognized_unpaid_interest`, `advance_covered_interest`, `expected_period_interest`, `evidence_reference` |
| Each continuation `bases` row | `item_id`, `principal_base`; exactly one for each collateral item |

Source IDs include their table prefix, for example `girvi_loan:42`,
`girvi_loanitem:51` and `contact_customer:7`. Borrower source system must be exactly
`legacy:{namespace UUID without hyphens}:{schema}` and its external ID must match
the source borrower. Public schema, nil namespace, released/proposed excluded loans
and unresolved source errors cannot reconcile. SHA-256 fields are structural
evidence identifiers; this command does not authenticate them against the archive.

All source items must appear exactly once. Quantity is an integer 1–10,000, metal
`GOLD`/`SILVER`/`OTHER`, both weights positive and below 10 billion, gross at least net,
purity above zero through 100, monthly rate zero through 100 percent. Original
allocated principal is positive; remaining principal may be zero but cannot exceed
original. Capitalization and increased principal need a different review contract.

## Reconciliation rules

Per-item remaining principal and remaining principal obligations independently sum
to P. Recognized unpaid interest obligations sum to I; projected future interest
need not equal I. Obligations keep their original due dates, may remain overdue,
cannot precede origination, and principal cannot be re-aged beyond original maturity.
This checks supplied dates, not whether someone edited the source agreement.

Original date must match the source timestamp in the chosen business timezone.
Billing anchor equals original date in this slice. Grace is an integer 0–366 days.
`rule_id` identifies the reviewed agreement (up to 120 characters), but does not
select an implemented servicing engine. Supported review descriptors are:

- `period_rule`: `ORIGINAL_ANNIVERSARY` adds months from the original date with
  month-end clamping; `CLAMPED_CONTIGUOUS` adds each month from the previous boundary.
  For January 31, 2020, their March boundaries are March 31 and March 29 respectively.
- `interest_basis`: `ORIGINAL_PRINCIPAL` must match each original item amount;
  `OUTSTANDING_AT_PERIOD_START` cannot be below remaining principal or above original
  principal, and equals remaining principal when the reviewed period starts after C.
- `partial_rule`: `COMPLETED_ONLY`, `FULL_MONTH` or `SLAB`. SLAB requires cutoff
  days 1–28 and a decimal lower fraction strictly between zero and one; other rules
  require both slab fields to be null. These are declarations for later rule review;
  this validator does not compute a partial-period charge or future payment effect.
- `rounding_scope`: `PER_ITEM` or `AGGREGATE`; `rounding_mode`: `HALF_UP` or
  `HALF_EVEN`; `interest_quantum`: the exact string `1` or `0.01`.

The period ordinal is 1–1,200 and both boundaries must match the original rule.
Period end is inclusive, one day before the next anniversary. Supply the current
unfinished period, or the next period starting exactly C+1. If C is the completed
period's last day, supply the next period; it carries zero recognized interest.

The validator independently calculates a **full-period** charge from per-item
principal bases times monthly percentages, using the declared rounding. This must
equal `expected_period_interest`. Already recognized interest includes amounts paid
and unpaid; `recognized_unpaid_interest` cannot exceed that recognition or opening I.
Separate `advance_covered_interest` must exclude coverage already counted as recognized.
The additional full-period amount is calculated charge minus recognition minus
separate advance coverage. A negative result is an issue, never clamped to zero.

The separate `jcl-owner/1` source preparation profile now maps owner-attested net
weight and emits collection illustrations using inclusive anniversaries. This
review format's existing continuation boundaries are not that collection rule.
Preparation deliberately leaves terms, balances and continuation empty; passing a
rule name alone does not establish compatible financial servicing. See the
[implemented owner-rule preparation](../implementation/legacy-reconciliation-worksheet.md#implemented-owner-rule-preparation-2026-09-12).
This arithmetic does not authorize posting, determine when recognition becomes due,
or prove actual cutover balances from incomplete legacy payment history.

For the synthetic contract example P=900, I=24, F=0, original interest basis=1,000,
monthly rate=1%, recognized current-period interest=4 and separate advance=0, the
opening total is 924 and additional full-period interest is 6. Paying the recognized
4 before cutover removes it from I but does not make that 4 chargeable again.

## Ownership and remaining gates

`loans.services.opening_validation` owns these pure checks. Data portability owns
dump adaptation, bounded parsing, source selection and report files. Commands have
system/migration checks disabled and their tests prohibit database queries.

`document_reconciled: true` means supplied fields and arithmetic pass this review.
It is not source authenticity, accepted selection, verified custody/valuation,
destination authorization, product compatibility or approval by a local actor.
Source fingerprints, error lists, IDs and evidence references in edited files
remain claims. Actual mapping existence, Workspace isolation and membership must
be checked by the future authorized preview/commit path, not inferred from IDs.
The source exclusion fingerprint also does not prove an edited review file contains
the full original cohort. Partial review is allowed; selection approval remains pending.

Immutable opening evidence and balance/tranche readers are implemented. Reviewed
remaining obligations can be materialized, and v2 supplies a named collection
projection; v1 alone still does not select a servicing engine. Actual import review
attribution, ordinary opening correction, export and financial commit
remain pending under the [proposed decision](../adr/2026-09-12-loans-opening-position-contract.md).
V2 now supports dedicated full release with coupled collection catch-up/reversal;
native monthly accrual and partial-principal servicing remain unsupported.
Released records and the simple Excel adapter remain separate MVP work.

## Validation reporting categories

Opening result issues include `category` alongside their existing code, field,
message, severity and rule version. Summary `category_counts` counts occurrences;
`readiness_checks` on each result separately records operational prerequisites as
`NOT_EVALUATED`. Existing `pending`, `document_reconciled` and `import_ready` keep
their meaning. These are additive report fields, not changes to the input profile.
See the [classification decision](../adr/2026-09-13-portability-validation-classification.md).

## Pilot result

On 2026-09-12 the existing `jcl` dump selection generated 2,448 candidates while
retaining all 54,713 source rows. Every candidate requires financial/setup/collateral
review; zero documents reconcile, and one loan retains a source error. Standalone
revalidation produces the same summary. Local ignored artifacts are under
`.tmp/legacy-opening-jcl-20260912/`; do not commit private source reports.

The representative [source reconciliation worksheet](../implementation/legacy-reconciliation-worksheet.md)
is now prepared with source facts and competing legacy interest expressions. Next,
review the concrete examples and agree a named rule and rehearsal cutover/balance
basis. Do not activate 2,448
loans, infer zeros or ask the owner to manually author 2,448 JSON documents.
