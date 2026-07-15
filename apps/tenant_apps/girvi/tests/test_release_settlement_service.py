from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.release_settlement import (
    COMPATIBILITY_NO_POSTED_ACCRUAL_ROWS,
    VARIANCE_ABOVE_TOLERANCE,
    VARIANCE_MATCH,
    apply_release_settlement_snapshot,
    build_release_settlement_basis,
)


class ReleaseSettlementServiceTests(SimpleTestCase):
    @patch("apps.tenant_apps.girvi.selectors.loan_total_interest_payments")
    @patch("apps.tenant_apps.girvi.selectors.build_loan_settlement_balance")
    def test_uses_posted_accrual_rows_when_available(self, mock_settlement, mock_paid):
        mock_settlement.return_value = SimpleNamespace(
            principal_due=Decimal("500.00"),
            interest_due=Decimal("150.00"),
        )
        mock_paid.return_value = Decimal("25.00")

        accruals = MagicMock()
        accruals.filter.return_value.aggregate.return_value = {
            "total": Decimal("175.00")
        }
        loan = SimpleNamespace(pk=1, interest_accruals=accruals)

        basis = build_release_settlement_basis(loan, "2026-07-06")

        self.assertTrue(basis.used_accrual_rows)
        self.assertEqual(basis.basis, "ACCRUAL_ROWS")
        self.assertEqual(basis.accrual_interest_gross, Decimal("175.00"))
        self.assertEqual(basis.interest_paid, Decimal("25.00"))
        self.assertEqual(basis.final_interest_due, Decimal("150.00"))
        self.assertEqual(basis.total_due, Decimal("650.00"))
        self.assertEqual(basis.variance_classification, VARIANCE_MATCH)

    @patch("apps.tenant_apps.girvi.selectors.loan_total_interest_payments")
    @patch("apps.tenant_apps.girvi.selectors.build_loan_settlement_balance")
    def test_falls_back_to_selector_when_no_accrual_rows(self, mock_settlement, mock_paid):
        mock_settlement.return_value = SimpleNamespace(
            principal_due=Decimal("500.00"),
            interest_due=Decimal("150.00"),
        )
        mock_paid.return_value = Decimal("0.00")

        accruals = MagicMock()
        accruals.filter.return_value.aggregate.return_value = {"total": None}
        loan = SimpleNamespace(pk=1, interest_accruals=accruals)

        basis = build_release_settlement_basis(loan, "2026-07-06")

        self.assertFalse(basis.used_accrual_rows)
        self.assertEqual(basis.basis, "SELECTOR_COMPATIBILITY")
        self.assertEqual(
            basis.compatibility_reason,
            "No posted accrual rows were available through the release date.",
        )
        self.assertEqual(
            basis.compatibility_code,
            COMPATIBILITY_NO_POSTED_ACCRUAL_ROWS,
        )
        self.assertEqual(basis.final_interest_due, Decimal("150.00"))
        self.assertEqual(basis.total_due, Decimal("650.00"))

    @patch("apps.tenant_apps.girvi.selectors.loan_total_interest_payments")
    @patch("apps.tenant_apps.girvi.selectors.build_loan_settlement_balance")
    def test_classifies_material_selector_to_accrual_variance(
        self,
        mock_settlement,
        mock_paid,
    ):
        mock_settlement.return_value = SimpleNamespace(
            principal_due=Decimal("500.00"),
            interest_due=Decimal("150.00"),
        )
        mock_paid.return_value = Decimal("25.00")
        accruals = MagicMock()
        accruals.filter.return_value.aggregate.return_value = {
            "total": Decimal("160.00")
        }
        loan = SimpleNamespace(pk=1, interest_accruals=accruals)

        basis = build_release_settlement_basis(loan, "2026-07-06")

        self.assertEqual(basis.variance, Decimal("15.00"))
        self.assertEqual(
            basis.variance_classification,
            VARIANCE_ABOVE_TOLERANCE,
        )

    @patch("apps.tenant_apps.girvi.selectors.build_loan_settlement_balance")
    def test_selector_failure_is_not_silently_converted_to_compatibility(
        self,
        mock_settlement,
    ):
        mock_settlement.side_effect = RuntimeError("selector unavailable")

        with self.assertRaisesMessage(RuntimeError, "selector unavailable"):
            build_release_settlement_basis(SimpleNamespace(pk=1), "2026-07-06")

    @patch("apps.tenant_apps.girvi.selectors.loan_total_interest_payments")
    @patch("apps.tenant_apps.girvi.selectors.build_loan_settlement_balance")
    def test_accrual_query_failure_is_not_treated_as_zero_rows(
        self,
        mock_settlement,
        mock_paid,
    ):
        mock_settlement.return_value = SimpleNamespace(
            principal_due=Decimal("500.00"),
            interest_due=Decimal("150.00"),
        )
        mock_paid.return_value = Decimal("0.00")
        accruals = MagicMock()
        accruals.filter.return_value.aggregate.side_effect = RuntimeError(
            "accrual query failed"
        )

        with self.assertRaisesMessage(RuntimeError, "accrual query failed"):
            build_release_settlement_basis(
                SimpleNamespace(pk=1, interest_accruals=accruals),
                "2026-07-06",
            )

    def test_apply_release_settlement_snapshot_sets_release_fields(self):
        release = SimpleNamespace()
        basis = SimpleNamespace(
            basis="ACCRUAL_ROWS",
            principal_due=Decimal("500.00"),
            final_interest_due=Decimal("150.00"),
            total_due=Decimal("650.00"),
            selector_interest_quote=Decimal("175.00"),
            accrual_interest_gross=Decimal("180.00"),
            interest_paid=Decimal("30.00"),
            variance=Decimal("25.00"),
        )

        apply_release_settlement_snapshot(release, basis)

        self.assertEqual(release.settlement_basis, "ACCRUAL_ROWS")
        self.assertEqual(release.settlement_principal_amount, Decimal("500.00"))
        self.assertEqual(release.settlement_interest_amount, Decimal("150.00"))
        self.assertEqual(release.settlement_total_amount, Decimal("650.00"))
        self.assertEqual(release.selector_interest_quote, Decimal("175.00"))
