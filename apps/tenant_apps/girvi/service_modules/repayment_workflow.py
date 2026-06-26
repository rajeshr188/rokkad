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
    def payment_options(preview):
        options = []
        if preview.suggested_total_amount > 0:
            options.append(
                {
                    "label": "Exact settlement",
                    "description": "Pay the full current outstanding amount.",
                    "total_amount": preview.suggested_total_amount,
                    "interest_amount": preview.suggested_interest_amount,
                    "button_class": "btn-outline-success",
                }
            )
        if preview.settlement.interest_due > 0:
            options.append(
                {
                    "label": "Interest only",
                    "description": "Clear outstanding interest without reducing principal.",
                    "total_amount": preview.settlement.interest_due,
                    "interest_amount": preview.settlement.interest_due,
                    "button_class": "btn-outline-primary",
                }
            )
        if preview.settlement.principal_due > 0:
            options.append(
                {
                    "label": "Principal only",
                    "description": "Apply the amount fully toward principal.",
                    "total_amount": preview.settlement.principal_due,
                    "interest_amount": 0,
                    "button_class": "btn-outline-secondary",
                }
            )
        return options

    @staticmethod
    def emit_result_messages(request, result):
        from django.contrib import messages

        for warning in result.warnings:
            messages.warning(request, warning)
        for error in result.errors:
            messages.error(request, error)
        if result.success_message:
            messages.success(request, result.success_message)
