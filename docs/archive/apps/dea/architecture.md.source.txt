---
status: active
owner: project
updated: 2026-06-17
tags: [dea, architecture, accounting]
related: [README.md, models.md, workflows.md, refactor-plan.md, ../../domain/accounting.md, ../../implementation/dependency-policy.md]
---

# DEA Architecture

## Responsibility

`apps/tenant_apps/dea` is the tenant accounting engine. Its job is to convert operational intent into auditable accounting effects.

DEA owns:

- Chart of accounts and ledger hierarchy.
- Party subledger accounts.
- Business accounting documents such as payment, expense, sales invoice, purchase invoice, and manual journal vouchers.
- Accounting-layer `Voucher`, `VoucherLine`, and `JournalEntry`.
- Posting rules and the posting engine.
- Accounting periods, opening balances, close/lock workflows, reports, reconciliation, audit, depreciation, and prepaid amortization.

DEA should not be bypassed by operational apps when ledger effects are needed. External apps should use [facade.py](../../../apps/tenant_apps/dea/facade.py) rather than importing DEA internals.

## Main Modules

### Public API

- [facade.py](../../../apps/tenant_apps/dea/facade.py): public API for other apps.
- [facades/accounts.py](../../../apps/tenant_apps/dea/facades/accounts.py): customer/account helper, currently `ensure_customer_account`.
- [facades/payments.py](../../../apps/tenant_apps/dea/facades/payments.py): create/post/reverse payment helpers.
- [facades/journals.py](../../../apps/tenant_apps/dea/facades/journals.py): manual journal and interest accrual posting helpers.
- [facades/reads.py](../../../apps/tenant_apps/dea/facades/reads.py): read-side helpers for journal entries and balances.

### Models

- [models/account.py](../../../apps/tenant_apps/dea/models/account.py): party accounts, account statements, account transactions, account balance view.
- [models/ledger.py](../../../apps/tenant_apps/dea/models/ledger.py): chart of accounts, ledger statements, GL transactions, ledger balance view.
- [models/voucher.py](../../../apps/tenant_apps/dea/models/voucher.py): `VoucherType`, `Voucher`, `VoucherLine`.
- [models/journal.py](../../../apps/tenant_apps/dea/models/journal.py): immutable voucher-backed journal entries.
- [models/doc.py](../../../apps/tenant_apps/dea/models/doc.py): abstract `BusinessDoc` base class.
- [models/payment.py](../../../apps/tenant_apps/dea/models/payment.py): payment-centric cash movement document.
- [models/expense.py](../../../apps/tenant_apps/dea/models/expense.py): expense voucher and line items.
- [models/journal_entry.py](../../../apps/tenant_apps/dea/models/journal_entry.py): manual journal adjustment voucher and line items.
- [models/sales_invoice.py](../../../apps/tenant_apps/dea/models/sales_invoice.py): sales invoice accounting document.
- [models/purchase_invoice.py](../../../apps/tenant_apps/dea/models/purchase_invoice.py): purchase invoice accounting document.
- [models/period.py](../../../apps/tenant_apps/dea/models/period.py): accounting periods and close/lock operations.
- [models/asset.py](../../../apps/tenant_apps/dea/models/asset.py): fixed assets and depreciation schedules.
- [models/prepaid.py](../../../apps/tenant_apps/dea/models/prepaid.py): prepaid expenses and amortization schedules.
- [models/bank.py](../../../apps/tenant_apps/dea/models/bank.py): bank accounts, bank statement lines, reconciliation matches.
- [models/audit.py](../../../apps/tenant_apps/dea/models/audit.py): immutable accounting audit events.

### Posting

