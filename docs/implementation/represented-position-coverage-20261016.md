---
status: locally-verified-release-pending
owner: loans
updated: 2026-10-16
tags: [loans, monitoring, coverage, reconciliation, notices]
related: [../adr/2026-10-16-represented-position-transaction-coverage.md]
---

# Represented-position coverage and optional book reconciliation

The owner accepts the treatment change: use available accepted financial facts,
without compulsory individual or bulk confirmation of unseen paper activity.
The implementation is local; production remains on its recorded release.

## Read boundary

`selectors/transaction_coverage.py` adds `recorded-position-coverage/1`. A scoped
supported financial origin/checkpoint and consistent continuation/obligations
establish `RECORDED_POSITION`. Missing or unsupported financial evidence returns
`UNAVAILABLE`. An explicit latest unresolved-activity report returns `INCOMPLETE`
until superseded; a later payment alone cannot silently resolve a free-text report.
The boundary reuses prepared financial inputs/exposure during monitoring rather
than fetching/calculating them again. Standalone servicing reads use supported
collection position, without requiring an unrelated future forecast; monetary
components must be finite, nonnegative and reconcile. Full risk calculations keep
their existing stricter financial/obligation checks. It never posts or alters a loan.

`transaction_completeness.py` keeps its existing book-assurance meanings for
immutable reviews and published portable histories. Missing, aged or changed
positive assurance no longer makes a supported represented position incomplete.
New position evidence nests the original book evidence separately. Accepted
openings retain their checkpoint/history boundary; accepted terminal positions
retain unavailable earlier cash. No complete lifetime transaction history is claimed.

Risk, saved assessment provenance, live evidence disclosures, optional servicing
metadata and auction prerequisites use the shared new boundary. Snapshot V13 makes
older derived assessments due for ordinary refresh without rewriting old results
as current. Financial formulas and valuation policy/freshness are unchanged.

## Staff presentation

Dashboard/Loan health distinguish usable represented positions, known unresolved
activity/unsupported positions and unknown/outdated results. Optional current book
checks count actual CONFIRMED/ROKKAD_ONLY assurance, not ordinary capture assumptions.
Loan detail, reports and statements label book checks optional; an aged positive
check does not assert missing activity. Known unresolved reports remain warnings.
The in-app owner guide and repository staff/developer references describe the new
treatment. Original reporting/portable book fields retain their published meaning.

Existing single and up-to-50-loan paper/mixed reviews remain available. A wider
future-capture batch choice is optional future assurance, not a migration prerequisite.
No automatic group attestations, invented reviewers or new capture setting is added.

## Servicing, communications and retained evidence

Auction still requires supported debt, existing authority, chronology, statutory
service, custody and exact settlement. Existing positive book assurance may be
carried through the supported closure; absence of assurance creates no new review.
New recovery memos describe represented-position support using the existing
Collection basis binding. Already-issued bytes/legacy evidence stay unchanged.

Paper/opening borrower reminders keep the existing reviewed risk-notice workflow,
consent, channel/provider, quiet hours and active/current-risk checks. New position
intents without current book assurance bind exact current source/date/amount under
the explicit new contract. The compatibility payload key remains `transaction_review`,
with null `review_id`; there is no fabricated review FK or reviewer. A genuinely
current review-bound intent retains the old contract. Already-issued legacy intents
are not silently upgraded. Source changes require a new preview/intent; current
positive optional reconciliation alone need not invalidate a position-bound intent.

Migration 0090 extends the existing no-review notice uniqueness with position
fingerprint identity, preserving old omitted-key identity. It protects new frozen
content and source relationships from replacement, preserves existing review guards,
and refuses downgrade while new position-bound notices remain. No table, ownership,
authorization or RLS change is introduced. It depends on pending 0089 policy lifecycle;
release must include compatible model/schema/readers together. Do not deploy a lone
web change, edit accepted financial records or remove old attestations.

The checkout also contains the independent pending
`0090_transaction_review_history_boundary` guard. The empty
`0091_merge_position_and_review_boundary` migration joins those two branches;
neither function overwrites the other. This preserves the separate checkpoint
review correction while keeping one unambiguous migration leaf for release.

## Verification

The final **235-case affected regression passes in 246.516 seconds**. Coverage
includes native/paper/opening positions, interest and balance parity, optional
assurance aging/change, known missing activity, prepared scope/date checks,
single-read query bounds, source-bound reminder replacement/dispatch, consent,
restricted-role content immutability, same-position SQL uniqueness and downgrade
refusal. Existing review signatures, legacy queued intent guards, auction statutory/
custody/exact settlement and supported correction/continuation paths pass.

The final run includes **ten desktop/phone states** at widths 1365 and 390: live
detail, independent observation, portfolio, dashboard and optional review. Real
tab/disclosure controls, overflow, required visibility and currency checks pass;
representative screenshots are visually inspected. Fictional responses and cached
assets intercept all browser requests; no external source or borrower is contacted.

Development runs expose and fix the old assumption that auction coverage always
names a review, repeated financial reads when requesting metadata, and an overly
broad requirement for a future forecast when only a supported collection position
is needed. An earlier 433-case broad run had 423 passes and ten failures/errors;
all failing cases are included in the final passing selection. The full 433-case
selection is not rerun after those refinements. The 102-case intermediate selection
also identifies an obsolete provisional-count assertion, corrected in the final
run. Selections overlap and must not be added as a unique total. Existing
appraisal-specific fixtures now explicitly select appraisal rather than depending
on the subsequently changed default.

System/model/migration checks pass. Import boundaries pass for 1,226 tracked Python
files and the four new source/test/migration files. Documentation links and
whitespace checks pass. The isolated QA database applies both independent guard
branches and the empty merge, then verifies one Loans migration leaf, no pending
Loans migrations, retained legacy/new notice protections and the opening checkpoint
guard. These are local QA checks, not production deployment evidence.

Only the isolated `test_rokkad_transaction_coverage_20261016` database is used;
it is removed after verification and its absence checked.
No production access, money action, external message, bulk confirmation, worker
configuration change, shelved load test, Git commit/push or deployment is performed.
