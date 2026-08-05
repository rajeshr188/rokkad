"""Atomic pay-and-renew and top-up renewal workflows for PawnLoan."""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_DOWN

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.loans.domain import (
    AccountingRecognition,
    CollateralCustodyState,
    PawnLoanEventKind,
    PawnLoanRenewalMode,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.integrations import (
    accrual_payload,
    renewal_opening_payload,
    renewal_settlement_payload,
    reversal_payload,
)
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    LoanPolicySnapshot,
    PawnCollateralCustodyEvent,
    PawnCollateralItem,
    PawnLoan,
    PawnLoanAccountingEvent,
    PawnLoanAccountingOutbox,
    PawnLoanInterestAccrual,
    PawnLoanPrincipalClosingLine,
    PawnLoanPrincipalOpeningLine,
    PawnLoanRenewal,
    PawnLoanRenewalReversal,
    current_tenant_workspace_id,
)
from apps.tenant_apps.loans.selectors import (
    get_pawn_loan_balance,
    get_pawn_loan_release_readiness,
)
from apps.tenant_apps.loans.services.accounting_outbox import (
    DeliveryHandler,
    record_loan_accounting_event,
)
from apps.tenant_apps.loans.services.accounting_readiness import (
    require_pawn_loan_accounting_readiness,
)
from apps.tenant_apps.loans.services.pawn_disbursal import (
    assert_pawn_loan_financial_actions_allowed,
)
from apps.tenant_apps.loans.services.pawn_drafts import (
    CollateralDraftInput,
    CreatePawnDraftCommand,
    create_pawn_draft,
)
from apps.tenant_apps.loans.services.pawn_interest import (
    build_pawn_accrual_detail,
    persist_pawn_accrual_lines,
    preview_pawn_loan_accruals,
    should_record_pawn_accrual_event,
)
from apps.tenant_apps.loans.services.pawn_lifecycle import approve_pawn_loan
from apps.tenant_apps.loans.services.pawn_tranches import (
    PawnTrancheBalanceError,
    get_pawn_principal_tranche_balances,
)


class PawnRenewalError(ValueError):
    pass


@dataclass(frozen=True)
class RetainedCollateralInput:
    collateral_item_id: int
    allocated_principal: Decimal


@dataclass(frozen=True)
class PawnRenewalResult:
    renewal: PawnLoanRenewal
    source_loan: PawnLoan
    successor_loan: PawnLoan
    settlement_event: PawnLoanAccountingEvent
    settlement_outbox: PawnLoanAccountingOutbox
    opening_event: PawnLoanAccountingEvent
    opening_outbox: PawnLoanAccountingOutbox
    already_renewed: bool = False


@dataclass(frozen=True)
class PawnRenewalReversalResult:
    renewal: PawnLoanRenewal
    reversal: PawnLoanRenewalReversal
    settlement_reversal_event: PawnLoanAccountingEvent
    opening_reversal_event: PawnLoanAccountingEvent
    catch_up_reversal_event: PawnLoanAccountingEvent | None
    already_reversed: bool = False


