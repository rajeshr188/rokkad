---
status: implemented
owner: project
updated: 2026-09-30
tags: [portability, fw-007, workspace-guide]
---

# Guided import of outstanding legacy loans

The first customer-facing loan-register adapter is `outstanding-register/1`.
An existing operating Workspace can admit supported old outstanding loans without
simulating a new loan or paying out cash again. The in-app guide is available from
**Workspace settings → Import existing loans → Import guide**. Only the owner or
the existing authorized platform override may approve historical debt.

## Supported first profile

Use a values-only XLSX or UTF-8 CSV with the downloaded template headers. Each row
describes a collateral item; multiple rows share stable loan and borrower references.
Original loan numbers, dates, item quantities, known weights/purity, allocated
principal and rates are retained. One batch covers one licence revision/series,
up to 20 loans and 200 collateral rows (at most 20 items per loan).

The source loans must have unchanged principal, a known whole-month bullet tenure,
first-month interest paid upfront, the existing original-anniversary inclusive
monthly rule, known unpaid interest/fees and collateral currently in the vault.
Monthly charges on original principal are aggregated across items and rounded
once to whole rupees using half-even rounding. Unknown amounts are not zero.
The source rule must be explicitly confirmed; the adapter does not convert another
business's interest convention. Reduced-principal openings, instalments, missing
required facts, other rules and released/repledged collateral require another
reviewed profile. They do not pass this importer.

Choose a completed handover date before today. All source payments through that
date must be reflected in opening balances. Stop transactions in the old register
for those loans; service them in Rokkad from the next day. Other existing Rokkad
loans can continue operating normally.

## Owner journey

1. Download the Excel template and read the column guide. Use date **text** in
   DD/MM/YYYY and numeric values without currency signs or grouping commas.
   A collateral row's principal and weight are totals, not per-piece values.
   Repeat whole-loan unpaid interest/fees on each item row; they count once.
2. Upload under a stable register key such as `old-ledger`. Reuse the key and
   source identifiers for later batches, regardless of filename changes.
3. Choose the original licence revision and destination series. Existing licence
   evidence and numbering guards still apply. An original number that overlaps
   a future number range requires a separate Loan setup correction; importing
   does not reserve, expand or rewind counters.
4. Explicitly match each source borrower to an existing customer using the
   searchable dropdown, or create a new customer from name/optional phone. Names
   are never automatic identity matches. Accepted source bindings remain fixed.
5. Enter the handover, original grace days and a reconciliation reference, then
   preview. Inspect customer matches, totals and each loan's original date,
   maturity, quantities, weights, purity and rates. Errors identify borrower/loan
   references and source rows. Correct choices and preview again; for source-file
   corrections cancel the staged review and upload a corrected file.
6. Confirm the reviewed batch. Approval expires after one hour; changed destination
   facts require a fresh review. All loans commit together. Any failure rolls back
   customers, source bindings, servicing setup and loans from that attempt.
7. Open the saved results and reconcile totals against the original register.
   Results retain the importing actor/time and links to every admitted loan.
   Repeating the same confirmation returns the same result without duplicate debt.

Exact file re-upload under the same key reopens the original review/result.
A changed file containing previously admitted source loans is held, not used to
overwrite accepted debt. Larger files must be split without overlapping loans;
do not split one loan's collateral across batches.

## Coverage and later scenarios

This is an **opening position**, not reconstructed receipt history or statutory
certification. Missing dated valuations stay unverified; this template imports no
media, address records or past receipts. New customers can be completed through
ordinary Party screens. A date-only source is represented at midnight in the
source timezone for the canonical contract; that is a representation of the date,
not evidence of the historical payout time.

| Scenario | Path through the shared architecture |
| --- | --- |
| Start new lending; keep old paper loans outside Rokkad | Normal origination; no import required |
| Add outstanding loans from this Excel/CSV template | This guided adapter → reviewed opening → normal servicing |
| Vendor export or a differently organized sheet | Future field/source adapter → same identity, validation and admission services |
| Manually enter old paper loans | Future manual adapter → same opening services; not ordinary new disbursal |
| Source contains trustworthy complete transactions | Existing strict complete-history admission; wider preparation UX remains future work |
| Closed/incomplete history unsuitable for live debt | Existing separate evidence archive |
| Export an entire Workspace and restore a new one | FW-012 packaging/coverage work; not delivered by this adapter |

Supported external formats and calculation profiles can expand independently.
The common contract still requires explicit identity matching, source provenance,
honest evidence coverage, reconciliation, safe retries and tenant isolation.
FW-007 remains partially delivered; arbitrary spreadsheets, additional rules,
manual admission and richer customer/media mapping remain planned.

## Implementation and verification

See the [decision](../adr/2026-09-30-guided-outstanding-register-import.md).
`opening_register.py` is the explicit adapter; `guided_openings.py` orchestrates
existing Party/catalog/opening commands. `GuidedOpeningBatch` is private staging
and review evidence, not a second loan ledger. Migration 0016 adds forced RLS,
immutable source/finished evidence and same-Workspace result guards.

Preview executes the same domain admission inside rolled-back savepoints.
Confirmation locks the Workspace/batch, rechecks authority and the signed
source/mapping/report, and compares fresh results before committing. New database
sequence IDs are not consent facts; existing selected identities and customer
fingerprints are. A dedicated retired servicing product is prepared on first
successful import and cannot appear in native new-lending product choices.

Tests cover real HTTP upload/review/confirmation and CSRF, XLSX roundtrip and
formula rejection, multi-item totals, bounds/unsupported facts, source/customer
binding, stale approval, exact replay, numbering protection, all-or-nothing
rollback, restricted-role RLS and immutable evidence. Opening regression tests
prove subsequent release and the existing servicing contract.
