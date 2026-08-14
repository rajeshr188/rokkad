from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.settlement_adjustments import (
    SettlementAdjustmentCommand,
    SettlementAdjustmentService,
    SettlementAdjustmentType,
)


class SettlementAdjustmentServiceTests(SimpleTestCase):
    def test_write_off_requires_document_and_posting_implementation(self):
        result = SettlementAdjustmentService.execute(
            SettlementAdjustmentCommand(
                loan=SimpleNamespace(pk=1, loan_id="GL-1"),
                adjustment_type=SettlementAdjustmentType.WRITE_OFF,
                created_by=SimpleNamespace(pk=1),
                reason="approved loss",
                principal_amount=Decimal("100.00"),
                interest_amount=Decimal("10.00"),
            )
        )

        self.assertFalse(result.success)
        self.assertIn("explicit settlement adjustment document", result.message)
        self.assertEqual(result.adjustment_type, SettlementAdjustmentType.WRITE_OFF)

    def test_rejects_missing_reason(self):
        result = SettlementAdjustmentService.execute(
            SettlementAdjustmentCommand(
                loan=SimpleNamespace(pk=1, loan_id="GL-1"),
                adjustment_type=SettlementAdjustmentType.INTEREST_WAIVER,
                created_by=SimpleNamespace(pk=1),
                reason="",
                interest_amount=Decimal("10.00"),
            )
        )

        self.assertFalse(result.success)
        self.assertIn("Adjustment reason is required.", result.errors)
