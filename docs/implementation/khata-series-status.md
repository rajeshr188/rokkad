---
status: implemented-local
owner: loans
updated: 2026-10-03
tags: [khata, series, status, audit, verification]
related: [../adr/2026-10-03-khata-series-status.md, khata-action-guidance.md, ../flows/khata-account-workflow.md]
---

# Khata series lending status

The later [document-navigation checkpoint](khata-document-navigation.md) records the current
local runtime. Counts and identities below are the dated phase-seven evidence.

Phase seven adds setup-authorized, reasoned pause/resume and permanent retirement,
with signed review and immutable status history. Existing commands remain the
authority for lending and servicing. Pausing/retiring blocks new drafts, opening
approval, every withdrawal and limit increase, including existing accounts.
Interest collection, receiving/replacing/returning collateral, reductions and
settlement preserve their existing rules. Resuming does not override licence or
number-capacity checks. No account number, consumed counter or association changes.

Migration `0041_khata_series_status` branches from the verified Khata 0040 schema;
the full checkout's no-operation 0046 merge joins ordinary Loans' separate branch.
The candidate must overlay only this phase onto the prior verified Khata archive,
not ship unrelated ordinary Loans developments. The new directly Workspace-owned
status table has forced RLS and registry coverage; database triggers refuse direct
status rewrites and evidence edits/deletes and project valid transitions atomically.
Native recovery includes retirement and status events. Older archives remain
usable only with their matching schema/guard image or full database/media recovery.

## Verification and current local identity

The successful frozen image passes **480 Linux regressions in
290.652 seconds**, including 11 new status tests and existing archive,
ordinary/flexible, financial/custody, isolation and recovery checks. The focused
status run also passed (11 tests in 9.607 seconds). Initial attempts corrected test
fixture assumptions, an invalid-token error-display bug, the older direct-toggle
fixture and registry counts; none was activated in the pilot.

Actual setup-only browser acceptance creates one fictional unused series, reviews
pause, retries its exact confirmation, resumes and permanently retires it. Status
history retains actor/time/reason; draft choices exclude paused/retired series and
include resumed series. Viewer requests are refused; mobile and no-JavaScript
controls work. Four desktop/mobile screenshots are inspected without document
overflow or page errors. Prior tabs, servicing, collections/events, custody/QR,
exception, guidance and cash/custody report checks also pass. QA uses the exact
configured Bootstrap 5.3.8 bytes/SRI; app configuration is unchanged. Harness
locator fixes scoped CSRF to the status form and resolved repeated audit reasons;
interrupted checks were resumed through the controls, preserving all seven events.
No application edit follows the successful freeze.

Read-only fingerprints before/after browser checks match for all 12 account,
policy, financial, custody, photo and document tables. Only the explicitly
identified fictional setup series and its seven recorded status changes are added; it
remains unused at next number 1. No cash/custody confirmation is submitted.

Candidate: `khata-local-20261003-6bfe7f30d391`; image `sha256:31dabdc493e9070bd4d8a68d58a819974f7e6d4fa8e747f66172abdf8ef4d85f`.
Source digest: `6bfe7f30d391537d6dc7158c65ba446cfe3b938d83cf8f45cdcf6138fad23a0e`;
archive digest: `97bd378728c716ab71718240cc72fc88f6dc657cd907e9ff2e1275b8e4545239`.
Private evidence: `.tmp/khata-series-candidate-20261003-v4/`.
All **1,429 application/settings files** match the frozen manifest and image.
The 17 explicit application paths overlay verified `khata-local-20261003-ac52235bea54`;
all unrelated applications and ordinary Loans migrations retain their base bytes.
The full checkout's no-op merge and the composed image both pass model-drift checks.
Registry counts reflect each candidate's distinct model inventory; only the new
Khata migration is applied to the fictional pilot. PostgreSQL default grants keep
the new table/sequence accessible to the restricted runtime role, with forced RLS
and immutable transition guards intact.

Schema, dependencies, owner-startup refusal and restricted runtime/static checks
pass. Active web is non-root with read-only root; static volume is
`khata-series-20261003-v4-static`. Fictional database/media persist. Pre-migration
database/media backup hashes and stopped rollback
`khata-img-20261002-web-pre-series-20261003` are retained. Rollback web retention
does not claim a new full database restore rehearsal. No production migration,
deployment, commit/push or remote CI occurs. Hosted/operator recovery and physical
acceptance remain separate. Next: bounded, selected collateral label batches.
