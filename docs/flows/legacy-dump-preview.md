---
status: active
owner: project
updated: 2026-09-12
tags: [portability, legacy, operator]
---

# Preview a legacy PostgreSQL dump

This offline operator command reads the previous application's custom-format dump
and prepares a source review. It does not connect to either business database,
execute archive SQL or legacy code, import records, or approve opening balances.
It lives in the existing portability app; the first slice has no browser upload.

Use the installed PostgreSQL client `pg_restore`, not `psql` or database restore.
Python/Django still needs the normal project environment. Use restricted runtime
settings (`django_project.settings.dev` locally); migration/owner credentials are
unnecessary. The command skips database system and migration checks.

## Discover source schemas

```powershell
.\.venv314\Scripts\python.exe manage.py preview_legacy_dump `
  --dump .\rokkaddb_prod_full_2026-04-10.dump `
  --list-schemas `
  --pg-restore 'C:\Program Files\PostgreSQL\17\bin\pg_restore.exe' `
  --settings django_project.settings.dev
```

This returns schema/table inventory and archive SHA-256 without source rows. A
business schema is selected explicitly; public is excluded. This is source tenant
selection, not authorization or a binding to a destination Workspace.

## Generate a preview

The first owner-selected source is `jcl`. The following namespace was assigned to
this legacy installation's pilot. Reuse it for later snapshots; do not generate a
new namespace for every dump, tenant, preview or retry. Unrelated installations
must use their own UUID.

```powershell
.\.venv314\Scripts\python.exe manage.py preview_legacy_dump `
  --dump .\rokkaddb_prod_full_2026-04-10.dump `
  --source-schema jcl `
  --source-namespace 6ca968d6-2647-4dbb-8e39-24f0c1a12ed6 `
  --output-dir .\.tmp\legacy-preview-jcl-next `
  --pg-restore 'C:\Program Files\PostgreSQL\17\bin\pg_restore.exe' `
  --settings django_project.settings.dev
```

Choose a new output directory for each run. Existing directories/reports are never
overwritten. `--pg-restore` may be omitted when the executable is on PATH. Only
lowercase ASCII business schema identifiers are supported in this bounded adapter.
With an explicit source schema, unrelated schema names do not block extraction;
general inventory mode still validates every listed table identifier. The adapter
accepts the two inspected legacy shapes: the original columns and the later
item `is_repledged` / series `loan_type` additions. Values remain source evidence;
repledged/unknown custody and non-Given series hold affected loans for review.
Unknown columns and rows outside the selected schema remain errors.

Open `review.html` in the output directory. It shows source counts, active/released
review cohorts, proposed entity mappings, issue totals and the first 200 error
occurrences. It also lists excluded tables and unresolved migration decisions.
`records.jsonl` includes every selected source row, its unchanged decoded facts,
stable source reference, proposed identity, source hash, parent references, review
route and all issues. `summary.json` contains machine-readable totals and source
namespace/fingerprint. A `COMPLETE` file is written last; without it, the output is
unfinished and must not be treated as a completed preview.

These are private source review files, not import packages for the Party or Loans
upload forms. Keep them in a private local location. The output directory includes
a `.gitignore` covering its contents. HTML escapes source values and loads no scripts
or external resources. A source row without errors is still not import-ready.

## Propose skipping incomplete collateral

Add `--propose-skip-incomplete-collateral` to the preview command to produce an
unapproved selection proposal for the initial migration. Use a new output directory.
The rule `incomplete-collateral/1` checks structured item presence, description,
positive weight/quantity/allocated principal and valid percentage purity; fractional
quantity is invalid. If any item fails, propose skipping its whole loan together
with all items, payments and releases. No age cutoff, payment-history filter, metal
filter or photo requirement is inferred.

`records.jsonl` still contains every source row and its original facts, hashes,
references, issues and review route. Proposed dispositions are additional fields;
customers and setup records stay available. `proposed-exclusions.jsonl` lists each
proposed skipped loan and its reasons. The HTML/summary show counts and stored
principal sums by released/unreleased state and proposed treatment, with unknown
amounts counted separately. These sums are not verified outstanding balances.

The proposal records `approved: false` and a selection fingerprint tied to source
evidence. This is not an approval token, deletion, debt settlement or importable
package. Financial selection and balances require a later concrete review.
See the [opening-position contract draft](../contracts/loan-opening-position-mvp.md).

## Prepare active opening reviews

Add `--prepare-openings` together with `--propose-skip-incomplete-collateral` to a
tenant preview command, using a new output directory. The adapter emits opening
review documents for retained unreleased loans, alongside the unchanged full source
review. It copies known source fields and leaves unverified balances, weight meaning,
due terms, interest continuation and destination mappings empty. It does not infer
financial values from missing payments or turn released records into active loans.

