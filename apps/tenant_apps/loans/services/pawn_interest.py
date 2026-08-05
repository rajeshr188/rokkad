"""Monthly PawnLoan interest preview, finalization, and capitalization."""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.tenant_apps.loans.domain import (
    AccountingRecognition,
    InterestMethod,
    PartialMonthMethod,
    PawnLoanEventKind,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.integrations import accrual_payload, capitalization_payload
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    PawnLoan,
    PawnLoanAccountingEvent,
    PawnLoanDisbursalSnapshot,
    PawnLoanInterestAccrual,
    PawnLoanInterestAccrualLine,
    current_tenant_workspace_id,
)
from apps.tenant_apps.loans.selectors import get_pawn_loan_balance
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
from apps.tenant_apps.loans.services.pawn_tranches import (
    PawnTrancheBalanceError,
    get_pawn_principal_tranche_balances,
)


class PawnInterestError(ValueError):
    pass


@dataclass(frozen=True)
class AccrualPeriodPreview:
    period_number: int
    period_start: date
    period_end: date
    period_fraction: Decimal
    calculation_base: Decimal
    unrounded_interest: Decimal
    recognized_interest: Decimal
    is_partial: bool
    calculated_interest: Decimal = Decimal("0")
    advance_interest_applied: Decimal = Decimal("0")
    lines: tuple["AccrualLinePreview", ...] = ()


@dataclass(frozen=True)
class AccrualLinePreview:
    collateral_item_id: int
    principal_base: Decimal
    monthly_interest_rate: Decimal
    period_fraction: Decimal
    unrounded_interest: Decimal
    calculated_interest: Decimal
    advance_interest_applied: Decimal
    recognized_interest: Decimal


@dataclass(frozen=True)
class AccrualFinalizationResult:
    accrual: PawnLoanInterestAccrual
    accounting_event: PawnLoanAccountingEvent | None
    outbox: object | None
    already_finalized: bool = False


@dataclass(frozen=True)
class CapitalizationResult:
    accounting_event: PawnLoanAccountingEvent
    outbox: object
    amount: Decimal
    already_recorded: bool = False


