---
status: active
owner: project
updated: 2026-10-10
tags: [implementation, portability, loans, rls]
---

# Browser restoration of supported loan files

PC-01/02 extend the existing **Import Loans** screen at
`/w/<workspace>/data-tools/loans/`. Staff can inspect the supported formats and
limits, upload a loan file, choose destination records, review reconciliation and
explicitly confirm restoration. The capability table states the exclusions;
this is partial loan exchange, not complete Workspace transfer.

The upload detects published history/opening JSONL, closed-position JSON and
servicing/closed-position ZIP profiles. Existing Loans parsers and commands remain
authoritative. Complete-history files continue through the existing history
review. Other supported files use a small `LoanRestoreBatch`, with no new financial
ledger or alternative interest calculation.

## Destination review

Source customer references can prefill an existing exact Party source identity.
Staff can search eligible destination customers, including inactive customers,
and explicitly choose destination series, licence revision and servicing product.
Closed-position files need only customer and series: missing historical terms are
not invented. Model choices and domain validation both enforce the destination
Workspace. Preparation does not post financial records.

The current owner/platform financial-import access policy controls preview and
confirmation. A signed, one-hour approval binds the actor, Workspace, source,
batch and mappings. Confirmation rechecks source bytes and reconciliation before
calling the existing Loans command. Successful retries return the completed
batch; the resulting ordinary loans are linked from its review screen.

## Persistence and rollout

Migration `data_portability/0020_loan_restore_batch` creates the directly owned,
forced-RLS batch table and PostgreSQL guards. Sources use private application
file storage and the existing storage inventory. Database metadata contains small
source references rather than package media or source bytes encoded as JSON.
Completed evidence is immutable. Cancellation clears an unfinished batch and
deletes its file after the database transaction commits. Reversing the migration
is refused while retained batches exist.

Existing profile limits remain enforced, including expanded ZIP bounds. SQL and
native database recovery uploads are rejected. The shared limit of 20 unfinished
loan imports applies to both history and file batches. Wider external registers,
representative-volume exchange and a fresh-Workspace business package remain
PC-03 through PC-06 in the [ordered plan](../plans/data-portability-completion-20261010.md).

Apply the migration through the owner-only migration settings before serving the
new code. Web processes retain the restricted runtime role. This local slice does
not migrate a shared development database or deploy production. The separate
port-8000 review snapshot must be deliberately refreshed and its isolated database
migrated before it can present these changes.

## Verification

All 128 regression checks pass. The run covers actual opening, servicing,
closed-position JSON/ZIP
and history restoration; non-posting preview; exact retries; changed source and
mapping rejection; required confirmation; private-file inventory/cancellation;
browser destination review/customer search; and restricted-role Workspace
isolation and database guards. Test fixtures use fictional records and a disposable
database, without changing live business data.

Model/migration consistency, supported-app import boundaries and local
documentation links also pass. Removal of the disposable test database is
verified. This verification includes browser HTTP flows;
visual acceptance of the new screen remains a local staff review step.

Concurrent Party/dashboard edits in the shared checkout caused an in-flight
interest-interface mismatch during the broader run. Final slice verification uses
the committed baseline `6dc71e4a` plus the 16 portability implementation/test files,
excluding those unfinished changes. It does not establish acceptance of unrelated
concurrent work or production deployment.

See the [accepted decision](../adr/2026-10-10-browser-loan-file-restoration.md)
and [dated architecture review](../architecture/data-portability-review-20261010.md).
