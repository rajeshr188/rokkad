from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from apps.tenant_apps.loans.domain import RepaymentScheduleInput, ScheduleRateTranche
from apps.tenant_apps.loans.domain import (
    LoanAmortisationMethod,
    LoanRepaymentStructure,
    ObligationComponent,
)
from apps.tenant_apps.loans.models import (
    PawnLoan,
    PawnLoanAccountingEvent,
    ObligationAllocation,
    RepaymentObligation,
    RepaymentScheduleChange,
    RepaymentScheduleChangeKind,
    RepaymentScheduleVersion,
)
from apps.tenant_apps.loans.services.repayment_schedules import (
    generate_repayment_schedule,
    generate_shortened_installment_schedule,
)


class RepaymentObligationError(ValueError):
    pass


@dataclass(frozen=True)
class ObligationReconciliation:
    principal_scheduled: Decimal
    interest_scheduled: Decimal
    principal_allocated: Decimal
    interest_allocated: Decimal
    principal_remaining: Decimal
    interest_remaining: Decimal
    integrity_findings: tuple[str, ...]


@transaction.atomic
def persist_disbursal_repayment_schedule(
    loan: PawnLoan,
    *,
    source_event: PawnLoanAccountingEvent,
    disbursed_on,
    currency_quantum=Decimal("0.01"),
    actor=None,
):
    if source_event.loan_id != loan.pk:
        raise RepaymentObligationError("Schedule source event must belong to the loan.")
    product_version = loan.product_version
    collateral = tuple(loan.collateral_items.order_by("pk"))
    rate_tranches = ()
    if collateral and all(
        item.allocated_principal is not None and item.monthly_interest_rate is not None
        for item in collateral
    ):
        rate_tranches = tuple(
            ScheduleRateTranche(item.allocated_principal, item.monthly_interest_rate)
            for item in collateral
        )
    schedule = generate_repayment_schedule(RepaymentScheduleInput(
        repayment_structure=product_version.repayment_structure,
        amortisation_method=product_version.amortisation_method,
        disbursed_on=disbursed_on,
        principal=loan.principal_amount,
        monthly_interest_rate=loan.monthly_interest_rate,
        tenure_months=loan.tenure_months,
        currency_quantum=currency_quantum,
        rate_tranches=rate_tranches,
        contract_version=product_version.calculation_contract_version,
    ))
    existing = RepaymentScheduleVersion.objects.filter(source_event=source_event).first()
    if existing:
        if existing.fingerprint != schedule.fingerprint:
            raise RepaymentObligationError(
                "Disbursal event already has a different repayment schedule."
            )
        return existing
    version = RepaymentScheduleVersion.objects.create(
        workspace_id=loan.workspace_id,
        loan=loan,
        source_event=source_event,
        version=1,
        contract_version=schedule.contract_version,
        fingerprint=schedule.fingerprint,
        disbursed_on=schedule.disbursed_on,
        maturity_date=schedule.maturity_date,
        principal=schedule.principal,
        contractual_interest=schedule.contractual_interest,
        rounding_adjustment=schedule.rounding_adjustment,
        created_by=actor,
    )
    for row in schedule.repayments:
        RepaymentObligation.objects.create(
            workspace_id=loan.workspace_id,
            loan=loan,
            schedule_version=version,
            sequence=row.sequence,
            due_date=row.due_date,
            principal_due=row.principal_due,
            interest_due=row.interest_due,
            opening_principal=row.opening_principal,
            closing_principal=row.closing_principal,
        )
    return version


def allocate_event_to_obligations(
    *, source_event, principal_amount=0, interest_amount=0, actor=None
):
    if source_event.obligation_allocations.exists():
        return tuple(source_event.obligation_allocations.order_by("allocation_order"))
    amounts = (
        (ObligationComponent.INTEREST.value, Decimal(str(interest_amount))),
        (ObligationComponent.PRINCIPAL.value, Decimal(str(principal_amount))),
    )
    order = 0
    results = []
    active_schedule_ids = _active_schedule_ids(source_event.loan)
    obligations = tuple(
        RepaymentObligation.objects.select_for_update()
        .filter(
            loan=source_event.loan,
            schedule_version_id__in=active_schedule_ids,
        )
        .order_by("due_date", "sequence", "pk")
    )
    for component, amount in amounts:
        remaining = amount
        if remaining < 0:
            raise RepaymentObligationError("Ordinary allocation amounts cannot be negative.")
        due_field = "interest_due" if component == ObligationComponent.INTEREST.value else "principal_due"
        for obligation in obligations:
            if remaining == 0:
                break
            allocated = sum(
                (
                    row.amount
                    for row in obligation.allocations.filter(component=component)
                ),
                Decimal("0"),
            )
            available = getattr(obligation, due_field) - allocated
            if available <= 0:
                continue
            applied = min(remaining, available)
            order += 1
            results.append(ObligationAllocation.objects.create(
                workspace_id=source_event.loan.workspace_id,
                loan=source_event.loan,
                source_event=source_event,
                obligation=obligation,
                component=component,
                amount=applied,
                allocation_order=order,
                created_by=actor,
            ))
            remaining -= applied
        if remaining:
            raise RepaymentObligationError(
                f"{component.title()} allocation exceeds scheduled obligations by {remaining}."
            )
    return tuple(results)