def preview_pawn_loan_accruals(
    loan_id: int,
    *,
    as_of_date: date,
    include_partial: bool = True,
) -> tuple[AccrualPeriodPreview, ...]:
    loan = _tenant_loan(loan_id)
    if loan.state != PawnLoanState.ACTIVE.value:
        raise PawnInterestError("Only an active PawnLoan can accrue interest.")
    policy = loan.policy_snapshot
    last_finalized = (
        loan.interest_accruals.exclude(
            release_catch_up__reversal__isnull=False
        )
        .order_by("-period_number")
        .first()
    )
    capitalized_boundaries = _capitalized_boundaries(loan)
    if (
        last_finalized
        and policy.interest_method == InterestMethod.COMPOUND.value
        and (
            last_finalized.period_number
            % policy.capitalization_interval_periods
            == 0
        )
        and last_finalized.period_number not in capitalized_boundaries
    ):
        return ()
    previews = []
    pending_advance_applied = {}
    if last_finalized:
        period_number = last_finalized.period_number + 1
        period_start = last_finalized.period_end + timedelta(days=1)
    else:
        period_number = 1
        period_start = loan.loan_date
    while True:
        exclusive_end = _add_months(period_start, 1)
        completed_end = exclusive_end - timedelta(days=1)
        if completed_end <= as_of_date:
            period_end = completed_end
            fraction = Decimal("1")
            is_partial = False
        elif include_partial and period_start <= as_of_date:
            period_end = as_of_date
            fraction = _partial_fraction(policy, period_start, period_end)
            is_partial = True
        else:
            break

        balance = get_pawn_loan_balance(loan.pk, as_of_date=period_start)
        base = balance.principal_outstanding
        lines = _itemized_accrual_lines(
            loan,
            as_of_date=period_start,
            period_fraction=fraction,
            aggregate_balance=balance,
            currency_quantum=policy.currency_quantum,
            pending_advance_applied=pending_advance_applied,
        )
        if lines:
            base = sum((line.principal_base for line in lines), Decimal("0"))
            unrounded = sum(
                (line.unrounded_interest for line in lines), Decimal("0")
            )
            calculated = sum(
                (line.calculated_interest for line in lines), Decimal("0")
            )
            advance_applied = sum(
                (line.advance_interest_applied for line in lines), Decimal("0")
            )
            recognized = sum(
                (line.recognized_interest for line in lines), Decimal("0")
            )
            for line in lines:
                pending_advance_applied[line.collateral_item_id] = (
                    pending_advance_applied.get(
                        line.collateral_item_id, Decimal("0")
                    )
                    + line.advance_interest_applied
                )
        else:
            unrounded, recognized = calculate_accrual_interest(
                calculation_base=base,
                monthly_interest_rate=loan.monthly_interest_rate,
                period_fraction=fraction,
                currency_quantum=policy.currency_quantum,
            )
            calculated = recognized
            advance_applied = Decimal("0")
        previews.append(
            AccrualPeriodPreview(
                period_number=period_number,
                period_start=period_start,
                period_end=period_end,
                period_fraction=fraction,
                calculation_base=base,
                unrounded_interest=unrounded,
                recognized_interest=recognized,
                is_partial=is_partial,
                calculated_interest=calculated,
                advance_interest_applied=advance_applied,
                lines=lines,
            )
        )

        if is_partial:
            break
        if (
            policy.interest_method == InterestMethod.COMPOUND.value
            and period_number % policy.capitalization_interval_periods == 0
            and period_number not in capitalized_boundaries
        ):
            break
        period_number += 1
        period_start = exclusive_end
    return tuple(previews)


def calculate_accrual_interest(
    *,
    calculation_base,
    monthly_interest_rate,
    period_fraction,
    currency_quantum,
):
    """Retain calculation precision and round only the finalized period amount."""
    base = Decimal(str(calculation_base))
    rate = Decimal(str(monthly_interest_rate))
    fraction = Decimal(str(period_fraction))
    quantum = Decimal(str(currency_quantum))
    if base < 0 or rate < 0 or not Decimal("0") < fraction <= Decimal("1"):
        raise PawnInterestError("Accrual calculation inputs are outside policy bounds.")
    unrounded = base * rate / Decimal("100") * fraction
    return unrounded, unrounded.quantize(quantum, rounding=ROUND_HALF_UP)


