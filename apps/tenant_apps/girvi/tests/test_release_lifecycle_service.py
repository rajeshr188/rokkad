from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.tenant_apps.girvi.services import (
    ReleaseCreateCommand,
    ReleaseLifecycleService,
)
from apps.tenant_apps.girvi.models.custody_tracking import ItemCustodyStatus


class ReleaseLifecycleServiceTests(TestCase):
    def _fake_user(self):
        return SimpleNamespace(profile=SimpleNamespace(workspace="tenant-1"))

    def _fake_loan(self):
        return SimpleNamespace(loan_id="L-001", status="Disbursed")

    def _fake_release_model(self):
        class FakeRelease:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
                self.saved = False
                self.release_id = "RL0001"

            def save(self):
                self.saved = True

        return FakeRelease

    def test_preview_rejects_missing_actor(self):
        preview = ReleaseLifecycleService.preview(
            ReleaseCreateCommand(
                loan=self._fake_loan(),
                created_by=None,
                release_date="2026-04-01",
            )
        )

        self.assertFalse(preview.is_valid)
        self.assertIn("created_by is required", " ".join(preview.errors))

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
        flow.request_closure.can_proceed.return_value = True
        flow.complete_closure.can_proceed.return_value = True

        with patch("apps.tenant_apps.girvi.services.apps.get_model", return_value=FakeRelease), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.build_runtime_loan_flow", return_value=flow
        ), patch("apps.tenant_apps.girvi.service_modules.release_lifecycle.record_loan_release") as post_release:
            release = ReleaseLifecycleService.create_release(
                loan=loan,
                created_by=user,
                release_date="2026-04-01",
                released_by=None,
            )

        self.assertTrue(release.saved)
        flow.request_closure.assert_called_once()
        flow.complete_closure.assert_called_once()
        post_release.assert_called_once_with(release, created_by=user)

    def test_execute_returns_structured_result(self):
        loan = self._fake_loan()
        user = self._fake_user()

        class FakeRelease:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
                self.saved = False
                self.release_id = "RL0001"

            def save(self):
                self.saved = True

        flow = MagicMock()
        flow.request_closure.can_proceed.return_value = True
        flow.complete_closure.can_proceed.return_value = True
        fake_payment = SimpleNamespace(payment_id="PAY-1")

        with patch("apps.tenant_apps.girvi.services.apps.get_model", return_value=FakeRelease), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.build_runtime_loan_flow", return_value=flow
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.record_loan_release",
            return_value=(fake_payment, True),
        ):
            result = ReleaseLifecycleService.execute(
                ReleaseCreateCommand(
                    loan=loan,
                    created_by=user,
                    release_date="2026-04-01",
                    released_by=None,
                )
            )

        self.assertTrue(result.success)
        self.assertEqual(result.release.loan, loan)
        self.assertEqual(result.payment, fake_payment)
        self.assertTrue(result.payment_created)

    def test_create_release_rejects_illegal_transition(self):
        loan = self._fake_loan()
        user = self._fake_user()

        class FakeRelease:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

            def save(self):
                raise AssertionError("save should not be called")

        flow = MagicMock()
        flow.request_closure.can_proceed.return_value = False
        flow.complete_closure.can_proceed.return_value = False

        with patch("apps.tenant_apps.girvi.services.apps.get_model", return_value=FakeRelease), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.build_runtime_loan_flow", return_value=flow
        ), patch("apps.tenant_apps.girvi.service_modules.release_lifecycle.record_loan_release") as post_release:
            with self.assertRaises(ValidationError):
                ReleaseLifecycleService.create_release(
                    loan=loan,
                    created_by=user,
                    release_date="2026-04-01",
                    released_by=None,
                )

        post_release.assert_not_called()

    def test_execute_uses_v2_closure_flow_for_active_current_loans(self):
        loan = SimpleNamespace(loan_id="L-001", status="ActiveCurrent")
        user = self._fake_user()

        class FakeRelease:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
                self.saved = False
                self.release_id = "RLV2-1"

            def save(self):
                self.saved = True

        flow = MagicMock()
        flow.request_closure.can_proceed.return_value = True
        flow.complete_closure.can_proceed.return_value = True
        fake_payment = SimpleNamespace(payment_id="PAY-V2")

        with patch("apps.tenant_apps.girvi.services.apps.get_model", return_value=FakeRelease), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.build_runtime_loan_flow", return_value=flow
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.record_loan_release",
            return_value=(fake_payment, True),
        ):
            result = ReleaseLifecycleService.execute(
                ReleaseCreateCommand(
                    loan=loan,
                    created_by=user,
                    release_date="2026-04-01",
                    released_by=None,
                )
            )

        self.assertTrue(result.success)
        flow.request_closure.assert_called_once_with(requested_by=user)
        flow.complete_closure.assert_called_once_with(
            completed_by=user,
            release_id="RLV2-1",
        )

    def test_execute_stops_before_closure_and_posting_when_item_release_fails(self):
        item = MagicMock(itemdesc="Chain")
        item.custody_status = ItemCustodyStatus.WITH_LENDER
        item.release_to_customer.side_effect = ValidationError("still with lender")
        loan = SimpleNamespace(
            loan_id="L-001",
            status="ActiveCurrent",
            loanitems=SimpleNamespace(all=lambda: [item]),
        )
        user = self._fake_user()
        flow = MagicMock()
        flow.request_closure.can_proceed.return_value = True
        flow.complete_closure.can_proceed.return_value = True

        with patch(
            "apps.tenant_apps.girvi.services.apps.get_model",
            return_value=self._fake_release_model(),
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.build_runtime_loan_flow",
            return_value=flow,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.record_loan_release"
        ) as post_release:
            result = ReleaseLifecycleService.execute(
                ReleaseCreateCommand(
                    loan=loan,
                    created_by=user,
                    release_date="2026-04-01",
                    released_by=None,
                )
            )

        self.assertFalse(result.success)
        self.assertIn("collateral custody update failed", result.message)
        self.assertIn("Chain", result.message)
        item.release_to_customer.assert_called_once_with(user=user)
        flow.request_closure.assert_not_called()
        flow.complete_closure.assert_not_called()
        post_release.assert_not_called()

    def test_execute_rejects_duplicate_release_before_side_effects(self):
        loan = SimpleNamespace(
            loan_id="L-001",
            status="Closed",
            release=SimpleNamespace(release_id="RL0001"),
        )
        user = self._fake_user()

        with patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.build_runtime_loan_flow"
        ) as flow_builder, patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.record_loan_release"
        ) as post_release:
            result = ReleaseLifecycleService.execute(
                ReleaseCreateCommand(
                    loan=loan,
                    created_by=user,
                    release_date="2026-04-01",
                    released_by=None,
                )
            )

        self.assertFalse(result.success)
        self.assertIn("already has a release", result.message)
        flow_builder.assert_not_called()
        post_release.assert_not_called()

    def test_execute_allows_item_already_with_customer_as_idempotent(self):
        item = MagicMock(itemdesc="Ring")
        item.custody_status = ItemCustodyStatus.WITH_CUSTOMER
        item.release_to_customer.side_effect = ValidationError(
            "already released to customer"
        )
        loan = SimpleNamespace(
            loan_id="L-001",
            status="ActiveCurrent",
            loanitems=SimpleNamespace(all=lambda: [item]),
        )
        user = self._fake_user()
        flow = MagicMock()
        flow.request_closure.can_proceed.return_value = True
        flow.complete_closure.can_proceed.return_value = True
        fake_payment = SimpleNamespace(payment_id="PAY-1")

        with patch(
            "apps.tenant_apps.girvi.services.apps.get_model",
            return_value=self._fake_release_model(),
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.build_runtime_loan_flow",
            return_value=flow,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.record_loan_release",
            return_value=(fake_payment, True),
        ):
            result = ReleaseLifecycleService.execute(
                ReleaseCreateCommand(
                    loan=loan,
                    created_by=user,
                    release_date="2026-04-01",
                    released_by=None,
                )
            )

        self.assertTrue(result.success)
        item.release_to_customer.assert_called_once_with(user=user)
        flow.request_closure.assert_called_once_with(requested_by=user)
        flow.complete_closure.assert_called_once_with(
            completed_by=user,
            release_id="RL0001",
        )
