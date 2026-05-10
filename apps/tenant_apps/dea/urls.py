from django.urls import path


from . import views
from .views import reports as reports_views
from .views import dashboard_enhanced

urlpatterns = [
    # for common views
    path("tally/", views.FileUploadView.as_view(), name="tally_upload"),
    path("", views.home, name="dea_home"),
    path("dea/gl/", views.generalledger, name="dea_general_ledger"),
    path("daybook/", views.daybook, name="dea_daybook"),
]

# Phase 2: Navigator + Hub URLs
urlpatterns += [
    path("chart-of-accounts/", views.chart_of_accounts, name="dea_chart_of_accounts"),
    path("create/", views.voucher_hub, name="dea_voucher_hub"),
    path("transactions/", views.transaction_list, name="dea_transaction_list"),
    path("reports/", views.reports_hub, name="dea_reports_hub"),
]

# Dashboard and Analytics URLs
urlpatterns += [
    path("dashboard/", views.dashboard, name="dea_dashboard"),
    path("dashboard/legacy/", views.dashboard, name="dea_dashboard_legacy"),
    path("dashboard/enhanced/", dashboard_enhanced.dashboard_enhanced, name="dea_dashboard_enhanced"),
    path(
        "dashboard/metrics/ajax/",
        views.dashboard_metrics_ajax,
        name="dashboard_metrics_ajax",
    ),
    # Aging reports
    path("reports/receivables/aging/", views.receivables_aging, name="ar_aging"),
    path("reports/payables/aging/", views.payables_aging, name="ap_aging"),
    # Financial ratios
    path("reports/ratios/", views.financial_ratios, name="financial_ratios"),
    # Phase 2.5 report views (period-aware)
    path(
        "reports/period/<int:period_id>/trial-balance/",
        reports_views.TrialBalanceView.as_view(),
        name="trial_balance_period",
    ),
    path(
        "reports/period/<int:period_id>/income-statement/",
        reports_views.IncomeStatementView.as_view(),
        name="income_statement_period",
    ),
    path(
        "reports/period/<int:period_id>/balance-sheet/",
        reports_views.BalanceSheetView.as_view(),
        name="balance_sheet_period",
    ),
    path(
        "reports/period/<int:period_id>/cash-flow/",
        reports_views.CashFlowView.as_view(),
        name="cash_flow_period",
    ),
    path(
        "reports/period/<int:period_id>/ar-aging/",
        reports_views.ARAgingView.as_view(),
        name="ar_aging_period",
    ),
    path(
        "reports/period/<int:period_id>/ap-aging/",
        reports_views.APAgingView.as_view(),
        name="ap_aging_period",
    ),
    path(
        "reports/period/<int:period_id>/trial-balance.csv",
        reports_views.trial_balance_csv,
        name="trial_balance_csv",
    ),
    path(
        "reports/period/<int:period_id>/income-statement.csv",
        reports_views.income_statement_csv,
        name="income_statement_csv",
    ),
    path(
        "reports/period/<int:period_id>/balance-sheet.csv",
        reports_views.balance_sheet_csv,
        name="balance_sheet_csv",
    ),
]
urlpatterns += [
    # for ledgers
    path("trial-balance/", views.trial_balance, name="trial_balance"),
    path("balance-sheet/", views.balance_sheet, name="balance_sheet"),
    path("profit-and-loss/", views.profit_loss, name="profit_loss"),
    path("income-statement/", views.income_statement, name="income_statement"),
    path("cash-flow/", views.cash_flow_statement, name="cash_flow"),
    path("ledger/audit/", views.audit_ledger, name="dea_ledger_audit"),
    path("ledger/", views.ledger_list, name="dea_ledger_list"),
    path("ledger/<int:pk>/", views.ledger_detail, name="dea_ledger_detail"),
    path("ledger/add/", views.ledger_save, name="dea_ledger_create"),
    path("ledger/<int:pk>/update/", views.ledger_save, name="dea_ledger_update"),
    path("ledger/<int:pk>/set-ob/", views.set_ledger_ob, name="dea_ledger_setob"),
    path(
        "ledger/statement/",
        views.ledger_statement_list,
        name="dea_ledgerstatement_list",
    ),
    path(
        "ledger/transaction/",
        views.ledger_transaction_list,
        name="dea_ledgertransaction_list",
    ),
]
urlpatterns += [
    # for accounts
    path("account/", views.account_list, name="dea_account_list"),
    path("account/<int:pk>/", views.account_detail, name="dea_account_detail"),
    path("account/<int:pk>/set-ob/", views.set_acc_ob, name="dea_account_setob"),
    path(
        "account/accountstatement/",
        views.accountstatement_list,
        name="dea_accountstatement_list",
    ),
    path(
        "account/accountstatement/<int:pk>/delete",
        views.accountstatement_delete,
        name="dea_accountstatement_delete",
    ),
    path("account/<int:pk>/audit/", views.audit_acc, name="dea_account_audit"),
    path("customer_balance/", views.get_customer_balance, name="get_customer_balance"),
]
urlpatterns += [
    # for journal entries
    path(
        "journal_entries/",
        views.journal_entry_list,
        name="dea_journal_entries_list",
    ),
    path(
        "journal_entry/<int:pk>/detail",
        views.journal_entry_detail,
        name="dea_journal_entry_detail",
    ),
    path(
        "journal_entry/<int:pk>/accounttransaction/create",
        views.accounttransaction_create,
        name="dea_accounttransaction_create",
    ),
    path(
        "journal_entry/<int:pk>/accounttransaction/update",
        views.accounttransaction_update,
        name="dea_accounttransaction_update",
    ),
    path(
        "journal_entry/<int:pk>/ledgertransaction/create",
        views.ledger_transaction_create,
        name="dea_ledgertransaction_create",
    ),
    path(
        "journal_entry/<int:pk>/ledgertransaction/update",
        views.ledger_transaction_update,
        name="dea_ledgertransaction_update",
    ),
    path(
        "journal_entry/<int:pk>/accounttransaction/delete",
        views.accounttransaction_delete,
        name="dea_accounttransaction_delete",
    ),
    path(
        "dea/accounttransaction/<int:pk>/detail/",
        views.accounttransaction_detail,
        name="dea_accounttransaction_detail",
    ),
    path(
        "dea/ledgertransaction/<int:pk>/detail/",
        views.ledger_transaction_detail,
        name="dea_ledgertransaction_detail",
    ),
    path(
        "journal_entry/<int:pk>/ledgertransaction/delete",
        views.ledger_transaction_delete,
        name="dea_ledgertransaction_delete",
    ),
    path(
        "journal_entry/<int:pk>/delete",
        views.journal_entry_delete,
        name="dea_journal_entry_delete",
    ),
    path(
        "journal_entry/create/",
        views.create_journal_entry,
        name="dea_journal_entry_create",
    ),
]

