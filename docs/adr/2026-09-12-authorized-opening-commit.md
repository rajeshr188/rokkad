---
status: accepted
owner: project
updated: 2026-09-12
tags: [loans, portability, opening, rls]
---

# Authorized opening commit and shared financial-origin identity

## Decision

Loans now owns `preview_opening_import` and `commit_opening_import` for reconciled
`loan-opening-review/2` documents. They use owner-only historical setup access,
matching Workspace context and active lifecycle. Authorization precedes both
lookups and replay and is repeated under the Workspace lock shared with complete
history import. No public upload, bulk runner or production migration is enabled
by this domain command alone.

The input also supplies reviewed original tenure, original licence number and an
explicit servicing policy. The policy must be simple interest with latest approved
appraisal valuation. Its existing snapshot fields support downstream Loans readers;
the frozen opening review's named original-anniversary rule governs collection.
No policy field creates historical interest, fees or payments. Tenure must match
the reviewed original maturity exactly; missing or zero tenure remains held.
Destination licence validity, matching series, product contract/grace/tenure and
exact Party source identity are rechecked before creation.

One transaction creates the loan, complete item set, migration-labelled appraisal
evidence, policy snapshot, one MIGRATION_OPENING, reviewed remaining obligations,
provenance and audit. Current custody is attested IN_VAULT at cutover through the
opening review; no historical custody movement is invented. Unknown gross weight
is excluded from ordinary model field validation only after v2 review validation.
No approval/disbursal snapshot, old receipt, notification or cash-out event is
created. Original number remains source evidence; the existing deterministic
historical local number does not consume a live numbering counter.

## Identity and retry

Reuse `HistoricalLoanImport` rather than introducing another identity table. Its
immutable document now identifies either a complete graph or `loan-opening-commit/1`.
Both commands use the same Workspace/source namespace/source ID uniqueness rule.
For legacy borrower source systems `legacy:<installation UUID hex>:<schema>`,
normalize the source loan ID to `<schema>:<loan ID>` in the identity table. Raw
source IDs remain unchanged in the original document. Other portable sources keep
their existing identity convention. Separate legacy schemas therefore cannot
collide just because their integer keys match.

An older complete-history binding that used the raw key is also recognized when
its frozen borrower source system and raw loan ID match exactly. It is not renamed
or rewritten. Ambiguous multiple accepted bindings fail closed. This preserves
authorized retries and prevents an opening from bypassing a pre-scoping import.

Both financial-origin writers use that key, so complete history cannot activate
an accepted opening and an opening cannot replace accepted complete history.
An identical authorized retry returns the accepted origin and its original import
summary, even after later servicing. A changed document/setup conflicts. Replay
does not reset the current loan balance or repeat schedule creation.

Preview runs the same writer inside a rolled-back savepoint and returns a SHA-256
of the exact review plus setup and an import summary. It retains no loan/appraisal/
event/schedule/provenance rows and no audit entry. PostgreSQL identity sequences
may advance; official loan-number counters do not. Commit requires explicit
confirmation of that fingerprint. The checksum detects changed input; it is not
authentication of a dump, a signature, or proof of the supplied source claims.

## Remaining boundary

The adapter/approval workflow still needs to bind an approved source snapshot and
selection to reviewed balances, custody/valuation, due terms and destination
mappings. Offline candidate reconciliation continues to report `import_ready=false`.
The owner must not construct JSON manually. The April dump, incomplete review
files and brief proceed instructions do not provide missing financial facts.

Only synthetic test Workspaces have exercised commit. Actual activation still
requires truthful opening export, source-selection/destination/cutover review and
a small reconciled rehearsal. Missing due terms and R07743 remain held. Opening
correction beyond the implemented release reversal and partial repayments remain
unsupported. See the [first-import plan](../plans/first-legacy-import.md).