@transaction.atomic
def renew_pawn_loan(
    source_loan_id: int,
    *,
    mode,
    renewal_date: date,
    principal_paid,
    top_up_amount,
    successor_license_id: int,
    successor_series_id: int,
    monthly_interest_rate=None,
    tenure_months: int,
    request_key: str,
    retained_collateral: tuple[RetainedCollateralInput, ...] | None = None,
    additional_collateral: tuple[CollateralDraftInput, ...] = (),
    actor=None,
    delivery_handler: DeliveryHandler | None = None,
) -> PawnRenewalResult:
    source = _locked_loan(source_loan_id)
    request_key = _request_key(request_key)
    request_fingerprint = _renewal_request_fingerprint(
        mode=mode,
        renewal_date=renewal_date,
        principal_paid=principal_paid,
        top_up_amount=top_up_amount,
        successor_license_id=successor_license_id,
        successor_series_id=successor_series_id,
        monthly_interest_rate=monthly_interest_rate,
        tenure_months=tenure_months,
        retained_collateral=retained_collateral,
        additional_collateral=additional_collateral,
    )
    existing = PawnLoanRenewal.objects.filter(
        workspace_id=source.workspace_id,
        request_key=request_key,
    ).select_related("source_loan", "successor_loan", "settlement_event__outbox", "opening_event__outbox").first()
    if existing:
        if existing.source_loan_id != source.pk:
            raise PawnRenewalError("Renewal request key belongs to another source loan.")
        recorded_fingerprint = existing.valuation_snapshot.get("request_fingerprint")
        if recorded_fingerprint and recorded_fingerprint != request_fingerprint:
            raise PawnRenewalError(
                "Renewal request key was already used with different instructions."
            )
        return PawnRenewalResult(
            existing,
            existing.source_loan,
            existing.successor_loan,
            existing.settlement_event,
            existing.settlement_event.outbox,
            existing.opening_event,
            existing.opening_event.outbox,
            True,
        )
    try:
        renewal_mode = PawnLoanRenewalMode(mode)
    except ValueError as exc:
        raise PawnRenewalError("Unknown PawnLoan renewal mode.") from exc
    if renewal_date != timezone.localdate():
        raise PawnRenewalError("MVP renewal must use the current business date.")
    if source.state != PawnLoanState.ACTIVE.value:
        raise PawnRenewalError("Only an active PawnLoan can be renewed.")
    if hasattr(source, "renewal_as_source"):
        raise PawnRenewalError("This PawnLoan already has a renewal successor.")
    if source.auctions.filter(state__in=("INITIATED", "IN_PROGRESS")).exists():
        raise PawnRenewalError("Cancel the active auction before renewing this loan.")
    items = tuple(
        PawnCollateralItem.objects.select_for_update().filter(loan=source).order_by("pk")
    )
    if not items or any(
        item.custody_state != CollateralCustodyState.IN_VAULT.value
        for item in items
    ):
        raise PawnRenewalError(
            "Every collateral item must be in the vault before renewal."
        )
    principal_paid = _money(principal_paid, source)
    top_up_amount = _money(top_up_amount, source)
    if retained_collateral is None:
        monthly_interest_rate = _rate(monthly_interest_rate)
    if not 1 <= int(tenure_months) <= 600:
        raise PawnRenewalError("Renewal tenure must be between 1 and 600 months.")
    if renewal_mode == PawnLoanRenewalMode.PAY_AND_RENEW:
        if top_up_amount != 0:
            raise PawnRenewalError("Pay-and-renew cannot include a top-up amount.")
    elif top_up_amount <= 0 or principal_paid != 0:
        raise PawnRenewalError(
            "Top-up renewal requires a positive top-up and no simultaneous principal paydown."
        )

    try:
        assert_pawn_loan_financial_actions_allowed(source.pk)
        completed = preview_pawn_loan_accruals(
            source.pk,
            as_of_date=renewal_date,
            include_partial=False,
        )
        if completed:
            raise PawnRenewalError(
                "Finalize every completed interest period before renewal."
            )
        partials = preview_pawn_loan_accruals(
            source.pk,
            as_of_date=renewal_date,
            include_partial=True,
        )
        partial = partials[0] if partials and partials[0].is_partial else None
        catch_up = (
            _record_renewal_accrual(
                source,
                preview=partial,
                actor=actor,
                delivery_handler=delivery_handler,
            )
            if partial
            else None
        )
        balance = get_pawn_loan_balance(source.pk, as_of_date=renewal_date)
        try:
            source_tranches = get_pawn_principal_tranche_balances(source)
        except PawnTrancheBalanceError as exc:
            raise PawnRenewalError(str(exc)) from exc
        if source_tranches and sum(
            (row.principal_outstanding for row in source_tranches), Decimal("0")
        ) != balance.original_principal_outstanding:
            raise PawnRenewalError(
                "Renewal source item principal does not reconcile to original principal."
            )
        if principal_paid >= balance.principal_outstanding:
            raise PawnRenewalError(
                "Renewal must carry a positive principal; use full release to settle the loan."
            )
        currency_quantum = Decimal(
            str(source.policy_snapshot.currency_quantum)
        ).normalize()
        successor_principal = (
            balance.principal_outstanding - principal_paid + top_up_amount
        ).quantize(currency_quantum)
        successor_collateral, retained_item_ids = _successor_collateral_plan(
            items,
            retained_collateral=retained_collateral,
            additional_collateral=additional_collateral,
            successor_principal=successor_principal,
        )
        readiness = get_pawn_loan_release_readiness(
            source.pk,
            selected_item_ids=tuple(item.pk for item in items),
            as_of_date=renewal_date,
        )
        if readiness.blockers:
            raise PawnRenewalError(
                "; ".join(blocker.message for blocker in readiness.blockers)
            )
        collateral_value = readiness.selected_collateral_value
        if collateral_value is None or collateral_value <= 0:
            raise PawnRenewalError("Renewal collateral valuation is unavailable.")
        allowed_principal = (
            collateral_value * source.policy_snapshot.maximum_ltv_ratio
        ).quantize(source.policy_snapshot.currency_quantum, rounding=ROUND_DOWN)
        if successor_principal > allowed_principal:
            raise PawnRenewalError(
                f"Successor principal {successor_principal} exceeds the allowed collateral-backed amount {allowed_principal}."
            )
        require_pawn_loan_accounting_readiness(
            source,
            effective_date=renewal_date,
            requires_fee_income=balance.fees_outstanding > 0,
            requires_interest_receivable=(
                source.policy_snapshot.accounting_recognition
                == AccountingRecognition.ACCRUAL.value
                and balance.interest_outstanding > 0
            ),
            requires_unearned_interest=(
                source.policy_snapshot.accounting_recognition
                == AccountingRecognition.ACCRUAL.value
                and partial is not None
                and partial.advance_interest_applied > 0
            ),
        )
    except PawnRenewalError:
        raise
    except Exception as exc:
        raise PawnRenewalError(str(exc)) from exc

    successor = create_pawn_draft(
        CreatePawnDraftCommand(
            workspace_id=source.workspace_id,
            borrower_id=source.borrower_id,
            license_id=successor_license_id,
            series_id=successor_series_id,
            principal_amount=successor_principal,
            monthly_interest_rate=monthly_interest_rate or Decimal("0"),
            loan_date=renewal_date,
            tenure_months=int(tenure_months),
            collateral=successor_collateral,
        ),
        actor=actor,
    )
    approval = approve_pawn_loan(successor.pk, actor=actor)
    successor_policy = _clone_policy(source, successor)
    successor_items = tuple(successor.collateral_items.order_by("pk"))
    if len(successor_items) != len(successor_collateral):
        raise PawnRenewalError("Renewal collateral lineage could not be established.")
    source_by_id = {item.pk: item for item in items}
    retained_ids_in_order = tuple(
        value.collateral_item_id for value in retained_collateral or ()
    ) if retained_collateral is not None else tuple(item.pk for item in items)
    for source_item_id, new_item in zip(
        retained_ids_in_order,
        successor_items[: len(retained_ids_in_order)],
        strict=True,
    ):
        new_item.renewed_from = source_by_id[source_item_id]
        new_item.save(update_fields=["renewed_from", "updated_at"])

    capitalized_paid = min(
        principal_paid,
        balance.capitalized_interest_principal_outstanding,
    )
    successor_capitalized = (
        balance.capitalized_interest_principal_outstanding - capitalized_paid
    ).quantize(currency_quantum)
    successor_original = (successor_principal - successor_capitalized).quantize(
        currency_quantum
    )
    if retained_collateral is not None and successor_capitalized:
        raise PawnRenewalError(
            "Release and renew cannot carry capitalized interest until it has "
            "explicit successor-item attribution. Settle it before renewal."
        )
    source_control = (
        balance.principal_outstanding
        if source.policy_snapshot.accounting_recognition
        == AccountingRecognition.ACCRUAL.value
        else balance.original_principal_outstanding
    )
    successor_control = (
        successor_principal
        if successor_policy.accounting_recognition
        == AccountingRecognition.ACCRUAL.value
        else successor_original
    )
    renewal_number = f"REN-{source.loan_number}"
    settlement_payload = renewal_settlement_payload(
        source,
        effective_date=renewal_date,
        principal_amount=balance.principal_outstanding,
        capitalized_interest_principal_amount=(
            balance.capitalized_interest_principal_outstanding
        ),
        interest_amount=balance.interest_outstanding,
        fee_amount=balance.fees_outstanding,
    ).to_dict()
    settlement_payload["renewal"] = {
        "renewal_number": renewal_number,
        "mode": renewal_mode.value,
        "source_loan_id": source.pk,
        "source_loan_number": source.loan_number,
        "successor_loan_id": successor.pk,
        "successor_loan_number": successor.loan_number,
        "principal_paid": str(principal_paid),
        "top_up_amount": str(top_up_amount),
        "successor_principal": str(successor_principal),
        "source_control_principal": str(source_control),
        "successor_control_principal": str(successor_control),
        "accounting_recognition": source.policy_snapshot.accounting_recognition,
        "catch_up_event_id": (
            catch_up.accounting_event_id if catch_up is not None else None
        ),
        "retained_source_item_ids": list(retained_item_ids),
        "returned_source_item_ids": [
            item.pk for item in items if item.pk not in retained_item_ids
        ],
    }
    settlement_event, settlement_outbox = record_loan_accounting_event(
        source.pk,
        event_kind=TransactionKind.RENEWAL_SETTLEMENT,
        effective_date=renewal_date,
        payload=settlement_payload,
        actor=actor,
        delivery_handler=delivery_handler,
    )
    for order, row in enumerate(
        sorted(
            source_tranches,
            key=lambda value: (-value.monthly_interest_rate, value.collateral_item_id),
        ),
        start=1,
    ):
        PawnLoanPrincipalClosingLine.objects.create(
            accounting_event=settlement_event,
            collateral_item_id=row.collateral_item_id,
            allocation_order=order,
            monthly_interest_rate=row.monthly_interest_rate,
            balance_before=row.principal_outstanding,
            principal_settled=row.principal_outstanding,
            balance_after=Decimal("0"),
        )
    opening_payload = renewal_opening_payload(
        successor,
        effective_date=renewal_date,
        principal_amount=successor_principal,
        capitalized_interest_principal_amount=successor_capitalized,
    ).to_dict()
    opening_payload["renewal"] = {
        "renewal_number": renewal_number,
        "source_loan_id": source.pk,
        "settlement_event_id": settlement_event.pk,
        "operational_opening": True,
        "retained_source_item_ids": list(retained_item_ids),
        "additional_successor_item_ids": [
            item.pk for item in successor_items if item.renewed_from_id is None
        ],
    }
    opening_event, opening_outbox = record_loan_accounting_event(
        successor.pk,
        event_kind=TransactionKind.RENEWAL_OPENING,
        effective_date=renewal_date,
        payload=opening_payload,
        actor=actor,
        delivery_handler=delivery_handler,
    )
    if retained_collateral is not None:
        if sum(
            (item.allocated_principal for item in successor_items), Decimal("0")
        ) != successor_original:
            raise PawnRenewalError(
                "Successor item principal does not reconcile to original principal."
            )
        for order, item in enumerate(successor_items, start=1):
            PawnLoanPrincipalOpeningLine.objects.create(
                accounting_event=opening_event,
                collateral_item=item,
                predecessor_collateral_item=item.renewed_from,
                allocation_order=order,
                monthly_interest_rate=item.monthly_interest_rate,
                principal_opened=item.allocated_principal,
            )
    valuation_snapshot = {
        "request_fingerprint": request_fingerprint,
        "valuation_method": readiness.valuation_method,
        "maximum_ltv_ratio": str(readiness.maximum_ltv_ratio),
        "collateral_value": str(collateral_value),
        "allowed_principal": str(allowed_principal),
        "items": [
            {
                "source_item_id": value.collateral_item_id,
                "description": value.description,
                "valuation_amount": str(value.valuation_amount),
                "rate_id": value.rate_id,
                "rate_per_unit": (
                    str(value.rate_per_unit)
                    if value.rate_per_unit is not None
                    else None
                ),
                "latest_appraised_value": (
                    str(value.latest_appraised_value)
                    if value.latest_appraised_value is not None
                    else None
                ),
            }
            for value in readiness.item_valuations
        ],
        "successor_approval_snapshot_id": approval.pk,
        "retained_source_item_ids": list(retained_item_ids),
        "returned_source_item_ids": [
            item.pk for item in items if item.pk not in retained_item_ids
        ],
        "additional_successor_item_ids": [
            item.pk for item in successor_items if item.renewed_from_id is None
        ],
    }
    renewal = PawnLoanRenewal.objects.create(
        workspace=source.workspace,
        source_loan=source,
        successor_loan=successor,
        renewal_number=renewal_number,
        request_key=request_key,
        mode=renewal_mode.value,
        renewal_date=renewal_date,
        source_principal_amount=balance.principal_outstanding,
        source_capitalized_principal_amount=(
            balance.capitalized_interest_principal_outstanding
        ),
        interest_settled=balance.interest_outstanding,
        fees_settled=balance.fees_outstanding,
        principal_paid=principal_paid,
        top_up_amount=top_up_amount,
        successor_principal_amount=successor_principal,
        successor_capitalized_principal_amount=successor_capitalized,
        valuation_snapshot=valuation_snapshot,
        settlement_event=settlement_event,
        opening_event=opening_event,
        catch_up_accrual=catch_up,
        created_by=actor,
    )
    effective_now = timezone.now()
    for old_item in items:
        retained = old_item.pk in retained_item_ids
        destination = (
            CollateralCustodyState.RENEWAL_TRANSFERRED.value
            if retained
            else CollateralCustodyState.WITH_CUSTOMER.value
        )
        PawnCollateralCustodyEvent.objects.create(
            collateral_item=old_item,
            renewal=renewal,
            from_state=CollateralCustodyState.IN_VAULT.value,
            to_state=destination,
            effective_date=renewal_date,
            actor=actor,
        )
        old_item.custody_state = destination
        old_item.save(update_fields=["custody_state", "updated_at"])
    source.state = PawnLoanState.CLOSED.value
    source.updated_by = actor
    source.save(update_fields=["state", "updated_by", "updated_at"])
    successor.state = PawnLoanState.ACTIVE.value
    successor.updated_by = actor
    successor.save(update_fields=["state", "updated_by", "updated_at"])
    LoanChangeLog.objects.create(
        loan=source,
        event_kind=PawnLoanEventKind.RENEWAL_COMPLETED.value,
        from_state=PawnLoanState.ACTIVE.value,
        to_state=PawnLoanState.CLOSED.value,
        actor=actor,
        metadata={
            "renewal_id": renewal.pk,
            "successor_loan_id": successor.pk,
            "settlement_event_id": settlement_event.pk,
            "retained_source_item_ids": list(retained_item_ids),
            "returned_source_item_ids": [
                item.pk for item in items if item.pk not in retained_item_ids
            ],
        },
    )
    LoanChangeLog.objects.create(
        loan=successor,
        event_kind=PawnLoanEventKind.RENEWAL_SUCCESSOR_ACTIVATED.value,
        from_state=PawnLoanState.APPROVED.value,
        to_state=PawnLoanState.ACTIVE.value,
        actor=actor,
        metadata={
            "renewal_id": renewal.pk,
            "source_loan_id": source.pk,
            "opening_event_id": opening_event.pk,
            "activated_at": effective_now.isoformat(),
        },
    )
    return PawnRenewalResult(
        renewal,
        source,
        successor,
        settlement_event,
        settlement_outbox,
        opening_event,
        opening_outbox,
    )


