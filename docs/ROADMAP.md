---
status: active
owner: project
updated: 2026-06-17
tags: [roadmap, planning]
related: [STATUS.md, plans/active.md, plans/backlog.md, plans/completed.md]
---

# Roadmap

## Priority 1

- Finish Girvi event-driven DEA posting design and implementation.
- Standardize Girvi lifecycle language and remove legacy status ambiguity from UI/tests.
- Continue moving cross-app reads behind facades/selectors.
- Keep accounting effects in DEA posting services and Girvi command/use-case classes.

## Priority 2

- Harden DEA posting rules with registration tests for every seeded voucher type.
- Expand period-lock validation coverage inside posting engine paths.
- Improve tenant setup so required master data, rates, voucher types, and account mappings are visible and recoverable.
- Consolidate UI patterns using the canonical UI principles.

## Priority 3

- Revisit inventory/sales/purchase posting boundaries.
- Normalize product/catalog attributes where the current model makes workflows difficult.
- Continue notification batching and workflow hardening.
- Review archived implementation plans before reviving any old proposal.

See [active](plans/active.md), [backlog](plans/backlog.md), and [completed](plans/completed.md).
