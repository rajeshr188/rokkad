---
status: active
owner: project
updated: 2026-10-14
tags: [loans, portability, contract, customer]
related: [../adr/2026-10-14-origination-consolidation.md, ../implementation/loan-origination-consolidation-20261014.md]
---

# Loan servicing bundle version 5

`loan-servicing-bundle/5` retains the ZIP limits, files, documents and source-local
financial/custody graph of one published financial profile (1–4). It adds exactly
two manifest fields, covered by the existing canonical manifest checksum:

- `financial_profile`: one of `loan-servicing-bundle/1` through `/4`. That version
  chooses the existing table inventory, coverage exclusions, storage and funding
  fields and validation. Existing row schemas remain unchanged.
- `agreement_parties`: object keyed by each source PawnLoan ID, each value an
  object keyed by canonical positive source Party row ID. Each identity is exactly
  `{source_system, id}`, referencing the source Party export identity.

Only v5 expands the LoanChangeLog event_kind vocabulary with BORROWER_CORRECTED.
Its borrower_correction metadata retains the immutable version-1 correction schema:
before/after Party snapshots, reason/reference, actor, request key/hash and source
fingerprint. Every correction event must have that metadata and other events cannot
hide it. Ordered endpoint chains must agree, finish at the current borrower, and
exactly match the Party inventory. The current reference matches setup.borrower.

Destination resolution uses exact accepted Party SourceIdentity records under the
destination Workspace. Distinct customers cannot collapse into one Party. Missing
identities hold preview and commit. User mappings continue selecting current
borrower, licence revision, series and product; former Party resolution is automatic
from accepted source identities, not a new manual mapping option.

Restore maps named original borrower IDs independently of current borrower IDs.
Correction endpoint IDs and request digests use their corresponding destination
identities, while portable_source retains the immediate source Workspace, old IDs
and original request digest. The entire unchanged source manifest, ancestry and
issued documents remain retained. Existing source checks and destination financial
reconciliation apply. Transfer does not inherit completeness, consent, authority or
an original digital approval for paper records.

Uncorrected exports continue selecting versions 1–4. Versions 1–4 and loan-history
contracts reject correction evidence. Format 5 remains bounded by the underlying
supported financial graph; it does not authorize unsupported connected corrections.
