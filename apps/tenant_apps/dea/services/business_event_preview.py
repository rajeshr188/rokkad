from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from apps.tenant_apps.dea.models import (
    Account,
    AccountingPeriod,
    BusinessEventDraft,
    Commodity,
    CommodityAccount,
    ExposureLine,
    Ledger,
    Voucher,
    VoucherStatus,
)
from apps.tenant_apps.dea.posting.context import compute_fingerprint
from apps.tenant_apps.dea.services.fixed_purchase import FIXED_PURCHASE_VOUCHER_TYPE
from apps.tenant_apps.dea.services.fixed_sale import FIXED_SALE_VOUCHER_TYPE
from apps.tenant_apps.dea.services.karigar import (
    KARIGAR_ISSUE_VOUCHER_TYPE,
    KARIGAR_RECEIPT_VOUCHER_TYPE,
)
from apps.tenant_apps.dea.services.unfixed_purchase import UNFIXED_PURCHASE_VOUCHER_TYPE
from apps.tenant_apps.dea.services.unfixed_sale import UNFIXED_SALE_VOUCHER_TYPE
from apps.tenant_apps.party.models import Party


FIXED_PURCHASE_PREVIEW_VERSION = "fixed-purchase-preview-v1"
UNFIXED_PURCHASE_PREVIEW_VERSION = "unfixed-purchase-preview-v1"
PURCHASE_RATE_FIXING_PREVIEW_VERSION = "purchase-rate-fixing-preview-v1"
SALE_RATE_FIXING_PREVIEW_VERSION = "sale-rate-fixing-preview-v1"
FIXED_SALE_PREVIEW_VERSION = "fixed-sale-preview-v1"
UNFIXED_SALE_PREVIEW_VERSION = "unfixed-sale-preview-v1"
MONETARY_SETTLEMENT_PREVIEW_VERSION = "monetary-settlement-preview-v1"
KARIGAR_MOVEMENT_PREVIEW_VERSION = "karigar-movement-preview-v1"


def build_fixed_purchase_preview(cleaned_data: dict) -> dict:
    normalized_payload = build_fixed_purchase_normalized_payload(cleaned_data)
    money_amount = cleaned_data["money_amount"].quantize(Decimal("0.01"))
    fine_weight = cleaned_data["fine_weight"].quantize(Decimal("0.001"))
    gross_weight = cleaned_data["gross_weight"].quantize(Decimal("0.001"))
    purity = cleaned_data["purity"].quantize(Decimal("0.000001"))
    rate = (money_amount / fine_weight).quantize(Decimal("0.0001"))
    expected_fine_weight = (gross_weight * purity).quantize(Decimal("0.001"))

    fingerprint = fixed_purchase_payload_hash(normalized_payload)

    warnings = []
    if expected_fine_weight != fine_weight:
        warnings.append(
            (
                "Fine weight does not equal gross weight multiplied by purity "
                f"({expected_fine_weight}). Confirm business policy before posting."
            )
        )

    return {
        "event_type": "fixed_purchase",
        "status": "warning" if warnings else "valid",
        "idempotency_key_preview": fingerprint[:16].upper(),
        "payload_hash": fingerprint,
        "business_facts": {
            "source_reference": cleaned_data["source_reference"].strip(),
            "purchase_date": cleaned_data["purchase_date"],
            "supplier_account": str(cleaned_data["supplier_account"]),
            "commodity": str(cleaned_data["commodity"]),
            "gross_weight": gross_weight,
            "purity": purity,
            "fine_weight": fine_weight,
            "rate": rate,
            "money_amount": money_amount,
            "currency": cleaned_data["currency"],
            "narration": cleaned_data.get("narration") or "",
        },
        "accounting_impact": {
            "creates_financial_posting": True,
            "currency": cleaned_data["currency"],
            "debits": [
                {
                    "ledger": str(cleaned_data["inventory_ledger"]),
                    "amount": money_amount,
                    "currency": cleaned_data["currency"],
                }
            ],
            "credits": [
                {
                    "ledger": str(cleaned_data["payable_ledger"]),
                    "account": str(cleaned_data["supplier_account"]),
                    "amount": money_amount,
                    "currency": cleaned_data["currency"],
                }
            ],
        },
        "commodity_impact": {
            "creates_commodity_movement": True,
            "movement_type": "PURCHASE_RECEIPT",
            "fixed_status": "FIXED",
            "metal": cleaned_data["commodity"].code,
            "gross_weight": gross_weight,
            "purity": purity,
            "fine_weight": fine_weight,
            "from_account": str(cleaned_data["from_commodity_account"]),
            "to_account": str(cleaned_data["to_commodity_account"]),
            "rate": rate,
            "valuation_currency": cleaned_data["currency"],
            "valuation_amount": money_amount,
        },
        "exposure_impact": {
            "creates_exposure": False,
            "side": "",
            "open_fine_weight": Decimal("0.000"),
        },
        "inventory_impact": {
            "status": "deferred",
            "message": "Inventory lot/costing integration is not in this MVP slice.",
        },
        "warnings": warnings,
        "errors": {},
    }


def build_unfixed_purchase_preview(cleaned_data: dict) -> dict:
    normalized_payload = build_unfixed_purchase_normalized_payload(cleaned_data)
    fine_weight = cleaned_data["fine_weight"].quantize(Decimal("0.001"))
    gross_weight = cleaned_data["gross_weight"].quantize(Decimal("0.001"))
    purity = cleaned_data["purity"].quantize(Decimal("0.000001"))
    last_valuation_rate = cleaned_data.get("last_valuation_rate")
    if last_valuation_rate is not None:
        last_valuation_rate = last_valuation_rate.quantize(Decimal("0.0001"))
    last_valuation_amount = (
        (fine_weight * last_valuation_rate).quantize(Decimal("0.01"))
        if last_valuation_rate is not None
        else None
    )
    expected_fine_weight = (gross_weight * purity).quantize(Decimal("0.001"))

    fingerprint = unfixed_purchase_payload_hash(normalized_payload)

    warnings = []
    if expected_fine_weight != fine_weight:
        warnings.append(
            (
                "Fine weight does not equal gross weight multiplied by purity "
                f"({expected_fine_weight}). Confirm business policy before posting."
            )
        )
    if not cleaned_data.get("rate_basis"):
        warnings.append(
            "Rate basis is blank. Capture the market source or fixing terms before final rate fixing."
        )

    return {
        "event_type": "unfixed_purchase",
        "status": "warning" if warnings else "valid",
        "idempotency_key_preview": fingerprint[:16].upper(),
        "payload_hash": fingerprint,
        "business_facts": {
            "source_reference": cleaned_data["source_reference"].strip(),
            "purchase_date": cleaned_data["purchase_date"],
            "party": str(cleaned_data["party"]),
            "commodity": str(cleaned_data["commodity"]),
            "gross_weight": gross_weight,
            "purity": purity,
            "fine_weight": fine_weight,
            "rate_basis": cleaned_data.get("rate_basis") or "",
            "valuation_currency": cleaned_data["valuation_currency"],
            "last_valuation_rate": last_valuation_rate or "",
            "last_valuation_amount": last_valuation_amount or "",
            "narration": cleaned_data.get("narration") or "",
        },
        "accounting_impact": {
            "creates_financial_posting": False,
            "message": (
                "No final monetary payable is created for an unfixed purchase. "
                "Supplier payable is created later through rate fixing."
            ),
            "debits": [],
            "credits": [],
        },
        "commodity_impact": {
            "creates_commodity_movement": True,
            "movement_type": "PURCHASE_RECEIPT",
            "fixed_status": "UNFIXED",
            "metal": cleaned_data["commodity"].code,
            "gross_weight": gross_weight,
            "purity": purity,
            "fine_weight": fine_weight,
            "from_account": str(cleaned_data["from_commodity_account"]),
            "to_account": str(cleaned_data["to_commodity_account"]),
            "valuation_currency": cleaned_data["valuation_currency"],
            "last_valuation_rate": last_valuation_rate or "",
            "last_valuation_amount": last_valuation_amount or "",
        },
        "exposure_impact": {
            "creates_exposure": True,
            "side": "PURCHASE",
            "fixed_status": "UNFIXED",
            "party": str(cleaned_data["party"]),
            "open_fine_weight": fine_weight,
            "rate_basis": cleaned_data.get("rate_basis") or "",
            "valuation_currency": cleaned_data["valuation_currency"],
            "last_valuation_rate": last_valuation_rate or "",
            "last_valuation_amount": last_valuation_amount or "",
        },
        "inventory_impact": {
            "status": "deferred",
            "message": "Inventory lot/costing integration is not in this MVP slice.",
        },
        "warnings": warnings,
        "errors": {},
    }


def build_purchase_rate_fixing_preview(cleaned_data: dict) -> dict:
    normalized_payload = build_purchase_rate_fixing_normalized_payload(cleaned_data)
    exposure = cleaned_data["exposure"]
    fine_weight = cleaned_data["fine_weight"].quantize(Decimal("0.001"))
    rate = cleaned_data["rate"].quantize(Decimal("0.0001"))
    amount = (fine_weight * rate).quantize(Decimal("0.01"))
    remaining_fine_weight = (exposure.open_fine_weight - fine_weight).quantize(
        Decimal("0.001")
    )
    fingerprint = purchase_rate_fixing_payload_hash(normalized_payload)

    warnings = []
    if fine_weight < exposure.open_fine_weight:
        warnings.append(
            (
                "This is a partial rate fixing. The exposure will remain open "
                f"for {remaining_fine_weight} fine weight."
            )
        )

    return {
        "event_type": "purchase_rate_fixing",
        "status": "warning" if warnings else "valid",
        "idempotency_key_preview": fingerprint[:16].upper(),
        "payload_hash": fingerprint,
        "business_facts": {
            "source_reference": cleaned_data["source_reference"].strip(),
            "exposure": str(exposure),
            "exposure_no": exposure.exposure_no,
            "fixing_date": cleaned_data["fixing_date"],
            "party": str(exposure.party),
            "commodity": str(exposure.commodity),
            "open_fine_weight_before": exposure.open_fine_weight,
            "fine_weight": fine_weight,
            "remaining_fine_weight": remaining_fine_weight,
            "rate": rate,
            "amount": amount,
            "currency": cleaned_data["currency"],
            "narration": cleaned_data.get("narration") or "",
        },
        "accounting_impact": {
            "creates_financial_posting": True,
            "currency": cleaned_data["currency"],
            "debits": [
                {
                    "ledger": str(cleaned_data["inventory_ledger"]),
                    "amount": amount,
                    "currency": cleaned_data["currency"],
                }
            ],
            "credits": [
                {
                    "ledger": str(cleaned_data["payable_ledger"]),
                    "account": str(cleaned_data["supplier_account"]),
                    "amount": amount,
                    "currency": cleaned_data["currency"],
                }
            ],
            "message": (
                "Posting will create monetary supplier payable for the fixed "
                "portion only. It will not move metal quantity."
            ),
        },
        "commodity_impact": {
            "creates_commodity_movement": False,
            "message": (
                "Rate fixing does not create a physical metal movement. The "
                "purchase receipt movement already exists from the unfixed purchase."
            ),
        },
        "exposure_impact": {
            "creates_rate_fixing": True,
            "side": "PURCHASE",
            "fixed_status_after": "FIXED"
            if remaining_fine_weight == Decimal("0.000")
            else "PARTIALLY_FIXED",
            "open_fine_weight_before": exposure.open_fine_weight,
            "fixing_fine_weight": fine_weight,
            "open_fine_weight_after": remaining_fine_weight,
            "valuation_amount": amount,
            "valuation_currency": cleaned_data["currency"],
        },
        "inventory_impact": {
            "status": "deferred",
            "message": "Inventory costing adjustment policy is not in this MVP UI slice.",
        },
        "warnings": warnings,
        "errors": {},
    }


