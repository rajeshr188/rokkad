from dataclasses import asdict, is_dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .types import TransitionResult


class BaseLoanTransitionCommand:
    transition_name = ""

    def __init__(self, loan, user, tenant):
        self.loan = loan
        self.user = user
        self.tenant = tenant

    def execute(self, transition_method, payload=None) -> TransitionResult:
        raise NotImplementedError()

    @staticmethod
    def _payload_to_kwargs(payload=None) -> dict:
        if payload is None:
            return {}
        if is_dataclass(payload):
            return asdict(payload)
        raise TypeError("payload must be a dataclass instance")

    @staticmethod
    def _format_exception_message(exc: Exception) -> str:
        if isinstance(exc, ValidationError):
            if getattr(exc, "message_dict", None):
                return " ".join(
                    str(message)
                    for messages in exc.message_dict.values()
                    for message in messages
                )
            if getattr(exc, "messages", None):
                return " ".join(str(message) for message in exc.messages)
        return str(exc)


class GenericForwardTransitionCommand(BaseLoanTransitionCommand):
    def execute(self, transition_method, payload=None) -> TransitionResult:
        try:
            transition_method(**self._payload_to_kwargs(payload))
            return TransitionResult(
                success=True,
                level="success",
                message=str(_("Loan status updated successfully.")),
            )
        except (ValueError, ValidationError) as exc:
            return TransitionResult(
                success=False,
                level="error",
                message=self._format_exception_message(exc),
            )


class DisburseTransitionCommand(BaseLoanTransitionCommand):
    transition_name = "disburse"

    def execute(self, transition_method, payload=None) -> TransitionResult:
        from apps.tenant_apps.girvi.models import LoanStatus
        from apps.tenant_apps.girvi.models.loan_refactored import LoanLifecycleState
        from apps.tenant_apps.girvi.payment_service import record_loan_disbursal

        try:
            with transaction.atomic():
                transition_method(**self._payload_to_kwargs(payload))
                if self.loan.status not in {
                    LoanStatus.DISBURSED,
                    LoanLifecycleState.ACTIVE_CURRENT,
                }:
                    return TransitionResult(
                        success=True,
                        level="success",
                        message=str(_("Loan status updated successfully.")),
                    )

                payment, created = record_loan_disbursal(self.loan, self.user)

            if created:
                msg = str(
                    _(
                        f"Loan status updated successfully. "
                        f"Disbursal voucher {payment.payment_id} posted."
                    )
                )
            else:
                msg = str(
                    _(
                        f"Loan status updated successfully. "
                        f"Disbursal already recorded as {payment.payment_id}."
                    )
                )

            return TransitionResult(
                success=True,
                level="success",
                message=msg,
                payment=payment,
                created=created,
            )
        except Exception as exc:
            return TransitionResult(
                success=False,
                level="error",
                message=str(
                    _(
                        f"Disbursal failed. Loan status was not changed: {exc}"
                    )
                ),
            )


class WarningTransitionCommand(BaseLoanTransitionCommand):
    warning_message = ""

    def execute(self, transition_method, payload=None) -> TransitionResult:
        transition_method(**self._payload_to_kwargs(payload))
        return TransitionResult(
            success=True,
            level="warning",
            message=str(_(self.warning_message)),
        )


class MarkAuctionedTransitionCommand(WarningTransitionCommand):
    transition_name = "mark_auctioned"
    warning_message = (
        "Loan status updated, but accounting posting for this "
        "transition is not implemented yet."
    )


class MarkSoldTransitionCommand(WarningTransitionCommand):
    transition_name = "mark_sold"
    warning_message = (
        "Loan status updated, but accounting posting for this "
        "transition is not implemented yet."
    )


class UndoDisburseTransitionCommand(BaseLoanTransitionCommand):
    transition_name = "undo_disburse"

    def execute(self, transition_method, payload=None) -> TransitionResult:
        from django.core.exceptions import ValidationError
        from apps.tenant_apps.girvi.payment_service import reverse_loan_disbursal

        try:
            with transaction.atomic():
                transition_method(**self._payload_to_kwargs(payload))
                reverse_loan_disbursal(self.loan, self.user)
            return TransitionResult(
                success=True,
                level="success",
                message=str(
                    _(
                        "Disbursal reversed successfully. Loan returned to Approved."
                    )
                ),
            )
        except (ValueError, ValidationError) as exc:
            return TransitionResult(success=False, level="error", message=str(exc))


