---
status: active
owner: project
updated: 2026-06-17
tags: [flows, inventory, sales, purchase]
related: [../domain/inventory.md, ../domain/accounting.md]
---

# Inventory, Sales, Purchase Flow

Inventory flows should keep operational stock movements separate from accounting posting while making their connection explicit.

## Flow

1. Product/catalog data is configured.
2. Purchase, sale, adjustment, transfer, or production operation creates a stock movement.
3. Inventory services validate quantity, ownership, and item identity.
4. Accounting-impacting movements request DEA posting through facade/service boundaries.
5. Reports read from stock movement history and accounting ledgers, depending on purpose.

Archived inventory sources are preserved in [archive/product](../archive/product/).
