from contextlib import nullcontext
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from dateutil.relativedelta import relativedelta
from django.test import SimpleTestCase
from django.utils import timezone
from moneyed import Money

from apps.tenant_apps.dea.posting.rules.givenloan_receipt import GivenLoanReceiptRule
from apps.tenant_apps.dea.posting.rules.givenloan_release import GivenLoanReleaseRule
from apps.tenant_apps.girvi.service_modules.accrual import (
    InterestAccrualCommand,
    InterestAccrualService,
)


class _FakeAccrualRelation:
    def values_list(self, *args, **kwargs):
        return []


class InterestAccrualAccountingTests(SimpleTestCase):
    def _build_loan(self):
        base_date = timezone.localdate() - relativedelta(months=2)
        return SimpleNamespace(
            pk=99,
            loan_id="GL-0099",
            loan_date=timezone.make_aware(datetime.combine(base_date, datetime.min.time()).replace(hour=10)),
            get_interest_amount=Decimal("125.00"),
            interest_accruals=_FakeAccrualRelation(),
        )

    def test_execute_posts_journal_entry_when_requested(self):
        loan = self._build_loan()
        command = InterestAccrualCommand(
            loan=loan,
            as_of_date=timezone.localdate(),
            trigger_source="PERIOD_CLOSE",
            created_by=SimpleNamespace(id=5),
            post_to_accounting=True,
        )

        created_rows = [
            MagicMock(accrued_amount=Decimal("125.00")),
            MagicMock(accrued_amount=Decimal("125.00")),
        ]

        with patch(
            "apps.tenant_apps.girvi.service_modules.accrual.transaction.atomic",
            side_effect=lambda: nullcontext(),
        ), patch(
            "apps.tenant_apps.girvi.service_modules.accrual.LoanInterestAccrual.objects.create",
            side_effect=created_rows,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.accrual.post_interest_accrual_batch",
            return_value=(MagicMock(), MagicMock(), MagicMock()),
        ) as mock_post:
            result = InterestAccrualService.execute(command)

        self.assertTrue(result.success)
        mock_post.assert_called_once_with(
            command,
            result.loan and InterestAccrualService.preview(command),
            created_rows,
            posted_status_value="POSTED",
        )
        self.assertEqual(result.created_count, 2)


class GivenLoanAccrualAwarePostingRuleTests(SimpleTestCase):
    @patch(
        "apps.tenant_apps.dea.posting.rules.givenloan_receipt.resolve_given_loan_borrower_account",
        return_value=SimpleNamespace(id=77),
    )
    @patch("apps.tenant_apps.dea.posting.rules.givenloan_receipt.get_ledger_id_by_key")
    def test_receipt_rule_clears_receivable_before_new_income(
        self,
        mock_get_ledger_id_by_key,
        _mock_resolve_account,
    ):
        mock_get_ledger_id_by_key.side_effect = lambda key, tenant_id=None: {
            "CASH": 1,
            "LOAN_PRINCIPAL_CTRL": 2,
            "BORROWER_LOAN_CTRL": 3,
            "INTEREST_RECEIVABLE": 4,
            "INTEREST_INCOME": 5,
        }[key]

        loan = SimpleNamespace(interest_receivable_balance=lambda: Decimal("80.00"))
        payment = SimpleNamespace(
            total_amount=Money(600, "INR"),
            principal_amount=Money(500, "INR"),
            interest_amount=Money(100, "INR"),
            source_loan=loan,
        )

        bundle = GivenLoanReceiptRule().build_posting(
            SimpleNamespace(doc=payment, tenant_id=None)
        )

        self.assertEqual(len(bundle.ledger_lines), 3)
        self.assertEqual(bundle.ledger_lines[1].credit_ledger_id, 4)
        self.assertEqual(bundle.ledger_lines[1].amount, Decimal("80"))
        self.assertEqual(bundle.ledger_lines[2].credit_ledger_id, 5)
        self.assertEqual(bundle.ledger_lines[2].amount, Decimal("20"))

    @patch(
        "apps.tenant_apps.dea.posting.rules.givenloan_release.resolve_given_loan_borrower_account",
        return_value=SimpleNamespace(id=77),
    )
    @patch("apps.tenant_apps.dea.posting.rules.givenloan_release.get_ledger_id_by_key")
    def test_release_rule_clears_receivable_before_new_income(
        self,
        mock_get_ledger_id_by_key,
        _mock_resolve_account,
    ):
        mock_get_ledger_id_by_key.side_effect = lambda key, tenant_id=None: {
            "CASH": 1,
            "LOAN_PRINCIPAL_CTRL": 2,
            "BORROWER_LOAN_CTRL": 3,
            "INTEREST_RECEIVABLE": 4,
            "INTEREST_INCOME": 5,
        }[key]

        loan = SimpleNamespace(interest_receivable_balance=lambda: Decimal("60.00"))
        payment = SimpleNamespace(
            total_amount=Money(560, "INR"),
            principal_amount=Money(500, "INR"),
            interest_amount=Money(60, "INR"),
            source_loan=loan,
        )

        bundle = GivenLoanReleaseRule().build_posting(
            SimpleNamespace(doc=payment, tenant_id=None)
        )

        self.assertEqual(len(bundle.ledger_lines), 2)
        self.assertEqual(bundle.ledger_lines[1].credit_ledger_id, 4)
        self.assertEqual(bundle.ledger_lines[1].amount, Decimal("60"))