# Accounting Period URLs
urlpatterns += [
    # Opening balance setup
    path(
        "opening-balance/wizard/",
        views.opening_balance_wizard,
        name="dea_opening_balance_wizard",
    ),
    path(
        "opening-balance/bulk-import/",
        views.opening_balance_bulk_import,
        name="dea_opening_balance_bulk_import",
    ),
    path(
        "opening-balance/template/",
        views.opening_balance_template_download,
        name="dea_ob_template",
    ),
    path(
        "opening-balance/validate/",
        views.opening_balance_validate_ajax,
        name="dea_opening_balance_validate_ajax",
    ),
    # Period management
    path("periods/", views.period_list, name="dea_period_list"),
    path("period/create/", views.period_create, name="dea_period_create"),
    path("period/<int:pk>/", views.period_detail, name="dea_period_detail"),
    path("period/<int:pk>/update/", views.period_update, name="dea_period_update"),
    path("period/<int:pk>/delete/", views.period_delete, name="dea_period_delete"),
    # Period actions
    path(
        "period/<int:pk>/adjustments/",
        views.period_adjustments,
        name="dea_period_adjustments",
    ),
    path("period/<int:pk>/close/", views.period_close, name="dea_period_close"),
    path("period/<int:pk>/lock/", views.period_lock, name="dea_period_lock"),
    path("period/<int:pk>/unlock/", views.period_unlock, name="dea_period_unlock"),
    # Period reports
    path(
        "period/<int:pk>/transactions/",
        views.period_transactions,
        name="dea_period_transactions",
    ),
    path(
        "period/<int:pk>/balances/", views.period_balances, name="dea_period_balances"
    ),
    path("period/<int:pk>/report/", views.period_report, name="dea_period_report"),
    # AJAX endpoints
    path("period/status/", views.period_status_ajax, name="dea_period_status_ajax"),
]