@transaction.atomic
def reverse_pawn_loan_renewal(
    renewal_id: int,
    *,
    reason: str,
    actor,
    delivery_handler: DeliveryHandler | None = None,
) -> PawnRenewalReversalResult:
    renewal = _locked_renewal(renewal_id)
    reason = str(reason or "").strip()
    if not reason:
        raise PawnRenewalError("Renewal reversal requires a reason.")
    try:
        existing = renewal.reversal
    except ObjectDoesNotExist:
        existing = None
    if existing:
        if existing.reason != reason:
            raise PawnRenewalError("Renewal was already reversed with another reason.")
        return PawnRenewalReversalResult(
            renewal,
            existing,
            existing.settlement_reversal_event,
            existing.opening_reversal_event,
            existing.catch_up_reversal_event,
            True,
        )
    if renewal.source_loan.state != PawnLoanState.CLOSED.value:
        raise PawnRenewalError("Renewal source must remain closed for reversal.")
    if renewal.successor_loan.state != PawnLoanState.ACTIVE.value:
        raise PawnRenewalError("Renewal successor must remain active for reversal.")
    source_items = tuple(
        PawnCollateralItem.objects.select_for_update()
        .filter(loan=renewal.source_loan)
        .order_by("pk")
    )
    successor_items = tuple(
        PawnCollateralItem.objects.select_for_update()
        .filter(loan=renewal.successor_loan)
        .order_by("pk")
    )
    if any(item.custody_state != CollateralCustodyState.RENEWAL_TRANSFERRED.value for item in source_items):
        raise PawnRenewalError("Source collateral custody changed after renewal.")
    if any(item.custody_state != CollateralCustodyState.IN_VAULT.value for item in successor_items):
        raise PawnRenewalError("Successor collateral custody changed after renewal.")
    from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event

    opening_result = reverse_pawn_loan_event(
        renewal.opening_event_id,
        reason=reason,
        actor=actor,
        delivery_handler=delivery_handler,
        allow_renewal=True,
    )
    settlement_result = reverse_pawn_loan_event(
        renewal.settlement_event_id,
        reason=reason,
        actor=actor,
        delivery_handler=delivery_handler,
        allow_renewal=True,
    )
    catch_up_reversal = _reverse_catch_up(
        renewal,
        reason=reason,
        actor=actor,
        delivery_handler=delivery_handler,
    )
    reversal = PawnLoanRenewalReversal.objects.create(
        renewal=renewal,
        settlement_reversal_event=settlement_result.reversal_event,
        opening_reversal_event=opening_result.reversal_event,
        catch_up_reversal_event=catch_up_reversal,
        reason=reason,
        created_by=actor,
    )
    effective_date = timezone.localdate()
    for item in source_items:
        PawnCollateralCustodyEvent.objects.create(
            collateral_item=item,
            renewal=renewal,
            renewal_reversal=reversal,
            from_state=CollateralCustodyState.RENEWAL_TRANSFERRED.value,
            to_state=CollateralCustodyState.IN_VAULT.value,
            effective_date=effective_date,
            actor=actor,
        )
        item.custody_state = CollateralCustodyState.IN_VAULT.value
        item.save(update_fields=["custody_state", "updated_at"])
    for item in successor_items:
        PawnCollateralCustodyEvent.objects.create(
            collateral_item=item,
            renewal=renewal,
            renewal_reversal=reversal,
            from_state=CollateralCustodyState.IN_VAULT.value,
            to_state=CollateralCustodyState.RENEWAL_REVERSED.value,
            effective_date=effective_date,
            actor=actor,
        )
        item.custody_state = CollateralCustodyState.RENEWAL_REVERSED.value
        item.save(update_fields=["custody_state", "updated_at"])
    renewal.source_loan.state = PawnLoanState.ACTIVE.value
    renewal.source_loan.updated_by = actor
    renewal.source_loan.save(update_fields=["state", "updated_by", "updated_at"])
    renewal.successor_loan.state = PawnLoanState.CANCELLED.value
    renewal.successor_loan.updated_by = actor
    renewal.successor_loan.save(update_fields=["state", "updated_by", "updated_at"])
    for loan, before, after in (
        (renewal.source_loan, PawnLoanState.CLOSED.value, PawnLoanState.ACTIVE.value),
        (renewal.successor_loan, PawnLoanState.ACTIVE.value, PawnLoanState.CANCELLED.value),
    ):
        LoanChangeLog.objects.create(
            loan=loan,
            event_kind=PawnLoanEventKind.RENEWAL_REVERSED.value,
            from_state=before,
            to_state=after,
            reason=reason,
            actor=actor,
            metadata={"renewal_id": renewal.pk, "renewal_reversal_id": reversal.pk},
        )
    return PawnRenewalReversalResult(
        renewal,
        reversal,
        settlement_result.reversal_event,
        opening_result.reversal_event,
        catch_up_reversal,
    )


