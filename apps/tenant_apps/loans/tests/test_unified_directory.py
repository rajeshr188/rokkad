"""The common directory is read-only; archive claims are never financial debt."""
from unittest.mock import patch
from uuid import uuid4

from django.test import override_settings
from django.urls import reverse
from django.db import connection, transaction, DatabaseError
from django.utils import timezone

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

    def accept(self, *, key='old-1', system='paper-register-a', amount=None, snapshot='scan-1', opened_on='1990-01-01', name='Former customer'):
        value = document()
        value['source'].update(loan_id=key, system=system, snapshot_reference=snapshot)
        value['facts'].update(loan_number=key, borrower_name=name, borrower_reference=None,
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
        self.assertContains(response, 'Closed claim \u00b7 Source record')
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

    def test_matching_old_snapshot_cannot_reappear_after_nonmatching_revision(self):
        self.accept(name='Old matching-only caption')
        newest = self.accept(name='Different revised caption', snapshot='revision-2')
        self.assertEqual(self.page(q='matching-only').context['page_obj'].paginator.count, 0)
        response = self.page(q='Different revised')
        self.assertEqual([r['evidence'].pk for r in response.context['directory_rows']], [newest.pk])

    def test_broad_candidate_fallback_preserves_all_pages_and_snapshot_rules(self):
        from apps.tenant_apps.loans.services.archive_contract import review_document
        rows = []
        for index in range(503):
            value = document(); key = f'broad-{index:04d}'
            value['source'].update(loan_id=key, system='broad-book')
            value['facts'].update(loan_number=key, borrower_name='Broad source name', borrower_reference=None)
            rows.append(m.HistoricalLoanEvidence(workspace=self.tenant, source_namespace=value['source']['namespace'],
                source_system='broad-book', source_id=key, source_sha256=digest(value), document=value,
                review=review_document(value), accepted_by=self.owner))
        m.HistoricalLoanEvidence.objects.bulk_create(rows)
        first = self.page(q='Broad source')
        last = self.page(q='Broad source', page=21)
        self.assertEqual(first.context['page_obj'].paginator.count, 503)
        self.assertEqual(len(last.context['directory_rows']), 3)
        self.assertEqual(self.page().context['page_obj'].paginator.count, 503)
        self.assertEqual(len(self.page(page=21).context['directory_rows']), 3)
        with patch('apps.tenant_apps.loans.selectors.directory.ARCHIVE_CANDIDATE_LIMIT', 1):
            self.assertEqual(self.page(q='Broad source').context['page_obj'].paginator.count, 503)

    def test_results_fragment_skips_readiness_but_history_restore_still_checks_setup(self):
        self.accept()
        with patch('apps.tenant_apps.loans.web.pawn_reads.get_pawn_draft_readiness', side_effect=AssertionError('Unneeded setup')):
            response = self.client.get(reverse('loans:pawn_loan_list'), {'q':'old-1'},
                HTTP_HX_REQUEST='true', HTTP_HX_TARGET='loan-results')
            self.assertEqual(response.status_code, 200)
        with patch('apps.tenant_apps.loans.web.pawn_reads.get_pawn_draft_readiness', return_value={'ready':True}) as readiness:
            self.client.get(reverse('loans:pawn_loan_list'), {}, HTTP_HX_REQUEST='true', HTTP_HX_TARGET='loan-results',
                HTTP_HX_HISTORY_RESTORE_REQUEST='true')
            readiness.assert_called_once()

    def admit_position(self, *, original_date='1990-01-01', number='Imported-closed-1', inconsistent_source=False):
        from apps.tenant_apps.data_portability.models import PartyIdentity, SourceIdentity
        from apps.tenant_apps.loans.services.closed_position import preview_closed_position, admit_closed_position
        licence, series = self._configured_setup()
        value = document(); system = 'accepted-source-book'
        value['source'].update(loan_id='original-external-id', system=system)
        reference = dict(system=system, id='customer-1')
        value['facts'].update(loan_number=number, borrower_name='Original source customer',
            borrower_reference=reference, original_principal=None, reported_balance='0', opened_on=original_date)
        evidence = accept_evidence(workspace_id=self.tenant.pk, actor=self.owner, document=value,
            expected_sha256=digest(value), confirmed=True)
        party_identity, _ = PartyIdentity.objects.get_or_create(workspace=self.tenant, party=self.party)
        SourceIdentity.objects.create(workspace=self.tenant, identity=party_identity, source_system=system,
            external_id='customer-1', accepted_digest='a'*64, local_digest='b'*64)
        position = dict(profile='loan-closed-position/1',
            source={k:value['source'][k] for k in ('namespace','system','loan_id')},
            loan=dict(number=number, borrower_reference=reference, original_date=original_date,
                closed_on=value['facts']['closed_on'], original_principal=None, monthly_rate=None, tenure_months=None),
            position=dict(state='CLOSED', as_of=timezone.localdate().isoformat(), currency='INR',
                principal='0', interest='0', fees='0', custody='RETURNED_TO_BORROWER', basis='OWNER_CLOSED_POSITION',
                evidence_reference='Owner checked closed position and returned collateral.'),
            earlier_history='UNAVAILABLE', retained_evidence=value)
        args = dict(workspace_id=self.tenant.pk, actor=self.owner, borrower_id=self.party.pk, series_id=series.pk,
            evidence_id=evidence.public_id, document=position)
        if inconsistent_source:
            # Deliberately bypass pure validation to model an inconsistent FK.
            # Browsing must still check source identity rather than trust the FK.
            from apps.tenant_apps.loans.services import closed_position
            workspace, selected_series, accepted = closed_position._prepare(**args)
            accepted['position']['source']['system'] = 'unrelated-source-book'
            with patch.object(closed_position, 'read_position', return_value={}):
                loan, _ = closed_position._write(workspace, selected_series, self.owner, accepted)
            return loan, evidence
        _, token = preview_closed_position(**args)
        loan, _ = admit_closed_position(**args, review_token=token, confirmed=True)
        return loan, evidence

    def test_admitted_closed_position_is_one_ordinary_card_and_searches_original_source_aliases(self):
        loan, evidence = self.admit_position()
        for query in ({'q':loan.loan_number}, {'q':'original-external-id'}, {'q':'Original source customer'},
                      {'borrower_q':'Original source customer'}, {'borrower':self.party.pk}, {'state':'CLOSED'}):
            with self.subTest(query=query):
                response = self.page(**query)
                self.assertEqual(response.context['page_obj'].paginator.count, 1)
                self.assertEqual(response.context['directory_rows'][0]['loan'].pk, loan.pk)
                self.assertNotContains(response, 'data-historical-record')
        self.assertEqual(self.page(records='historical').context['page_obj'].paginator.count, 0)
        response = self.client.get(reverse('workspace_portability:archive_list', kwargs={'workspace_slug':self.tenant.slug}))
        self.assertContains(response, 'Retained source documents')
        self.assertContains(response, 'Linked ordinary loan')
        self.assertTrue(m.HistoricalLoanEvidence.objects.filter(pk=evidence.pk).exists())

    def test_running_loan_precedes_newly_admitted_old_closed_record_without_changing_timestamps(self):
        closed, _ = self.admit_position()
        licence, series = closed.license, closed.series
        response = self.client.post(reverse('loans:pawn_loan_create'), self._payload(licence, series))
        self.assertEqual(response.status_code, 302)
        draft = m.PawnLoan.objects.exclude(pk=closed.pk).get()
        before = {l.pk:l.created_at for l in m.PawnLoan.objects.all()}
        self.accept(opened_on=None)
        result = self.page().context['directory_rows']
        self.assertEqual([r['kind'] for r in result], ['ordinary','ordinary','historical'])
        self.assertEqual([r['loan'].pk for r in result[:2]], [draft.pk,closed.pk])
        self.assertEqual(before, {l.pk:l.created_at for l in m.PawnLoan.objects.all()})

    def test_source_search_fields_are_generated_nullable_and_immutable(self):
        evidence = self.accept(opened_on=None)
        evidence.refresh_from_db()
        self.assertEqual((evidence.search_loan_number, evidence.search_borrower_name, evidence.search_opened_on),
            ('old-1','Former customer',None))
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('UPDATE loans_historicalloanevidence SET search_loan_number=%s WHERE id=%s', ['fake', evidence.pk])
        evidence.refresh_from_db(); self.assertEqual(evidence.source_sha256, digest(evidence.document))

    def test_invalid_legacy_binding_cannot_hide_behind_an_unrelated_origin(self):
        loan, _ = self.admit_position()
        origin = loan.historical_import
        invalid = self.accept(key=origin.source_id, system=f'legacy:{origin.source_namespace.hex}:public')
        self.assertIn(invalid.pk, unadmitted_historical_records(self.tenant.pk).values_list('pk',flat=True))
        self.assertEqual(self.page(q=origin.source_id).context['page_obj'].paginator.count, 2)

    def test_inconsistent_closed_origin_fk_does_not_hide_unbound_source(self):
        loan, evidence = self.admit_position(inconsistent_source=True)
        self.assertIn(evidence.pk, unadmitted_historical_records(self.tenant.pk).values_list('pk', flat=True))
        self.assertEqual(self.page(q=loan.loan_number).context['page_obj'].paginator.count, 2)

    def test_older_financial_import_number_aliases_remain_searchable(self):
        licence, series = self._configured_setup()
        self.client.post(reverse('loans:pawn_loan_create'), self._payload(licence, series))
        loan = m.PawnLoan.objects.get()
        value = {'profile':'old-history', 'loan':{'number':'Former-number', 'book_reference':'Book-alias'},
            'source_loan':{'loan_number':'Legacy-number'}, 'review':{'source':{'number':'Reviewed-number'}}}
        m.HistoricalLoanImport.objects.create(workspace=self.tenant, loan=loan,
            source_namespace=uuid4(), source_id='Earlier-external-id', source_sha256=digest(value),
            document=value, references={}, imported_by=self.owner)
        for alias in ('Former-number','Book-alias','Legacy-number','Reviewed-number','Earlier-external-id'):
            with self.subTest(alias=alias):
                result = self.page(q=alias).context['page_obj']
                self.assertEqual(result.paginator.count, 1)
                self.assertEqual(result.object_list[0]['loan'].pk, loan.pk)
                from apps.tenant_apps.loans.filters import PawnLoanFilter
                with patch.object(PawnLoanFilter, 'IMPORT_ALIAS_CANDIDATE_LIMIT', 0):
                    complete = self.page(q=alias).context['page_obj']
                self.assertEqual(complete.paginator.count, result.paginator.count)
                self.assertEqual(complete.object_list[0]['loan'].pk, loan.pk)

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
