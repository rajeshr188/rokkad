---
status: active
owner: project
updated: 2026-06-17
tags: [domain, inventory, sales, purchase]
related: [../flows/inventory-sales-purchase-flow.md, ../domain/accounting.md]
---

# Inventory, Sales, Purchase

The inventory/product domain manages catalog records, item attributes, stock movements, purchases, sales, and future accounting integration.

## Direction

- Stock movement recording should use explicit service-layer operations.
- Sales and purchase flows should create business documents first, then request DEA posting through accounting boundaries.
- Product/catalog attributes should be normalized when variant workflows require predictable querying and validation.

Archived product and inventory sources are preserved in [archive/product](../archive/product/).
