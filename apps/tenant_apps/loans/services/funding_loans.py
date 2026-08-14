from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.tenant_apps.loans.domain import CollateralCustodyState, PawnLoanState
from apps.tenant_apps.loans.domain.future_funding import (
    FundingCollateralCandidate,
    FundingLoanEvent as DomainFundingLoanEvent,
    FundingLoanEventKind,
    FundingLoanState,
    FundingLoanTerms,
    FundingPledgePolicyError,
    allocate_funding_repayment,
    assess_funding_closure,
    calculate_funding_interest,
    calculate_funding_loan_balance,
    plan_funding_pledge,
    plan_funding_reversal,
    plan_funding_return,
)
from apps.tenant_apps.loans.models import (
    FundingLoan,
    FundingLoanCancellation,
    FundingLoanDraftCollateral,
    FundingLoanDraftTerms,
    FundingLoanEvent,
    FundingLoanSequence,
    FundingLoanTermsSnapshot,
    FundingPledge,
    FundingPledgeItem,
    FundingPledgeReversal,
    FundingReturn,
    FundingReturnItem,
    FundingReturnReversal,
    PawnCollateralCustodyEvent,
    PawnCollateralItem,
    PawnLoan,
    current_tenant_workspace_id,
)
from apps.tenant_apps.party.models import Party


class FundingLoanServiceError(ValueError):
    pass


@dataclass(frozen=True)
class CreateFundingLoanDraft:
    workspace_id: int
    lender_id: int


@dataclass(frozen=True)
class CancelFundingLoanDraft:
    workspace_id: int
    funding_loan_id: int
    reason: str


@dataclass(frozen=True)
class SaveFundingLoanDraftInputs:
    workspace_id: int
    funding_loan_id: int
    principal_amount: Decimal
    monthly_interest_rate: Decimal
    activated_on: date
    maturity_on: date
    maximum_funding_ltv_ratio: Decimal
    currency_quantum: Decimal
    collateral: tuple[FundingCollateralInput, ...]


@dataclass(frozen=True)
class FundingDraftReadiness:
    ready: bool
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class FundingCollateralInput:
    collateral_item_id: int
    selected_value: Decimal


@dataclass(frozen=True)
class ActivateFundingLoan:
    workspace_id: int
    funding_loan_id: int
    principal_amount: Decimal
    monthly_interest_rate: Decimal
    activated_on: date
    maturity_on: date
    maximum_funding_ltv_ratio: Decimal
    currency_quantum: Decimal
    collateral: tuple[FundingCollateralInput, ...]
    request_key: str


@dataclass(frozen=True)
class ActivateSavedFundingLoanDraft:
    workspace_id: int
    funding_loan_id: int


@dataclass(frozen=True)
class AccrueFundingInterest:
    workspace_id: int
    funding_loan_id: int
    periods: int
    effective_date: date
    request_key: str


@dataclass(frozen=True)
class AssessFundingFee:
    workspace_id: int
    funding_loan_id: int
    amount: Decimal
    effective_date: date
    request_key: str


@dataclass(frozen=True)
class RecordFundingRepayment:
    workspace_id: int
    funding_loan_id: int
    amount: Decimal
    effective_date: date
    request_key: str


@dataclass(frozen=True)
class ReverseFundingEvent:
    workspace_id: int
    funding_loan_id: int
    original_event_id: int
    effective_date: date
    reason: str
    request_key: str


@dataclass(frozen=True)
class BeginFundingSettlement:
    workspace_id: int
    funding_loan_id: int


@dataclass(frozen=True)
class ReturnFundingCollateral:
    workspace_id: int
    funding_loan_id: int
    collateral_item_ids: tuple[int, ...]
    effective_date: date
    request_key: str


@dataclass(frozen=True)
class ReverseFundingPledge:
    workspace_id: int
    funding_loan_id: int
    effective_date: date
    reason: str
    request_key: str


@dataclass(frozen=True)
class ReverseFundingReturn:
    workspace_id: int
    funding_loan_id: int
    funding_return_id: int
    effective_date: date
    reason: str
    request_key: str


@dataclass(frozen=True)
class CloseFundingLoan:
    workspace_id: int
    funding_loan_id: int


@dataclass(frozen=True)
class FundingActivationResult:
    funding_loan: FundingLoan
    terms: FundingLoanTermsSnapshot
    event: FundingLoanEvent
    pledge: FundingPledge
    already_activated: bool = False


@dataclass(frozen=True)
class OperationalOnlyReceipt:
    delivery: str = "OPERATIONAL_ONLY"


class FundingOutboundPort(Protocol):
    def record(self, *, funding_loan_id: int, operation: str) -> OperationalOnlyReceipt: ...


class NullFundingOutboundAdapter:
    def record(self, *, funding_loan_id: int, operation: str) -> OperationalOnlyReceipt:
        return OperationalOnlyReceipt()


@transaction.atomic
def create_funding_loan_draft(
    command: CreateFundingLoanDraft,
    *,
    actor=None,
) -> FundingLoan:
    workspace_id = _require_workspace(command.workspace_id)
    lender = _active_party(command.lender_id)
    funding_number = _allocate_funding_number(workspace_id)
    return FundingLoan.objects.create(
        workspace_id=workspace_id,
        lender=lender,
        funding_number=funding_number,
        state=FundingLoanState.DRAFT.value,
        created_by=actor,
        updated_by=actor,
    )


