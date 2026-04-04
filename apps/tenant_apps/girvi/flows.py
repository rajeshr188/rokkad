from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from viewflow import fsm

from apps.orgs.models import Membership

from .models import BaseLoan, LoanChangeLog, LoanStatus

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
    "approve": "Move a newly created loan into Approved. This is a review/approval step only.",
    "disburse": "Move an approved loan into Disbursed and record the fund-outflow accounting entry.",
    "deliver": "Business release action: return collateral to the customer, create the Release document, and move the loan to Released.",
    "cancel": "Cancel a loan before disbursal. No accounting posting is expected.",
    "mark_defaulted": "Flag a disbursed loan as Defaulted so recovery actions can follow.",
    "mark_auctioned": "Record that defaulted collateral was auctioned. Follow-up accounting may be required.",
    "mark_sold": "Record that collateral was sold from the Disbursed state. Follow-up accounting may be required.",
    "undo_disburse": "Reverse the disbursal and return the loan to Approved.",
    "undo_release": "Reverse the release document and return the loan to Disbursed.",
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
