---
status: accepted
owner: project
updated: 2026-09-30
tags: [portability, guided-import, fw-007]
---

# Guided outstanding-register import over existing opening services

The owner selected an operating Workspace bringing outstanding loans from Excel
as the first guided journey. Other source adapters, manual historical entry,
complete history, archive-only evidence and Workspace restoration retain their
separate documented coverage. This does not make arbitrary vendor data compatible.

Use a plain, values-only XLSX/CSV register, one row per collateral item and stable
loan/borrower/item references. The first bounded batch has at most 20 loans and
200 rows, one destination licence revision/series and one financial handover date.
The existing hardened parser handles files; a small explicit adapter produces the
existing Loans opening contract. No spreadsheet formulas or generic ORM importer.

The supported servicing rule is the existing original-anniversary, first-month-
paid-upfront aggregate rule, unchanged principal, bullet maturity and known unpaid
interest/fees. Original dates/rates/tenure and current vault custody require source
confirmation. Reduced principal, other interest rules, instalments and missing
required facts are held, not converted. Unknown historical appraisals stay unknown.
Servicing dates must be after the handover date. No historic cash payout is created.

A directly Workspace-owned staging envelope retains parsed source rows, file hash,
source-register key, settings, borrower choices and signed preview. Forced RLS,
registry coverage, SQL source/terminal immutability and same-Workspace result
guards apply. Cancellation clears unfinished private source/mapping data while
retaining actor/time metadata. Completed evidence and result links cannot be erased.

The source register key derives a stable Workspace-scoped namespace; filenames
never define identity. Exact re-upload reopens the batch. Other repeated source
loans conflict rather than create duplicate debt. Existing customers are explicitly
selected; new customers use the ordinary Party form/service. Names never silently
merge identities. A changed source borrower mapping cannot replace an accepted one.

Preview composes Party binding and Loans admission inside rolled-back savepoints.
Commit rechecks current authority, locked mappings and all validation, comparing
the displayed result to the signed preview before the outer transaction commits.
New surrogate IDs are not preview commitments; selected existing Party IDs and
their current identity digests are. Changes invalidate approval. All selected
loans commit together; a failure leaves no partial customers, debt or setup.
Double submission returns the immutable batch result after current authorization.

Historical admission remains owner-only (or existing platform override), with
data-import/setup permissions and business-write access. The user reviews the
named servicing rule; a dedicated retired product definition is prepared through
the existing catalog services on commit if needed, never offered for new lending.
Numbering guards preserve original numbers and reject overlaps with future native
numbers. Counter expansion/reservation is a separate reviewed setup action.

UI provides upload/template/help, borrower matching, grouped errors, totals and
explicit final confirmation, persisted results and loan links. It is a limited
supported import journey, not full FW-007 or FW-012 completion. Existing loans,
statutory reviews and production financial data are not test fixtures.
