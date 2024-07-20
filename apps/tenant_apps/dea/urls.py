from django.urls import path

from . import views

urlpatterns = [
    # for common views
    path("", views.home, name="dea_home"),
    path("dea/gl/", views.generalledger, name="dea_general_ledger"),
    path("daybook/", views.daybook, name="dea_daybook"),
]
urlpatterns += [
    # for ledgers
    path("ledger/audit/", views.audit_ledger, name="dea_ledger_audit"),
    path("ledger/", views.ledger_list, name="dea_ledger_list"),
    path("ledger/<int:pk>/", views.ledger_detail, name="dea_ledger_detail"),
    path("ledger/add/", views.ledger_create, name="dea_ledger_create"),
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
        "journal_entry/<int:pk>/ledgertransaction/create",
        views.ledger_transaction_create,
        name="dea_ledgertransaction_create",
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
