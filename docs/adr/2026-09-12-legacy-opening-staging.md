---
status: accepted
owner: project
updated: 2026-09-12
tags: [portability, loans, staging, approval, rls]
---

# Source-verified legacy opening staging and browser approval

Reuse LoanHistoryBatch with an immutable profile discriminator. Existing rows and
complete-history APIs remain `loan-history/1`; the first legacy bridge uses
`legacy-opening/1`. Separate list/review routes prevent one financial contract from
being processed through another's handlers. No new Workspace-owned table is added.
Migration 0013 adds the profile and SQL checks for immutable supported profiles and
an exact accepted-result document, retaining existing forced RLS and source guards.

An operator stages one fully prepared v2 review plus explicit setup against the
original custom archive. Authorization precedes source access. The existing
bounded pg_restore adapter reads a private snapshot without restoring or executing
SQL. Staging rebuilds the exclusion proposal and owner-scoped candidates, then
compares source identity, archive and selection hashes, original loan number,
borrower, complete item set and physical/economic item facts. It rejects source
errors, exclusions, released loans, payment rows, changed principal and invalid or
conflicting recorded tenure. The first bridge is restricted to the agreed
`jcl-owner/2` scope. The subsequent owner instruction on 2026-09-12 permits
three calendar months from the original loan date when maturity is missing:
source tenure zero may map to three only with the explicit owner terms evidence
reference. The wrapper retains raw tenure, selected tenure/maturity and the basis
for that choice. Known positive tenure stays unchanged; the signed review and
export retain the rule without rewriting source facts. This reuses the existing
dated opening contract and introduces no model or native-origination default.

Source evidence retained with the immutable staged document includes the exact
selected loan, all its items, customer, series and licence, their original facts
and row hashes, archive/selection fingerprints and one selected loan ID. It binds
the reviewed source snapshot, not the production database's later state. Missing
original licence numbers, current custody/appraisals, balances and first-month
coverage still require reviewed declarations; extraction does not invent them.

The staged document wraps the exact Loans commit document and source evidence.
`source_sha256` identifies the inner accepted Loans document, matching the existing
result SQL guard. The approval digest additionally covers the whole wrapper and
preview, so source evidence is included in the signed review. PostgreSQL prevents
editing staged documents; corrections require cancellation and restaging.

Preview runs the Loans command under rollback and stores its summary. A Django
timestamped signature binds the operator, Workspace, batch and approval digest for
one hour. Commit requires explicit confirmation, repeats authorization under the
Workspace/batch locks, checks the signature and all digests, then calls the Loans
command. A changed destination summary rolls the financial write back. Completed
replay returns the accepted result after renewed access checks; it does not reset
servicing. Cancellation clears only unfinished staged values. Finished batches,
provenance and source files cannot be erased by cancellation. The existing limit
of 20 unfinished Loans batches applies across both profiles.

The operator command stages only. The owner reviews balances, original dates,
continuation, custody/appraisals, destination licence/series/product and the exact
borrower in the existing Workspace UI, with CSRF protection and no-store responses.
Users do not need to author JSON. The technical operator package is prepared from
source data and recorded decisions; it is not a normal customer upload format.

No real `jcl` loan is activated by delivering this bridge. Missing due terms,
approved balances and destination/cutover decisions remain held. Truthful opening
export is still required before the actual pilot. See the
[operator flow](../flows/legacy-opening-import.md) and
[first-import plan](../plans/first-legacy-import.md).

## Bounded operator staging (2026-09-17)

For the owner-authorized full rehearsal, `stage_many` stages 1–20 reviewed
openings using one newly extracted private archive snapshot. All reviews must
have one source schema/namespace and distinct source loan IDs. Every opening
still passes its own domain preview and the same source-evidence checks as the
single-loan path. Callers cannot supply extracted records or a persistent cache.
Authorization precedes extraction and is repeated under the Workspace lock.
All staged documents are created atomically, subject to the existing combined
20-unfinished-batch limit. Preview signatures, admission and retry remain per loan.
This changes extraction frequency, not financial admission or evidence semantics.