class UndoReleaseTransitionCommand(BaseLoanTransitionCommand):
    transition_name = "undo_release"

    def execute(self, transition_method, payload=None) -> TransitionResult:
        from django.core.exceptions import ValidationError
        from apps.tenant_apps.girvi.payment_service import reverse_loan_release

        try:
            with transaction.atomic():
                release = self.loan.release
                transition_method(**self._payload_to_kwargs(payload))
                reverse_loan_release(self.loan, self.user)
                release.delete()
            return TransitionResult(
                success=True,
                level="success",
                message=str(
                    _(
                        "Release reversed successfully. Loan returned to Disbursed."
                    )
                ),
            )
        except (ValueError, ValidationError) as exc:
            return TransitionResult(success=False, level="error", message=str(exc))


class UndoRepledgeTransitionCommand(BaseLoanTransitionCommand):
    transition_name = "undo_repledge"

    def execute(self, transition_method, payload=None) -> TransitionResult:
        from django.core.exceptions import ValidationError

        from apps.tenant_apps.girvi.models.loan_refactored import LoanStatus
        from apps.tenant_apps.girvi.models.renewal import LoanRenewal

        try:
            with transaction.atomic():
                renewal = LoanRenewal.objects.filter(
                    source_loan=self.loan
                ).select_related("renewed_loan").latest("created_at")

                new_loan = renewal.renewed_loan
                if new_loan and new_loan.status in {
                    LoanStatus.CREATED,
                    LoanStatus.APPROVED,
                    LoanStatus.DISBURSED,
                }:
                    new_loan.loanitems.all().delete()
                    new_loan.delete()
                elif new_loan:
                    raise ValidationError(
                        f"Cannot undo renewal: renewed loan {new_loan.loan_id} "
                        f"is already in status '{new_loan.status}' and cannot be deleted."
                    )

                marker_prefix = f"RENEWAL-PAYMENT-{self.loan.pk}"
                self.loan.payments.filter(
                    reference_number__startswith=marker_prefix
                ).delete()

                renewal.delete()
                transition_method(**self._payload_to_kwargs(payload))

            return TransitionResult(
                success=True,
                level="success",
                message=str(
                    _(
                        "Renewal reversed successfully. Loan returned to Disbursed."
                    )
                ),
            )
        except LoanRenewal.DoesNotExist:
            return TransitionResult(
                success=False,
                level="error",
                message="No renewal record found for this loan.",
            )
        except (ValueError, ValidationError) as exc:
            return TransitionResult(success=False, level="error", message=str(exc))


TRANSITION_COMMAND_REGISTRY = {
    "approve": GenericForwardTransitionCommand,
    "disburse": DisburseTransitionCommand,
    "cancel": GenericForwardTransitionCommand,
    "mark_defaulted": GenericForwardTransitionCommand,
    "mark_auctioned": MarkAuctionedTransitionCommand,
    "mark_sold": MarkSoldTransitionCommand,
    "repledge": GenericForwardTransitionCommand,
    "undo_disburse": UndoDisburseTransitionCommand,
    "undo_release": UndoReleaseTransitionCommand,
    "undo_repledge": UndoRepledgeTransitionCommand,
    # V2 lifecycle commands
    "submit_for_approval": GenericForwardTransitionCommand,
    "return_to_draft": GenericForwardTransitionCommand,
    "approve_loan": GenericForwardTransitionCommand,
    "reject_loan": GenericForwardTransitionCommand,
    "cancel_loan": GenericForwardTransitionCommand,
    "disburse_loan": DisburseTransitionCommand,
    "undo_disbursal": UndoDisburseTransitionCommand,
    "mark_overdue": GenericForwardTransitionCommand,
    "cure_to_current": GenericForwardTransitionCommand,
    "mark_npa": GenericForwardTransitionCommand,
    "request_closure": GenericForwardTransitionCommand,
    "complete_closure": GenericForwardTransitionCommand,
    "reopen_from_closure_pending": GenericForwardTransitionCommand,
    "request_renewal": GenericForwardTransitionCommand,
    "complete_renewal": GenericForwardTransitionCommand,
    "cancel_renewal_request": GenericForwardTransitionCommand,
    "initiate_auction": GenericForwardTransitionCommand,
    "start_auction": GenericForwardTransitionCommand,
    "cancel_auction": GenericForwardTransitionCommand,
    "complete_auction": MarkAuctionedTransitionCommand,
    "close_after_auction": GenericForwardTransitionCommand,
    "write_off_loan": GenericForwardTransitionCommand,
}


def get_transition_command_class(transition_name: str):
    return TRANSITION_COMMAND_REGISTRY.get(
        transition_name,
        GenericForwardTransitionCommand,
    )
