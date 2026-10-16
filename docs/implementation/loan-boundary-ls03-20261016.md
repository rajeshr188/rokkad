---
status: verified-locally
owner: loans
updated: 2026-10-16
tags: [loans, architecture, monitoring, verification]
related: [../adr/2026-10-16-supported-loan-financial-reads.md, ../plans/loan-boundary-simplification-20261016.md]
---

# LS-03: supported shared financial reads

The owner authorized this slice after local LS-01/02 verification. Work is local;
production and all live agreements remain unchanged. The unrelated WhatsApp
sender-setup documentation edit is preserved.

## Implementation

- Add [financial_inputs.py](../../apps/tenant_apps/loans/selectors/financial_inputs.py),
  promoting the existing prepared continuation/balance/obligation read into typed,
  frozen, Workspace-scoped containers. Normalize original-principal basis,
  terminal position, correction-aware opening schedule and agreed grace here.
- Exposure, delinquency, live risk and saved risk use the supported
  `financial_inputs` argument. The saved writer imports no private exposure helper.
  Live risk prepares once and passes the same inputs to its monetary readers.
- Retain a narrower obligation reader for standalone DPD; it neither projects nor
  requires support for unrecognized interest. Full prepared financial inputs can
  be passed to DPD without further source queries, including reviewed openings.
- Preserve original compatibility calculators, canonical correction readers,
  unavailable earlier history, optional book coverage and source/expiry checks.
  Existing commands, documents and exchange readers retain their contracts.
- Minimal verified closed positions return zero obligations without requiring a
  product or invented grace policy. Unknown original principal remains unknown;
  earlier history still fails explicitly.

## Verification

All **305 affected regression cases pass** in **504.810 seconds** against the
isolated local `test_rokkad_ls03_20261016` database. The earlier 28-case development
selection overlaps this run and is not an additional unique count. Coverage includes:

- Direct, paper, imported complete history and reviewed opening admissions, with
  rupee/paise rounding, multiple item rates, advance interest and reduced principal.
  Explicit numerical assertions cover both sides of the anniversary boundary;
  prepared monetary reads issue no further queries and source reads perform no DML.
- Missing/foreign Workspace, wrong prepared loan/date, restricted-role RLS reads,
  unsupported interest projection with usable standalone DPD, closed positions
  without original terms, and explicit refusal before the accepted history date.
- Existing financial/obligation integrity failures, corrected native and opening
  schedule lineage, servicing/settlement and reversal/retry, issued document
  preservation, compatible portable roundtrips and exact recovery.
- Book/valuation independence, live/saved assessment parity, financial query reuse,
  live evidence cutoffs, scheduled expiry, source checks, risk summaries and
  completed-payout review/recovery.

Django system checks and migration detection pass: no model changes. Import
boundaries pass for 1,226 tracked Python files plus the new LS source/verification
files. Local documentation-link and whitespace checks pass. No UI changes require
new screen acceptance. The exact disposable test database is removed after testing
and its absence verified; ordinary development and production data are untouched.

No production source/data access, deployment or production migration is part of
this slice. LS-01/02/03 and the separately committed corrections await a coordinated
release. LS-04 is the next authorized-plan slice, requiring its own implementation.
