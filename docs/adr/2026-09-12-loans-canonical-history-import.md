---
status: accepted
owner: project
updated: 2026-09-12
tags: [loans, portability, jsonl, rls]
---

# Canonical complete-history JSONL delivery

## Decision

The owner selected canonical JSONL as the first source format. Implement one
complete loan per file using [loan-history/1](../contracts/loan-history-jsonl.md),
covering active and fully released flexible partial-payment loans together.
The existing Party pipeline resolves borrower identity; destination licence,
series and product selections stay explicit. No vendor/Excel adapter is added.

Loans owns the historical command, financial reconciliation and native export.
Data portability owns upload, persistent staging, signed approval and HTTP review.
The Loans bridge checks exact Party source identity again at the command boundary;
it cannot accept a caller's arbitrary borrower mapping. It introduces no new
financial rules and does not invoke current-date workflows as historical replay.

Preview executes the full command inside a rolled-back savepoint, then saves the
mapping and summary. No external side effects or on-commit callbacks occur in the
command. Commit serializes through the Workspace and loan aggregate, verifies
approval identity/digest/expiry and current authorization, and repeats all checks.
Any late failure rolls back the loan and its financial/custody evidence together.
Preview may consume PostgreSQL sequence IDs, but it allocates no live document
numbers and retains no business rows.

## Persistence and provenance

Loans migration 0009 adds immutable HistoricalLoanImport, one per restored loan,
with unique Workspace/source namespace/source ID, source checksum, canonical
source document, destination references, original source identities and importer.
Source actors and original timestamps remain explicit historical evidence; local
recording actors/timestamps name the import operation. SQL rejects UPDATE/DELETE
and foreign-Workspace loan references. A changed accepted source is a conflict,
not permission to replace a loan. Later native servicing appends normal evidence.

Portability migrations 0011–0012 add LoanHistoryBatch and finish its Workspace and
result references before enabling runtime registration. Migration 0011 immediately
enables forced RLS with no policy, denying restricted-role DML until 0012 installs
the Workspace policy. Finished batches and source
identity are SQL-guarded. Explicit cancellation clears unfinished staged values;
it cannot delete completed source evidence. Both models have direct non-null
Workspace ownership, forced RLS, restricted-role tests and registry coverage.

Canonical export freezes a supported current graph under the aggregate lock,
retains original imported identities and appends portable identities for subsequent
supported native events. Export records an audit entry and may allocate missing
Party/Workspace portable identities. It is a partial operational-history export,
not a full archive or attachment restoration. Missing native frozen evidence,
unsupported financial events, storage/funding history or unlinked accrual evidence
fail explicitly. Collector claims are not converted to locally verified identity.

## Consequences

The bounded workflow is usable without building bulk bundles, history filters,
opening positions, setup import or a generic vendor mapping engine. Owners can
retry identical history without duplication and continue servicing restored active
loans. Exact original operational numbers remain source aliases; local historical
numbers use the previously accepted deterministic namespace and do not consume
live counters. External vendor compatibility still requires a representative
source with sufficient original facts. Expanded structures need separate contracts.
