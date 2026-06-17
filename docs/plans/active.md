---
status: active
owner: project
updated: 2026-06-17
tags: [plans, active, girvi, dea]
related: [../domain/girvi.md, ../domain/accounting.md, ../flows/dea-posting-flow.md, ../archive/girvi/GIRVI_EVENT_DRIVEN_DEA_POSTING_SPEC.md]
---

# Active Plan

## Girvi Event-Driven DEA Posting

The current active architecture track is to make Girvi lifecycle accounting effects explicit, reliable, and idempotent.

Source spec:

- [Archived full spec](../archive/girvi/GIRVI_EVENT_DRIVEN_DEA_POSTING_SPEC.md)

Current direction:

- Girvi emits explicit business events for disbursal, repayment, release, renewal, auction, sale, undo, and adjustments.
- DEA owns posting rules, period-lock validation, voucher creation, voucher line creation, and journal entry creation.
- Each event/posting path needs an idempotency marker so retries do not double-post.
- Existing command/use-case services should remain the primary place for Girvi lifecycle behavior.
- Views should orchestrate requests and responses, not accounting effects.

Implementation guardrails:

- Use [DEA posting flow](../flows/dea-posting-flow.md) for ledger behavior.
- Use [Girvi loan lifecycle](../flows/girvi-loan-lifecycle.md) for domain state behavior.
- Respect [dependency policy](../implementation/dependency-policy.md).
