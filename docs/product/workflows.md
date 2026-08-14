---
status: active
owner: project
updated: 2026-06-18
tags: [product, workflows, accounting, operations]
related: [userflows.md, page_hierarchy.md, ../flows/dea-posting-flow.md, ../flows/girvi-loan-lifecycle.md]
---

# Workflows

This document separates business workflow, screen workflow, accounting workflow, approval/status workflow, and error handling workflow.

## Core Operating Model

EXISTING principle:

Business Event -> Source Document -> Posting Engine -> Voucher -> Journal Entry -> Ledgers -> Reports.

REFACTOR target:

Every operational document should expose the same workflow shape:

1. Draft.
2. Validate.
3. Approve when required.
4. Post.
5. Show accounting/inventory/commodity impact.
6. Reverse/correct instead of mutating posted effects.
7. Preserve timeline/audit.

## Business Workflow

### Sale

- EXISTING: Sales invoice and receipt flows exist.
- REFACTOR: Sale should be a source document with role-aware Party customer, item lines, payment allocations, inventory impact, and accounting impact.
- PROPOSED: Sale should support Draft, Approved, Posted, Partially Paid, Paid, Reversed/Cancelled.

### Purchase

- EXISTING: Purchase and supplier payment flows exist.
- REFACTOR: Purchase should mirror Sale page pattern.
- PROPOSED: Purchase should support Draft, Approved, Posted, Stock Received, Partially Paid, Paid, Reversed/Cancelled.

### Loan

- EXISTING: Girvi GivenLoan/TakenLoan exist with lifecycle transition commands and payment/release flows.
- REFACTOR: Pick one lifecycle language and show it consistently in UI.
- PROPOSED: Separate loan aggregate lifecycle from accounting events.

### Inventory

- EXISTING: Inventory movement service and stock pages exist.
- REFACTOR: Inventory movements should be visible on source documents, not only stock pages.
- PROPOSED: Manual adjustment should be a formal source document with reason, approval, and optional accounting effect.

### Accounting

- EXISTING: DEA voucher/journal/ledger/period pages exist.
- REFACTOR: Accounting screens should be traceable from source document and back.
- PROPOSED: Accounting dashboard should prioritize exceptions: unposted vouchers, failed postings, period close blockers, imbalance checks.

## Screen Workflow

### Document List

REFACTOR standard list pattern:

- Filters at top.
- Main table using `django-tables2`.
- Saved views where useful.
- Create button as primary action.
- Bulk actions in a menu, not scattered buttons.
- Empty state with one recommended action.
- HTMX table refresh for filters/pagination.

### Document Create/Edit

REFACTOR standard form pattern:

- Header with document type and status.
- Left/main column for required document fields.
- Right setup panel for rates, party account, period status, validation summary.
- Line-item editor in the same screen.
- Save Draft and Preview/Post actions separated.

### Document Detail

REFACTOR standard tabs:

- Overview.
- Lines/items/collateral.
- Payments/settlements.
- Inventory/commodity impact.
- Accounting impact.
- Attachments/documents.
- Timeline/audit.

### Action Flow

PROPOSED:

- Use action buttons for state transitions.
- Use modals/drawers for short forms such as repayment, release, allocation, confirmation.
- Use full pages for high-risk operations such as posting, period close, reversal, bulk release, merge.

## Accounting Workflow

### Posting

EXISTING:

- DEA posting rules and voucher posting exist.
- Period locking exists.

REFACTOR:

- Posting should always go through DEA facade/services.
- Period-lock validation should be inside posting engine paths.
- Missing Party account/subledger should produce a setup action.

Workflow:

1. Source document requests posting.
2. DEA resolves voucher type and posting rule.
3. DEA resolves control ledgers and subledger account mappings.
4. DEA validates period and balance.
5. DEA creates/posts Voucher and VoucherLine.
6. DEA materializes immutable JournalEntry.
7. Source document stores or resolves posted accounting impact.

### Correction

PROPOSED:

1. User clicks Correct or Reverse.
2. System explains that posted entries are immutable.
3. User chooses correction reason.
4. DEA creates reversal voucher/journal entry.
5. Optional corrected source document is created.
6. Timeline links original, reversal, and correction.

## Approval And Status Workflow

### Owner/Admin/Member/Viewer

EXISTING:

- Orgs permission system maps Owner/Admin/Member/Viewer to codenames.

REFACTOR:

- Status transitions should check permissions through services, not only templates.
- UI should hide disallowed actions and backend should enforce them.

### Suggested Status Vocabulary

PROPOSED shared document vocabulary:

- Draft.
- Pending Approval.
- Approved.
- Posted.
- Partially Settled.
- Settled.
- Reversed.
- Cancelled.

REFACTOR Girvi:

- Girvi currently has legacy statuses and next-gen lifecycle states. UI should expose one canonical state set and map legacy values behind selectors/services.

## Error And Edge-Case Workflow

### Setup Blocker

Examples:

- Missing rate source.
- Missing current metal rate.
- Missing DEA voucher type.
- Missing party account mapping.
- Missing loan license/series.

Pattern:

1. Show blocker inline near the action.
2. Explain why the workflow cannot continue.
3. Provide direct setup link.
4. After setup, return to original document/action.

### Validation Error

Pattern:

- Field-level validation for form issues.
- Line-level validation for item/stock/collateral issues.
- Page-level validation summary for cross-document issues.

### Posting Error

Pattern:

- Show source document unchanged.
- Show failed posting reason.
- Log failure with context.
- Provide Retry after setup.

### Permission Error

Pattern:

- Do not expose action if user lacks permission.
- Backend returns 403 with explanation.
- For team/role flows, state which owner/admin action is required.

### Concurrency

PROPOSED:

- Use optimistic version/timestamps for high-risk documents.
- Use idempotency fingerprints for posting.
- Use database constraints for default flags, unique codes, and active role uniqueness.
