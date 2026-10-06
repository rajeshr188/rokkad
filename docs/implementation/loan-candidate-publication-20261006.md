---
status: active
owner: project
updated: 2026-10-06
tags: [loans, release, production, verification]
---

# Loan candidate publication and production acceptance

The owner requested proceeding with commit/CI, live cohort inventory, real source
examples and staging on 6 October. The accepted local LC-01–07 candidate includes
the separately completed LD work already committed on
`work/loan-servicing-contract-ld01`. Local source, finance/portability regressions,
restricted runtime and fictional full recovery are recorded in
[LC-07 delivery](loan-release-acceptance-lc07.md).

Candidate `b69df6ab71af27a85100cfa59325bd85f097323f` is committed and pushed.
Its clean committed-source image is `rokkad:loan-continuation-b69df6ab`, digest
`sha256:2453bbf53a5cd0642138b76d7900a2aad7cd7230638ec556162063e8ae4d629a`.
The first [exact-commit CI run](https://github.com/rajeshr188/rokkad/actions/runs/37455205020)
failed in foundation checks: 14 journey fixtures omitted current public-trial
requirements, and one auction-access mock omitted the command business-write
prerequisite. The fixtures are corrected without changing runtime policy:
verified sign-in email, explicitly selected six-member trial and current consent;
second-Workspace isolation fixtures use separate test commercial access. The
auction unit fixture verifies delegation to the business-write boundary.
All **24 journey/access tests pass** (117.532s) in isolated PostgreSQL QA; current
docs/import boundaries and whitespace checks pass. A new exact-head CI run is required.
The correction commit is `dce0d00a5e9b31979ed6d5ab98d50841cca3f91c`; its
[rerun](https://github.com/rajeshr188/rokkad/actions/runs/37456878400) passes the
foundation step. Its clean committed-source image digest is
`sha256:1b8d27d5f7bb8f8488c788368723973a87027dbe03ebee7b5001e2b8d878c37f`.
Production-settings restricted runtime, schema/cohort reads and actual owner-role
rejection pass on both fictional recovery databases, with all 202 public tables
unchanged. The first local owner-rejection attempt mistakenly retained runtime
credentials; it did not test owner startup and was corrected before reporting
the complete successful check. None of these are a production-copy rehearsal.

The release CI job allowance is raised from 25 to 45 minutes because the Loans
suite now contains over 1,800 test methods, besides foundation, recurring/mail,
quote/isolation and image gates. No checks are removed. A new exact-head run is
required after this workflow change.

CI on `dce0d00a` completed the 277-check billing/mail stage with one error in the
static invitation-flow assertion (not a billing/provider runtime failure).
CI on `422763d5` reproduces that same error. The old assertion expected invitation
mutation immediately after opening the transaction, omitting the current Company
lock, policy and capacity checks. It is corrected to compare policy/mutation order
within each function and retain the transaction-before-mutation assertion.
All **15 invitation static checks pass** locally (0.009s), after the runtime-image
QA harness was supplied with the required repository docs fixture. Publication
and exact-head CI await the corrected full Loans-suite run. The first local run
completed **1,296 tests in 821.602s**, with three failures and 82 errors. Its
namespace-package discovery imported many files without package context. An
explicit repository top level discovers **2,089 tests and zero import errors**;
the CI Loans command now specifies it. Three historical migration tests also
downgraded the shared database across an irreversible migration and left later
tests on an older schema. Separate empty migration-test databases now
copy only explicitly supplied generated fixtures and their
prerequisites, never production/customer records. The shared QA schema is restored.
The missing-submission-reference runtime correction preserves invalid POST
references instead of silently replacing them; explicit entry-purpose changes
still receive a new form reference. Quote-policy and receipt-format unit fixes
pass **three checks** (0.041s). All **41 migration/submission/opening/paper-entry/
recovery regressions pass** (215.625s), including all three isolated populated
upgrades and exact recovery. PostgreSQL's earlier deadlock log identifies
autovacuum competing with the test fixture transaction; the isolated recovery
rerun passes. No recovery lock is weakened and autovacuum is not disabled.
The correctly discovered full suite and exact-head CI remain pending.
CI must pass against the exact published commit before
the candidate is treated as verified for release. Real-source acceptance and the
production-copy migration rehearsal are additional gates; a branch push does not
deploy the application. No live loan, source archive or risk snapshot is changed
by this verification.

## Production baseline captured on 6 October

The established deployment transport is available. A probe inside the existing
production app verified a non-superuser/non-bypass runtime and PostgreSQL
repeatable-read/read-only enforcement. The database is
`rokkad_production_20260924`; Loans is at `0032_series_partial_interest` and
data portability at `0017_loan_history_v2`. The live application image is
`rokkad:ticket-autofit-20261001-8dd479dbb0bf`.

The following is one consistent read at **16:43:27 IST**, not a frozen ongoing
claim. Staff were recording real JSK closures between probes.

| Workspace | Active | Closed | Other states | Retained archive snapshots |
| --- | ---: | ---: | --- | ---: |
| JCL | 2,592 | 10 | 1 approved | 26,664 |
| JSK | 1,585 | 73 | 1 approved, 6 cancelled | 3,840 |
| Lakshmi Pawn Broker | 2,440 | 0 | 2 drafts | 8,711 |

These archive counts are retained evidence, not automatically admitted ordinary
closed loans. Source financial-origin event counts are JCL 165 disbursals/2,438
openings, JSK 145/1,514 and Lakshmi 2/2,439. Counts of source events are not current
active-origin counts: reversals and current state must be examined by the candidate
on an isolated, consistent production restore.

The owner confirmed **JCL RA00500** (correcting RA0500). It is an active loan dated
2 September 2026, principal 60,000 at 2% monthly, three-month tenure, admitted by
a 24 September migration opening. It is an opening example, not direct lending.
Its recorded principal is not proof of collection interest or complete books.

The owner also selected **Lakshmi D01623**. Rokkad stores a DRAFT with an October
2 disbursal and its reversal, so its current recorded debt is zero. The owner
confirmed the actual paper facts: 24 September payout, principal 2,100 at 4%
monthly, 84 advance interest and 10 document charge, net proceeds 2,006,
three-month tenure and no later receipts or closure. Verification must preserve
the reversal and test the retained-native correction adapter; no actual source
event or draft has been changed. The current 12-month standing default must not
replace the actual three-month agreement.
Borrower names, documents, attachments and free-text evidence are not included in
the sanitized baseline. Private probe evidence is under
`.tmp/lc07-publish-20261006/`.

## Production-copy approval gate

Automatic approval review rejected the full server-side production copy because
the general staging authorization did not explicitly cover the sensitive payload
and destination. The rejected operation did not execute. Specific approval is
pending for copying `rokkad_production_20260924` into the new private database
`rokkad_lc07_stage_b69df6ab_20261006` on the same established server. Full backups
would remain in its private deployment folder, without a customer-data download
to this local workspace. A separate runtime role, local file storage, disabled
notifications/provider calls and no public routing are required. Production
data/application remain unchanged. This duplicates all tenants' sensitive records
and consumes disk; no workaround or indirect execution is authorized.

## Selected-source correction finding

A further restricted, repeatable-read/read-only probe at **17:02:26 IST** found
that D01623's retained approval is dated 2 October and freezes a 2 October loan
date. It is not an original-day approval for the confirmed 24 September paper
payout. Lakshmi's digital economic/rate policies were created on 25 September
and 2 October; even the later backdated-effective policies were entered after
the actual day's cutoff. The retained-native correction path therefore cannot
establish the required original-day evidence.

A generated, customer-free reproduction under a restricted non-bypass role
confirms this boundary (**one test passes**, 0.736s): after a later-dated native
payout is fully reversed and the draft has its actual earlier paper date, the
adapter selects retained-native review, finds no qualifying approval/policy,
and rejects review. General completed-draft admission also rejects existing
posted history. The original approval/events remain unchanged and debt stays
zero. This is a guarded unsupported correction, not successful paper admission.
The reproduction is not a production-copy migration rehearsal.

Before claiming D01623 can be recorded or accepted, add an explicit reviewed
paper correction for this fully reversed native shape. Retain the same loan,
number/items, old approval, payout and reversal; validate the actual agreement,
deductions and proceeds; then establish one supported unreversed recorded origin
without claiming a historical digital approval. Preserve ordinary unpaid-draft
admission and the stricter retained-approval path. Do not select a weaker writer
automatically after a missing/stale evidence or authorization failure. This
requires targeted command, chronology, retry, reversal, servicing and isolation
checks; it is not resolved by removing an old price/policy cutoff.

## Next verification gates

1. Commit and publish the complete candidate, then dispatch the Workspace CI
   workflow explicitly because this working branch is outside its push filters.
2. Prepare a consistent production checkpoint and restore it to a new isolated
   target on the established host. Keep full database/media/customer artifacts on
   the server; only sanitized counts, hashes and acceptance results may be copied
   into this local workspace. Do not apply candidate migrations to production.
3. Rehearse the actual upgrade from 0032, including intervening LD/Khata changes,
   through owner-only migration settings. Verify isolated restricted-runtime reads,
   unsupported cohorts, saved source integrity and exact recovery.
4. Compare the confirmed JCL reference and a real Lakshmi paper case with actual
   books; staff must confirm the source figures, including receipts and remaining
   principal or closure. Software-generated facts alone do not provide acceptance.
5. Resolve findings and verify release identity, CI, current backup/recovery and
   compatible web/worker readers before deployment.

See the [acceptance matrix](../flows/loan-continuation-release-acceptance.md) and
[consolidation plan](../plans/loan-continuation-consolidation.md).