def build_sale_rate_fixing_preview(cleaned_data: dict) -> dict:
    normalized_payload = build_sale_rate_fixing_normalized_payload(cleaned_data)
    exposure = cleaned_data["exposure"]
    fine_weight = cleaned_data["fine_weight"].quantize(Decimal("0.001"))
    rate = cleaned_data["rate"].quantize(Decimal("0.0001"))
    amount = (fine_weight * rate).quantize(Decimal("0.01"))
    remaining_fine_weight = (exposure.open_fine_weight - fine_weight).quantize(
        Decimal("0.001")
    )
    fingerprint = sale_rate_fixing_payload_hash(normalized_payload)

    warnings = []
    if fine_weight < exposure.open_fine_weight:
        warnings.append(
            (
                "This is a partial sale rate fixing. The exposure will remain "
                f"open for {remaining_fine_weight} fine weight."
            )
        )

    return {
        "event_type": "sale_rate_fixing",
        "status": "warning" if warnings else "valid",
        "idempotency_key_preview": fingerprint[:16].upper(),
        "payload_hash": fingerprint,
        "business_facts": {
            "source_reference": cleaned_data["source_reference"].strip(),
            "exposure": str(exposure),
            "exposure_no": exposure.exposure_no,
            "fixing_date": cleaned_data["fixing_date"],
            "party": str(exposure.party),
            "commodity": str(exposure.commodity),
            "open_fine_weight_before": exposure.open_fine_weight,
            "fine_weight": fine_weight,
            "remaining_fine_weight": remaining_fine_weight,
            "rate": rate,
            "amount": amount,
            "currency": cleaned_data["currency"],
            "narration": cleaned_data.get("narration") or "",
        },
        "accounting_impact": {
            "creates_financial_posting": True,
            "currency": cleaned_data["currency"],
            "debits": [
                {
                    "ledger": str(cleaned_data["receivable_ledger"]),
                    "account": str(cleaned_data["customer_account"]),
                    "amount": amount,
                    "currency": cleaned_data["currency"],
                }
            ],
            "credits": [
                {
                    "ledger": str(cleaned_data["revenue_ledger"]),
                    "amount": amount,
                    "currency": cleaned_data["currency"],
                }
            ],
            "message": (
                "Posting will create monetary customer receivable and revenue "
                "for the fixed sale portion only. It will not move metal quantity."
            ),
        },
        "commodity_impact": {
            "creates_commodity_movement": False,
            "message": (
                "Rate fixing does not create a physical metal movement. The "
                "sale issue movement already exists from the unfixed sale."
            ),
        },
        "exposure_impact": {
            "creates_rate_fixing": True,
            "side": "SALE",
            "fixed_status_after": "FIXED"
            if remaining_fine_weight == Decimal("0.000")
            else "PARTIALLY_FIXED",
            "open_fine_weight_before": exposure.open_fine_weight,
            "fixing_fine_weight": fine_weight,
            "open_fine_weight_after": remaining_fine_weight,
            "valuation_amount": amount,
            "valuation_currency": cleaned_data["currency"],
        },
        "inventory_impact": {
            "status": "deferred",
            "message": "COGS and inventory costing policy is not in this MVP UI slice.",
        },
        "warnings": warnings,
        "errors": {},
    }


def build_monetary_settlement_preview(cleaned_data: dict) -> dict:
    normalized_payload = build_monetary_settlement_normalized_payload(cleaned_data)
    money_amount = cleaned_data["money_amount"].quantize(Decimal("0.01"))
    fingerprint = monetary_settlement_payload_hash(normalized_payload)
    is_receipt = normalized_payload["settlement_type"] == "CUSTOMER_RECEIPT"
    settlement_label = (
        "Customer receipt" if is_receipt else "Supplier payment"
    )

    if is_receipt:
        debits = [
            {
                "ledger": str(cleaned_data["cash_or_bank_ledger"]),
                "account": "",
                "amount": money_amount,
                "currency": cleaned_data["currency"],
            }
        ]
        credits = [
            {
                "ledger": str(cleaned_data["counterparty_ledger"]),
                "account": str(cleaned_data["party_account"]),
                "amount": money_amount,
                "currency": cleaned_data["currency"],
            }
        ]
        message = (
            "Posting will debit cash/bank and credit customer receivable. "
            "It is financial settlement only and does not affect commodity balances."
        )
    else:
        debits = [
            {
                "ledger": str(cleaned_data["counterparty_ledger"]),
                "account": str(cleaned_data["party_account"]),
                "amount": money_amount,
                "currency": cleaned_data["currency"],
            }
        ]
        credits = [
            {
                "ledger": str(cleaned_data["cash_or_bank_ledger"]),
                "account": "",
                "amount": money_amount,
                "currency": cleaned_data["currency"],
            }
        ]
        message = (
            "Posting will debit supplier payable and credit cash/bank. "
            "It is financial settlement only and does not affect commodity balances."
        )

    return {
        "event_type": "monetary_settlement",
        "status": "valid",
        "idempotency_key_preview": fingerprint[:16].upper(),
        "payload_hash": fingerprint,
        "business_facts": {
            "settlement_type": normalized_payload["settlement_type"],
            "settlement_label": settlement_label,
            "source_reference": normalized_payload["source_reference"],
            "event_date": cleaned_data["event_date"],
            "party_account": str(cleaned_data["party_account"]),
            "cash_or_bank_ledger": str(cleaned_data["cash_or_bank_ledger"]),
            "counterparty_ledger": str(cleaned_data["counterparty_ledger"]),
            "money_amount": money_amount,
            "currency": cleaned_data["currency"],
            "payment_method": cleaned_data["payment_method"],
            "reference_number": normalized_payload["reference_number"],
            "narration": cleaned_data.get("narration") or "",
        },
        "accounting_impact": {
            "creates_financial_posting": True,
            "currency": cleaned_data["currency"],
            "debits": debits,
            "credits": credits,
            "message": message,
        },
        "payment_impact": {
            "creates_payment_voucher": True,
            "direction": "RECEIPT" if is_receipt else "PAYMENT",
            "method": cleaned_data["payment_method"],
            "reference_number": normalized_payload["reference_number"],
            "amount": money_amount,
            "currency": cleaned_data["currency"],
            "message": (
                "Future confirm will create a PaymentVoucher and posted accounting voucher. "
                "Preview stores only this draft."
            ),
        },
        "commodity_impact": {
            "creates_commodity_movement": False,
            "message": "Normal monetary receipt/payment creates no commodity movement, exposure, or rate fixing.",
        },
        "warnings": [],
        "errors": {},
    }


def build_fixed_sale_preview(cleaned_data: dict) -> dict:
    normalized_payload = build_fixed_sale_normalized_payload(cleaned_data)
    money_amount = cleaned_data["money_amount"].quantize(Decimal("0.01"))
    fine_weight = cleaned_data["fine_weight"].quantize(Decimal("0.001"))
    gross_weight = cleaned_data["gross_weight"].quantize(Decimal("0.001"))
    purity = cleaned_data["purity"].quantize(Decimal("0.000001"))
    rate = (money_amount / fine_weight).quantize(Decimal("0.0001"))
    expected_fine_weight = (gross_weight * purity).quantize(Decimal("0.001"))

    fingerprint = fixed_sale_payload_hash(normalized_payload)

    warnings = []
    if expected_fine_weight != fine_weight:
        warnings.append(
            (
                "Fine weight does not equal gross weight multiplied by purity "
                f"({expected_fine_weight}). Confirm business policy before posting."
            )
        )

    return {
        "event_type": "fixed_sale",
        "status": "warning" if warnings else "valid",
        "idempotency_key_preview": fingerprint[:16].upper(),
        "payload_hash": fingerprint,
        "business_facts": {
            "source_reference": cleaned_data["source_reference"].strip(),
            "sale_date": cleaned_data["sale_date"],
            "customer_account": str(cleaned_data["customer_account"]),
            "commodity": str(cleaned_data["commodity"]),
            "gross_weight": gross_weight,
            "purity": purity,
            "fine_weight": fine_weight,
            "rate": rate,
            "money_amount": money_amount,
            "currency": cleaned_data["currency"],
            "narration": cleaned_data.get("narration") or "",
        },
        "accounting_impact": {
            "creates_financial_posting": True,
            "currency": cleaned_data["currency"],
            "debits": [
                {
                    "ledger": str(cleaned_data["receivable_ledger"]),
                    "account": str(cleaned_data["customer_account"]),
                    "amount": money_amount,
                    "currency": cleaned_data["currency"],
                }
            ],
            "credits": [
                {
                    "ledger": str(cleaned_data["revenue_ledger"]),
                    "amount": money_amount,
                    "currency": cleaned_data["currency"],
                }
            ],
        },
        "commodity_impact": {
            "creates_commodity_movement": True,
            "movement_type": "SALE_ISSUE",
            "fixed_status": "FIXED",
            "metal": cleaned_data["commodity"].code,
            "gross_weight": gross_weight,
            "purity": purity,
            "fine_weight": fine_weight,
            "from_account": str(cleaned_data["from_commodity_account"]),
            "to_account": "External customer / delivered out",
            "rate": rate,
            "valuation_currency": cleaned_data["currency"],
            "valuation_amount": money_amount,
        },
        "exposure_impact": {
            "creates_exposure": False,
            "side": "",
            "open_fine_weight": Decimal("0.000"),
        },
        "inventory_impact": {
            "status": "deferred",
            "message": "Inventory lot/costing and COGS integration is not in this MVP slice.",
        },
        "warnings": warnings,
        "errors": {},
    }


