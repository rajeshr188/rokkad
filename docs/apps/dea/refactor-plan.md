---
status: active
owner: project
updated: 2026-06-17
tags: [dea, refactor, plan]
related: [README.md, architecture.md, models.md, workflows.md, userflows.md, ../../plans/backlog.md]
---

# DEA Refactor Plan

## Target Architecture

DEA should have one clear internal shape:

```text
models/
  persistence and invariants only

forms/
  input validation and UI shape only

views/
  authentication, permission, request parsing, response rendering

services/
  use cases and commands

selectors/
  query/read models for dashboards and reports

posting/
  posting rules, registry, engine, context, DTOs

facades/
  stable public API for other apps
```

## What Should Stay Where

### Models

Keep:

- Field definitions.
- Database constraints.
- Lightweight invariants.
- Status helpers.
- Identity methods.

Move out:

- Posting orchestration.
- Complex reporting queries.
- Debug prints.
- Large workflow logic.

### Views

Keep:

- URL/request handling.
- Permission checks.
- Form binding.
- Template rendering.
- Redirects/messages.

Move out:

- Posting logic.
- Period close calculations.
- Dashboard metrics.
- Report aggregation.
- Voucher reversal logic.

### Forms

Keep:

- UI-level validation.
- Formset validation.
- Widget/helper configuration.

Move out:

- Posting side effects.
- Cross-app lookup logic.

### Services

Own:

- Create/post payment.
- Manual journal posting.
- Expense posting.
- Period close.
- Opening balance application.
- Depreciation/prepaid posting.
- Reconciliation actions.
- Settlement.

### Selectors

Add selectors for:

- Dashboard metrics.
- Voucher list summary counts.
- Period detail summaries.
- Reports.
- Top debtors/creditors.
- Alerts.

## Priority Plan

### P0: Remove Parallel Posting Paths

Problem:

- [views/voucher.py](../../../apps/tenant_apps/dea/views/voucher.py) has legacy `post_voucher()` / `reverse_voucher()` helpers.
- `_calculate_totals()` is placeholder logic.
- `_create_journal_entry()` is placeholder logic.
- Reversal logic references fields that do not match `AccountTransaction`.

Plan:

1. Create `services/voucher_actions.py`.
2. Move post/reverse use cases there.
3. Make both use `DjangoPostingEngine`.
4. Update views to call service only.
5. Add tests that URL posting uses engine and materializes `VoucherLine` correctly.

### P0: Permission Policy

Problem:

- Sidebar checks `dea_entry_view`, but most routes are only `login_required`.

Plan:

1. Define DEA permission codenames for view/create/post/reverse/period/report/admin actions.
2. Add `DeaPermissionRequiredMixin` and function decorator.
3. Apply to class-based and function views.
4. Add route permission tests.

### P1: Make BusinessDoc Posting Explicit

Problem:

- [models/doc.py](../../../apps/tenant_apps/dea/models/doc.py) can auto-post after save and swallow posting errors.

Plan:

1. Default all interactive document flows to explicit posting services.
2. Deprecate `auto_post_to_accounting`.
3. If retained, make failures visible and test-covered.
4. Remove silent failure behavior.

### P1: Extract Dashboard And Reports Selectors

Problem:

- [views/dashboard.py](../../../apps/tenant_apps/dea/views/dashboard.py) does heavy metric calculation.
- Some calculations swallow exceptions and continue silently.

Plan:

1. Add `selectors/dashboard.py`.
2. Add `selectors/accounts.py`.
3. Add `selectors/reports.py`.
4. Keep views thin.
5. Add selector tests independent of templates.

### P1: Normalize Constraints

Problem:

- Several models still use `unique_together`.

Plan:

1. Convert to named `UniqueConstraint`.
2. Use `migrate_schemas` for tenant app migrations.
3. Add migration tests where needed.

### P1: Remove Debug Prints

Problem:

- [models/account.py](../../../apps/tenant_apps/dea/models/account.py) prints active currencies and balance details.

Plan:

1. Replace with `logger.debug`.
2. Add no behavior changes.

### P2: Contact Boundary

Problem:

- DEA directly imports `Customer` and Contact widgets.

Plan:

1. Keep the `Account.contact` relation for now because it is a core domain relationship.
2. Move Contact widget/query use in filters behind Contact facade/selectors.
3. Document `Contact -> DEA Account` as an accepted dependency or create ADR if changing it.

### P2: Inventory Boundary

Problem:

- Product stock models and views reference `dea.JournalEntry` directly.

Plan:

1. Define stock posting facade/service in DEA or product.
2. Link stock movements to source voucher or posted journal through a stable facade result.
3. Add architecture import tests for product -> DEA internals.

### P2: Period Close Service Extraction

Problem:

- [views/period.py](../../../apps/tenant_apps/dea/views/period.py) contains adjustment and close orchestration.

Plan:

1. Move adjustment creation to `services/period_adjustments.py`.
2. Move close orchestration to `services/period_close.py`.
3. Keep `AccountingPeriod.close_period()` as final invariant operation or move all close behavior into a service with model guardrails.

### P3: UI Cleanup

Plan:

1. Change sidebar Accounting target to `dea_dashboard` or `dea_voucher_hub`.
2. Make document detail pages consistently show:
   - source document
   - voucher
   - voucher lines
   - journal entries
   - reversal/correction history
   - audit events
3. Hide edit/delete for posted documents and expose reverse/correct actions.

## Suggested New Structure

```text
apps/tenant_apps/dea/
  facades/
    accounts.py
    journals.py
    payments.py
    reads.py
    inventory.py
  selectors/
    dashboard.py
    reports.py
    accounts.py
    periods.py
    vouchers.py
  services/
    posting_documents.py
    voucher_actions.py
    period_close.py
    period_adjustments.py
    opening_balances.py
    settlement.py
    reconciliation.py
    depreciation.py
    prepaid.py
  posting/
    engine.py
    registry.py
    rules/
  views/
    thin request/response modules
```

## Test Plan

Add or expand tests for:

- Every voucher URL posting path uses engine.
- Posted vouchers cannot be edited/deleted through views.
- Reversal creates reversing journal entries and marks voucher state correctly.
- Permission policy blocks direct URL access.
- Dashboard selectors produce expected metrics.
- Period close services block draft vouchers and locked periods.
- Contact/account creation via facade remains stable.
- Product/inventory never imports DEA posting internals directly.
