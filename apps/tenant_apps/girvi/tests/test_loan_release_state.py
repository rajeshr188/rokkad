from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.models.loan_refactored import GivenLoan
from apps.tenant_apps.girvi.models.release import Release


class GivenLoanReleaseStateTests(SimpleTestCase):
    def test_is_released_ignores_stale_cached_release_after_rollback(self):
        loan = GivenLoan(pk=42)
        loan._state.fields_cache["release"] = SimpleNamespace(pk=91)

        queryset = SimpleNamespace(exists=lambda: False)
        with patch.object(Release._default_manager, "filter", return_value=queryset) as filter_mock:
            self.assertFalse(loan.is_released)

        filter_mock.assert_called_once_with(pk=91, loan_id=42)
        self.assertNotIn("release", loan._state.fields_cache)

    def test_is_released_accepts_cached_release_when_row_still_exists(self):
        loan = GivenLoan(pk=42)
        loan._state.fields_cache["release"] = SimpleNamespace(pk=91)

        queryset = SimpleNamespace(exists=lambda: True)
        with patch.object(Release._default_manager, "filter", return_value=queryset) as filter_mock:
            self.assertTrue(loan.is_released)

        filter_mock.assert_called_once_with(pk=91, loan_id=42)