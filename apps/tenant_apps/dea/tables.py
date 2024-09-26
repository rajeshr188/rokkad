import django_tables2 as tables

from .models import (Account, AccountStatement, JournalEntry, Ledger,
                     LedgerStatement, LedgerTransaction)

# Import the required modules


# Define the tables for each model
class LedgerTable(tables.Table):
    ledger_balance = tables.Column(accessor="get_balance", verbose_name="Balance")

    class Meta:
        model = Ledger
        fields = (
            "id",
            "name",
            "account_type",
            "parent," "ledger_balance",
        )
        attrs = {
            "class": "table table-sm table-bordered table-striped-columns table-hover"
        }
        empty_text = "There are no loans matching the search criteria..."
        template_name = "django_tables2/bootstrap.html"  # Use Bootstrap styling
        # template_name = "table_htmx.html"


class AccountTable(tables.Table):
    id = tables.Column(verbose_name="ID", linkify=True)
    AccountType_Ext = tables.Column(verbose_name="Type")
    balance = tables.Column(accessor="get_balance", verbose_name="Balance")
    contact = tables.Column(linkify=True, verbose_name="Account")

    class Meta:
        model = Account
        fields = (
            "id",
            "contact",
            "AccountType_Ext",
            "balance",
        )
        attrs = {
            "class": "table table-sm table-bordered table-striped-columns table-hover"
        }
        empty_text = "There are no loans matching the search criteria..."
        template_name = "django_tables2/bootstrap.html"  # Use Bootstrap styling
        # template_name = "table_htmx.html"


class LedgerStatementTable(tables.Table):
    class Meta:
        model = LedgerStatement

        attrs = {
            "class": "table table-sm table-bordered table-striped-columns table-hover"
        }
        empty_text = "There are no loans matching the search criteria..."
        template_name = "django_tables2/bootstrap.html"  # Use Bootstrap styling
        # template_name = "table_htmx.html"


class LedgerTransactionTable(tables.Table):
    journal_entry = tables.Column(linkify=True, verbose_name="Journal Entry")
    ledgerno = tables.Column(linkify=True, verbose_name=" Credit Ledger")
    ledgerno_dr = tables.Column(linkify=True, verbose_name="Debit Ledger")

    class Meta:
        model = LedgerTransaction
        fields = (
            "journal_entry",
            "ledgerno_dr",
            "ledgerno",
            "amount",
            "desc",
        )
        attrs = {
            "class": "table table-sm table-bordered table-striped-columns table-hover"
        }
        empty_text = "There are no loans matching the search criteria..."
        template_name = "django_tables2/bootstrap.html"  # Use Bootstrap styling
        # template_name = "table_htmx.html"


class AccountStatementTable(tables.Table):
    class Meta:
        model = AccountStatement

        attrs = {
            "class": "table table-sm table-bordered table-striped-columns table-hover"
        }
        empty_text = "There are no loans matching the search criteria..."
        template_name = "django_tables2/bootstrap.html"  # Use Bootstrap styling
        # template_name = "table_htmx.html"


class JournalEntriesTable(tables.Table):
    id = tables.Column(verbose_name="ID", linkify=True)
    desc = tables.Column(
        verbose_name="Description", linkify=lambda record: record.get_voucher_url()
    )
    content_object = tables.Column(
        linkify=lambda record: record.get_voucher_url(),
        verbose_name="Voucher",
    )

    class Meta:
        model = JournalEntry
        fields = (
            "id",
            "created",
            "updated",
            "desc",
        )
        attrs = {
            "class": "table table-sm table-bordered table-striped-columns table-hover"
        }
        empty_text = "There are no loans matching the search criteria..."
        template_name = "django_tables2/bootstrap.html"  # Use Bootstrap styling
        # template_name = "table_htmx.html"