@transaction.atomic
def cancel_funding_loan_draft(
    command: CancelFundingLoanDraft,
    *,
    actor=None,
) -> FundingLoan:
    funding_loan = _locked_funding_loan(
        command.funding_loan_id,
        command.workspace_id,
    )
    if funding_loan.state == FundingLoanState.CANCELLED.value:
        return funding_loan
    if funding_loan.state != FundingLoanState.DRAFT.value:
        raise FundingLoanServiceError("Only a draft FundingLoan can be cancelled.")
    reason = str(command.reason or "").strip()
    if not reason:
        raise FundingLoanServiceError("A FundingLoan cancellation reason is required.")
    FundingLoanCancellation.objects.create(
        funding_loan=funding_loan,
        reason=reason,
        actor=actor,
    )
    funding_loan.state = FundingLoanState.CANCELLED.value
    funding_loan.updated_by = actor
    funding_loan.save(update_fields=["state", "updated_by", "updated_at"])
    return funding_loan


@transaction.atomic
def save_funding_loan_draft_inputs(
    command: SaveFundingLoanDraftInputs,
    *,
    actor=None,
) -> FundingDraftReadiness:
    funding_loan = _locked_funding_loan(
        command.funding_loan_id,
        command.workspace_id,
    )
    if funding_loan.state != FundingLoanState.DRAFT.value:
        raise FundingLoanServiceError("Only a draft FundingLoan can be edited.")
    terms = FundingLoanTerms(
        principal_amount=command.principal_amount,
        monthly_interest_rate=command.monthly_interest_rate,
        activated_on=command.activated_on,
        maturity_on=command.maturity_on,
        maximum_funding_ltv_ratio=command.maximum_funding_ltv_ratio,
        currency_quantum=command.currency_quantum,
    )
    collateral_inputs = tuple(command.collateral)
    input_ids = tuple(item.collateral_item_id for item in collateral_inputs)
    if not input_ids:
        raise FundingLoanServiceError("Select at least one eligible collateral item.")
    if len(input_ids) != len(set(input_ids)):
        raise FundingLoanServiceError("A collateral item cannot appear more than once.")
    value_by_item = {
        item.collateral_item_id: Decimal(str(item.selected_value))
        for item in collateral_inputs
    }
    collateral = _locked_collateral(funding_loan.workspace_id, input_ids)
    from .physical_verification import (
        PawnPhysicalVerificationBlockerError,
        assert_physical_verification_clear,
    )

    try:
        assert_physical_verification_clear(
            input_ids, operation="FundingLoan collateral pledge"
        )
    except PawnPhysicalVerificationBlockerError as exc:
        raise FundingLoanServiceError(str(exc)) from exc
    active_pledges = {
        item.collateral_item_id: item.pk
        for item in FundingPledgeItem.objects.select_for_update()
        .filter(collateral_item_id__in=input_ids, released_at__isnull=True)
        .order_by("collateral_item_id")
    }
    candidates = tuple(
        FundingCollateralCandidate(
            collateral_item_id=item.pk,
            pawn_loan_id=item.loan_id,
            pawn_loan_state=PawnLoanState(item.loan.state),
            custody_state=CollateralCustodyState(item.custody_state),
            active_funding_pledge_id=active_pledges.get(item.pk),
            collateral_value=value_by_item[item.pk],
        )
        for item in collateral
    )
    try:
        plan_funding_pledge(candidates, terms=terms)
    except (FundingPledgePolicyError, ValueError) as exc:
        raise FundingLoanServiceError(str(exc)) from exc
    FundingLoanDraftTerms.objects.update_or_create(
        funding_loan=funding_loan,
        defaults={
            "principal_amount": terms.principal_amount,
            "monthly_interest_rate": terms.monthly_interest_rate,
            "activated_on": terms.activated_on,
            "maturity_on": terms.maturity_on,
            "maximum_funding_ltv_ratio": terms.maximum_funding_ltv_ratio,
            "currency_quantum": terms.currency_quantum,
            "updated_by": actor,
        },
    )
    funding_loan.draft_collateral.all().delete()
    FundingLoanDraftCollateral.objects.bulk_create(
        [
            FundingLoanDraftCollateral(
                funding_loan=funding_loan,
                collateral_item=item,
                selected_collateral_value=value_by_item[item.pk],
            )
            for item in collateral
        ]
    )
    funding_loan.updated_by = actor
    funding_loan.save(update_fields=["updated_by", "updated_at"])
    return FundingDraftReadiness(ready=True, blockers=())


