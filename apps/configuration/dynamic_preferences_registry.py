from decimal import Decimal

from dynamic_preferences.preferences import Section
from dynamic_preferences.registries import global_preferences_registry
from dynamic_preferences.types import (
    BooleanPreference,
    ChoicePreference,
    DecimalPreference,
    IntegerPreference,
    StringPreference,
)
from dynamic_preferences.users.registries import user_preferences_registry

from .registries import workspace_preferences_registry

accounting = Section("accounting")
commodity = Section("commodity")
loan = Section("loan")
inventory = Section("inventory")
notifications = Section("notifications")
documents = Section("documents")
ui = Section("ui")
platform = Section("platform")


def register_workspace_and_global(cls):
    global_preferences_registry.register(type(f"Global{cls.__name__}", (cls,), {}))
    workspace_preferences_registry.register(type(f"Workspace{cls.__name__}", (cls,), {}))
    return cls


def register_user(cls):
    user_preferences_registry.register(type(f"User{cls.__name__}", (cls,), {}))
    return cls


@global_preferences_registry.register
class PlatformTrialDays(IntegerPreference):
    section = platform
    name = "trial_days"
    default = 14
    required = True


@global_preferences_registry.register
class PlatformSupportEmail(StringPreference):
    section = platform
    name = "support_email"
    default = "support@rokkad.local"
    required = False


@global_preferences_registry.register
class PlatformDefaultTimezone(StringPreference):
    section = platform
    name = "default_timezone"
    default = "Asia/Kolkata"
    required = True


@global_preferences_registry.register
class PlatformFeatureDefaults(StringPreference):
    section = platform
    name = "feature_defaults"
    default = "{}"
    required = False


@global_preferences_registry.register
class PlatformMaintenanceMode(BooleanPreference):
    section = platform
    name = "maintenance_mode"
    default = False
    required = False


@register_workspace_and_global
class AccountingFinancialYearStartMonth(IntegerPreference):
    section = accounting
    name = "financial_year_start_month"
    default = 4
    required = True


@register_workspace_and_global
class AccountingFinancialYearStartDay(IntegerPreference):
    section = accounting
    name = "financial_year_start_day"
    default = 1
    required = True


@register_workspace_and_global
class AccountingDefaultCurrency(StringPreference):
    section = accounting
    name = "default_currency"
    default = "INR"
    required = True


@register_workspace_and_global
class AccountingVoucherPrefix(StringPreference):
    section = accounting
    name = "voucher_prefix"
    default = "VCH"
    required = True


@register_workspace_and_global
class AccountingInvoicePrefix(StringPreference):
    section = accounting
    name = "invoice_prefix"
    default = "INV"
    required = True


@register_workspace_and_global
class AccountingNumberingStrategy(ChoicePreference):
    section = accounting
    name = "numbering_strategy"
    default = "period_sequence"
    choices = [
        ("period_sequence", "Period sequence"),
        ("date_sequence", "Date sequence"),
        ("global_sequence", "Global sequence"),
    ]
    required = True


@register_workspace_and_global
class AccountingDefaultCashLedger(StringPreference):
    section = accounting
    name = "default_cash_ledger"
    default = ""
    required = False


@register_workspace_and_global
class AccountingDefaultBankLedger(StringPreference):
    section = accounting
    name = "default_bank_ledger"
    default = ""
    required = False


@register_workspace_and_global
class AccountingDefaultReceivableLedger(StringPreference):
    section = accounting
    name = "default_receivable_ledger"
    default = ""
    required = False


@register_workspace_and_global
class AccountingDefaultPayableLedger(StringPreference):
    section = accounting
    name = "default_payable_ledger"
    default = ""
    required = False


@register_workspace_and_global
class AccountingDefaultSalesLedger(StringPreference):
    section = accounting
    name = "default_sales_ledger"
    default = ""
    required = False


@register_workspace_and_global
class AccountingDefaultPurchaseLedger(StringPreference):
    section = accounting
    name = "default_purchase_ledger"
    default = ""
    required = False


@register_workspace_and_global
class AccountingRoundingPolicy(ChoicePreference):
    section = accounting
    name = "rounding_policy"
    default = "nearest_paisa"
    choices = [
        ("nearest_paisa", "Nearest paisa"),
        ("nearest_rupee", "Nearest rupee"),
        ("none", "No rounding"),
    ]
    required = True