def build_unfixed_sale_preview(cleaned_data: dict) -> dict:
    normalized_payload = build_unfixed_sale_normalized_payload(cleaned_data)
    fine_weight = cleaned_data["fine_weight"].quantize(Decimal("0.001"))
    gross_weight = cleaned_data["gross_weight"].quantize(Decimal("0.001"))
    purity = cleaned_data["purity"].quantize(Decimal("0.000001"))
    last_valuation_rate = cleaned_data.get("last_valuation_rate")
    if last_valuation_rate is not None:
        last_valuation_rate = last_valuation_rate.quantize(Decimal("0.0001"))
    last_valuation_amount = (
        (fine_weight * last_valuation_rate).quantize(Decimal("0.01"))
        if last_valuation_rate is not None
        else None
    )
    expected_fine_weight = (gross_weight * purity).quantize(Decimal("0.001"))

    fingerprint = unfixed_sale_payload_hash(normalized_payload)

    warnings = []
    if expected_fine_weight != fine_weight:
        warnings.append(
            (
                "Fine weight does not equal gross weight multiplied by purity "
                f"({expected_fine_weight}). Confirm business policy before posting."
            )
        )
    if not cleaned_data.get("rate_basis"):
        warnings.append(
            "Rate basis is blank. Capture the market source or fixing terms before final rate fixing."
        )

    return {
        "event_type": "unfixed_sale",
        "status": "warning" if warnings else "valid",
        "idempotency_key_preview": fingerprint[:16].upper(),
        "payload_hash": fingerprint,
        "business_facts": {
            "source_reference": cleaned_data["source_reference"].strip(),
            "sale_date": cleaned_data["sale_date"],
            "party": str(cleaned_data["party"]),
            "commodity": str(cleaned_data["commodity"]),
            "gross_weight": gross_weight,
            "purity": purity,
            "fine_weight": fine_weight,
            "rate_basis": cleaned_data.get("rate_basis") or "",
            "valuation_currency": cleaned_data["valuation_currency"],
            "last_valuation_rate": last_valuation_rate or "",
            "last_valuation_amount": last_valuation_amount or "",
            "narration": cleaned_data.get("narration") or "",
        },
        "accounting_impact": {
            "creates_financial_posting": False,
            "message": (
                "No final monetary receivable or revenue is created for an unfixed sale. "
                "Customer receivable and revenue are created later through rate fixing."
            ),
            "debits": [],
            "credits": [],
        },
        "commodity_impact": {
            "creates_commodity_movement": True,
            "movement_type": "SALE_ISSUE",
            "fixed_status": "UNFIXED",
            "metal": cleaned_data["commodity"].code,
            "gross_weight": gross_weight,
            "purity": purity,
            "fine_weight": fine_weight,
            "from_account": str(cleaned_data["from_commodity_account"]),
            "to_account": "External customer / delivered out",
            "valuation_currency": cleaned_data["valuation_currency"],
            "last_valuation_rate": last_valuation_rate or "",
            "last_valuation_amount": last_valuation_amount or "",
        },
        "exposure_impact": {
            "creates_exposure": True,
            "side": "SALE",
            "fixed_status": "UNFIXED",
            "party": str(cleaned_data["party"]),
            "open_fine_weight": fine_weight,
            "rate_basis": cleaned_data.get("rate_basis") or "",
            "valuation_currency": cleaned_data["valuation_currency"],
            "last_valuation_rate": last_valuation_rate or "",
            "last_valuation_amount": last_valuation_amount or "",
        },
        "inventory_impact": {
            "status": "deferred",
            "message": "Inventory lot/costing and COGS integration is not in this MVP slice.",
        },
        "warnings": warnings,
        "errors": {},
    }


def build_karigar_movement_preview(cleaned_data: dict) -> dict:
    normalized_payload = build_karigar_movement_normalized_payload(cleaned_data)
    fine_weight = cleaned_data["fine_weight"].quantize(Decimal("0.001"))
    gross_weight = cleaned_data["gross_weight"].quantize(Decimal("0.001"))
    purity = cleaned_data["purity"].quantize(Decimal("0.000001"))
    expected_fine_weight = (gross_weight * purity).quantize(Decimal("0.001"))
    is_issue = normalized_payload["movement_type"] == "KARIGAR_ISSUE"
    movement_label = "Karigar issue" if is_issue else "Karigar receipt"
    movement_type = "KARIGAR_ISSUE" if is_issue else "KARIGAR_RECEIPT"
    fingerprint = karigar_movement_payload_hash(normalized_payload)

    warnings = []
    if expected_fine_weight != fine_weight:
        warnings.append(
            (
                "Fine weight does not equal gross weight multiplied by purity "
                f"({expected_fine_weight}). Confirm business policy before posting."
            )
        )

    return {
        "event_type": "karigar_movement",
        "status": "warning" if warnings else "valid",
        "idempotency_key_preview": fingerprint[:16].upper(),
        "payload_hash": fingerprint,
        "business_facts": {
            "movement_type": movement_type,
            "movement_label": movement_label,
            "source_reference": normalized_payload["source_reference"],
            "event_date": cleaned_data["event_date"],
            "karigar": str(cleaned_data["karigar"]),
            "commodity": str(cleaned_data["commodity"]),
            "gross_weight": gross_weight,
            "purity": purity,
            "fine_weight": fine_weight,
            "narration": cleaned_data.get("narration") or "",
        },
        "accounting_impact": {
            "creates_financial_posting": False,
            "debits": [],
            "credits": [],
            "message": (
                "Karigar custody movement is commodity-only in this MVP slice. "
                "It creates no journal entry, ledger transaction, account transaction, "
                "payment voucher, payable, receivable, revenue, or expense."
            ),
        },
        "commodity_impact": {
            "creates_commodity_movement": True,
            "movement_type": movement_type,
            "fixed_status": "NOT_APPLICABLE",
            "metal": cleaned_data["commodity"].code,
            "gross_weight": gross_weight,
            "purity": purity,
            "fine_weight": fine_weight,
            "from_account": str(cleaned_data["from_commodity_account"]),
            "to_account": str(cleaned_data["to_commodity_account"]),
        },
        "exposure_impact": {
            "creates_exposure": False,
            "side": "",
            "open_fine_weight": Decimal("0.000"),
            "message": "Karigar custody movement does not create fixed/unfixed exposure.",
        },
        "inventory_impact": {
            "status": "deferred",
            "message": (
                "Inventory lot, finished-goods transformation, wastage, and making-charge "
                "accounting are deferred. This preview tracks custody quantity only."
            ),
        },
        "warnings": warnings,
        "errors": {},
    }


def build_fixed_purchase_normalized_payload(cleaned_data: dict) -> dict:
    return {
        "event_type": "fixed_purchase",
        "source_reference": cleaned_data["source_reference"].strip(),
        "purchase_date": cleaned_data["purchase_date"].isoformat(),
        "supplier_account": cleaned_data["supplier_account"].pk,
        "inventory_ledger": cleaned_data["inventory_ledger"].pk,
        "payable_ledger": cleaned_data["payable_ledger"].pk,
        "commodity": cleaned_data["commodity"].pk,
        "gross_weight": str(cleaned_data["gross_weight"].quantize(Decimal("0.001"))),
        "purity": str(cleaned_data["purity"].quantize(Decimal("0.000001"))),
        "fine_weight": str(cleaned_data["fine_weight"].quantize(Decimal("0.001"))),
        "from_commodity_account": cleaned_data["from_commodity_account"].pk,
        "to_commodity_account": cleaned_data["to_commodity_account"].pk,
        "money_amount": str(cleaned_data["money_amount"].quantize(Decimal("0.01"))),
        "currency": cleaned_data["currency"],
        "narration": cleaned_data.get("narration") or "",
    }


def build_unfixed_purchase_normalized_payload(cleaned_data: dict) -> dict:
    last_valuation_rate = cleaned_data.get("last_valuation_rate")
    return {
        "event_type": "unfixed_purchase",
        "source_reference": cleaned_data["source_reference"].strip(),
        "purchase_date": cleaned_data["purchase_date"].isoformat(),
        "party": cleaned_data["party"].pk,
        "commodity": cleaned_data["commodity"].pk,
        "gross_weight": str(cleaned_data["gross_weight"].quantize(Decimal("0.001"))),
        "purity": str(cleaned_data["purity"].quantize(Decimal("0.000001"))),
        "fine_weight": str(cleaned_data["fine_weight"].quantize(Decimal("0.001"))),
        "from_commodity_account": cleaned_data["from_commodity_account"].pk,
        "to_commodity_account": cleaned_data["to_commodity_account"].pk,
        "rate_basis": cleaned_data.get("rate_basis") or "",
        "valuation_currency": cleaned_data["valuation_currency"],
        "last_valuation_rate": str(last_valuation_rate.quantize(Decimal("0.0001")))
        if last_valuation_rate is not None
        else "",
        "narration": cleaned_data.get("narration") or "",
    }


def build_purchase_rate_fixing_normalized_payload(cleaned_data: dict) -> dict:
    return {
        "event_type": "purchase_rate_fixing",
        "source_reference": cleaned_data["source_reference"].strip(),
        "exposure": cleaned_data["exposure"].pk,
        "fixing_date": cleaned_data["fixing_date"].isoformat(),
        "fine_weight": str(cleaned_data["fine_weight"].quantize(Decimal("0.001"))),
        "rate": str(cleaned_data["rate"].quantize(Decimal("0.0001"))),
        "supplier_account": cleaned_data["supplier_account"].pk,
        "inventory_ledger": cleaned_data["inventory_ledger"].pk,
        "payable_ledger": cleaned_data["payable_ledger"].pk,
        "currency": cleaned_data["currency"],
        "narration": cleaned_data.get("narration") or "",
    }


def build_sale_rate_fixing_normalized_payload(cleaned_data: dict) -> dict:
    return {
        "event_type": "sale_rate_fixing",
        "source_reference": cleaned_data["source_reference"].strip(),
        "exposure": cleaned_data["exposure"].pk,
        "fixing_date": cleaned_data["fixing_date"].isoformat(),
        "fine_weight": str(cleaned_data["fine_weight"].quantize(Decimal("0.001"))),
        "rate": str(cleaned_data["rate"].quantize(Decimal("0.0001"))),
        "customer_account": cleaned_data["customer_account"].pk,
        "receivable_ledger": cleaned_data["receivable_ledger"].pk,
        "revenue_ledger": cleaned_data["revenue_ledger"].pk,
        "currency": cleaned_data["currency"],
        "narration": cleaned_data.get("narration") or "",
    }