def _record_renewal_accrual(loan, *, preview, actor, delivery_handler):
    event = None
    outbox = None
    if should_record_pawn_accrual_event(preview, loan.policy_snapshot):
        payload = accrual_payload(
            loan,
            effective_date=preview.period_end,
            interest_amount=preview.recognized_interest,
            advance_interest_applied=preview.advance_interest_applied,
        ).to_dict()
        payload["accrual"] = build_pawn_accrual_detail(
            preview, loan.policy_snapshot
        )
        payload["accrual"]["renewal_catch_up"] = True
        event, outbox = record_loan_accounting_event(
            loan.pk,
            event_kind=TransactionKind.INTEREST_ACCRUAL,
            effective_date=preview.period_end,
            payload=payload,
            actor=actor,
            delivery_handler=delivery_handler,
        )
    accrual = PawnLoanInterestAccrual.objects.create(
        loan=loan,
        period_number=preview.period_number,
        period_start=preview.period_start,
        period_end=preview.period_end,
        period_fraction=preview.period_fraction,
        calculation_base=preview.calculation_base,
        unrounded_interest=preview.unrounded_interest,
        recognized_interest=preview.recognized_interest,
        accounting_event=event,
        finalized_by=actor,
    )
    persist_pawn_accrual_lines(accrual, preview)
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.ACCRUAL_FINALIZED.value,
        from_state=loan.state,
        to_state=loan.state,
        actor=actor,
        metadata={
            "period_number": preview.period_number,
            "renewal_catch_up": True,
            "accounting_event_id": event.pk if event else None,
            "outbox_id": outbox.pk if outbox else None,
        },
    )
    return accrual


