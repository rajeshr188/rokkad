from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from viewflow import fsm

from apps.orgs.models import Membership
from apps.tenant_apps.girvi.service_modules.overdue_policy import evaluate_overdue_policy

from .models.loan import LoanChangeLog
from .models.loan_refactored import (
    BaseLoan,
    GivenLoan,
    LoanLifecycleState,
    LoanStatus,
    TakenLoan,
    TakenLoanLifecycleState,
)


GIVEN_LOAN_LEGACY_STATUS_MAP = {
    LoanStatus.CREATED: LoanLifecycleState.DRAFT,
    LoanStatus.APPROVED: LoanLifecycleState.APPROVED,
    LoanStatus.DISBURSED: LoanLifecycleState.ACTIVE_CURRENT,
    LoanStatus.DEFAULTED: LoanLifecycleState.ACTIVE_NPA,
    LoanStatus.AUCTIONED: LoanLifecycleState.AUCTION_COMPLETE,
    LoanStatus.RELEASED: LoanLifecycleState.CLOSED,
    LoanStatus.CLOSED: LoanLifecycleState.CLOSED,
    LoanStatus.REPLEDGED: LoanLifecycleState.RENEWED,
    LoanStatus.REJECTED: LoanLifecycleState.REJECTED,
    LoanStatus.CANCELLED: LoanLifecycleState.CANCELLED,
    LoanStatus.SOLD: LoanLifecycleState.AUCTION_COMPLETE,
}

TAKEN_LOAN_LEGACY_STATUS_MAP = {
    LoanStatus.CREATED: TakenLoanLifecycleState.DRAFT,
    LoanStatus.APPROVED: TakenLoanLifecycleState.DRAFT,
    LoanStatus.DISBURSED: TakenLoanLifecycleState.ACTIVE,
    LoanStatus.RELEASED: TakenLoanLifecycleState.CLOSED,
    LoanStatus.CLOSED: TakenLoanLifecycleState.CLOSED,
    LoanStatus.CANCELLED: TakenLoanLifecycleState.CANCELLED,
    LoanStatus.REJECTED: TakenLoanLifecycleState.CANCELLED,
    LoanStatus.DEFAULTED: TakenLoanLifecycleState.ACTIVE,
    LoanStatus.AUCTIONED: TakenLoanLifecycleState.ACTIVE,
    LoanStatus.SOLD: TakenLoanLifecycleState.ACTIVE,
    LoanStatus.REPLEDGED: TakenLoanLifecycleState.ACTIVE,
}

GIVEN_TRANSITION_ALIAS_MAP = {
    "approve": "approve_loan",
    "reject": "reject_loan",
    "cancel": "cancel_loan",
    "disburse": "disburse_loan",
    "undo_disburse": "undo_disbursal",
    "mark_defaulted": "mark_npa",
    "release": "request_closure",
    "deliver": "request_closure",
}

TAKEN_TRANSITION_ALIAS_MAP = {
    "approve": "activate",
    "disburse": "activate",
    "disburse_loan": "activate",
    "cancel": "cancel_loan",
    "close": "request_settlement",
}

TRANSITION_ACCOUNTING_IMPACT = {
    "approve_loan": False,
    "disburse_loan": True,
    "cancel_loan": False,
    "mark_npa": False,
    "complete_auction": True,
    "write_off_loan": True,
    "undo_disbursal": True,
    "request_closure": False,
    "complete_closure": True,
    "activate": True,
    "request_settlement": False,
    "complete_settlement": True,
}

TRANSITION_DESCRIPTIONS = {
    "approve_loan": "Loan reviewed and approved for disbursement. No accounting impact.",
    "disburse_loan": "Cash disbursed and accounting posted through DEA.",
    "cancel_loan": "Loan cancelled before activation. No accounting impact.",
    "mark_npa": "Loan moved into non-performing state. No immediate GL impact.",
    "undo_disbursal": "Reverses the disbursal accounting entry and returns the loan to Approved.",
    "request_closure": "Starts closure after financial settlement checks.",
    "complete_closure": "Completes release and closure through the release workflow.",
}


def has_permission(user, permission_codename):
    workspace = getattr(getattr(user, "profile", None), "workspace", None)
    if workspace is None:
        return False
    membership = Membership.objects.filter(user=user, company=workspace).first()
    if not membership:
        return False
    return membership.role.permissions.filter(codename=permission_codename).exists()


