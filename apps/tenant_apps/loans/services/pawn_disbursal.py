"""Atomic PawnLoan disbursal source-event workflow."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction

from apps.tenant_apps.loans.domain import (
    InterestMethod,
    PawnLoanEventKind,
    PawnLoanState,
    PartialMonthMethod,
    RoundingMethod,
    TransactionKind,
    ValuationMethod,
    WorkspacePolicyDefaults,
    resolve_policy,
)
from apps.tenant_apps.loans.integrations import disbursal_payload
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    LoanPolicySnapshot,
    PawnLoan,
    PawnLoanEvent,
    PawnLoanDisbursalSnapshot,
    current_tenant_workspace_id,
)
from apps.tenant_apps.loans.services.event_recording import (
    record_loan_event,
)
from apps.tenant_apps.loans.services.obligations import (
    persist_disbursal_repayment_schedule,
)
from apps.tenant_apps.loans.services.license_series import assert_series_can_issue


class PawnDisbursalError(ValueError):
    """Raised when a PawnLoan cannot be safely disbursed."""


@dataclass(frozen=True)
class PawnDisbursalResult:
    loan: PawnLoan
    policy_snapshot: LoanPolicySnapshot
    loan_event: PawnLoanEvent
    disbursal_snapshot: PawnLoanDisbursalSnapshot | None = None
    already_disbursed: bool = False


@transaction.atomic
def disburse_pawn_loan(
    loan_id: int,
    *,
    effective_date: date,
    actor=None,
) -> PawnDisbursalResult:
    """Activate an approved loan and record its once-only operational event."""
    loan = _locked_loan(loan_id)
    if loan.state == PawnLoanState.ACTIVE.value:
        return _existing_disbursal_result(loan)
    if loan.state != PawnLoanState.APPROVED.value:
        raise PawnDisbursalError("Only an approved PawnLoan can be disbursed.")

    approval_snapshot = loan.approval_snapshots.order_by("-version").first()
    if approval_snapshot is None:
        raise PawnDisbursalError("Approved PawnLoan is missing its approval snapshot.")
    economics = _approved_economics(loan, approval_snapshot)
    resolved_policy = _approved_disbursal_policy(economics)
    try:
        assert_series_can_issue(loan.series, as_of_date=effective_date)
    except Exception as exc:
        if isinstance(exc, PawnDisbursalError):
            raise
        raise PawnDisbursalError(str(exc)) from exc

    policy_snapshot = _persist_policy_snapshot(loan, resolved_policy)
    if economics is None:
        payload = disbursal_payload(
            loan,
            effective_date=effective_date,
            principal_amount=loan.principal_amount,
        ).to_dict()
    else:
        payload = disbursal_payload(
            loan,
            effective_date=effective_date,
            principal_amount=economics["gross_principal"],
            net_cash_amount=economics["net_disbursed"],
            advance_interest_amount=economics["advance_interest"],
            deducted_fee_amount=economics["deducted_fees"],
        ).to_dict()
        payload["disbursal"] = {
            "approval_snapshot_id": approval_snapshot.pk,
            "policy_snapshot_id": policy_snapshot.pk,
            "advance_interest_periods": economics["advance_interest_periods"],
            "monthly_interest": str(economics["monthly_interest"]),
            "tranches": economics["evidence"].get("tranches", []),
            "fees": economics["evidence"].get("fees", []),
        }
    event, _ = record_loan_event(
        loan.pk,
        event_kind=TransactionKind.DISBURSAL,
        effective_date=effective_date,
        payload=payload,
        actor=actor,
    )
    repayment_schedule = persist_disbursal_repayment_schedule(
        loan,
        source_event=event,
        disbursed_on=effective_date,
        currency_quantum=policy_snapshot.currency_quantum,
        actor=actor,
    )
    disbursal_snapshot = None
    if economics is not None:
        disbursal_snapshot = PawnLoanDisbursalSnapshot.objects.create(
            loan=loan,
            approval_snapshot=approval_snapshot,
            policy_snapshot=policy_snapshot,
            loan_event=event,
            gross_principal=economics["gross_principal"],
            monthly_interest=economics["monthly_interest"],
            advance_interest_periods=economics["advance_interest_periods"],
            advance_interest=economics["advance_interest"],
            deducted_fees=economics["deducted_fees"],
            net_disbursed=economics["net_disbursed"],
            evidence=economics["evidence"],
            created_by=actor,
        )
    previous_state = loan.state
    loan.state = PawnLoanState.ACTIVE.value
    loan.updated_by = actor
    loan.save(update_fields=["state", "updated_by", "updated_at"])
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.DISBURSED.value,
        from_state=previous_state,
        to_state=PawnLoanState.ACTIVE.value,
        actor=actor,
        metadata={
            "effective_date": effective_date.isoformat(),
            "policy_snapshot_id": policy_snapshot.pk,
            "loan_event_id": event.pk,
            "idempotency_key": event.idempotency_key,
            "disbursal_snapshot_id": (
                disbursal_snapshot.pk if disbursal_snapshot is not None else None
            ),
            "repayment_schedule_version_id": repayment_schedule.pk,
        },
    )
    return PawnDisbursalResult(
        loan, policy_snapshot, event, disbursal_snapshot
    )


def assert_pawn_loan_financial_actions_allowed(
    loan_id: int,
    *,
    lock: bool = True,
) -> PawnLoan:
    """Load and optionally lock the loan for an operational financial action.

    Mutation commands retain the default row lock. Read-only previews must pass
    ``lock=False`` so they remain safe outside an atomic request.
    """
    return _locked_loan(loan_id) if lock else _tenant_loan(loan_id)


def _locked_loan(loan_id: int) -> PawnLoan:
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnDisbursalError("PawnLoan disbursal requires an active tenant schema.")
    try:
        return (
            PawnLoan.objects.select_for_update()
            .select_related("license", "series", "series__license", "borrower")
            .get(pk=loan_id, workspace_id=workspace_id)
        )
    except PawnLoan.DoesNotExist as exc:
        raise PawnDisbursalError("PawnLoan was not found in the active workspace.") from exc


def _tenant_loan(loan_id: int) -> PawnLoan:
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnDisbursalError("PawnLoan disbursal requires an active tenant schema.")
    try:
        return PawnLoan.objects.select_related(
            "license", "series", "series__license", "borrower"
        ).get(pk=loan_id, workspace_id=workspace_id)
    except PawnLoan.DoesNotExist as exc:
        raise PawnDisbursalError("PawnLoan was not found in the active workspace.") from exc


def _persist_policy_snapshot(loan: PawnLoan, resolved_policy=None) -> LoanPolicySnapshot:
    policy = (resolved_policy or resolve_policy()).to_disbursal_snapshot()
    values = {
        "policy_version": policy.policy_version,
        "interest_method": policy.interest_method.value,
        "partial_month_method": policy.partial_month_method.value,
        "partial_month_cutoff_days": policy.partial_month_cutoff_days,
        "partial_month_lower_fraction": policy.partial_month_lower_fraction,
        "capitalization_interval_periods": policy.capitalization_interval_periods,
        "valuation_method": policy.valuation_method.value,
        "maximum_ltv_ratio": policy.maximum_ltv_ratio,
        "rounding_method": policy.rounding_method.value,
        "currency_quantum": policy.currency_quantum,
    }
    snapshot, created = LoanPolicySnapshot.objects.get_or_create(
        loan=loan,
        defaults=values,
    )
    if not created:
        raise PawnDisbursalError("PawnLoan already has a disbursal policy snapshot.")
    return snapshot


def _approved_economics(loan, approval_snapshot):
    """Parse and reconcile the exact collateral economics frozen at approval."""
    evidence = approval_snapshot.payload.get("collateral_economics")
    if evidence is None:
        # Compatibility for internal legacy callers whose collateral allocations
        # are all null. No economic facts are invented for those development rows.
        return None
    try:
        values = {
            "gross_principal": Decimal(
                str(approval_snapshot.payload["principal_amount"])
            ),
            "monthly_interest": Decimal(str(evidence["monthly_interest"])),
            "advance_interest_periods": int(evidence["advance_interest_periods"]),
            "advance_interest": Decimal(str(evidence["advance_interest"])),
            "deducted_fees": Decimal(str(evidence["deducted_fees"])),
            "net_disbursed": Decimal(str(evidence["net_disbursed"])),
            "evidence": evidence,
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise PawnDisbursalError(
            "Approval has incomplete collateral economics."
        ) from exc
    if not evidence.get("tranches"):
        raise PawnDisbursalError(
            "Approval predates immutable tranche evidence; reopen and approve the loan again."
        )
    if values["gross_principal"] != loan.principal_amount:
        raise PawnDisbursalError("Approved gross principal no longer matches the loan.")
    if (
        values["net_disbursed"]
        + values["advance_interest"]
        + values["deducted_fees"]
        != values["gross_principal"]
    ):
        raise PawnDisbursalError("Approved gross-to-net disbursal does not reconcile.")
    return values


def _approved_disbursal_policy(economics):
    """Rehydrate frozen policy, with compatibility for pre-itemized approvals."""
    if economics is None:
        return resolve_policy()
    evidence = economics["evidence"]
    required = {
        "interest_method",
        "partial_month_method",
        "partial_month_cutoff_days",
        "partial_month_lower_fraction",
        "capitalization_interval_periods",
        "valuation_method",
        "maximum_ltv_ratio",
        "rounding_method",
        "currency_quantum",
    }
    if not required.issubset(evidence):
        return resolve_policy()
    try:
        defaults = WorkspacePolicyDefaults(
            interest_method=InterestMethod(evidence["interest_method"]),
            partial_month_method=PartialMonthMethod(evidence["partial_month_method"]),
            partial_month_cutoff_days=int(evidence["partial_month_cutoff_days"]),
            partial_month_lower_fraction=Decimal(
                str(evidence["partial_month_lower_fraction"])
            ),
            capitalization_interval_periods=int(
                evidence["capitalization_interval_periods"]
            ),
            valuation_method=ValuationMethod(evidence["valuation_method"]),
            maximum_ltv_ratio=Decimal(str(evidence["maximum_ltv_ratio"])),
            rounding_method=RoundingMethod(evidence["rounding_method"]),
            currency_quantum=Decimal(str(evidence["currency_quantum"])),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PawnDisbursalError("Approval has an invalid frozen loan policy.") from exc
    return resolve_policy(workspace_defaults=defaults)


def _existing_disbursal_result(loan: PawnLoan) -> PawnDisbursalResult:
    try:
        event = loan.loan_events.get(event_kind=TransactionKind.DISBURSAL.value)
        snapshot = loan.policy_snapshot
        try:
            disbursal_snapshot = loan.disbursal_snapshot
        except PawnLoanDisbursalSnapshot.DoesNotExist:
            disbursal_snapshot = None
        return PawnDisbursalResult(
            loan=loan,
            policy_snapshot=snapshot,
            loan_event=event,
            disbursal_snapshot=disbursal_snapshot,
            already_disbursed=True,
        )
    except (
        PawnLoanEvent.DoesNotExist,
        LoanPolicySnapshot.DoesNotExist,
    ) as exc:
        raise PawnDisbursalError(
            "Active PawnLoan is missing its required disbursal event records."
        ) from exc
