import django_tables2 as tables
from django.utils.html import format_html

from .models import (
    Account,
    AccountingPeriod,
    AccountStatement,
    JournalEntry,
    Ledger,
    LedgerStatement,
    LedgerTransaction,
    Voucher,
)

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
    desc = tables.Column(verbose_name="Description")
    voucher = tables.Column(verbose_name="Voucher", accessor="voucher", linkify=True)
    posted_at = tables.DateTimeColumn(verbose_name="Posted At", format="Y-m-d H:i")
    balance_status = tables.Column(empty_values=(), verbose_name="Balance")
    imbalance = tables.Column(empty_values=(), verbose_name="Difference")

    class Meta:
        model = JournalEntry
        fields = (
            "id",
            "posted_at",
            "voucher",
            "desc",
            "balance_status",
            "imbalance",
        )
        attrs = {
            "class": "table table-sm table-bordered table-striped-columns table-hover"
        }
        empty_text = "There are no loans matching the search criteria..."
        template_name = "django_tables2/bootstrap.html"  # Use Bootstrap styling
        # template_name = "table_htmx.html"

    def _get_balance_data(self, record):
        if not hasattr(record, "_balance_validation_cache"):
            is_balanced, _, _, imbalances = record.validate_balanced()
            imbalance_text = ", ".join(
                str(amount) for amount in imbalances.values()
            )
            record._balance_validation_cache = {
                "is_balanced": is_balanced,
                "imbalance_text": imbalance_text,
            }
        return record._balance_validation_cache

    def render_balance_status(self, record):
        balance_data = self._get_balance_data(record)
        if balance_data["is_balanced"]:
            return format_html(
                '<span class="badge bg-success">{}</span>',
                "Balanced",
            )

        return format_html(
            '<span class="badge bg-danger">{}</span>',
            "Unbalanced",
        )

    def render_imbalance(self, record):
        balance_data = self._get_balance_data(record)
        if balance_data["is_balanced"]:
            return format_html(
                '<span class="text-muted">{}</span>',
                "-",
            )

        return format_html(
            '<span class="text-danger fw-semibold">{}</span>',
            balance_data["imbalance_text"] or "Check lines",
        )


class PeriodTable(tables.Table):
    """Table for displaying accounting periods"""

    id = tables.Column(verbose_name="ID", linkify=True)
    name = tables.Column(linkify=True, verbose_name="Period Name")
    start_date = tables.DateColumn(verbose_name="Start Date", format="Y-m-d")
    end_date = tables.DateColumn(verbose_name="End Date", format="Y-m-d")
    status = tables.Column(verbose_name="Status")
    journal_count = tables.Column(verbose_name="Entries", accessor="journal_count")

    actions = tables.TemplateColumn(
        template_name="dea/partials/period_actions.html",
        verbose_name="Actions",
        orderable=False,
    )

    class Meta:
        model = AccountingPeriod
        fields = (
            "id",
            "name",
            "start_date",
            "end_date",
            "status",
            "journal_count",
            "actions",
        )
        attrs = {"class": "table table-sm table-bordered table-striped table-hover"}
        empty_text = "No accounting periods found"
        template_name = "django_tables2/bootstrap5.html"

    def render_status(self, value):
        """Render status with badge"""
        badge_class = {"OPEN": "success", "CLOSED": "warning", "LOCKED": "danger"}.get(
            value, "secondary"
        )
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            badge_class,
            value,
        )


# ============================================================================
# VOUCHER TABLE
# ============================================================================


class VoucherTable(tables.Table):
    """
    Table for displaying vouchers with filtering and actions.

    Features:
    - Clickable voucher number (links to detail)
    - Status badge with color coding
    - Voucher type display
    - Created by user
    - Date filters
    - Action buttons (edit, post, reverse)
    """

    from .models import Voucher

    voucher_no = tables.Column(
        verbose_name="Voucher#",
        linkify=lambda record: record.get_absolute_url(),
        orderable=True,
    )
    voucher_type = tables.Column(
        verbose_name="Type", accessor="voucher_type.name", orderable=True
    )
    voucher_date = tables.DateColumn(
        verbose_name="Date", format="Y-m-d", orderable=True
    )
    status = tables.Column(verbose_name="Status", orderable=True)
    created_by = tables.Column(
        verbose_name="Created By", accessor="created_by.get_full_name", orderable=True
    )
    created_at = tables.DateTimeColumn(
        verbose_name="Created", format="Y-m-d H:i", orderable=True
    )
    actions = tables.TemplateColumn(
        template_name="dea/partials/voucher_actions.html",
        verbose_name="Actions",
        orderable=False,
        exclude_from_export=True,
    )

    class Meta:
        model = Voucher
        fields = (
            "voucher_no",
            "voucher_type",
            "voucher_date",
            "status",
            "created_by",
            "created_at",
            "actions",
        )
        attrs = {
            "class": "table table-sm table-bordered table-striped-columns table-hover",
            "id": "voucher-table",
        }
        empty_text = "No vouchers found"
        template_name = "django_tables2/bootstrap5.html"
        order_by = "-created_at"
        row_attrs = {
            "data-voucher-id": lambda record: record.pk,
            "data-status": lambda record: record.status,
        }

    def render_status(self, value, record):
        """Render status with color-coded badge"""
        badge_class = {
            "DRAFT": "secondary",
            "POSTED": "success",
            "CORRECTED": "warning",
            "REVERSED": "danger",
        }.get(value, "secondary")

        status_text = {
            "DRAFT": "📝 Draft",
            "POSTED": "✓ Posted",
            "CORRECTED": "⚠️ Corrected",
            "REVERSED": "↩️ Reversed",
        }.get(value, value)

        return format_html(
            '<span class="badge bg-{}">{}</span>',
            badge_class,
            status_text,
        )

    def render_created_by(self, value):
        """Render user name with fallback"""
        return value or "System"


class VoucherLineItemTable(tables.Table):
    """
    Table for displaying line items within a voucher.

    Shows debit/credit entries with running totals.
    """

    from .models import LedgerTransaction, AccountTransaction

    SIDE_CHOICES = {
        "DEBIT": "💰 DR",
        "CREDIT": "📤 CR",
    }

    class Meta:
        attrs = {
            "class": "table table-sm table-bordered table-striped-columns",
            "id": "line-items-table",
        }
        empty_text = "No line items added yet"
        template_name = "django_tables2/bootstrap5.html"

    def render_side(self, value):
        """Render debit/credit with emoji"""
        return self.SIDE_CHOICES.get(value, value)