def _reverse_catch_up(renewal, *, reason, actor, delivery_handler):
    accrual = renewal.catch_up_accrual
    if not accrual or not accrual.accounting_event_id:
        return None
    original = accrual.accounting_event
    payload = reversal_payload(
        renewal.source_loan,
        effective_date=timezone.localdate(),
        original_event_id=original.pk,
        original_event_kind=original.event_kind,
        values=original.payload.get("values") or {},
        reason=reason,
    ).to_dict()
    payload["reversal"]["renewal_id"] = renewal.pk
    event, _ = record_loan_accounting_event(
        renewal.source_loan_id,
        event_kind=TransactionKind.REVERSAL,
        effective_date=timezone.localdate(),
        payload=payload,
        actor=actor,
        delivery_handler=delivery_handler,
        reversal_of=original,
    )
    return event


def _clone_policy(source, successor):
    source_policy = source.policy_snapshot
    fields = (
        "policy_version",
        "interest_method",
        "partial_month_method",
        "partial_month_cutoff_days",
        "partial_month_lower_fraction",
        "capitalization_interval_periods",
        "accounting_recognition",
        "valuation_method",
        "maximum_ltv_ratio",
        "rounding_method",
        "currency_quantum",
    )
    return LoanPolicySnapshot.objects.create(
        loan=successor,
        **{field: getattr(source_policy, field) for field in fields},
    )


