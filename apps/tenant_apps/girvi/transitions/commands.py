import logging
from dataclasses import asdict, is_dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.tenant_apps.girvi.service_modules.transition_posting import (
    post_auction_recovery_for_transition,
    post_sale_recovery_for_transition,
)
from .types import TransitionResult

logger = logging.getLogger(__name__)


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
    transition_name = "disburse_loan"

    def execute(self, transition_method, payload=None) -> TransitionResult:
        from apps.tenant_apps.girvi.models.loan_refactored import (
            LoanLifecycleState,
            TakenLoanLifecycleState,
        )
        from apps.tenant_apps.girvi.service_modules.payment import record_loan_disbursal

        try:
            with transaction.atomic():
                transition_method(**self._payload_to_kwargs(payload))
                if self.loan.status not in {
                    LoanLifecycleState.ACTIVE_CURRENT,
                    TakenLoanLifecycleState.ACTIVE,
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


class AuctionNoticeMixin:
    notice_success_suffix = " Auction notice created."

    def _create_auction_notice(self) -> bool:
        borrower = getattr(self.loan, "borrower", None)
        if borrower is None:
            return False

        try:
            from apps.tenant_apps.notify.services import create_loan_auction_notice

            create_loan_auction_notice(loan=self.loan)
            return True
        except Exception:
            logger.exception(
                "Auction notice trigger failed for loan %s",
                getattr(self.loan, "loan_id", getattr(self.loan, "pk", "unknown")),
            )
            return False

    def _attach_notice_message(self, result: TransitionResult) -> TransitionResult:
        if result.success and self._create_auction_notice():
            result.message = f"{result.message}{self.notice_success_suffix}"
        return result


class AuctionNoticeTransitionCommand(AuctionNoticeMixin, GenericForwardTransitionCommand):
    transition_name = "initiate_auction"

    def execute(self, transition_method, payload=None) -> TransitionResult:
        result = super().execute(transition_method, payload=payload)
        return self._attach_notice_message(result)


class MarkAuctionedTransitionCommand(AuctionNoticeMixin, BaseLoanTransitionCommand):
    transition_name = "complete_auction"

    def execute(self, transition_method, payload=None) -> TransitionResult:
        from apps.tenant_apps.girvi.models.loan_refactored import LoanLifecycleState

        payload_kwargs = self._payload_to_kwargs(payload)
        amount = payload_kwargs.get("amount") or payload_kwargs.get("recovery_amount")
        if amount is None:
            return TransitionResult(
                success=False,
                level="error",
                message="Auction recovery amount is required.",
            )

        try:
            with transaction.atomic():
                transition_method(**payload_kwargs)
                if self.loan.status != LoanLifecycleState.AUCTION_COMPLETE:
                    result = TransitionResult(
                        success=True,
                        level="success",
                        message=str(_("Loan status updated successfully.")),
                    )
                    return self._attach_notice_message(result)

                payment, created = post_auction_recovery_for_transition(
                    self.loan, amount, self.user
                )

            if created:
                message = str(
                    _(
                        f"Loan status updated successfully. "
                        f"Auction recovery voucher {payment.payment_id} posted."
                    )
                )
            else:
                message = str(
                    _(
                        f"Loan status updated successfully. "
                        f"Auction recovery already recorded as {payment.payment_id}."
                    )
                )

            result = TransitionResult(
                success=True,
                level="success",
                message=message,
                payment=payment,
                created=created,
            )
        except Exception as exc:
            result = TransitionResult(
                success=False,
                level="error",
                message=str(
                    _(
                        f"Auction posting failed. Loan status was not changed: {exc}"
                    )
                ),
            )

        return self._attach_notice_message(result)


class MarkSoldTransitionCommand(BaseLoanTransitionCommand):
    transition_name = "mark_sold"

    def execute(self, transition_method, payload=None) -> TransitionResult:
        from apps.tenant_apps.girvi.models.loan_refactored import LoanLifecycleState

        payload_kwargs = self._payload_to_kwargs(payload)
        amount = payload_kwargs.get("amount") or payload_kwargs.get("recovery_amount")
        if amount is None:
            return TransitionResult(
                success=False,
                level="error",
                message="Sale recovery amount is required.",
            )

        try:
            with transaction.atomic():
                transition_method(**payload_kwargs)
                if self.loan.status != LoanLifecycleState.AUCTION_COMPLETE:
                    return TransitionResult(
                        success=True,
                        level="success",
                        message=str(_("Loan status updated successfully.")),
                    )

                payment, created = post_sale_recovery_for_transition(
                    self.loan, amount, self.user
                )

            if created:
                msg = str(
                    _(
                        f"Loan status updated successfully. "
                        f"Sale recovery voucher {payment.payment_id} posted."
                    )
                )
            else:
                msg = str(
                    _(
                        f"Loan status updated successfully. "
                        f"Sale recovery already recorded as {payment.payment_id}."
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
                        f"Sale posting failed. Loan status was not changed: {exc}"
                    )
                ),
            )


class UndoDisburseTransitionCommand(BaseLoanTransitionCommand):
    transition_name = "undo_disburse"

    def execute(self, transition_method, payload=None) -> TransitionResult:
        from django.core.exceptions import ValidationError
        from apps.tenant_apps.girvi.service_modules.payment import reverse_loan_disbursal

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
        from apps.tenant_apps.girvi.service_modules.payment import reverse_loan_release

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

        from apps.tenant_apps.girvi.models.loan_refactored import LoanLifecycleState
        from apps.tenant_apps.girvi.models.renewal import LoanRenewal

        try:
            with transaction.atomic():
                renewal = LoanRenewal.objects.filter(
                    source_loan=self.loan
                ).select_related("renewed_loan").latest("created_at")

                new_loan = renewal.renewed_loan
                if new_loan and new_loan.status in {
                    LoanLifecycleState.DRAFT,
                    LoanLifecycleState.PENDING_APPROVAL,
                    LoanLifecycleState.APPROVED,
                    LoanLifecycleState.ACTIVE_CURRENT,
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
    "mark_sold": MarkSoldTransitionCommand,
    "undo_release": UndoReleaseTransitionCommand,
    "undo_repledge": UndoRepledgeTransitionCommand,
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
    "initiate_auction": AuctionNoticeTransitionCommand,
    "start_auction": GenericForwardTransitionCommand,
    "cancel_auction": GenericForwardTransitionCommand,
    "complete_auction": MarkAuctionedTransitionCommand,
    "close_after_auction": GenericForwardTransitionCommand,
    "write_off_loan": GenericForwardTransitionCommand,
    "activate": DisburseTransitionCommand,
    "request_settlement": GenericForwardTransitionCommand,
    "complete_settlement": GenericForwardTransitionCommand,
}


def get_transition_command_class(transition_name: str):
    return TRANSITION_COMMAND_REGISTRY.get(
        transition_name,
        GenericForwardTransitionCommand,
    )
