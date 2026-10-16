"""Everyday counter disclosures and navigation use existing financial services."""
from django.urls import reverse
from django.test import RequestFactory, SimpleTestCase
from django.http import HttpResponseRedirect
from types import SimpleNamespace
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from . import test_monitoring_presentation as native
from . import test_paper_entry_simplification as paper


class CounterAmountTests(native.MonitoringPresentationTests):
    get_test_schema_name = classmethod(lambda cls: 'counter-amounts')

    def test_collection_summary_includes_eligible_unposted_interest(self):
        from apps.tenant_apps.loans.selectors.loan_summary import get_loan_summary
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        result = client.get(reverse('workspace_loans:pawn_loan_detail', args=[self.tenant.slug, self.loan.pk]))
        summary = get_loan_summary(self.loan, as_of_date=self.today)
        self.assertEqual(result.context['collection_position'].balance, summary.balance)
        self.assertEqual(result.context['balance'].total_due, 1000)
        self.assertEqual(summary.balance.total_due, 1080)
        self.assertContains(result, 'Total to collect')
        self.assertContains(result, '1,080')
        self.assertContains(result, 'Recorded total')
        self.assertNotContains(result, 'Current balance as of')

    def test_prepared_collection_preserves_amount_and_scope(self):
        from apps.tenant_apps.loans.selectors.financial_inputs import get_pawn_loan_financial_inputs
        from apps.tenant_apps.loans.selectors.servicing_contract import get_servicing_position
        baseline = get_servicing_position(self.loan, as_of_date=self.today)
        inputs = get_pawn_loan_financial_inputs(self.loan.pk, as_of_date=self.today)
        prepared = get_servicing_position(self.loan, as_of_date=self.today, financial_inputs=inputs)
        self.assertEqual(prepared.balance, baseline.balance)
        self.assertEqual(prepared.balance_basis, baseline.balance_basis)
        with self.assertRaises(ValueError):
            get_servicing_position(self.loan, as_of_date=self.today + timedelta(days=1), financial_inputs=inputs)

    def test_detail_shares_financial_inputs_and_retains_narrow_legacy_reads(self):
        from apps.tenant_apps.loans.selectors.financial_inputs import get_pawn_loan_financial_inputs
        with patch('apps.tenant_apps.loans.selectors.financial_inputs.get_pawn_loan_financial_inputs', wraps=get_pawn_loan_financial_inputs) as read:
            self.assertEqual(self.detail().status_code, 200)
        self.assertEqual(read.call_count, 1)
        loan, _ = self.legacy_loan()
        response = self.detail(loan)
        self.assertContains(response, 'Recorded amount pending')
        self.assertContains(response, 'This retained contract supplies recorded debt only')

    def test_list_amounts_are_optional_and_use_the_collection_position(self):
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        url = reverse('workspace_loans:pawn_loan_list', args=[self.tenant.slug])
        with patch('apps.tenant_apps.loans.selectors.servicing_contract.get_servicing_position') as read:
            page = client.get(url, {'amounts': '0'})
            self.assertEqual(page.status_code, 200)
            read.assert_not_called()
        page = client.get(url, {'amounts': '1', 'borrower': self.loan.borrower_id})
        self.assertContains(page, '1,080')
        self.assertContains(page, 'Principal pending')
        self.assertContains(page, 'Record payment')
        self.assertContains(page, 'return_to=')

    def test_detail_retains_the_filtered_return_location(self):
        from django.utils.html import escape
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        origin = reverse('workspace_loans:pawn_loan_list', args=[self.tenant.slug]) + '?borrower=1&state=ACTIVE&page=2'
        url = reverse('workspace_loans:pawn_loan_detail', args=[self.tenant.slug, self.loan.pk])
        response = client.get(url, {'return_to': origin})
        self.assertContains(response, 'href="' + escape(origin) + '"')
        self.assertContains(response, 'return_to=')


class CounterNavigationTests(SimpleTestCase):
    def request(self, target):
        request = RequestFactory().get('/w/counter/loans/internal/1/', {'return_to': target})
        request.workspace = SimpleNamespace(slug='counter')
        return request

    def test_return_context_is_scoped_and_strips_fragment_export_controls(self):
        from apps.tenant_apps.loans.web.counter_navigation import counter_return
        origin = reverse('workspace_loans:pawn_loan_list', args=['counter'])
        self.assertEqual(counter_return(self.request(origin + '?q=ring&page=2&export=xlsx')), origin + '?q=ring&page=2')
        dashboard = reverse('workspace_slug_dashboard', args=['counter'])
        self.assertEqual(counter_return(self.request(dashboard + '?queue=overdue&section=queues')), dashboard + '?queue=overdue')
        for target in ('//elsewhere.test/', 'https://elsewhere.test/', 'http://[',
                       '/w/other/loans/internal/', '/w/counter/loans/internal/create/', '\\evil', origin + '\r\nX:bad'):
            self.assertEqual(counter_return(self.request(target)), '', target)

    def test_successful_action_preserves_only_its_validated_context(self):
        from apps.tenant_apps.loans.web.counter_navigation import preserve_counter_return
        origin = reverse('workspace_loans:pawn_loan_list', args=['counter']) + '?q=ring&page=2'
        detail = reverse('workspace_loans:pawn_loan_detail', args=['counter', 8])
        wrapped = preserve_counter_return(lambda request: HttpResponseRedirect(detail))
        result = wrapped(self.request(origin))
        self.assertEqual(parse_qs(urlsplit(result.url).query)['return_to'], [origin])
        result = wrapped(self.request('https://elsewhere.test/'))
        self.assertEqual(result.url, detail)


class CounterAssuranceTests(paper.PaperEntrySimplificationTests):
    get_test_schema_name = classmethod(lambda cls: 'counter-assurance')

    def test_unconfirmed_admission_makes_no_checked_through_claim(self):
        loan, _, _ = self.admit()
        self.assertFalse(loan.transaction_reviews.exists())
        page = self.client.get(reverse('workspace_loans:pawn_loan_detail', args=[self.tenant.slug, loan.pk]))
        self.assertContains(page, 'Optional paper-book reconciliation was not confirmed')
        self.assertNotContains(page, 'paper activity was checked through')
        self.assertNotContains(page, 'Auction recovery requires complete transaction confirmation')
        self.assertEqual(page.context['evidence_quality']['transactions']['status'], 'RECORDED_POSITION')
        self.assertFalse(loan.transaction_reviews.exists())

    def test_confirmed_admission_retains_its_dated_historical_claim(self):
        values = self.facts(confirmed_history='on', complete_through=self.today.isoformat())
        loan, _, _ = self.admit(values)
        page = self.client.get(reverse('workspace_loans:pawn_loan_detail', args=[self.tenant.slug, loan.pk]))
        self.assertContains(page, 'At recording, paper activity was confirmed entered through')
        self.assertContains(page, 'Current book assurance is shown')
