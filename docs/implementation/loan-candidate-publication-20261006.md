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

Publication is in progress. CI must run against the exact published commit before
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

Exact **RA0500** is absent from JCL's ordinary loans and archive numbers. One
leading-zero match, **RA00500**, is an active loan dated 2 September 2026. The owner
has been asked to confirm that identity before it is used as the selected case.
A real Lakshmi paper reference and source/staff confirmation remain outstanding.
Borrower names, documents, attachments and free-text evidence are not included in
the sanitized baseline. Private probe evidence is under
`.tmp/lc07-publish-20261006/`.

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
