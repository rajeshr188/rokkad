from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.tenant_apps.loans.selectors.obligation_state import (
    calculate_obligation_state_as_of, _fold_obligation_state,
)


class _Rows(list):
    def order_by(self, *_args):
        return self

    def filter(self, **_kwargs):
        return self


class ObligationStateContractTests(SimpleTestCase):
    def test_one_fold_owns_remaining_due_and_overdue_amounts(self):
        schedule = self._schedule(
            self._obligation(
                1,
                due=date(2026, 8, 12),
                principal="1000",
                interest="100",
                allocations=(self._allocation("PRINCIPAL", "250"),),
            ),
            self._obligation(
                2,
                due=date(2026, 8, 13),
                principal="500",
                interest="50",
            ),
            self._obligation(
                3,
                due=date(2026, 9, 13),
                principal="2000",
                interest="200",
            ),
        )

        state = _fold_obligation_state(schedule, date(2026, 8, 13), schedule.obligations, lambda row: row.allocations)

        self.assertEqual(state.remaining.principal, Decimal("3250"))
        self.assertEqual(state.remaining.interest, Decimal("350"))
        self.assertEqual(state.due_now.total, Decimal("1400"))
        self.assertEqual(state.overdue.total, Decimal("850"))
        self.assertEqual(state.schedule_id, 91)
        self.assertEqual(state.schedule_fingerprint, "schedule-fingerprint")
        self.assertEqual(state.integrity_findings, ())

    def test_overallocation_is_visible_and_excluded_from_aggregate_amounts(self):
        schedule = self._schedule(
            self._obligation(
                7,
                due=date(2026, 8, 1),
                principal="100",
                interest="10",
                allocations=(self._allocation("PRINCIPAL", "101"),),
            )
        )

        state = _fold_obligation_state(schedule, date(2026, 8, 13), schedule.obligations, lambda row: row.allocations)

        self.assertEqual(state.remaining.total, Decimal("0"))
        self.assertEqual(
            state.integrity_findings,
            ("Obligation 7 is over-allocated.",),
        )
        self.assertEqual(state.obligations[0].principal, Decimal("-1"))

    def test_no_active_schedule_is_an_explicit_zero_contract(self):
        state = calculate_obligation_state_as_of(None, date(2026, 8, 13))

        self.assertIsNone(state.schedule_id)
        self.assertEqual(state.due_now.total, Decimal("0"))
        self.assertEqual(state.overdue.total, Decimal("0"))
        self.assertEqual(state.remaining.total, Decimal("0"))

    def _schedule(self, *obligations):
        return SimpleNamespace(
            pk=91,
            fingerprint="schedule-fingerprint",
            maturity_date=date(2026, 9, 13),
            obligations=_Rows(obligations),
        )

    def _obligation(self, pk, *, due, principal, interest, allocations=()):
        return SimpleNamespace(
            pk=pk,
            due_date=due,
            principal_due=Decimal(principal),
            interest_due=Decimal(interest),
            allocations=_Rows(allocations),
        )

    def _allocation(self, component, amount):
        return SimpleNamespace(component=component, amount=Decimal(amount))