def normalize_legacy_given_loan_status(status_value):
    if status_value in (None, ""):
        return status_value
    return GIVEN_LOAN_LEGACY_STATUS_MAP.get(str(status_value), str(status_value))


def normalize_legacy_taken_loan_status(status_value):
    if status_value in (None, ""):
        return status_value
    return TAKEN_LOAN_LEGACY_STATUS_MAP.get(str(status_value), str(status_value))


def map_loan_status_to_lifecycle_state(status_value):
    """Compatibility alias for older imports."""
    return normalize_legacy_given_loan_status(status_value)


def _save_transition(loan, user, ip_address, source="", target="", metadata=None):
    if loan is None:
        return

    save = getattr(loan, "save", None)
    if not getattr(loan, "pk", None):
        if callable(save):
            try:
                save(update_fields=["status"])
            except TypeError:
                save()
        return

    with transaction.atomic():
        if callable(save):
            try:
                save(update_fields=["status"])
            except TypeError:
                save()

        LoanChangeLog.objects.create(
            loan=loan,
            source=str(source),
            target=str(target or getattr(loan, "status", "")),
            author=user,
            ip_address=ip_address,
            diff="",
            metadata=metadata or {},
        )


class BaseLifecycleFlow:
    def __init__(self, loan: BaseLoan, user, tenant, ip_address=None):
        self.loan = loan
        self.user = user
        self.tenant = tenant
        self.ip_address = ip_address

    def _record_meta(self, **kwargs):
        self._additional_data = {
            k: str(v) if v is not None else None for k, v in kwargs.items()
        }

    def _consume_meta(self):
        data = getattr(self, "_additional_data", None)
        if hasattr(self, "_additional_data"):
            delattr(self, "_additional_data")
        return data

    def requires_accounting(self, transition_name):
        return TRANSITION_ACCOUNTING_IMPACT.get(transition_name, False)


