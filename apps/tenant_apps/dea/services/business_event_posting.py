"""Business-event confirm handoffs for DEA UI drafts.

The UI still controls when these services are exposed. These functions are the
service-level boundary between a previewed source draft and existing posting
services.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.tenant_apps.dea.models import (
    Account,
    BusinessEventDraft,
    Commodity,
    CommodityAccount,
    ExposureLine,
    Ledger,
)
from apps.tenant_apps.dea.services.business_event_preview import (
    build_fixed_purchase_posting_readiness,
    build_fixed_sale_posting_readiness,
    build_karigar_movement_posting_readiness,
    build_monetary_settlement_posting_readiness,
    build_purchase_rate_fixing_posting_readiness,
    build_sale_rate_fixing_posting_readiness,
    build_unfixed_purchase_posting_readiness,
    build_unfixed_sale_posting_readiness,
    fixed_purchase_payload_hash,
    fixed_sale_payload_hash,
    karigar_movement_payload_hash,
    monetary_settlement_payload_hash,
    purchase_rate_fixing_payload_hash,
    sale_rate_fixing_payload_hash,
    unfixed_purchase_payload_hash,
    unfixed_sale_payload_hash,
)
from apps.tenant_apps.dea.services.karigar import (
    KarigarIssuePayload,
    KarigarMovementResult,
    KarigarReceiptPayload,
    post_karigar_issue,
    post_karigar_receipt,
)
from apps.tenant_apps.dea.services.fixed_purchase import (
    FixedPurchasePostingPayload,
    FixedPurchasePostingResult,
    post_fixed_purchase,
)
from apps.tenant_apps.dea.services.fixed_sale import (
    FixedSalePostingPayload,
    FixedSalePostingResult,
    post_fixed_sale,
)
from apps.tenant_apps.dea.services.monetary_settlement import (
    CustomerReceiptPayload,
    MonetarySettlementResult,
    SupplierPaymentPayload,
    post_customer_receipt,
    post_supplier_payment,
)
from apps.tenant_apps.dea.services.rate_fixing import (
    PurchaseRateFixingPayload,
    PurchaseRateFixingResult,
    SaleRateFixingPayload,
    SaleRateFixingResult,
    post_purchase_rate_fixing,
    post_sale_rate_fixing,
)
from apps.tenant_apps.dea.services.unfixed_purchase import (
    UnfixedPurchasePostingPayload,
    UnfixedPurchasePostingResult,
    post_unfixed_purchase,
)
from apps.tenant_apps.dea.services.unfixed_sale import (
    UnfixedSalePostingPayload,
    UnfixedSalePostingResult,
    post_unfixed_sale,
)
from apps.tenant_apps.party.models import Party


@transaction.atomic
def confirm_fixed_purchase_draft(
    draft_id: int,
    *,
    actor=None,
) -> FixedPurchasePostingResult:
    """Post a previewed fixed-purchase draft through the backend posting service.

    This service intentionally owns the row lock, stale-preview check, readiness
    gate, and draft-to-payload mapping. Views should not recreate this mapping.
    """

    draft = (
        BusinessEventDraft.objects.select_for_update()
        .get(pk=draft_id)
    )
    _validate_fixed_purchase_draft(draft)

    readiness = build_fixed_purchase_posting_readiness(
        draft,
        actor=actor,
        include_existing_posting_guard=False,
    )
    blockers = readiness["blockers"]
    if blockers:
        raise ValidationError(
            {
                "readiness": [
                    f"{blocker['label']}: {blocker['detail']}"
                    for blocker in blockers
                ]
            }
        )

    return post_fixed_purchase(
        _fixed_purchase_payload_from_draft(draft),
        actor=actor,
    )


@transaction.atomic
def confirm_unfixed_purchase_draft(
    draft_id: int,
    *,
    actor=None,
) -> UnfixedPurchasePostingResult:
    """Post a previewed unfixed-purchase draft through the backend posting service."""

    draft = BusinessEventDraft.objects.select_for_update().get(pk=draft_id)
    _validate_unfixed_purchase_draft(draft)

    readiness = build_unfixed_purchase_posting_readiness(
        draft,
        actor=actor,
        include_existing_posting_guard=False,
    )
    blockers = readiness["blockers"]
    if blockers:
        raise ValidationError(
            {
                "readiness": [
                    f"{blocker['label']}: {blocker['detail']}"
                    for blocker in blockers
                ]
            }
        )

    return post_unfixed_purchase(
        _unfixed_purchase_payload_from_draft(draft),
        actor=actor,
    )


@transaction.atomic
def confirm_purchase_rate_fixing_draft(
    draft_id: int,
    *,
    actor=None,
) -> PurchaseRateFixingResult:
    """Post a previewed purchase rate-fixing draft through the backend service."""

    draft = BusinessEventDraft.objects.select_for_update().get(pk=draft_id)
    _validate_purchase_rate_fixing_draft(draft)

    readiness = build_purchase_rate_fixing_posting_readiness(
        draft,
        actor=actor,
    )
    blockers = readiness["blockers"]
    if blockers:
        raise ValidationError(
            {
                "readiness": [
                    f"{blocker['label']}: {blocker['detail']}"
                    for blocker in blockers
                ]
            }
        )

    return post_purchase_rate_fixing(
        _purchase_rate_fixing_payload_from_draft(draft),
        actor=actor,
    )


@transaction.atomic
def confirm_sale_rate_fixing_draft(
    draft_id: int,
    *,
    actor=None,
) -> SaleRateFixingResult:
    """Post a previewed sale rate-fixing draft through the backend service."""

    draft = BusinessEventDraft.objects.select_for_update().get(pk=draft_id)
    _validate_sale_rate_fixing_draft(draft)

    readiness = build_sale_rate_fixing_posting_readiness(
        draft,
        actor=actor,
    )
    blockers = readiness["blockers"]
    if blockers:
        raise ValidationError(
            {
                "readiness": [
                    f"{blocker['label']}: {blocker['detail']}"
                    for blocker in blockers
                ]
            }
        )

    return post_sale_rate_fixing(
        _sale_rate_fixing_payload_from_draft(draft),
        actor=actor,
    )


@transaction.atomic
def confirm_fixed_sale_draft(
    draft_id: int,
    *,
    actor=None,
) -> FixedSalePostingResult:
    """Post a previewed fixed-sale draft through the backend posting service."""

    draft = BusinessEventDraft.objects.select_for_update().get(pk=draft_id)
    _validate_fixed_sale_draft(draft)

    readiness = build_fixed_sale_posting_readiness(
        draft,
        actor=actor,
        include_existing_posting_guard=False,
    )
    blockers = readiness["blockers"]
    if blockers:
        raise ValidationError(
            {
                "readiness": [
                    f"{blocker['label']}: {blocker['detail']}"
                    for blocker in blockers
                ]
            }
        )

    return post_fixed_sale(
        _fixed_sale_payload_from_draft(draft),
        actor=actor,
    )


@transaction.atomic
def confirm_unfixed_sale_draft(
    draft_id: int,
    *,
    actor=None,
) -> UnfixedSalePostingResult:
    """Post a previewed unfixed-sale draft through the backend posting service."""

    draft = BusinessEventDraft.objects.select_for_update().get(pk=draft_id)
    _validate_unfixed_sale_draft(draft)

    readiness = build_unfixed_sale_posting_readiness(
        draft,
        actor=actor,
        include_existing_posting_guard=False,
    )
    blockers = readiness["blockers"]
    if blockers:
        raise ValidationError(
            {
                "readiness": [
                    f"{blocker['label']}: {blocker['detail']}"
                    for blocker in blockers
                ]
            }
        )

    return post_unfixed_sale(
        _unfixed_sale_payload_from_draft(draft),
        actor=actor,
    )


@transaction.atomic
def confirm_monetary_settlement_draft(
    draft_id: int,
    *,
    actor=None,
) -> MonetarySettlementResult:
    """Post a previewed monetary receipt/payment draft through the backend service."""

    draft = BusinessEventDraft.objects.select_for_update().get(pk=draft_id)
    _validate_monetary_settlement_draft(draft)

    readiness = build_monetary_settlement_posting_readiness(
        draft,
        actor=actor,
    )
    blockers = readiness["blockers"]
    if blockers:
        raise ValidationError(
            {
                "readiness": [
                    f"{blocker['label']}: {blocker['detail']}"
                    for blocker in blockers
                ]
            }
        )

    if draft.event_type == BusinessEventDraft.EventType.CUSTOMER_RECEIPT:
        return post_customer_receipt(
            _customer_receipt_payload_from_draft(draft),
            actor=actor,
        )
    return post_supplier_payment(
        _supplier_payment_payload_from_draft(draft),
        actor=actor,
    )


@transaction.atomic
def confirm_karigar_movement_draft(
    draft_id: int,
    *,
    actor=None,
) -> KarigarMovementResult:
    """Post a previewed karigar issue/receipt draft through the backend service."""

    draft = BusinessEventDraft.objects.select_for_update().get(pk=draft_id)
    _validate_karigar_movement_draft(draft)

    readiness = build_karigar_movement_posting_readiness(
        draft,
        actor=actor,
        include_existing_posting_guard=False,
    )
    blockers = readiness["blockers"]
    if blockers:
        raise ValidationError(
            {
                "readiness": [
                    f"{blocker['label']}: {blocker['detail']}"
                    for blocker in blockers
                ]
            }
        )

    if draft.event_type == BusinessEventDraft.EventType.KARIGAR_ISSUE:
        return post_karigar_issue(
            _karigar_issue_payload_from_draft(draft),
            actor=actor,
        )
    return post_karigar_receipt(
        _karigar_receipt_payload_from_draft(draft),
        actor=actor,
    )


def _validate_fixed_purchase_draft(draft: BusinessEventDraft) -> None:
    if draft.event_type != BusinessEventDraft.EventType.FIXED_PURCHASE:
        raise ValidationError({"event_type": "Draft is not a fixed-purchase draft."})
    if draft.status != BusinessEventDraft.Status.PREVIEWED:
        raise ValidationError({"status": "Draft must be previewed before posting."})
    payload = draft.normalized_payload or {}
    expected_hash = fixed_purchase_payload_hash(payload) if payload else ""
    if not payload or draft.payload_hash != expected_hash:
        raise ValidationError(
            {"payload_hash": "Draft preview is stale. Re-preview before posting."}
        )


def _validate_unfixed_purchase_draft(draft: BusinessEventDraft) -> None:
    if draft.event_type != BusinessEventDraft.EventType.UNFIXED_PURCHASE:
        raise ValidationError({"event_type": "Draft is not an unfixed-purchase draft."})
    if draft.status != BusinessEventDraft.Status.PREVIEWED:
        raise ValidationError({"status": "Draft must be previewed before posting."})
    payload = draft.normalized_payload or {}
    expected_hash = unfixed_purchase_payload_hash(payload) if payload else ""
    if not payload or draft.payload_hash != expected_hash:
        raise ValidationError(
            {"payload_hash": "Draft preview is stale. Re-preview before posting."}
        )


def _validate_purchase_rate_fixing_draft(draft: BusinessEventDraft) -> None:
    if draft.event_type != BusinessEventDraft.EventType.PURCHASE_RATE_FIXING:
        raise ValidationError(
            {"event_type": "Draft is not a purchase rate-fixing draft."}
        )
    if draft.status != BusinessEventDraft.Status.PREVIEWED:
        raise ValidationError({"status": "Draft must be previewed before posting."})
    payload = draft.normalized_payload or {}
    expected_hash = purchase_rate_fixing_payload_hash(payload) if payload else ""
    if not payload or draft.payload_hash != expected_hash:
        raise ValidationError(
            {"payload_hash": "Draft preview is stale. Re-preview before posting."}
        )


def _validate_sale_rate_fixing_draft(draft: BusinessEventDraft) -> None:
    if draft.event_type != BusinessEventDraft.EventType.SALE_RATE_FIXING:
        raise ValidationError({"event_type": "Draft is not a sale rate-fixing draft."})
    if draft.status != BusinessEventDraft.Status.PREVIEWED:
        raise ValidationError({"status": "Draft must be previewed before posting."})
    payload = draft.normalized_payload or {}
    expected_hash = sale_rate_fixing_payload_hash(payload) if payload else ""
    if not payload or draft.payload_hash != expected_hash:
        raise ValidationError(
            {"payload_hash": "Draft preview is stale. Re-preview before posting."}
        )


def _validate_fixed_sale_draft(draft: BusinessEventDraft) -> None:
    if draft.event_type != BusinessEventDraft.EventType.FIXED_SALE:
        raise ValidationError({"event_type": "Draft is not a fixed-sale draft."})
    if draft.status != BusinessEventDraft.Status.PREVIEWED:
        raise ValidationError({"status": "Draft must be previewed before posting."})
    payload = draft.normalized_payload or {}
    expected_hash = fixed_sale_payload_hash(payload) if payload else ""
    if not payload or draft.payload_hash != expected_hash:
        raise ValidationError(
            {"payload_hash": "Draft preview is stale. Re-preview before posting."}
        )


def _validate_unfixed_sale_draft(draft: BusinessEventDraft) -> None:
    if draft.event_type != BusinessEventDraft.EventType.UNFIXED_SALE:
        raise ValidationError({"event_type": "Draft is not an unfixed-sale draft."})
    if draft.status != BusinessEventDraft.Status.PREVIEWED:
        raise ValidationError({"status": "Draft must be previewed before posting."})
    payload = draft.normalized_payload or {}
    expected_hash = unfixed_sale_payload_hash(payload) if payload else ""
    if not payload or draft.payload_hash != expected_hash:
        raise ValidationError(
            {"payload_hash": "Draft preview is stale. Re-preview before posting."}
        )


def _validate_monetary_settlement_draft(draft: BusinessEventDraft) -> None:
    if draft.event_type not in {
        BusinessEventDraft.EventType.CUSTOMER_RECEIPT,
        BusinessEventDraft.EventType.SUPPLIER_PAYMENT,
    }:
        raise ValidationError(
            {"event_type": "Draft is not a monetary receipt/payment draft."}
        )
    if draft.status != BusinessEventDraft.Status.PREVIEWED:
        raise ValidationError({"status": "Draft must be previewed before posting."})
    payload = draft.normalized_payload or {}
    expected_hash = monetary_settlement_payload_hash(payload) if payload else ""
    if not payload or draft.payload_hash != expected_hash:
        raise ValidationError(
            {"payload_hash": "Draft preview is stale. Re-preview before posting."}
        )


def _validate_karigar_movement_draft(draft: BusinessEventDraft) -> None:
    if draft.event_type not in {
        BusinessEventDraft.EventType.KARIGAR_ISSUE,
        BusinessEventDraft.EventType.KARIGAR_RECEIPT,
    }:
        raise ValidationError(
            {"event_type": "Draft is not a karigar issue/receipt draft."}
        )
    if draft.status != BusinessEventDraft.Status.PREVIEWED:
        raise ValidationError({"status": "Draft must be previewed before posting."})
    payload = draft.normalized_payload or {}
    expected_hash = karigar_movement_payload_hash(payload) if payload else ""
    if not payload or draft.payload_hash != expected_hash:
        raise ValidationError(
            {"payload_hash": "Draft preview is stale. Re-preview before posting."}
        )


def _fixed_purchase_payload_from_draft(
    draft: BusinessEventDraft,
) -> FixedPurchasePostingPayload:
    payload = draft.normalized_payload or {}
    return FixedPurchasePostingPayload(
        source=draft,
        purchase_date=draft.event_date,
        supplier_account=_required_object(Account, payload, "supplier_account"),
        inventory_ledger=_required_object(Ledger, payload, "inventory_ledger"),
        payable_ledger=_required_object(Ledger, payload, "payable_ledger"),
        commodity=_required_object(Commodity, payload, "commodity"),
        gross_weight=Decimal(payload["gross_weight"]),
        purity=Decimal(payload["purity"]),
        fine_weight=Decimal(payload["fine_weight"]),
        from_commodity_account=_required_object(
            CommodityAccount, payload, "from_commodity_account"
        ),
        to_commodity_account=_required_object(
            CommodityAccount, payload, "to_commodity_account"
        ),
        money_amount=Decimal(payload["money_amount"]),
        currency=payload["currency"],
        narration=payload.get("narration") or "",
        metadata={
            "business_event_draft_id": draft.pk,
            "source_reference": draft.source_reference,
            "payload_hash": draft.payload_hash,
        },
    )


def _unfixed_purchase_payload_from_draft(
    draft: BusinessEventDraft,
) -> UnfixedPurchasePostingPayload:
    payload = draft.normalized_payload or {}
    last_valuation_rate = payload.get("last_valuation_rate")
    return UnfixedPurchasePostingPayload(
        source=draft,
        purchase_date=draft.event_date,
        party=_required_object(Party, payload, "party"),
        commodity=_required_object(Commodity, payload, "commodity"),
        gross_weight=Decimal(payload["gross_weight"]),
        purity=Decimal(payload["purity"]),
        fine_weight=Decimal(payload["fine_weight"]),
        from_commodity_account=_required_object(
            CommodityAccount, payload, "from_commodity_account"
        ),
        to_commodity_account=_required_object(
            CommodityAccount, payload, "to_commodity_account"
        ),
        rate_basis=payload.get("rate_basis") or "",
        valuation_currency=payload["valuation_currency"],
        last_valuation_rate=Decimal(last_valuation_rate)
        if last_valuation_rate
        else None,
        narration=payload.get("narration") or "",
        metadata={
            "business_event_draft_id": draft.pk,
            "source_reference": draft.source_reference,
            "payload_hash": draft.payload_hash,
        },
    )


def _purchase_rate_fixing_payload_from_draft(
    draft: BusinessEventDraft,
) -> PurchaseRateFixingPayload:
    payload = draft.normalized_payload or {}
    return PurchaseRateFixingPayload(
        exposure=_required_object(ExposureLine, payload, "exposure"),
        fixing_date=draft.event_date,
        fine_weight=Decimal(payload["fine_weight"]),
        rate=Decimal(payload["rate"]),
        supplier_account=_required_object(Account, payload, "supplier_account"),
        inventory_ledger=_required_object(Ledger, payload, "inventory_ledger"),
        payable_ledger=_required_object(Ledger, payload, "payable_ledger"),
        currency=payload["currency"],
        narration=payload.get("narration") or "",
    )


def _sale_rate_fixing_payload_from_draft(
    draft: BusinessEventDraft,
) -> SaleRateFixingPayload:
    payload = draft.normalized_payload or {}
    return SaleRateFixingPayload(
        exposure=_required_object(ExposureLine, payload, "exposure"),
        fixing_date=draft.event_date,
        fine_weight=Decimal(payload["fine_weight"]),
        rate=Decimal(payload["rate"]),
        customer_account=_required_object(Account, payload, "customer_account"),
        receivable_ledger=_required_object(Ledger, payload, "receivable_ledger"),
        revenue_ledger=_required_object(Ledger, payload, "revenue_ledger"),
        currency=payload["currency"],
        narration=payload.get("narration") or "",
    )


def _fixed_sale_payload_from_draft(
    draft: BusinessEventDraft,
) -> FixedSalePostingPayload:
    payload = draft.normalized_payload or {}
    return FixedSalePostingPayload(
        source=draft,
        sale_date=draft.event_date,
        customer_account=_required_object(Account, payload, "customer_account"),
        receivable_ledger=_required_object(Ledger, payload, "receivable_ledger"),
        revenue_ledger=_required_object(Ledger, payload, "revenue_ledger"),
        commodity=_required_object(Commodity, payload, "commodity"),
        gross_weight=Decimal(payload["gross_weight"]),
        purity=Decimal(payload["purity"]),
        fine_weight=Decimal(payload["fine_weight"]),
        from_commodity_account=_required_object(
            CommodityAccount, payload, "from_commodity_account"
        ),
        money_amount=Decimal(payload["money_amount"]),
        currency=payload["currency"],
        narration=payload.get("narration") or "",
        metadata={
            "business_event_draft_id": draft.pk,
            "source_reference": draft.source_reference,
            "payload_hash": draft.payload_hash,
        },
    )


def _unfixed_sale_payload_from_draft(
    draft: BusinessEventDraft,
) -> UnfixedSalePostingPayload:
    payload = draft.normalized_payload or {}
    last_valuation_rate = payload.get("last_valuation_rate")
    return UnfixedSalePostingPayload(
        source=draft,
        sale_date=draft.event_date,
        party=_required_object(Party, payload, "party"),
        commodity=_required_object(Commodity, payload, "commodity"),
        gross_weight=Decimal(payload["gross_weight"]),
        purity=Decimal(payload["purity"]),
        fine_weight=Decimal(payload["fine_weight"]),
        from_commodity_account=_required_object(
            CommodityAccount, payload, "from_commodity_account"
        ),
        rate_basis=payload.get("rate_basis") or "",
        valuation_currency=payload["valuation_currency"],
        last_valuation_rate=Decimal(last_valuation_rate)
        if last_valuation_rate
        else None,
        narration=payload.get("narration") or "",
        metadata={
            "business_event_draft_id": draft.pk,
            "source_reference": draft.source_reference,
            "payload_hash": draft.payload_hash,
        },
    )


def _customer_receipt_payload_from_draft(
    draft: BusinessEventDraft,
) -> CustomerReceiptPayload:
    payload = draft.normalized_payload or {}
    return CustomerReceiptPayload(
        source=draft,
        receipt_date=draft.event_date,
        customer_account=_required_object(Account, payload, "party_account"),
        cash_or_bank_ledger=_required_object(Ledger, payload, "cash_or_bank_ledger"),
        receivable_ledger=_required_object(Ledger, payload, "counterparty_ledger"),
        money_amount=Decimal(payload["money_amount"]),
        reference_number=payload["reference_number"],
        currency=payload["currency"],
        payment_method=payload["payment_method"],
        narration=payload.get("narration") or "",
    )


def _supplier_payment_payload_from_draft(
    draft: BusinessEventDraft,
) -> SupplierPaymentPayload:
    payload = draft.normalized_payload or {}
    return SupplierPaymentPayload(
        source=draft,
        payment_date=draft.event_date,
        supplier_account=_required_object(Account, payload, "party_account"),
        payable_ledger=_required_object(Ledger, payload, "counterparty_ledger"),
        cash_or_bank_ledger=_required_object(Ledger, payload, "cash_or_bank_ledger"),
        money_amount=Decimal(payload["money_amount"]),
        reference_number=payload["reference_number"],
        currency=payload["currency"],
        payment_method=payload["payment_method"],
        narration=payload.get("narration") or "",
    )


def _karigar_issue_payload_from_draft(
    draft: BusinessEventDraft,
) -> KarigarIssuePayload:
    payload = draft.normalized_payload or {}
    return KarigarIssuePayload(
        source=draft,
        issue_date=draft.event_date,
        karigar=_required_object(Party, payload, "karigar"),
        commodity=_required_object(Commodity, payload, "commodity"),
        gross_weight=Decimal(payload["gross_weight"]),
        purity=Decimal(payload["purity"]),
        fine_weight=Decimal(payload["fine_weight"]),
        from_commodity_account=_required_object(
            CommodityAccount, payload, "from_commodity_account"
        ),
        to_karigar_account=_required_object(
            CommodityAccount, payload, "to_commodity_account"
        ),
        narration=payload.get("narration") or "",
        metadata={
            "business_event_draft_id": draft.pk,
            "source_reference": draft.source_reference,
            "payload_hash": draft.payload_hash,
        },
    )


def _karigar_receipt_payload_from_draft(
    draft: BusinessEventDraft,
) -> KarigarReceiptPayload:
    payload = draft.normalized_payload or {}
    return KarigarReceiptPayload(
        source=draft,
        receipt_date=draft.event_date,
        karigar=_required_object(Party, payload, "karigar"),
        commodity=_required_object(Commodity, payload, "commodity"),
        gross_weight=Decimal(payload["gross_weight"]),
        purity=Decimal(payload["purity"]),
        fine_weight=Decimal(payload["fine_weight"]),
        from_karigar_account=_required_object(
            CommodityAccount, payload, "from_commodity_account"
        ),
        to_commodity_account=_required_object(
            CommodityAccount, payload, "to_commodity_account"
        ),
        narration=payload.get("narration") or "",
        metadata={
            "business_event_draft_id": draft.pk,
            "source_reference": draft.source_reference,
            "payload_hash": draft.payload_hash,
        },
    )


def _required_object(model, payload: dict, key: str):
    obj = model.objects.filter(pk=payload.get(key)).first()
    if obj is None:
        raise ValidationError({key: f"Referenced {key} record is missing."})
    return obj