# Voucher URLs
urlpatterns += [
    # Voucher list and detail views
    path("vouchers/", views.VoucherListView.as_view(), name="dea_voucher_list"),
    path(
        "vouchers/<int:pk>/",
        views.VoucherDetailView.as_view(),
        name="dea_voucher_detail",
    ),
    path(
        "vouchers/create/", views.VoucherCreateView.as_view(), name="dea_voucher_create"
    ),
    path(
        "vouchers/<int:pk>/edit/",
        views.VoucherUpdateView.as_view(),
        name="dea_voucher_update",
    ),
    path(
        "vouchers/<int:pk>/delete/",
        views.VoucherDeleteView.as_view(),
        name="dea_voucher_delete",
    ),
    # Voucher actions
    path("vouchers/<int:pk>/post/", views.post_voucher, name="dea_voucher_post"),
    path(
        "vouchers/<int:pk>/reverse/", views.reverse_voucher, name="dea_voucher_reverse"
    ),
    # AJAX / HTMX endpoints for vouchers
    path(
        "vouchers/<int:pk>/balance/",
        views.voucher_check_balance,
        name="dea_voucher_check_balance",
    ),
    path(
        "vouchers/<int:pk>/status/",
        views.voucher_status_badge,
        name="dea_voucher_status_badge",
    ),
]
# Payment Voucher URLs
urlpatterns += [
    # Payment Voucher list and detail views
    path("payments/", views.PaymentVoucherListView.as_view(), name="dea_payment_list"),
    path(
        "payments/<int:pk>/",
        views.PaymentVoucherDetailView.as_view(),
        name="dea_payment_detail",
    ),
    path(
        "payments/create/",
        views.PaymentVoucherCreateView.as_view(),
        name="dea_payment_create",
    ),
    path(
        "payments/<int:pk>/edit/",
        views.PaymentVoucherUpdateView.as_view(),
        name="dea_payment_update",
    ),
    path(
        "payments/<int:pk>/delete/",
        views.PaymentVoucherDeleteView.as_view(),
        name="dea_payment_delete",
    ),
]

# Expense Voucher URLs
urlpatterns += [
    # Expense Voucher list, detail, and post views
    path(
        "expenses/",
        views.expense.ExpenseVoucherListView.as_view(),
        name="dea_expense_list",
    ),
    path(
        "expenses/<int:pk>/",
        views.expense.ExpenseVoucherDetailView.as_view(),
        name="dea_expense_detail",
    ),
    path(
        "expenses/<int:pk>/post/",
        views.expense.post_expense_voucher,
        name="dea_expense_post",
    ),
    path(
        "expenses/create/",
        views.expense.ExpenseVoucherCreateView.as_view(),
        name="dea_expense_create",
    ),
    path(
        "expenses/<int:pk>/update/",
        views.expense.ExpenseVoucherUpdateView.as_view(),
        name="dea_expense_update",
    ),
    path(
        "expenses/<int:pk>/delete/",
        views.expense.ExpenseVoucherDeleteView.as_view(),
        name="dea_expense_delete",
    ),
    # Sales Invoice Voucher URLs
    path(
        "sales-invoices/create/",
        views.sales_invoice.SalesInvoiceCreateView.as_view(),
        name="dea_sales_invoice_create",
    ),
]

# Journal Entry Voucher URLs
urlpatterns += [
    # Journal Entry Voucher list and detail views
    path(
        "journal-entry-vouchers/",
        views.journal_entry_voucher.JournalEntryVoucherListView.as_view(),
        name="dea_journal_entry_voucher_list",
    ),
    path(
        "journal-entry-vouchers/<int:pk>/",
        views.journal_entry_voucher.JournalEntryVoucherDetailView.as_view(),
        name="dea_journal_entry_voucher_detail",
    ),
    path(
        "journal-entry-vouchers/create/",
        views.journal_entry_voucher.JournalEntryVoucherCreateView.as_view(),
        name="dea_journal_entry_voucher_create",
    ),
    path(
        "journal-entry-vouchers/<int:pk>/update/",
        views.journal_entry_voucher.JournalEntryVoucherUpdateView.as_view(),
        name="dea_journal_entry_voucher_update",
    ),
    path(
        "journal-entry-vouchers/<int:pk>/delete/",
        views.journal_entry_voucher.JournalEntryVoucherDeleteView.as_view(),
        name="dea_journal_entry_voucher_delete",
    ),
]