class GivenLoanFlow(BaseLifecycleFlow):
    """Canonical runtime lifecycle for GivenLoan."""

    status = fsm.State(LoanLifecycleState, default=LoanLifecycleState.DRAFT)

    @status.setter()
    def _set_loan_status(self, state_value):
        self.loan.status = state_value

    @status.getter()
    def _get_loan_status(self):
        return normalize_legacy_given_loan_status(getattr(self.loan, "status", None))

    @status.on_success()
    def _on_success_transition(self, descriptor, source, target, **kwargs):
        _save_transition(
            self.loan,
            self.user,
            self.ip_address,
            source=source,
            target=target,
            metadata=self._consume_meta(),
        )

    def _current_state(self):
        return normalize_legacy_given_loan_status(getattr(self.loan, "status", None))

    def _collateral_exists(self) -> bool:
        manager = getattr(self.loan, "loanitems", None) or getattr(self.loan, "items", None)
        if manager is None:
            return True
        exists = getattr(manager, "exists", None)
        if callable(exists):
            return bool(exists())
        try:
            return bool(manager)
        except Exception:
            return True

    def _outstanding_amount(self):
        amount = getattr(self.loan, "outstanding_amount", None)
        if amount is not None:
            return amount

        try:
            from apps.tenant_apps.girvi.selectors import build_loan_settlement_balance

            return build_loan_settlement_balance(self.loan).total_outstanding
        except Exception:
            pass

        total_due = getattr(self.loan, "total_due", None)
        total_payments_getter = getattr(self.loan, "get_total_payments", None)
        if total_due is not None and callable(total_payments_getter):
            try:
                return total_due - total_payments_getter()
            except Exception:
                return None
        return None

    def _assert_can_submit_for_approval(self):
        if hasattr(self.loan, "borrower_id") and not getattr(self.loan, "borrower_id"):
            raise ValidationError("Borrower is required.")
        if hasattr(self.loan, "customer_id") and not getattr(self.loan, "customer_id"):
            raise ValidationError("Borrower is required.")
        if not self._collateral_exists():
            raise ValidationError("At least one collateral item is required.")
        if hasattr(self.loan, "get_loan_amount") and getattr(self.loan, "get_loan_amount", 1) <= 0:
            raise ValidationError("Loan amount must be greater than zero.")

    def _assert_can_approve(self):
        self._assert_can_submit_for_approval()

    def _assert_can_disburse(self):
        if self._current_state() not in {
            LoanLifecycleState.APPROVED,
            LoanLifecycleState.ACTIVE_CURRENT,
        }:
            raise ValidationError("Only approved loans can be disbursed.")

    def _assert_can_undo_disbursal(self):
        if self._current_state() not in {
            LoanLifecycleState.ACTIVE_CURRENT,
            LoanLifecycleState.APPROVED,
        }:
            raise ValidationError("Only active current loans can be returned to Approved.")

    def _assert_can_request_closure(self):
        outstanding = self._outstanding_amount()
        if (
            outstanding is not None
            and outstanding > 0
            and not getattr(self.loan, "closure_exception_approved", False)
        ):
            raise ValidationError("Loan must be fully settled before closure request.")

    def _assert_can_complete_closure(self, release_id=None):
        if not release_id and not getattr(self.loan, "release", None):
            raise ValidationError("Release document must exist before closure completes.")

    def _assert_can_request_renewal(self):
        if not self._collateral_exists():
            raise ValidationError("Renewal requires valid collateral.")
        if getattr(self.loan, "is_released", False) or getattr(self.loan, "release", None):
            raise ValidationError("Released loans cannot be renewed.")
        renewal_manager = getattr(self.loan, "renewals_as_source", None)
        exists = getattr(renewal_manager, "exists", None)
        if callable(exists) and exists():
            raise ValidationError("Loan already has a renewal record.")

    def _assert_can_complete_renewal(self, successor_loan_id=None):
        if successor_loan_id:
            return
        if (
            getattr(self.loan, "renewal", None) is None
            and getattr(self.loan, "loanrenewal_set", None) is None
        ):
            raise ValidationError("Renewal linkage must exist before completion.")

    def _assert_can_initiate_auction(self):
        if self._current_state() not in {
            LoanLifecycleState.ACTIVE_NPA,
            LoanLifecycleState.AUCTION_INITIATED,
        }:
            raise ValidationError("Only NPA loans can be sent to auction.")

    def _assert_can_mark_overdue(self):
        policy = evaluate_overdue_policy(self.loan)
        if policy.maturity_date is None:
            raise ValidationError("Loan date and tenure are required to mark overdue.")
        if not policy.is_overdue:
            raise ValidationError(
                "Loan is not overdue: maturity has not passed and settlement does not exceed collateral value."
            )

    def _assert_can_cure_to_current(self):
        outstanding = self._outstanding_amount()
        if outstanding is not None and outstanding > 0:
            raise ValidationError("Loan cannot be cured while dues are outstanding.")

    def _assert_can_mark_npa(self):
        policy = evaluate_overdue_policy(self.loan)
        if not policy.is_npa:
            raise ValidationError(
                "Loan cannot be marked NPA while settlement amount is covered by current collateral value."
            )

    def _assert_can_complete_auction(self, recovery_amount=None):
        try:
            amount = Decimal(str(recovery_amount))
        except (InvalidOperation, TypeError, ValueError):
            amount = Decimal("0")
        if amount <= 0:
            raise ValidationError("Auction recovery amount must be greater than zero.")

    def _assert_recovery_clears_balance(self):
        outstanding = self._outstanding_amount()
        if outstanding is not None and outstanding > 0:
            raise ValidationError("Auction recovery must clear the balance before closing.")

    def _assert_can_write_off(self, reason=""):
        if self._current_state() not in {
            LoanLifecycleState.ACTIVE_NPA,
            LoanLifecycleState.AUCTION_COMPLETE,
            LoanLifecycleState.WRITTEN_OFF,
        }:
            raise ValidationError("Only NPA or auction-complete loans can be written off.")
        if not str(reason or "").strip():
            raise ValidationError("Write-off reason is required.")
        outstanding = self._outstanding_amount()
        if outstanding is not None and outstanding <= 0:
            raise ValidationError("Fully settled loans must be closed, not written off.")

    def get_transitions(self):
        return [
            transition.label
            for method, transitions in GivenLoanFlow.status.get_transitions().items()
            for transition in transitions
        ]

    def get_available_transitions(self):
        return [
            transition
            for transition in GivenLoanFlow.status.get_available_transitions(
                self, self.status, self.user
            )
        ]

    def get_outgoing_transitions(self):
        return [
            transition
            for transition in GivenLoanFlow.status.get_outgoing_transitions(self.status)
        ]

    @status.transition(source=LoanLifecycleState.DRAFT, target=LoanLifecycleState.PENDING_APPROVAL, label=_("submit_for_approval"))
    def submit_for_approval(self, submitted_by=None):
        self._assert_can_submit_for_approval()
        self._record_meta(submitted_by=submitted_by, submitted_at=timezone.now().isoformat())

    @status.transition(source=LoanLifecycleState.PENDING_APPROVAL, target=LoanLifecycleState.DRAFT, label=_("return_to_draft"), permission=lambda flow, user: has_permission(user, "can_approve_loan"))
    def return_to_draft(self, returned_by=None, reason=""):
        self._record_meta(returned_by=returned_by, reason=reason)

    @status.transition(source=LoanLifecycleState.PENDING_APPROVAL, target=LoanLifecycleState.APPROVED, label=_("approve_loan"), permission=lambda flow, user: has_permission(user, "can_approve_loan"))
    def approve_loan(self, approved_by=None):
        self._assert_can_approve()
        self._record_meta(approved_by=approved_by, approved_at=timezone.now().isoformat())

    @status.transition(source=LoanLifecycleState.PENDING_APPROVAL, target=LoanLifecycleState.REJECTED, label=_("reject_loan"), permission=lambda flow, user: has_permission(user, "can_approve_loan"))
    def reject_loan(self, rejected_by=None, reason=""):
        if not reason:
            raise ValidationError("Rejection reason is required.")
        self._record_meta(rejected_by=rejected_by, reason=reason)

    @status.transition(source=[LoanLifecycleState.DRAFT, LoanLifecycleState.PENDING_APPROVAL], target=LoanLifecycleState.CANCELLED, label=_("cancel_loan"), permission=lambda flow, user: has_permission(user, "can_cancel_loan"))
    def cancel_loan(self, cancelled_by=None, reason=""):
        if not reason:
            raise ValidationError("Cancellation reason is required.")
        self._record_meta(cancelled_by=cancelled_by, reason=reason)

    @status.transition(source=LoanLifecycleState.APPROVED, target=LoanLifecycleState.ACTIVE_CURRENT, label=_("disburse_loan"), permission=lambda flow, user: has_permission(user, "can_disburse_loan"))
    def disburse_loan(self, disbursed_by=None):
        self._assert_can_disburse()
        self._record_meta(disbursed_by=disbursed_by, disbursed_at=timezone.now().isoformat())

    @status.transition(source=LoanLifecycleState.ACTIVE_CURRENT, target=LoanLifecycleState.APPROVED, label=_("undo_disbursal"), permission=lambda flow, user: has_permission(user, "can_disburse_loan"))
    def undo_disbursal(self, undone_by=None, reason=""):
        self._assert_can_undo_disbursal()
        self._record_meta(undone_by=undone_by, reason=reason)

    @status.transition(source=LoanLifecycleState.ACTIVE_CURRENT, target=LoanLifecycleState.ACTIVE_OVERDUE, label=_("mark_overdue"))
    def mark_overdue(self, marked_by=None):
        self._assert_can_mark_overdue()
        self._record_meta(marked_by=marked_by, marked_at=timezone.now().isoformat())

    @status.transition(source=[LoanLifecycleState.ACTIVE_OVERDUE, LoanLifecycleState.ACTIVE_NPA], target=LoanLifecycleState.ACTIVE_CURRENT, label=_("cure_to_current"))
    def cure_to_current(self, cured_by=None, note=""):
        self._assert_can_cure_to_current()
        self._record_meta(cured_by=cured_by, note=note)

    @status.transition(source=LoanLifecycleState.ACTIVE_OVERDUE, target=LoanLifecycleState.ACTIVE_NPA, label=_("mark_npa"), permission=lambda flow, user: has_permission(user, "can_mark_defaulted"))
    def mark_npa(self, marked_by=None, reason=""):
        self._assert_can_mark_npa()
        self._record_meta(marked_by=marked_by, reason=reason)

    @status.transition(source=[LoanLifecycleState.ACTIVE_CURRENT, LoanLifecycleState.ACTIVE_OVERDUE, LoanLifecycleState.ACTIVE_NPA], target=LoanLifecycleState.CLOSURE_PENDING, label=_("request_closure"), permission=lambda flow, user: has_permission(user, "can_release_loan"))
    def request_closure(self, requested_by=None):
        self._assert_can_request_closure()
        self._record_meta(requested_by=requested_by, requested_at=timezone.now().isoformat())

    @status.transition(source=LoanLifecycleState.CLOSURE_PENDING, target=LoanLifecycleState.CLOSED, label=_("complete_closure"), permission=lambda flow, user: has_permission(user, "can_release_loan"))
    def complete_closure(self, completed_by=None, release_id=None):
        self._assert_can_complete_closure(release_id=release_id)
        self._record_meta(completed_by=completed_by, release_id=release_id)

    @status.transition(source=LoanLifecycleState.CLOSURE_PENDING, target=LoanLifecycleState.ACTIVE_CURRENT, label=_("reopen_from_closure_pending"), permission=lambda flow, user: has_permission(user, "can_release_loan"))
    def reopen_from_closure_pending(self, reopened_by=None, reason=""):
        self._record_meta(reopened_by=reopened_by, reason=reason)

    @status.transition(source=[LoanLifecycleState.ACTIVE_CURRENT, LoanLifecycleState.ACTIVE_OVERDUE, LoanLifecycleState.ACTIVE_NPA], target=LoanLifecycleState.RENEWAL_PENDING, label=_("request_renewal"), permission=lambda flow, user: has_permission(user, "can_release_loan"))
    def request_renewal(self, requested_by=None):
        self._assert_can_request_renewal()
        self._record_meta(requested_by=requested_by, requested_at=timezone.now().isoformat())

    @status.transition(source=LoanLifecycleState.RENEWAL_PENDING, target=LoanLifecycleState.RENEWED, label=_("complete_renewal"), permission=lambda flow, user: has_permission(user, "can_release_loan"))
    def complete_renewal(self, completed_by=None, successor_loan_id=None):
        self._assert_can_complete_renewal(successor_loan_id=successor_loan_id)
        self._record_meta(completed_by=completed_by, successor_loan_id=successor_loan_id)

    @status.transition(source=LoanLifecycleState.RENEWAL_PENDING, target=LoanLifecycleState.ACTIVE_CURRENT, label=_("cancel_renewal_request"), permission=lambda flow, user: has_permission(user, "can_release_loan"))
    def cancel_renewal_request(self, cancelled_by=None, reason=""):
        self._record_meta(cancelled_by=cancelled_by, reason=reason)

    @status.transition(source=LoanLifecycleState.ACTIVE_NPA, target=LoanLifecycleState.AUCTION_INITIATED, label=_("initiate_auction"), permission=lambda flow, user: has_permission(user, "can_mark_auctioned"))
    def initiate_auction(self, initiated_by=None):
        self._assert_can_initiate_auction()
        self._record_meta(initiated_by=initiated_by, initiated_at=timezone.now().isoformat())

    @status.transition(source=LoanLifecycleState.AUCTION_INITIATED, target=LoanLifecycleState.AUCTION_IN_PROGRESS, label=_("start_auction"), permission=lambda flow, user: has_permission(user, "can_mark_auctioned"))
    def start_auction(self, started_by=None):
        self._record_meta(started_by=started_by, started_at=timezone.now().isoformat())

    @status.transition(source=LoanLifecycleState.AUCTION_INITIATED, target=LoanLifecycleState.ACTIVE_NPA, label=_("cancel_auction"), permission=lambda flow, user: has_permission(user, "can_mark_auctioned"))
    def cancel_auction(self, cancelled_by=None, reason=""):
        self._record_meta(cancelled_by=cancelled_by, reason=reason)

    @status.transition(source=LoanLifecycleState.AUCTION_IN_PROGRESS, target=LoanLifecycleState.AUCTION_COMPLETE, label=_("complete_auction"), permission=lambda flow, user: has_permission(user, "can_mark_auctioned"))
    def complete_auction(self, completed_by=None, recovery_amount=None):
        self._assert_can_complete_auction(recovery_amount=recovery_amount)
        self._record_meta(completed_by=completed_by, recovery_amount=recovery_amount)

    @status.transition(source=LoanLifecycleState.AUCTION_COMPLETE, target=LoanLifecycleState.CLOSED, label=_("close_after_auction"), permission=lambda flow, user: has_permission(user, "can_mark_auctioned"))
    def close_after_auction(self, completed_by=None):
        self._assert_recovery_clears_balance()
        self._record_meta(completed_by=completed_by)

    @status.transition(source=[LoanLifecycleState.ACTIVE_NPA, LoanLifecycleState.AUCTION_COMPLETE], target=LoanLifecycleState.WRITTEN_OFF, label=_("write_off_loan"), permission=lambda flow, user: has_permission(user, "can_mark_defaulted"))
    def write_off_loan(self, written_off_by=None, reason=""):
        self._assert_can_write_off(reason=reason)
        self._record_meta(written_off_by=written_off_by, reason=reason)


