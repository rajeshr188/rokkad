from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from viewflow import fsm, this

from apps.orgs.models import Membership
from apps.orgs.views import has_permission

from .models import BaseLoan, LoanChangeLog, LoanStatus


def has_permission(user, permission_codename):
    membership = Membership.objects.filter(
        user=user, company=user.profile.workspace
    ).first()
    if not membership:
        return False
    return membership.role.permissions.filter(codename=permission_codename).exists()


class LoanFlow(object):
    """Loan process definition"""

    # TODO: Add permissions
    # TODO: determine the extra fields needed for each state

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

            # Create change log with additional data
            log_data = {
                "loan": self.loan,
                "source": source,
                "target": target,
                "author": self.user,
                "ip_address": self.ip_address,
            }

            # Add any additional data stored during transition
            if hasattr(self, "_additional_data"):
                log_data["metadata"] = self._additional_data
                delattr(self, "_additional_data")

            LoanChangeLog.objects.create(**log_data)

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

    @status.transition(
        source=LoanStatus.CREATED,
        target=LoanStatus.APPROVED,
        label=_("approve"),
        permission=lambda flow, user: has_permission(
            user, "can_approve_loan"
        ),  # either this or a function that returns a boolean
    )
    def approve(self, approved_by):
        """Approve a loan"""
        pass
        # self.approved_at = timezone.now()
        # self.approved_by = self.user

    @status.transition(
        source=LoanStatus.APPROVED,
        target=LoanStatus.DISBURSED,
        label=_("disburse"),
        permission=lambda flow, user: has_permission(user, "can_disburse_loan"),
    )
    def disburse(self, disbursed_by):
        """Disburse an approved loan"""
        # self.disbursed_at = timezone.now()
        # self.disbursed_by = self.user
        pass
        # self.create_transactions()

    @status.transition(
        source={LoanStatus.DISBURSED, LoanStatus.REPLEDGED},
        target=LoanStatus.RELEASED,
        label=_("deliver"),
        permission=lambda flow, user: has_permission(user, "can_release_loan"),
    )
    def deliver(self, created_by, released_by, release_date=None):
        print("delivering")
        """Release a disbursed loan"""
        # if not release_date:
        #     release_date = timezone.now()
        # return self.loan.create_release(
        #     release_date=release_date,
        #     released_by=released_by,
        #     created_by=self.user
        # )
        # self.released_at = timezone.now()
        # self.released_by = released_by
        pass

    @status.transition(
        label=_("cancel"),
        source=[LoanStatus.CREATED, LoanStatus.APPROVED],
        target=LoanStatus.CANCELLED,
        permission=lambda flow, user: has_permission(user, "can_cancel_loan"),
    )
    def cancel(self, cancelled_by, reason):
        """Cancel a loan"""
        # self.cancelled_at = timezone.now()
        # self.cancelled_by = cancelled_by
        # self.cancellation_reason = reason
        self._additional_data = {"reason": reason}

    @status.transition(
        source=LoanStatus.DISBURSED,
        target=LoanStatus.DEFAULTED,
        label=_("mark_defaulted"),
        permission=lambda flow, user: has_permission(user, "can_mark_defaulted"),
    )
    def mark_defaulted(self, marked_by, reason):
        """Mark a loan as defaulted"""
        # self.defaulted_at = timezone.now()
        # self.defaulted_by = marked_by
        # self.default_reason = reason
        self._additional_data = {"reason": reason}

    @status.transition(
        source=LoanStatus.DEFAULTED,
        target=LoanStatus.AUCTIONED,
        label=_("mark_auctioned"),
        permission=lambda flow, user: has_permission(user, "can_mark_auctioned"),
    )
    def mark_auctioned(self, auctioned_by, amount):
        """Mark a defaulted loan as auctioned"""
        self._additional_data = {
            "auctioned_at": timezone.now(),
            "auctioned_by": auctioned_by,
            "auction_amount": amount,
        }

    @status.transition(
        source=LoanStatus.DISBURSED,
        target=LoanStatus.SOLD,
        label=_("mark sold"),
        # permission=lambda self: has_permission(self.user, self.tenant,'can_mark_sold')
    )
    def mark_sold(self, sold_by, amount):
        """Mark a loan as sold"""
        self._additional_data = {
            "sold_at": timezone.now(),
            "sold_by": sold_by,
            "sold_amount": amount,
        }
