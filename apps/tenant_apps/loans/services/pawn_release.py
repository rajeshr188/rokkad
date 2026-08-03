"""Atomic full-settlement and collateral-return workflow for PawnLoans."""

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.loans.domain import (
    AccountingRecognition,
    CollateralCustodyState,
    PawnLoanEventKind,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.integrations import accrual_payload, release_receipt_payload
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    PawnCollateralCustodyEvent,
    PawnCollateralItem,
    PawnLoan,
    PawnLoanAccountingEvent,
    PawnLoanAccountingOutbox,
    PawnLoanInterestAccrual,
    PawnLoanRelease,
    PawnLoanReleaseItem,
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
from apps.tenant_apps.loans.services.number_allocation import allocate_release_number
from apps.tenant_apps.loans.services.pawn_disbursal import (
    assert_pawn_loan_financial_actions_allowed,
)
from apps.tenant_apps.loans.services.pawn_interest import preview_pawn_loan_accruals


class PawnReleaseError(ValueError):
    pass


@dataclass(frozen=True)
class PawnFullReleaseResult:
    loan: PawnLoan
    release: PawnLoanRelease
    accounting_event: PawnLoanAccountingEvent
    outbox: PawnLoanAccountingOutbox
    already_released: bool = False


@transaction.atomic
def release_pawn_loan_in_full(
    loan_id: int,
    *,
    settlement_amount,
    request_key: str,
    actor=None,
    delivery_handler: DeliveryHandler | None = None,
) -> PawnFullReleaseResult:
    """Settle an active loan and return every item in one durable transaction."""
    loan = _locked_loan(loan_id)
    request_key = _request_key(request_key)
    amount = _money_amount(settlement_amount, loan)
    existing = loan.releases.filter(request_key=request_key).first()
    if existing:
        if existing.settlement_amount != amount:
            raise PawnReleaseError(
                "Release request key was already used with a different amount."
            )
        return PawnFullReleaseResult(
            loan,
            existing,
            existing.accounting_event,
            existing.accounting_event.outbox,
            True,
        )
    if loan.state != PawnLoanState.ACTIVE.value:
        raise PawnReleaseError("Only an active PawnLoan can be released.")

    effective_date = timezone.localdate()
    collateral = tuple(
        PawnCollateralItem.objects.select_for_update().filter(loan=loan)
    )
    if not collateral:
        raise PawnReleaseError("A PawnLoan without collateral cannot be released.")
    try:
        assert_pawn_loan_financial_actions_allowed(loan.pk)
        missing_accruals = preview_pawn_loan_accruals(
            loan.pk,
            as_of_date=effective_date,
            include_partial=False,
        )
        if missing_accruals:
            raise PawnReleaseError(
                "Finalize every completed interest period before releasing the loan."
            )
        partial_candidates = preview_pawn_loan_accruals(
            loan.pk,
            as_of_date=effective_date,
            include_partial=True,
        )
        partial_accrual = (
            partial_candidates[0]
            if partial_candidates and partial_candidates[0].is_partial
            else None
        )
        readiness = get_pawn_loan_release_readiness(
            loan.pk,
            selected_item_ids=tuple(item.pk for item in collateral),
            as_of_date=effective_date,
        )
        if not readiness.ready:
            raise PawnReleaseError(
                "PawnLoan is not ready for release: "
                + "; ".join(blocker.message for blocker in readiness.blockers)
            )
        if not readiness.is_full_release:
            raise PawnReleaseError("Full release must return every collateral item.")
        catch_up_interest = (
            partial_accrual.recognized_interest if partial_accrual else Decimal("0")
        )
        required_settlement = readiness.minimum_settlement + catch_up_interest
        if amount != required_settlement:
            raise PawnReleaseError(
                "Full release settlement must equal the current total due of "
                f"{required_settlement}."
            )
        balance = get_pawn_loan_balance(loan.pk, as_of_date=effective_date)
        balance_interest = readiness.fees_and_interest_settlement
        fee_amount = balance.fees_outstanding
        interest_amount = balance_interest - fee_amount + catch_up_interest
        principal_amount = amount - balance_interest - catch_up_interest
        capitalized_principal = min(
            principal_amount,
            balance.capitalized_interest_principal_outstanding,
        )
        recognition = loan.policy_snapshot.accounting_recognition
        require_pawn_loan_accounting_readiness(
            loan,
            effective_date=effective_date,
            requires_fee_income=fee_amount > 0,
            requires_interest_receivable=(
                recognition == AccountingRecognition.ACCRUAL.value
                and interest_amount > 0
            ),
        )
    except PawnReleaseError:
        raise
    except Exception as exc:
        raise PawnReleaseError(str(exc)) from exc

    allocation = allocate_release_number(series=loan.series, actor=actor)
    if partial_accrual:
        _record_release_accrual(
            loan,
            preview=partial_accrual,
            actor=actor,
            delivery_handler=delivery_handler,
        )
    payload = release_receipt_payload(
        loan,
        effective_date=effective_date,
        principal_amount=principal_amount,
        interest_amount=interest_amount,
        fee_amount=fee_amount,
        original_principal_amount=principal_amount - capitalized_principal,
        capitalized_interest_principal_amount=capitalized_principal,
    ).to_dict()
    payload["release"] = {
        "request_key": request_key,
        "release_number": allocation.value,
        "is_full_release": True,
        "accounting_recognition": recognition,
    }
    event, outbox = record_loan_accounting_event(
        loan.pk,
        event_kind=TransactionKind.RELEASE_RECEIPT,
        effective_date=effective_date,
        payload=payload,
        actor=actor,
        delivery_handler=delivery_handler,
    )
    release = PawnLoanRelease.objects.create(
        workspace=loan.workspace,
        loan=loan,
        release_number=allocation.value,
        request_key=request_key,
        effective_date=effective_date,
        settlement_amount=amount,
        principal_amount=principal_amount,
        interest_amount=interest_amount,
        fee_amount=fee_amount,
        valuation_snapshot=_readiness_snapshot(
            readiness,
            catch_up_interest=catch_up_interest,
        ),
        accounting_event=event,
        created_by=actor,
    )
    snapshots = {item.collateral_item_id: item for item in readiness.item_valuations}
    now = timezone.now()
    for item in collateral:
        snapshot = snapshots[item.pk]
        PawnLoanReleaseItem.objects.create(
            release=release,
            collateral_item=item,
            valuation_snapshot=_json_snapshot(snapshot),
            returned_at=now,
        )
        PawnCollateralCustodyEvent.objects.create(
            collateral_item=item,
            release=release,
            from_state=item.custody_state,
            to_state=CollateralCustodyState.WITH_CUSTOMER.value,
            effective_date=effective_date,
            actor=actor,
        )
        item.custody_state = CollateralCustodyState.WITH_CUSTOMER.value
        item.save(update_fields=["custody_state", "updated_at"])

    if PawnCollateralItem.objects.filter(loan=loan).exclude(
        custody_state=CollateralCustodyState.WITH_CUSTOMER.value
    ).exists():
        raise PawnReleaseError("Loan cannot close until every item is returned.")
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.RELEASE_COMPLETED.value,
        from_state=PawnLoanState.ACTIVE.value,
        to_state=PawnLoanState.ACTIVE.value,
        actor=actor,
        metadata={"release_id": release.pk, "release_number": release.release_number},
    )
    loan.state = PawnLoanState.CLOSED.value
    loan.updated_by = actor
    loan.save(update_fields=["state", "updated_by", "updated_at"])
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.CLOSED.value,
        from_state=PawnLoanState.ACTIVE.value,
        to_state=PawnLoanState.CLOSED.value,
        actor=actor,
        metadata={"release_id": release.pk},
    )
    return PawnFullReleaseResult(loan, release, event, outbox)


