from django.contrib import admin
from mptt.admin import MPTTModelAdmin

# Register your models here.
from . import models


class JournalEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        # "content_type",
        # "content_object",
        "posted_at",
        "desc",
    )
    # list_filter = ("journal_type",)
    search_fields = ("voucher__id",)


# === PRIORITY 1 VOUCHER ADMINS ===


class ExpenseLineItemInline(admin.TabularInline):
    """Inline admin for expense line items"""

    model = models.ExpenseLineItem
    extra = 1
    fields = (
        "line_number",
        "category",
        "description",
        "amount",
        "is_taxable",
        "tax_rate",
        "tds_rate",
    )
    readonly_fields = ("line_number", "tax_amount", "tds_amount", "line_total")


@admin.register(models.ExpenseVoucher)
class ExpenseVoucherAdmin(admin.ModelAdmin):
    """Admin for Expense Vouchers"""

    list_display = (
        "expense_number",
        "expense_date",
        "source_type",
        "party_name",
        "net_payable",
        "is_paid",
        "created_at",
    )
    list_filter = ("source_type", "is_paid", "expense_date", "created_at")
    search_fields = ("expense_number", "party_name", "source_doc_id")
    readonly_fields = (
        "expense_number",
        "gross_amount",
        "taxable_amount",
        "tax_amount",
        "tds_amount",
        "net_payable",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )
    inlines = [ExpenseLineItemInline]
    fieldsets = (
        (
            "Identity & Classification",
            {
                "fields": (
                    "expense_number",
                    "expense_date",
                    "source_type",
                    "source_doc_id",
                )
            },
        ),
        ("Party Information", {"fields": ("party_name", "party_email")}),
        (
            "Amounts",
            {
                "fields": (
                    "gross_amount",
                    "taxable_amount",
                    "tax_amount",
                    "tds_amount",
                    "net_payable",
                )
            },
        ),
        ("Description", {"fields": ("description", "memo")}),
        ("Payment Status", {"fields": ("is_paid", "paid_amount", "paid_date")}),
        (
            "Audit",
            {
                "fields": ("created_at", "updated_at", "created_by", "updated_by"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(models.ExpenseLineItem)
class ExpenseLineItemAdmin(admin.ModelAdmin):
    """Admin for Expense Line Items"""

    list_display = (
        "expense_voucher",
        "line_number",
        "category",
        "amount",
        "tax_amount",
        "tds_amount",
        "line_total",
    )
    list_filter = ("category", "is_taxable", "expense_voucher__expense_date")
    search_fields = ("expense_voucher__expense_number", "description")
    readonly_fields = ("line_number", "tax_amount", "tds_amount", "line_total")


class JournalEntryLineItemInline(admin.TabularInline):
    """Inline admin for journal entry line items"""

    model = models.JournalEntryLineItem
    extra = 1
    fields = ("line_number", "side", "ledger_name", "amount", "description")
    readonly_fields = ("line_number",)


@admin.register(models.JournalEntryVoucher)
class JournalEntryVoucherAdmin(admin.ModelAdmin):
    """Admin for Journal Entry Vouchers"""

    list_display = (
        "je_number",
        "je_date",
        "entry_type",
        "total_debit",
        "total_credit",
        "is_balanced",
        "created_at",
    )
    list_filter = ("entry_type", "je_date", "created_at")
    search_fields = ("je_number", "description", "reference")
    readonly_fields = (
        "je_number",
        "total_debit",
        "total_credit",
        "is_balanced",
        "balance_difference",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "reviewed_at",
    )
    inlines = [JournalEntryLineItemInline]
    fieldsets = (
        ("Identity", {"fields": ("je_number", "je_date", "entry_type")}),
        (
            "Amounts",
            {
                "fields": (
                    "total_debit",
                    "total_credit",
                    "is_balanced",
                    "balance_difference",
                )
            },
        ),
        ("Description", {"fields": ("description", "reference", "memo")}),
        ("Approval", {"fields": ("reviewed_by", "reviewed_at")}),
        (
            "Audit",
            {
                "fields": ("created_at", "updated_at", "created_by", "updated_by"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(models.JournalEntryLineItem)
class JournalEntryLineItemAdmin(admin.ModelAdmin):
    """Admin for Journal Entry Line Items"""

    list_display = (
        "journal_entry",
        "line_number",
        "side",
        "ledger_name",
        "amount",
    )
    list_filter = ("side", "journal_entry__je_date")
    search_fields = ("journal_entry__je_number", "ledger_name", "description")
    readonly_fields = ("line_number",)


# === PRIORITY 2 VOUCHER ADMINS ===


class SalesInvoiceLineItemInline(admin.TabularInline):
    """Inline admin for sales invoice line items"""

    model = models.SalesInvoiceLineItem
    extra = 1
    fields = (
        "line_number",
        "item_code",
        "description",
        "quantity",
        "unit_price",
        "line_total",
        "discount_percentage",
        "discount_amount",
        "cgst_rate",
        "sgst_rate",
        "igst_rate",
    )
    readonly_fields = (
        "line_number",
        "line_total",
        "discount_amount",
    )


@admin.register(models.SalesInvoiceVoucher)
class SalesInvoiceVoucherAdmin(admin.ModelAdmin):
    """Admin for Sales Invoice Vouchers"""

    list_display = (
        "invoice_number",
        "customer",
        "invoice_date",
        "total_amount",
        "received_amount",
        "is_fully_paid",
        "created_at",
    )
    list_filter = (
        "is_fully_paid",
        "invoice_date",
        "created_at",
    )
    search_fields = (
        "invoice_number",
        "customer__name",
    )
    readonly_fields = (
        "invoice_number",
        "subtotal",
        "discount_amount",
        "taxable_amount",
        "cgst_amount",
        "sgst_amount",
        "igst_amount",
        "tcs_amount",
        "total_amount",
        "outstanding_balance",
        "is_overdue",
        "payment_percentage",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )
    inlines = [SalesInvoiceLineItemInline]
    fieldsets = (
        ("Identity", {"fields": ("invoice_number", "customer", "invoice_date")}),
        (
            "Amounts",
            {
                "fields": (
                    "subtotal",
                    "discount_amount",
                    "taxable_amount",
                    "cgst_amount",
                    "sgst_amount",
                    "igst_amount",
                    "tcs_amount",
                    "total_amount",
                )
            },
        ),
        (
            "Payment Tracking",
            {
                "fields": (
                    "received_amount",
                    "is_fully_paid",
                    "outstanding_balance",
                    "is_overdue",
                    "payment_percentage",
                )
            },
        ),
        ("Description", {"fields": ("description", "memo")}),
        (
            "Audit",
            {
                "fields": ("created_at", "updated_at", "created_by", "updated_by"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(models.SalesInvoiceLineItem)
class SalesInvoiceLineItemAdmin(admin.ModelAdmin):
    """Admin for Sales Invoice Line Items"""

    list_display = (
        "invoice",
        "line_number",
        "item_code",
        "quantity",
        "unit_price",
        "line_total",
    )
    list_filter = (
        "line_number",
        "invoice",
    )
    search_fields = (
        "invoice__invoice_number",
        "item_code",
        "description",
    )
    readonly_fields = (
        "line_number",
        "line_total",
        "discount_amount",
    )


class PurchaseInvoiceLineItemInline(admin.TabularInline):
    """Inline admin for purchase invoice line items"""

    model = models.PurchaseInvoiceLineItem
    extra = 1
    fields = (
        "line_number",
        "item_code",
        "description",
        "quantity",
        "unit_price",
        "line_total",
        "cgst_rate",
        "sgst_rate",
        "igst_rate",
    )
    readonly_fields = (
        "line_number",
        "line_total",
    )


@admin.register(models.PurchaseInvoiceVoucher)
class PurchaseInvoiceVoucherAdmin(admin.ModelAdmin):
    """Admin for Purchase Invoice Vouchers"""

    list_display = (
        "internal_number",
        "vendor",
        "purchase_type",
        "invoice_date",
        "net_payable",
        "paid_amount",
        "is_fully_paid",
        "created_at",
    )
    list_filter = (
        "purchase_type",
        "is_fully_paid",
        "invoice_date",
        "created_at",
    )
    search_fields = (
        "internal_number",
        "invoice_number",
        "vendor__name",
    )
    readonly_fields = (
        "internal_number",
        "subtotal",
        "discount_amount",
        "taxable_amount",
        "cgst_amount",
        "sgst_amount",
        "igst_amount",
        "tds_amount",
        "net_payable",
        "outstanding_balance",
        "is_overdue",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )
    inlines = [PurchaseInvoiceLineItemInline]
    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "internal_number",
                    "vendor",
                    "purchase_type",
                    "invoice_number",
                    "invoice_date",
                    "received_date",
                )
            },
        ),
        (
            "Amounts",
            {
                "fields": (
                    "subtotal",
                    "discount_amount",
                    "taxable_amount",
                    "cgst_amount",
                    "sgst_amount",
                    "igst_amount",
                    "tds_amount",
                    "net_payable",
                )
            },
        ),
        (
            "Payment Tracking",
            {
                "fields": (
                    "paid_amount",
                    "is_fully_paid",
                    "outstanding_balance",
                    "is_overdue",
                )
            },
        ),
        ("Description", {"fields": ("description", "memo")}),
        (
            "Audit",
            {
                "fields": ("created_at", "updated_at", "created_by", "updated_by"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(models.PurchaseInvoiceLineItem)
class PurchaseInvoiceLineItemAdmin(admin.ModelAdmin):
    """Admin for Purchase Invoice Line Items"""

    list_display = (
        "invoice",
        "line_number",
        "item_code",
        "quantity",
        "unit_price",
        "line_total",
    )
    list_filter = (
        "line_number",
        "invoice",
    )
    search_fields = (
        "invoice__internal_number",
        "item_code",
        "description",
    )
    readonly_fields = (
        "line_number",
        "line_total",
    )


# Register your models here.
admin.site.register(models.Account)
admin.site.register(models.AccountType)
admin.site.register(models.EntityType)
admin.site.register(models.Ledger, MPTTModelAdmin)
admin.site.register(models.TransactionType_DE)
admin.site.register(models.TransactionType_Ext)
admin.site.register(models.LedgerTransaction)
admin.site.register(models.LedgerStatement)
admin.site.register(models.AccountType_Ext)
admin.site.register(models.AccountTransaction)
admin.site.register(models.AccountStatement)
admin.site.register(models.JournalEntry, JournalEntryAdmin)
