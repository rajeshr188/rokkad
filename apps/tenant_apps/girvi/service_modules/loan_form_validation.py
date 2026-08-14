"""Validation helpers for loan-related forms."""

from django import forms
from django.utils import timezone

from apps.tenant_apps.girvi.policies import assert_loan_header_editable


class LoanFormValidationService:
    """Keep loan forms focused on binding while centralizing rule checks."""

    @staticmethod
    def validate_not_future(value):
        if value and value > timezone.now():
            raise forms.ValidationError("Date cannot be in the future.")
        return value

    @staticmethod
    def validate_series_active(form, series):
        if series and not series.is_active:
            form.add_error("series", f"Series {series} is Inactive")

    @classmethod
    def validate_loan_form(cls, form, cleaned_data):
        if form.instance and form.instance.pk:
            assert_loan_header_editable(form.instance)
        cls.validate_series_active(form, cleaned_data.get("series"))
        return cleaned_data

    @classmethod
    def validate_loan_create_form(cls, form, cleaned_data):
        cls.validate_series_active(form, cleaned_data.get("series"))
        return cleaned_data

    @staticmethod
    def validate_loan_renewal(form, cleaned_data):
        mode = cleaned_data.get("mode")
        extra = cleaned_data.get("requested_extra_amount") or 0
        if mode == "TOPUP_RENEW" and extra <= 0:
            form.add_error(
                "requested_extra_amount",
                "Top-Up mode requires a positive extra amount.",
            )
        return cleaned_data

    @staticmethod
    def validate_storage_box_range(*, start_loan, end_loan):
        if start_loan and end_loan and start_loan.loan_id > end_loan.loan_id:
            raise forms.ValidationError("Start Loan ID must be less than End Loan ID.")
