from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from viewflow import fsm

from apps.orgs.models import Membership

from .models.loan import LoanChangeLog
from .models.loan_refactored import BaseLoan, LoanLifecycleState, LoanStatus

# ─── Transition metadata ────────────────────────────────────────────────────

# True = this transition triggers voucher creation in the view
TRANSITION_ACCOUNTING_IMPACT = {
    "approve": False,
    "disburse": True,
    "deliver": False,
    "cancel": False,
    "mark_defaulted": False,
    "mark_auctioned": True,
    "mark_sold": True,
    # Reversal transitions
    "undo_disburse": True,   # reverses the GIVENLOAN_DISBURSAL voucher
    "undo_release": True,    # reverses the GIVENLOAN_RELEASE voucher + deletes Release
}

TRANSITION_DESCRIPTIONS = {
    "approve": "Loan reviewed and approved for disbursement. No accounting impact.",
    "disburse": "Cash disbursed to borrower. Creates a LOAN_DISBURSE accounting entry.",
    "deliver": "Collateral released to the loan holder. No immediate accounting impact.",
    "cancel": "Loan cancelled before disbursement. No accounting impact.",
    "mark_defaulted": "Borrower has defaulted. Event recorded; no immediate GL impact.",
    "mark_auctioned": "Collateral auctioned to recover the loan amount. Creates an accounting entry.",
    "mark_sold": "Collateral sold. Creates an accounting entry.",
    "undo_disburse": "Reverses the disbursal — returns loan to Approved. Reverses GIVENLOAN_DISBURSAL voucher.",
    "undo_release": "Reverses the release — returns loan to Disbursed. Reverses GIVENLOAN_RELEASE voucher and deletes the Release record.",
}

# ─── Permission helper ───────────────────────────────────────────────────────


def has_permission(user, permission_codename):
    membership = Membership.objects.filter(
        user=user, company=user.profile.workspace
    ).first()
    if not membership:
        return False
    return membership.role.permissions.filter(codename=permission_codename).exists()


# ─── Flow ────────────────────────────────────────────────────────────────────