@transaction.atomic
def activate_funding_loan(
    command: ActivateFundingLoan,
    *,
    actor=None,
    outbound: FundingOutboundPort | None = None,
) -> FundingActivationResult:
    funding_loan = _locked_funding_loan(
        command.funding_loan_id,
        command.workspace_id,
    )
    request_key = str(command.request_key or "").strip()
    if not request_key:
        raise FundingLoanServiceError("Funding activation requires a request key.")
    fingerprint = _activation_fingerprint(command)
    replay = _activation_replay(funding_loan, request_key, fingerprint)
    if replay is not None:
        return replay
    if funding_loan.state != FundingLoanState.DRAFT.value:
        raise FundingLoanServiceError("Only a draft FundingLoan can be activated.")

    terms = FundingLoanTerms(
        principal_amount=command.principal_amount,
        monthly_interest_rate=command.monthly_interest_rate,
        activated_on=command.activated_on,
        maturity_on=command.maturity_on,
        maximum_funding_ltv_ratio=command.maximum_funding_ltv_ratio,
        currency_quantum=command.currency_quantum,
    )
    collateral_inputs = tuple(command.collateral)
    input_ids = tuple(item.collateral_item_id for item in collateral_inputs)
    if len(input_ids) != len(set(input_ids)):
        raise FundingLoanServiceError("A collateral item cannot appear more than once.")
    value_by_item = {
        item.collateral_item_id: Decimal(str(item.selected_value))
        for item in collateral_inputs
    }
    collateral = _locked_collateral(funding_loan.workspace_id, input_ids)
    active_pledges = {
        item.collateral_item_id: item.pk
        for item in FundingPledgeItem.objects.select_for_update()
        .filter(collateral_item_id__in=input_ids, released_at__isnull=True)
        .order_by("collateral_item_id")
    }
    candidates = tuple(
        FundingCollateralCandidate(
            collateral_item_id=item.pk,
            pawn_loan_id=item.loan_id,
            pawn_loan_state=PawnLoanState(item.loan.state),
            custody_state=CollateralCustodyState(item.custody_state),
            active_funding_pledge_id=active_pledges.get(item.pk),
            collateral_value=value_by_item[item.pk],
        )
        for item in collateral
    )
    try:
        plan_funding_pledge(candidates, terms=terms)
    except (FundingPledgePolicyError, ValueError) as exc:
        raise FundingLoanServiceError(str(exc)) from exc

    terms_payload = {
        "principal_amount": str(terms.principal_amount),
        "monthly_interest_rate": str(terms.monthly_interest_rate),
        "activated_on": terms.activated_on.isoformat(),
        "maturity_on": terms.maturity_on.isoformat(),
        "maximum_funding_ltv_ratio": str(terms.maximum_funding_ltv_ratio),
        "currency_quantum": str(terms.currency_quantum),
    }
    terms_snapshot = FundingLoanTermsSnapshot.objects.create(
        funding_loan=funding_loan,
        principal_amount=terms.principal_amount,
        monthly_interest_rate=terms.monthly_interest_rate,
        activated_on=terms.activated_on,
        maturity_on=terms.maturity_on,
        maximum_funding_ltv_ratio=terms.maximum_funding_ltv_ratio,
        currency_quantum=terms.currency_quantum,
        fingerprint=_fingerprint(terms_payload),
        created_by=actor,
    )
    event = FundingLoanEvent.objects.create(
        funding_loan=funding_loan,
        sequence=1,
        event_kind=FundingLoanEventKind.ACTIVATION.value,
        operation="ACTIVATE",
        effective_date=terms.activated_on,
        principal_amount=terms.principal_amount,
        request_key=request_key,
        request_fingerprint=fingerprint,
        actor=actor,
    )
    total_value = sum(value_by_item.values(), Decimal("0"))
    pledge = FundingPledge.objects.create(
        workspace_id=funding_loan.workspace_id,
        funding_loan=funding_loan,
        effective_date=terms.activated_on,
        request_key=request_key,
        request_fingerprint=fingerprint,
        total_collateral_value=total_value,
        maximum_funded_amount=(
            total_value * terms.maximum_funding_ltv_ratio
        ).quantize(terms.currency_quantum),
        valuation_method="COMMAND_SELECTED_VALUE",
        valuation_snapshot={
            "items": [
                {"collateral_item_id": item.pk, "selected_value": str(value_by_item[item.pk])}
                for item in collateral
            ]
        },
        actor=actor,
    )
    try:
        pledge_items = FundingPledgeItem.objects.bulk_create(
            [
                FundingPledgeItem(
                    funding_pledge=pledge,
                    collateral_item=item,
                    source_pawn_loan_id=item.loan_id,
                    selected_collateral_value=value_by_item[item.pk],
                    valuation_snapshot={
                        "latest_appraised_value": str(item.latest_appraised_value),
                        "selected_value": str(value_by_item[item.pk]),
                    },
                    valuation_fingerprint=_fingerprint(
                        {
                            "collateral_item_id": item.pk,
                            "selected_value": str(value_by_item[item.pk]),
                        }
                    ),
                )
                for item in collateral
            ]
        )
    except IntegrityError as exc:
        raise FundingLoanServiceError("Collateral is already pledged to an active FundingLoan.") from exc

    for collateral_item, pledge_item in zip(collateral, pledge_items, strict=True):
        PawnCollateralCustodyEvent.objects.create(
            collateral_item=collateral_item,
            funding_pledge=pledge,
            from_state=CollateralCustodyState.IN_VAULT.value,
            to_state=CollateralCustodyState.WITH_FUNDING_LENDER.value,
            effective_date=terms.activated_on,
            actor=actor,
        )
        PawnCollateralItem.objects.filter(pk=collateral_item.pk).update(
            custody_state=CollateralCustodyState.WITH_FUNDING_LENDER.value
        )
        pledge_item.collateral_item.custody_state = (
            CollateralCustodyState.WITH_FUNDING_LENDER.value
        )

    funding_loan.state = FundingLoanState.ACTIVE.value
    funding_loan.updated_by = actor
    funding_loan.save(update_fields=["state", "updated_by", "updated_at"])
    (outbound or NullFundingOutboundAdapter()).record(
        funding_loan_id=funding_loan.pk,
        operation="ACTIVATE",
    )
    return FundingActivationResult(funding_loan, terms_snapshot, event, pledge)


