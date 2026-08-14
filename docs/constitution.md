---
status: active
owner: project
updated: 2026-06-17
tags: [constitution, architecture, accounting]
related: [AGENT_MEMORY.md, domain/accounting.md, flows/dea-posting-flow.md]
---

# Constitution

These are the non-negotiable principles for Rokkad.

1. Accounting is central.
2. Business events become source documents or explicit domain events.
3. Source documents and domain events become vouchers.
4. Posted vouchers create immutable journal entries.
5. Corrections happen through reversals.
6. Posted journal entries are not edited in place.
7. Every accounting effect must be traceable to its source document or domain event.
8. Inventory, commodity, and accounting effects must remain consistent.
9. Workspace/tenant isolation must be preserved.
10. Architecture decisions that change these principles require an ADR.