def reverse_event_obligation_allocations(*, original_event, reversal_event, actor=None):
    existing = tuple(reversal_event.obligation_allocations.order_by("allocation_order"))
    if existing:
        return existing
    results = []
    for order, original in enumerate(
        original_event.obligation_allocations.order_by("allocation_order"), start=1
    ):
        results.append(ObligationAllocation.objects.create(
            workspace_id=original.workspace_id,
            loan=original.loan,
            source_event=reversal_event,
            obligation=original.obligation,
            component=original.component,
            amount=-original.amount,
            allocation_order=order,
            reversal_of=original,
            created_by=actor,
        ))
    return tuple(results)


def terminate_active_repayment_schedule(*, loan, source_event, reason, actor=None):
    existing = RepaymentScheduleChange.objects.filter(source_event=source_event).first()
    if existing:
        return existing
    active_ids = _active_schedule_ids(loan)
    if not active_ids:
        return None
    if len(active_ids) != 1:
        raise RepaymentObligationError("Loan must have exactly one active repayment schedule.")
    return RepaymentScheduleChange.objects.create(
        workspace_id=loan.workspace_id,
        loan=loan,
        schedule_version_id=active_ids[0],
        source_event=source_event,
        kind=RepaymentScheduleChangeKind.TERMINATE,
        effective_date=source_event.effective_date,
        reason=reason,
        created_by=actor,
    )


def installment_extra_principal_amount(*, loan, effective_date, principal_amount):
    if loan.product_version.repayment_structure != LoanRepaymentStructure.INSTALLMENT.value:
        return Decimal("0")
    active_ids = _active_schedule_ids(loan)
    due_capacity = Decimal("0")
    for obligation in RepaymentObligation.objects.filter(
        schedule_version_id__in=active_ids, due_date__lte=effective_date
    ):
        allocated = sum(
            (row.amount for row in obligation.allocations.filter(component=ObligationComponent.PRINCIPAL.value)),
            Decimal("0"),
        )
        due_capacity += max(Decimal("0"), obligation.principal_due - allocated)
    return max(Decimal("0"), Decimal(str(principal_amount)) - due_capacity)


def supersede_installment_schedule(
    *, loan, source_event, remaining_principal, extra_principal, currency_quantum, actor=None
):
    if Decimal(str(extra_principal)) <= 0 or Decimal(str(remaining_principal)) <= 0:
        return None
    existing = RepaymentScheduleVersion.objects.filter(source_event=source_event).first()
    if existing:
        return existing
    active_ids = _active_schedule_ids(loan)
    if len(active_ids) != 1:
        raise RepaymentObligationError("Installment rescheduling requires one active schedule.")
    previous = RepaymentScheduleVersion.objects.select_for_update().get(pk=active_ids[0])
    previous_rows = tuple(previous.obligations.order_by("sequence"))
    if not previous_rows:
        raise RepaymentObligationError("Installment schedule has no obligations.")
    product = loan.product_version
    value = RepaymentScheduleInput(
        repayment_structure=product.repayment_structure,
        amortisation_method=product.amortisation_method,
        disbursed_on=source_event.effective_date,
        principal=Decimal(str(remaining_principal)),
        monthly_interest_rate=loan.monthly_interest_rate,
        tenure_months=loan.tenure_months,
        currency_quantum=Decimal(str(currency_quantum)),
        contract_version=product.calculation_contract_version,
    )
    if product.amortisation_method == LoanAmortisationMethod.EMI.value:
        schedule = generate_shortened_installment_schedule(
            value, emi_payment=previous_rows[0].principal_due + previous_rows[0].interest_due
        )
    else:
        schedule = generate_shortened_installment_schedule(
            value, equal_principal_component=previous_rows[0].principal_due
        )
    version = RepaymentScheduleVersion.objects.create(
        workspace_id=loan.workspace_id,
        loan=loan,
        source_event=source_event,
        version=previous.version + 1,
        contract_version=schedule.contract_version,
        fingerprint=schedule.fingerprint,
        disbursed_on=schedule.disbursed_on,
        maturity_date=schedule.maturity_date,
        principal=schedule.principal,
        contractual_interest=schedule.contractual_interest,
        rounding_adjustment=schedule.rounding_adjustment,
        supersedes=previous,
        created_by=actor,
    )
    for row in schedule.repayments:
        RepaymentObligation.objects.create(
            workspace_id=loan.workspace_id,
            loan=loan,
            schedule_version=version,
            sequence=row.sequence,
            due_date=row.due_date,
            principal_due=row.principal_due,
            interest_due=row.interest_due,
            opening_principal=row.opening_principal,
            closing_principal=row.closing_principal,
        )
    return version