@transaction.atomic
def activate_saved_funding_loan_draft(
    command: ActivateSavedFundingLoanDraft,
    *,
    actor=None,
    outbound: FundingOutboundPort | None = None,
) -> FundingActivationResult:
    funding_loan = _locked_funding_loan(
        command.funding_loan_id,
        command.workspace_id,
    )
    if funding_loan.state != FundingLoanState.DRAFT.value:
        raise FundingLoanServiceError("Only a draft FundingLoan can be activated.")
    try:
        terms = FundingLoanDraftTerms.objects.select_for_update().get(
            funding_loan=funding_loan
        )
    except FundingLoanDraftTerms.DoesNotExist as exc:
        raise FundingLoanServiceError(
            "Complete and validate the FundingLoan draft before activation."
        ) from exc
    collateral = tuple(
        FundingLoanDraftCollateral.objects.select_for_update()
        .filter(funding_loan=funding_loan)
        .order_by("collateral_item_id")
    )
    if not collateral:
        raise FundingLoanServiceError(
            "Complete and validate the FundingLoan draft before activation."
        )
    result = activate_funding_loan(
        ActivateFundingLoan(
            workspace_id=funding_loan.workspace_id,
            funding_loan_id=funding_loan.pk,
            principal_amount=terms.principal_amount,
            monthly_interest_rate=terms.monthly_interest_rate,
            activated_on=terms.activated_on,
            maturity_on=terms.maturity_on,
            maximum_funding_ltv_ratio=terms.maximum_funding_ltv_ratio,
            currency_quantum=terms.currency_quantum,
            collateral=tuple(
                FundingCollateralInput(
                    collateral_item_id=item.collateral_item_id,
                    selected_value=item.selected_collateral_value,
                )
                for item in collateral
            ),
            request_key=f"saved-draft-activation-v1:{funding_loan.pk}",
        ),
        actor=actor,
        outbound=outbound,
    )
    FundingLoanDraftCollateral.objects.filter(funding_loan=funding_loan).delete()
    terms.delete()
    return result


@transaction.atomic
def accrue_funding_interest(
    command: AccrueFundingInterest,
    *,
    actor=None,
    outbound: FundingOutboundPort | None = None,
) -> FundingLoanEvent:
    funding_loan, events = _locked_open_funding_events(
        command.funding_loan_id, command.workspace_id
    )
    fingerprint = _fingerprint(command)
    replay = _event_replay(
        funding_loan, "ACCRUE_INTEREST", command.request_key, fingerprint
    )
    if replay is not None:
        return replay
    terms = _domain_terms(funding_loan.terms_snapshot)
    balance = calculate_funding_loan_balance(
        _domain_events(events), currency_quantum=terms.currency_quantum
    )
    amount = calculate_funding_interest(
        terms,
        principal_outstanding=balance.principal_outstanding,
        periods=command.periods,
    )
    event = _append_funding_event(
        funding_loan,
        events,
        kind=FundingLoanEventKind.INTEREST_ACCRUAL,
        operation="ACCRUE_INTEREST",
        effective_date=command.effective_date,
        request_key=command.request_key,
        request_fingerprint=fingerprint,
        interest_amount=amount,
        actor=actor,
    )
    (outbound or NullFundingOutboundAdapter()).record(
        funding_loan_id=funding_loan.pk, operation="ACCRUE_INTEREST"
    )
    return event


@transaction.atomic
def assess_funding_fee(
    command: AssessFundingFee,
    *,
    actor=None,
    outbound: FundingOutboundPort | None = None,
) -> FundingLoanEvent:
    funding_loan, events = _locked_open_funding_events(
        command.funding_loan_id, command.workspace_id
    )
    fingerprint = _fingerprint(command)
    replay = _event_replay(funding_loan, "ASSESS_FEE", command.request_key, fingerprint)
    if replay is not None:
        return replay
    amount = Decimal(str(command.amount))
    if amount <= 0:
        raise FundingLoanServiceError("Funding fee must be positive.")
    event = _append_funding_event(
        funding_loan,
        events,
        kind=FundingLoanEventKind.FEE_ASSESSMENT,
        operation="ASSESS_FEE",
        effective_date=command.effective_date,
        request_key=command.request_key,
        request_fingerprint=fingerprint,
        fee_amount=amount,
        actor=actor,
    )
    (outbound or NullFundingOutboundAdapter()).record(
        funding_loan_id=funding_loan.pk, operation="ASSESS_FEE"
    )
    return event


@transaction.atomic
def record_funding_repayment(
    command: RecordFundingRepayment,
    *,
    actor=None,
    outbound: FundingOutboundPort | None = None,
) -> FundingLoanEvent:
    funding_loan, events = _locked_open_funding_events(
        command.funding_loan_id, command.workspace_id
    )
    fingerprint = _fingerprint(command)
    replay = _event_replay(
        funding_loan, "RECORD_REPAYMENT", command.request_key, fingerprint
    )
    if replay is not None:
        return replay
    terms = _domain_terms(funding_loan.terms_snapshot)
    balance = calculate_funding_loan_balance(
        _domain_events(events), currency_quantum=terms.currency_quantum
    )
    try:
        allocation = allocate_funding_repayment(balance, command.amount)
    except ValueError as exc:
        raise FundingLoanServiceError(str(exc)) from exc
    event = _append_funding_event(
        funding_loan,
        events,
        kind=FundingLoanEventKind.REPAYMENT,
        operation="RECORD_REPAYMENT",
        effective_date=command.effective_date,
        request_key=command.request_key,
        request_fingerprint=fingerprint,
        principal_amount=allocation.principal,
        interest_amount=allocation.interest,
        fee_amount=allocation.fees,
        actor=actor,
    )
    (outbound or NullFundingOutboundAdapter()).record(
        funding_loan_id=funding_loan.pk, operation="RECORD_REPAYMENT"
    )
    return event