class TakenLoanFlow(BaseLifecycleFlow):
    """Minimal runtime lifecycle for TakenLoan."""

    status = fsm.State(TakenLoanLifecycleState, default=TakenLoanLifecycleState.DRAFT)

    @status.setter()
    def _set_loan_status(self, state_value):
        self.loan.status = state_value

    @status.getter()
    def _get_loan_status(self):
        return normalize_legacy_taken_loan_status(getattr(self.loan, "status", None))

    @status.on_success()
    def _on_success_transition(self, descriptor, source, target, **kwargs):
        _save_transition(
            self.loan,
            self.user,
            self.ip_address,
            source=source,
            target=target,
            metadata=self._consume_meta(),
        )

    def get_transitions(self):
        return [
            transition.label
            for method, transitions in TakenLoanFlow.status.get_transitions().items()
            for transition in transitions
        ]

    def get_available_transitions(self):
        return [
            transition
            for transition in TakenLoanFlow.status.get_available_transitions(
                self, self.status, self.user
            )
        ]

    def get_outgoing_transitions(self):
        return [
            transition
            for transition in TakenLoanFlow.status.get_outgoing_transitions(self.status)
        ]

    @status.transition(source=TakenLoanLifecycleState.DRAFT, target=TakenLoanLifecycleState.ACTIVE, label=_("activate"), permission=lambda flow, user: has_permission(user, "can_disburse_loan"))
    def activate(self, activated_by=None, disbursed_by=None):
        self._record_meta(
            activated_by=activated_by or disbursed_by,
            activated_at=timezone.now().isoformat(),
        )

    @status.transition(source=TakenLoanLifecycleState.DRAFT, target=TakenLoanLifecycleState.CANCELLED, label=_("cancel_loan"), permission=lambda flow, user: has_permission(user, "can_cancel_loan"))
    def cancel_loan(self, cancelled_by=None, reason=""):
        if not reason:
            raise ValidationError("Cancellation reason is required.")
        self._record_meta(cancelled_by=cancelled_by, reason=reason)

    @status.transition(source=TakenLoanLifecycleState.ACTIVE, target=TakenLoanLifecycleState.SETTLEMENT_PENDING, label=_("request_settlement"))
    def request_settlement(self, requested_by=None):
        self._record_meta(requested_by=requested_by, requested_at=timezone.now().isoformat())

    @status.transition(source=TakenLoanLifecycleState.SETTLEMENT_PENDING, target=TakenLoanLifecycleState.CLOSED, label=_("complete_settlement"))
    def complete_settlement(self, completed_by=None):
        self._record_meta(completed_by=completed_by, completed_at=timezone.now().isoformat())


GivenLoanFlowV2 = GivenLoanFlow

GIVEN_RUNTIME_STATUS_VALUES = frozenset(value for value, _label in LoanLifecycleState.choices)
TAKEN_RUNTIME_STATUS_VALUES = frozenset(value for value, _label in TakenLoanLifecycleState.choices)


def _is_taken_loan_instance(loan):
    return (
        isinstance(loan, TakenLoan)
        or getattr(loan, "loan_type", None) == "Taken"
        or loan.__class__.__name__ == "TakenLoan"
    )


def resolve_runtime_transition_name(loan, transition_name):
    normalized_transition = str(transition_name or "").strip()
    if not normalized_transition:
        return normalized_transition

    if _is_taken_loan_instance(loan):
        return TAKEN_TRANSITION_ALIAS_MAP.get(normalized_transition, normalized_transition)

    return GIVEN_TRANSITION_ALIAS_MAP.get(normalized_transition, normalized_transition)


def build_runtime_loan_flow(loan, user, tenant, transition_name=None, ip_address=None):
    if _is_taken_loan_instance(loan):
        return TakenLoanFlow(loan, user, tenant, ip_address=ip_address)
    return GivenLoanFlow(loan, user, tenant, ip_address=ip_address)