def _locked_loan(loan_id):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnReleaseError("PawnLoan release requires an active tenant schema.")
    try:
        return (
            PawnLoan.objects.select_for_update(of=("self",))
            .select_related("series", "policy_snapshot", "borrower")
            .get(pk=loan_id, workspace_id=workspace_id)
        )
    except PawnLoan.DoesNotExist as exc:
        raise PawnReleaseError(
            "PawnLoan was not found in the active workspace."
        ) from exc


def _request_key(value):
    value = str(value or "").strip()
    if not value or len(value) > 120:
        raise PawnReleaseError(
            "A release request key of at most 120 characters is required."
        )
    return value


def _record_release_accrual(loan, *, preview, actor, delivery_handler):
    """Persist the release-day partial period before its settlement event."""
    policy = loan.policy_snapshot
    event = None
    outbox = None
    if preview.recognized_interest > 0:
        payload = accrual_payload(
            loan,
            effective_date=preview.period_end,
            interest_amount=preview.recognized_interest,
        ).to_dict()
        payload["accrual"] = {
            "period_number": preview.period_number,
            "period_start": preview.period_start.isoformat(),
            "period_end": preview.period_end.isoformat(),
            "period_fraction": str(preview.period_fraction),
            "calculation_base": str(preview.calculation_base),
            "unrounded_interest": str(preview.unrounded_interest),
            "recognized_interest": str(preview.recognized_interest),
            "accounting_recognition": policy.accounting_recognition,
            "release_catch_up": True,
        }
        event, outbox = record_loan_accounting_event(
            loan.pk,
            event_kind=TransactionKind.INTEREST_ACCRUAL,
            effective_date=preview.period_end,
            payload=payload,
            actor=actor,
            delivery_handler=delivery_handler,
        )
    PawnLoanInterestAccrual.objects.create(
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
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.ACCRUAL_FINALIZED.value,
        from_state=PawnLoanState.ACTIVE.value,
        to_state=PawnLoanState.ACTIVE.value,
        actor=actor,
        metadata={
            "period_number": preview.period_number,
            "period_fraction": str(preview.period_fraction),
            "recognized_interest": str(preview.recognized_interest),
            "release_catch_up": True,
            "accounting_event_id": event.pk if event else None,
            "outbox_id": outbox.pk if outbox else None,
        },
    )


def _money_amount(value, loan):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PawnReleaseError("Settlement amount must be a valid number.") from exc
    quantum = Decimal(str(loan.policy_snapshot.currency_quantum))
    if amount < 0 or amount != amount.quantize(quantum):
        raise PawnReleaseError(
            f"Settlement amount must be non-negative and use precision {quantum}."
        )
    return amount


def _readiness_snapshot(readiness, *, catch_up_interest):
    return {
        "as_of_date": readiness.as_of_date.isoformat(),
        "valuation_method": readiness.valuation_method,
        "maximum_ltv_ratio": str(readiness.maximum_ltv_ratio),
        "selected_collateral_value": str(readiness.selected_collateral_value),
        "base_minimum_settlement": str(readiness.minimum_settlement),
        "release_day_catch_up_interest": str(catch_up_interest),
        "minimum_settlement": str(
            readiness.minimum_settlement + catch_up_interest
        ),
    }


def _json_snapshot(snapshot):
    values = asdict(snapshot)
    for key, value in tuple(values.items()):
        if isinstance(value, Decimal):
            values[key] = str(value)
        elif hasattr(value, "isoformat"):
            values[key] = value.isoformat()
    return values
