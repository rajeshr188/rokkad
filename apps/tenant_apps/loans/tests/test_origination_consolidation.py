from copy import deepcopy
from datetime import date
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import connection, transaction, DatabaseError
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context, without_workspace_context
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.services.series_reservations import preview_register_reservation, confirm_register_reservation
from apps.tenant_apps.loans.services.license_series import configure_sequence, create_series, create_license
from apps.tenant_apps.loans.services.borrower_corrections import preview_borrower_correction, record_borrower_correction
from apps.tenant_apps.loans.services.recorded_history import new_recording_intent, preview_recorded_history, admit_recorded_history
from apps.tenant_apps.loans.tests.test_continuation_admissions import AdmissionFixture
from apps.tenant_apps.loans.tests.test_settlement_continuation import on
from apps.tenant_apps.loans.tests import test_recorded_origination as origins, test_recorded_history as histories


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class RegisterReservationTests(WorkspaceTestCase):
    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history

    def setUp(self):
        self.prepare_history()
        self.series.code = "AA"
        self.series.save()
        configure_sequence(series=self.series, document_kind="PAWN_LOAN", prefix="AA", width=5, actor=self.actor)
        self.values = dict(actor=self.actor, kind="PAWN_LOAN", last_used=5000, reference="Original AA register through AA05000")

    def test_signed_reservation_no_loans_and_idempotent_confirmation(self):
        count = m.PawnLoan.objects.count()
        review, token = preview_register_reservation(self.series.pk, **self.values)
        self.assertEqual(review["next_number"], "AA05001")
        self.seq.refresh_from_db()
        self.assertEqual(self.seq.next_number, 1)
        self.assertTrue(confirm_register_reservation(self.series.pk, **self.values, review_token=token, confirmed=True))
        self.assertFalse(confirm_register_reservation(self.series.pk, **self.values, review_token=token, confirmed=True))
        self.assertEqual(m.PawnLoan.objects.count(), count)
        from apps.tenant_apps.loans.services.number_allocation import allocate_pawn_loan_number
        self.assertEqual(allocate_pawn_loan_number(series=self.series, actor=self.actor).value, "AA05001")

    def test_changed_format_actor_reference_and_forged_confirmation_are_rejected(self):
        _, token = preview_register_reservation(self.series.pk, **self.values)
        for changed in (dict(reference="Another register"), dict(last_used=4999)):
            with self.assertRaises(ValueError):
                confirm_register_reservation(self.series.pk, **dict(self.values, **changed), review_token=token, confirmed=True)
        with self.assertRaises(ValueError):
            confirm_register_reservation(self.series.pk, **self.values, review_token="forged", confirmed=True)
        with self.assertRaises(ValueError):
            confirm_register_reservation(self.series.pk, **self.values, review_token=token)
        with self.assertRaises(PermissionDenied):
            preview_register_reservation(self.series.pk, **dict(self.values, actor=None))
        configure_sequence(series=self.series, document_kind="PAWN_LOAN", prefix="BB", width=5, actor=self.actor)
        with self.assertRaisesMessage(ValueError, "facts changed"):
            confirm_register_reservation(self.series.pk, **self.values, review_token=token, confirmed=True)

    def test_counter_change_expired_review_and_cross_workspace_are_rejected(self):
        with patch("django.core.signing.time.time", return_value=0):
            _, expired = preview_register_reservation(self.series.pk, **self.values)
        with self.assertRaisesMessage(ValueError, "again"):
            confirm_register_reservation(self.series.pk, **self.values, review_token=expired, confirmed=True)
        _, token = preview_register_reservation(self.series.pk, **self.values)
        from apps.tenant_apps.loans.services.number_allocation import allocate_pawn_loan_number
        allocate_pawn_loan_number(series=self.series, actor=self.actor)
        with self.assertRaisesMessage(ValueError, "facts changed"):
            confirm_register_reservation(self.series.pk, **self.values, review_token=token, confirmed=True)
        other = Company.objects.create(name="Other register", owner=self.actor, creator=self.actor)
        with without_workspace_context(), workspace_context(other.pk), self.assertRaises((ValueError, PermissionDenied)):
            preview_register_reservation(self.series.pk, **self.values)

    def test_http_register_adoption_review_and_link_from_ordinary_setup(self):
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        kwargs = dict(workspace_slug=self.tenant.slug, pk=self.series.pk)
        self.assertContains(client.get(reverse("workspace_loans:series_update", kwargs=kwargs)), "Use an existing register")
        url = reverse("workspace_loans:series_reserve_register", kwargs=kwargs)
        response = client.post(url, dict(kind="PAWN_LOAN", last_used=5000, reference="Register AA", action="preview"))
        self.assertContains(response, "AA05001")
        import os
        from pathlib import Path
        if os.environ.get('PAPER_QA_CAPTURE'):
            capture = Path(os.environ['PAPER_QA_CAPTURE'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture/'register-review.html').write_bytes(response.content)
        token = response.context["form"]["review_token"].value()
        response = client.post(url, dict(kind="PAWN_LOAN", last_used=5000, reference="Register AA",
            action="confirm", review_token=token, confirmed="on"))
        self.assertEqual(response.status_code, 302)
        self.seq.refresh_from_db()
        self.assertEqual(self.seq.next_number, 5001)


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class CommonOriginationTests(AdmissionFixture):
    def export(self):
        from apps.tenant_apps.loans.services.servicing_bundle import export_servicing_bundle
        with self.scoped():
            return export_servicing_bundle(workspace_id=self.a.pk, actor=self.actor, loan_id=self.loan.pk)

    def test_native_corrected_approval_roundtrip_retains_original_borrower(self):
        with self.scoped(), on(date(2026,5,6)):
            self.loan = self.direct
            self.old_party = self.loan.borrower
            self.current_party = Party.objects.create(display_name='Correct approved customer')
            data = dict(borrower_id=self.current_party.pk, reference='Actual signed ticket', reason='Wrong selection', request_key=uuid4().hex)
            _, token = preview_borrower_correction(self.loan.pk, actor=self.actor, data=data)
            record_borrower_correction(self.loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        PortableBorrowerCorrectionTests.test_exact_two_party_destination_restore_preview_commit_reexport_and_retry(self)

    def new_direct(self, series, day):
        from apps.tenant_apps.loans.services import (create_pawn_draft, CreatePawnDraftCommand, CollateralDraftInput,
            append_collateral_photo, approve_pawn_loan, disburse_pawn_loan)
        loan = create_pawn_draft(CreatePawnDraftCommand(workspace_id=self.a.pk, borrower_id=self.direct.borrower_id,
            license_id=series.license_id, series_id=series.pk, product_version_id=self.direct.product_version_id,
            principal_amount=Decimal("1000"), monthly_interest_rate=Decimal("2"), loan_date=day, tenure_months=12,
            collateral=(CollateralDraftInput(description="Ring", metal="GOLD", gross_weight=Decimal("1"),
                net_weight=Decimal("1"), purity_percentage=Decimal("100"), latest_appraised_value=Decimal("10000"), allocated_principal=Decimal("1000")),)), actor=self.actor)
        append_collateral_photo(loan.collateral_items.get().pk, upload=SimpleUploadedFile("ring.jpg", b"\xff\xd8\xff\xe0evidence", content_type="image/jpeg"), actor=self.actor)
        approve_pawn_loan(loan.pk, actor=self.actor)
        disburse_pawn_loan(loan.pk, effective_date=day, actor=self.actor)
        loan.refresh_from_db()
        return loan

    def test_actual_direct_and_interleaved_paper_backlog_share_AA_register(self):
        with self.scoped(), on(date(2026, 5, 6)):
            series = create_series(license=self.direct.license, name="Existing AA register", code="AA", actor=self.actor)
            configure_sequence(series=series, document_kind="PAWN_LOAN", prefix="AA", width=5, actor=self.actor)
            values = dict(actor=self.actor, kind="PAWN_LOAN", last_used=5000, reference="AA register through 5000")
            _, token = preview_register_reservation(series.pk, **values)
            confirm_register_reservation(series.pk, **values, review_token=token, confirmed=True)
            first = self.new_direct(series, date(2026, 5, 6))
            self.assertEqual(first.loan_number, "AA05001")
            for number in ("AA05000", "AA00001"):
                data = dict(borrower_id=first.borrower_id, series_id=series.pk, product_version_id=first.product_version_id,
                    number=number, date=self.original.isoformat(), principal="1000", rate="2", tenure=12,
                    advance_months=1, cash_paid="980", source_reference="Original book / "+number,
                    description="Ring", metal="GOLD", quantity=1, gross_weight="1", net_weight="1", purity="100",
                    monitoring_method="LATEST_APPRAISAL", monitoring_ltv=".8", monitoring_reason="Current appraisal basis",
                    complete_through="2026-05-06", final_state="ACTIVE", confirmed_history=True, confirmed_rule=True, events=[])
                args = dict(workspace=self.a, actor=self.actor, data=data,
                    intent_token=new_recording_intent(workspace=self.a, actor=self.actor))
                _, token = preview_recorded_history(**args)
                old, created = admit_recorded_history(**args, review_token=token, confirmed=True)
                self.assertTrue(created)
                self.assertEqual(old.loan_number, number)
                self.assertFalse(old.approval_snapshots.exists())
                self.assertEqual(series.number_sequences.get(document_kind="PAWN_LOAN").next_number, 5002)
                with self.assertRaises(ValueError):
                    preview_recorded_history(**dict(args, intent_token=new_recording_intent(workspace=self.a, actor=self.actor)))
            self.assertEqual(self.new_direct(series, date(2026, 5, 6)).loan_number, "AA05002")

    def test_common_capability_reads_preserve_four_origin_finances_and_risk_inputs(self):
        from apps.tenant_apps.loans.selectors.servicing_contract import resolve_servicing_contract, get_servicing_position
        from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
        from apps.tenant_apps.loans.selectors.risk import get_pawn_loan_risk_assessment
        from apps.tenant_apps.loans.services.servicing_eligibility import servicing_eligibility
        with self.scoped(), on(date(2026, 5, 6)):
            before = list(m.PawnLoanEvent.objects.values_list("pk", "payload_fingerprint"))
            balances, performance = [], []
            for loan in self.loans:
                contract = resolve_servicing_contract(loan, as_of_date=date(2026, 5, 6))
                self.assertTrue(contract.supports_completed_monthly_servicing, contract)
                eligibility = servicing_eligibility(loan, operation="REPAYMENT", purpose="PAPER", effective_date=date(2026, 5, 6))
                self.assertTrue(eligibility.ready, eligibility.blockers)
                position = get_servicing_position(loan, as_of_date=date(2026, 5, 6))
                exposure = get_pawn_loan_exposure(loan.pk, as_of_date=date(2026, 5, 6))
                risk = get_pawn_loan_risk_assessment(loan.pk, as_of_date=date(2026, 5, 6))
                balances.append((position.balance.principal_outstanding, position.balance.interest_outstanding, exposure.total_economic_exposure))
                from apps.tenant_apps.loans.selectors.delinquency import get_pawn_loan_delinquency
                dpd = get_pawn_loan_delinquency(loan.pk, as_of_date=date(2026, 5, 6)).assessment.days_past_due
                performance.append((dpd, risk.performance_class, risk.days_to_maturity))
            self.assertEqual(balances, [balances[0]]*4)
            self.assertEqual(performance, [performance[0]]*4)
            self.assertEqual(list(m.PawnLoanEvent.objects.values_list("pk", "payload_fingerprint")), before)

    def test_borrower_correction_supported_on_every_origin_preserves_economics_and_approval(self):
        from apps.tenant_apps.loans.services.recorded_collections import collection_balance
        from apps.tenant_apps.loans.selectors.servicing_contract import get_servicing_position
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        entered_through = timezone.now()
        with self.scoped(), on(date(2026, 5, 6)):
            target = Party.objects.create(display_name="Correct common borrower")
            for loan in self.loans:
                before = list(loan.loan_events.values_list("pk", "payload_fingerprint"))
                approvals = list(loan.approval_snapshots.values())
                balance = get_servicing_position(loan, as_of_date=date(2026, 5, 6)).balance
                data = dict(borrower_id=target.pk, reference="Actual agreement "+loan.loan_number,
                    reason="Selected wrong customer during entry", request_key=uuid4().hex)
                _, token = preview_borrower_correction(loan.pk, actor=self.actor, data=data)
                record_borrower_correction(loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
                loan.refresh_from_db()
                self.assertEqual(loan.borrower_id, target.pk)
                self.assertEqual(list(loan.loan_events.values_list("pk", "payload_fingerprint")), before)
                self.assertEqual(list(loan.approval_snapshots.values()), approvals)
                self.assertEqual(get_servicing_position(loan, as_of_date=date(2026, 5, 6)).balance, balance)
                from apps.tenant_apps.loans.services.opening_export import export_loan_data, export_opening
                from apps.tenant_apps.loans.services.servicing_bundle_contract import read_bundle
                # Admission fixtures contain later-recorded original photographs.
                # Export is allowed after recording; the financial cutover is May 6.
                with patch('django.utils.timezone.now', return_value=entered_through):
                    content, filename = export_loan_data(workspace_id=self.a.pk, actor=self.actor, loan_id=loan.pk)
                    self.assertEqual(filename, 'loan-servicing.zip')
                    self.assertEqual(read_bundle(content)[0]['profile'], 'loan-servicing-bundle/5')
                if loan == self.opening:
                    with self.assertRaisesMessage(ValueError, 'both Party identities'):
                        export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=loan.pk)
                if loan.approval_snapshots.exists():
                    payload = PawnLoanDocumentProjectionBuilder.loan_ticket(loan)
                    self.assertEqual(dict(payload.details)["Borrower source ID"], f"Party:{target.pk}")

    def test_same_current_evidence_produces_same_risk_snapshot_and_alert_decisions(self):
        from apps.tenant_apps.loans.services.collateral_reappraisal import record_collateral_reappraisal
        from apps.tenant_apps.loans.services.transaction_reviews import preview_transaction_review, confirm_transaction_review
        from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
        with self.scoped(), on(date(2026, 5, 6)):
            before = list(m.PawnLoanEvent.objects.values_list('pk', 'payload_fingerprint'))
            values, alerts = [], []
            for loan in self.loans:
                item = loan.collateral_items.get()
                prior = item.appraisals.order_by('-version').first()
                record_collateral_reappraisal(loan_id=loan.pk, item_id=item.pk, actor=self.actor,
                    appraised_value=Decimal('5500'), method='PHYSICAL_INSPECTION', evidence_reference='Same inspection',
                    review_notes='Same current condition and value', expected_version=prior.version if prior else 0)
                data = dict(through_date=date(2026,5,6), confirmed_complete=True,
                    source_reference='All actual activity checked', request_key=uuid4().hex, future_capture='ROKKAD_ONLY')
                _, token = preview_transaction_review(loan.pk, actor=self.actor, **data)
                confirm_transaction_review(loan.pk, actor=self.actor, review_token=token, acknowledged=True, **data)
                snapshot = refresh_loan_risk_snapshot(loan.pk, as_of_date=date(2026,5,6))
                self.assertEqual(snapshot.status, 'CURRENT')
                values.append(tuple(getattr(snapshot, field) for field in ('exposure', 'due', 'overdue',
                    'days_past_due', 'days_to_maturity', 'collateral_value', 'ltv_ratio', 'performance_class',
                    'severity', 'action_hint', 'flags', 'policy_identity')))
                alerts.append(list(loan.risk_alerts.values_list('alert_kind','severity','status').order_by('alert_kind')))
            self.assertEqual(values, [values[0]]*4)
            self.assertEqual(alerts, [alerts[0]]*4)
            self.assertEqual(list(m.PawnLoanEvent.objects.values_list('pk','payload_fingerprint')), before)

    def test_queued_native_notice_is_blocked_after_customer_correction_even_with_same_contact(self):
        from unittest.mock import Mock
        from apps.tenant_apps.loans.services.pawn_notices import create_pawn_loan_notice
        from apps.tenant_apps.loans.services.notice_delivery_readiness import dispatch_with_transaction_review
        from apps.tenant_apps.notify_v2.models import NotificationJob
        with self.scoped(), on(date(2026,5,6)):
            old = self.direct.borrower
            old.primary_email = 'shared@example.com'
            old.save(update_fields=['primary_email'])
            notice = create_pawn_loan_notice(self.direct.pk, notice_kind='REPAYMENT_REMINDER', channel='EMAIL',
                request_key=uuid4().hex, actor=self.actor, dispatch_due=False)
            target = Party.objects.create(display_name='Correct customer', primary_email=old.primary_email)
            data = dict(borrower_id=target.pk, reference='Actual signed agreement', reason='Wrong customer selected', request_key=uuid4().hex)
            _, token = preview_borrower_correction(self.direct.pk, actor=self.actor, data=data)
            record_borrower_correction(self.direct.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
            deliver = Mock()
            job = NotificationJob.objects.get(pk=notice.notification_job_id)
            self.assertFalse(dispatch_with_transaction_review(job, deliver))
            deliver.assert_not_called()
            job.refresh_from_db()
            self.assertEqual(job.status, 'FAILED')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend', DEFAULT_FROM_EMAIL='test@example.test')
    def test_new_native_risk_reminder_after_correction_has_separate_once_only_intent(self):
        from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
        from apps.tenant_apps.loans.services.risk_borrower_notices import preview_risk_borrower_notice, create_risk_borrower_notice
        from apps.tenant_apps.notify_v2.models import NotificationEventType, NotificationTemplate
        with self.scoped(), on(date(2027,4,1)):
            old = self.direct.borrower
            old.primary_email = 'shared@example.test'
            old.save(update_fields=['primary_email'])
            refresh_loan_risk_snapshot(self.direct.pk, as_of_date=date(2027,4,1))
            alert = m.LoanRiskAlert.objects.get(loan=self.direct, alert_kind='MATURITY')
            m.PawnLoanCommunicationConsent.objects.create(workspace=self.a, party=old, channel='EMAIL',
                service_notices_allowed=True, evidence='Old customer consent', updated_by=self.actor)
            event, _ = NotificationEventType.objects.get_or_create(key='pawn_loan.repayment_reminder', defaults=dict(name='Repayment',domain='LOAN'))
            NotificationTemplate.objects.create(event_type=event, channel='EMAIL', name='Repayment',
                body_template='{{ customer.name }}: {{ loans.0.total_due }}',subject_template='Repayment')
            before = preview_risk_borrower_notice(alert.pk)
            original = create_risk_borrower_notice(alert.pk, actor=self.actor, expected_fingerprint=before.fingerprint)
            self.assertIsNone(original.transaction_review_id)
            target = Party.objects.create(display_name='Correct reminder customer', primary_email=old.primary_email)
            data = dict(borrower_id=target.pk,reference='Actual signed agreement',reason='Wrong customer selected',request_key=uuid4().hex)
            _, token = preview_borrower_correction(self.direct.pk, actor=self.actor, data=data)
            record_borrower_correction(self.direct.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
            refresh_loan_risk_snapshot(self.direct.pk, as_of_date=date(2027,4,1))
            with self.assertRaisesMessage(ValueError, 'consent'):
                preview_risk_borrower_notice(alert.pk)
            m.PawnLoanCommunicationConsent.objects.create(workspace=self.a, party=target, channel='EMAIL',
                service_notices_allowed=True, evidence='Correct customer independent consent', updated_by=self.actor)
            preview = preview_risk_borrower_notice(alert.pk)
            replacement = create_risk_borrower_notice(alert.pk, actor=self.actor, expected_fingerprint=preview.fingerprint)
            self.assertNotEqual(original.pk, replacement.pk)
            self.assertEqual(replacement.source_risk_event_id, original.source_risk_event_id)
            self.assertEqual(replacement.payload_snapshot['borrower_identity']['party_id'], target.pk)
            with self.assertRaisesMessage(ValueError, 'already has'):
                preview_risk_borrower_notice(alert.pk)
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.PawnLoanNotice.objects.create(workspace=self.a, loan=self.direct, notice_kind=replacement.notice_kind,
                    channel='EMAIL',request_key=uuid4().hex,scheduled_for=replacement.scheduled_for,recipient_email=replacement.recipient_email,
                    source_risk_alert=alert,source_risk_event=alert.source_event,
                    notification_template_id=replacement.notification_template_id,notification_template_version=replacement.notification_template_version,
                    payload_snapshot=replacement.payload_snapshot)
            from importlib import import_module
            operation = import_module('apps.tenant_apps.loans.migrations.0077_corrected_borrower_notice_intent').Migration.operations[-1]
            with self.assertRaisesMessage(DatabaseError, 'prevents downgrade'), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(operation.reverse_sql)


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class PortableBorrowerCorrectionTests(WorkspaceTestCase):
    from apps.tenant_apps.data_portability.tests.fixtures import PortabilityFixture
    scoped = PortabilityFixture.scoped

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.role_sql = connection.ops.quote_name('borrower_port_' + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE ROLE {cls.role_sql} NOLOGIN NOSUPERUSER NOBYPASSRLS')
            cursor.execute(f'GRANT USAGE ON SCHEMA public TO {cls.role_sql}')
            cursor.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {cls.role_sql}')
            cursor.execute(f'GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {cls.role_sql}')

    @classmethod
    def tearDownClass(cls):
        with connection.cursor() as cursor:
            cursor.execute('RESET ROLE')
            cursor.execute(f'DROP OWNED BY {cls.role_sql}')
            cursor.execute(f'DROP ROLE {cls.role_sql}')
        super().tearDownClass()

    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history
    row = histories.RecordedHistoryTests.row
    admit = histories.RecordedHistoryTests.admit

    def setUp(self):
        self.prepare_history()
        self.data["events"] = [self.row()]
        self.loan, _, _ = self.admit()
        self.old_party = self.loan.borrower
        self.current_party = Party.objects.create(display_name="Correct source customer")
        data = dict(borrower_id=self.current_party.pk, reference="Book page 10", reason="Mistaken customer", request_key=uuid4().hex)
        _, token = preview_borrower_correction(self.loan.pk, actor=self.actor, data=data)
        record_borrower_correction(self.loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)

    def export(self):
        from apps.tenant_apps.loans.services.servicing_bundle import export_servicing_bundle
        return export_servicing_bundle(workspace_id=self.tenant.pk, actor=self.actor, loan_id=self.loan.pk)

    def test_version_five_retains_both_parties_and_old_profiles_refuse_its_evidence(self):
        from apps.tenant_apps.loans.services.servicing_bundle_contract import read_bundle, BORROWER_PROFILE
        document, _ = read_bundle(self.export())
        self.assertEqual(document["profile"], BORROWER_PROFILE)
        from apps.tenant_apps.loans.services.servicing_bundle_contract import decode
        correction_log = next(row for row in document['tables']['LoanChangeLog'] if row['event_kind']=='BORROWER_CORRECTED')
        for version in range(1,5):
            with self.assertRaises(ValueError):
                decode('LoanChangeLog', correction_log, profile=f'loan-servicing-bundle/{version}')
        self.assertEqual(set(document["agreement_parties"][str(self.loan.pk)]), {str(self.old_party.pk), str(self.current_party.pk)})
        from apps.tenant_apps.loans.services.servicing_bundle import _source_graph
        bad = deepcopy(document)
        log = next(row for row in bad["tables"]["LoanChangeLog"] if row["event_kind"] == "BORROWER_CORRECTED")
        log["metadata"]["borrower_correction"]["after"]["id"] = self.old_party.pk
        with self.assertRaises(ValueError):
            _source_graph(bad)
        bad = deepcopy(document)
        next(row for row in bad['tables']['LoanChangeLog'] if row['event_kind']=='BORROWER_CORRECTED')['event_kind'] = 'NOTE'
        with self.assertRaises(ValueError):
            _source_graph(bad)

    def test_missing_or_collapsed_former_customer_mapping_is_held(self):
        from apps.tenant_apps.loans.services.servicing_bundle_contract import read_bundle
        from apps.tenant_apps.loans.services.servicing_borrowers import destination_parties
        from apps.tenant_apps.data_portability.models import PartyIdentity, SourceIdentity
        document, _ = read_bundle(self.export())
        target = Company.objects.create(name='Mapping destination', owner=self.actor, creator=self.actor)
        with without_workspace_context(), self.scoped(target):
            party = Party.objects.create(display_name='Current destination')
            identity = PartyIdentity.objects.create(workspace=target, party=party)
            references = document['agreement_parties'][str(self.loan.pk)]
            current = references[str(self.current_party.pk)]
            SourceIdentity.objects.create(workspace=target, identity=identity, source_system=current['source_system'],
                external_id=current['id'], accepted_digest='a'*64, local_digest='a'*64)
            with self.assertRaisesMessage(ValueError, 'every exact'):
                destination_parties(document, str(self.loan.pk), target.pk, party.pk)
            former = references[str(self.old_party.pk)]
            SourceIdentity.objects.create(workspace=target, identity=identity, source_system=former['source_system'],
                external_id=former['id'], accepted_digest='a'*64, local_digest='a'*64)
            with self.assertRaisesMessage(ValueError, 'cannot collapse'):
                destination_parties(document, str(self.loan.pk), target.pk, party.pk)
            self.assertFalse(m.PawnLoan.objects.exists())

    def test_repeated_corrections_retain_every_customer_and_complete_chain(self):
        from apps.tenant_apps.loans.services.servicing_bundle_contract import read_bundle
        from apps.tenant_apps.loans.services.servicing_bundle import _source_graph
        third = Party.objects.create(display_name='Third corrected customer')
        data = dict(borrower_id=third.pk, reference='Book page 11', reason='Second documented correction', request_key=uuid4().hex)
        _, token = preview_borrower_correction(self.loan.pk, actor=self.actor, data=data)
        record_borrower_correction(self.loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        document, _ = read_bundle(self.export())
        self.assertEqual(set(document['agreement_parties'][str(self.loan.pk)]),
            {str(p.pk) for p in (self.old_party, self.current_party, third)})
        _source_graph(document)

    def test_version_five_staging_guard_and_retained_evidence_prevent_downgrade(self):
        from importlib import import_module
        from apps.tenant_apps.data_portability import loan_restore
        content = self.export()
        with self.scoped(self.tenant):
            batch = loan_restore.stage(workspace_id=self.tenant.pk, actor=self.actor, content=content)
            self.assertEqual(batch.profile, 'loan-servicing-bundle/5')
            self.assertEqual(loan_restore.stage(workspace_id=self.tenant.pk, actor=self.actor, content=content).pk, batch.pk)
            operation = import_module('apps.tenant_apps.data_portability.migrations.0027_borrower_correction_profile').Migration.operations[0]
            with self.assertRaisesMessage(DatabaseError, 'prevents downgrade'), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(operation.reverse_sql)

    def test_exact_two_party_destination_restore_preview_commit_reexport_and_retry(self):
        from apps.tenant_apps.loans.services.servicing_bundle import restore_servicing_bundle, export_servicing_bundle
        from apps.tenant_apps.loans.services.servicing_bundle_contract import read_bundle
        from apps.tenant_apps.data_portability.models import PartyIdentity, SourceIdentity
        content = self.export()
        document, _ = read_bundle(content)
        self.actor.is_superuser = True
        self.actor.save(update_fields=["is_superuser"])
        target = Company.objects.create(name="Borrower correction destination", owner=self.actor, creator=self.actor)
        with without_workspace_context(), self.scoped(target):
            parties = {}
            for source_id, reference in document["agreement_parties"][str(self.loan.pk)].items():
                party = Party.objects.create(display_name="Exact destination "+source_id)
                parties[int(source_id)] = party
                identity = PartyIdentity.objects.create(workspace=target, party=party)
                SourceIdentity.objects.create(workspace=target, identity=identity, source_system=reference["source_system"],
                    external_id=reference["id"], accepted_digest="a"*64, local_digest="a"*64)
            setup = document["setup"][str(self.loan.pk)]
            license = create_license(workspace=target, actor=self.actor, name="Matching source", license_number=setup["licence_number"], issued_on=date(2020,1,1), expires_on=date(2099,1,1))
            series = m.LoanSeries.objects.create(license=license, name="Imported", code="AA")
            product = m.LoanProduct.objects.create(workspace=target, name="Supported agreement", code="AA")
            version = m.LoanProductVersion.objects.create(product=product, version=1, status="RETIRED", maximum_tenor_months=1200, **setup["product"])
            args = dict(workspace_id=target.pk, actor=self.actor, content=content, mapping={str(self.loan.pk):dict(
                borrower_id=parties[self.current_party.pk].pk, revision_id=license.revisions.get().pk, series_id=series.pk, product_version_id=version.pk)})
            preview = restore_servicing_bundle(**args)
            self.assertFalse(m.PawnLoan.objects.exists())
            result = restore_servicing_bundle(**args, expected_sha256=preview["sha256"], confirmed=True)
            restored = m.PawnLoan.objects.get(pk=result["loans"][0])
            evidence = restored.change_log.get(event_kind="BORROWER_CORRECTED").metadata["borrower_correction"]
            self.assertEqual(evidence["before"]["id"], parties[self.old_party.pk].pk)
            self.assertEqual(evidence["after"]["id"], parties[self.current_party.pk].pk)
            self.assertEqual(restored.borrower_id, parties[self.current_party.pk].pk)
            if restored.approval_snapshots.exists():
                self.assertEqual(restored.approval_snapshots.first().payload['borrower_id'], parties[self.old_party.pk].pk)
                from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
                payload = PawnLoanDocumentProjectionBuilder.loan_ticket(restored)
                self.assertEqual(dict(payload.details)['Borrower source ID'], f'Party:{parties[self.current_party.pk].pk}')
            again, _ = read_bundle(export_servicing_bundle(workspace_id=target.pk, actor=self.actor, loan_id=restored.pk))
            self.assertEqual(again["positions"][str(restored.pk)]["recorded"], document["positions"][str(self.loan.pk)]["recorded"])
            self.assertTrue(restore_servicing_bundle(**args, expected_sha256=preview["sha256"], confirmed=True)["already_restored"])
