from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django import forms
from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.release_form_validation import (
    ReleaseFormValidationService,
)


class _FakeForm:
    def __init__(self, cleaned_data):
        self.cleaned_data = cleaned_data
        self.errors = {}
        self.add_error = MagicMock()


class _FakeFormSet:
    def __init__(self, forms_):
        self.forms = forms_


class ReleaseFormValidationServiceTests(SimpleTestCase):
    def test_validate_formset_requires_at_least_one_active_loan(self):
        formset = _FakeFormSet([_FakeForm({}), _FakeForm({"DELETE": True})])

        with self.assertRaises(forms.ValidationError):
            ReleaseFormValidationService.validate_formset(formset)

    def test_validate_formset_flags_duplicate_loans(self):
        loan = SimpleNamespace(id=1)
        form_a = _FakeForm({"loan": loan})
        form_b = _FakeForm({"loan": loan})
        formset = _FakeFormSet([form_a, form_b])

        with patch(
            "apps.tenant_apps.girvi.service_modules.release_form_validation.GivenLoan.objects.filter"
        ) as filter_mock:
            filter_mock.return_value.values_list.return_value = []
            ReleaseFormValidationService.validate_formset(formset)

        form_b.add_error.assert_called_once_with(
            "loan", "Duplicate loan selected in bulk release."
        )

    def test_validate_formset_raises_when_loans_already_released(self):
        loan = SimpleNamespace(id=2)
        form = _FakeForm({"loan": loan})
        formset = _FakeFormSet([form])

        with patch(
            "apps.tenant_apps.girvi.service_modules.release_form_validation.GivenLoan.objects.filter"
        ) as filter_mock:
            filter_mock.return_value.values_list.return_value = [2]
            with self.assertRaises(forms.ValidationError):
                ReleaseFormValidationService.validate_formset(formset)

        form.add_error.assert_called_once_with(
            "loan", "This loan was already released. Refresh and try again."
        )
