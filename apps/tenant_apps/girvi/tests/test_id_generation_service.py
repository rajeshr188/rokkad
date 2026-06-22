from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.id_generation import (
    LoanIDGenerator,
    validate_loan_id_unique_across_loan_tables,
)


class LoanIDGeneratorTests(SimpleTestCase):
    def test_generate_uses_highest_sequence_across_given_and_taken_loans(self):
        series = SimpleNamespace(id=1, prefix="I", format_loan_id=lambda n: f"I{n:05d}")
        given_manager = MagicMock()
        taken_manager = MagicMock()
        given_manager.objects.filter.return_value.values_list.return_value = [
            "I00005",
            "I00002",
        ]
        taken_manager.objects.filter.return_value.values_list.return_value = [
            "I00007",
        ]

        with patch(
            "apps.tenant_apps.girvi.service_modules.id_generation.transaction.atomic",
            return_value=nullcontext(),
        ), patch(
            "apps.tenant_apps.girvi.service_modules.id_generation.Series.objects.select_for_update"
        ) as mock_select_for_update, patch(
            "apps.tenant_apps.girvi.service_modules.id_generation.apps.get_model",
            side_effect=[given_manager, taken_manager],
        ):
            mock_select_for_update.return_value.get.return_value = series
            next_id = LoanIDGenerator.generate(series)

        self.assertEqual(next_id, "I00008")

    def test_validate_loan_id_checks_given_and_taken_tables(self):
        given_manager = MagicMock()
        taken_manager = MagicMock()
        given_qs = MagicMock()
        taken_qs = MagicMock()
        given_manager.objects.filter.return_value = given_qs
        taken_manager.objects.filter.return_value = taken_qs
        given_qs.exists.return_value = False
        taken_qs.exists.return_value = True

        with patch(
            "apps.tenant_apps.girvi.service_modules.id_generation.apps.get_model",
            side_effect=[given_manager, taken_manager],
        ):
            with self.assertRaises(ValidationError):
                validate_loan_id_unique_across_loan_tables("I00008")

        given_manager.objects.filter.assert_called_once_with(loan_id="I00008")
        taken_manager.objects.filter.assert_called_once_with(loan_id="I00008")