def reverse_event_schedule_change(*, original_event, reversal_event, actor=None):
    existing = RepaymentScheduleChange.objects.filter(source_event=reversal_event).first()
    if existing:
        return existing
    try:
        original_change = original_event.repayment_schedule_change
    except RepaymentScheduleChange.DoesNotExist:
        original_change = None
    if original_change is not None:
        return RepaymentScheduleChange.objects.create(
            workspace_id=original_change.workspace_id,
            loan=original_change.loan,
            schedule_version=original_change.schedule_version,
            source_event=reversal_event,
            kind=RepaymentScheduleChangeKind.REACTIVATE,
            effective_date=reversal_event.effective_date,
            reason="Reversal of schedule termination",
            reversal_of=original_change,
            created_by=actor,
        )
    try:
        opened_schedule = original_event.repayment_schedule
    except RepaymentScheduleVersion.DoesNotExist:
        return None
    return RepaymentScheduleChange.objects.create(
        workspace_id=opened_schedule.workspace_id,
        loan=opened_schedule.loan,
        schedule_version=opened_schedule,
        source_event=reversal_event,
        kind=RepaymentScheduleChangeKind.TERMINATE,
        effective_date=reversal_event.effective_date,
        reason="Schedule source event reversed",
        created_by=actor,
    )


def reconcile_loan_obligations(loan):
    active_ids = set(_active_schedule_ids(loan))
    obligations = tuple(RepaymentObligation.objects.filter(loan=loan))
    allocations = ObligationAllocation.objects.filter(loan=loan)
    principal_allocated = sum(
        (row.amount for row in allocations if row.component == ObligationComponent.PRINCIPAL.value),
        Decimal("0"),
    )
    interest_allocated = sum(
        (row.amount for row in allocations if row.component == ObligationComponent.INTEREST.value),
        Decimal("0"),
    )
    principal_scheduled = Decimal("0")
    interest_scheduled = Decimal("0")
    for obligation in obligations:
        principal_net = sum(
            (row.amount for row in obligation.allocations.filter(component=ObligationComponent.PRINCIPAL.value)),
            Decimal("0"),
        )
        interest_net = sum(
            (row.amount for row in obligation.allocations.filter(component=ObligationComponent.INTEREST.value)),
            Decimal("0"),
        )
        if obligation.schedule_version_id in active_ids:
            principal_scheduled += obligation.principal_due
            interest_scheduled += obligation.interest_due
        else:
            principal_scheduled += principal_net
            interest_scheduled += interest_net
    findings = []
    if principal_allocated > principal_scheduled:
        findings.append("Principal allocations exceed scheduled principal.")
    if interest_allocated > interest_scheduled:
        findings.append("Interest allocations exceed scheduled interest.")
    if principal_allocated < 0 or interest_allocated < 0:
        findings.append("Net obligation allocations cannot be negative.")
    return ObligationReconciliation(
        principal_scheduled=principal_scheduled,
        interest_scheduled=interest_scheduled,
        principal_allocated=principal_allocated,
        interest_allocated=interest_allocated,
        principal_remaining=principal_scheduled - principal_allocated,
        interest_remaining=interest_scheduled - interest_allocated,
        integrity_findings=tuple(findings),
    )


def _active_schedule_ids(loan):
    schedules = RepaymentScheduleVersion.objects.filter(loan=loan).order_by("-version", "-pk")
    for schedule in schedules:
        unterminated = not schedule.changes.filter(
            kind=RepaymentScheduleChangeKind.TERMINATE,
            reversal__isnull=True,
        ).exists()
        if unterminated:
            return (schedule.pk,)
    return ()