def build_fixed_sale_normalized_payload(cleaned_data: dict) -> dict:
    return {
        "event_type": "fixed_sale",
        "source_reference": cleaned_data["source_reference"].strip(),
        "sale_date": cleaned_data["sale_date"].isoformat(),
        "customer_account": cleaned_data["customer_account"].pk,
        "receivable_ledger": cleaned_data["receivable_ledger"].pk,
        "revenue_ledger": cleaned_data["revenue_ledger"].pk,
        "commodity": cleaned_data["commodity"].pk,
        "gross_weight": str(cleaned_data["gross_weight"].quantize(Decimal("0.001"))),
        "purity": str(cleaned_data["purity"].quantize(Decimal("0.000001"))),
        "fine_weight": str(cleaned_data["fine_weight"].quantize(Decimal("0.001"))),
        "from_commodity_account": cleaned_data["from_commodity_account"].pk,
        "money_amount": str(cleaned_data["money_amount"].quantize(Decimal("0.01"))),
        "currency": cleaned_data["currency"],
        "narration": cleaned_data.get("narration") or "",
    }


def build_unfixed_sale_normalized_payload(cleaned_data: dict) -> dict:
    last_valuation_rate = cleaned_data.get("last_valuation_rate")
    return {
        "event_type": "unfixed_sale",
        "source_reference": cleaned_data["source_reference"].strip(),
        "sale_date": cleaned_data["sale_date"].isoformat(),
        "party": cleaned_data["party"].pk,
        "commodity": cleaned_data["commodity"].pk,
        "gross_weight": str(cleaned_data["gross_weight"].quantize(Decimal("0.001"))),
        "purity": str(cleaned_data["purity"].quantize(Decimal("0.000001"))),
        "fine_weight": str(cleaned_data["fine_weight"].quantize(Decimal("0.001"))),
        "from_commodity_account": cleaned_data["from_commodity_account"].pk,
        "rate_basis": cleaned_data.get("rate_basis") or "",
        "valuation_currency": cleaned_data["valuation_currency"],
        "last_valuation_rate": str(last_valuation_rate.quantize(Decimal("0.0001")))
        if last_valuation_rate is not None
        else "",
        "narration": cleaned_data.get("narration") or "",
    }


def build_monetary_settlement_normalized_payload(cleaned_data: dict) -> dict:
    return {
        "event_type": "monetary_settlement",
        "settlement_type": cleaned_data["settlement_type"],
        "source_reference": cleaned_data["source_reference"].strip(),
        "event_date": cleaned_data["event_date"].isoformat(),
        "party_account": cleaned_data["party_account"].pk,
        "cash_or_bank_ledger": cleaned_data["cash_or_bank_ledger"].pk,
        "counterparty_ledger": cleaned_data["counterparty_ledger"].pk,
        "money_amount": str(cleaned_data["money_amount"].quantize(Decimal("0.01"))),
        "reference_number": cleaned_data["reference_number"].strip(),
        "currency": cleaned_data["currency"],
        "payment_method": cleaned_data["payment_method"],
        "narration": cleaned_data.get("narration") or "",
    }


def build_karigar_movement_normalized_payload(cleaned_data: dict) -> dict:
    return {
        "event_type": "karigar_movement",
        "movement_type": cleaned_data["movement_type"],
        "source_reference": cleaned_data["source_reference"].strip(),
        "event_date": cleaned_data["event_date"].isoformat(),
        "karigar": cleaned_data["karigar"].pk,
        "commodity": cleaned_data["commodity"].pk,
        "gross_weight": str(cleaned_data["gross_weight"].quantize(Decimal("0.001"))),
        "purity": str(cleaned_data["purity"].quantize(Decimal("0.000001"))),
        "fine_weight": str(cleaned_data["fine_weight"].quantize(Decimal("0.001"))),
        "from_commodity_account": cleaned_data["from_commodity_account"].pk,
        "to_commodity_account": cleaned_data["to_commodity_account"].pk,
        "narration": cleaned_data.get("narration") or "",
    }


def fixed_purchase_payload_hash(normalized_payload: dict) -> str:
    return compute_fingerprint(normalized_payload, FIXED_PURCHASE_PREVIEW_VERSION)


def unfixed_purchase_payload_hash(normalized_payload: dict) -> str:
    return compute_fingerprint(normalized_payload, UNFIXED_PURCHASE_PREVIEW_VERSION)


def purchase_rate_fixing_payload_hash(normalized_payload: dict) -> str:
    return compute_fingerprint(
        normalized_payload,
        PURCHASE_RATE_FIXING_PREVIEW_VERSION,
    )


def sale_rate_fixing_payload_hash(normalized_payload: dict) -> str:
    return compute_fingerprint(
        normalized_payload,
        SALE_RATE_FIXING_PREVIEW_VERSION,
    )


def fixed_sale_payload_hash(normalized_payload: dict) -> str:
    return compute_fingerprint(normalized_payload, FIXED_SALE_PREVIEW_VERSION)


def unfixed_sale_payload_hash(normalized_payload: dict) -> str:
    return compute_fingerprint(normalized_payload, UNFIXED_SALE_PREVIEW_VERSION)


def monetary_settlement_payload_hash(normalized_payload: dict) -> str:
    return compute_fingerprint(
        normalized_payload,
        MONETARY_SETTLEMENT_PREVIEW_VERSION,
    )


def karigar_movement_payload_hash(normalized_payload: dict) -> str:
    return compute_fingerprint(
        normalized_payload,
        KARIGAR_MOVEMENT_PREVIEW_VERSION,
    )


def build_monetary_settlement_posting_readiness(
    draft: BusinessEventDraft,
    *,
    actor=None,
) -> dict:
    """Return a read-only readiness checklist for future settlement posting."""

    payload = draft.normalized_payload or {}
    checks = []

    def add_check(code: str, label: str, passed: bool, detail: str = ""):
        checks.append(
            {
                "code": code,
                "label": label,
                "passed": bool(passed),
                "detail": detail,
            }
        )

    add_check(
        "source_saved",
        "Draft source saved",
        bool(draft.pk and draft.source_reference),
        f"Draft #{draft.pk}" if draft.pk else "Draft must be saved before posting.",
    )
    add_check(
        "previewed",
        "Draft has preview status",
        draft.status == BusinessEventDraft.Status.PREVIEWED,
        draft.get_status_display(),
    )

    expected_hash = monetary_settlement_payload_hash(payload) if payload else ""
    add_check(
        "payload_hash",
        "Payload hash matches preview",
        bool(payload and draft.payload_hash == expected_hash),
        "Economic payload is unchanged."
        if payload and draft.payload_hash == expected_hash
        else "Re-preview the settlement facts before posting.",
    )

    period = AccountingPeriod.objects.get_period_for_date(draft.event_date)
    add_check(
        "open_period",
        "Open accounting period",
        bool(period and period.can_modify_transactions()),
        str(period) if period else "No accounting period contains this event date.",
    )

    add_check(
        "authenticated_actor",
        "Authenticated actor",
        bool(actor and getattr(actor, "is_authenticated", False)),
        str(actor) if actor and getattr(actor, "is_authenticated", False) else "Login required.",
    )

    party_account = _get_payload_object(Account, payload, "party_account")
    cash_or_bank_ledger = _get_payload_object(Ledger, payload, "cash_or_bank_ledger")
    counterparty_ledger = _get_payload_object(Ledger, payload, "counterparty_ledger")
    reference_number = (payload.get("reference_number") or "").strip()

    add_check(
        "party_account",
        "Party account exists",
        bool(party_account),
        str(party_account) if party_account else "Party account is missing.",
    )
    add_check(
        "cash_or_bank_ledger",
        "Cash/bank ledger exists",
        bool(cash_or_bank_ledger),
        str(cash_or_bank_ledger)
        if cash_or_bank_ledger
        else "Cash/bank ledger is missing.",
    )
    add_check(
        "counterparty_ledger",
        "Receivable/payable ledger exists",
        bool(counterparty_ledger),
        str(counterparty_ledger)
        if counterparty_ledger
        else "Counterparty ledger is missing.",
    )
    add_check(
        "reference_number",
        "Settlement reference captured",
        bool(reference_number),
        reference_number if reference_number else "Reference number is required.",
    )

    blockers = [check for check in checks if not check["passed"]]
    return {
        "ready": not blockers,
        "status": "ready" if not blockers else "blocked",
        "checks": checks,
        "blockers": blockers,
    }


def build_karigar_movement_posting_readiness(
    draft: BusinessEventDraft,
    *,
    actor=None,
    include_existing_posting_guard=True,
) -> dict:
    """Return a read-only readiness checklist for future karigar posting."""

    payload = draft.normalized_payload or {}
    checks = []

    def add_check(code: str, label: str, passed: bool, detail: str = ""):
        checks.append(
            {
                "code": code,
                "label": label,
                "passed": bool(passed),
                "detail": detail,
            }
        )

    add_check(
        "source_saved",
        "Draft source saved",
        bool(draft.pk and draft.source_reference),
        f"Draft #{draft.pk}" if draft.pk else "Draft must be saved before posting.",
    )
    add_check(
        "previewed",
        "Draft has preview status",
        draft.status == BusinessEventDraft.Status.PREVIEWED,
        draft.get_status_display(),
    )

    expected_hash = karigar_movement_payload_hash(payload) if payload else ""
    add_check(
        "payload_hash",
        "Payload hash matches preview",
        bool(payload and draft.payload_hash == expected_hash),
        "Economic payload is unchanged."
        if payload and draft.payload_hash == expected_hash
        else "Re-preview the karigar movement facts before posting.",
    )

    period = AccountingPeriod.objects.get_period_for_date(draft.event_date)
    add_check(
        "open_period",
        "Open accounting period",
        bool(period and period.can_modify_transactions()),
        str(period) if period else "No accounting period contains this event date.",
    )

    add_check(
        "authenticated_actor",
        "Authenticated actor",
        bool(actor and getattr(actor, "is_authenticated", False)),
        str(actor) if actor and getattr(actor, "is_authenticated", False) else "Login required.",
    )

    movement_type = payload.get("movement_type")
    karigar = _get_payload_object(Party, payload, "karigar")
    commodity = _get_payload_object(Commodity, payload, "commodity")
    from_account = _get_payload_object(
        CommodityAccount, payload, "from_commodity_account"
    )
    to_account = _get_payload_object(CommodityAccount, payload, "to_commodity_account")

    add_check(
        "karigar_active",
        "Karigar party exists and is active",
        bool(karigar and karigar.status == Party.PartyStatus.ACTIVE),
        str(karigar)
        if karigar and karigar.status == Party.PartyStatus.ACTIVE
        else "Karigar party is missing or not active.",
    )
    add_check(
        "commodity_active",
        "Commodity exists and is active",
        bool(commodity and commodity.is_active),
        str(commodity) if commodity else "Commodity is missing.",
    )
    accounts_match = bool(
        commodity
        and from_account
        and to_account
        and from_account.commodity_id == commodity.pk
        and to_account.commodity_id == commodity.pk
        and from_account.pk != to_account.pk
        and from_account.is_active
        and to_account.is_active
    )
    add_check(
        "commodity_accounts",
        "Commodity accounts are active and match commodity",
        accounts_match,
        "From and to commodity accounts are ready."
        if accounts_match
        else "Commodity accounts are missing, inactive, identical, or mismatched.",
    )

    if movement_type == "KARIGAR_ISSUE":
        custody_ready = bool(
            karigar
            and to_account
            and to_account.purpose == CommodityAccount.Purpose.KARIGAR_CUSTODY
            and to_account.party_id == karigar.pk
        )
        add_check(
            "karigar_custody_direction",
            "Issue destination is selected karigar custody",
            custody_ready,
            "Issue will move metal into karigar custody."
            if custody_ready
            else "Issue destination must be the selected karigar custody account.",
        )
    elif movement_type == "KARIGAR_RECEIPT":
        custody_ready = bool(
            karigar
            and from_account
            and from_account.purpose == CommodityAccount.Purpose.KARIGAR_CUSTODY
            and from_account.party_id == karigar.pk
        )
        add_check(
            "karigar_custody_direction",
            "Receipt source is selected karigar custody",
            custody_ready,
            "Receipt will move metal out of karigar custody."
            if custody_ready
            else "Receipt source must be the selected karigar custody account.",
        )
    else:
        add_check(
            "movement_type",
            "Karigar movement type selected",
            False,
            "Movement type must be issue or receipt.",
        )

    if include_existing_posting_guard:
        has_existing_posting = _has_posted_karigar_voucher(draft)
        add_check(
            "no_existing_posting",
            "No posted karigar voucher for this draft",
            not has_existing_posting,
            "Ready for future first posting."
            if not has_existing_posting
            else "A posted voucher already exists; use reversal/correction instead.",
        )

    blockers = [check for check in checks if not check["passed"]]
    return {
        "ready": not blockers,
        "status": "ready" if not blockers else "blocked",
        "checks": checks,
        "blockers": blockers,
    }