@register_workspace_and_global
class CommodityDefaultMetalUnit(ChoicePreference):
    section = commodity
    name = "default_metal_unit"
    default = "gram"
    choices = [("gram", "Gram"), ("tola", "Tola")]
    required = True


@register_workspace_and_global
class CommodityDefaultGoldPurity(DecimalPreference):
    section = commodity
    name = "default_gold_purity"
    default = Decimal("0.916000")
    required = True


@register_workspace_and_global
class CommodityDefaultSilverPurity(DecimalPreference):
    section = commodity
    name = "default_silver_purity"
    default = Decimal("0.999000")
    required = True


@register_workspace_and_global
class CommodityDefaultRateSource(StringPreference):
    section = commodity
    name = "default_rate_source"
    default = ""
    required = False


@register_workspace_and_global
class CommodityDefaultFixingBehavior(ChoicePreference):
    section = commodity
    name = "default_fixing_behavior"
    default = "manual"
    choices = [("manual", "Manual"), ("same_day", "Same day")]
    required = True


@register_workspace_and_global
class LoanDefaultInterestCalculationMethod(ChoicePreference):
    section = loan
    name = "default_interest_calculation_method"
    default = "monthly_simple"
    choices = [
        ("monthly_simple", "Monthly simple"),
        ("daily_simple", "Daily simple"),
    ]
    required = True


@register_workspace_and_global
class LoanDefaultDate(StringPreference):
    section = loan
    name = "default_date"
    default = "N"
    required = True


@register_workspace_and_global
class LoanInterestDeductionEnabled(BooleanPreference):
    section = loan
    name = "interest_deduction_enabled"
    default = False
    required = False


@register_workspace_and_global
class LoanCollateralHaircutPercent(DecimalPreference):
    section = loan
    name = "collateral_haircut_percent"
    default = Decimal("75.00")
    required = True


@register_workspace_and_global
class LoanDefaultGoldInterestRate(DecimalPreference):
    section = loan
    name = "default_gold_interest_rate"
    default = Decimal("2.00")
    required = True


@register_workspace_and_global
class LoanDefaultSilverInterestRate(DecimalPreference):
    section = loan
    name = "default_silver_interest_rate"
    default = Decimal("4.00")
    required = True


@register_workspace_and_global
class LoanDefaultOtherInterestRate(DecimalPreference):
    section = loan
    name = "default_other_interest_rate"
    default = Decimal("8.00")
    required = True


@register_workspace_and_global
class LoanAccrualTiming(ChoicePreference):
    section = loan
    name = "accrual_timing"
    default = "EOM"
    choices = [("EOM", "End of month"), ("BOM", "Beginning of month")]
    required = True


@register_workspace_and_global
class LoanAutoPostAccruals(BooleanPreference):
    section = loan
    name = "auto_post_accruals"
    default = True
    required = False


@register_workspace_and_global
class LoanCatchupOnReceipt(BooleanPreference):
    section = loan
    name = "catchup_on_receipt"
    default = True
    required = False


@register_workspace_and_global
class LoanCatchupOnRelease(BooleanPreference):
    section = loan
    name = "catchup_on_release"
    default = True
    required = False


@register_workspace_and_global
class LoanReleaseFailClosedOnAccrualError(BooleanPreference):
    section = loan
    name = "release_fail_closed_on_accrual_error"
    default = False
    required = False


@register_workspace_and_global
class LoanCatchupOnRenewal(BooleanPreference):
    section = loan
    name = "catchup_on_renewal"
    default = True
    required = False


@register_workspace_and_global
class LoanAllowBackfillPosting(BooleanPreference):
    section = loan
    name = "allow_backfill_posting"
    default = False
    required = False


@register_workspace_and_global
class LoanDisbursalDeductionsEnabled(BooleanPreference):
    section = loan
    name = "disbursal_deductions_enabled"
    default = False
    required = False


@register_workspace_and_global
class LoanMinimumDocumentCharge(DecimalPreference):
    section = loan
    name = "minimum_document_charge"
    default = Decimal("0.00")
    required = True


@register_workspace_and_global
class LoanGracePeriodDays(IntegerPreference):
    section = loan
    name = "grace_period_days"
    default = 0
    required = True


@register_workspace_and_global
class LoanNoticeTimingDays(IntegerPreference):
    section = loan
    name = "notice_timing_days"
    default = 30
    required = True


