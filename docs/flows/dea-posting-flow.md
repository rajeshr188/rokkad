---
status: active
owner: project
updated: 2026-06-17
tags: [flows, dea, posting]
related: [../domain/accounting.md, ../implementation/dea-vouchers.md, ../plans/active.md]
---

# DEA Posting Flow

DEA posting converts business documents or business events into accounting effects.

## Flow

1. Caller uses DEA facade or approved command service.
2. DEA resolves the business document/event and voucher type.
3. Posting engine validates period lock, accounts, rule registration, idempotency, and document state.
4. Voucher and voucher lines are created or reused.
5. Journal entries are written atomically.
6. Posting result is returned to the caller.

## Rules

- Views should not contain posting logic.
- Domain models should not directly create journal entries.
- Posting errors should be explicit and recoverable where setup is missing.

Archived DEA posting sources are preserved in [archive/dea](../archive/dea/) and [archive/girvi/GIRVI_EVENT_DRIVEN_DEA_POSTING_SPEC](../archive/girvi/GIRVI_EVENT_DRIVEN_DEA_POSTING_SPEC.md).
