"""Workflow helpers for repayment view orchestration."""

from django.utils import timezone

from apps.tenant_apps.girvi.selectors import build_repayment_preview


class RepaymentWorkflowService:
    """Keep repayment view logic focused on HTTP/form concerns."""

    @staticmethod
    def build_preview(loan, *, loan_kind="given"):
        return build_repayment_preview(loan, loan_kind=loan_kind)

    @staticmethod
    def initial_form_data(preview):
        return {
            "payment_date": timezone.now(),
            "interest_amount": preview.suggested_interest_amount,
        }

    @staticmethod
    def emit_result_messages(request, result):
        from django.contrib import messages

        for warning in result.warnings:
            messages.warning(request, warning)
        for error in result.errors:
            messages.error(request, error)
        if result.success_message:
            messages.success(request, result.success_message)
