import hashlib
import io
import uuid
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

import fitz
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection, transaction
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from reportlab.pdfgen import canvas

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.models import PawnLoanAuction
from apps.tenant_apps.loans.models.statutory import StatutoryAuctionNotice, StatutoryNoticeEvidence
from apps.tenant_apps.loans.services.statutory_notices import (
    StatutoryNoticeError, prepare_catalogue, record_handling, auction_readiness,
)
from apps.tenant_apps.loans.services.pawn_auctions import PawnAuctionError, start_pawn_loan_auction, complete_pawn_loan_auction
from . import test_collateral_reappraisal as loan_fixtures


@contextmanager
def on_day(value):
    with patch('django.utils.timezone.now', return_value=timezone.make_aware(datetime.combine(value, time(10)))):
        yield


def upload():
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(50, 750, 'Fictional postal / permission evidence for tests only')
    pdf.save()
    return SimpleUploadedFile('evidence.pdf', buffer.getvalue(), content_type='application/pdf')


@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class StatutoryNoticeTests(WorkspaceTestCase):
    make_loan = loan_fixtures.CollateralReappraisalTests.make_loan

    @classmethod
    def setup_tenant(cls, tenant):
        tenant.owner = get_user_model().objects.create_user(username='stat-owner-' + uuid.uuid4().hex[:8])
        tenant.creator = tenant.owner
        tenant.name = 'Statutory notice test'

    def setUp(self):
        super().setUp()
        self.actor = self.tenant.owner
        role, _ = Role.objects.get_or_create(name='Owner')
        Membership.objects.get_or_create(user=self.actor, company=self.tenant, defaults={'role': role})
        self.start_active_trial()
        from apps.tenancy.testing import set_workspace_trial_end
        set_workspace_trial_end(self.tenant, ends_at=timezone.now() + timedelta(days=365))
        self.day = timezone.localdate()
        # Auction servicing now validates the origin: use a real approved payout.
        self.make_loan(method='LATEST_APPRAISAL', age_days=400)
        self.loan.borrower.display_name = 'Fictional Pawner'
        self.loan.borrower.save(update_fields=['display_name'])
        self.auction = PawnLoanAuction.objects.create(workspace=self.tenant, loan=self.loan, auction_number='AUC-T00001-01',
            attempt_number=1, request_key='auction', notice_date=self.day, scheduled_date=self.day + timedelta(days=60), created_by=self.actor)
        self.catalogue = dict(request_key='catalogue', business_name='Fictional lender', business_address='1 Fictional Road, Tamil Nadu',
            borrower_address='2 Fictional Road, Tamil Nadu', auctioneer_name='Fictional auctioneer', auctioneer_reference='TEST-APPROVAL',
            sale_time='10:00', sale_place='Fictional auction hall', reviewed=True)

    def prepare(self):
        return prepare_catalogue(self.auction.pk, data=self.catalogue, actor=self.actor)

    def event(self, kind, offset=0, **details):
        data = dict(request_key=uuid.uuid4().hex, occurred_on=self.day + timedelta(days=offset), notes='Fictional evidence', **details)
        with on_day(self.day + timedelta(days=offset)):
            return record_handling(self.auction.pk, kind=kind, data=data, actor=self.actor,
                attachment=upload() if kind not in {'PRINTED', 'WITHDRAWN'} else None)

    def post(self, offset=0):
        self.event('PRINTED')
        return self.event('POSTED', offset, article_number='TEST123456IN', postal_service='SPEED_REGISTERED_POD', posted_by='Fictional auctioneer')

    def acknowledge(self):
        self.post()
        self.event('ACKNOWLEDGED', 3, delivered_on=self.day + timedelta(days=2))

    def review(self, offset=15, **overrides):
        details = dict(authority_reference='TEST authority permission', permission_expires_on=self.auction.scheduled_date,
            first_publication_on=self.day + timedelta(days=7), second_publication_on=self.day + timedelta(days=10),
            police_sent_on=self.day + timedelta(days=7), legal_review_reference='Fictional current-rule review',
            permission_checked=True, publication_checked=True, authority_checked=True, valuation_checked=True, service_checked=True)
        details.update(overrides)
        return self.event('REVIEWED', offset, **details)

    def test_prepare_preview_has_no_rows_and_issue_is_idempotent_frozen_pdf(self):
        pdf = prepare_catalogue(self.auction.pk, data=self.catalogue, actor=self.actor, preview=True)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertFalse(StatutoryAuctionNotice.objects.exists())
        notice = self.prepare()
        self.loan.borrower.display_name = 'Later name'
        self.loan.borrower.save()
        self.assertEqual(self.prepare().pk, notice.pk)
        self.assertEqual(notice.snapshot['borrower_name'], 'Fictional Pawner')
        with notice.artifact.open('rb') as handle:
            content = handle.read()
        self.assertEqual(hashlib.sha256(content).hexdigest(), notice.artifact_sha256)
        with fitz.open(stream=content, filetype='pdf') as doc:
            self.assertIn(self.loan.loan_number, ''.join(page.get_text() for page in doc))
        with self.assertRaises(StatutoryNoticeError):
            prepare_catalogue(self.auction.pk, data={**self.catalogue, 'sale_place': 'Changed'}, actor=self.actor)

    def test_acknowledged_route_allows_only_advertised_date_and_start(self):
        self.prepare()
        self.acknowledge()
        self.review()
        with on_day(self.auction.scheduled_date - timedelta(days=1)):
            self.assertFalse(auction_readiness(self.auction).ready)
        with on_day(self.auction.scheduled_date):
            self.assertTrue(auction_readiness(self.auction).ready)
            started = start_pawn_loan_auction(self.auction.pk, actor=self.actor)
            self.assertEqual(started.state, 'IN_PROGRESS')
        with on_day(self.auction.scheduled_date + timedelta(days=1)):
            self.assertFalse(auction_readiness(self.auction).ready)

    def test_digital_sent_cannot_clear_missing_statutory_notice(self):
        from apps.tenant_apps.loans.services.pawn_notices import create_pawn_loan_notice
        from apps.tenant_apps.notify_v2.models import NotificationJob
        self.loan.borrower.primary_email = 'fictional@example.com'
        self.loan.borrower.save()
        notice = create_pawn_loan_notice(self.loan.pk, notice_kind='AUCTION_NOTICE', channel='EMAIL',
            request_key='digital', source_auction_id=self.auction.pk, actor=self.actor, dispatch_due=False)
        NotificationJob.objects.filter(pk=notice.notification_job_id).update(status='SENT')
        with on_day(self.auction.scheduled_date), self.assertRaisesMessage(PawnAuctionError, 'statutory auction catalogue'):
            start_pawn_loan_auction(self.auction.pk, actor=self.actor)

    def test_existing_in_progress_auction_cannot_complete_without_review(self):
        PawnLoanAuction.objects.filter(pk=self.auction.pk).update(state='IN_PROGRESS')
        with on_day(self.auction.scheduled_date), patch('apps.tenant_apps.loans.services.pawn_auctions._money', return_value=1000), self.assertRaisesMessage(PawnAuctionError, 'Statutory notice'):
            complete_pawn_loan_auction(self.auction.pk, actor=self.actor, recovery_amount='1000', buyer_name='Buyer')

    def test_return_route_and_late_handling_are_retained_but_fail_closed(self):
        notice = self.prepare()
        self.post()
        self.event('RETURNED', 3)
        with self.assertRaises(StatutoryNoticeError):
            self.event('ACKNOWLEDGED', 4, delivered_on=self.day + timedelta(days=2))
        self.event('REFERRED', 5, officer='Fictional VAO', officer_received_on=self.day + timedelta(days=6), reference='TEST-REF')
        self.event('OFFICER_RECEIVED', 6)
        self.event('CERTIFIED', 12, affixed_on=self.day + timedelta(days=10), certified_on=self.day + timedelta(days=11))
        self.review()
        with on_day(self.auction.scheduled_date):
            self.assertTrue(auction_readiness(self.auction).ready)
        self.assertEqual(notice.evidence.count(), 7)

    def test_late_posting_is_recorded_without_misleading_readiness(self):
        self.prepare()
        self.post(offset=16)  # 44 days before sale
        self.event('ACKNOWLEDGED', 18, delivered_on=self.day + timedelta(days=17))
        with self.assertRaisesMessage(StatutoryNoticeError, '45 days'):
            self.review(offset=20)

    def test_exact_45_day_postal_boundary_is_accepted(self):
        self.prepare()
        self.post(offset=15)
        self.event('ACKNOWLEDGED', 18, delivered_on=self.day + timedelta(days=17))
        self.review(offset=20)
        with on_day(self.auction.scheduled_date):
            self.assertTrue(auction_readiness(self.auction).ready)

    def test_late_referral_is_preserved_and_blocks_review(self):
        self.prepare()
        self.post()
        self.event('RETURNED', 2)
        self.event('REFERRED', 10, officer='VAO', officer_received_on=self.day + timedelta(days=10), reference='REF')
        self.event('OFFICER_RECEIVED', 10)
        self.event('CERTIFIED', 13, affixed_on=self.day + timedelta(days=11), certified_on=self.day + timedelta(days=12))
        with self.assertRaisesMessage(StatutoryNoticeError, 'seven-day'):
            self.review()

    def test_review_requires_proof_and_ten_clear_publication_days(self):
        self.prepare()
        self.post()
        with self.assertRaisesMessage(StatutoryNoticeError, 'proof of delivery'):
            self.review()
        self.event('ACKNOWLEDGED', 3, delivered_on=self.day + timedelta(days=2))
        with self.assertRaisesMessage(StatutoryNoticeError, 'ten clear'):
            self.review(offset=50, second_publication_on=self.day + timedelta(days=50))

    def test_future_dates_invalid_file_and_missing_receipt_rejected(self):
        self.prepare()
        with self.assertRaises(StatutoryNoticeError):
            record_handling(self.auction.pk, kind='PRINTED', data={'request_key': 'future', 'occurred_on': self.day + timedelta(days=1), 'notes': 'test'}, actor=self.actor)
        self.event('PRINTED')
        data = dict(request_key='post', occurred_on=self.day, notes='test', article_number='TEST', postal_service='RPAD', posted_by='Auctioneer')
        with self.assertRaises(ValidationError):
            record_handling(self.auction.pk, kind='POSTED', data=data, actor=self.actor)
        with self.assertRaises(StatutoryNoticeError):
            record_handling(self.auction.pk, kind='POSTED', data=data, actor=self.actor,
                attachment=SimpleUploadedFile('fake.pdf', b'<script>test</script>'))

    def test_withdrawal_invalidates_review_and_requires_restart(self):
        self.prepare()
        self.acknowledge()
        self.review()
        self.event('WITHDRAWN', 20)
        with on_day(self.auction.scheduled_date):
            self.assertFalse(auction_readiness(self.auction).ready)
            with self.assertRaises(PawnAuctionError):
                start_pawn_loan_auction(self.auction.pk, actor=self.actor)

    def test_service_duplicate_request_and_immutable_sql(self):
        notice = self.prepare()
        data = dict(request_key='printed', occurred_on=self.day, notes='Actually printed')
        first = record_handling(self.auction.pk, kind='PRINTED', data=data, actor=self.actor)
        second = record_handling(self.auction.pk, kind='PRINTED', data=data, actor=self.actor)
        self.assertEqual(first.pk, second.pk)
        with self.assertRaises(StatutoryNoticeError):
            record_handling(self.auction.pk, kind='PRINTED', data={**data, 'notes': 'Changed'}, actor=self.actor)
        for model, pk in ((StatutoryAuctionNotice, notice.pk), (StatutoryNoticeEvidence, first.pk)):
            with self.assertRaises(DatabaseError), transaction.atomic():
                model.objects.filter(pk=pk).update(request_key='overwrite')
            with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(f'DELETE FROM {model._meta.db_table} WHERE id=%s', [pk])

    def test_admin_ui_private_pdf_member_denied_and_no_post_on_get(self):
        client = self.make_workspace_client()
        client.force_login(self.actor)
        guide_url = reverse('workspace_loans:statutory_guide', args=[self.tenant.slug])
        self.assertContains(client.get(guide_url), 'Prescribed-document coverage')
        url = reverse('workspace_loans:statutory_auction_notice', args=[self.tenant.slug, self.auction.pk])
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Prepare the auction catalogue')
        self.assertFalse(StatutoryAuctionNotice.objects.exists())
        response = client.post(url, {**self.catalogue, 'operation': 'issue'})
        self.assertEqual(response.status_code, 302)
        self.assertContains(client.get(url + '?step=POSTED'), 'Postal article')
        pdf_url = reverse('workspace_loans:statutory_auction_catalogue', args=[self.tenant.slug, self.auction.pk])
        response = client.get(pdf_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        member = get_user_model().objects.create_user(username='stat-member')
        role, _ = Role.objects.get_or_create(name='Member')
        Membership.objects.create(user=member, company=self.tenant, role=role)
        client.force_login(member)
        self.assertEqual(client.get(pdf_url).status_code, 403)
        with self.assertRaises((PawnAuctionError, PermissionDenied)):
            prepare_catalogue(self.auction.pk, data=self.catalogue, actor=member)

    def test_cross_workspace_urls_and_csrf_cannot_record_evidence(self):
        from apps.tenancy.testing import WorkspaceClient
        client = WorkspaceClient(self.tenant, enforce_csrf_checks=True)
        client.force_login(self.actor)
        url = reverse('workspace_loans:statutory_auction_notice', args=[self.tenant.slug, self.auction.pk])
        self.assertEqual(client.post(url, self.catalogue).status_code, 403)
        self.assertFalse(StatutoryAuctionNotice.objects.exists())
        self.prepare()
        other = Company.objects.create(name='Other URL test', schema_name='stat-url-' + uuid.uuid4().hex[:8], owner=self.actor, creator=self.actor)
        from apps.tenancy.testing import start_workspace_trial
        # A client cannot use a valid auction ID under a different Workspace path.
        from apps.tenancy.context import without_workspace_context
        with without_workspace_context():
            start_workspace_trial(other)
            member_role, _ = Role.objects.get_or_create(name='Owner')
            with workspace_context(other.pk):
                Membership.objects.get_or_create(user=self.actor, company=other, defaults={'role':member_role})
            foreign_url = reverse('workspace_loans:statutory_auction_catalogue', args=[other.slug, self.auction.pk])
            self.assertEqual(client.get(foreign_url, HTTP_HOST='testserver').status_code, 404)

    def test_expired_workspace_cannot_add_statutory_evidence(self):
        self.prepare()
        from apps.tenancy.testing import expire_workspace_trial
        expire_workspace_trial(self.tenant, days_ago=30)
        with self.assertRaises(PermissionDenied):
            self.event('PRINTED')

    def test_rls_and_parent_scope_under_restricted_role(self):
        notice = self.prepare()
        self.event('PRINTED')
        # A separate atomic transaction's local role cannot escape this test.
        name = 'stat_rls_' + uuid.uuid4().hex[:12]
        other = Company.objects.create(name='Other statutory test', schema_name=name, owner=self.actor, creator=self.actor)
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(f'CREATE ROLE {name} NOLOGIN NOSUPERUSER NOBYPASSRLS')
            cursor.execute(f'GRANT USAGE ON SCHEMA public TO {name}')
            cursor.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {name}')
            cursor.execute(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {name}')
            cursor.execute(f'SET LOCAL ROLE {name}')
            cursor.execute("SELECT set_config('app.workspace_id', %s, true)", [str(other.pk)])
            self.assertFalse(StatutoryAuctionNotice.objects.exists())
            self.assertFalse(StatutoryNoticeEvidence.objects.exists())
            self.assertEqual(StatutoryNoticeEvidence.objects.all().update(request_key='other'), 0)
            with self.assertRaises(DatabaseError), transaction.atomic():
                StatutoryNoticeEvidence.objects.bulk_create([StatutoryNoticeEvidence(workspace=other, notice=notice,
                    kind='PRINTED', occurred_on=self.day, details={'notes':'test'}, request_key='spoof', created_by=self.actor)])
            cursor.execute("SELECT set_config('app.workspace_id', '', true)")
            self.assertFalse(StatutoryAuctionNotice.objects.exists())
            cursor.execute('RESET ROLE')
            cursor.execute(f'DROP OWNED BY {name}')
            cursor.execute(f'DROP ROLE {name}')
