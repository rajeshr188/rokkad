---
status: accepted
owner: project
updated: 2026-08-08
tags: [loans, license, regulatory, evidence, documents]
related: [2026-07-15-loans-rewrite-domain-and-cutover-architecture.md, ../plans/loan-operational-parity-pilot.md]
---

# ADR: Loans License Regulatory Evidence

## Context

`LoanLicense` is the current setup projection used by numbering and origination.
Editing that row alone cannot preserve legal issue, amendment, renewal, and
document history. A renewed projection must not change which license version an
existing PawnLoan and its documents claim to have used.

## Decision

1. `LoanLicense` remains the current operational projection.
2. Every issue, amendment, and renewal appends an immutable
   `LoanLicenseRevision` snapshot.
3. Supporting PDF, PNG, or JPEG evidence stores its original filename, MIME
   type, size, and SHA-256 hash. New UI-created licenses and renewals require a
   document. Backfilled development records remain visible as missing evidence.
4. PostgreSQL blocks revision update and deletion.
5. A PawnLoan captures the current license revision at draft creation. The link
   may change only while transferring an unavailable draft to replacement
   setup. PostgreSQL freezes it after draft.
6. Loan documents use the captured revision and fall back to the root license
   only for legacy rows without revision evidence.
7. The license dashboard and selector-backed register show active, inactive,
   expired, expiring, and document-missing readiness. The register is available
   as a PDF.
8. External expiry delivery remains part of OP5's Notify v2 audit. License
   models do not duplicate provider or delivery state.

## Consequences

- Renewal cannot rewrite historical loan or document identity.
- Existing loans remain serviceable after license expiry or renewal.
- Operators can inspect and download the complete regulatory evidence chain.
- Missing legacy evidence is explicit rather than fabricated.
- Tenant migrations `loans.0027` through `loans.0029` carry the evidence,
  portable index rename, backfill, and immutable loan-to-revision link.