- [posting/registry.py](../../../apps/tenant_apps/dea/posting/registry.py): global `PostingRuleRegistry`.
- [posting/types.py](../../../apps/tenant_apps/dea/posting/types.py): posting DTOs such as posting bundles and lines.
- [posting/context.py](../../../apps/tenant_apps/dea/posting/context.py): `PostingContext` and fingerprint calculation.
- [posting/engine.py](../../../apps/tenant_apps/dea/posting/engine.py): period validation, idempotency, rule execution, materialization, reversal, and audit logging.
- [posting/commands.py](../../../apps/tenant_apps/dea/posting/commands.py): command entry point around the engine.
- [posting/resolver.py](../../../apps/tenant_apps/dea/posting/resolver.py): ledger lookup helpers for posting rules.
- [posting/required_rules.py](../../../apps/tenant_apps/dea/posting/required_rules.py): required seeded rule keys.
- [posting/rules/](../../../apps/tenant_apps/dea/posting/rules): concrete posting rules.
- [posting/legacy_direct_write_engine.py](../../../apps/tenant_apps/dea/posting/legacy_direct_write_engine.py): legacy path retained for compatibility; not the target architecture.

Posting rules are imported at app startup in [apps.py](../../../apps/tenant_apps/dea/apps.py), which imports every module in `posting.rules`.

### Services

- [services/post_doc.py](../../../apps/tenant_apps/dea/services/post_doc.py): creates/reuses vouchers for business docs and posts through the engine.
- [services/materialize_journal.py](../../../apps/tenant_apps/dea/services/materialize_journal.py): turns `VoucherLine` rows into `JournalEntry`, `LedgerTransaction`, and `AccountTransaction`.
- [services/voucher_type_seed.py](../../../apps/tenant_apps/dea/services/voucher_type_seed.py): restores known voucher types.
- [services/voucher_numbering.py](../../../apps/tenant_apps/dea/services/voucher_numbering.py): date-based voucher numbering.
- [services/settlement.py](../../../apps/tenant_apps/dea/services/settlement.py): invoice settlement after payment posting.
- [services/pre_close.py](../../../apps/tenant_apps/dea/services/pre_close.py): period close checklist.
- [services/reports.py](../../../apps/tenant_apps/dea/services/reports.py): report data builders.
- [services/reconciliation.py](../../../apps/tenant_apps/dea/services/reconciliation.py): bank reconciliation logic.
- [services/depreciation.py](../../../apps/tenant_apps/dea/services/depreciation.py): fixed asset depreciation posting.
- [services/prepaid.py](../../../apps/tenant_apps/dea/services/prepaid.py): prepaid amortization posting.
- [services/audit.py](../../../apps/tenant_apps/dea/services/audit.py): accounting audit event writer.

### Views, URLs, Forms, Templates

- [urls.py](../../../apps/tenant_apps/dea/urls.py): route table for dashboards, ledgers, accounts, journal entries, vouchers, payments, expenses, periods, reports, opening balances, and reconciliation.
- [views/](../../../apps/tenant_apps/dea/views): web views grouped by area.
- [forms.py](../../../apps/tenant_apps/dea/forms.py): legacy and period/opening balance/account forms.
- [forms_vouchers.py](../../../apps/tenant_apps/dea/forms_vouchers.py): document/voucher line forms and pair-based journal entry formsets.
- [templates/dea/](../../../templates/dea): DEA templates.

### Management Commands

- [management/commands/seed_core_ledgers.py](../../../apps/tenant_apps/dea/management/commands/seed_core_ledgers.py): seeds baseline masters and standard chart of accounts per tenant schema.

There are no active DEA Celery tasks or signal modules. Comments in [apps.py](../../../apps/tenant_apps/dea/apps.py) mention older signal loading, but the current active startup behavior is posting rule import.

## Connection Pattern

```text
URL -> view -> form/formset -> model/service -> posting engine -> voucher lines -> journal entries -> reports/templates
```

For cross-app callers:

```text
External app -> apps.tenant_apps.dea.facade -> internal facade/service -> posting engine
```

## Current Boundary Concerns

- DEA still directly imports Contact model/form internals in [models/account.py](../../../apps/tenant_apps/dea/models/account.py) and [filters.py](../../../apps/tenant_apps/dea/filters.py).
- Product inventory still has direct references to `dea.JournalEntry` outside DEA.
- Some views contain business/posting logic directly, especially [views/voucher.py](../../../apps/tenant_apps/dea/views/voucher.py) and [views/period.py](../../../apps/tenant_apps/dea/views/period.py).
- The template sidebar gates DEA visibility with `dea_entry_view`, but most DEA routes are only login-protected.
