"""Current-date PawnLoan repayment allocation and source-event workflow."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.loans.domain import (
    AccountingRecognition,
    PawnLoanEventKind,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.integrations import repayment_payload
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    PawnLoan,
    PawnLoanAccountingEvent,
    PawnLoanAccountingOutbox,
    PawnLoanRepaymentAllocationLine,
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


class PawnRepaymentError(ValueError):
    pass


@dataclass(frozen=True)
class RepaymentAllocation:
    amount_received: Decimal
    fees: Decimal
    overdue_interest: Decimal
    current_interest: Decimal
    principal: Decimal

    @property
    def interest(self):
        return self.overdue_interest + self.current_interest


@dataclass(frozen=True)
class PawnRepaymentResult:
    loan: PawnLoan
    allocation: RepaymentAllocation
    accounting_event: PawnLoanAccountingEvent
    outbox: PawnLoanAccountingOutbox
    already_recorded: bool = False
    item_allocations: tuple["ItemPrincipalAllocation", ...] = ()


@dataclass(frozen=True)
class ItemPrincipalAllocation:
    collateral_item_id: int
    allocation_order: int
    monthly_interest_rate: Decimal
    balance_before: Decimal
    principal_applied: Decimal
    balance_after: Decimal


@transaction.atomic
def record_pawn_loan_repayment(
    loan_id: int,
    *,
    amount,
    request_key: str,
    actor=None,
    delivery_handler: DeliveryHandler | None = None,
) -> PawnRepaymentResult:
    loan = _locked_loan(loan_id)
    request_key = _request_key(request_key)
    amount = _money_amount(amount, loan)
    existing = _existing_result(loan, request_key, amount)
    if existing:
        return existing
    if loan.state != PawnLoanState.ACTIVE.value:
        raise PawnRepaymentError("Only an active PawnLoan can receive repayment.")

    try:
        assert_pawn_loan_financial_actions_allowed(loan.pk)
        effective_date = timezone.localdate()
        balance = get_pawn_loan_balance(loan.pk, as_of_date=effective_date)
        allocation = allocate_repayment(balance, amount)
        policy = loan.policy_snapshot
        recognition = policy.accounting_recognition
        require_pawn_loan_accounting_readiness(
            loan,
            effective_date=effective_date,
            requires_fee_income=allocation.fees > 0,
            requires_interest_receivable=(
                recognition == AccountingRecognition.ACCRUAL.value
                and allocation.interest > 0
            ),
        )
    except PawnRepaymentError:
        raise
    except Exception as exc:
        raise PawnRepaymentError(str(exc)) from exc

    capitalized_principal = min(
        allocation.principal,
        balance.capitalized_interest_principal_outstanding,
    )
    original_principal = allocation.principal - capitalized_principal
    item_allocations = allocate_repayment_principal_to_tranches(
        loan,
        original_principal,
        expected_outstanding=balance.original_principal_outstanding,
    )
    payload = repayment_payload(
        loan,
        effective_date=effective_date,
        principal_amount=allocation.principal,
        interest_amount=allocation.interest,
        overdue_interest_amount=allocation.overdue_interest,
        current_interest_amount=allocation.current_interest,
        fee_amount=allocation.fees,
        original_principal_amount=original_principal,
        capitalized_interest_principal_amount=capitalized_principal,
    ).to_dict()
    payload["repayment"] = {
        "request_key": request_key,
        "amount_received": _decimal_string(allocation.amount_received),
        "allocation_order": [
            "fees",
            "overdue_interest",
            "current_interest",
            "principal",
        ],
        "accounting_recognition": recognition,
        "item_principal_allocation_order": "HIGHEST_MONTHLY_RATE_FIRST",
        "item_principal_allocations": [
            {
                "collateral_item_id": item.collateral_item_id,
                "allocation_order": item.allocation_order,
                "monthly_interest_rate": _decimal_string(
                    item.monthly_interest_rate
                ),
                "balance_before": _decimal_string(item.balance_before),
                "principal_applied": _decimal_string(item.principal_applied),
                "balance_after": _decimal_string(item.balance_after),
            }
            for item in item_allocations
        ],
    }
    event, outbox = record_loan_accounting_event(
        loan.pk,
        event_kind=TransactionKind.REPAYMENT,
        effective_date=effective_date,
        payload=payload,
        actor=actor,
        delivery_handler=delivery_handler,
    )
    for item in item_allocations:
        PawnLoanRepaymentAllocationLine.objects.create(
            accounting_event=event,
            collateral_item_id=item.collateral_item_id,
            allocation_order=item.allocation_order,
            monthly_interest_rate=item.monthly_interest_rate,
            balance_before=item.balance_before,
            principal_applied=item.principal_applied,
            balance_after=item.balance_after,
        )
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.REPAYMENT_RECORDED.value,
        from_state=PawnLoanState.ACTIVE.value,
        to_state=PawnLoanState.ACTIVE.value,
        actor=actor,
        metadata={
            "request_key": request_key,
            "amount_received": _decimal_string(allocation.amount_received),
            "allocation": {
                "fees": _decimal_string(allocation.fees),
                "overdue_interest": _decimal_string(allocation.overdue_interest),
                "current_interest": _decimal_string(allocation.current_interest),
                "principal": _decimal_string(allocation.principal),
            },
            "accounting_event_id": event.pk,
            "outbox_id": outbox.pk,
        },
    )
    return PawnRepaymentResult(
        loan,
        allocation,
        event,
        outbox,
        item_allocations=item_allocations,
    )


def allocate_repayment_principal_to_tranches(
    loan,
    principal_amount,
    *,
    expected_outstanding,
) -> tuple[ItemPrincipalAllocation, ...]:
    """Allocate original principal to highest-rate collateral first."""
    amount = Decimal(str(principal_amount))
    if amount < 0:
        raise PawnRepaymentError("Item principal allocation cannot be negative.")
    try:
        balances = get_pawn_principal_tranche_balances(loan)
    except PawnTrancheBalanceError as exc:
        raise PawnRepaymentError(str(exc)) from exc
    if not balances:
        return ()
    total_outstanding = sum(
        (item.principal_outstanding for item in balances), Decimal("0")
    )
    if total_outstanding != Decimal(str(expected_outstanding)):
        raise PawnRepaymentError(
            "Item principal balances do not reconcile to original principal outstanding."
        )
    if amount == 0:
        return ()
    remaining = amount
    results = []
    ordered = sorted(
        balances,
        key=lambda item: (-item.monthly_interest_rate, item.collateral_item_id),
    )
    for order, item in enumerate(ordered, start=1):
        applied = min(remaining, item.principal_outstanding)
        results.append(
            ItemPrincipalAllocation(
                collateral_item_id=item.collateral_item_id,
                allocation_order=order,
                monthly_interest_rate=item.monthly_interest_rate,
                balance_before=item.principal_outstanding,
                principal_applied=applied,
                balance_after=item.principal_outstanding - applied,
            )
        )
        remaining -= applied
    if remaining:
        raise PawnRepaymentError(
            "Repayment principal exceeds itemized original principal outstanding."
        )
    return tuple(results)


def allocate_repayment(balance, amount: Decimal) -> RepaymentAllocation:
    """Allocate fees, overdue interest, current interest, then principal."""
    remaining = Decimal(amount)
    if remaining <= 0:
        raise PawnRepaymentError("Repayment amount must be positive.")
    fees = min(remaining, balance.fees_outstanding)
    remaining -= fees
    overdue_interest = min(remaining, balance.overdue_interest_outstanding)
    remaining -= overdue_interest
    current_interest = min(remaining, balance.current_interest_outstanding)
    remaining -= current_interest
    principal = min(remaining, balance.principal_outstanding)
    remaining -= principal
    if remaining:
        raise PawnRepaymentError(
            f"Repayment exceeds total due by {_decimal_string(remaining)}."
        )
    return RepaymentAllocation(amount, fees, overdue_interest, current_interest, principal)


def _locked_loan(loan_id):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnRepaymentError("PawnLoan repayment requires an active tenant schema.")
    try:
        return (
            PawnLoan.objects.select_for_update()
            .select_related("borrower")
            .get(pk=loan_id, workspace_id=workspace_id)
        )
    except PawnLoan.DoesNotExist as exc:
        raise PawnRepaymentError("PawnLoan was not found in the active workspace.") from exc


def _existing_result(loan, request_key, amount):
    event = loan.accounting_events.filter(
        event_kind=TransactionKind.REPAYMENT.value,
        payload__repayment__request_key=request_key,
    ).first()
    if event is None:
        return None
    recorded = Decimal(str(event.payload["repayment"]["amount_received"]))
    if recorded != amount:
        raise PawnRepaymentError(
            "Repayment request key was already used with a different amount."
        )
    values = event.payload["values"]
    allocation = RepaymentAllocation(
        amount_received=recorded,
        fees=Decimal(values.get("fees", "0")),
        overdue_interest=Decimal(values.get("overdue_interest", "0")),
        current_interest=Decimal(values.get("current_interest", "0")),
        principal=Decimal(values.get("principal", "0")),
    )
    item_allocations = tuple(
        ItemPrincipalAllocation(
            collateral_item_id=line.collateral_item_id,
            allocation_order=line.allocation_order,
            monthly_interest_rate=line.monthly_interest_rate,
            balance_before=line.balance_before,
            principal_applied=line.principal_applied,
            balance_after=line.balance_after,
        )
        for line in event.repayment_allocation_lines.order_by("allocation_order")
    )
    return PawnRepaymentResult(
        loan,
        allocation,
        event,
        event.outbox,
        already_recorded=True,
        item_allocations=item_allocations,
    )


def _request_key(value):
    value = str(value or "").strip()
    if not value or len(value) > 120:
        raise PawnRepaymentError(
            "A repayment request key of at most 120 characters is required."
        )
    return value


def _money_amount(value, loan):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PawnRepaymentError("Repayment amount must be a valid number.") from exc
    quantum = Decimal(str(loan.policy_snapshot.currency_quantum))
    rounded = amount.quantize(quantum)
    if amount != rounded:
        raise PawnRepaymentError(
            f"Repayment amount must use the currency precision {quantum}."
        )
    return rounded


def _decimal_string(value):
    return format(Decimal(value).normalize(), "f")
