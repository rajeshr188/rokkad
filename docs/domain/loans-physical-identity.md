---
status: active
owner: loans
updated: 2026-08-09
tags: [loans, ticket, collateral, label, qr, signature]
related:
  - ../adr/2026-08-09-loans-collateral-identity-media-and-labels.md
  - ../adr/2026-08-09-loans-pilot-report-and-document-boundary.md
  - ../implementation/loans-girvi-operator-parity-pilot.md
  - ../implementation/loans-configurable-document-operations.md
---

# Loans Physical Identity

## P3 Boundary

Draft capture is pre-contract working data: a mistaken collateral item and its
draft media/label evidence may be deleted only while the PawnLoan remains
`DRAFT`. Approval is the immutability boundary for retained collateral identity
and photographs.

On the saved draft loan, editors can use **Delete photo** beside an image and
confirm its removal. This is a POST action with a draft-state check and audit entry.
The last image may be removed to correct a mistake, but approval requires a new
image. Photographs on approved loans have no delete action. File deletion waits
for commit and preserves files referenced by inherited renewal evidence.

P3 preserves the mature physical identity outcome without copying Girvi's
document internals:

| Outcome | Decision | Loans expression |
| --- | --- | --- |
| Customer and branch retain matching loan-ticket copies | PORT | The fixed fallback and every pilot-assigned layout emit Original and Duplicate from one frozen approval projection and verification identity. |
| Both parties sign the ticket | PORT | Borrower/customer and authorized staff signature areas are required on both copy fronts. |
| Every pledged item can be identified physically | REPLACE | The label uses immutable collateral UUID identity rather than a mutable row or display description. |
| Label carries useful counter information | PORT | Loan number, item identity, description, Party, and net weight are printed. |
| Scanning identifies the correct record | REPLACE | The QR contains the tenant route for the immutable item UUID and redirects to its owning loan and item anchor. |
| Reprints remain explainable | REPLACE | Label preview/print and official configurable-document issue evidence retain actor, time, source identity, and content hash. |

## Software Evidence

- Fixed tickets render two pages labelled Original and Duplicate with the same
  source verification identity and both required signature areas.
- Configurable-document integrity rejects an active pilot ticket that omits
  either copy or does not provide both signature roles on each front.
- Label tests prove the loan number, immutable item code, description, Party,
  net weight, exact tenant scan target, and PDF content hash.
- The scan route resolves the immutable item inside the active tenant and opens
  the owning loan anchored to that collateral.
- The complete 59-test document layout, rendering, persistence, media, label,
  and scan gate passes.

## Manual Evidence Still Required

Software cannot certify a physical printer. The Owner must print intended A4
and A5 paths, confirm margins and both signature boxes are usable, record
simplex/duplex driver behavior, and scan the QR from paper. Printer model,
driver, paper, scaling, operator, and date belong in the physical matrix.

The workspace Owner accepted P3 on 2026-08-09 after the software gate and
physical ticket, label, signature-area, and QR scan checks.
