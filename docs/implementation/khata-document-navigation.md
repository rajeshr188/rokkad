---
status: implemented-local
owner: loans
updated: 2026-10-03
tags: [khata, documents, navigation, local-pilot]
---

# Khata presentation and saved-document navigation

Phase 9 adds 25-row saved-document pages with title/reference/identity search,
document-type/date filters and deterministic issued-time ordering. Filters read
retained payloads, rather than substituting current account facts. Existing exact
private downloads and correction/source relationships remain authoritative.

The active mobile tab is positioned in view. A server-rendered section chooser
also works through ordinary GET without JavaScript. Action forms/reviews have
fixed same-account return links; interest/finalization returns to Interest,
agreement work to Actions, withdrawals/settlement to Overview and corrections to
their new source-history event. Existing exchange/receipt/pending-return routing
is retained. The recent photo disclosure shows up to 25 and links to the existing
searchable collateral browser. New-issue source choices remain the original
complete operation selector; this phase bounds saved issues, not that selector.

## Verified local identity

- Candidate: `khata-local-20261003-2216df647199`.
- Image: `sha256:0c865188048aa179eb4d3a4f26145563aeff3c1616f8399ca18d63b0675ca417`.
- Source: `2216df647199940b63c27c620c84353cc7d202672e6d7c62da6f046178e689f2`.
- Archive: `dba8fbd73531de729b232b6588961aa22ddc9558addef81832c0d430d5597c4f`.
- All **1,435 application/settings files** match the built image. Exactly twelve
  UI/read/test paths match the scoped worktree overlay; the other 1,423 paths retain
  the [verified label base](khata-label-batches.md). Unrelated ordinary Loans
  development and migrations are excluded from this candidate.
- **29 focused checks pass in 14.083 seconds**; **498 frozen Linux regressions
  pass in 250.389 seconds**, including financial/custody, isolation, ordinary/flexible
  and archive coverage. Frozen and full-worktree models have no migration drift.
- Dependencies, owner-runtime startup refusal, restricted runtime/static startup
  and current migration checks pass. No migration is applied by this phase.
  Pre-switch database/media backups and the previous stopped web container are
  retained; the verified candidate is running at `http://127.0.0.1:8077`.

Actual desktop/mobile browser checks pass: 28 saved issues paginate as **25 + 3**;
search, document-type filters and issued ordering persist across pages. Exact label
and request UUIDs find the original issue; its private download retains the saved
SHA-256 and no-store response. Invalid ranges show an error without partial results.
Fixed contextual links ignore arbitrary external return URLs. The active mobile
tab stays in view and the section chooser/filter form also work without JavaScript.
Viewer metadata remains available while export and issue controls are refused.
Desktop/mobile/no-JavaScript screenshots are inspected; no overflow or page errors
are observed. Signed interest confirmation/retry routing and source relationships
are exercised by tests, rather than posting cash in the browser trial.

The isolated fictional draft **QNAV00001** (account 9) has one simulated collateral
receipt, 27 statements and one label for navigation acceptance. It remains unapproved
with zero principal, withdrawals and interest. Every pre-existing financial/custody/
policy/series/document row and media byte is unchanged. Restricted-runtime readiness
passes; the native archive retains all fourteen tables, 39 files and all 28 fixture
issues. Its guard fingerprint matches the preceding label build. An evidence-helper
comparison initially used an integer against the archive's string-encoded foreign
key; correcting that helper resolved the assertion without application changes.

No schema, money/custody command, authorization contract, original document bytes
or native recovery guard changes. Production, remote CI, named operator trials,
hosted deployment, off-device recovery and physical camera/printer/QR acceptance
remain separate gates. Broader correction outcomes and optional reminders retain
their design boundaries in the [delivery sequence](../plans/future-work.md#improvement-delivery-sequence).
