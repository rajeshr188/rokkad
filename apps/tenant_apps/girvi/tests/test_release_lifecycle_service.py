from types import SimpleNamespace
from decimal import Decimal
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
        self.assertEqual(result.stage_outcomes["readiness_checked"], "completed")
        self.assertNotEqual(result.stage_outcomes["accrual_catchup"], "failed")
        self.assertEqual(result.stage_outcomes["custody_transferred"], "completed")
        self.assertEqual(result.stage_outcomes["release_saved"], "completed")
        self.assertEqual(result.stage_outcomes["closure_completed"], "completed")
        self.assertEqual(result.stage_outcomes["posting_completed"], "completed")
        self.assertEqual(result.failed_stage, "")

    def test_execute_snapshots_release_settlement_basis_before_posting(self):
        loan = self._fake_loan()
        user = self._fake_user()
        basis = SimpleNamespace(
            basis="ACCRUAL_ROWS",
            principal_due=Decimal("500.00"),
            final_interest_due=Decimal("125.00"),
            total_due=Decimal("625.00"),
            selector_interest_quote=Decimal("150.00"),
            accrual_interest_gross=Decimal("175.00"),
            interest_paid=Decimal("50.00"),
            variance=Decimal("25.00"),
            used_accrual_rows=True,
        )

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

        with patch(
            "apps.tenant_apps.girvi.services.apps.get_model",
            return_value=FakeRelease,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.build_release_settlement_basis",
            return_value=basis,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.build_runtime_loan_flow",
            return_value=flow,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.record_loan_release",
            return_value=(fake_payment, True),
        ) as post_release:
            result = ReleaseLifecycleService.execute(
                ReleaseCreateCommand(
                    loan=loan,
                    created_by=user,
                    release_date="2026-04-01",
                    released_by=None,
                )
            )

        self.assertTrue(result.success)
        self.assertEqual(result.release.settlement_basis, "ACCRUAL_ROWS")
        self.assertEqual(result.release.settlement_interest_amount, Decimal("125.00"))
        self.assertEqual(result.settlement_basis, basis)
        post_release.assert_called_once_with(result.release, created_by=user)

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
        self.assertEqual(result.failed_stage, "custody_transferred")
        self.assertEqual(result.stage_outcomes["readiness_checked"], "completed")
        self.assertNotEqual(result.stage_outcomes["accrual_catchup"], "failed")
        self.assertEqual(result.stage_outcomes["custody_transferred"], "failed")
        self.assertEqual(result.stage_outcomes["release_saved"], "not_started")
        self.assertEqual(result.stage_outcomes["closure_completed"], "not_started")
        self.assertEqual(result.stage_outcomes["posting_completed"], "not_started")
        self.assertIn("custody_transferred", result.stage_errors)
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

    def test_execute_releases_custody_before_persisting_release_row(self):
        user = self._fake_user()
        saved_state = {"saved": False}

        class FakeRelease:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
                self.release_id = "RL0002"

            def save(self):
                saved_state["saved"] = True

        def assert_not_saved_yet(*, user):
            self.assertFalse(saved_state["saved"])

        item = MagicMock(itemdesc="Ring")
        item.custody_status = ItemCustodyStatus.IN_VAULT
        item.release_to_customer.side_effect = assert_not_saved_yet
        loan = SimpleNamespace(
            loan_id="L-001",
            status="ActiveCurrent",
            loanitems=SimpleNamespace(all=lambda: [item]),
        )
        flow = MagicMock()
        flow.request_closure.can_proceed.return_value = True
        flow.complete_closure.can_proceed.return_value = True
        fake_payment = SimpleNamespace(payment_id="PAY-1")

        with patch(
            "apps.tenant_apps.girvi.services.apps.get_model",
            return_value=FakeRelease,
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
        self.assertTrue(saved_state["saved"])
        item.release_to_customer.assert_called_once_with(user=user)

    def test_execute_skips_accrual_when_catchup_disabled(self):
        loan = self._fake_loan()
        user = self._fake_user()
        flow = MagicMock()
        flow.request_closure.can_proceed.return_value = True
        flow.complete_closure.can_proceed.return_value = True
        fake_payment = SimpleNamespace(payment_id="PAY-1")
        with patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.is_loan_catchup_on_release_enabled",
            return_value=False,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.is_loan_release_fail_closed_on_accrual_error_enabled",
            return_value=False,
        ), patch(
            "apps.tenant_apps.girvi.services.apps.get_model",
            return_value=self._fake_release_model(),
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.InterestAccrualService.execute"
        ) as accrue, patch(
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
        self.assertEqual(result.stage_outcomes["accrual_catchup"], "skipped")
        accrue.assert_not_called()

    def test_execute_warns_and_continues_when_accrual_fails_in_compat_mode(self):
        loan = self._fake_loan()
        user = self._fake_user()
        flow = MagicMock()
        flow.request_closure.can_proceed.return_value = True
        flow.complete_closure.can_proceed.return_value = True
        fake_payment = SimpleNamespace(payment_id="PAY-1")
        accrual_result = SimpleNamespace(
            success=False,
            message="accrual posting failed",
            warnings=[],
        )

        with patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.is_loan_catchup_on_release_enabled",
            return_value=True,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.is_loan_release_fail_closed_on_accrual_error_enabled",
            return_value=False,
        ), patch(
            "apps.tenant_apps.girvi.services.apps.get_model",
            return_value=self._fake_release_model(),
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.InterestAccrualService.execute",
            return_value=accrual_result,
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
        self.assertEqual(result.stage_outcomes["accrual_catchup"], "warning")
        self.assertIn("accrual catch-up failed", " ".join(result.warnings).lower())

    def test_execute_fails_closed_when_accrual_fails_and_policy_enabled(self):
        loan = self._fake_loan()
        user = self._fake_user()
        accrual_result = SimpleNamespace(
            success=False,
            message="accrual posting failed",
            warnings=[],
        )

        with patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.is_loan_catchup_on_release_enabled",
            return_value=True,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.is_loan_release_fail_closed_on_accrual_error_enabled",
            return_value=True,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.InterestAccrualService.execute",
            return_value=accrual_result,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.build_runtime_loan_flow"
        ) as flow_builder, patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.record_loan_release"
        ) as post_release, patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.ReleaseLifecycleService._release_items_to_customer"
        ) as release_items:
            result = ReleaseLifecycleService.execute(
                ReleaseCreateCommand(
                    loan=loan,
                    created_by=user,
                    release_date="2026-04-01",
                    released_by=None,
                )
            )

        self.assertFalse(result.success)
        self.assertEqual(result.failed_stage, "accrual_catchup")
        self.assertEqual(result.stage_outcomes["accrual_catchup"], "failed")
        self.assertEqual(result.stage_outcomes["custody_transferred"], "not_started")
        self.assertEqual(result.stage_outcomes["release_saved"], "not_started")
        self.assertIn("accrual catch-up failed", result.message.lower())
        release_items.assert_not_called()
        post_release.assert_not_called()