class LoanFlow(object):
    """
    Loan lifecycle FSM — liaison layer between BusinessDoc and Voucher.

    Responsibilities:
    - Advance loan.status via FSM transitions
    - Record transition metadata in LoanChangeLog
    - Signal accounting impact to the calling view

    The flow does NOT create vouchers itself. For accounting transitions,
    the service/command layer performs any required posting or reversal
    after the legal state change succeeds.
    """

    status = fsm.State(LoanStatus, default=LoanStatus.CREATED)

    def __init__(self, loan: BaseLoan, user, tenant, ip_address=None):
        self.loan = loan
        self.user = user
        self.tenant = tenant
        self.ip_address = ip_address

    @status.setter()
    def _set_loan_status(self, state_value):
        self.loan.status = state_value

    @status.getter()
    def _get_loan_status(self):
        if self.loan.status:
            return self.loan.status

    @status.on_success()
    def _on_success_transition(self, descriptor, source, target, **kwargs):
        if self.loan is None:
            return

        if not getattr(self.loan, "pk", None):
            self.loan.save()
            if hasattr(self, "_additional_data"):
                delattr(self, "_additional_data")
            return

        with transaction.atomic():
            self.loan.save()

            log_data = {
                "loan": self.loan,
                "source": str(source),
                "target": str(target),
                "author": self.user,
                "ip_address": self.ip_address,
                "diff": "",
            }

            if hasattr(self, "_additional_data"):
                log_data["metadata"] = self._additional_data
                delattr(self, "_additional_data")

            LoanChangeLog.objects.create(**log_data)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def get_transitions(self):
        return [
            transition.label
            for method, transitions in LoanFlow.status.get_transitions().items()
            for transition in transitions
        ]

    def get_available_transitions(self):
        return [
            transition
            for transition in LoanFlow.status.get_available_transitions(
                self, self.status, self.user
            )
        ]

    def get_outgoing_transitions(self):
        return [
            transition
            for transition in LoanFlow.status.get_outgoing_transitions(self.status)
        ]

    def requires_accounting(self, transition_name):
        """Return True if this transition should trigger voucher creation."""
        return TRANSITION_ACCOUNTING_IMPACT.get(transition_name, False)

    # ── Transitions ──────────────────────────────────────────────────────────

    @status.transition(
        source=LoanStatus.CREATED,
        target=LoanStatus.APPROVED,
        label=_("approve"),
        permission=lambda flow, user: has_permission(user, "can_approve_loan"),
    )
    def approve(self, approved_by):
        """Approve a loan — no accounting impact."""
        self._additional_data = {
            "approved_by": str(approved_by),
            "approved_at": timezone.now().isoformat(),
        }

    @status.transition(
        source=LoanStatus.APPROVED,
        target=LoanStatus.DISBURSED,
        label=_("disburse"),
        permission=lambda flow, user: has_permission(user, "can_disburse_loan"),
    )
    def disburse(self, disbursed_by):
        """Disburse an approved loan — accounting is handled by the service layer."""
        self._additional_data = {
            "disbursed_by": str(disbursed_by),
            "disbursed_at": timezone.now().isoformat(),
        }

    @status.transition(
        source=LoanStatus.DISBURSED,
        target=LoanStatus.RELEASED,
        label=_("deliver"),
        permission=lambda flow, user: has_permission(user, "can_release_loan"),
    )
    def deliver(self, created_by, released_by, release_date=None):
        """Release a disbursed loan — collateral returned to borrower."""
        self._additional_data = {
            "created_by": str(created_by) if created_by else None,
            "released_by": str(released_by) if released_by else None,
            "release_date": (release_date or timezone.now()).isoformat(),
        }

    @status.transition(
        label=_("cancel"),
        source=[LoanStatus.CREATED, LoanStatus.APPROVED],
        target=LoanStatus.CANCELLED,
        permission=lambda flow, user: has_permission(user, "can_cancel_loan"),
    )
    def cancel(self, cancelled_by, reason):
        """Cancel a loan before disbursement — no accounting impact."""
        self._additional_data = {
            "cancelled_by": str(cancelled_by),
            "cancelled_at": timezone.now().isoformat(),
            "reason": reason,
        }

    @status.transition(
        source=LoanStatus.DISBURSED,
        target=LoanStatus.APPROVED,
        label=_("undo_disburse"),
        permission=lambda flow, user: has_permission(user, "can_disburse_loan"),
    )
    def undo_disburse(self, undone_by, reason):
        """Revert a disbursed loan back to Approved — reverses GIVENLOAN_DISBURSAL voucher."""
        self._additional_data = {
            "undone_by": str(undone_by),
            "undone_at": timezone.now().isoformat(),
            "reason": reason,
        }

    @status.transition(
        source=LoanStatus.RELEASED,
        target=LoanStatus.DISBURSED,
        label=_("undo_release"),
        permission=lambda flow, user: has_permission(user, "can_release_loan"),
    )
    def undo_release(self, undone_by, reason):
        """Revert a released loan back to Disbursed — reverses GIVENLOAN_RELEASE voucher and deletes Release."""
        self._additional_data = {
            "undone_by": str(undone_by),
            "undone_at": timezone.now().isoformat(),
            "reason": reason,
        }

    @status.transition(
        source=LoanStatus.DISBURSED,
        target=LoanStatus.DEFAULTED,
        label=_("mark_defaulted"),
        permission=lambda flow, user: has_permission(user, "can_mark_defaulted"),
    )
    def mark_defaulted(self, marked_by, reason):
        """Mark a disbursed loan as defaulted — event recorded, no immediate GL impact."""
        self._additional_data = {
            "marked_by": str(marked_by),
            "defaulted_at": timezone.now().isoformat(),
            "reason": reason,
        }

    @status.transition(
        source=LoanStatus.DEFAULTED,
        target=LoanStatus.AUCTIONED,
        label=_("mark_auctioned"),
        permission=lambda flow, user: has_permission(user, "can_mark_auctioned"),
    )
    def mark_auctioned(self, auctioned_by, amount):
        """Auction collateral — any accounting side-effects are handled above the flow."""
        self._additional_data = {
            "auctioned_at": timezone.now().isoformat(),
            "auctioned_by": str(auctioned_by),
            "auction_amount": str(amount),
        }

    @status.transition(
        source=LoanStatus.DISBURSED,
        target=LoanStatus.REPLEDGED,
        label=_("repledge"),
        permission=lambda flow, user: has_permission(user, "can_release_loan"),
    )
    def repledge(self, created_by):
        """Mark a disbursed loan as repledged (renewed) — collateral stays in custody."""
        self._additional_data = {
            "created_by": str(created_by),
            "repledged_at": timezone.now().isoformat(),
        }

    @status.transition(
        source=LoanStatus.REPLEDGED,
        target=LoanStatus.DISBURSED,
        label=_("undo_repledge"),
        permission=lambda flow, user: has_permission(user, "can_release_loan"),
    )
    def undo_repledge(self, undone_by, reason=""):
        """Reverse a repledge — cancels the renewal and returns source loan to Disbursed."""
        self._additional_data = {
            "undone_by": str(undone_by),
            "undone_at": timezone.now().isoformat(),
            "reason": reason,
        }

    @status.transition(
        source=LoanStatus.DISBURSED,
        target=LoanStatus.SOLD,
        label=_("mark_sold"),
        permission=lambda flow, user: has_permission(user, "can_mark_sold"),
    )
    def mark_sold(self, sold_by, amount):
        """Record a collateral sale; any accounting side-effects are handled above the flow."""
        self._additional_data = {
            "sold_at": timezone.now().isoformat(),
            "sold_by": str(sold_by),
            "sold_amount": str(amount),
        }