def build_fixed_sale_posting_readiness(
    draft: BusinessEventDraft,
    *,
    actor=None,
    include_existing_posting_guard=True,
) -> dict:
    """Return a read-only readiness checklist for future fixed sale posting."""

    payload = draft.normalized_payload or {}
    checks = []

    def add_check(code: str, label: str, passed: bool, detail: str = ""):
        checks.append(
            {
                "code": code,
                "label": label,
                "passed": bool(passed),
                "detail": detail,
            }
        )

    add_check(
        "source_saved",
        "Draft source saved",
        bool(draft.pk and draft.source_reference),
        f"Draft #{draft.pk}" if draft.pk else "Draft must be saved before posting.",
    )
    add_check(
        "previewed",
        "Draft has preview status",
        draft.status == BusinessEventDraft.Status.PREVIEWED,
        draft.get_status_display(),
    )

    expected_hash = fixed_sale_payload_hash(payload) if payload else ""
    add_check(
        "payload_hash",
        "Payload hash matches preview",
        bool(payload and draft.payload_hash == expected_hash),
        "Economic payload is unchanged."
        if payload and draft.payload_hash == expected_hash
        else "Re-preview the sale facts before posting.",
    )

    period = AccountingPeriod.objects.get_period_for_date(draft.event_date)
    add_check(
        "open_period",
        "Open accounting period",
        bool(period and period.can_modify_transactions()),
        str(period) if period else "No accounting period contains this event date.",
    )

    add_check(
        "authenticated_actor",
        "Authenticated actor",
        bool(actor and getattr(actor, "is_authenticated", False)),
        str(actor) if actor and getattr(actor, "is_authenticated", False) else "Login required.",
    )

    customer_account = _get_payload_object(Account, payload, "customer_account")
    receivable_ledger = _get_payload_object(Ledger, payload, "receivable_ledger")
    revenue_ledger = _get_payload_object(Ledger, payload, "revenue_ledger")
    commodity = _get_payload_object(Commodity, payload, "commodity")
    from_account = _get_payload_object(
        CommodityAccount, payload, "from_commodity_account"
    )

    add_check(
        "customer_account",
        "Customer account exists",
        bool(customer_account),
        str(customer_account) if customer_account else "Customer account is missing.",
    )
    add_check(
        "financial_ledgers",
        "Financial ledgers exist",
        bool(receivable_ledger and revenue_ledger),
        "Receivable and revenue ledgers are available."
        if receivable_ledger and revenue_ledger
        else "Receivable or revenue ledger is missing.",
    )
    add_check(
        "commodity_active",
        "Commodity exists and is active",
        bool(commodity and commodity.is_active),
        str(commodity) if commodity else "Commodity is missing.",
    )
    commodity_account_ready = bool(
        commodity
        and from_account
        and from_account.commodity_id == commodity.pk
        and from_account.is_active
    )
    add_check(
        "commodity_account",
        "Source commodity account is active and matches commodity",
        commodity_account_ready,
        str(from_account)
        if commodity_account_ready
        else "Source commodity account is missing, inactive, or mismatched.",
    )

    if include_existing_posting_guard:
        has_existing_posting = _has_posted_fixed_sale_voucher(draft)
        add_check(
            "no_existing_posting",
            "No posted fixed-sale voucher for this draft",
            not has_existing_posting,
            "Ready for future first posting."
            if not has_existing_posting
            else "A posted voucher already exists; use reversal/correction instead.",
        )

    blockers = [check for check in checks if not check["passed"]]
    return {
        "ready": not blockers,
        "status": "ready" if not blockers else "blocked",
        "checks": checks,
        "blockers": blockers,
    }


def build_purchase_rate_fixing_readiness(cleaned_data: dict, *, actor=None) -> dict:
    checks = []

    def add_check(code: str, label: str, passed: bool, detail: str = ""):
        checks.append(
            {
                "code": code,
                "label": label,
                "passed": bool(passed),
                "detail": detail,
            }
        )

    exposure = cleaned_data.get("exposure")
    fixing_date = cleaned_data.get("fixing_date")
    fine_weight = cleaned_data.get("fine_weight")
    supplier_account = cleaned_data.get("supplier_account")
    inventory_ledger = cleaned_data.get("inventory_ledger")
    payable_ledger = cleaned_data.get("payable_ledger")

    add_check(
        "authenticated_actor",
        "Authenticated actor",
        bool(actor and getattr(actor, "is_authenticated", False)),
        str(actor) if actor and getattr(actor, "is_authenticated", False) else "Login required.",
    )
    period = AccountingPeriod.objects.get_period_for_date(fixing_date) if fixing_date else None
    add_check(
        "open_period",
        "Open accounting period",
        bool(period and period.can_modify_transactions()),
        str(period) if period else "No accounting period contains this fixing date.",
    )
    exposure_ready = bool(
        exposure
        and exposure.side == "PURCHASE"
        and exposure.status in {"OPEN", "PARTIALLY_FIXED"}
        and exposure.fixed_status in {"UNFIXED", "PARTIALLY_FIXED"}
        and exposure.open_fine_weight > Decimal("0.000")
    )
    add_check(
        "open_purchase_exposure",
        "Open purchase exposure",
        exposure_ready,
        str(exposure) if exposure_ready else "Exposure is missing or not open for purchase fixing.",
    )
    add_check(
        "fixing_weight",
        "Fixing weight is within open exposure",
        bool(exposure and fine_weight and fine_weight > 0 and fine_weight <= exposure.open_fine_weight),
        f"{fine_weight} of {exposure.open_fine_weight}"
        if exposure and fine_weight
        else "Enter a positive fixing fine weight.",
    )
    account_party_matches = bool(
        exposure
        and supplier_account
        and (
            not supplier_account.party_id
            or supplier_account.party_id == exposure.party_id
        )
    )
    add_check(
        "supplier_account",
        "Supplier monetary account is compatible",
        account_party_matches,
        str(supplier_account)
        if account_party_matches
        else "Supplier account is missing or linked to a different party.",
    )
    add_check(
        "financial_ledgers",
        "Financial ledgers exist",
        bool(inventory_ledger and payable_ledger),
        "Inventory/valuation and payable ledgers are available."
        if inventory_ledger and payable_ledger
        else "Inventory/valuation or payable ledger is missing.",
    )

    blockers = [check for check in checks if not check["passed"]]
    return {
        "ready": not blockers,
        "status": "ready" if not blockers else "blocked",
        "checks": checks,
        "blockers": blockers,
    }


def build_purchase_rate_fixing_posting_readiness(
    draft: BusinessEventDraft,
    *,
    actor=None,
) -> dict:
    """Return a read-only readiness checklist for future purchase rate fixing."""

    payload = draft.normalized_payload or {}
    checks = []

    def add_check(code: str, label: str, passed: bool, detail: str = ""):
        checks.append(
            {
                "code": code,
                "label": label,
                "passed": bool(passed),
                "detail": detail,
            }
        )

    add_check(
        "source_saved",
        "Draft source saved",
        bool(draft.pk and draft.source_reference),
        f"Draft #{draft.pk}" if draft.pk else "Draft must be saved before posting.",
    )
    add_check(
        "previewed",
        "Draft has preview status",
        draft.status == BusinessEventDraft.Status.PREVIEWED,
        draft.get_status_display(),
    )

    expected_hash = purchase_rate_fixing_payload_hash(payload) if payload else ""
    add_check(
        "payload_hash",
        "Payload hash matches preview",
        bool(payload and draft.payload_hash == expected_hash),
        "Economic payload is unchanged."
        if payload and draft.payload_hash == expected_hash
        else "Re-preview the rate fixing facts before posting.",
    )

    period = AccountingPeriod.objects.get_period_for_date(draft.event_date)
    add_check(
        "open_period",
        "Open accounting period",
        bool(period and period.can_modify_transactions()),
        str(period) if period else "No accounting period contains this fixing date.",
    )

    add_check(
        "authenticated_actor",
        "Authenticated actor",
        bool(actor and getattr(actor, "is_authenticated", False)),
        str(actor) if actor and getattr(actor, "is_authenticated", False) else "Login required.",
    )

    exposure = _get_payload_object(ExposureLine, payload, "exposure")
    supplier_account = _get_payload_object(Account, payload, "supplier_account")
    inventory_ledger = _get_payload_object(Ledger, payload, "inventory_ledger")
    payable_ledger = _get_payload_object(Ledger, payload, "payable_ledger")
    fine_weight = Decimal(payload.get("fine_weight") or "0")

    exposure_ready = bool(
        exposure
        and exposure.side == "PURCHASE"
        and exposure.status in {"OPEN", "PARTIALLY_FIXED"}
        and exposure.fixed_status in {"UNFIXED", "PARTIALLY_FIXED"}
        and exposure.open_fine_weight > Decimal("0.000")
    )
    add_check(
        "open_purchase_exposure",
        "Open purchase exposure",
        exposure_ready,
        str(exposure) if exposure_ready else "Exposure is missing or not open for purchase fixing.",
    )
    add_check(
        "fixing_weight",
        "Fixing weight is within open exposure",
        bool(exposure and fine_weight > 0 and fine_weight <= exposure.open_fine_weight),
        f"{fine_weight} of {exposure.open_fine_weight}"
        if exposure
        else "Enter a positive fixing fine weight.",
    )
    account_party_matches = bool(
        exposure
        and supplier_account
        and (
            not supplier_account.party_id
            or supplier_account.party_id == exposure.party_id
        )
    )
    add_check(
        "supplier_account",
        "Supplier monetary account is compatible",
        account_party_matches,
        str(supplier_account)
        if account_party_matches
        else "Supplier account is missing or linked to a different party.",
    )
    add_check(
        "financial_ledgers",
        "Financial ledgers exist",
        bool(inventory_ledger and payable_ledger),
        "Inventory/valuation and payable ledgers are available."
        if inventory_ledger and payable_ledger
        else "Inventory/valuation or payable ledger is missing.",
    )

    blockers = [check for check in checks if not check["passed"]]
    return {
        "ready": not blockers,
        "status": "ready" if not blockers else "blocked",
        "checks": checks,
        "blockers": blockers,
    }


