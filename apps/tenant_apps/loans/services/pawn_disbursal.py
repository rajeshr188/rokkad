"""Atomic PawnLoan disbursal source-event workflow."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Q

from apps.tenant_apps.loans.domain import (
    AccountingRecognition,
    InterestMethod,
    LoanOutboxStatus,
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
    PawnLoanAccountingEvent,
    PawnLoanAccountingOutbox,
    PawnLoanDisbursalSnapshot,
    current_tenant_workspace_id,
)
from apps.tenant_apps.loans.services.accounting_outbox import (
    DeliveryHandler,
    record_loan_accounting_event,
)
from apps.tenant_apps.loans.services.accounting_readiness import (
    require_pawn_loan_accounting_readiness,
)
from apps.tenant_apps.loans.services.license_series import assert_series_can_issue


class PawnDisbursalError(ValueError):
    """Raised when a PawnLoan cannot be safely disbursed."""


@dataclass(frozen=True)
class PawnDisbursalResult:
    loan: PawnLoan
    policy_snapshot: LoanPolicySnapshot
    accounting_event: PawnLoanAccountingEvent
    outbox: PawnLoanAccountingOutbox
    disbursal_snapshot: PawnLoanDisbursalSnapshot | None = None
    already_disbursed: bool = False


@transaction.atomic
def disburse_pawn_loan(
    loan_id: int,
    *,
    effective_date: date,
    actor=None,
    delivery_handler: DeliveryHandler | None = None,
) -> PawnDisbursalResult:
    """Activate an approved loan and enqueue its once-only disbursal intent.

    The outer transaction makes the state change, immutable policy snapshot,
    source accounting event, outbox row, and audit row all-or-nothing.  Actual
    voucher/journal creation remains in DEA and is attempted after commit by
    the outbox delivery seam.
    """
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
    recognition = resolved_policy.accounting_recognition.value

    try:
        assert_series_can_issue(loan.series, as_of_date=effective_date)
        require_pawn_loan_accounting_readiness(
            loan,
            effective_date=effective_date,
            requires_fee_income=(
                economics is not None and economics["deducted_fees"] > 0
            ),
            requires_unearned_interest=(
                economics is not None
                and economics["advance_interest"] > 0
                and recognition == "ACCRUAL"
            ),
        )
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
            "accounting_recognition": policy_snapshot.accounting_recognition,
            "advance_interest_periods": economics["advance_interest_periods"],
            "monthly_interest": str(economics["monthly_interest"]),
            "tranches": economics["evidence"].get("tranches", []),
            "fees": economics["evidence"].get("fees", []),
        }
    event, outbox = record_loan_accounting_event(
        loan.pk,
        event_kind=TransactionKind.DISBURSAL,
        effective_date=effective_date,
        payload=payload,
        actor=actor,
        delivery_handler=delivery_handler,
    )
    disbursal_snapshot = None
    if economics is not None:
        disbursal_snapshot = PawnLoanDisbursalSnapshot.objects.create(
            loan=loan,
            approval_snapshot=approval_snapshot,
            policy_snapshot=policy_snapshot,
            accounting_event=event,
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
            "accounting_event_id": event.pk,
            "outbox_id": outbox.pk,
            "idempotency_key": outbox.idempotency_key,
            "disbursal_snapshot_id": (
                disbursal_snapshot.pk if disbursal_snapshot is not None else None
            ),
        },
    )
    return PawnDisbursalResult(
        loan, policy_snapshot, event, outbox, disbursal_snapshot
    )


def assert_pawn_loan_financial_actions_allowed(loan_id: int) -> PawnLoan:
    """Block later repayment/release actions while any loan posting is unresolved."""
    loan = _locked_loan(loan_id)
    from apps.tenant_apps.loans.integrations.accounting_policy import (
        is_dea_integration_enabled,
    )

    blocking_statuses = [
        LoanOutboxStatus.PROCESSING.value,
        LoanOutboxStatus.FAILED.value,
    ]
    if is_dea_integration_enabled(loan.workspace):
        blocking_statuses.append(LoanOutboxStatus.PENDING.value)
    if loan.accounting_events.filter(
        Q(outbox__isnull=True) | Q(outbox__status__in=blocking_statuses)
    ).exists():
        raise PawnDisbursalError(
            "PawnLoan financial actions are blocked by missing, failed, or unresolved accounting evidence."
        )
    return loan


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


def _persist_policy_snapshot(loan: PawnLoan, resolved_policy=None) -> LoanPolicySnapshot:
    policy = (resolved_policy or resolve_policy()).to_disbursal_snapshot()
    values = {
        "policy_version": policy.policy_version,
        "interest_method": policy.interest_method.value,
        "partial_month_method": policy.partial_month_method.value,
        "partial_month_cutoff_days": policy.partial_month_cutoff_days,
        "partial_month_lower_fraction": policy.partial_month_lower_fraction,
        "capitalization_interval_periods": policy.capitalization_interval_periods,
        "accounting_recognition": policy.accounting_recognition.value,
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
        "accounting_recognition",
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
            accounting_recognition=AccountingRecognition(
                evidence["accounting_recognition"]
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
        event = loan.accounting_events.get(event_kind=TransactionKind.DISBURSAL.value)
        snapshot = loan.policy_snapshot
        try:
            disbursal_snapshot = loan.disbursal_snapshot
        except PawnLoanDisbursalSnapshot.DoesNotExist:
            disbursal_snapshot = None
        return PawnDisbursalResult(
            loan=loan,
            policy_snapshot=snapshot,
            accounting_event=event,
            outbox=event.outbox,
            disbursal_snapshot=disbursal_snapshot,
            already_disbursed=True,
        )
    except (
        PawnLoanAccountingEvent.DoesNotExist,
        PawnLoanAccountingOutbox.DoesNotExist,
        LoanPolicySnapshot.DoesNotExist,
    ) as exc:
        raise PawnDisbursalError(
            "Active PawnLoan is missing its required disbursal accounting records."
        ) from exc
