from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.db import connection
from django.utils import timezone

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.selectors.business_overview import get_daily_counter_activity
from . import test_business_overview as fixtures


class DailyCounterTests(fixtures.BusinessOverviewTests):
    def test_actual_day_receipts_have_components_and_exclude_offsets(self):
        today = timezone.localdate()
        with workspace_context(self.workspace.pk):
            loan = self.loan(self.workspace)
            self.event(loan, 'DISBURSAL', {'principal': 1000, 'net_cash': 980})
            self.event(loan, 'REPAYMENT', {'principal': 100, 'interest': 20, 'fees': 2})
            self.event(loan, 'RELEASE_RECEIPT', {'principal': 900, 'interest': 10, 'fees': 3})
            self.event(loan, 'REPAYMENT', {'principal': 888, 'interest': 88}, day=today - timedelta(days=1))
            self.event(loan, 'REPAYMENT', {'principal': 999, 'interest': 99}, day=today + timedelta(days=1))
            self.event(loan, 'RENEWAL_SETTLEMENT', {'principal': 700, 'interest': 70})
            self.event(loan, 'AUCTION_RECOVERY', {'principal': 600, 'interest': 60})
            result = get_daily_counter_activity(workspace=self.workspace)
            self.assertEqual(result['new_loans'], 1)
            self.assertEqual(result['proceeds'], Decimal('980'))
            self.assertEqual((result['receipts_count'], result['principal'], result['interest'], result['fees']), (2, 1000, 30, 5))
            self.assertEqual(result['total'], Decimal('1035'))

    def test_current_reversal_excludes_receipt_but_future_reversal_does_not(self):
        with workspace_context(self.workspace.pk):
            loan = self.loan(self.workspace)
            first = self.event(loan, 'REPAYMENT', {'principal': 100, 'interest': 10})
            self.event(loan, 'REVERSAL', first.payload['values'], original=first)
            second = self.event(loan, 'REPAYMENT', {'principal': 200, 'interest': 20})
            self.event(loan, 'REVERSAL', second.payload['values'], original=second,
                day=timezone.localdate() + timedelta(days=1))
            result = get_daily_counter_activity(workspace=self.workspace)
            self.assertEqual((result['receipts_count'], result['total']), (1, 220))

    def test_malformed_receipt_makes_entire_amount_unavailable(self):
        with workspace_context(self.workspace.pk):
            loan = self.loan(self.workspace)
            self.event(loan, 'REPAYMENT', {'principal': 100, 'interest': 10})
            self.event(loan, 'REPAYMENT', {'principal': 100, 'interest': 'NaN'})
            result = get_daily_counter_activity(workspace=self.workspace)
            self.assertEqual((result['receipts_count'], result['unavailable_receipts']), (2, 1))
            self.assertIsNone(result['total'])
            self.assertIsNone(result['principal'])

    def test_restricted_reader_and_workspace_scope(self):
        other = Company.objects.create(name='Other counter', schema_name='daily-other', owner=self.owner, creator=self.owner)
        with workspace_context(other.pk):
            self.event(self.loan(other), 'REPAYMENT', {'principal': 99999, 'interest': 99})
        with workspace_context(self.workspace.pk):
            self.event(self.loan(self.workspace), 'REPAYMENT', {'principal': 100, 'interest': 10})
            with self.assertRaises(ValueError):
                get_daily_counter_activity(workspace=other)
            role = connection.ops.quote_name('counter_read_' + uuid4().hex)
            with connection.cursor() as cursor:
                cursor.execute(f'CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS')
                cursor.execute(f'GRANT USAGE ON SCHEMA public TO {role}')
                cursor.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}')
                cursor.execute(f'SET LOCAL ROLE {role}')
            try:
                self.assertEqual(get_daily_counter_activity(workspace=self.workspace)['total'], 110)
            finally:
                with connection.cursor() as cursor:
                    cursor.execute('RESET ROLE')
