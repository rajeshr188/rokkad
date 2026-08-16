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
    LoanLicense,
    LoanPolicySnapshot,
    LoanSeries,
    PawnCollateralCustodyEvent,
    PawnCollateralItem,
    PawnLoan,
    PawnLoanEvent,
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
from apps.tenant_apps.loans.services.event_recording import (
    record_loan_event,
)
from apps.tenant_apps.loans.services.pawn_disbursal import (
    assert_pawn_loan_financial_actions_allowed,
)
from apps.tenant_apps.loans.services.pawn_drafts import (
    CollateralDraftInput,
    CreatePawnDraftCommand,
    create_pawn_draft,
)
from apps.tenant_apps.loans.services.pawn_economics import (
    resolve_pawn_draft_economics,
)
from apps.tenant_apps.loans.services.license_series import assert_series_can_issue
from apps.tenant_apps.loans.services.pawn_interest import (
    build_pawn_accrual_detail,
    persist_pawn_accrual_lines,
    preview_pawn_loan_accruals,
    should_record_pawn_accrual_event,
)
from apps.tenant_apps.loans.services.pawn_lifecycle import approve_pawn_loan
from apps.tenant_apps.loans.services.collateral_media import (
    append_collateral_photo,
    inherit_collateral_photos,
)
from apps.tenant_apps.loans.services.storage_operations import (
    carry_storage_to_renewal_successor,
    remove_collateral_from_storage,
)
from apps.tenant_apps.loans.services.pawn_tranches import (
    PawnTrancheBalanceError,
    get_pawn_principal_tranche_balances,
)
from apps.tenant_apps.loans.services.obligations import (
    allocate_event_to_obligations,
    persist_disbursal_repayment_schedule,
    reverse_event_obligation_allocations,
    terminate_active_repayment_schedule,
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
    settlement_event: PawnLoanEvent
    opening_event: PawnLoanEvent
    already_renewed: bool = False


@dataclass(frozen=True)
class PawnRenewalReversalResult:
    renewal: PawnLoanRenewal
    reversal: PawnLoanRenewalReversal
    settlement_reversal_event: PawnLoanEvent
    opening_reversal_event: PawnLoanEvent
    catch_up_reversal_event: PawnLoanEvent | None
    already_reversed: bool = False


@dataclass(frozen=True)
class PawnRenewalSourcePreview:
    source_loan: PawnLoan
    source_items: tuple[PawnCollateralItem, ...]
    balance: object
    release_day_accrual: object | None
    readiness: object

    @property
    def source_principal(self):
        return self.balance.principal_outstanding

    @property
    def release_day_interest(self):
        return (
            self.release_day_accrual.recognized_interest
            if self.release_day_accrual is not None
            else Decimal("0")
        )

    @property
    def interest_settled(self):
        return self.balance.interest_outstanding + self.release_day_interest

    @property
    def fees_settled(self):
        return self.balance.fees_outstanding

    @property
    def base_cash_received(self):
        """Interest and fees collected before principal paydown/top-up netting."""
        return self.interest_settled + self.fees_settled

    @property
    def item_valuations(self):
        return self.readiness.item_valuations


@dataclass(frozen=True)
class PawnRenewalPlanPreview:
    fingerprint: str
    source: PawnRenewalSourcePreview
    successor_principal: Decimal
    successor_monthly_interest: Decimal
    successor_advance_interest: Decimal
    successor_deducted_fees: Decimal
    principal_paid: Decimal
    top_up_amount: Decimal
    retained_item_ids: frozenset[int]
    returned_item_ids: tuple[int, ...]
    successor_collateral_count: int

    @property
    def total_cash_received(self):
        return (
            self.source.base_cash_received
            + self.principal_paid
            + self.successor_advance_interest
            + self.successor_deducted_fees
        )

    @property
    def net_cash_amount(self):
        return self.total_cash_received - self.top_up_amount

    @property
    def net_cash_direction(self):
        if self.net_cash_amount > 0:
            return "COLLECT_FROM_CUSTOMER"
        if self.net_cash_amount < 0:
            return "PAY_TO_CUSTOMER"
        return "NO_NET_CASH"


def preview_pawn_loan_renewal_source(
    source_loan_id: int,
) -> PawnRenewalSourcePreview:
    """Return current source settlement facts without locks or writes."""
    source = _tenant_loan(source_loan_id)
    if source.state != PawnLoanState.ACTIVE.value:
        raise PawnRenewalError("Only an active PawnLoan can be renewed.")
    if hasattr(source, "renewal_as_source"):
        raise PawnRenewalError("This PawnLoan already has a renewal successor.")
    if source.auctions.filter(state__in=("INITIATED", "IN_PROGRESS")).exists():
        raise PawnRenewalError("Cancel the active auction before renewing this loan.")
    items = tuple(source.collateral_items.order_by("pk"))
    if not items or any(
        item.custody_state != CollateralCustodyState.IN_VAULT.value
        for item in items
    ):
        raise PawnRenewalError(
            "Every collateral item must be in the vault before renewal."
        )
    from .physical_verification import (
        PawnPhysicalVerificationBlockerError,
        assert_physical_verification_clear,
    )

    try:
        assert_physical_verification_clear(
            (item.pk for item in items), operation="PawnLoan release and renew"
        )
    except PawnPhysicalVerificationBlockerError as exc:
        raise PawnRenewalError(str(exc)) from exc
    try:
        assert_pawn_loan_financial_actions_allowed(source.pk, lock=False)
        effective_date = timezone.localdate()
        completed = preview_pawn_loan_accruals(
            source.pk,
            as_of_date=effective_date,
            include_partial=False,
        )
        if completed:
            raise PawnRenewalError(
                "Finalize every completed interest period before renewal."
            )
        partials = preview_pawn_loan_accruals(
            source.pk,
            as_of_date=effective_date,
            include_partial=True,
        )
        partial = partials[0] if partials and partials[0].is_partial else None
        balance = get_pawn_loan_balance(source.pk, as_of_date=effective_date)
        readiness = get_pawn_loan_release_readiness(
            source.pk,
            selected_item_ids=tuple(item.pk for item in items),
            as_of_date=effective_date,
        )
        if readiness.blockers:
            raise PawnRenewalError(
                "; ".join(blocker.message for blocker in readiness.blockers)
            )
    except PawnRenewalError:
        raise
    except Exception as exc:
        raise PawnRenewalError(str(exc)) from exc
    return PawnRenewalSourcePreview(
        source_loan=source,
        source_items=items,
        balance=balance,
        release_day_accrual=partial,
        readiness=readiness,
    )


def preview_pawn_loan_renewal_plan(
    source_loan_id: int,
    *,
    mode,
    principal_paid,
    top_up_amount,
    successor_license_id: int,
    successor_series_id: int,
    tenure_months: int,
    retained_collateral: tuple[RetainedCollateralInput, ...],
    additional_collateral: tuple[CollateralDraftInput, ...] = (),
) -> PawnRenewalPlanPreview:
    """Validate and price a complete renewal plan without allocating a number."""
    source_preview = preview_pawn_loan_renewal_source(source_loan_id)
    source = source_preview.source_loan
    try:
        renewal_mode = PawnLoanRenewalMode(mode)
    except ValueError as exc:
        raise PawnRenewalError("Unknown PawnLoan renewal mode.") from exc
    principal_paid = _money(principal_paid, source)
    top_up_amount = _money(top_up_amount, source)
    if not 1 <= int(tenure_months) <= 600:
        raise PawnRenewalError("Renewal tenure must be between 1 and 600 months.")
    if renewal_mode == PawnLoanRenewalMode.PAY_AND_RENEW:
        if top_up_amount != 0:
            raise PawnRenewalError("Pay-and-renew cannot include a top-up amount.")
    elif top_up_amount <= 0 or principal_paid != 0:
        raise PawnRenewalError(
            "Top-up renewal requires a positive top-up and no simultaneous principal paydown."
        )
    balance = source_preview.balance
    quantum = Decimal(str(source.policy_snapshot.currency_quantum)).normalize()
    successor_principal = (
        balance.principal_outstanding - principal_paid + top_up_amount
    ).quantize(quantum)
    if successor_principal <= 0:
        raise PawnRenewalError(
            "Renewal must carry a positive principal; use full release to settle the loan."
        )
    successor_collateral, retained_ids = _successor_collateral_plan(
        source_preview.source_items,
        retained_collateral=retained_collateral,
        additional_collateral=additional_collateral,
        successor_principal=successor_principal,
    )
    workspace_id = source.workspace_id
    try:
        license = LoanLicense.objects.get(
            pk=successor_license_id,
            workspace_id=workspace_id,
        )
        series = LoanSeries.objects.select_related("license").get(
            pk=successor_series_id,
            license=license,
        )
        assert_series_can_issue(series, as_of_date=timezone.localdate())
        resolved = resolve_pawn_draft_economics(
            workspace_id=workspace_id,
            license_id=license.pk,
            as_of_date=timezone.localdate(),
            collateral=successor_collateral,
        )
    except (LoanLicense.DoesNotExist, LoanSeries.DoesNotExist) as exc:
        raise PawnRenewalError(
            "Successor license and series must belong to the active workspace."
        ) from exc
    except Exception as exc:
        raise PawnRenewalError(str(exc)) from exc
    economics = resolved.economics
    if economics.gross_principal != successor_principal:
        raise PawnRenewalError(
            "Successor collateral allocations do not reconcile to successor principal."
        )
    if balance.capitalized_interest_principal_outstanding:
        raise PawnRenewalError(
            "Release and renew cannot carry capitalized interest until it has "
            "explicit successor-item attribution. Settle it before renewal."
        )
    return PawnRenewalPlanPreview(
        fingerprint=_renewal_plan_fingerprint(
            source_loan_id=source.pk,
            effective_date=timezone.localdate(),
            mode=renewal_mode.value,
            principal_paid=principal_paid,
            top_up_amount=top_up_amount,
            successor_license_id=license.pk,
            successor_series_id=series.pk,
            tenure_months=int(tenure_months),
            retained_collateral=retained_collateral,
            additional_collateral=additional_collateral,
            successor_principal=successor_principal,
            successor_advance_interest=economics.advance_interest,
            successor_deducted_fees=economics.deducted_fees,
        ),
        source=source_preview,
        successor_principal=successor_principal,
        successor_monthly_interest=economics.monthly_interest,
        successor_advance_interest=economics.advance_interest,
        successor_deducted_fees=economics.deducted_fees,
        principal_paid=principal_paid,
        top_up_amount=top_up_amount,
        retained_item_ids=retained_ids,
        returned_item_ids=tuple(
            item.pk
            for item in source_preview.source_items
            if item.pk not in retained_ids
        ),
        successor_collateral_count=len(successor_collateral),
    )


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
    additional_photo_uploads: tuple = (),
    expected_preview_fingerprint: str | None = None,
    actor=None,
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
    ).select_related("source_loan", "successor_loan", "settlement_event", "opening_event").first()
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
            existing.opening_event,
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
    from .physical_verification import (
        PawnPhysicalVerificationBlockerError,
        assert_physical_verification_clear,
    )

    try:
        assert_physical_verification_clear(
            (item.pk for item in items), operation="PawnLoan release and renew"
        )
    except PawnPhysicalVerificationBlockerError as exc:
        raise PawnRenewalError(str(exc)) from exc
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
        currency_quantum = Decimal(
            str(source.policy_snapshot.currency_quantum)
        ).normalize()
        successor_principal = (
            balance.principal_outstanding - principal_paid + top_up_amount
        ).quantize(currency_quantum)
        if successor_principal <= 0:
            raise PawnRenewalError(
                "Renewal must carry a positive principal; use full release to settle the loan."
            )
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
            product_version_id=source.product_version_id,
            principal_amount=successor_principal,
            monthly_interest_rate=monthly_interest_rate or Decimal("0"),
            loan_date=renewal_date,
            tenure_months=int(tenure_months),
            collateral=successor_collateral,
        ),
        actor=actor,
    )
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
        inherit_collateral_photos(
            source_by_id[source_item_id], new_item, actor=actor
        )
    additional_items = successor_items[len(retained_ids_in_order):]
    if len(additional_items) != len(additional_photo_uploads):
        raise PawnRenewalError(
            "Every additional renewal collateral item requires one photograph."
        )
    for item, upload in zip(additional_items, additional_photo_uploads, strict=True):
        append_collateral_photo(
            item.pk,
            upload=upload,
            actor=actor,
            workflow_source="RENEWAL",
        )
    approval = approve_pawn_loan(successor.pk, actor=actor)
    successor_economics = _successor_approval_economics(successor, approval)
    successor_policy = _successor_policy_from_approval(
        successor,
        successor_economics,
    )
    actual_preview_fingerprint = _renewal_plan_fingerprint(
        source_loan_id=source.pk,
        effective_date=renewal_date,
        mode=renewal_mode.value,
        principal_paid=principal_paid,
        top_up_amount=top_up_amount,
        successor_license_id=successor_license_id,
        successor_series_id=successor_series_id,
        tenure_months=int(tenure_months),
        retained_collateral=retained_collateral,
        additional_collateral=additional_collateral,
        successor_principal=successor_principal,
        successor_advance_interest=successor_economics["advance_interest"],
        successor_deducted_fees=successor_economics["deducted_fees"],
    )
    if (
        expected_preview_fingerprint is not None
        and expected_preview_fingerprint != actual_preview_fingerprint
    ):
        raise PawnRenewalError(
            "Renewal economics changed after preview; calculate and review it again."
        )

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
    source_control = balance.principal_outstanding
    successor_control = successor_principal
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
        "successor_advance_interest": str(
            successor_economics["advance_interest"]
        ),
        "successor_deducted_fees": str(
            successor_economics["deducted_fees"]
        ),
        "catch_up_event_id": (
            catch_up.loan_event_id if catch_up is not None else None
        ),
        "retained_source_item_ids": list(retained_item_ids),
        "returned_source_item_ids": [
            item.pk for item in items if item.pk not in retained_item_ids
        ],
    }
    settlement_event, _ = record_loan_event(
        source.pk,
        event_kind=TransactionKind.RENEWAL_SETTLEMENT,
        effective_date=renewal_date,
        payload=settlement_payload,
        actor=actor,
    )
    allocate_event_to_obligations(
        source_event=settlement_event,
        principal_amount=balance.principal_outstanding,
        interest_amount=balance.interest_outstanding,
        actor=actor,
    )
    terminate_active_repayment_schedule(
        loan=source,
        source_event=settlement_event,
        reason="RENEWAL_SETTLEMENT",
        actor=actor,
    )
    for order, row in enumerate(
        sorted(
            source_tranches,
            key=lambda value: (-value.monthly_interest_rate, value.collateral_item_id),
        ),
        start=1,
    ):
        PawnLoanPrincipalClosingLine.objects.create(
            loan_event=settlement_event,
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
        "successor_economics": {
            "approval_snapshot_id": approval.pk,
            "policy_snapshot_id": successor_policy.pk,
            "advance_interest_periods": successor_economics[
                "advance_interest_periods"
            ],
            "monthly_interest": str(successor_economics["monthly_interest"]),
            "advance_interest": str(successor_economics["advance_interest"]),
            "deducted_fees": str(successor_economics["deducted_fees"]),
            "tranches": successor_economics["evidence"].get("tranches", []),
            "fees": successor_economics["evidence"].get("fees", []),
        },
    }
    opening_event, _ = record_loan_event(
        successor.pk,
        event_kind=TransactionKind.RENEWAL_OPENING,
        effective_date=renewal_date,
        payload=opening_payload,
        actor=actor,
    )
    persist_disbursal_repayment_schedule(
        successor,
        source_event=opening_event,
        disbursed_on=renewal_date,
        currency_quantum=successor_policy.currency_quantum,
        actor=actor,
    )
    if sum(
        (item.allocated_principal for item in successor_items), Decimal("0")
    ) != successor_original:
        raise PawnRenewalError(
            "Successor item principal does not reconcile to original principal."
        )
    for order, item in enumerate(successor_items, start=1):
        PawnLoanPrincipalOpeningLine.objects.create(
            loan_event=opening_event,
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
        "successor_economics": {
            "policy_snapshot_id": successor_policy.pk,
            "advance_interest_periods": successor_economics[
                "advance_interest_periods"
            ],
            "monthly_interest": str(successor_economics["monthly_interest"]),
            "advance_interest": str(successor_economics["advance_interest"]),
            "deducted_fees": str(successor_economics["deducted_fees"]),
            "tranches": successor_economics["evidence"].get("tranches", []),
            "fees": successor_economics["evidence"].get("fees", []),
        },
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
        successor_advance_interest=successor_economics["advance_interest"],
        successor_deducted_fees=successor_economics["deducted_fees"],
        valuation_snapshot=valuation_snapshot,
        settlement_event=settlement_event,
        opening_event=opening_event,
        catch_up_accrual=catch_up,
        created_by=actor,
    )
    effective_now = timezone.now()
    successor_by_source = {
        item.renewed_from_id: item
        for item in successor_items
        if item.renewed_from_id is not None
    }
    for old_item in items:
        retained = old_item.pk in retained_item_ids
        destination = (
            CollateralCustodyState.RENEWAL_TRANSFERRED.value
            if retained
            else CollateralCustodyState.WITH_CUSTOMER.value
        )
        if retained:
            carry_storage_to_renewal_successor(
                old_item,
                successor_by_source[old_item.pk],
                renewal=renewal,
                actor=actor,
            )
        else:
            remove_collateral_from_storage(
                old_item,
                workflow_source="RENEWAL_RETURN",
                source_reference=str(renewal.pk),
                actor=actor,
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
        opening_event,
    )