def _successor_collateral_plan(
    source_items,
    *,
    retained_collateral,
    additional_collateral,
    successor_principal,
):
    """Build successor inputs and return the retained source identities."""
    if retained_collateral is None:
        if additional_collateral:
            raise PawnRenewalError(
                "Additional collateral requires an explicit retained-collateral plan."
            )
        return (
            tuple(
                CollateralDraftInput(
                    description=item.description,
                    metal=item.metal,
                    gross_weight=item.gross_weight,
                    net_weight=item.net_weight,
                    purity_percentage=item.purity_percentage,
                    latest_appraised_value=item.latest_appraised_value,
                )
                for item in source_items
            ),
            frozenset(item.pk for item in source_items),
        )

    source_by_id = {item.pk: item for item in source_items}
    retained = tuple(retained_collateral)
    retained_ids = tuple(value.collateral_item_id for value in retained)
    if len(set(retained_ids)) != len(retained_ids):
        raise PawnRenewalError("A source collateral item can be retained only once.")
    if any(item_id not in source_by_id for item_id in retained_ids):
        raise PawnRenewalError(
            "Retained collateral must belong to the source PawnLoan."
        )
    successor_inputs = []
    for value in retained:
        source = source_by_id[value.collateral_item_id]
        try:
            allocated = Decimal(str(value.allocated_principal))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise PawnRenewalError(
                "Every retained item requires a valid allocated principal."
            ) from exc
        if allocated <= 0:
            raise PawnRenewalError(
                "Every retained item requires a positive allocated principal."
            )
        successor_inputs.append(
            CollateralDraftInput(
                description=source.description,
                metal=source.metal,
                gross_weight=source.gross_weight,
                net_weight=source.net_weight,
                purity_percentage=source.purity_percentage,
                latest_appraised_value=source.latest_appraised_value,
                allocated_principal=allocated,
            )
        )
    successor_inputs.extend(tuple(additional_collateral))
    if not successor_inputs:
        raise PawnRenewalError(
            "Release and renew requires retained or additional collateral."
        )
    allocations = [item.allocated_principal for item in successor_inputs]
    if any(value is None for value in allocations):
        raise PawnRenewalError(
            "Every successor collateral item requires an allocated principal."
        )
    allocated_total = sum((Decimal(str(value)) for value in allocations), Decimal("0"))
    if allocated_total != successor_principal:
        raise PawnRenewalError(
            "Successor collateral allocations must equal successor principal "
            f"{successor_principal}; received {allocated_total}."
        )
    return tuple(successor_inputs), frozenset(retained_ids)