@transaction.atomic
def reverse_funding_event(
    command: ReverseFundingEvent,
    *,
    actor=None,
    outbound: FundingOutboundPort | None = None,
) -> FundingLoanEvent:
    funding_loan, events = _locked_open_funding_events(
        command.funding_loan_id, command.workspace_id
    )
    fingerprint = _fingerprint(command)
    replay = _event_replay(
        funding_loan, "REVERSE_EVENT", command.request_key, fingerprint
    )
    if replay is not None:
        return replay
    reason = str(command.reason or "").strip()
    if not reason:
        raise FundingLoanServiceError("Funding event reversal requires a reason.")
    original = next(
        (event for event in events if event.pk == command.original_event_id), None
    )
    if original is None:
        raise FundingLoanServiceError(
            "Original funding event was not found in this FundingLoan."
        )
    if original.event_kind == FundingLoanEventKind.ACTIVATION.value:
        raise FundingLoanServiceError(
            "Funding activation cannot be reversed through financial correction."
        )
    try:
        planned = plan_funding_reversal(
            _domain_events(events), original_sequence=original.sequence
        )
    except ValueError as exc:
        raise FundingLoanServiceError(str(exc)) from exc
    reversal = FundingLoanEvent.objects.create(
        funding_loan=funding_loan,
        sequence=planned.sequence,
        event_kind=FundingLoanEventKind.REVERSAL.value,
        operation="REVERSE_EVENT",
        effective_date=command.effective_date,
        principal_amount=planned.principal_amount,
        interest_amount=planned.interest_amount,
        fee_amount=planned.fee_amount,
        request_key=command.request_key,
        request_fingerprint=fingerprint,
        reversal_of=original,
        reason=reason,
        actor=actor,
    )
    (outbound or NullFundingOutboundAdapter()).record(
        funding_loan_id=funding_loan.pk, operation="REVERSE_EVENT"
    )
    return reversal


@transaction.atomic
def begin_funding_settlement(
    command: BeginFundingSettlement,
    *,
    actor=None,
) -> FundingLoan:
    funding_loan = _locked_funding_loan(command.funding_loan_id, command.workspace_id)
    if funding_loan.state == FundingLoanState.SETTLEMENT_PENDING.value:
        return funding_loan
    if funding_loan.state != FundingLoanState.ACTIVE.value:
        raise FundingLoanServiceError("Only an active FundingLoan can begin settlement.")
    terms = _domain_terms(funding_loan.terms_snapshot)
    events = tuple(
        FundingLoanEvent.objects.select_for_update()
        .filter(funding_loan=funding_loan)
        .order_by("sequence")
    )
    balance = calculate_funding_loan_balance(
        _domain_events(events), currency_quantum=terms.currency_quantum
    )
    if not balance.financially_settled:
        raise FundingLoanServiceError(
            "Funding balance must be fully settled before settlement review."
        )
    funding_loan.state = FundingLoanState.SETTLEMENT_PENDING.value
    funding_loan.updated_by = actor
    funding_loan.save(update_fields=["state", "updated_by", "updated_at"])
    return funding_loan


@transaction.atomic
def return_funding_collateral(
    command: ReturnFundingCollateral,
    *,
    actor=None,
    outbound: FundingOutboundPort | None = None,
) -> FundingReturn:
    funding_loan, events = _locked_open_funding_events(
        command.funding_loan_id, command.workspace_id
    )
    fingerprint = _return_fingerprint(command)
    replay = funding_loan.returns.filter(
        operation="RETURN_COLLATERAL", request_key=command.request_key
    ).first()
    if replay is not None:
        if replay.request_fingerprint != fingerprint:
            raise FundingLoanServiceError(
                "Funding return request key was reused with different input."
            )
        return replay
    item_ids = tuple(sorted(set(command.collateral_item_ids)))
    if not item_ids or len(item_ids) != len(command.collateral_item_ids):
        raise FundingLoanServiceError("Funding return requires unique collateral items.")
    pledge_items = tuple(
        FundingPledgeItem.objects.select_for_update()
        .select_related("collateral_item", "collateral_item__loan")
        .filter(
            funding_pledge__funding_loan=funding_loan,
            collateral_item_id__in=item_ids,
            released_at__isnull=True,
        )
        .order_by("collateral_item_id")
    )
    if len(pledge_items) != len(item_ids):
        raise FundingLoanServiceError(
            "Every returned item must be actively pledged to this FundingLoan."
        )
    active_items = tuple(
        FundingPledgeItem.objects.select_for_update()
        .select_related("collateral_item", "collateral_item__loan")
        .filter(funding_pledge__funding_loan=funding_loan, released_at__isnull=True)
        .order_by("collateral_item_id")
    )
    returning_ids = set(item_ids)
    retained_items = tuple(
        item for item in active_items if item.collateral_item_id not in returning_ids
    )
    terms = _domain_terms(funding_loan.terms_snapshot)
    balance = calculate_funding_loan_balance(
        _domain_events(events), currency_quantum=terms.currency_quantum
    )
    try:
        plan_funding_return(
            tuple(_pledge_candidate(item) for item in pledge_items),
            funding_loan_state=FundingLoanState(funding_loan.state),
            principal_outstanding=balance.principal_outstanding,
            maximum_funding_ltv_ratio=terms.maximum_funding_ltv_ratio,
            retained_candidates=tuple(
                _pledge_candidate(item) for item in retained_items
            ),
        )
    except (FundingPledgePolicyError, ValueError) as exc:
        raise FundingLoanServiceError(str(exc)) from exc
    retained_value = sum(
        (item.selected_collateral_value for item in retained_items), Decimal("0")
    )
    retained_ltv = (
        (balance.principal_outstanding / retained_value).quantize(Decimal("0.000001"))
        if retained_value
        else None
    )
    funding_return = FundingReturn.objects.create(
        workspace_id=funding_loan.workspace_id,
        funding_loan=funding_loan,
        effective_date=command.effective_date,
        request_key=command.request_key,
        request_fingerprint=fingerprint,
        principal_outstanding=balance.principal_outstanding,
        retained_collateral_value=retained_value,
        retained_ltv_ratio=retained_ltv,
        evidence_snapshot={"returned_collateral_item_ids": list(item_ids)},
        actor=actor,
    )
    returned_at = timezone.now()
    for pledge_item in pledge_items:
        FundingReturnItem.objects.create(
            funding_return=funding_return,
            pledge_item=pledge_item,
            returned_at=returned_at,
            evidence_snapshot={
                "selected_collateral_value": str(pledge_item.selected_collateral_value)
            },
        )
    for pledge_item in pledge_items:
        pledge_item.released_at = returned_at
        pledge_item.save(update_fields=["released_at"])
        PawnCollateralCustodyEvent.objects.create(
            collateral_item=pledge_item.collateral_item,
            funding_return=funding_return,
            from_state=CollateralCustodyState.WITH_FUNDING_LENDER.value,
            to_state=CollateralCustodyState.IN_VAULT.value,
            effective_date=command.effective_date,
            actor=actor,
        )
        PawnCollateralItem.objects.filter(pk=pledge_item.collateral_item_id).update(
            custody_state=CollateralCustodyState.IN_VAULT.value
        )
    (outbound or NullFundingOutboundAdapter()).record(
        funding_loan_id=funding_loan.pk, operation="RETURN_COLLATERAL"
    )
    return funding_return