def build_sale_rate_fixing_readiness(cleaned_data: dict, *, actor=None) -> dict:
    checks = []

    def add_check(code: str, label: str, passed: bool, detail: str = ""):
        checks.append(
            {
                "code": code,
                "label": label,
                "passed": bool(passed),
                "detail": detail,
            }
        )

    exposure = cleaned_data.get("exposure")
    fixing_date = cleaned_data.get("fixing_date")
    fine_weight = cleaned_data.get("fine_weight")
    customer_account = cleaned_data.get("customer_account")
    receivable_ledger = cleaned_data.get("receivable_ledger")
    revenue_ledger = cleaned_data.get("revenue_ledger")

    add_check(
        "authenticated_actor",
        "Authenticated actor",
        bool(actor and getattr(actor, "is_authenticated", False)),
        str(actor) if actor and getattr(actor, "is_authenticated", False) else "Login required.",
    )
    period = AccountingPeriod.objects.get_period_for_date(fixing_date) if fixing_date else None
    add_check(
        "open_period",
        "Open accounting period",
        bool(period and period.can_modify_transactions()),
        str(period) if period else "No accounting period contains this fixing date.",
    )
    exposure_ready = bool(
        exposure
        and exposure.side == "SALE"
        and exposure.status in {"OPEN", "PARTIALLY_FIXED"}
        and exposure.fixed_status in {"UNFIXED", "PARTIALLY_FIXED"}
        and exposure.open_fine_weight > Decimal("0.000")
    )
    add_check(
        "open_sale_exposure",
        "Open sale exposure",
        exposure_ready,
        str(exposure) if exposure_ready else "Exposure is missing or not open for sale fixing.",
    )
    add_check(
        "fixing_weight",
        "Fixing weight is within open exposure",
        bool(exposure and fine_weight and fine_weight > 0 and fine_weight <= exposure.open_fine_weight),
        f"{fine_weight} of {exposure.open_fine_weight}"
        if exposure and fine_weight
        else "Enter a positive fixing fine weight.",
    )
    account_party_matches = bool(
        exposure
        and customer_account
        and (
            not customer_account.party_id
            or customer_account.party_id == exposure.party_id
        )
    )
    add_check(
        "customer_account",
        "Customer monetary account is compatible",
        account_party_matches,
        str(customer_account)
        if account_party_matches
        else "Customer account is missing or linked to a different party.",
    )
    add_check(
        "financial_ledgers",
        "Financial ledgers exist",
        bool(receivable_ledger and revenue_ledger),
        "Receivable and revenue ledgers are available."
        if receivable_ledger and revenue_ledger
        else "Receivable or revenue ledger is missing.",
    )

    blockers = [check for check in checks if not check["passed"]]
    return {
        "ready": not blockers,
        "status": "ready" if not blockers else "blocked",
        "checks": checks,
        "blockers": blockers,
    }


def build_sale_rate_fixing_posting_readiness(
    draft: BusinessEventDraft,
    *,
    actor=None,
) -> dict:
    """Return a read-only readiness checklist for future sale rate fixing."""

    payload = draft.normalized_payload or {}
    checks = []

    def add_check(code: str, label: str, passed: bool, detail: str = ""):
        checks.append(
            {
                "code": code,
                "label": label,
                "passed": bool(passed),
                "detail": detail,
            }
        )

    add_check(
        "source_saved",
        "Draft source saved",
        bool(draft.pk and draft.source_reference),
        f"Draft #{draft.pk}" if draft.pk else "Draft must be saved before posting.",
    )
    add_check(
        "previewed",
        "Draft has preview status",
        draft.status == BusinessEventDraft.Status.PREVIEWED,
        draft.get_status_display(),
    )

    expected_hash = sale_rate_fixing_payload_hash(payload) if payload else ""
    add_check(
        "payload_hash",
        "Payload hash matches preview",
        bool(payload and draft.payload_hash == expected_hash),
        "Economic payload is unchanged."
        if payload and draft.payload_hash == expected_hash
        else "Re-preview the rate fixing facts before posting.",
    )

    period = AccountingPeriod.objects.get_period_for_date(draft.event_date)
    add_check(
        "open_period",
        "Open accounting period",
        bool(period and period.can_modify_transactions()),
        str(period) if period else "No accounting period contains this fixing date.",
    )

    add_check(
        "authenticated_actor",
        "Authenticated actor",
        bool(actor and getattr(actor, "is_authenticated", False)),
        str(actor) if actor and getattr(actor, "is_authenticated", False) else "Login required.",
    )

    exposure = _get_payload_object(ExposureLine, payload, "exposure")
    customer_account = _get_payload_object(Account, payload, "customer_account")
    receivable_ledger = _get_payload_object(Ledger, payload, "receivable_ledger")
    revenue_ledger = _get_payload_object(Ledger, payload, "revenue_ledger")
    fine_weight = Decimal(payload.get("fine_weight") or "0")

    exposure_ready = bool(
        exposure
        and exposure.side == "SALE"
        and exposure.status in {"OPEN", "PARTIALLY_FIXED"}
        and exposure.fixed_status in {"UNFIXED", "PARTIALLY_FIXED"}
        and exposure.open_fine_weight > Decimal("0.000")
    )
    add_check(
        "open_sale_exposure",
        "Open sale exposure",
        exposure_ready,
        str(exposure) if exposure_ready else "Exposure is missing or not open for sale fixing.",
    )
    add_check(
        "fixing_weight",
        "Fixing weight is within open exposure",
        bool(exposure and fine_weight > 0 and fine_weight <= exposure.open_fine_weight),
        f"{fine_weight} of {exposure.open_fine_weight}"
        if exposure
        else "Enter a positive fixing fine weight.",
    )
    account_party_matches = bool(
        exposure
        and customer_account
        and (
            not customer_account.party_id
            or customer_account.party_id == exposure.party_id
        )
    )
    add_check(
        "customer_account",
        "Customer monetary account is compatible",
        account_party_matches,
        str(customer_account)
        if account_party_matches
        else "Customer account is missing or linked to a different party.",
    )
    add_check(
        "financial_ledgers",
        "Financial ledgers exist",
        bool(receivable_ledger and revenue_ledger),
        "Receivable and revenue ledgers are available."
        if receivable_ledger and revenue_ledger
        else "Receivable or revenue ledger is missing.",
    )

    blockers = [check for check in checks if not check["passed"]]
    return {
        "ready": not blockers,
        "status": "ready" if not blockers else "blocked",
        "checks": checks,
        "blockers": blockers,
    }


def build_fixed_purchase_posting_readiness(
    draft: BusinessEventDraft,
    *,
    actor=None,
    include_existing_posting_guard=True,
) -> dict:
    """Return a read-only readiness checklist for future fixed purchase posting."""

    payload = draft.normalized_payload or {}
    checks = []

    def add_check(code: str, label: str, passed: bool, detail: str = ""):
        checks.append(
            {
                "code": code,
                "label": label,
                "passed": bool(passed),
                "detail": detail,
            }
        )

    add_check(
        "source_saved",
        "Draft source saved",
        bool(draft.pk and draft.source_reference),
        f"Draft #{draft.pk}" if draft.pk else "Draft must be saved before posting.",
    )
    add_check(
        "previewed",
        "Draft has preview status",
        draft.status == BusinessEventDraft.Status.PREVIEWED,
        draft.get_status_display(),
    )

    expected_hash = fixed_purchase_payload_hash(payload) if payload else ""
    add_check(
        "payload_hash",
        "Payload hash matches preview",
        bool(payload and draft.payload_hash == expected_hash),
        "Economic payload is unchanged."
        if payload and draft.payload_hash == expected_hash
        else "Re-preview the business facts before posting.",
    )

    period = AccountingPeriod.objects.get_period_for_date(draft.event_date)
    add_check(
        "open_period",
        "Open accounting period",
        bool(period and period.can_modify_transactions()),
        str(period) if period else "No accounting period contains this event date.",
    )

    add_check(
        "authenticated_actor",
        "Authenticated actor",
        bool(actor and getattr(actor, "is_authenticated", False)),
        str(actor) if actor and getattr(actor, "is_authenticated", False) else "Login required.",
    )

    supplier_account = _get_payload_object(Account, payload, "supplier_account")
    inventory_ledger = _get_payload_object(Ledger, payload, "inventory_ledger")
    payable_ledger = _get_payload_object(Ledger, payload, "payable_ledger")
    commodity = _get_payload_object(Commodity, payload, "commodity")
    from_account = _get_payload_object(
        CommodityAccount, payload, "from_commodity_account"
    )
    to_account = _get_payload_object(CommodityAccount, payload, "to_commodity_account")

    add_check(
        "supplier_account",
        "Supplier account exists",
        bool(supplier_account),
        str(supplier_account) if supplier_account else "Supplier account is missing.",
    )
    add_check(
        "financial_ledgers",
        "Financial ledgers exist",
        bool(inventory_ledger and payable_ledger),
        "Inventory and payable ledgers are available."
        if inventory_ledger and payable_ledger
        else "Inventory or payable ledger is missing.",
    )
    add_check(
        "commodity_active",
        "Commodity exists and is active",
        bool(commodity and commodity.is_active),
        str(commodity) if commodity else "Commodity is missing.",
    )
    commodity_accounts_match = bool(
        commodity
        and from_account
        and to_account
        and from_account.commodity_id == commodity.pk
        and to_account.commodity_id == commodity.pk
        and from_account.pk != to_account.pk
        and from_account.is_active
        and to_account.is_active
    )
    add_check(
        "commodity_accounts",
        "Commodity accounts are active and match commodity",
        commodity_accounts_match,
        "From and to commodity accounts are ready."
        if commodity_accounts_match
        else "Commodity accounts are missing, inactive, identical, or mismatched.",
    )

    if include_existing_posting_guard:
        has_existing_posting = _has_posted_fixed_purchase_voucher(draft)
        add_check(
            "no_existing_posting",
            "No posted fixed-purchase voucher for this draft",
            not has_existing_posting,
            "Ready for first posting."
            if not has_existing_posting
            else "A posted voucher already exists; use reversal/correction instead.",
        )

    blockers = [check for check in checks if not check["passed"]]
    return {
        "ready": not blockers,
        "status": "ready" if not blockers else "blocked",
        "checks": checks,
        "blockers": blockers,
    }


