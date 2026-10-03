---
status: active
owner: loans
updated: 2026-10-01
tags: [khata, integration, documents, verification]
related: [../adr/2026-10-01-khata-summaries-and-documents.md, ../flows/khata-balances-and-documents.md, khata-corrections.md]
---

# Khata borrower/dashboard, summary and document integration

Implemented locally following the owner's instruction. No development or
production database was migrated and no real workspace was enabled.

## Delivered

- Batched canonical khata summaries compose with ordinary loans in Party history,
  including existing date sorting and independent page controls. Totals include
  every eligible account before pagination. Typed detail URLs prevent PK collisions.
- The new-loan borrower card includes actual khata principal and accrued unpaid
  interest while separately labelling ordinary-loan recorded interest. Neither
  sanctioned limits nor unused entitlement enters outstanding.
- Dashboard counts deduplicate mixed borrowers, combine actual principal, and
  show a compact khata card with accrued/due/overdue interest, limit/entitlement
  and pending-return links. Ordinary activity, health and reports retain their
  original scope. Aggregate reads retain only a batch of account graphs.
- A paginated khata register filters number/borrower, state, due/overdue interest,
  pending returns, series and licence association, including no-licence accounts.
  Detail shows balances, interest schedule, current cover/policies, custody and
  immutable source/correction links. Missing prices leave known balances intact.
- Verified borrower portal loan/statement summaries and payment history include
  khatas. Net source receipts exclude corrected interest payments; repayments
  already reflected in outstanding are not deducted again in the statement.
- Approved opening/amendment, withdrawal, interest receipt, exchange, reduction,
  actual handover, settlement, correction and dated statement PDFs preserve their
  source references and original evidence. Later collateral receipt/return
  vouchers require preceding approved lender evidence. Drafts can issue clearly
  labelled dated statements; early deposit sources do not invent original terms.
- Today's statement may freeze current same-day collateral cover and rate
  references separately from debt. Financial settlement and actual handover
  remain separate on the screen and in printed evidence.

## Persistence and access

Migration `0039_khata_documents` adds `KhataDocumentIssue` with forced RLS,
direct non-null Workspace ownership, source/account/identity/position/agreement/
licence guards and update/delete refusal. The RLS registry now covers 140 models;
private-file inventory covers 16 file fields. Model cleanup ignores issued evidence.
The artifact path contains workspace, account and issuance UUID.

Issuance locks the company/account in the existing order and requires edit/export
plus current write access. A retry with identical UUID/instructions returns the
same issue; conflicting reuse fails. Save/render/database failure removes only
the newly uncommitted artifact. Downloads require export authority, retain no-store
headers, and verify hashes/size. Missing or changed bytes produce an integrity
failure; reprints never use current borrower addresses or regenerated output.

`khata-document/1` and `khata-a4-v1` are frozen payload/renderer identities.
Source vouchers use their operation prefix; their borrower contact identity is
explicitly recorded at issuance. Statements support today only. Unicode text
flows across complete A4 pages, with a 100-page hard failure rather than truncation.

## Verification

Focused tests cover mixed-kind borrower/portfolio parity, pagination, draft limits,
annual/monthly accrual and dues, receipt compensation, pending outgoing cover,
settled custody, both association modes, private issuance/downloads, retries,
delayed vouchers, preserved original bytes, renderer/integrity failure, long
addresses/items and adversarial restricted-role DML. The existing calculator,
servicing/concurrency, ordinary product, Party UI/portal, dashboard, ticket/layout,
RLS registry and storage inventory suites are also checked. Final counts and
verification results are recorded in [Status](../STATUS.md).

A fictional A4 sample is rendered to page images and inspected for complete
addresses, multilingual identity, all collateral descriptions, pagination and
footer separation. No production borrower data is used for visual review.

## Remaining release boundary

Read-only account screens and document issuance are delivered here. The subsequent
[operator/recovery checkpoint](khata-operator-and-recovery.md) delivers supported
opening/approval/money/custody/correction forms, private photos and exact-identity
native recovery. Item labels, statutory/default boundaries, unsupported correction
coverage and reviewed pilot activation remain release gates. Ordinary pawn
products/calculations and original print paths remain unchanged.