@register_workspace_and_global
class LoanAuctionTimingDays(IntegerPreference):
    section = loan
    name = "auction_timing_days"
    default = 30
    required = True


@register_workspace_and_global
class LoanDefaultDocumentTemplate(StringPreference):
    section = loan
    name = "default_document_template"
    default = ""
    required = False


@register_workspace_and_global
class InventoryDefaultStockMode(ChoicePreference):
    section = inventory
    name = "default_stock_mode"
    default = "quantity"
    choices = [("quantity", "Quantity"), ("weight", "Weight")]
    required = True


@register_workspace_and_global
class InventoryBarcodeQrBehavior(ChoicePreference):
    section = inventory
    name = "barcode_qr_behavior"
    default = "disabled"
    choices = [("disabled", "Disabled"), ("barcode", "Barcode"), ("qr", "QR")]
    required = True


@register_workspace_and_global
class InventoryDefaultValuationMethod(ChoicePreference):
    section = inventory
    name = "default_valuation_method"
    default = "weighted_average"
    choices = [
        ("weighted_average", "Weighted average"),
        ("fifo", "FIFO"),
        ("specific_identification", "Specific identification"),
    ]
    required = True


@register_workspace_and_global
class InventoryDefaultPurity(StringPreference):
    section = inventory
    name = "default_purity"
    default = ""
    required = False


@register_workspace_and_global
class InventoryDefaultUnit(StringPreference):
    section = inventory
    name = "default_unit"
    default = ""
    required = False


@register_workspace_and_global
class NotificationsWhatsappEnabled(BooleanPreference):
    section = notifications
    name = "whatsapp_enabled"
    default = False
    required = False


@register_workspace_and_global
class NotificationsEmailEnabled(BooleanPreference):
    section = notifications
    name = "email_enabled"
    default = True
    required = False


@register_workspace_and_global
class NotificationsDefaultReminderTimingDays(IntegerPreference):
    section = notifications
    name = "default_reminder_timing_days"
    default = 7
    required = True


@register_workspace_and_global
class NotificationsCustomerReminderRules(StringPreference):
    section = notifications
    name = "customer_reminder_rules"
    default = "{}"
    required = False


@register_workspace_and_global
class NotificationsFallbackBehavior(ChoicePreference):
    section = notifications
    name = "fallback_behavior"
    default = "email_after_whatsapp_failure"
    choices = [
        ("none", "No fallback"),
        ("email_after_whatsapp_failure", "Email after WhatsApp failure"),
    ]
    required = True


@register_workspace_and_global
class DocumentsInvoiceTemplate(StringPreference):
    section = documents
    name = "invoice_template"
    default = ""
    required = False


@register_workspace_and_global
class DocumentsReceiptTemplate(StringPreference):
    section = documents
    name = "receipt_template"
    default = ""
    required = False


@register_workspace_and_global
class DocumentsLoanDocumentTemplate(StringPreference):
    section = documents
    name = "loan_document_template"
    default = ""
    required = False


@register_workspace_and_global
class DocumentsPrintFormatDefaults(StringPreference):
    section = documents
    name = "print_format_defaults"
    default = "{}"
    required = False


@register_workspace_and_global
class UIDefaultTablePageSize(IntegerPreference):
    section = ui
    name = "default_table_page_size"
    default = 25
    required = True


@register_workspace_and_global
class UIDefaultLandingPage(StringPreference):
    section = ui
    name = "default_landing_page"
    default = "dashboard"
    required = True


@register_user
class UITheme(ChoicePreference):
    section = ui
    name = "theme"
    default = "system"
    choices = [("system", "System"), ("light", "Light"), ("dark", "Dark")]
    required = True


@register_user
class UISidebarCollapsed(BooleanPreference):
    section = ui
    name = "sidebar_collapsed"
    default = False
    required = False


@register_user
class UIDashboardWidgets(StringPreference):
    section = ui
    name = "dashboard_widgets"
    default = "[]"
    required = False


@register_user
class UITablePageSize(IntegerPreference):
    section = ui
    name = "table_page_size"
    default = 25
    required = True


@register_user
class UIDateDisplayFormat(StringPreference):
    section = ui
    name = "date_display_format"
    default = "YYYY-MM-DD"
    required = True


@register_user
class UIDefaultLandingPageUser(StringPreference):
    section = ui
    name = "default_landing_page"
    default = "dashboard"
    required = True
