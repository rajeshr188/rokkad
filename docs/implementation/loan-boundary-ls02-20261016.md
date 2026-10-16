---
status: verified-locally
owner: loans
updated: 2026-10-16
tags: [loans, origination, completed-payout, verification]
related: [../adr/2026-10-16-completed-payout-purpose.md, ../plans/loan-boundary-simplification-20261016.md]
---

# LS-02: Shared completed-payout review

## Scope

Implement the second owner-approved simplification slice. Preserve uncommitted
LS-01 timing work and committed correction/Party-merge source. No production data,
configuration, migration, Git publication or deployment is part of this slice.

## Changes

- Unpaid drafts with or without earlier approval use the same completed-fact
  screen. Step one reads saved customer, number, date, product and collateral;
  step two reviews the agreement, actual cash and recording explanation.
- Common service commands build the recorded input under existing Workspace and
  loan locks and call the canonical recorded-history preview/admission engine.
  Standing setup supplies defaults; frozen approval economics take precedence.
- Retain approval identity, original monetary terms and quote observations. Quote
  corrections/withdrawals require explicit review and are bound into source proof,
  not used as a new original valuation. No replacement approval is created.
- Check retained agreement/item principal, rates, amounts, precision and supported
  fee/calculation semantics. Different financial facts require reconciliation.
  Canonical same-customer borrower merge chains remain supported.
- Preserve old native and recorded signed POST dispatch, retries, existing draft
  numbering and one-origin protection. Fully reversed/posted histories retain
  correction guards. The new editor does not attest complete paper books.
- Routine monitoring/rounding defaults are hidden when supplied; missing values
  remain explicit. The final review explains the shared monthly boundary.

## Verification

The wider **193-case regression passes in 195.306 seconds**: common/legacy payout
reviews, recorded admission and history, ordinary current origination and quote
rules, origination corrections, portable correction, recorded servicing bundle
re-export, LS-01 monitoring timing and desktop/phone layout checks.

Following final input-error handling and presentation changes, the **68-case
affected selection passes in 45.053 seconds**. An additional new restricted-role
command test passes in 1.226 seconds. These 69 final acceptance cases are disjoint
between those two runs, but overlap the wider 193-case run; do not combine the
wider/final counts into a unique total.

Coverage includes one financial origin and unchanged counters/items, retry safety,
separate review step, retained approval bytes, explicit changed-quote review,
stale-source rejection, a valid original prior-day quote, actual deductions,
different-rate item allocation, audited borrower merges, actor-bound confirmation,
old signed POSTs and recorded/native corrections. Staff with recorded-entry
permissions can record facts while remaining unable to approve a new loan.
The final restricted-role check proves NOSUPERUSER/NOBYPASSRLS command success
under the matching Workspace and refusal of foreign-Workspace input.

An owner-only disposable-database exact restore/re-export preserves all tables,
files, reconciliation and guards, including the retained approval and its changed
quote observations. The final browser case captures facts/review at 1365 and 390
pixels, verifies no horizontal overflow and a required final confirmation, and
uses the actual shared agreement partial. Representative screenshots were
visually inspected; output is under `outputs/loan-boundary-ls02/`.

Django checks, migration/model consistency (no migration), supported-app import
boundaries and whitespace checks pass. Current documentation links pass.

Use the dedicated Django database `test_rokkad_ls02_20261016`, selected by
`DB_MIGRATION_NAME=rokkad_ls02_20261016` with test settings. Browser checks intercept
every request and use fictional Django responses, local static assets and cached
Bootstrap; they cannot submit to production.
The dedicated database was removed after acceptance and its absence verified in
the PostgreSQL catalogue. Fictional test logs/screenshots remain local and ignored.

## Release

No new schema migration or financial export profile is introduced. Pending LS-01
V10 still requires matching readers at release. Older issued reviews may require
refresh if their bound source evidence changed; they retain their original
command and cannot be silently reinterpreted. Ordinary current lending remains
subject to approval and quote rules. Deployment and real-loan actions are separate.