@transaction.atomic
def reverse_funding_pledge(
    command: ReverseFundingPledge,
    *,
    actor=None,
    outbound: FundingOutboundPort | None = None,
) -> FundingPledgeReversal:
    funding_loan, events = _locked_open_funding_events(
        command.funding_loan_id, command.workspace_id
    )
    pledge = FundingPledge.objects.select_for_update().get(funding_loan=funding_loan)
    fingerprint = _fingerprint(command)
    try:
        existing = pledge.reversal
    except FundingPledgeReversal.DoesNotExist:
        existing = None
    if existing is not None:
        if existing.request_key != command.request_key or existing.request_fingerprint != fingerprint:
            raise FundingLoanServiceError(
                "Funding pledge was already reversed with different input."
            )
        return existing
    reason = str(command.reason or "").strip()
    if not str(command.request_key or "").strip():
        raise FundingLoanServiceError("Funding pledge reversal requires a request key.")
    if not reason:
        raise FundingLoanServiceError("Funding pledge reversal requires a reason.")
    if funding_loan.state != FundingLoanState.SETTLEMENT_PENDING.value:
        raise FundingLoanServiceError(
            "FundingLoan must be settlement pending before pledge reversal."
        )
    terms = _domain_terms(funding_loan.terms_snapshot)
    balance = calculate_funding_loan_balance(
        _domain_events(events), currency_quantum=terms.currency_quantum
    )
    if not balance.financially_settled:
        raise FundingLoanServiceError(
            "Funding balance must be fully settled before pledge reversal."
        )
    pledge_items = tuple(
        FundingPledgeItem.objects.select_for_update()
        .select_related("collateral_item", "collateral_item__loan")
        .filter(funding_pledge=pledge)
        .order_by("collateral_item_id")
    )
    if not pledge_items or any(item.released_at is not None for item in pledge_items):
        raise FundingLoanServiceError(
            "Funding pledge reversal requires every pledge item to remain active."
        )
    if any(
        item.collateral_item.custody_state
        != CollateralCustodyState.WITH_FUNDING_LENDER.value
        for item in pledge_items
    ):
        raise FundingLoanServiceError(
            "Funding collateral custody changed after pledge and cannot be reversed."
        )
    reversal = FundingPledgeReversal.objects.create(
        funding_pledge=pledge,
        effective_date=command.effective_date,
        request_key=command.request_key,
        request_fingerprint=fingerprint,
        reason=reason,
        actor=actor,
    )
    released_at = timezone.now()
    for pledge_item in pledge_items:
        PawnCollateralCustodyEvent.objects.create(
            collateral_item=pledge_item.collateral_item,
            funding_pledge=pledge,
            funding_pledge_reversal=reversal,
            from_state=CollateralCustodyState.WITH_FUNDING_LENDER.value,
            to_state=CollateralCustodyState.IN_VAULT.value,
            effective_date=command.effective_date,
            actor=actor,
        )
        pledge_item.released_at = released_at
        pledge_item.save(update_fields=["released_at"])
        PawnCollateralItem.objects.filter(pk=pledge_item.collateral_item_id).update(
            custody_state=CollateralCustodyState.IN_VAULT.value
        )
    (outbound or NullFundingOutboundAdapter()).record(
        funding_loan_id=funding_loan.pk, operation="REVERSE_PLEDGE"
    )
    return reversal


