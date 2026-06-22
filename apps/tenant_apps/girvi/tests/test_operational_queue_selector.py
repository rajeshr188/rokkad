from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.selectors import build_dashboard_operational_queue


class DashboardOperationalQueueSelectorTests(SimpleTestCase):
    @patch("apps.tenant_apps.girvi.flows.build_runtime_loan_flow")
    @patch("apps.tenant_apps.girvi.service_modules.overdue_policy.evaluate_overdue_policy")
    @patch("apps.tenant_apps.girvi.selectors.build_loan_settlement_balance")
    def test_build_operational_queue_groups_due_overdue_npa_and_notice_candidates(
        self,
        mock_settlement,
        mock_policy,
        mock_flow,
    ):
        as_of = date(2026, 6, 22)

        class FakeNoticeQuerySet:
            def __init__(self, has_draft=False):
                self._has_draft = has_draft

            def filter(self, **_kwargs):
                return self

            def exists(self):
                return self._has_draft

        loan_due = SimpleNamespace(
            pk=1,
            loan_id="GL-001",
            status="ActiveCurrent",
            borrower=SimpleNamespace(name="Asha"),
            notifications=FakeNoticeQuerySet(False),
        )
        loan_overdue = SimpleNamespace(
            pk=2,
            loan_id="GL-002",
            status="ActiveCurrent",
            borrower=SimpleNamespace(name="Ravi"),
            notifications=FakeNoticeQuerySet(False),
        )
        loan_npa = SimpleNamespace(
            pk=3,
            loan_id="GL-003",
            status="ActiveOverdue",
            borrower=SimpleNamespace(name="Mina"),
            notifications=FakeNoticeQuerySet(False),
        )
        loan_cure = SimpleNamespace(
            pk=4,
            loan_id="GL-004",
            status="ActiveNPA",
            borrower=SimpleNamespace(name="Kiran"),
            notifications=FakeNoticeQuerySet(True),
        )

        settlements = {
            1: SimpleNamespace(total_outstanding=Decimal("100.00")),
            2: SimpleNamespace(total_outstanding=Decimal("150.00")),
            3: SimpleNamespace(total_outstanding=Decimal("250.00")),
            4: SimpleNamespace(total_outstanding=Decimal("0.00")),
        }
        policies = {
            1: SimpleNamespace(
                maturity_date=as_of,
                settlement_amount=Decimal("100.00"),
                current_value=Decimal("500.00"),
                undersecured=False,
                is_overdue=False,
                is_npa=False,
            ),
            2: SimpleNamespace(
                maturity_date=date(2026, 6, 21),
                settlement_amount=Decimal("150.00"),
                current_value=Decimal("400.00"),
                undersecured=False,
                is_overdue=True,
                is_npa=False,
            ),
            3: SimpleNamespace(
                maturity_date=date(2026, 6, 10),
                settlement_amount=Decimal("250.00"),
                current_value=Decimal("200.00"),
                undersecured=True,
                is_overdue=True,
                is_npa=True,
            ),
            4: SimpleNamespace(
                maturity_date=date(2026, 6, 1),
                settlement_amount=Decimal("0.00"),
                current_value=Decimal("300.00"),
                undersecured=False,
                is_overdue=False,
                is_npa=False,
            ),
        }

        mock_settlement.side_effect = lambda loan, **_kwargs: settlements[loan.pk]
        mock_policy.side_effect = lambda loan, **_kwargs: policies[loan.pk]

        def _fake_flow(loan, *_args, **_kwargs):
            return SimpleNamespace(
                mark_overdue=SimpleNamespace(can_proceed=lambda: loan.pk == 2),
                mark_npa=SimpleNamespace(can_proceed=lambda: loan.pk == 3),
                cure_to_current=SimpleNamespace(can_proceed=lambda: loan.pk == 4),
            )

        mock_flow.side_effect = _fake_flow

        queue = build_dashboard_operational_queue(
            user=SimpleNamespace(),
            workspace=SimpleNamespace(),
            as_of_date=as_of,
            loans=[loan_due, loan_overdue, loan_npa, loan_cure],
        )

        self.assertEqual(queue["counts"]["due_today"], 1)
        self.assertEqual(queue["counts"]["overdue_candidates"], 1)
        self.assertEqual(queue["counts"]["npa_candidates"], 1)
        self.assertEqual(queue["counts"]["cure_candidates"], 1)
        self.assertEqual(queue["counts"]["notice_candidates"], 1)

        self.assertEqual(queue["due_today"][0]["loan_id"], "GL-001")
        self.assertEqual(queue["overdue_candidates"][0]["loan_id"], "GL-002")
        self.assertEqual(queue["npa_candidates"][0]["loan_id"], "GL-003")
        self.assertEqual(queue["cure_candidates"][0]["loan_id"], "GL-004")
