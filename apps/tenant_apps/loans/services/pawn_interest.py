"""Monthly PawnLoan interest preview, finalization, and capitalization."""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.tenant_apps.loans.services.action_access import require_loan_action
from apps.tenant_apps.loans.domain import (
    InterestMethod,
    PartialMonthMethod,
    PawnLoanEventKind,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.domain.interest import (
    InterestCalculationError,
    calculate_period_interest,
)
from apps.tenant_apps.loans.domain.monthly_contract import POLICY_VERSION, period_dates
from apps.tenant_apps.loans.integrations import accrual_payload, capitalization_payload
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    PawnLoan,
    PawnLoanEvent,
    PawnLoanInterestAccrual,
    PawnLoanInterestAccrualLine,
    current_tenant_workspace_id,
)
from apps.tenant_apps.loans.selectors import get_pawn_loan_balance
from apps.tenant_apps.loans.services.event_recording import (
    record_loan_event,
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
    loan_event: PawnLoanEvent | None
    already_finalized: bool = False


@dataclass(frozen=True)
class CapitalizationResult:
    loan_event: PawnLoanEvent
    amount: Decimal
    already_recorded: bool = False


def preview_pawn_loan_accruals(
    loan_id: int,
    *,
    as_of_date: date,
    include_partial: bool = True,
    known_through: date | None = None,
) -> tuple[AccrualPeriodPreview, ...]:
    loan = _tenant_loan(loan_id)
    from .recorded_collections import recording_for
    if recording_for(loan):
        # This profile recognizes cumulative anniversary charges at collection;
        # it does not manufacture completed calendar-period accrual rows.
        return ()
    if loan.loan_events.filter(event_kind="MIGRATION_OPENING").exists():
        raise PawnInterestError("Migration opening interest continuation is not enabled; historical periods cannot be replayed.")
    if loan.state != PawnLoanState.ACTIVE.value:
        raise PawnInterestError("Only an active PawnLoan can accrue interest.")
    policy = loan.policy_snapshot
    if policy is None:
        raise PawnInterestError("Loan is missing its frozen disbursal policy.")
    if known_through is not None and (policy.policy_version != POLICY_VERSION or
            not loan.loan_date <= known_through <= as_of_date):
        raise PawnInterestError("Forecast knowledge must be within the supported shared contract dates.")
    known_through = known_through or as_of_date
    # SQL DecimalFields return 0.0100. New minimum-first-month policies use
    # its numeric precision (paise), retaining the historic calculation for
    # earlier frozen snapshots.
    quantum = policy.currency_quantum.normalize() if (
        policy.minimum_first_month or policy.basis == "RECORDED_CONTRACT" or policy.policy_version == POLICY_VERSION
    ) else policy.currency_quantum
    eligible_accruals = loan.interest_accruals
    if policy.policy_version == POLICY_VERSION:
        eligible_accruals = eligible_accruals.filter(period_end__lte=known_through)
        if eligible_accruals.filter(loan_event__reversed_by_event__effective_date__lte=known_through).exclude(
                release_catch_up__reversal__isnull=False).exists():
            raise PawnInterestError("Review the reversed monthly charge before continuing this loan; its retained calculation cannot be silently reused.")
    last_finalized = (
        eligible_accruals.exclude(
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
        if policy.policy_version == POLICY_VERSION:
            period_start, completed_end = period_dates(loan.loan_date, period_number)
            exclusive_end = completed_end + timedelta(days=1)
        else:
            exclusive_end = _add_months(period_start, 1)
            completed_end = exclusive_end - timedelta(days=1)
        if completed_end <= as_of_date:
            period_end = completed_end
            fraction = Decimal("1")
            is_partial = False
        elif include_partial and period_start <= as_of_date:
            period_end = as_of_date
            fraction = _partial_fraction(policy, period_start, period_end, period_number=period_number,
                original_date=loan.loan_date)
            is_partial = True
        else:
            break

        basis_date = period_start - timedelta(days=1) if policy.policy_version == POLICY_VERSION and period_number > 1 else period_start
        if policy.policy_version == POLICY_VERSION:
            basis_date = min(basis_date, known_through)
        balance = get_pawn_loan_balance(loan.pk, as_of_date=basis_date)
        base = balance.principal_outstanding
        lines = _itemized_accrual_lines(
            loan,
            as_of_date=basis_date,
            period_fraction=fraction,
            aggregate_balance=balance,
            currency_quantum=quantum,
            pending_advance_applied=pending_advance_applied,
            use_original_principal=policy.policy_version == POLICY_VERSION and period_number == 1,
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
                currency_quantum=quantum,
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
    try:
        return calculate_period_interest(
            calculation_base=calculation_base,
            monthly_interest_rate=monthly_interest_rate,
            period_fraction=period_fraction,
            currency_quantum=currency_quantum,
        )
    except InterestCalculationError as exc:
        raise PawnInterestError(str(exc)) from exc


def _itemized_accrual_lines(
    loan,
    *,
    as_of_date,
    period_fraction,
    aggregate_balance,
    currency_quantum,
    pending_advance_applied,
    use_original_principal=False,
):
    from apps.tenant_apps.loans.selectors.disbursal import effective_disbursal_snapshot
    disbursal = effective_disbursal_snapshot(loan, as_of_date=as_of_date)
    if disbursal is None:
        opening_event = loan.loan_events.filter(
            event_kind=TransactionKind.RENEWAL_OPENING.value,
            reversed_by_event__isnull=True,
        ).first()
        opening_lines = (
            tuple(opening_event.principal_opening_lines.order_by("allocation_order"))
            if opening_event
            else ()
        )
        opening_economics = (
            (opening_event.payload.get("renewal") or {}).get(
                "successor_economics"
            )
            if opening_event
            else None
        ) or {}
        opening_tranches = {
            int(item["collateral_item_id"]): item
            for item in opening_economics.get("tranches", ())
            if item.get("collateral_item_id") is not None
        }
        tranches = tuple(
            {
                "collateral_item_id": line.collateral_item_id,
                "allocated_principal": line.principal_opened,
                "monthly_interest_rate": line.monthly_interest_rate,
                "advance_interest": Decimal(
                    str(
                        opening_tranches.get(line.collateral_item_id, {}).get(
                            "advance_interest",
                            "0",
                        )
                    )
                ),
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
            PawnLoanInterestAccrualLine.objects.filter(accrual__loan=loan,
                **({"accrual__period_end__lte": as_of_date} if loan.policy_snapshot.policy_version == POLICY_VERSION else {}))
            .exclude(
                accrual__loan_event__reversed_by_event__isnull=False
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
        principal_base = Decimal(str(tranche["allocated_principal"])) if use_original_principal else principal_balance.principal_outstanding
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
    principal_quantum = Decimal("0.01") if loan.policy_snapshot.policy_version == POLICY_VERSION else quantum
    if item_base.quantize(principal_quantum) != Decimal(
        str(loan.principal_amount if use_original_principal else aggregate_balance.original_principal_outstanding)
    ).quantize(principal_quantum):
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
) -> AccrualFinalizationResult:
    loan = _locked_loan(loan_id)
    require_loan_action(loan, actor, "loan.accrue")
    from .recorded_collections import recording_for
    if recording_for(loan):
        raise PawnInterestError("This recorded contract recognizes anniversary interest with collection.")
    if loan.loan_events.filter(event_kind="MIGRATION_OPENING").exists():
        raise PawnInterestError("Opening collection catch-up is posted only within full release, not native period finalization.")
    existing = loan.interest_accruals.filter(period_number=period_number).first()
    if existing:
        event = existing.loan_event
        if loan.policy_snapshot.policy_version == POLICY_VERSION and event and hasattr(event, "reversed_by_event"):
            raise PawnInterestError("This monthly charge was reversed. Review its correction before recognizing it again.")
        return AccrualFinalizationResult(
            existing,
            event,
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
            include_partial=started_month_charge_allowed(loan.policy_snapshot),
        )
        preview = candidates[0] if candidates else None
        if preview is None or preview.period_number != period_number:
            raise PawnInterestError(
                "The requested period is not the next eligible monthly charge."
            )
        policy = loan.policy_snapshot
    except PawnInterestError:
        raise
    except Exception as exc:
        raise PawnInterestError(str(exc)) from exc

    return _persist_accrual_preview(loan, preview, actor=actor)


def _persist_accrual_preview(loan, preview, *, actor):
    """Validated atomic caller owns authorization and the aggregate lock."""
    if loan.policy_snapshot.policy_version == POLICY_VERSION and loan.interest_accruals.filter(period_number=preview.period_number).exists():
        raise PawnInterestError("This monthly period retains an earlier recognition. Review its correction before recording a replacement charge.")
    event = None
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
        event, _ = record_loan_event(
            loan.pk,
            event_kind=TransactionKind.INTEREST_ACCRUAL,
            effective_date=preview.period_end,
            payload=payload,
            actor=actor,
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
        loan_event=event,
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
            "loan_event_id": event.pk if event else None,
        },
    )
    return AccrualFinalizationResult(accrual, event)


def started_month_charge_allowed(policy):
    return bool(policy and policy.policy_version == POLICY_VERSION and
                policy.interest_method == "SIMPLE" and policy.partial_month_method == "FULL_MONTH")


def monthly_collection_balance(loan, on):
    from dataclasses import replace
    balance = get_pawn_loan_balance(loan, as_of_date=on)
    extra = sum((row.recognized_interest for row in preview_pawn_loan_accruals(loan.pk, as_of_date=on)), Decimal("0"))
    return replace(balance, interest_outstanding=balance.interest_outstanding + extra,
        current_interest_outstanding=balance.current_interest_outstanding + (Decimal("0") if on > balance.due_date else extra),
        overdue_interest_outstanding=balance.overdue_interest_outstanding + (extra if on > balance.due_date else Decimal("0")),
        total_due=balance.total_due + extra, closure_ready=balance.closure_ready and extra == 0)


def recognize_due_monthly_interest(loan, on, *, actor, include_partial=True):
    """Native monthly recognition inside an authorized, locked repayment command."""
    if started_month_charge_allowed(loan.policy_snapshot):
        pending = preview_pawn_loan_accruals(loan.pk, as_of_date=on, include_partial=include_partial)
        if not include_partial or any(row.recognized_interest > 0 for row in pending):
            for row in pending:
                _persist_accrual_preview(loan, row, actor=actor)


def persist_pawn_accrual_lines(accrual, preview):
    """Persist the immutable item calculations behind an accrual header."""
    for line in preview.lines:
        PawnLoanInterestAccrualLine.objects.create(
            accrual=accrual,
            collateral_item_id=line.collateral_item_id,
            principal_base=line.principal_base,
            monthly_interest_rate=line.monthly_interest_rate,
            # Fixed-precision row projections; full computed values are retained
            # in build_pawn_accrual_detail before these rows are persisted.
            period_fraction=line.period_fraction.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
            unrounded_interest=line.unrounded_interest.quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_UP),
            calculated_interest=line.calculated_interest,
            advance_interest_applied=line.advance_interest_applied,
            recognized_interest=line.recognized_interest,
        )


def should_record_pawn_accrual_event(preview, policy):
    return preview.recognized_interest > 0


@transaction.atomic
def capitalize_pawn_loan_interest(
    loan_id: int,
    *,
    through_period_number: int,
    actor=None,
) -> CapitalizationResult:
    loan = _locked_loan(loan_id)
    require_loan_action(loan, actor, "loan.capitalize")
    existing = loan.loan_events.filter(
        event_kind=TransactionKind.INTEREST_CAPITALIZATION.value,
        payload__capitalization__through_period_number=through_period_number,
    ).first()
    if existing:
        return CapitalizationResult(
            existing,
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
    }
    event, _ = record_loan_event(
        loan.pk,
        event_kind=TransactionKind.INTEREST_CAPITALIZATION,
        effective_date=boundary.period_end,
        payload=payload,
        actor=actor,
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
            "loan_event_id": event.pk,
        },
    )
    return CapitalizationResult(event, amount)


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


def _partial_fraction(policy, period_start, period_end, *, period_number=1, original_date=None):
    from apps.tenant_apps.loans.domain.interest import partial_period_fraction
    if getattr(policy, "policy_version", 1) == POLICY_VERSION:
        if original_date is None:
            # Derive the original anchor only from the related frozen loan.
            original_date = policy.loan.loan_date
        start, end = period_dates(original_date, period_number)
        if start != period_start or not start <= period_end <= end:
            raise PawnInterestError("Accrual dates do not match the frozen inclusive monthly contract.")
        days = (end - start).days + 1
    else:
        days = (_add_months(period_start, 1) - period_start).days
    return partial_period_fraction(
        method=policy.partial_month_method,
        elapsed_days=(period_end - period_start).days + 1,
        period_days=days,
        minimum_first_month=policy.minimum_first_month,
        period_number=period_number,
        cutoff_days=policy.partial_month_cutoff_days,
        lower_fraction=policy.partial_month_lower_fraction,
    )


def _capitalized_boundaries(loan):
    return {
        int(event.payload["capitalization"]["through_period_number"])
        for event in loan.loan_events.filter(
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
    }


def _add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _decimal_string(value):
    return format(Decimal(value).normalize(), "f")