@transaction.atomic
def reverse_pawn_loan_renewal(
    renewal_id: int,
    *,
    reason: str,
    actor,
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
    source_transition_rows = tuple(
        PawnCollateralCustodyEvent.objects.select_for_update().filter(
            renewal=renewal,
            renewal_reversal__isnull=True,
            collateral_item__loan=renewal.source_loan,
        )
    )
    source_transitions = {
        event.collateral_item_id: event for event in source_transition_rows
    }
    if (
        len(source_transition_rows) != len(source_items)
        or set(source_transitions) != {item.pk for item in source_items}
    ):
        raise PawnRenewalError(
            "Renewal source custody evidence is missing or duplicated."
        )
    if any(
        item.custody_state != source_transitions[item.pk].to_state
        for item in source_items
    ):
        raise PawnRenewalError("Source collateral custody changed after renewal.")
    if any(item.custody_state != CollateralCustodyState.IN_VAULT.value for item in successor_items):
        raise PawnRenewalError("Successor collateral custody changed after renewal.")
    from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event

    opening_result = reverse_pawn_loan_event(
        renewal.opening_event_id,
        reason=reason,
        actor=actor,
        allow_renewal=True,
    )
    settlement_result = reverse_pawn_loan_event(
        renewal.settlement_event_id,
        reason=reason,
        actor=actor,
        allow_renewal=True,
    )
    catch_up_reversal = _reverse_catch_up(
        renewal,
        reason=reason,
        actor=actor,
    )
    reversal = PawnLoanRenewalReversal.objects.create(
        renewal=renewal,
        settlement_reversal_event=settlement_result.reversal_event,
        opening_reversal_event=opening_result.reversal_event,
        catch_up_reversal_event=catch_up_reversal,
        reason=reason,
        created_by=actor,
    )
    for item in successor_items:
        if item.renewed_from_id:
            carry_storage_to_renewal_successor(
                item,
                next(
                    source
                    for source in source_items
                    if source.pk == item.renewed_from_id
                ),
                renewal=reversal,
                actor=actor,
                workflow_source="RENEWAL_REVERSAL",
            )
        else:
            remove_collateral_from_storage(
                item,
                workflow_source="RENEWAL_REVERSAL",
                source_reference=str(reversal.pk),
                actor=actor,
            )
    effective_date = timezone.localdate()
    for item in source_items:
        transition = source_transitions[item.pk]
        PawnCollateralCustodyEvent.objects.create(
            collateral_item=item,
            renewal=renewal,
            renewal_reversal=reversal,
            from_state=transition.to_state,
            to_state=transition.from_state,
            effective_date=effective_date,
            actor=actor,
        )
        item.custody_state = transition.from_state
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


def _record_renewal_accrual(loan, *, preview, actor):
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
        payload["accrual"]["renewal_catch_up"] = True
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
        from_state=loan.state,
        to_state=loan.state,
        actor=actor,
        metadata={
            "period_number": preview.period_number,
            "renewal_catch_up": True,
            "loan_event_id": event.pk if event else None,
        },
    )
    return accrual


