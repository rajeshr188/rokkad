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
    def test_validate_release_form_loan_flags_released_on_create(self):
        form = SimpleNamespace(
            instance=SimpleNamespace(pk=None),
            add_error=MagicMock(),
        )
        loan = SimpleNamespace(is_released=True)

        returned = ReleaseFormValidationService.validate_release_form_loan(form, loan)

        self.assertIs(returned, loan)
        form.add_error.assert_called_once_with("loan", "Loan already has a release.")

    def test_validate_release_form_loan_skips_check_for_existing_release_instance(self):
        form = SimpleNamespace(
            instance=SimpleNamespace(pk=10),
            add_error=MagicMock(),
        )
        loan = SimpleNamespace(is_released=True)

        returned = ReleaseFormValidationService.validate_release_form_loan(form, loan)

        self.assertIs(returned, loan)
        form.add_error.assert_not_called()

    def test_validate_release_amount_flags_when_amount_exceeds_due(self):
        form = SimpleNamespace(add_error=MagicMock())
        loan = SimpleNamespace(total_due=None, due=MagicMock(return_value=150))

        ReleaseFormValidationService.validate_release_amount(form, 200, loan)

        form.add_error.assert_called_once_with(
            "release_amount",
            "Release amount 200 cannot be > due amount 150.",
        )

    def test_validate_release_amount_uses_callable_total_due(self):
        form = SimpleNamespace(add_error=MagicMock())
        loan = SimpleNamespace(total_due=MagicMock(return_value=250))

        result = ReleaseFormValidationService.validate_release_amount(form, 200, loan)

        self.assertEqual(result, 200)
        form.add_error.assert_not_called()

    def test_validate_release_amount_allows_missing_loan(self):
        form = SimpleNamespace(add_error=MagicMock())

        result = ReleaseFormValidationService.validate_release_amount(form, 100, None)

        self.assertEqual(result, 100)
        form.add_error.assert_not_called()

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