LEGACY_TO_V2_STATUS_MAP = {
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


def map_loan_status_to_lifecycle_state(status_value):
    """Normalize a stored loan status into the V2 lifecycle state model."""
    if status_value in (None, ""):
        return status_value
    return LEGACY_TO_V2_STATUS_MAP.get(status_value, status_value)


class GivenLoanFlowV2(object):
    """Deterministic next-generation lifecycle FSM for GivenLoan.

    This flow co-exists with the legacy `LoanFlow` so the codebase can migrate in
    small steps. It captures the richer lifecycle contract agreed for approval,
    servicing, closure, renewal, auction, and write-off workflows.
    """

    status = fsm.State(LoanLifecycleState, default=LoanLifecycleState.DRAFT)

    def __init__(self, loan: BaseLoan, user, tenant, ip_address=None):
        self.loan = loan
        self.user = user
        self.tenant = tenant
        self.ip_address = ip_address

    @status.setter()
    def _set_loan_status(self, state_value):
        self.loan.status = state_value

    @status.getter()
    def _get_loan_status(self):
        return map_loan_status_to_lifecycle_state(getattr(self.loan, "status", None))

    @status.on_success()
    def _on_success_transition(self, descriptor, source, target, **kwargs):
        if self.loan is None:
            return

        save = getattr(self.loan, "save", None)
        if not getattr(self.loan, "pk", None):
            if callable(save):
                try:
                    save(update_fields=["status"])
                except TypeError:
                    save()
            if hasattr(self, "_additional_data"):
                delattr(self, "_additional_data")
            return

        with transaction.atomic():
            if callable(save):
                try:
                    save(update_fields=["status"])
                except TypeError:
                    save()

            log_data = {
                "loan": self.loan,
                "source": str(source),
                "target": str(target),
                "author": self.user,
                "ip_address": self.ip_address,
                "diff": "",
            }

            if hasattr(self, "_additional_data"):
                log_data["metadata"] = self._additional_data
                delattr(self, "_additional_data")

            LoanChangeLog.objects.create(**log_data)

    def _record_meta(self, **kwargs):
        self._additional_data = {k: str(v) if v is not None else None for k, v in kwargs.items()}

    def _current_state(self):
        return map_loan_status_to_lifecycle_state(getattr(self.loan, "status", None))

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

        total_due = getattr(self.loan, "total_due", None)
        total_payments_getter = getattr(self.loan, "get_total_payments", None)
        if total_due is not None and callable(total_payments_getter):
            try:
                return total_due - total_payments_getter()
            except Exception:
                return None
        return None

    def _assert_can_submit_for_approval(self):
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
        if outstanding is not None and outstanding > 0 and not getattr(self.loan, "closure_exception_approved", False):
            raise ValidationError("Loan must be fully settled before closure request.")

    def _assert_can_complete_closure(self, release_id=None):
        if not release_id and not getattr(self.loan, "release", None):
            raise ValidationError("Release document must exist before closure completes.")

    def _assert_can_request_renewal(self):
        if not self._collateral_exists():
            raise ValidationError("Renewal requires valid collateral.")

    def _assert_can_complete_renewal(self, successor_loan_id=None):
        if successor_loan_id:
            return
        if getattr(self.loan, "renewal", None) is None and getattr(self.loan, "loanrenewal_set", None) is None:
            raise ValidationError("Renewal linkage must exist before completion.")

    def _assert_can_initiate_auction(self):
        if self._current_state() not in {
            LoanLifecycleState.ACTIVE_NPA,
            LoanLifecycleState.AUCTION_INITIATED,
        }:
            raise ValidationError("Only NPA loans can be sent to auction.")

    def _assert_recovery_clears_balance(self):
        outstanding = self._outstanding_amount()
        if outstanding is not None and outstanding > 0:
            raise ValidationError("Auction recovery must clear the balance before closing.")

    def _assert_can_write_off(self):
        if self._current_state() not in {
            LoanLifecycleState.ACTIVE_NPA,
            LoanLifecycleState.AUCTION_COMPLETE,
            LoanLifecycleState.WRITTEN_OFF,
        }:
            raise ValidationError("Only NPA or auction-complete loans can be written off.")

    def get_transitions(self):
        return [
            transition.label
            for method, transitions in GivenLoanFlowV2.status.get_transitions().items()
            for transition in transitions
        ]

    def get_available_transitions(self):
        return [
            transition
            for transition in GivenLoanFlowV2.status.get_available_transitions(
                self, self.status, self.user
            )
        ]

    def get_outgoing_transitions(self):
        return [
            transition
            for transition in GivenLoanFlowV2.status.get_outgoing_transitions(self.status)
        ]

    @status.transition(
        source=LoanLifecycleState.DRAFT,
        target=LoanLifecycleState.PENDING_APPROVAL,
        label=_("submit_for_approval"),
    )
    def submit_for_approval(self, submitted_by=None):
        self._assert_can_submit_for_approval()
        self._record_meta(
            submitted_by=submitted_by,
            submitted_at=timezone.now().isoformat(),
        )

    @status.transition(
        source=LoanLifecycleState.PENDING_APPROVAL,
        target=LoanLifecycleState.DRAFT,
        label=_("return_to_draft"),
        permission=lambda flow, user: has_permission(user, "can_approve_loan"),
    )
    def return_to_draft(self, returned_by=None, reason=""):
        self._record_meta(returned_by=returned_by, reason=reason)

    @status.transition(
        source=LoanLifecycleState.PENDING_APPROVAL,
        target=LoanLifecycleState.APPROVED,
        label=_("approve_loan"),
        permission=lambda flow, user: has_permission(user, "can_approve_loan"),
    )
    def approve_loan(self, approved_by=None):
        self._assert_can_approve()
        self._record_meta(approved_by=approved_by, approved_at=timezone.now().isoformat())

    @status.transition(
        source=LoanLifecycleState.PENDING_APPROVAL,
        target=LoanLifecycleState.REJECTED,
        label=_("reject_loan"),
        permission=lambda flow, user: has_permission(user, "can_approve_loan"),
    )
    def reject_loan(self, rejected_by=None, reason=""):
        if not reason:
            raise ValidationError("Rejection reason is required.")
        self._record_meta(rejected_by=rejected_by, reason=reason)

    @status.transition(
        source=[LoanLifecycleState.DRAFT, LoanLifecycleState.PENDING_APPROVAL],
        target=LoanLifecycleState.CANCELLED,
        label=_("cancel_loan"),
        permission=lambda flow, user: has_permission(user, "can_cancel_loan"),
    )
    def cancel_loan(self, cancelled_by=None, reason=""):
        if not reason:
            raise ValidationError("Cancellation reason is required.")
        self._record_meta(cancelled_by=cancelled_by, reason=reason)

    @status.transition(
        source=LoanLifecycleState.APPROVED,
        target=LoanLifecycleState.ACTIVE_CURRENT,
        label=_("disburse_loan"),
        permission=lambda flow, user: has_permission(user, "can_disburse_loan"),
    )
    def disburse_loan(self, disbursed_by=None):
        self._assert_can_disburse()
        self._record_meta(disbursed_by=disbursed_by, disbursed_at=timezone.now().isoformat())

    @status.transition(
        source=LoanLifecycleState.ACTIVE_CURRENT,
        target=LoanLifecycleState.APPROVED,
        label=_("undo_disbursal"),
        permission=lambda flow, user: has_permission(user, "can_disburse_loan"),
    )
    def undo_disbursal(self, undone_by=None, reason=""):
        self._assert_can_undo_disbursal()
        self._record_meta(undone_by=undone_by, reason=reason)

    @status.transition(
        source=LoanLifecycleState.ACTIVE_CURRENT,
        target=LoanLifecycleState.ACTIVE_OVERDUE,
        label=_("mark_overdue"),
    )
    def mark_overdue(self, marked_by=None):
        self._record_meta(marked_by=marked_by, marked_at=timezone.now().isoformat())

    @status.transition(
        source=[LoanLifecycleState.ACTIVE_OVERDUE, LoanLifecycleState.ACTIVE_NPA],
        target=LoanLifecycleState.ACTIVE_CURRENT,
        label=_("cure_to_current"),
    )
    def cure_to_current(self, cured_by=None, note=""):
        self._record_meta(cured_by=cured_by, note=note)

    @status.transition(
        source=LoanLifecycleState.ACTIVE_OVERDUE,
        target=LoanLifecycleState.ACTIVE_NPA,
        label=_("mark_npa"),
        permission=lambda flow, user: has_permission(user, "can_mark_defaulted"),
    )
    def mark_npa(self, marked_by=None, reason=""):
        self._record_meta(marked_by=marked_by, reason=reason)

    @status.transition(
        source=[
            LoanLifecycleState.ACTIVE_CURRENT,
            LoanLifecycleState.ACTIVE_OVERDUE,
            LoanLifecycleState.ACTIVE_NPA,
        ],
        target=LoanLifecycleState.CLOSURE_PENDING,
        label=_("request_closure"),
        permission=lambda flow, user: has_permission(user, "can_release_loan"),
    )
    def request_closure(self, requested_by=None):
        self._assert_can_request_closure()
        self._record_meta(requested_by=requested_by, requested_at=timezone.now().isoformat())

    @status.transition(
        source=LoanLifecycleState.CLOSURE_PENDING,
        target=LoanLifecycleState.CLOSED,
        label=_("complete_closure"),
        permission=lambda flow, user: has_permission(user, "can_release_loan"),
    )
    def complete_closure(self, completed_by=None, release_id=None):
        self._assert_can_complete_closure(release_id=release_id)
        self._record_meta(completed_by=completed_by, release_id=release_id)

    @status.transition(
        source=LoanLifecycleState.CLOSURE_PENDING,
        target=LoanLifecycleState.ACTIVE_CURRENT,
        label=_("reopen_from_closure_pending"),
        permission=lambda flow, user: has_permission(user, "can_release_loan"),
    )
    def reopen_from_closure_pending(self, reopened_by=None, reason=""):
        self._record_meta(reopened_by=reopened_by, reason=reason)

    @status.transition(
        source=[
            LoanLifecycleState.ACTIVE_CURRENT,
            LoanLifecycleState.ACTIVE_OVERDUE,
            LoanLifecycleState.ACTIVE_NPA,
        ],
        target=LoanLifecycleState.RENEWAL_PENDING,
        label=_("request_renewal"),
        permission=lambda flow, user: has_permission(user, "can_release_loan"),
    )
    def request_renewal(self, requested_by=None):
        self._assert_can_request_renewal()
        self._record_meta(requested_by=requested_by, requested_at=timezone.now().isoformat())

    @status.transition(
        source=LoanLifecycleState.RENEWAL_PENDING,
        target=LoanLifecycleState.RENEWED,
        label=_("complete_renewal"),
        permission=lambda flow, user: has_permission(user, "can_release_loan"),
    )
    def complete_renewal(self, completed_by=None, successor_loan_id=None):
        self._assert_can_complete_renewal(successor_loan_id=successor_loan_id)
        self._record_meta(completed_by=completed_by, successor_loan_id=successor_loan_id)

    @status.transition(
        source=LoanLifecycleState.RENEWAL_PENDING,
        target=LoanLifecycleState.ACTIVE_CURRENT,
        label=_("cancel_renewal_request"),
        permission=lambda flow, user: has_permission(user, "can_release_loan"),
    )
    def cancel_renewal_request(self, cancelled_by=None, reason=""):
        self._record_meta(cancelled_by=cancelled_by, reason=reason)

    @status.transition(
        source=LoanLifecycleState.ACTIVE_NPA,
        target=LoanLifecycleState.AUCTION_INITIATED,
        label=_("initiate_auction"),
        permission=lambda flow, user: has_permission(user, "can_mark_auctioned"),
    )
    def initiate_auction(self, initiated_by=None):
        self._assert_can_initiate_auction()
        self._record_meta(initiated_by=initiated_by, initiated_at=timezone.now().isoformat())

    @status.transition(
        source=LoanLifecycleState.AUCTION_INITIATED,
        target=LoanLifecycleState.AUCTION_IN_PROGRESS,
        label=_("start_auction"),
        permission=lambda flow, user: has_permission(user, "can_mark_auctioned"),
    )
    def start_auction(self, started_by=None):
        self._record_meta(started_by=started_by, started_at=timezone.now().isoformat())

    @status.transition(
        source=LoanLifecycleState.AUCTION_INITIATED,
        target=LoanLifecycleState.ACTIVE_NPA,
        label=_("cancel_auction"),
        permission=lambda flow, user: has_permission(user, "can_mark_auctioned"),
    )
    def cancel_auction(self, cancelled_by=None, reason=""):
        self._record_meta(cancelled_by=cancelled_by, reason=reason)

    @status.transition(
        source=LoanLifecycleState.AUCTION_IN_PROGRESS,
        target=LoanLifecycleState.AUCTION_COMPLETE,
        label=_("complete_auction"),
        permission=lambda flow, user: has_permission(user, "can_mark_auctioned"),
    )
    def complete_auction(self, completed_by=None, recovery_amount=None):
        self._record_meta(completed_by=completed_by, recovery_amount=recovery_amount)

    @status.transition(
        source=LoanLifecycleState.AUCTION_COMPLETE,
        target=LoanLifecycleState.CLOSED,
        label=_("close_after_auction"),
        permission=lambda flow, user: has_permission(user, "can_mark_auctioned"),
    )
    def close_after_auction(self, completed_by=None):
        self._assert_recovery_clears_balance()
        self._record_meta(completed_by=completed_by)

    @status.transition(
        source=[LoanLifecycleState.ACTIVE_NPA, LoanLifecycleState.AUCTION_COMPLETE],
        target=LoanLifecycleState.WRITTEN_OFF,
        label=_("write_off_loan"),
        permission=lambda flow, user: has_permission(user, "can_mark_defaulted"),
    )
    def write_off_loan(self, written_off_by=None, reason=""):
        self._assert_can_write_off()
        self._record_meta(written_off_by=written_off_by, reason=reason)


V2_RUNTIME_STATUS_VALUES = frozenset(
    {
        LoanLifecycleState.DRAFT,
        LoanLifecycleState.PENDING_APPROVAL,
        LoanLifecycleState.APPROVED,
        LoanLifecycleState.REJECTED,
        LoanLifecycleState.CANCELLED,
        LoanLifecycleState.ACTIVE_CURRENT,
        LoanLifecycleState.ACTIVE_OVERDUE,
        LoanLifecycleState.ACTIVE_NPA,
        LoanLifecycleState.CLOSURE_PENDING,
        LoanLifecycleState.RENEWAL_PENDING,
        LoanLifecycleState.CLOSED,
        LoanLifecycleState.RENEWED,
        LoanLifecycleState.AUCTION_INITIATED,
        LoanLifecycleState.AUCTION_IN_PROGRESS,
        LoanLifecycleState.AUCTION_COMPLETE,
        LoanLifecycleState.WRITTEN_OFF,
    }
)

V2_TRANSITION_KEYS = frozenset(
    {
        "submit_for_approval",
        "return_to_draft",
        "approve_loan",
        "reject_loan",
        "cancel_loan",
        "disburse_loan",
        "undo_disbursal",
        "mark_overdue",
        "cure_to_current",
        "mark_npa",
        "request_closure",
        "complete_closure",
        "reopen_from_closure_pending",
        "request_renewal",
        "complete_renewal",
        "cancel_renewal_request",
        "initiate_auction",
        "start_auction",
        "cancel_auction",
        "complete_auction",
        "close_after_auction",
        "write_off_loan",
    }
)

V2_COMPATIBILITY_TRANSITION_MAP = {
    LoanLifecycleState.DRAFT: {
        "cancel": "cancel_loan",
    },
    LoanLifecycleState.PENDING_APPROVAL: {
        "approve": "approve_loan",
        "reject": "reject_loan",
        "cancel": "cancel_loan",
    },
    LoanLifecycleState.APPROVED: {
        "disburse": "disburse_loan",
    },
    LoanLifecycleState.ACTIVE_CURRENT: {
        "undo_disburse": "undo_disbursal",
    },
}


def resolve_runtime_transition_name(loan, transition_name):
    """Map legacy transition keys to their V2 runtime equivalents for the loan state."""
    normalized_transition = str(transition_name or "").strip()
    if not normalized_transition:
        return normalized_transition

    current_status = map_loan_status_to_lifecycle_state(getattr(loan, "status", None))
    return V2_COMPATIBILITY_TRANSITION_MAP.get(current_status, {}).get(
        normalized_transition,
        normalized_transition,
    )


def build_runtime_loan_flow(loan, user, tenant, transition_name=None, ip_address=None):
    """Return the appropriate FSM implementation for the current loan/transition.

    Legacy transitions continue to run through `LoanFlow`, while the new
    deterministic lifecycle keys and V2-only states are routed to
    `GivenLoanFlowV2`.
    """
    current_status = map_loan_status_to_lifecycle_state(getattr(loan, "status", None))
    normalized_transition = resolve_runtime_transition_name(loan, transition_name)

    if normalized_transition in V2_TRANSITION_KEYS or current_status in V2_RUNTIME_STATUS_VALUES:
        return GivenLoanFlowV2(loan, user, tenant, ip_address=ip_address)

    return LoanFlow(loan, user, tenant, ip_address=ip_address)