Open `opening-review.html` for the per-group missing-information counts and
`opening-results.jsonl` for all issues. `opening-candidates.jsonl` is generated
technical input for further review, not something users must manually author.
Use `validate_loan_openings --input <review.jsonl> --output-dir <new-directory>`
with the same settings to revalidate reviewed evidence without database access.
See [review shape, bounds and checks](../contracts/loan-opening-review-v1.md).
A report can complete with unresolved issues; even a reconciled document is not
approved or import-ready. The overall `COMPLETE` marker is written after both reports.

## What is checked

For a representative worksheet, additionally supply `--reconciliation-as-of` and
`--reconciliation-timezone`. The command emits `reconciliation.json` containing
source-linked examples and competing legacy expressions at that explicit comparison
date. It includes a separate released-payment control when available, without
changing the active selection. See the [worksheet guide](../implementation/legacy-reconciliation-worksheet.md).
No expression is adopted as an agreed financial rule by this comparison.

Nine tables: customers, contacts, addresses, licences, series, loans, loan items,
payments and releases. The parser requires the exact observed column sets, unique
positive source primary keys and complete COPY sections. Missing fields, extra
fields, cross-schema sections or duplicate primary keys fail extraction rather
than being silently omitted or remapped.

The preview checks customer/setup/loan/collector references, financial number and
event timestamp syntax, selected nonpositive values, duplicate loan numbers,
multiple releases, loan/item principal and monthly-interest totals, stored payment
split arithmetic, and events dated before their loans. It flags missing item rows,
payment rows, collectors and unresolved relation/metal/setup mappings. Linked
item/event errors also appear on their loans, so issue totals can count both the
source error and its parent finding. Counts are not unique rejected-loan totals.

Known source facts remain distinct from calculations and verified destination
evidence. For example, a release without a payment can be a valid source record;
the preview does not fabricate its settlement. Loan-level interest is stored money,
not an inferred percentage. Missing item rows do not cause inline weight strings
to be interpreted as a guessed gross/net weight. It does not certify economic
balances, payment completeness, exact production code version, licence validity,
historical valuation, custody, or compatibility with current servicing policies.

## Bounds and next action

For the owner-reviewed `jcl` source only, add `--owner-profile jcl-owner/2` to a
preview with `--prepare-openings`, `--propose-skip-incomplete-collateral`,
`--reconciliation-as-of` and `--reconciliation-timezone`. The profile is restricted
to namespace `6ca968d6-2647-4dbb-8e39-24f0c1a12ed6`; it maps structured source
weight to net weight with the owner attestation, while leaving gross unknown.
It also writes `owner-rule-review.html` and separate owner-rule diagnostics in
`reconciliation.json`. These illustrate collection under the confirmed inclusive
anniversary rule for reconciled monthly item charges and unchanged principal.
The rehearsal sums item charges, multiplies by additional months and rounds once
to whole rupees with HALF_EVEN. Actual collections and accepted interest losses
are separate and remain unknown where evidence is missing. Source errors and
payment treatment still cause holds; no automatic tolerance or waiver is applied.
Version 1 remains available with its prior whole-rupee-only calculation behavior.
The comparison date is still a rehearsal assumption. No opening balances or
current servicing rules are changed, and the owner-edited workbook is untouched.
See the [updated profile](../implementation/legacy-reconciliation-worksheet.md#negotiated-collections-and-version-2-2026-09-12).

Maximum custom archive: 64 MiB; selected extracted data: 128 MiB; inventory: 4 MiB;
selected source records: 100,000 across all nine tables; row: 128 KiB; decoded field:
4 KiB. Each pg_restore extraction/list process has a 60-second read limit and bounded
output. Nonzero exit/timeout errors are sanitized; private subprocess stderr is not
printed. Temporary archive copies are removed after extraction. There is no database
write, approval receipt, resumable import or recovery job in this command.

The representative [source worksheet](../implementation/legacy-reconciliation-worksheet.md)
is now prepared. Next, review its Interest rule and Payment coverage decisions against the
[opening-position contract draft](../contracts/loan-opening-position-mvp.md) for
owner review of agreed interest rules, rehearsal cutover and balance evidence.
The [offline validator](../contracts/loan-opening-review-v1.md) now identifies
missing facts; active servicing and the limited-evidence released-record contract remain separate. Source selection
does not select the destination Workspace; Party, licence, series, product and
financial mappings require explicit review before any later staging or commit.
The Excel adapter will reuse those same domain contracts. See the
[source review](../implementation/legacy-dump-source-review.md) and
[decision](../adr/2026-09-12-offline-legacy-dump-preview.md).

A fully reviewed single-loan candidate can now proceed through the
[source-verified opening staging flow](legacy-opening-import.md). That separate
command re-extracts the dump, stages source evidence and gives the owner a browser
review URL. The read-only preview command above still performs no database writes.
Unknown business facts remain held; the bridge does not fill them automatically.
