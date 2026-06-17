---
status: active
owner: project
updated: 2026-06-17
tags: [implementation, dea, vouchers]
related: [../domain/accounting.md, ../flows/dea-posting-flow.md]
---

# DEA Vouchers

Vouchers are the accounting-layer representation of posted business intent.

## Model Boundary

- Business documents express operational intent.
- `Voucher` records the accounting document.
- `VoucherLine` records debits and credits.
- `JournalEntry` records ledger effects.

## Posting Expectations

- Voucher type must have a registered posting rule.
- Posting must validate account availability and period locks.
- Idempotency must prevent duplicate postings.
- Setup errors should be actionable.

Archived voucher sources are preserved in [archive/dea](../archive/dea/).
