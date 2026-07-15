import logging
from dataclasses import asdict, is_dataclass

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.tenant_apps.girvi.service_modules.transition_posting import (
    post_auction_recovery_for_transition,
    post_sale_recovery_for_transition,
)
from apps.tenant_apps.girvi.service_modules.transition_side_effects import (
    execute_disbursal_transition,
    execute_recovery_transition,
    parse_recovery_amount,
)
from apps.tenant_apps.girvi.integrations.notification_adapter import (
    create_girvi_reminder_batch,
    get_default_notice_channel,
)
from apps.tenant_apps.girvi.models import LoanChangeLog
from .types import TransitionResult

logger = logging.getLogger(__name__)

AUCTION_NOTICE_EVENT_KEY = "loan.auction_notice_due"


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
            return execute_disbursal_transition(
                loan=self.loan,
                user=self.user,
                transition_method=transition_method,
                payload_kwargs=self._payload_to_kwargs(payload),
                active_statuses={
                    LoanLifecycleState.ACTIVE_CURRENT,
                    TakenLoanLifecycleState.ACTIVE,
                },
                post_disbursal=record_loan_disbursal,
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

    def _record_notice_failure(self, exc):
        if not getattr(self.loan, "pk", None) or not getattr(self.user, "pk", None):
            return

        try:
            LoanChangeLog.objects.create(
                content_type=ContentType.objects.get_for_model(self.loan),
                object_id=self.loan.pk,
                source=str(getattr(self.loan, "status", "")),
                target=str(getattr(self.loan, "status", "")),
                author=self.user,
                diff="Auction notice creation failed.",
                notes=str(exc),
                metadata={
                    "event": "auction_notice_failed",
                    "event_key": AUCTION_NOTICE_EVENT_KEY,
                    "error": str(exc),
                },
            )
        except Exception:
            logger.exception(
                "Failed to record auction notice failure for loan %s",
                getattr(self.loan, "loan_id", getattr(self.loan, "pk", "unknown")),
            )

    def _create_auction_notice(self) -> bool:
        borrower = getattr(self.loan, "borrower", None)
        if borrower is None:
            return False

        try:
            create_girvi_reminder_batch(
                loans=[self.loan],
                created_by=self.user,
                event_key=AUCTION_NOTICE_EVENT_KEY,
                channel=get_default_notice_channel(),
                notes="Generated from Girvi auction lifecycle transition.",
            )
            return True
        except Exception as exc:
            logger.exception(
                "Auction notice trigger failed for loan %s",
                getattr(self.loan, "loan_id", getattr(self.loan, "pk", "unknown")),
            )
            self._record_notice_failure(exc)
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
        parsed_amount = parse_recovery_amount(
            payload_kwargs,
            missing_message="Auction recovery amount is required.",
            non_positive_message="Auction recovery amount must be greater than zero.",
        )
        if parsed_amount.error_message:
            return TransitionResult(
                success=False,
                level="error",
                message=parsed_amount.error_message,
            )

        try:
            result = execute_recovery_transition(
                loan=self.loan,
                user=self.user,
                transition_method=transition_method,
                payload_kwargs=payload_kwargs,
                success_status=LoanLifecycleState.AUCTION_COMPLETE,
                post_recovery=post_auction_recovery_for_transition,
                posted_message=(
                    "Loan status updated successfully. "
                    "Auction recovery voucher {payment_id} posted."
                ),
                existing_message=(
                    "Loan status updated successfully. "
                    "Auction recovery already recorded as {payment_id}."
                ),
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
        parsed_amount = parse_recovery_amount(
            payload_kwargs,
            missing_message="Sale recovery amount is required.",
            non_positive_message="Sale recovery amount must be greater than zero.",
        )
        if parsed_amount.error_message:
            return TransitionResult(
                success=False,
                level="error",
                message=parsed_amount.error_message,
            )

        try:
            return execute_recovery_transition(
                loan=self.loan,
                user=self.user,
                transition_method=transition_method,
                payload_kwargs=payload_kwargs,
                success_status=LoanLifecycleState.AUCTION_COMPLETE,
                post_recovery=post_sale_recovery_for_transition,
                posted_message=(
                    "Loan status updated successfully. "
                    "Sale recovery voucher {payment_id} posted."
                ),
                existing_message=(
                    "Loan status updated successfully. "
                    "Sale recovery already recorded as {payment_id}."
                ),
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


class WriteOffTransitionCommand(BaseLoanTransitionCommand):
    transition_name = "write_off_loan"

    def execute(self, transition_method, payload=None) -> TransitionResult:
        from decimal import Decimal

        from apps.tenant_apps.girvi.service_modules.settlement_adjustments import (
            SettlementAdjustmentCommand,
            SettlementAdjustmentService,
            SettlementAdjustmentType,
        )

        payload_kwargs = self._payload_to_kwargs(payload)
        outstanding = getattr(self.loan, "outstanding_amount", None)
        if outstanding is not None and Decimal(str(outstanding)) <= Decimal("0.00"):
            return TransitionResult(
                success=False,
                level="error",
                message="Fully settled loans must be closed, not written off.",
            )

        result = SettlementAdjustmentService.execute(
            SettlementAdjustmentCommand(
                loan=self.loan,
                adjustment_type=SettlementAdjustmentType.WRITE_OFF,
                created_by=self.user,
                reason=payload_kwargs.get("reason", ""),
                principal_amount=getattr(self.loan, "outstanding_principal", Decimal("0.00")),
                interest_amount=getattr(self.loan, "outstanding_interest", Decimal("0.00")),
            )
        )
        return TransitionResult(
            success=result.success,
            level="success" if result.success else "error",
            message=result.message,
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
    "write_off_loan": WriteOffTransitionCommand,
    "activate": DisburseTransitionCommand,
    "request_settlement": GenericForwardTransitionCommand,
    "complete_settlement": GenericForwardTransitionCommand,
}


def get_transition_command_class(transition_name: str):
    return TRANSITION_COMMAND_REGISTRY.get(
        transition_name,
        GenericForwardTransitionCommand,
    )