def _renewal_request_fingerprint(**values):
    def normalize(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, date):
            return value.isoformat()
        if hasattr(value, "value"):
            return value.value
        if hasattr(value, "__dataclass_fields__"):
            return {key: normalize(item) for key, item in asdict(value).items()}
        if isinstance(value, (tuple, list)):
            return [normalize(item) for item in value]
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items()}
        return value

    serialized = json.dumps(normalize(values), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _locked_loan(loan_id):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnRenewalError("PawnLoan renewal requires an active tenant schema.")
    try:
        return (
            PawnLoan.objects.select_for_update(of=("self",))
            .select_related("workspace", "borrower", "policy_snapshot")
            .get(pk=loan_id, workspace_id=workspace_id)
        )
    except PawnLoan.DoesNotExist as exc:
        raise PawnRenewalError("PawnLoan was not found in the active workspace.") from exc


def _locked_renewal(renewal_id):
    workspace_id = current_tenant_workspace_id()
    try:
        return (
            PawnLoanRenewal.objects.select_for_update(of=("self",))
            .select_related(
                "source_loan",
                "source_loan__workspace",
                "successor_loan",
                "settlement_event__outbox",
                "opening_event__outbox",
                "catch_up_accrual__accounting_event__outbox",
            )
            .get(pk=renewal_id, workspace_id=workspace_id)
        )
    except PawnLoanRenewal.DoesNotExist as exc:
        raise PawnRenewalError("PawnLoan renewal was not found.") from exc


def _money(value, loan):
    try:
        amount = Decimal(str(value or "0"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PawnRenewalError("Renewal amount must be a valid number.") from exc
    quantum = Decimal(str(loan.policy_snapshot.currency_quantum))
    if amount < 0 or amount != amount.quantize(quantum):
        raise PawnRenewalError(
            f"Renewal amount must be non-negative and use precision {quantum}."
        )
    return amount


def _rate(value):
    try:
        rate = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PawnRenewalError("Monthly interest rate must be valid.") from exc
    if rate < 0 or rate > 100:
        raise PawnRenewalError("Monthly interest rate must be between 0 and 100.")
    return rate


def _request_key(value):
    value = str(value or "").strip()
    if not value or len(value) > 120:
        raise PawnRenewalError("A renewal request key of at most 120 characters is required.")
    return value


__all__ = [
    "PawnRenewalError",
    "PawnRenewalResult",
    "PawnRenewalReversalResult",
    "renew_pawn_loan",
    "reverse_pawn_loan_renewal",
]
