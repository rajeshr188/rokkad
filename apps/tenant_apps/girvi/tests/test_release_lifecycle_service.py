from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.tenant_apps.girvi.services import ReleaseLifecycleService


class ReleaseLifecycleServiceTests(TestCase):
    def _fake_user(self):
        return SimpleNamespace(profile=SimpleNamespace(workspace="tenant-1"))

    def _fake_loan(self):
        return SimpleNamespace(loan_id="L-001", status="DISBURSED")

    def test_create_release_runs_flow_and_posting(self):
        loan = self._fake_loan()
        user = self._fake_user()

        class FakeRelease:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
                self.saved = False

            def save(self):
                self.saved = True

        flow = MagicMock()
        flow.deliver.can_proceed.return_value = True

        with patch("apps.tenant_apps.girvi.services.apps.get_model", return_value=FakeRelease), patch(
            "apps.tenant_apps.girvi.flows.LoanFlow", return_value=flow
        ), patch("apps.tenant_apps.girvi.payment_service.record_loan_release") as post_release:
            release = ReleaseLifecycleService.create_release(
                loan=loan,
                created_by=user,
                release_date="2026-04-01",
                released_by=None,
            )

        self.assertTrue(release.saved)
        flow.deliver.assert_called_once()
        post_release.assert_called_once_with(release, created_by=user)

    def test_create_release_rejects_illegal_transition(self):
        loan = self._fake_loan()
        user = self._fake_user()

        class FakeRelease:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

            def save(self):
                raise AssertionError("save should not be called")

        flow = MagicMock()
        flow.deliver.can_proceed.return_value = False

        with patch("apps.tenant_apps.girvi.services.apps.get_model", return_value=FakeRelease), patch(
            "apps.tenant_apps.girvi.flows.LoanFlow", return_value=flow
        ), patch("apps.tenant_apps.girvi.payment_service.record_loan_release") as post_release:
            with self.assertRaises(ValidationError):
                ReleaseLifecycleService.create_release(
                    loan=loan,
                    created_by=user,
                    release_date="2026-04-01",
                    released_by=None,
                )

        post_release.assert_not_called()
