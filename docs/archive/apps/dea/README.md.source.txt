---
status: active
owner: project
updated: 2026-06-17
tags: [dea, accounting, app-docs]
related: [architecture.md, models.md, workflows.md, userflows.md, refactor-plan.md, ../../domain/accounting.md, ../../flows/dea-posting-flow.md, ../../implementation/dea-vouchers.md]
---

# DEA App Documentation

This folder documents the current `apps/tenant_apps/dea` Django app.

DEA is the accounting core of Rokkad. It owns the chart of accounts, subledger accounts, business accounting documents, vouchers, voucher lines, journal entries, posting rules, opening balances, accounting periods, reports, settlement, reconciliation, depreciation, prepaid schedules, and accounting audit events.

## Reading Map

- [Architecture](architecture.md): module map, dependencies, boundaries, and current problems.
- [Models](models.md): important models and relationships.
- [Workflows](workflows.md): backend/business flows and data changes.
- [Userflows](userflows.md): UI navigation, URLs, forms, templates, HTMX paths.
- [Refactor Plan](refactor-plan.md): cleaned-up target architecture and priority plan.

## Canonical Project Context

- [Accounting domain](../../domain/accounting.md)
- [DEA posting flow](../../flows/dea-posting-flow.md)
- [DEA voucher implementation notes](../../implementation/dea-vouchers.md)
- [Project constitution](../../constitution.md)

## Important Archived Sources

The current code has evolved beyond parts of the archive, but these documents explain why the app is shaped this way:

- [DEA architecture analysis](../../archive/dea/dea__architecture__DEA_ARCHITECTURE_ANALYSIS.md)
- [Voucher architecture](../../archive/dea/voucher__VOUCHER_ARCHITECTURE.md)
- [Payment voucher design](../../archive/dea/voucher__payment__PAYMENT_VOUCHER_DESIGN.md)
- [Pre-close checklist workflow](../../archive/dea/period__PRE_CLOSE_CHECKLIST_AND_ADJUSTMENTS_WORKFLOW.md)

## Current Mental Model

```text
Business document or event
-> DEA facade / command service
-> Voucher
-> VoucherLine
-> Posting engine
-> JournalEntry
-> LedgerTransaction / AccountTransaction
-> Reports, balances, audit
```

The newer engine path is the preferred architecture. Some older direct-write and view-level paths still exist and are called out in [Refactor Plan](refactor-plan.md).