def _itemized_accrual_lines(
    loan,
    *,
    as_of_date,
    period_fraction,
    aggregate_balance,
    currency_quantum,
    pending_advance_applied,
):
    try:
        disbursal = loan.disbursal_snapshot
    except PawnLoanDisbursalSnapshot.DoesNotExist:
        opening_event = loan.accounting_events.filter(
            event_kind=TransactionKind.RENEWAL_OPENING.value,
            reversed_by_event__isnull=True,
        ).first()
        opening_lines = (
            tuple(opening_event.principal_opening_lines.order_by("allocation_order"))
            if opening_event
            else ()
        )
        tranches = tuple(
            {
                "collateral_item_id": line.collateral_item_id,
                "allocated_principal": line.principal_opened,
                "monthly_interest_rate": line.monthly_interest_rate,
                "advance_interest": Decimal("0"),
            }
            for line in opening_lines
        )
    else:
        tranches = tuple(disbursal.evidence.get("tranches") or ())
    if not tranches:
        raise PawnInterestError(
            "Itemized PawnLoan is missing frozen opening tranche evidence."
        )
    try:
        principal_balances = {
            item.collateral_item_id: item
            for item in get_pawn_principal_tranche_balances(
                loan, as_of_date=as_of_date
            )
        }
    except PawnTrancheBalanceError as exc:
        raise PawnInterestError(str(exc)) from exc
    consumed = {
        row["collateral_item_id"]: row["total"] or Decimal("0")
        for row in (
            PawnLoanInterestAccrualLine.objects.filter(accrual__loan=loan)
            .exclude(
                accrual__accounting_event__reversed_by_event__isnull=False
            )
            .values("collateral_item_id")
            .annotate(total=Sum("advance_interest_applied"))
        )
    }
    lines = []
    for tranche in tranches:
        try:
            item_id = int(tranche["collateral_item_id"])
            rate = Decimal(str(tranche["monthly_interest_rate"]))
            advance_total = Decimal(str(tranche["advance_interest"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise PawnInterestError(
                "Frozen disbursal tranche evidence is incomplete."
            ) from exc
        if item_id not in principal_balances:
            raise PawnInterestError(
                "Frozen disbursal tranche references collateral outside this PawnLoan."
            )
        principal_balance = principal_balances[item_id]
        if principal_balance.monthly_interest_rate != rate:
            raise PawnInterestError(
                "Reconstructed item rate differs from frozen disbursal evidence."
            )
        principal_base = principal_balance.principal_outstanding
        already_applied = consumed.get(item_id, Decimal("0")) + (
            pending_advance_applied.get(item_id, Decimal("0"))
        )
        remaining_advance = max(advance_total - already_applied, Decimal("0"))
        unrounded, calculated = calculate_accrual_interest(
            calculation_base=principal_base,
            monthly_interest_rate=rate,
            period_fraction=period_fraction,
            currency_quantum=currency_quantum,
        )
        advance_applied = min(remaining_advance, calculated)
        lines.append(
            AccrualLinePreview(
                collateral_item_id=item_id,
                principal_base=principal_base,
                monthly_interest_rate=rate,
                period_fraction=Decimal(str(period_fraction)),
                unrounded_interest=unrounded,
                calculated_interest=calculated,
                advance_interest_applied=advance_applied,
                recognized_interest=calculated - advance_applied,
            )
        )
    quantum = Decimal(str(currency_quantum))
    item_base = sum((line.principal_base for line in lines), Decimal("0"))
    if aggregate_balance.capitalized_interest_principal_outstanding:
        raise PawnInterestError(
            "Capitalized principal lacks immutable item attribution; "
            "itemized accrual cannot continue yet."
        )
    if item_base.quantize(quantum) != Decimal(
        str(aggregate_balance.original_principal_outstanding)
    ).quantize(quantum):
        raise PawnInterestError(
            "Collateral principal does not reconcile to immutable item allocations."
        )
    return tuple(lines)


@transaction.atomic
def finalize_pawn_loan_accrual(
    loan_id: int,
    *,
    period_number: int,
    actor=None,
    delivery_handler: DeliveryHandler | None = None,
) -> AccrualFinalizationResult:
    loan = _locked_loan(loan_id)
    existing = loan.interest_accruals.filter(period_number=period_number).first()
    if existing:
        event = existing.accounting_event
        return AccrualFinalizationResult(
            existing,
            event,
            event.outbox if event else None,
            True,
        )
    if period_number < 1:
        raise PawnInterestError("Accrual period number must be positive.")
    if loan.state != PawnLoanState.ACTIVE.value:
        raise PawnInterestError("Only an active PawnLoan can accrue interest.")

    try:
        assert_pawn_loan_financial_actions_allowed(loan.pk)
        candidates = preview_pawn_loan_accruals(
            loan.pk,
            as_of_date=timezone.localdate(),
            include_partial=False,
        )
        preview = candidates[0] if candidates else None
        if preview is None or preview.period_number != period_number:
            raise PawnInterestError(
                "The requested period is not the next eligible completed period."
            )
        policy = loan.policy_snapshot
        if (
            preview.calculated_interest > 0
            and policy.accounting_recognition == AccountingRecognition.ACCRUAL.value
        ):
            require_pawn_loan_accounting_readiness(
                loan,
                effective_date=preview.period_end,
                requires_interest_receivable=preview.recognized_interest > 0,
                requires_unearned_interest=preview.advance_interest_applied > 0,
            )
    except PawnInterestError:
        raise
    except Exception as exc:
        raise PawnInterestError(str(exc)) from exc

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
        from_state=PawnLoanState.ACTIVE.value,
        to_state=PawnLoanState.ACTIVE.value,
        actor=actor,
        metadata={
            "period_number": preview.period_number,
            "period_start": preview.period_start.isoformat(),
            "period_end": preview.period_end.isoformat(),
            "period_fraction": _decimal_string(preview.period_fraction),
            "calculation_base": _decimal_string(preview.calculation_base),
            "unrounded_interest": _decimal_string(preview.unrounded_interest),
            "recognized_interest": _decimal_string(preview.recognized_interest),
            "calculated_interest": _decimal_string(preview.calculated_interest),
            "advance_interest_applied": _decimal_string(
                preview.advance_interest_applied
            ),
            "accounting_event_id": event.pk if event else None,
            "outbox_id": outbox.pk if outbox else None,
        },
    )
    return AccrualFinalizationResult(accrual, event, outbox)


def persist_pawn_accrual_lines(accrual, preview):
    """Persist the immutable item calculations behind an accrual header."""
    for line in preview.lines:
        PawnLoanInterestAccrualLine.objects.create(
            accrual=accrual,
            collateral_item_id=line.collateral_item_id,
            principal_base=line.principal_base,
            monthly_interest_rate=line.monthly_interest_rate,
            period_fraction=line.period_fraction,
            unrounded_interest=line.unrounded_interest,
            calculated_interest=line.calculated_interest,
            advance_interest_applied=line.advance_interest_applied,
            recognized_interest=line.recognized_interest,
        )


def should_record_pawn_accrual_event(preview, policy):
    return preview.recognized_interest > 0 or (
        preview.advance_interest_applied > 0
        and policy.accounting_recognition == AccountingRecognition.ACCRUAL.value
    )


@transaction.atomic
def capitalize_pawn_loan_interest(
    loan_id: int,
    *,
    through_period_number: int,
    actor=None,
    delivery_handler: DeliveryHandler | None = None,
) -> CapitalizationResult:
    loan = _locked_loan(loan_id)
    existing = loan.accounting_events.filter(
        event_kind=TransactionKind.INTEREST_CAPITALIZATION.value,
        payload__capitalization__through_period_number=through_period_number,
    ).first()
    if existing:
        return CapitalizationResult(
            existing,
            existing.outbox,
            Decimal(existing.payload["values"]["interest"]),
            True,
        )
    policy = loan.policy_snapshot
    if policy.interest_method != InterestMethod.COMPOUND.value:
        raise PawnInterestError("Only a compound PawnLoan can capitalize interest.")
    if through_period_number % policy.capitalization_interval_periods:
        raise PawnInterestError("Capitalization is not due at this accrual period.")
    try:
        assert_pawn_loan_financial_actions_allowed(loan.pk)
        boundary = loan.interest_accruals.get(period_number=through_period_number)
        balance = get_pawn_loan_balance(loan.pk, as_of_date=boundary.period_end)
        amount = balance.interest_outstanding
        if amount <= 0:
            raise PawnInterestError("There is no unpaid interest to capitalize.")
        if policy.accounting_recognition == AccountingRecognition.ACCRUAL.value:
            require_pawn_loan_accounting_readiness(
                loan,
                effective_date=boundary.period_end,
                requires_interest_receivable=True,
            )
    except PawnLoanInterestAccrual.DoesNotExist as exc:
        raise PawnInterestError(
            "The capitalization boundary accrual has not been finalized."
        ) from exc
    except PawnInterestError:
        raise
    except Exception as exc:
        raise PawnInterestError(str(exc)) from exc

    payload = capitalization_payload(
        loan,
        effective_date=boundary.period_end,
        interest_amount=amount,
    ).to_dict()
    payload["capitalization"] = {
        "through_period_number": through_period_number,
        "capitalization_interval_periods": policy.capitalization_interval_periods,
        "accounting_recognition": policy.accounting_recognition,
    }
    event, outbox = record_loan_accounting_event(
        loan.pk,
        event_kind=TransactionKind.INTEREST_CAPITALIZATION,
        effective_date=boundary.period_end,
        payload=payload,
        actor=actor,
        delivery_handler=delivery_handler,
    )
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.INTEREST_CAPITALIZED.value,
        from_state=PawnLoanState.ACTIVE.value,
        to_state=PawnLoanState.ACTIVE.value,
        actor=actor,
        metadata={
            "through_period_number": through_period_number,
            "amount": _decimal_string(amount),
            "accounting_event_id": event.pk,
            "outbox_id": outbox.pk,
        },
    )
    return CapitalizationResult(event, outbox, amount)


def _tenant_loan(loan_id):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnInterestError("PawnLoan interest requires an active tenant schema.")
    try:
        return PawnLoan.objects.select_related("policy_snapshot").get(
            pk=loan_id,
            workspace_id=workspace_id,
        )
    except PawnLoan.DoesNotExist as exc:
        raise PawnInterestError("PawnLoan was not found in the active workspace.") from exc


def _locked_loan(loan_id):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnInterestError("PawnLoan interest requires an active tenant schema.")
    try:
        return PawnLoan.objects.select_for_update().get(
            pk=loan_id,
            workspace_id=workspace_id,
        )
    except PawnLoan.DoesNotExist as exc:
        raise PawnInterestError("PawnLoan was not found in the active workspace.") from exc


def _partial_fraction(policy, period_start, period_end):
    if policy.partial_month_method == PartialMonthMethod.FULL_MONTH.value:
        return Decimal("1")
    elapsed_days = (period_end - period_start).days + 1
    if elapsed_days <= policy.partial_month_cutoff_days:
        return Decimal(str(policy.partial_month_lower_fraction))
    return Decimal("1")


def _capitalized_boundaries(loan):
    return {
        int(event.payload["capitalization"]["through_period_number"])
        for event in loan.accounting_events.filter(
            event_kind=TransactionKind.INTEREST_CAPITALIZATION.value
        )
        if event.payload.get("capitalization")
    }


def build_pawn_accrual_detail(preview, policy):
    return {
        "period_number": preview.period_number,
        "period_start": preview.period_start.isoformat(),
        "period_end": preview.period_end.isoformat(),
        "period_fraction": _decimal_string(preview.period_fraction),
        "calculation_base": _decimal_string(preview.calculation_base),
        "unrounded_interest": _decimal_string(preview.unrounded_interest),
        "recognized_interest": _decimal_string(preview.recognized_interest),
        "calculated_interest": _decimal_string(preview.calculated_interest),
        "advance_interest_applied": _decimal_string(
            preview.advance_interest_applied
        ),
        "lines": [
            {
                "collateral_item_id": line.collateral_item_id,
                "principal_base": _decimal_string(line.principal_base),
                "monthly_interest_rate": _decimal_string(
                    line.monthly_interest_rate
                ),
                "period_fraction": _decimal_string(line.period_fraction),
                "unrounded_interest": _decimal_string(
                    line.unrounded_interest
                ),
                "calculated_interest": _decimal_string(
                    line.calculated_interest
                ),
                "advance_interest_applied": _decimal_string(
                    line.advance_interest_applied
                ),
                "recognized_interest": _decimal_string(
                    line.recognized_interest
                ),
            }
            for line in preview.lines
        ],
        "is_partial": preview.is_partial,
        "accounting_recognition": policy.accounting_recognition,
    }


def _add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _decimal_string(value):
    return format(Decimal(value).normalize(), "f")