def _reverse_catch_up(renewal, *, reason, actor):
    accrual = renewal.catch_up_accrual
    if not accrual or not accrual.loan_event_id:
        return None
    original = accrual.loan_event
    payload = reversal_payload(
        renewal.source_loan,
        effective_date=timezone.localdate(),
        original_event_id=original.pk,
        original_event_kind=original.event_kind,
        values=original.payload.get("values") or {},
        reason=reason,
    ).to_dict()
    payload["reversal"]["renewal_id"] = renewal.pk
    event, _ = record_loan_event(
        renewal.source_loan_id,
        event_kind=TransactionKind.REVERSAL,
        effective_date=timezone.localdate(),
        payload=payload,
        actor=actor,
        reversal_of=original,
    )
    reverse_event_obligation_allocations(
        original_event=original,
        reversal_event=event,
        actor=actor,
    )
    return event


def _successor_approval_economics(successor, approval):
    evidence = approval.payload.get("collateral_economics")
    if evidence is None:
        raise PawnRenewalError(
            "Renewal successor approval is missing collateral economics."
        )
    try:
        values = {
            "gross_principal": Decimal(str(approval.payload["principal_amount"])),
            "monthly_interest": Decimal(str(evidence["monthly_interest"])),
            "advance_interest_periods": int(evidence["advance_interest_periods"]),
            "advance_interest": Decimal(str(evidence["advance_interest"])),
            "deducted_fees": Decimal(str(evidence["deducted_fees"])),
            "net_disbursed": Decimal(str(evidence["net_disbursed"])),
            "evidence": evidence,
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise PawnRenewalError(
            "Renewal successor approval has incomplete economics."
        ) from exc
    if not evidence.get("tranches"):
        raise PawnRenewalError(
            "Renewal successor approval is missing tranche evidence."
        )
    if values["gross_principal"] != successor.principal_amount:
        raise PawnRenewalError(
            "Renewal successor approved principal no longer matches the loan."
        )
    if (
        values["net_disbursed"]
        + values["advance_interest"]
        + values["deducted_fees"]
        != values["gross_principal"]
    ):
        raise PawnRenewalError(
            "Renewal successor gross-to-net economics do not reconcile."
        )
    return values


def _successor_policy_from_approval(successor, economics):
    evidence = economics["evidence"]
    required = (
        "interest_method",
        "partial_month_method",
        "partial_month_cutoff_days",
        "partial_month_lower_fraction",
        "capitalization_interval_periods",
        "valuation_method",
        "maximum_ltv_ratio",
        "rounding_method",
        "currency_quantum",
    )
    if any(key not in evidence for key in required):
        raise PawnRenewalError(
            "Renewal successor approval is missing frozen policy evidence."
        )
    try:
        return LoanPolicySnapshot.objects.create(
            loan=successor,
            policy_version=1,
            interest_method=evidence["interest_method"],
            partial_month_method=evidence["partial_month_method"],
            partial_month_cutoff_days=int(evidence["partial_month_cutoff_days"]),
            partial_month_lower_fraction=Decimal(
                str(evidence["partial_month_lower_fraction"])
            ),
            capitalization_interval_periods=int(
                evidence["capitalization_interval_periods"]
            ),
            valuation_method=evidence["valuation_method"],
            maximum_ltv_ratio=Decimal(str(evidence["maximum_ltv_ratio"])),
            rounding_method=evidence["rounding_method"],
            currency_quantum=Decimal(str(evidence["currency_quantum"])),
        )
    except (TypeError, ValueError) as exc:
        raise PawnRenewalError(
            "Renewal successor approval has invalid frozen policy evidence."
        ) from exc


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
        if len(source_items) != 1:
            raise PawnRenewalError(
                "A multi-item renewal requires an explicit retained-collateral plan."
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
                    allocated_principal=successor_principal,
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


def _renewal_plan_fingerprint(**values):
    return _renewal_request_fingerprint(**values)


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


def _tenant_loan(loan_id):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnRenewalError("PawnLoan renewal requires an active tenant schema.")
    try:
        return (
            PawnLoan.objects.select_related(
                "workspace", "license", "series", "borrower", "policy_snapshot"
            )
            .prefetch_related("collateral_items")
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
                "settlement_event",
                "opening_event",
                "catch_up_accrual__loan_event",
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
    "PawnRenewalPlanPreview",
    "PawnRenewalSourcePreview",
    "preview_pawn_loan_renewal_plan",
    "preview_pawn_loan_renewal_source",
    "renew_pawn_loan",
    "reverse_pawn_loan_renewal",
]
