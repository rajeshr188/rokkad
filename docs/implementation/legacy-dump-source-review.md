---
status: active
owner: project
updated: 2026-09-12
tags: [portability, legacy, source-review]
---

# Legacy dump and source review

## Scope and conclusion

The owner identified branch `tenants_workspace`, commit
`c9fb81bc70adafa1d942721d642bfb2b38953f41`, as the legacy production source.
The commit exists locally and was read using Git object access, without changing
the working branch. Its commit date is 2024-12-09. The supplied archive is
`rokkaddb_prod_full_2026-04-10.dump`; its filename date is not independently verified
as a business cutover date.

This source supports interpretation of the dump, but its model/migration state
does not exactly match the archive. No historical financial reconstruction is
certified by this review. The practical initial migration direction is reviewed
opening positions for unreleased loans and a limited-evidence historical record
for released loans, with the strict complete-history importer used only where its
requirements can actually be established. Opening positions now have a draft
contract and offline validator; financial activation and limited-evidence released
imports remain pending. See [source priorities](../plans/data-portability.md#actual-source-priorities-2026-09-12).

## Method and evidence boundary

Read `pg_restore --list`, schema-only output and selected data-only COPY output as
text. Source files were extracted from the exact commit and inspected as text.
No legacy Python, SQL, trigger, ORM or migration was executed; neither the old nor
current database was changed. Source helpers must not be called during migration:
several save methods update loan fields or create journal/payment/release records.

Local scratch evidence lives in `.tmp/legacy-dump-inspection/`, with a directory
ignore rule covering all extracted code, data and reports. `source-reconciliation.json`
contains aggregate findings; `loan-review.csv` has one row per source loan with its
schema/key, source release state, item/payment counts, proposed review route and
selected review flags. Every row is marked not import-ready. The scratch parser is
specific to these inspected COPY headers, not a supported general PostgreSQL parser
or a production import adapter. It does not decode arbitrary COPY field escapes or
validate every field, date, relationship or destination-domain requirement.

## Source/dump version differences

The later owner-supplied `backup_20260912_224652.sql` was inspected on 2026-09-12.
It is custom PostgreSQL format and contains both `girvi_series.loan_type` and
`girvi_loanitem.is_repledged`, matching the reviewed commit's model declarations.
The adapter accepts exactly the older and these later column sets, preserving
presence/absence and actual values in source facts/hashes. It never defaults a
missing repledge flag to false. True/unknown flags require custody review; series
types other than explicit Given require review. Current jcl has all false flags
and all Given series. Other arbitrary column changes remain unsupported.
Its unrelated `jsk-knb` schema exposed an inventory scope issue: explicit jcl
selection now validates only jcl's table identifiers, with cross-schema COPY still
rejected. This does not add support for selecting hyphenated schemas.

The following differences describe the earlier rehearsal archive:

The dump has no `orgs_company.is_deleted`, `girvi_series.loan_type`,
`girvi_loanitem.is_repledged` or `girvi_repledgedloanitem` table, although the supplied
commit defines them. Its recorded Girvi migrations run through
`0023_alter_loan_options`; Contact through `0015_alter_customerpic_is_default`;
Orgs through `0013_alter_companyinvitation_email_and_more`. Later code includes
squashed migrations and additional model fields. Actual columns and the recorded
migration history must both be checked; neither Git age nor migration names alone
prove which code ran when a particular record was entered.

This is a compatibility finding, not proof that the owner supplied the wrong code.
Use the dump's actual columns as the extraction contract; establish deployed
calculation behavior before activating financial data. Never run the commit's
migrations against the archive to make it appear compatible.

## Loan and release semantics

All paths and line numbers below refer to the supplied commit, under
`apps/tenant_apps/girvi/`, not the current retired-app tree.

| Source evidence | Observed behavior | Migration implication |
| --- | --- | --- |
| `models/loan.py:117`, `managers.py:29` | Released state means existence of a one-to-one Release row | Preserve the source release claim; this alone does not prove a settlement amount or physical return |
| `forms.py:449`, `forms.py:532` | Release amount is optional; a LoanPayment is created only for a positive supplied amount | A release without a payment is a supported source path, not automatically missing/corrupt data |
| `models/release.py:123` | Release save generates its number and saves the record | No unconditional settlement payment or financial event is created by this method |
| `models/loan.py:689` | Item interest is `interestrate / 100 * loanamount` | `interestrate` is the percentage input; `interest` is a monetary amount |
| `models/loan.py:301` | Loan update sums item principal and item interest, and refreshes description, weight and value | Loan-level interest is a monthly monetary total in this calculation path; do not map it as an annual/monthly percentage |
| `models/loan.py:208` | Interest due is rounded monthly money times completed calendar months via relativedelta | This differs from the report calculation and is not automatically today's Loans policy |
| `managers.py:100` | Report months use `ceil(elapsed_days / 30.44)`; interest is rounded `monthly_interest * (months - 1)`; total due adds stored loan amount without deducting payment rows | Do not select this aggregate as the authoritative opening balance without reconciliation |
| `tables.py:149` | Displayed interest calls `interestdue()` while the query also computes report interest | The old screen/export paths can show different derived figures |
| `models/loan.py:919` | Payment split uses `loan.interestdue()` without passing payment_date, then sets principal to payment minus that interest | Stored splits may depend on entry/edit time; preserve them as source facts and flag inconsistencies instead of recalculating them on migration day |
| `models/loan.py:670` | Current item valuation uses cached/latest Rates; Loan.update refreshes value | Stored value is not established as an immutable origination appraisal |
| `views/loan.py:296` | Renewal path moves item relationships and creates a release; no durable old/new-loan link is shown in this path | Do not infer collateral custody or a complete renewal chain from release existence; source execution of this path is unproven |

The calculation differences explain why marking every source loan `Simple` does
not establish compatibility with `loan-history/1`. The source also does not supply
the current frozen approval, valuation, schedule, accrual and release-evidence
contract merely by having loan, item and payment tables.

The inspected journal records resolve to loanitem (2,238), loanpayment (988), and
loan (1,413) content types, with no direct release content type among those rows.
Only one of the 15,876 released loans without payment rows has a direct loan journal
with account transactions. This limited check does not find a universal alternative
settlement ledger; it does not rule out other or manual evidence. No retired DEA
records are authorized to become a new accounting subsystem.

## Source inventory and reconciliation

Six Company rows bind public plus five business schemas; three business schemas
contain loan rows. Map each selected business schema explicitly to a destination
Workspace. Do not migrate public as an ordinary business tenant or import old
memberships, credentials and permissions by default.

| Source records | Count |
| --- | ---: |
| Customers | 6,924 |
| Customer contacts / addresses | 1,935 / 4,864 |
| Licences / series | 4 / 10 |
| Loans | 22,987 |
| Released / unreleased loans | 16,880 / 6,107 |
| Item rows | 12,408 |
| Unreleased loans with separate items | 6,103 |
| Released loans without separate items | 10,654 |
| Payment rows / loans with payments | 1,010 / 1,009 |
| Unreleased loans with payment rows | 5 |
| Released loans without payment rows | 15,876 |

Selected source anomalies (counts overlap and are not rejected-loan totals):

- 23 release rows dated before the corresponding loan timestamp.
- 9 payment rows dated before the corresponding loan timestamp.
- 2 unreleased loans whose stored principal differs from the sum of their items.
- 1 unreleased loan whose stored monthly interest differs from its item sum.
- 4 unreleased and 8 released loans with missing or nonpositive principal.
- 4 unreleased loans without separate item rows.
- Bronze collateral occurs in 36 items, on 31 unreleased and 5 released loans.
  Current canonical metal values are GOLD/SILVER/OTHER; an explicit OTHER mapping
  must preserve the original metal and compatible servicing terms.

No missing references were found for loan -> customer/series, series -> licence,
contact/address -> customer, non-null release collector -> customer, or item/payment/
release -> loan in the selected records. All stored payment splits sum to payment
amount, and no negative payment components were found. These checks do not establish
that the split was economically correct or that payments are complete.

## Proposed source mapping

| Source | Destination/review |
| --- | --- |
| Schema + table + primary key under stable source-system identity | Exact per-Workspace portable reference, stable across snapshots; no name matching or cross-schema PK merging |
| Customer name, active, relatedas, relatedto | Party master; map relation label/name, not a fabricated second Party. Review legacy `c` (label C/o) before choosing CARE_OF |
| Contact/address rows and their source customer IDs | Party child profiles with retained child identities; source verification stays source-only |
| Licence and Series.license_id | Explicit current setup mapping. Licence name/renewal_date do not establish current licence number or validity interval |
| Loan.id / loan_id / lid | Keep source PK identity separate from original printed loan number and sequence value; preserve exact strings, including leading zeroes |
| Item rows, or inline loan item fields where rows are absent | Preserve available collateral facts; never turn a formatted weight string into an assumed gross/net/metal split |
| LoanPayment | Preserve payment date, amount and stored components as evidence; no current save/replay callbacks |
| Release | Preserve source date, number and collector reference with declared evidence coverage; no fabricated payment or verified return receipt |

## Next bounded implementation

The read-only legacy source adapter/preview is now implemented against the inspected
archive shape and exercised on the owner-selected `jcl` schema. See the
[operator guide](../flows/legacy-dump-preview.md). It produces dependency references,
counts, source conflicts and per-record review dispositions using portability
conventions. It keeps excluded tables explicit, generates stable proposed identities,
and does not read or write the destination database. The initial scratch evidence
above remains the prior inspection baseline, not the production adapter.

The [Loans opening-position contract draft](../contracts/loan-opening-position-mvp.md)
now specifies the requirements for active servicing: approved cutover principal/interest/fees,
paid-through/accrual basis, remaining obligations, collateral and future calculations.
Specify limited-evidence released record behavior separately. Neither needs invented
historical approvals or payments, and neither may weaken the existing complete-history
profile. Resolve source/schema and calculation discrepancies before financial commit.
The Excel adapter should reuse those contracts once established.

Production migration still needs a final consistent snapshot/write handover and
separate media source where only file paths are present. This review is a rehearsal;
no production import, deployment, data repair or counter rewrite was performed.

The [representative reconciliation worksheet](legacy-reconciliation-worksheet.md)
now makes the calculation choices concrete for the selected `jcl` cohort. It includes
exact source examples, a separate released payment control and owner response fields.
No agreed rule or cutover balances have been inferred from this comparison.