def build_unfixed_purchase_posting_readiness(
    draft: BusinessEventDraft,
    *,
    actor=None,
    include_existing_posting_guard=True,
) -> dict:
    """Return a read-only readiness checklist for future unfixed purchase posting."""

    payload = draft.normalized_payload or {}
    checks = []

    def add_check(code: str, label: str, passed: bool, detail: str = ""):
        checks.append(
            {
                "code": code,
                "label": label,
                "passed": bool(passed),
                "detail": detail,
            }
        )

    add_check(
        "source_saved",
        "Draft source saved",
        bool(draft.pk and draft.source_reference),
        f"Draft #{draft.pk}" if draft.pk else "Draft must be saved before posting.",
    )
    add_check(
        "previewed",
        "Draft has preview status",
        draft.status == BusinessEventDraft.Status.PREVIEWED,
        draft.get_status_display(),
    )

    expected_hash = unfixed_purchase_payload_hash(payload) if payload else ""
    add_check(
        "payload_hash",
        "Payload hash matches preview",
        bool(payload and draft.payload_hash == expected_hash),
        "Economic payload is unchanged."
        if payload and draft.payload_hash == expected_hash
        else "Re-preview the business facts before posting.",
    )

    period = AccountingPeriod.objects.get_period_for_date(draft.event_date)
    add_check(
        "open_period",
        "Open accounting period",
        bool(period and period.can_modify_transactions()),
        str(period) if period else "No accounting period contains this event date.",
    )

    add_check(
        "authenticated_actor",
        "Authenticated actor",
        bool(actor and getattr(actor, "is_authenticated", False)),
        str(actor) if actor and getattr(actor, "is_authenticated", False) else "Login required.",
    )

    party = _get_payload_object(Party, payload, "party")
    commodity = _get_payload_object(Commodity, payload, "commodity")
    from_account = _get_payload_object(
        CommodityAccount, payload, "from_commodity_account"
    )
    to_account = _get_payload_object(CommodityAccount, payload, "to_commodity_account")

    add_check(
        "party_active",
        "Supplier party exists and is active",
        bool(party and party.status == Party.PartyStatus.ACTIVE),
        str(party)
        if party and party.status == Party.PartyStatus.ACTIVE
        else "Supplier party is missing or not active.",
    )
    add_check(
        "commodity_active",
        "Commodity exists and is active",
        bool(commodity and commodity.is_active),
        str(commodity) if commodity else "Commodity is missing.",
    )
    commodity_accounts_match = bool(
        commodity
        and from_account
        and to_account
        and from_account.commodity_id == commodity.pk
        and to_account.commodity_id == commodity.pk
        and from_account.pk != to_account.pk
        and from_account.is_active
        and to_account.is_active
    )
    add_check(
        "commodity_accounts",
        "Commodity accounts are active and match commodity",
        commodity_accounts_match,
        "From and to commodity accounts are ready."
        if commodity_accounts_match
        else "Commodity accounts are missing, inactive, identical, or mismatched.",
    )

    if include_existing_posting_guard:
        has_existing_posting = _has_posted_unfixed_purchase_voucher(draft)
        add_check(
            "no_existing_posting",
            "No posted unfixed-purchase voucher for this draft",
            not has_existing_posting,
            "Ready for future first posting."
            if not has_existing_posting
            else "A posted voucher already exists; use reversal/correction instead.",
        )

    blockers = [check for check in checks if not check["passed"]]
    return {
        "ready": not blockers,
        "status": "ready" if not blockers else "blocked",
        "checks": checks,
        "blockers": blockers,
    }


def build_unfixed_sale_posting_readiness(
    draft: BusinessEventDraft,
    *,
    actor=None,
    include_existing_posting_guard=True,
) -> dict:
    """Return a read-only readiness checklist for future unfixed sale posting."""

    payload = draft.normalized_payload or {}
    checks = []

    def add_check(code: str, label: str, passed: bool, detail: str = ""):
        checks.append(
            {
                "code": code,
                "label": label,
                "passed": bool(passed),
                "detail": detail,
            }
        )

    add_check(
        "source_saved",
        "Draft source saved",
        bool(draft.pk and draft.source_reference),
        f"Draft #{draft.pk}" if draft.pk else "Draft must be saved before posting.",
    )
    add_check(
        "previewed",
        "Draft has preview status",
        draft.status == BusinessEventDraft.Status.PREVIEWED,
        draft.get_status_display(),
    )

    expected_hash = unfixed_sale_payload_hash(payload) if payload else ""
    add_check(
        "payload_hash",
        "Payload hash matches preview",
        bool(payload and draft.payload_hash == expected_hash),
        "Economic payload is unchanged."
        if payload and draft.payload_hash == expected_hash
        else "Re-preview the sale facts before posting.",
    )

    period = AccountingPeriod.objects.get_period_for_date(draft.event_date)
    add_check(
        "open_period",
        "Open accounting period",
        bool(period and period.can_modify_transactions()),
        str(period) if period else "No accounting period contains this event date.",
    )

    add_check(
        "authenticated_actor",
        "Authenticated actor",
        bool(actor and getattr(actor, "is_authenticated", False)),
        str(actor) if actor and getattr(actor, "is_authenticated", False) else "Login required.",
    )

    party = _get_payload_object(Party, payload, "party")
    commodity = _get_payload_object(Commodity, payload, "commodity")
    from_account = _get_payload_object(
        CommodityAccount, payload, "from_commodity_account"
    )

    add_check(
        "party_active",
        "Customer party exists and is active",
        bool(party and party.status == Party.PartyStatus.ACTIVE),
        str(party)
        if party and party.status == Party.PartyStatus.ACTIVE
        else "Customer party is missing or not active.",
    )
    add_check(
        "commodity_active",
        "Commodity exists and is active",
        bool(commodity and commodity.is_active),
        str(commodity) if commodity else "Commodity is missing.",
    )
    commodity_account_ready = bool(
        commodity
        and from_account
        and from_account.commodity_id == commodity.pk
        and from_account.is_active
    )
    add_check(
        "commodity_account",
        "Source commodity account is active and matches commodity",
        commodity_account_ready,
        "Source commodity account is ready."
        if commodity_account_ready
        else "Source commodity account is missing, inactive, or mismatched.",
    )

    if include_existing_posting_guard:
        has_existing_posting = _has_posted_unfixed_sale_voucher(draft)
        add_check(
            "no_existing_posting",
            "No posted unfixed-sale voucher for this draft",
            not has_existing_posting,
            "Ready for future first posting."
            if not has_existing_posting
            else "A posted voucher already exists; use reversal/correction instead.",
        )

    blockers = [check for check in checks if not check["passed"]]
    return {
        "ready": not blockers,
        "status": "ready" if not blockers else "blocked",
        "checks": checks,
        "blockers": blockers,
    }


