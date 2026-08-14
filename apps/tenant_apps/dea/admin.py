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


@admin.register(models.Commodity)
class CommodityAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "commodity_type", "default_uom", "is_active")
    list_filter = ("commodity_type", "default_uom", "is_active")
    search_fields = ("code", "name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(models.CommodityAccount)
class CommodityAccountAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "commodity",
        "purpose",
        "party",
        "location_label",
        "is_active",
    )
    list_filter = ("commodity", "purpose", "is_active")
    search_fields = ("code", "name", "party__display_name", "location_label")
    autocomplete_fields = ("commodity", "party")
    readonly_fields = ("created_at", "updated_at")


@admin.register(models.CommodityMovement)
class CommodityMovementAdmin(admin.ModelAdmin):
    list_display = (
        "movement_no",
        "movement_date",
        "commodity",
        "movement_type",
        "fixed_status",
        "from_account",
        "to_account",
        "fine_weight",
        "uom",
    )
    list_filter = ("commodity", "movement_type", "fixed_status", "uom")
    search_fields = (
        "movement_no",
        "idempotency_key",
        "from_account__code",
        "to_account__code",
        "narration",
    )
    raw_id_fields = (
        "commodity",
        "from_account",
        "to_account",
        "voucher",
        "source_content_type",
        "is_reversal_of",
        "created_by",
    )
    readonly_fields = (
        "movement_no",
        "movement_date",
        "source_content_type",
        "source_object_id",
        "voucher",
        "commodity",
        "uom",
        "gross_weight",
        "purity",
        "fine_weight",
        "from_account",
        "to_account",
        "movement_type",
        "fixed_status",
        "rate",
        "rate_currency",
        "valuation_currency",
        "valuation_amount",
        "is_reversal_of",
        "idempotency_key",
        "narration",
        "metadata",
        "created_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class RateFixingAllocationInline(admin.TabularInline):
    model = models.RateFixingAllocation
    extra = 0
    raw_id_fields = ("exposure",)
    readonly_fields = ("rate_fixing", "exposure", "fine_weight", "amount")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(models.ExposureLine)
class ExposureLineAdmin(admin.ModelAdmin):
    list_display = (
        "exposure_no",
        "party",
        "commodity",
        "side",
        "status",
        "fixed_status",
        "original_fine_weight",
        "open_fine_weight",
        "uom",
    )
    list_filter = ("commodity", "side", "status", "fixed_status", "uom")
    search_fields = (
        "exposure_no",
        "idempotency_key",
        "party__display_name",
        "rate_basis",
    )
    raw_id_fields = (
        "source_content_type",
        "voucher",
        "party",
        "commodity",
        "is_reversal_of",
        "created_by",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(models.RateFixing)
class RateFixingAdmin(admin.ModelAdmin):
    list_display = (
        "fixing_no",
        "fixing_date",
        "party",
        "commodity",
        "side",
        "fine_weight",
        "rate",
        "currency",
        "valuation_amount",
        "status",
    )
    list_filter = ("commodity", "side", "status", "currency")
    search_fields = ("fixing_no", "idempotency_key", "party__display_name")
    raw_id_fields = ("party", "commodity", "voucher", "created_by", "updated_by")
    readonly_fields = ("created_at", "updated_at")
    inlines = [RateFixingAllocationInline]


@admin.register(models.RateFixingAllocation)
class RateFixingAllocationAdmin(admin.ModelAdmin):
    list_display = ("rate_fixing", "exposure", "fine_weight", "amount")
    raw_id_fields = ("rate_fixing", "exposure")


@admin.register(models.BusinessEventDraft)
class BusinessEventDraftAdmin(admin.ModelAdmin):
    list_display = (
        "event_type",
        "source_reference",
        "event_date",
        "status",
        "payload_hash",
        "updated_at",
    )
    list_filter = ("event_type", "status", "event_date")
    search_fields = ("source_reference", "payload_hash")
    raw_id_fields = ("created_by", "updated_by")
    readonly_fields = ("created_at", "updated_at")


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


@admin.register(models.PartyAccountMapping)
class PartyAccountMappingAdmin(admin.ModelAdmin):
    list_display = (
        "party",
        "role_key",
        "purpose",
        "account",
        "control_ledger",
        "status",
        "is_default",
    )
    list_filter = ("status", "purpose", "role_key", "is_default")
    search_fields = (
        "party__display_name",
        "party__party_code",
        "account__account_number",
        "role_key",
        "purpose",
    )
    raw_id_fields = ("party", "account", "control_ledger")


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
