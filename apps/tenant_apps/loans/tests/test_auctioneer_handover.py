import copy
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.urls import reverse
from django.test import override_settings
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.testing import WorkspaceClient, WorkspaceTestCase
from apps.tenant_apps.loans.models import (AuctioneerHandover, AuctioneerHandoverRevision, PawnLoan, PawnCollateralItem,
    LoanLicense, LoanSeries, LoanPolicySnapshot, PawnLoanEvent)
from apps.tenant_apps.loans.services import auctioneer_handover as service
from apps.tenant_apps.loans.tests.factories import ensure_test_product_version
from apps.tenant_apps.party.models import Party


@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class AuctioneerHandoverTests(WorkspaceTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.owner = get_user_model().objects.create_user(username='handover-owner-' + uuid.uuid4().hex[:8])
        tenant.creator = tenant.owner
        tenant.name = 'Fictional handover workspace'

    def setUp(self):
        super().setUp()
        self.actor = self.tenant.owner
        role, _ = Role.objects.get_or_create(name='Owner')
        Membership.objects.get_or_create(user=self.actor, company=self.tenant, defaults={'role': role})
        self.start_active_trial()
        self.today = timezone.localdate()
        self.day = self.today - timedelta(days=400)
        self.license = LoanLicense.objects.create(workspace=self.tenant, name='Fictional licence', license_number='TEST-AH',
            issued_on=self.day - timedelta(days=100), expires_on=self.today + timedelta(days=300))
        self.series = LoanSeries.objects.create(workspace=self.tenant, license=self.license, name='Main', code='X')
        borrower = Party.objects.create(display_name='Fictional borrower')
        self.loan = PawnLoan.objects.create(workspace=self.tenant, license=self.license, series=self.series,
            product_version=ensure_test_product_version(self.tenant), borrower=borrower, loan_number='00001',
            state='ACTIVE', principal_amount='10000', monthly_interest_rate='2', loan_date=self.day,
            tenure_months=12, created_by=self.actor, updated_by=self.actor)
        LoanPolicySnapshot.objects.create(loan=self.loan, interest_method='SIMPLE', partial_month_method='FULL_MONTH',
            valuation_method='LATEST_APPRAISAL', rounding_method='PER_ACCRUAL_PERIOD')
        self.event('DISBURSAL', self.day, {'principal':'10000', 'interest':'0', 'fees':'0'})
        self.item = PawnCollateralItem.objects.create(workspace=self.tenant, loan=self.loan,
            description='Fictional gold ring', metal='GOLD', quantity=2, gross_weight='3', net_weight='2.8', purity_percentage='75')

    def event(self, kind, day, values):
        return PawnLoanEvent.objects.create(loan=self.loan, event_kind=kind, effective_date=day,
            payload={'values':values}, payload_fingerprint=uuid.uuid4().hex*2,
            idempotency_key=uuid.uuid4().hex, created_by=self.actor)

    def preview(self, handover=None):
        return service.plan(workspace=self.tenant, actor=self.actor, license_id=self.license.pk,
            loan_ids=[self.loan.pk], title='Fictional October list', auctioneer='Fictional auctioneer', handover=handover)

    def save_list(self, *, handover=None, token=None, included=None, notes='Reviewed original loan and vault custody.'):
        return service.save_review(workspace=self.tenant, actor=self.actor,
            token=token or service.review_token(self.preview(handover), self.actor, handover),
            included_ids=[self.loan.pk] if included is None else included, notes=notes)

    def test_initial_list_frozen_idempotent_and_does_not_initiate_auction(self):
        before = self.loan.loan_events.count()
        plan = self.preview()
        self.assertTrue(plan['rows'][0]['eligible'])
        token = service.review_token(plan, self.actor)
        revision = self.save_list(token=token)
        self.assertEqual(self.save_list(token=token).pk, revision.pk)
        self.assertEqual(revision.created_by, self.actor)
        self.assertEqual(Decimal(revision.snapshot['rows'][0]['principal']), Decimal('10000'))
        self.assertFalse(self.loan.auctions.exists())
        self.assertEqual(self.loan.loan_events.count(), before)
        with self.assertRaisesMessage(ValueError, 'different instructions'):
            self.save_list(token=token, notes='Different review')
        self.loan.borrower.display_name = 'Changed after saving'
        self.loan.borrower.save()
        revision.refresh_from_db()
        self.assertNotEqual(revision.snapshot['rows'][0]['borrower'], 'Changed after saving')

    def test_release_removes_loan_but_preserves_original_cohort_and_versions(self):
        original = self.save_list()
        self.event('RELEASE_RECEIPT', self.today, {'principal':'10000', 'interest':'0', 'fees':'0'})
        PawnLoan.objects.filter(pk=self.loan.pk).update(state='CLOSED')
        PawnCollateralItem.objects.filter(pk=self.item.pk).update(custody_state='RELEASED')
        preview = self.preview(original.handover)
        row = preview['rows'][0]
        self.assertFalse(row['eligible']); self.assertIn('state', row['changes'])
        self.assertEqual(Decimal(row['principal']), Decimal('0'))
        with self.assertRaisesMessage(ValueError, 'on hold'):
            self.save_list(handover=original.handover)
        revised = self.save_list(handover=original.handover, included=[], notes='All loans released; no remaining handover.')
        self.assertEqual(revised.number, 2)
        self.assertEqual(revised.snapshot['loan_ids'], original.snapshot['loan_ids'])
        self.assertFalse(revised.snapshot['rows'][0]['included'])
        original.refresh_from_db()
        self.assertTrue(original.snapshot['rows'][0]['included'])

    def test_repayment_change_is_visible_and_stale_confirmation_fails(self):
        original = self.save_list()
        token = service.review_token(self.preview(original.handover), self.actor, original.handover)
        self.event('REPAYMENT', self.today, {'principal':'100', 'interest':'0', 'fees':'0'})
        with self.assertRaisesMessage(ValueError, 'changed after preview'):
            self.save_list(token=token)
        row = self.preview(original.handover)['rows'][0]
        self.assertIn('principal', row['changes']); self.assertIn('activity', row['changes'])
        self.assertEqual(Decimal(row['principal']), Decimal('9900'))
        self.assertEqual(AuctioneerHandoverRevision.objects.count(), 1)

    def test_withheld_loan_stays_unticked_until_explicitly_selected(self):
        first = self.save_list()
        self.save_list(handover=first.handover, included=[], notes='Customer dispute; withhold pending review.')
        row = self.preview(first.handover)['rows'][0]
        self.assertTrue(row['eligible']); self.assertFalse(row['suggested'])
        third = self.save_list(handover=first.handover, notes='Dispute resolved; explicitly reselected.')
        self.assertTrue(third.snapshot['rows'][0]['included'])

    def test_current_missing_and_partial_custody_hold(self):
        PawnLoan.objects.filter(pk=self.loan.pk).update(loan_date=self.today)
        self.assertFalse(self.preview()['rows'][0]['eligible'])
        PawnLoan.objects.filter(pk=self.loan.pk).update(loan_date=self.today - timedelta(days=400))
        PawnCollateralItem.objects.filter(pk=self.item.pk).update(custody_state='RELEASED')
        self.assertFalse(self.preview()['rows'][0]['eligible'])
        with patch.object(service, 'get_pawn_loan_balance', side_effect=ValueError('Missing origin')):
            row = self.preview()['rows'][0]
        self.assertIsNone(row['principal']); self.assertFalse(row['eligible'])

    def test_exact_numbers_and_limits(self):
        self.assertEqual(service.resolve_numbers(self.tenant, self.license.pk, '00001'), [self.loan.pk])
        for numbers in ('1', '00001,00001', '', ','.join(str(i) for i in range(101))):
            with self.assertRaises(ValueError):
                service.resolve_numbers(self.tenant, self.license.pk, numbers)
        with self.assertRaises(ValueError):
            service.plan(workspace=self.tenant, actor=self.actor, license_id=self.license.pk, loan_ids=[self.loan.pk, self.loan.pk])

    def test_permission_actor_binding_and_write_gate(self):
        member = get_user_model().objects.create_user(username='handover-member')
        role, _ = Role.objects.get_or_create(name='Member')
        Membership.objects.create(company=self.tenant, user=member, role=role)
        token = service.review_token(self.preview(), self.actor)
        with self.assertRaises(PermissionDenied):
            service.save_review(workspace=self.tenant, actor=member, token=token, included_ids=[self.loan.pk], notes='No authority')
        from apps.tenancy.testing import expire_workspace_trial
        expire_workspace_trial(self.tenant, days_ago=30)
        with self.assertRaises(PermissionDenied):
            self.save_list(token=token)

    def test_expired_tampered_and_outside_selection_rejected(self):
        token = service.review_token(self.preview(), self.actor)
        with self.assertRaisesMessage(ValueError, 'invalid'):
            self.save_list(token=token + 'tamper')
        with patch('django.core.signing.time.time', return_value=__import__('time').time() + 3601):
            with self.assertRaisesMessage(ValueError, 'expired'):
                self.save_list(token=token)
        with self.assertRaisesMessage(ValueError, 'outside'):
            self.save_list(included=[self.loan.pk + 999])
        with self.assertRaises(ValueError):
            self.save_list(notes='')

    def test_ui_preview_confirm_history_print_csv_and_csrf(self):
        client = self.make_workspace_client(); client.force_login(self.actor)
        url = reverse('workspace_loans:auctioneer_handovers', args=[self.tenant.slug])
        self.assertContains(client.get(url), 'Auctioneer handover lists')
        response = client.post(url, dict(action='preview', license=self.license.pk, title='Test list', auctioneer='Test firm', numbers='00001'))
        self.assertContains(response, 'Save reviewed list')
        data = dict(action='save', token=response.context['token'], included=[self.loan.pk], notes='Reviewed the loan.', reviewed='yes')
        csrf = WorkspaceClient(self.tenant, enforce_csrf_checks=True); csrf.force_login(self.actor)
        self.assertEqual(csrf.post(url, data).status_code, 403)
        self.assertEqual(client.post(url, data).status_code, 302)
        revision = AuctioneerHandoverRevision.objects.get()
        detail = reverse('workspace_loans:auctioneer_handover_detail', args=[self.tenant.slug, revision.handover_id])
        self.assertContains(client.get(detail), 'Reconcile against version 1')
        export = reverse('workspace_loans:auctioneer_handover_export', args=[self.tenant.slug, revision.handover_id, revision.pk])
        self.assertContains(client.get(export), '00001')
        self.assertIn('no-store', client.get(export)['Cache-Control'])
        csv = client.get(export + '?format=csv')
        self.assertContains(csv, '00001')
        self.assertIn('text/csv', csv['Content-Type'])
        with patch.object(service, 'digest', return_value='corrupt'):
            self.assertEqual(client.get(export).status_code, 409)

    def test_sql_immutability_sequence_cohort_and_rls(self):
        revision = self.save_list(); handover = revision.handover
        for model, obj in ((AuctioneerHandover, handover), (AuctioneerHandoverRevision, revision)):
            with self.assertRaises(DatabaseError), transaction.atomic():
                model.objects.filter(pk=obj.pk).update(created_by=self.actor)
            with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(f'DELETE FROM {model._meta.db_table} WHERE id=%s', [obj.pk])
        wrong = copy.deepcopy(revision.snapshot); wrong['rows'] = []
        with self.assertRaises(DatabaseError), transaction.atomic():
            AuctioneerHandoverRevision.objects.bulk_create([AuctioneerHandoverRevision(workspace=self.tenant,
                handover=handover, number=2, snapshot=wrong, snapshot_sha256='a'*64, request_sha256='b'*64,
                request_key='wrong-cohort', created_by=self.actor)])
        role = 'handover_rls_' + uuid.uuid4().hex[:10]
        other = Company.objects.create(name='Other handover', schema_name=role, owner=self.actor, creator=self.actor)
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(f'CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS')
            cursor.execute(f'GRANT USAGE ON SCHEMA public TO {role}')
            cursor.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}')
            cursor.execute(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}')
            cursor.execute(f'SET LOCAL ROLE {role}')
            cursor.execute("SELECT set_config('app.workspace_id', %s, true)", [str(other.pk)])
            self.assertFalse(AuctioneerHandover.objects.exists()); self.assertFalse(AuctioneerHandoverRevision.objects.exists())
            with self.assertRaises(DatabaseError), transaction.atomic():
                AuctioneerHandover.objects.bulk_create([AuctioneerHandover(workspace=other, license=self.license,
                    title='Forged', auctioneer='Other', loan_ids=[self.loan.pk], request_key='forged', created_by=self.actor)])
            with self.assertRaises(DatabaseError), transaction.atomic():
                AuctioneerHandoverRevision.objects.bulk_create([AuctioneerHandoverRevision(workspace=other, handover=handover,
                    number=2, snapshot=revision.snapshot, snapshot_sha256='a'*64, request_sha256='b'*64,
                    request_key='foreign-parent', created_by=self.actor)])
            cursor.execute("SELECT set_config('app.workspace_id', '', true)")
            self.assertFalse(AuctioneerHandover.objects.exists()); self.assertFalse(AuctioneerHandoverRevision.objects.exists())
            cursor.execute('RESET ROLE'); cursor.execute(f'DROP OWNED BY {role}'); cursor.execute(f'DROP ROLE {role}')

    def test_csv_formula_protection(self):
        from apps.tenant_apps.loans.web.auctioneer_handover import csv_cell
        for value in ('=HYPERLINK("bad")', ' +SUM(1)', '@SUM(1)', '-10', '\t=1'):
            self.assertTrue(csv_cell(value).startswith("'"))
        self.assertEqual(csv_cell('Normal borrower'), 'Normal borrower')

    def test_newer_version_invalidates_old_preview_and_db_rejects_gap(self):
        first = self.save_list()
        old = service.review_token(self.preview(first.handover), self.actor, first.handover)
        self.save_list(handover=first.handover)
        with self.assertRaisesMessage(ValueError, 'changed after preview'):
            self.save_list(token=old)
        with self.assertRaises(DatabaseError), transaction.atomic():
            AuctioneerHandoverRevision.objects.bulk_create([AuctioneerHandoverRevision(workspace=self.tenant,
                handover=first.handover, number=4, snapshot=first.snapshot, snapshot_sha256='a'*64,
                request_sha256='b'*64, request_key='gap', created_by=self.actor)])

    def test_notices_stay_independent_and_need_review(self):
        from apps.tenant_apps.loans.models import PawnLoanAuction
        auction = PawnLoanAuction.objects.create(workspace=self.tenant, loan=self.loan, auction_number='AUC-TEST-1',
            attempt_number=1, request_key='test-auction', notice_date=self.today,
            scheduled_date=self.today + timedelta(days=60), created_by=self.actor)
        first = self.save_list()
        row = first.snapshot['rows'][0]
        self.assertEqual(row['auction_id'], auction.pk)
        self.assertIn('Prepare and review the statutory auction catalogue.', row['readiness'])
        auction.refresh_from_db()
        self.assertEqual(auction.state, 'INITIATED')