@transaction.atomic
def save_fixed_purchase_preview_draft(
    cleaned_data: dict,
    preview: dict,
    *,
    actor=None,
) -> BusinessEventDraft:
    normalized_payload = build_fixed_purchase_normalized_payload(cleaned_data)
    payload_hash = fixed_purchase_payload_hash(normalized_payload)
    draft, created = BusinessEventDraft.objects.get_or_create(
        event_type=BusinessEventDraft.EventType.FIXED_PURCHASE,
        source_reference=normalized_payload["source_reference"],
        defaults={
            "event_date": cleaned_data["purchase_date"],
            "status": BusinessEventDraft.Status.PREVIEWED,
            "normalized_payload": normalized_payload,
            "preview_payload": _json_safe(preview),
            "payload_hash": payload_hash,
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        draft.event_date = cleaned_data["purchase_date"]
        draft.status = BusinessEventDraft.Status.PREVIEWED
        draft.normalized_payload = normalized_payload
        draft.preview_payload = _json_safe(preview)
        draft.payload_hash = payload_hash
        draft.updated_by = actor
        draft.save(
            update_fields=[
                "event_date",
                "status",
                "normalized_payload",
                "preview_payload",
                "payload_hash",
                "updated_by",
                "updated_at",
            ]
        )
    return draft


@transaction.atomic
def save_unfixed_purchase_preview_draft(
    cleaned_data: dict,
    preview: dict,
    *,
    actor=None,
) -> BusinessEventDraft:
    normalized_payload = build_unfixed_purchase_normalized_payload(cleaned_data)
    payload_hash = unfixed_purchase_payload_hash(normalized_payload)
    draft, created = BusinessEventDraft.objects.get_or_create(
        event_type=BusinessEventDraft.EventType.UNFIXED_PURCHASE,
        source_reference=normalized_payload["source_reference"],
        defaults={
            "event_date": cleaned_data["purchase_date"],
            "status": BusinessEventDraft.Status.PREVIEWED,
            "normalized_payload": normalized_payload,
            "preview_payload": _json_safe(preview),
            "payload_hash": payload_hash,
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        draft.event_date = cleaned_data["purchase_date"]
        draft.status = BusinessEventDraft.Status.PREVIEWED
        draft.normalized_payload = normalized_payload
        draft.preview_payload = _json_safe(preview)
        draft.payload_hash = payload_hash
        draft.updated_by = actor
        draft.save(
            update_fields=[
                "event_date",
                "status",
                "normalized_payload",
                "preview_payload",
                "payload_hash",
                "updated_by",
                "updated_at",
            ]
        )
    return draft


@transaction.atomic
def save_purchase_rate_fixing_preview_draft(
    cleaned_data: dict,
    preview: dict,
    *,
    actor=None,
) -> BusinessEventDraft:
    normalized_payload = build_purchase_rate_fixing_normalized_payload(cleaned_data)
    payload_hash = purchase_rate_fixing_payload_hash(normalized_payload)
    draft, created = BusinessEventDraft.objects.get_or_create(
        event_type=BusinessEventDraft.EventType.PURCHASE_RATE_FIXING,
        source_reference=normalized_payload["source_reference"],
        defaults={
            "event_date": cleaned_data["fixing_date"],
            "status": BusinessEventDraft.Status.PREVIEWED,
            "normalized_payload": normalized_payload,
            "preview_payload": _json_safe(preview),
            "payload_hash": payload_hash,
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        draft.event_date = cleaned_data["fixing_date"]
        draft.status = BusinessEventDraft.Status.PREVIEWED
        draft.normalized_payload = normalized_payload
        draft.preview_payload = _json_safe(preview)
        draft.payload_hash = payload_hash
        draft.updated_by = actor
        draft.save(
            update_fields=[
                "event_date",
                "status",
                "normalized_payload",
                "preview_payload",
                "payload_hash",
                "updated_by",
                "updated_at",
            ]
        )
    return draft


@transaction.atomic
def save_sale_rate_fixing_preview_draft(
    cleaned_data: dict,
    preview: dict,
    *,
    actor=None,
) -> BusinessEventDraft:
    normalized_payload = build_sale_rate_fixing_normalized_payload(cleaned_data)
    payload_hash = sale_rate_fixing_payload_hash(normalized_payload)
    draft, created = BusinessEventDraft.objects.get_or_create(
        event_type=BusinessEventDraft.EventType.SALE_RATE_FIXING,
        source_reference=normalized_payload["source_reference"],
        defaults={
            "event_date": cleaned_data["fixing_date"],
            "status": BusinessEventDraft.Status.PREVIEWED,
            "normalized_payload": normalized_payload,
            "preview_payload": _json_safe(preview),
            "payload_hash": payload_hash,
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        draft.event_date = cleaned_data["fixing_date"]
        draft.status = BusinessEventDraft.Status.PREVIEWED
        draft.normalized_payload = normalized_payload
        draft.preview_payload = _json_safe(preview)
        draft.payload_hash = payload_hash
        draft.updated_by = actor
        draft.save(
            update_fields=[
                "event_date",
                "status",
                "normalized_payload",
                "preview_payload",
                "payload_hash",
                "updated_by",
                "updated_at",
            ]
        )
    return draft


@transaction.atomic
def save_fixed_sale_preview_draft(
    cleaned_data: dict,
    preview: dict,
    *,
    actor=None,
) -> BusinessEventDraft:
    normalized_payload = build_fixed_sale_normalized_payload(cleaned_data)
    payload_hash = fixed_sale_payload_hash(normalized_payload)
    draft, created = BusinessEventDraft.objects.get_or_create(
        event_type=BusinessEventDraft.EventType.FIXED_SALE,
        source_reference=normalized_payload["source_reference"],
        defaults={
            "event_date": cleaned_data["sale_date"],
            "status": BusinessEventDraft.Status.PREVIEWED,
            "normalized_payload": normalized_payload,
            "preview_payload": _json_safe(preview),
            "payload_hash": payload_hash,
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        draft.event_date = cleaned_data["sale_date"]
        draft.status = BusinessEventDraft.Status.PREVIEWED
        draft.normalized_payload = normalized_payload
        draft.preview_payload = _json_safe(preview)
        draft.payload_hash = payload_hash
        draft.updated_by = actor
        draft.save(
            update_fields=[
                "event_date",
                "status",
                "normalized_payload",
                "preview_payload",
                "payload_hash",
                "updated_by",
                "updated_at",
            ]
        )
    return draft


@transaction.atomic
def save_unfixed_sale_preview_draft(
    cleaned_data: dict,
    preview: dict,
    *,
    actor=None,
) -> BusinessEventDraft:
    normalized_payload = build_unfixed_sale_normalized_payload(cleaned_data)
    payload_hash = unfixed_sale_payload_hash(normalized_payload)
    draft, created = BusinessEventDraft.objects.get_or_create(
        event_type=BusinessEventDraft.EventType.UNFIXED_SALE,
        source_reference=normalized_payload["source_reference"],
        defaults={
            "event_date": cleaned_data["sale_date"],
            "status": BusinessEventDraft.Status.PREVIEWED,
            "normalized_payload": normalized_payload,
            "preview_payload": _json_safe(preview),
            "payload_hash": payload_hash,
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        draft.event_date = cleaned_data["sale_date"]
        draft.status = BusinessEventDraft.Status.PREVIEWED
        draft.normalized_payload = normalized_payload
        draft.preview_payload = _json_safe(preview)
        draft.payload_hash = payload_hash
        draft.updated_by = actor
        draft.save(
            update_fields=[
                "event_date",
                "status",
                "normalized_payload",
                "preview_payload",
                "payload_hash",
                "updated_by",
                "updated_at",
            ]
        )
    return draft


@transaction.atomic
def save_monetary_settlement_preview_draft(
    cleaned_data: dict,
    preview: dict,
    *,
    actor=None,
) -> BusinessEventDraft:
    normalized_payload = build_monetary_settlement_normalized_payload(cleaned_data)
    payload_hash = monetary_settlement_payload_hash(normalized_payload)
    event_type = (
        BusinessEventDraft.EventType.CUSTOMER_RECEIPT
        if normalized_payload["settlement_type"] == "CUSTOMER_RECEIPT"
        else BusinessEventDraft.EventType.SUPPLIER_PAYMENT
    )
    draft, created = BusinessEventDraft.objects.get_or_create(
        event_type=event_type,
        source_reference=normalized_payload["source_reference"],
        defaults={
            "event_date": cleaned_data["event_date"],
            "status": BusinessEventDraft.Status.PREVIEWED,
            "normalized_payload": normalized_payload,
            "preview_payload": _json_safe(preview),
            "payload_hash": payload_hash,
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        draft.event_date = cleaned_data["event_date"]
        draft.status = BusinessEventDraft.Status.PREVIEWED
        draft.normalized_payload = normalized_payload
        draft.preview_payload = _json_safe(preview)
        draft.payload_hash = payload_hash
        draft.updated_by = actor
        draft.save(
            update_fields=[
                "event_date",
                "status",
                "normalized_payload",
                "preview_payload",
                "payload_hash",
                "updated_by",
                "updated_at",
            ]
        )
    return draft


@transaction.atomic
def save_karigar_movement_preview_draft(
    cleaned_data: dict,
    preview: dict,
    *,
    actor=None,
) -> BusinessEventDraft:
    normalized_payload = build_karigar_movement_normalized_payload(cleaned_data)
    payload_hash = karigar_movement_payload_hash(normalized_payload)
    event_type = (
        BusinessEventDraft.EventType.KARIGAR_ISSUE
        if normalized_payload["movement_type"] == "KARIGAR_ISSUE"
        else BusinessEventDraft.EventType.KARIGAR_RECEIPT
    )
    draft, created = BusinessEventDraft.objects.get_or_create(
        event_type=event_type,
        source_reference=normalized_payload["source_reference"],
        defaults={
            "event_date": cleaned_data["event_date"],
            "status": BusinessEventDraft.Status.PREVIEWED,
            "normalized_payload": normalized_payload,
            "preview_payload": _json_safe(preview),
            "payload_hash": payload_hash,
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        draft.event_date = cleaned_data["event_date"]
        draft.status = BusinessEventDraft.Status.PREVIEWED
        draft.normalized_payload = normalized_payload
        draft.preview_payload = _json_safe(preview)
        draft.payload_hash = payload_hash
        draft.updated_by = actor
        draft.save(
            update_fields=[
                "event_date",
                "status",
                "normalized_payload",
                "preview_payload",
                "payload_hash",
                "updated_by",
                "updated_at",
            ]
        )
    return draft


def _get_payload_object(model, payload: dict, key: str):
    value = payload.get(key)
    if not value:
        return None
    return model.objects.filter(pk=value).first()


def _has_posted_fixed_purchase_voucher(draft: BusinessEventDraft) -> bool:
    content_type = ContentType.objects.filter(
        app_label=draft._meta.app_label,
        model=draft._meta.model_name,
    ).first()
    if content_type is None:
        return False
    return Voucher.objects.filter(
        doc_content_type=content_type,
        doc_object_id=draft.pk,
        voucher_type__name=FIXED_PURCHASE_VOUCHER_TYPE,
        status=VoucherStatus.POSTED,
    ).exists()


def _has_posted_unfixed_purchase_voucher(draft: BusinessEventDraft) -> bool:
    content_type = ContentType.objects.filter(
        app_label=draft._meta.app_label,
        model=draft._meta.model_name,
    ).first()
    if content_type is None:
        return False
    return Voucher.objects.filter(
        doc_content_type=content_type,
        doc_object_id=draft.pk,
        voucher_type__name=UNFIXED_PURCHASE_VOUCHER_TYPE,
        status=VoucherStatus.POSTED,
    ).exists()


def _has_posted_fixed_sale_voucher(draft: BusinessEventDraft) -> bool:
    content_type = ContentType.objects.filter(
        app_label=draft._meta.app_label,
        model=draft._meta.model_name,
    ).first()
    if content_type is None:
        return False
    return Voucher.objects.filter(
        doc_content_type=content_type,
        doc_object_id=draft.pk,
        voucher_type__name=FIXED_SALE_VOUCHER_TYPE,
        status=VoucherStatus.POSTED,
    ).exists()


def _has_posted_unfixed_sale_voucher(draft: BusinessEventDraft) -> bool:
    content_type = ContentType.objects.filter(
        app_label=draft._meta.app_label,
        model=draft._meta.model_name,
    ).first()
    if content_type is None:
        return False
    return Voucher.objects.filter(
        doc_content_type=content_type,
        doc_object_id=draft.pk,
        voucher_type__name=UNFIXED_SALE_VOUCHER_TYPE,
        status=VoucherStatus.POSTED,
    ).exists()


def _has_posted_karigar_voucher(draft: BusinessEventDraft) -> bool:
    content_type = ContentType.objects.filter(
        app_label=draft._meta.app_label,
        model=draft._meta.model_name,
    ).first()
    if content_type is None:
        return False
    voucher_type_name = (
        KARIGAR_ISSUE_VOUCHER_TYPE
        if draft.event_type == BusinessEventDraft.EventType.KARIGAR_ISSUE
        else KARIGAR_RECEIPT_VOUCHER_TYPE
    )
    return Voucher.objects.filter(
        doc_content_type=content_type,
        doc_object_id=draft.pk,
        voucher_type__name=voucher_type_name,
        status=VoucherStatus.POSTED,
    ).exists()


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value
