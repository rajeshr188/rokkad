"""Validation helpers to keep release forms focused on input shape checks."""

from django import forms

from apps.tenant_apps.girvi.models import GivenLoan


class ReleaseFormValidationService:
    """Encapsulate release formset row/cross-row validation rules."""

    @staticmethod
    def _iter_active_forms(formset):
        for form in formset.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if not form.cleaned_data:
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            yield form

    @classmethod
    def _collect_loan_ids(cls, formset):
        seen_ids = set()
        loan_ids = []

        for form in cls._iter_active_forms(formset):
            loan = form.cleaned_data.get("loan")
            if not loan:
                continue

            if loan.id in seen_ids:
                form.add_error("loan", "Duplicate loan selected in bulk release.")
            else:
                seen_ids.add(loan.id)

            loan_ids.append(loan.id)

        return loan_ids

    @classmethod
    def _validate_not_already_released(cls, formset, loan_ids):
        released_ids = set(
            GivenLoan.objects.filter(id__in=loan_ids, release__isnull=False).values_list(
                "id", flat=True
            )
        )
        if not released_ids:
            return

        for form in cls._iter_active_forms(formset):
            loan = form.cleaned_data.get("loan")
            if loan and loan.id in released_ids:
                form.add_error(
                    "loan", "This loan was already released. Refresh and try again."
                )

        raise forms.ValidationError(
            "Some loans are already released. Please review highlighted rows."
        )

    @classmethod
    def validate_formset(cls, formset):
        loan_ids = cls._collect_loan_ids(formset)
        if not loan_ids:
            raise forms.ValidationError("Please select at least one loan.")

        cls._validate_not_already_released(formset, loan_ids)
