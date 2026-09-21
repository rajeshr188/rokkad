---
status: accepted
owner: project
updated: 2026-09-13
tags: [loans, portability, archive, rls]
---

# Retain incomplete closed-loan source claims separately from operational Loans

The owner authorized the bounded historical-only archive slice after freezing
the opening v1 wire contract. A source can report a released loan while its payment
book, borrower mapping, dates or collateral evidence are unavailable. Requiring
an operational PawnLoan would either reject the history or invent financial facts.

Add `loan-closed-evidence/1` for one source-reported closed loan. Acceptance means
retention of source claims, not verified closure, settlement, custody or balances.
Unknown values stay null; reported zero and an explicitly empty list remain distinct.
Preserve normalized facts and supplied raw source records. Contradictory date order,
nonzero reported balances and duplicate payment claims are displayed as findings
and retained without correction. The bounded checks do not certify source truth.
Active claims require a separate future profile; no old-age or product-policy gate
applies to this archive.

Loans owns immutable `HistoricalLoanEvidence`, directly Workspace-owned and protected
by forced RLS. It has no foreign key to PawnLoan or Party. The source namespace,
source system (including its tenant scope), source loan ID and canonical document
SHA-256 identify a snapshot within a Workspace. Identical retries reuse it; changed
documents append distinct snapshots. No revision automatically supersedes another.
This identity is not an operational financial-origin binding.

Data portability owns `LoanArchiveBatch` for upload, review, explicit acceptance
and cancellation. It is separately Workspace-owned with forced RLS. The signed
approval binds Workspace, operator, batch, document and review findings and expires
after one hour. Acceptance rechecks current authority under the Workspace lock,
then writes evidence, audit and completed batch atomically. Cancellation clears
only unfinished staged content. Finished batches and accepted evidence cannot be
updated or deleted; SQL guards also verify batch-result Workspace/document binding.
Both tables are created with their ownership, RLS and guards in the same migration.

Reuse the existing owner historical-import gate for staging and acceptance:
matching context, current membership/platform override, ACTIVE Workspace and
data.view/data.import/workspace.settings.manage. No approve/disburse/repay grant
or local borrower/setup mapping is needed because no operational rows are created.
Historical browsing requires data.view; export additionally requires data.export,
without import/setup grants. Current ACTIVE lifecycle restrictions remain; broader
recovery export policy is a separate slice. Services authorize before lookup/replay.

The Workspace navigation and Loans import page link to a separate historical
archive. Its review/detail pages label every record as source evidence and expose
all supplied facts for review. A record has no servicing action or operational
loan-detail link. Borrower references remain unresolved claims; no Party is created
or linked by name. Normal loan balances, obligations and custody readers remain
unchanged.

Export writes the exact accepted document values in canonical JSON, retaining
decimal spellings and original source references. Reaccepting in another Workspace
preserves those values while recording a new local acceptance actor/time. These
local audit fields and staging history are not impersonated or part of the portable
source document. Binary files and authenticated source extraction are outside this
profile; evidence references are claims, not proof of authenticity.

No active reconciliation, admission link, live backfill, existing-loan mutation or
real-source migration is authorized by this implementation. Disabling uploads can
stop new acceptance while preserving existing evidence and export access. Do not
roll back a deployed populated archive by dropping its tables. See the
[contract](../contracts/loan-closed-evidence-v1.md),
[flow](../flows/historical-loan-archive.md) and [Status](../STATUS.md) for validation.