@transaction.atomic
def reverse_funding_return(
    command: ReverseFundingReturn,
    *,
    actor=None,
    outbound: FundingOutboundPort | None = None,
) -> FundingReturnReversal:
    funding_loan, _ = _locked_open_funding_events(
        command.funding_loan_id, command.workspace_id
    )
    try:
        funding_return = FundingReturn.objects.select_for_update().get(
            pk=command.funding_return_id,
            funding_loan=funding_loan,
        )
    except FundingReturn.DoesNotExist as exc:
        raise FundingLoanServiceError(
            "Funding return was not found in this FundingLoan."
        ) from exc
    fingerprint = _fingerprint(command)
    try:
        existing = funding_return.reversal
    except FundingReturnReversal.DoesNotExist:
        existing = None
    if existing is not None:
        if existing.request_key != command.request_key or existing.request_fingerprint != fingerprint:
            raise FundingLoanServiceError(
                "Funding return was already reversed with different input."
            )
        return existing
    reason = str(command.reason or "").strip()
    if not str(command.request_key or "").strip():
        raise FundingLoanServiceError("Funding return reversal requires a request key.")
    if not reason:
        raise FundingLoanServiceError("Funding return reversal requires a reason.")
    return_items = tuple(
        FundingReturnItem.objects.select_for_update()
        .select_related("pledge_item", "pledge_item__collateral_item")
        .filter(funding_return=funding_return)
        .order_by("pledge_item__collateral_item_id")
    )
    if not return_items or any(
        item.pledge_item.released_at is None for item in return_items
    ):
        raise FundingLoanServiceError(
            "Funding return reversal requires every returned pledge item to remain released."
        )
    if any(
        item.pledge_item.collateral_item.custody_state
        != CollateralCustodyState.IN_VAULT.value
        for item in return_items
    ):
        raise FundingLoanServiceError(
            "Funding collateral custody changed after return and cannot be reversed."
        )
    reversal = FundingReturnReversal.objects.create(
        funding_return=funding_return,
        effective_date=command.effective_date,
        request_key=command.request_key,
        request_fingerprint=fingerprint,
        reason=reason,
        actor=actor,
    )
    for return_item in return_items:
        pledge_item = return_item.pledge_item
        PawnCollateralCustodyEvent.objects.create(
            collateral_item=pledge_item.collateral_item,
            funding_return=funding_return,
            funding_return_reversal=reversal,
            from_state=CollateralCustodyState.IN_VAULT.value,
            to_state=CollateralCustodyState.WITH_FUNDING_LENDER.value,
            effective_date=command.effective_date,
            actor=actor,
        )
        pledge_item.released_at = None
        pledge_item.save(update_fields=["released_at"])
        PawnCollateralItem.objects.filter(pk=pledge_item.collateral_item_id).update(
            custody_state=CollateralCustodyState.WITH_FUNDING_LENDER.value
        )
    (outbound or NullFundingOutboundAdapter()).record(
        funding_loan_id=funding_loan.pk, operation="REVERSE_RETURN"
    )
    return reversal


@transaction.atomic
def close_funding_loan(command: CloseFundingLoan, *, actor=None) -> FundingLoan:
    funding_loan, events = _locked_open_funding_events(
        command.funding_loan_id, command.workspace_id, allow_closed=True
    )
    if funding_loan.state == FundingLoanState.CLOSED.value:
        return funding_loan
    if funding_loan.state != FundingLoanState.SETTLEMENT_PENDING.value:
        raise FundingLoanServiceError(
            "FundingLoan must be settlement pending before closure."
        )
    terms = _domain_terms(funding_loan.terms_snapshot)
    balance = calculate_funding_loan_balance(
        _domain_events(events), currency_quantum=terms.currency_quantum
    )
    pledge_items = tuple(
        FundingPledgeItem.objects.select_for_update()
        .select_related("collateral_item", "collateral_item__loan")
        .filter(funding_pledge__funding_loan=funding_loan)
        .order_by("collateral_item_id")
    )
    readiness = assess_funding_closure(
        balance, tuple(_pledge_candidate(item) for item in pledge_items)
    )
    if not readiness.ready:
        raise FundingLoanServiceError(" ".join(readiness.blockers))
    funding_loan.state = FundingLoanState.CLOSED.value
    funding_loan.updated_by = actor
    funding_loan.save(update_fields=["state", "updated_by", "updated_at"])
    return funding_loan


def _allocate_funding_number(workspace_id: int) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(%s, %s)",
            [0x464C, workspace_id],
        )
    sequence, _ = FundingLoanSequence.objects.get_or_create(workspace_id=workspace_id)
    sequence = FundingLoanSequence.objects.select_for_update().get(pk=sequence.pk)
    if sequence.maximum_value is not None and sequence.next_value > sequence.maximum_value:
        raise FundingLoanServiceError("The FundingLoan number sequence is exhausted.")
    value = f"{sequence.prefix}{sequence.next_value:0{sequence.width}d}"
    FundingLoanSequence.objects.filter(pk=sequence.pk).update(
        next_value=sequence.next_value + 1
    )
    return value


def _locked_funding_loan(funding_loan_id: int, workspace_id: int) -> FundingLoan:
    active_workspace_id = _require_workspace(workspace_id)
    try:
        return FundingLoan.objects.select_for_update().get(
            pk=funding_loan_id,
            workspace_id=active_workspace_id,
        )
    except FundingLoan.DoesNotExist as exc:
        raise FundingLoanServiceError(
            "FundingLoan was not found in the active workspace."
        ) from exc


