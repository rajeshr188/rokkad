---
status: active
owner: project
updated: 2026-06-17
tags: [dea, userflows, ui]
related: [README.md, workflows.md, architecture.md]
---

# DEA Userflows

## Navigation Entry

The workspace sidebar shows Accounting when `dea_entry_view` is available, or the user is Owner/Admin. See [templates/components/navigation/sidebar.html](../../../templates/components/navigation/sidebar.html).

Current sidebar target is `dea_journal_entries_list`, which lands users on journal entries rather than the newer accounting dashboard or voucher hub. A better target would be `dea_dashboard` or `dea_voucher_hub`.

## Main DEA URLs

Defined in [urls.py](../../../apps/tenant_apps/dea/urls.py).

Main pages:

- `/dea/`: legacy/home chart-of-accounts page.
- `/dea/dashboard/`: accounting dashboard.
- `/dea/create/`: voucher creation hub.
- `/dea/transactions/`: transaction list.
- `/dea/reports/`: reports hub.
- `/dea/chart-of-accounts/`: chart of accounts.
- `/dea/vouchers/`: accounting vouchers.
- `/dea/payments/`: payment vouchers.
- `/dea/expenses/`: expense vouchers.
- `/dea/journal-entry-vouchers/`: manual journal entry vouchers.
- `/dea/periods/`: accounting periods.
- `/dea/opening-balance/wizard/`: opening balance wizard.
- `/dea/reconciliation/`: bank reconciliation.

## Voucher Hub Userflow

URL: `/dea/create/`

View: [views/voucher_hub.py](../../../apps/tenant_apps/dea/views/voucher_hub.py)

Template: [templates/dea/voucher_hub.html](../../../templates/dea/voucher_hub.html)

Flow:

1. User opens Create Voucher hub.
2. View checks for an open period.
3. Template groups voucher cards by category.
4. If no open period exists, create actions are visually disabled and user is linked to period creation.
5. User chooses Journal Entry, Payment, Expense, or Sales Invoice.

## Manual Journal Userflow

URLs:

- `/dea/journal-entry-vouchers/`
- `/dea/journal-entry-vouchers/create/`
- `/dea/journal-entry-vouchers/<pk>/`
- `/dea/journal-entry-vouchers/<pk>/update/`

Views: [views/journal_entry_voucher.py](../../../apps/tenant_apps/dea/views/journal_entry_voucher.py)

Template family:

- [templates/dea/journalentryvoucher_list.html](../../../templates/dea/journalentryvoucher_list.html)
- [templates/dea/journalentryvoucher_form.html](../../../templates/dea/journalentryvoucher_form.html)
- [templates/dea/journalentryvoucher_detail.html](../../../templates/dea/journalentryvoucher_detail.html)

User path:

1. Open list.
2. Click create.
3. Enter header and debit/credit posting pairs.
4. Submit form.
5. View saves the document, creates line items, posts via engine, and redirects to list.

## Payment Userflow

URLs:

- `/dea/payments/`
- `/dea/payments/create/`
- `/dea/payments/<pk>/`
- `/dea/payments/<pk>/edit/`

Views: [views/payment.py](../../../apps/tenant_apps/dea/views/payment.py)

Templates:

- [templates/dea/paymentvoucher_list.html](../../../templates/dea/paymentvoucher_list.html)
- [templates/dea/paymentvoucher_form.html](../../../templates/dea/paymentvoucher_form.html)
- [templates/dea/paymentvoucher_detail.html](../../../templates/dea/paymentvoucher_detail.html)

User path:

1. Open payment list.
2. Filter by direction, method, loan/source id, date range.
3. Create payment manually or arrive with `source_model` and `source_id` query parameters.
4. Submit payment form.
5. Payment is saved and posted.
6. Detail page shows source document and related journal entries if posted.

## Period Userflow

URLs:

- `/dea/periods/`
- `/dea/period/create/`
- `/dea/period/<pk>/`
- `/dea/period/<pk>/adjustments/`
- `/dea/period/<pk>/close/`
- `/dea/period/<pk>/lock/`
- `/dea/period/<pk>/unlock/`

Views: [views/period.py](../../../apps/tenant_apps/dea/views/period.py)

Templates:

- [templates/dea/period_list.html](../../../templates/dea/period_list.html)
- [templates/dea/period_detail.html](../../../templates/dea/period_detail.html)
- [templates/dea/period_form.html](../../../templates/dea/period_form.html)
- [templates/dea/period_adjustments.html](../../../templates/dea/period_adjustments.html)
- [templates/dea/period_close_confirm.html](../../../templates/dea/period_close_confirm.html)

User path:

1. Create or open period.
2. Review period detail and transaction counts.
3. Use adjustments page to post accrual/prepaid/depreciation/custom entries.
4. Open close confirmation page.
5. Review checklist and warnings.
6. Close period.
7. Lock period after review if permitted.

## Opening Balance Userflow

URL: `/dea/opening-balance/wizard/`

View: [views/opening_balance.py](../../../apps/tenant_apps/dea/views/opening_balance.py)

Templates:

- [templates/dea/opening_balance/step1_period.html](../../../templates/dea/opening_balance/step1_period.html)
- [templates/dea/opening_balance/step2_entry.html](../../../templates/dea/opening_balance/step2_entry.html)
- [templates/dea/opening_balance/step3_review.html](../../../templates/dea/opening_balance/step3_review.html)

User path:

1. Select period.
2. Enter ledger and account opening balances.
3. Review debit/credit balance.
4. Confirm to create/update opening statements.

## HTMX And Partials

HTMX support appears through:

- `for_htmx(use_block="content")` decorators in period and voucher/report views.
- `voucher_check_balance` and `voucher_status_badge` in [views/voucher.py](../../../apps/tenant_apps/dea/views/voucher.py).
- Partials under [templates/dea/partials](../../../templates/dea/partials).

## Permission Userflow Gap

The UI hides Accounting behind `dea_entry_view`, but many DEA views only require login. Direct URL access is therefore broader than sidebar access. Permission behavior should be standardized in a DEA permission mixin/decorator.
