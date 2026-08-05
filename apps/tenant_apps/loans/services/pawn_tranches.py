"""Reconstruct collateral principal balances from immutable source evidence."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import groupby

from apps.tenant_apps.loans.models import (
    PawnLoanDisbursalSnapshot,
    PawnLoanRepaymentAllocationLine,
)


class PawnTrancheBalanceError(ValueError):
    pass


@dataclass(frozen=True)
class PawnPrincipalTrancheBalance:
    collateral_item_id: int
    monthly_interest_rate: Decimal
    initial_principal: Decimal
    principal_outstanding: Decimal


def get_pawn_principal_tranche_balances(
    loan, *, as_of_date: date | None = None
) -> tuple[PawnPrincipalTrancheBalance, ...]:
    """Fold active repayment lines over the frozen disbursal allocations."""
    try:
        disbursal = loan.disbursal_snapshot
    except PawnLoanDisbursalSnapshot.DoesNotExist:
        return ()
    tranches = tuple(disbursal.evidence.get("tranches") or ())
    if not tranches:
        raise PawnTrancheBalanceError(
            "Itemized PawnLoan disbursal is missing frozen tranche evidence."
        )
    collateral_ids = set(loan.collateral_items.values_list("pk", flat=True))
    ordered_ids = []
    rates = {}
    initial = {}
    current = {}
    for tranche in tranches:
        try:
            item_id = int(tranche["collateral_item_id"])
            principal = Decimal(str(tranche["allocated_principal"]))
            rate = Decimal(str(tranche["monthly_interest_rate"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise PawnTrancheBalanceError(
                "Frozen disbursal tranche evidence is incomplete."
            ) from exc
        if item_id not in collateral_ids or item_id in current:
            raise PawnTrancheBalanceError(
                "Frozen disbursal tranche identities do not match this PawnLoan."
            )
        if principal < 0 or rate < 0:
            raise PawnTrancheBalanceError(
                "Frozen disbursal tranche amounts cannot be negative."
            )
        ordered_ids.append(item_id)
        rates[item_id] = rate
        initial[item_id] = principal
        current[item_id] = principal

    lines = (
        PawnLoanRepaymentAllocationLine.objects.filter(
            accounting_event__loan=loan,
            accounting_event__reversed_by_event__isnull=True,
        )
        .select_related("accounting_event")
        .order_by(
            "accounting_event__effective_date",
            "accounting_event_id",
            "allocation_order",
        )
    )
    if as_of_date is not None:
        lines = lines.filter(accounting_event__effective_date__lte=as_of_date)
    for _event_id, event_lines_iter in groupby(lines, key=lambda line: line.accounting_event_id):
        event_lines = tuple(event_lines_iter)
        event = event_lines[0].accounting_event
        values = event.payload.get("values") or {}
        expected_principal = Decimal(
            str(values.get("original_principal", values.get("principal", "0")))
        )
        if sum(
            (line.principal_applied for line in event_lines), Decimal("0")
        ) != expected_principal:
            raise PawnTrancheBalanceError(
                "Repayment allocation lines do not reconcile to event principal."
            )
        expected_order = sorted(
            current,
            key=lambda item_id: (-rates[item_id], item_id),
        )
        if [line.allocation_order for line in event_lines] != list(
            range(1, len(event_lines) + 1)
        ) or [line.collateral_item_id for line in event_lines] != expected_order:
            raise PawnTrancheBalanceError(
                "Repayment allocation lines violate highest-rate-first ordering."
            )
        for line in event_lines:
            item_id = line.collateral_item_id
            if item_id not in current:
                raise PawnTrancheBalanceError(
                    "Repayment allocation references unknown collateral."
                )
            if line.monthly_interest_rate != rates[item_id]:
                raise PawnTrancheBalanceError(
                    "Repayment allocation rate differs from frozen disbursal evidence."
                )
            if line.balance_before != current[item_id]:
                raise PawnTrancheBalanceError(
                    "Repayment allocation history has a discontinuous item balance."
                )
            if line.balance_before - line.principal_applied != line.balance_after:
                raise PawnTrancheBalanceError(
                    "Repayment allocation history does not reconcile."
                )
            current[item_id] = line.balance_after

    return tuple(
        PawnPrincipalTrancheBalance(
            collateral_item_id=item_id,
            monthly_interest_rate=rates[item_id],
            initial_principal=initial[item_id],
            principal_outstanding=current[item_id],
        )
        for item_id in ordered_ids
    )


__all__ = [
    "PawnPrincipalTrancheBalance",
    "PawnTrancheBalanceError",
    "get_pawn_principal_tranche_balances",
]
