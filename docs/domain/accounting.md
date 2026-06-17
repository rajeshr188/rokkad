---
status: active
owner: project
updated: 2026-06-17
tags: [domain, accounting, dea]
related: [../flows/dea-posting-flow.md, ../implementation/dea-vouchers.md, ../implementation/dependency-policy.md]
---

# Accounting / DEA

DEA is the accounting core. It owns charts/accounts, accounting documents, vouchers, voucher lines, journal entries, posting rules, opening balances, and period controls.

## Boundary

- Operational apps create business documents and request accounting effects through the DEA facade.
- DEA converts business intent into vouchers and journal entries.
- Period-lock validation belongs in posting engine paths, not scattered view-only checks.
- Posting rules should be registered and test-covered for every seeded `VoucherType`.

## Document Layers

- Business documents: `PaymentVoucher`, `JournalEntryVoucher`, `ExpenseVoucher`, loan events, sale/purchase documents.
- Accounting layer: `Voucher`, `VoucherLine`, `JournalEntry`.

## Current Concerns

- Ensure every external caller uses the facade instead of models/posting internals.
- Revisit voucher uniqueness constraints if event-driven Girvi needs multiple vouchers against one loan/document.
- Keep fingerprint behavior consistent: nullable until posting or assigned when drafts are created.

Archived DEA sources are preserved in [archive/dea](../archive/dea/).