def _locked_collateral(workspace_id: int, collateral_ids: tuple[int, ...]):
    pawn_loan_ids = tuple(
        PawnCollateralItem.objects.filter(pk__in=collateral_ids)
        .order_by("loan_id")
        .values_list("loan_id", flat=True)
        .distinct()
    )
    tuple(
        PawnLoan.objects.select_for_update()
        .filter(pk__in=pawn_loan_ids, workspace_id=workspace_id)
        .order_by("pk")
    )
    collateral = tuple(
        PawnCollateralItem.objects.select_for_update()
        .select_related("loan")
        .filter(pk__in=collateral_ids, loan__workspace_id=workspace_id)
        .order_by("pk")
    )
    if len(collateral) != len(collateral_ids):
        raise FundingLoanServiceError(
            "Every collateral item must exist in the active workspace."
        )
    return collateral


def _activation_replay(funding_loan, request_key, fingerprint):
    event = funding_loan.events.filter(
        operation="ACTIVATE",
        request_key=request_key,
    ).first()
    if event is None:
        return None
    if event.request_fingerprint != fingerprint:
        raise FundingLoanServiceError(
            "Funding activation request key was reused with different input."
        )
    try:
        return FundingActivationResult(
            funding_loan,
            funding_loan.terms_snapshot,
            event,
            funding_loan.pledge,
            already_activated=True,
        )
    except (FundingLoanTermsSnapshot.DoesNotExist, FundingPledge.DoesNotExist) as exc:
        raise FundingLoanServiceError(
            "Funding activation evidence is incomplete."
        ) from exc


def _locked_open_funding_events(funding_loan_id, workspace_id, *, allow_closed=False):
    funding_loan = _locked_funding_loan(funding_loan_id, workspace_id)
    allowed = {
        FundingLoanState.ACTIVE.value,
        FundingLoanState.SETTLEMENT_PENDING.value,
    }
    if allow_closed:
        allowed.add(FundingLoanState.CLOSED.value)
    if funding_loan.state not in allowed:
        raise FundingLoanServiceError("FundingLoan must be open for servicing.")
    events = tuple(
        FundingLoanEvent.objects.select_for_update()
        .filter(funding_loan=funding_loan)
        .order_by("sequence")
    )
    return funding_loan, events


def _append_funding_event(
    funding_loan,
    events,
    *,
    kind,
    operation,
    effective_date,
    request_key,
    request_fingerprint,
    principal_amount=Decimal("0"),
    interest_amount=Decimal("0"),
    fee_amount=Decimal("0"),
    actor=None,
):
    if not str(request_key or "").strip():
        raise FundingLoanServiceError(f"{operation} requires a request key.")
    return FundingLoanEvent.objects.create(
        funding_loan=funding_loan,
        sequence=events[-1].sequence + 1,
        event_kind=kind.value,
        operation=operation,
        effective_date=effective_date,
        principal_amount=principal_amount,
        interest_amount=interest_amount,
        fee_amount=fee_amount,
        request_key=request_key,
        request_fingerprint=request_fingerprint,
        actor=actor,
    )


def _event_replay(funding_loan, operation, request_key, fingerprint):
    if not str(request_key or "").strip():
        raise FundingLoanServiceError(f"{operation} requires a request key.")
    event = funding_loan.events.filter(operation=operation, request_key=request_key).first()
    if event is not None and event.request_fingerprint != fingerprint:
        raise FundingLoanServiceError(
            f"{operation} request key was reused with different input."
        )
    return event


def _domain_terms(snapshot):
    return FundingLoanTerms(
        principal_amount=snapshot.principal_amount,
        monthly_interest_rate=snapshot.monthly_interest_rate,
        activated_on=snapshot.activated_on,
        maturity_on=snapshot.maturity_on,
        maximum_funding_ltv_ratio=snapshot.maximum_funding_ltv_ratio,
        currency_quantum=snapshot.currency_quantum,
    )


def _domain_events(events):
    return tuple(
        DomainFundingLoanEvent(
            sequence=event.sequence,
            kind=FundingLoanEventKind(event.event_kind),
            principal_amount=event.principal_amount,
            interest_amount=event.interest_amount,
            fee_amount=event.fee_amount,
            reversal_of_sequence=(
                event.reversal_of.sequence if event.reversal_of_id else None
            ),
        )
        for event in events
    )


def _pledge_candidate(pledge_item):
    return FundingCollateralCandidate(
        collateral_item_id=pledge_item.collateral_item_id,
        pawn_loan_id=pledge_item.source_pawn_loan_id,
        pawn_loan_state=PawnLoanState(pledge_item.collateral_item.loan.state),
        custody_state=CollateralCustodyState(
            pledge_item.collateral_item.custody_state
        ),
        active_funding_pledge_id=(None if pledge_item.released_at else pledge_item.pk),
        collateral_value=pledge_item.selected_collateral_value,
    )


def _activation_fingerprint(command):
    value = asdict(command)
    value["collateral"] = sorted(
        value["collateral"], key=lambda item: item["collateral_item_id"]
    )
    return _fingerprint(value)


def _return_fingerprint(command):
    value = asdict(command)
    value["collateral_item_ids"] = sorted(value["collateral_item_ids"])
    return _fingerprint(value)


def _active_party(party_id: int) -> Party:
    try:
        return Party.objects.get(pk=party_id, status=Party.PartyStatus.ACTIVE)
    except Party.DoesNotExist as exc:
        raise FundingLoanServiceError(
            "Lender must be an active Party in this workspace."
        ) from exc


def _require_workspace(expected_workspace_id: int) -> int:
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise FundingLoanServiceError("FundingLoan operations require an active tenant schema.")
    if workspace_id != expected_workspace_id:
        raise FundingLoanServiceError("FundingLoan workspace must match the active tenant.")
    return workspace_id


def _fingerprint(value) -> str:
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
