"""The common directory is read-only; archive claims are never financial debt."""
from unittest.mock import patch
from uuid import uuid4

from django.test import override_settings
from django.urls import reverse
from django.db import connection

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenancy.context import without_workspace_context, workspace_context
from apps.orgs.models import Company, Membership, Role
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.selectors.directory import unadmitted_historical_records
from apps.tenant_apps.loans.services.archive import accept_evidence
from apps.tenant_apps.loans.services.history_contract import digest
from apps.tenant_apps.data_portability.tests.test_loan_archive import document
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.services.product_catalog import _seed_default_loan_products
from . import test_pawn_draft_ui as ui


@override_settings(ROOT_URLCONF='django_project.workspace_urls', STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class UnifiedDirectoryTests(WorkspaceTestCase):
    setup_tenant = classmethod(ui.PawnDraftUiTests.setup_tenant.__func__)
    _configured_setup = ui.PawnDraftUiTests._configured_setup
    _payload = ui.PawnDraftUiTests._payload

    def setUp(self):
        super().setUp()
        static = patch('django.templatetags.static.StaticNode.handle_simple', side_effect=lambda path:f'/static/{path}')
        static.start()
        self.addCleanup(static.stop)
        self.owner = self.tenant.owner
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.owner)
        self.party = Party.objects.create(display_name='Draft Borrower')
        self.product_version = _seed_default_loan_products()[0]
        type(self.product_version).objects.filter(pk=self.product_version.pk).update(status='ACTIVE')

    @classmethod
    def get_test_schema_name(cls):
        return 'unified-directory'

    def accept(self, *, key='old-1', system='paper-register-a', amount=None, snapshot='scan-1', opened_on='1990-01-01'):
        value = document()
        value['source'].update(loan_id=key, system=system, snapshot_reference=snapshot)
        value['facts'].update(loan_number=key, borrower_name='Former customer', borrower_reference=None,
                              original_principal=amount,opened_on=opened_on)
        return accept_evidence(workspace_id=self.tenant.pk, actor=self.owner, document=value,
                               expected_sha256=digest(value), confirmed=True)

    def page(self, **query):
        return self.client.get(reverse('loans:pawn_loan_list'), query)

    def test_ordinary_and_historical_together_without_posting_or_unknown_zero(self):
        licence, series = self._configured_setup()
        self.client.post(reverse('loans:pawn_loan_create'), self._payload(licence, series))
        evidence = self.accept()
        counts = [model.objects.count() for model in (m.PawnLoan, m.PawnLoanEvent, m.HistoricalLoanImport)]
        response = self.page()
        self.assertEqual(response.context['page_obj'].paginator.count, 2)
        self.assertContains(response, 'Closed · Historical record')
        self.assertContains(response, 'Not known')
        self.assertContains(response, reverse('workspace_portability:archive_detail',
            kwargs={'workspace_slug':self.tenant.slug, 'evidence_id':evidence.public_id}))
        self.assertEqual(counts, [model.objects.count() for model in (m.PawnLoan, m.PawnLoanEvent, m.HistoricalLoanImport)])
        fragment = self.client.get(reverse('loans:pawn_loan_list'), {'q':'old-1'},
                                   HTTP_HX_REQUEST='true', HTTP_HX_TARGET='loan-results')
        self.assertContains(fragment, 'old-1')
        self.assertNotContains(fragment, 'id="loan-search-form"')
        self.assertIn('no-store', fragment['Cache-Control'])

    def test_scoped_snapshots_deduplicate_without_merging_reused_ids(self):
        namespace = document()['source']['namespace'].replace('-','')
        first = self.accept(system=f'legacy:{namespace}:jcl')
        latest = self.accept(system=f'legacy:{namespace}:jcl', snapshot='scan-2')
        other_book = self.accept(system=f'legacy:{namespace}:jsk')
        self.assertEqual(set(unadmitted_historical_records(self.tenant.pk).values_list('pk',flat=True)),
                         {latest.pk,other_book.pk})
        self.assertEqual(m.HistoricalLoanEvidence.objects.count(), 3)
        self.assertNotEqual(first.pk, latest.pk)

    def test_search_dates_modes_and_closed_status(self):
        self.accept(amount='1000.00')
        for query in ({'q':'old-1'}, {'q':'Former customer'}, {'state':'CLOSED'},
                      {'records':'historical'}, {'loan_date_from':'1990-01-01','loan_date_to':'1990-01-01'}):
            with self.subTest(query=query):
                self.assertEqual(self.page(**query).context['page_obj'].paginator.count,1)
        for query in ({'q':'absent'}, {'state':'ACTIVE'}, {'records':'ordinary'}, {'loan_date_from':'1990-01-02'}):
            with self.subTest(query=query):
                self.assertEqual(self.page(**query).context['page_obj'].paginator.count,0)

    def test_invalid_filters_never_fall_back_to_all_records(self):
        self.accept()
        for query in ({'records':'bogus'}, {'state':'bogus'}, {'borrower':'999999'},
                      {'loan_date_from':'bad'}, {'loan_date_from':'1990-02-01','loan_date_to':'1990-01-01'}):
            with self.subTest(query=query):
                response = self.page(**query)
                self.assertEqual(response.context['page_obj'].paginator.count,0)
                self.assertNotContains(response, 'old-1')
                self.assertContains(response, 'Check the filters')

    def test_local_mapping_filters_disclose_historical_exclusion(self):
        licence, series = self._configured_setup()
        self.accept()
        for query in ({'borrower':self.party.pk}, {'license':licence.pk}, {'series':series.pk}):
            with self.subTest(query=query):
                response = self.page(**query)
                self.assertEqual(response.context['page_obj'].paginator.count,0)
                self.assertContains(response, 'clear these filters')

    def test_unknown_original_date_does_not_match_either_date_bound(self):
        self.accept(opened_on=None)
        self.assertEqual(self.page().context['page_obj'].paginator.count,1)
        for query in ({'loan_date_from':'1989-01-01'},{'loan_date_to':'1991-01-01'}):
            with self.subTest(query=query):
                self.assertEqual(self.page(**query).context['page_obj'].paginator.count,0)

    def test_sql_pagination_preserves_filters_and_no_duplicates(self):
        for number in range(27):
            self.accept(key=f'old-{number}')
        first = self.page(records='historical',state='CLOSED')
        second = self.page(records='historical',state='CLOSED',page=2)
        a, b = first.context['directory_rows'], second.context['directory_rows']
        self.assertEqual((len(a),len(b)),(25,2))
        self.assertEqual(len({r['evidence'].pk for r in a+b}),27)
        self.assertContains(first, 'records=historical&amp;state=CLOSED&amp;page=2')

    def test_active_workspace_mismatch_is_rejected_before_browsing(self):
        with self.assertRaisesMessage(ValueError, 'active Workspace'):
            unadmitted_historical_records(self.tenant.pk+1)

    def test_restricted_role_and_http_search_do_not_expose_other_workspace(self):
        self.accept()
        other = Company.objects.create(name='Directory isolation',schema_name=uuid4().hex,
                                       owner=self.owner,creator=self.owner)
        value = document()
        value['source']['loan_id'] = 'foreign-secret'
        value['facts']['loan_number'] = 'foreign-secret'
        with without_workspace_context(),workspace_context(other.pk):
            Membership.objects.get_or_create(company=other,user=self.owner,defaults={'role':Role.objects.get(name='Owner')})
            accept_evidence(workspace_id=other.pk,actor=self.owner,document=value,
                            expected_sha256=digest(value),confirmed=True)
        role = connection.ops.quote_name('directory_'+uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS')
            cursor.execute(f'GRANT USAGE ON SCHEMA public TO {role}')
            cursor.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}')
        try:
            with connection.cursor() as cursor:
                cursor.execute(f'SET LOCAL ROLE {role}')
            self.assertEqual(list(unadmitted_historical_records(self.tenant.pk).values_list('source_id',flat=True)),['old-1'])
            response = self.page(q='foreign-secret')
            self.assertEqual(response.context['page_obj'].paginator.count,0)
            self.assertNotContains(response,'data-historical-record')
        finally:
            with connection.cursor() as cursor:
                cursor.execute('RESET ROLE')
                cursor.execute(f'DROP OWNED BY {role}')
                cursor.execute(f'DROP ROLE {role}')
