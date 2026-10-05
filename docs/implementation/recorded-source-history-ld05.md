---
status: complete-local
owner: project
updated: 2026-10-05
tags: [implementation, loans, source-history, ld05]
related: [../adr/2026-10-05-recorded-source-history-v4.md, ../plans/unified-loan-domain-correction.md]
---

# LD-05 supported recorded source history

`history_contract` adds a sealed v4 source agreement alongside unchanged native
v1/v2/v3 schemas. `recorded_history_portability` adapts exact Party/source/setup
mapping into the existing recorded history writer, compares immutable receipt and
closing lines with supplied source allocations, checks eligible cutover debt and
retains immutable source claims. The recorded writer gets a private reviewed
historical setup parameter; ordinary direct/paper entry remains unchanged. No past
Rokkad approval, quote, appraisal, extra cash origin or separate servicing entity
is added.

The new setup path allows ACTIVE/RETIRED compatible product versions independent
of original local catalog availability. Licence validity or explicitly unknown
legacy references, original tenor/grace/calculation identity and native issuance
checks remain enforced. An inactive legacy payout uses the already existing
0058 recorded-origin guard and matching snapshot requirement.

Namespace/scoped source ID continues to be the shared identity across opening and
history admission. Duplicate original numbers across genuine books are aliases
in `HistoricalLoanImport.document`; H/... local numbers remain unique. Same
book/licence/borrower scope and number with a new ID is blocked. Unbound ordinary
paper source references are also checked to prevent duplicate admissions. No alias
table, registry entry or new tenant-owned table is required. Loan-list search and
recorded loan detail expose original number/book/reference without rewriting local
numbers, counters or issued documents.

V4 export handles supported shared recorded origins, original and later receipts,
and paper or current full closure. Source event claims and known original handover
time remain in accepted source JSON; the destination uses completed day-level
recording. Export verifies frozen origination, item/financial conservation, derived
recognition, state/custody and transaction review coverage. Standalone recognition,
compensated history, linked renewal/auction and connected custody/funding/storage
are blocked explicitly. Existing source-evidence archive and opening workflows
remain distinct. Exact recovery still preserves the original local identities.

Portability staging/listing/schema/review/export is wired for v4. Migration 0019
extends the existing batch profile choices and immutable SQL guard; downgrade is
refused while v4 batches exist. It introduces no tables. Only the disposable QA
test database is migrated in this delivery.

The affected regression passes 450 tests in 267.804s. Final conservation and
normalized-alias hardening plus ordinary paper entry/receipt compatibility passes
100 tests in 69.320s, including all 22 new LD-05 tests. System checks, migration
consistency/drift against the dedicated test DB, 672-file Python parsing and scoped
whitespace checks pass. The affected list retains the previously proven baseline
pilot renewal-link assertion exclusion; the full repository is not claimed green.
No production/candidate application migration, live-data conversion or deployment
is performed. Source preparation/staff acceptance and wider operation/coverage/risk
parity remain LD-06–08 work.
