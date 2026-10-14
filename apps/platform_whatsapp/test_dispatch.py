"""Real committed restricted-role transactions; every outbound provider call mocked."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, time as clock_time
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command, CommandError
from django.db import connection, connections, close_old_connections, DatabaseError, transaction
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from apps.tenancy.context import current_workspace_id, workspace_context
from .configuration import transport_blockers
from .dispatch import dispatch_one, reconcile_delivery, _claim, _before_request
from .intents import review_setup, confirm_setup, preview_delivery
from .models import Attempt, Delivery, ReceiptLink, ProviderReceipt
from .receipts import parse_status, record_receipt, attempt_summary
from .services import change_contact
from .tests import EnrollmentFixture
from .test_intents import STORAGE
from .test_receipts import status_payload, status_fact
from .test_transport import SEND
from .transport import TransportFailure


class DispatchFixture(EnrollmentFixture):
    def setUp(self):
        with transaction.atomic():
            EnrollmentFixture.setUp(self)
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_user")
                self.runtime_role = cursor.fetchone()[0]
        with connection.cursor() as cursor:
            cursor.execute("SET ROLE " + connection.ops.quote_name(self.runtime_role))
        self.contact = self.paired()
        from .test_release_controls import fixture_pilot
        self.pilot_settings = override_settings(PLATFORM_WHATSAPP_PILOT=fixture_pilot(self))
        self.pilot_settings.enable()
        self.addCleanup(self.pilot_settings.disable)
        self.quiet_gate = patch("apps.platform_whatsapp.controls.time",
            side_effect=lambda h: clock_time(0) if h == 9 else clock_time(23,59))
        self.quiet_gate.start()
        self.gate = patch("apps.platform_whatsapp.configuration.release_blockers", return_value=[])
        self.gate.start()
        self.send = patch("apps.platform_whatsapp.dispatch.send_cloud", return_value="wamid.accepted_fixture").start()
        self.addCleanup(patch.stopall)

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            role = connection.ops.quote_name(self.runtime_role)
            cursor.execute("DROP OWNED BY " + role)
            cursor.execute("DROP ROLE " + role)
        super().tearDown()

    def source(self, capture=False, workspace=None):
        workspace = workspace or self.ws
        reviewed = review_setup(actor=self.owner, workspace_slug=workspace.slug)
        create = Delivery.objects.create
        # New fictional non-capture creation only. Never rewrite an old captured row.
        with patch("apps.platform_whatsapp.intents.Delivery.objects.create",
                   side_effect=lambda **values: create(**{**values, "capture_only": capture})):
            return confirm_setup(actor=self.owner, token=reviewed["token"])

    def dispatch(self, row):
        return dispatch_one(workspace_id=row.workspace_id, delivery_id=row.pk)

    def attempts(self, row):
        with workspace_context(row.workspace_id):
            return list(Attempt.objects.filter(delivery=row).order_by("number"))

    def reconcile(self, row, **kw):
        return reconcile_delivery(workspace_id=row.workspace_id, delivery_id=row.pk, **kw)

    def concurrent(self, action):
        barrier = Barrier(2)
        def invoke(_):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET ROLE " + connection.ops.quote_name(self.runtime_role))
                barrier.wait(timeout=15)
                return action()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(invoke,range(2)))


@override_settings(**SEND, STORAGES=STORAGE)
class DispatchTests(DispatchFixture, TransactionTestCase):
    def test_capture_history_never_promotes_or_claims_even_with_enabled_flags(self):
        row = self.source(capture=True)
        self.assertEqual(self.dispatch(row),"captured")
        self.send.assert_not_called()
        self.assertFalse(self.attempts(row))
        with workspace_context(self.ws.pk),self.assertRaises(DatabaseError),transaction.atomic():
            Delivery.objects.filter(pk=row.pk).update(capture_only=False)

    def test_native_source_writers_still_create_capture_only_without_fixture_override(self):
        reviewed = review_setup(actor=self.owner, workspace_slug=self.ws.slug)
        row = confirm_setup(actor=self.owner,token=reviewed["token"])
        self.assertTrue(row.capture_only)
        self.assertEqual(self.dispatch(row),"captured")
        self.send.assert_not_called()

    def test_actual_release_gate_cannot_be_bypassed_by_configuration(self):
        row = self.source()
        self.gate.stop()
        with override_settings(PLATFORM_WHATSAPP_PILOT={}):
            self.assertIn("dated_pilot_controls_required",transport_blockers())
            with self.assertRaises(ValidationError):
                self.dispatch(row)
        self.send.assert_not_called()
        self.assertFalse(self.attempts(row))

    def test_claim_is_visible_on_a_second_connection_before_outbound_io(self):
        row = self.source()
        def observe(payload):
            self.assertFalse(connection.in_atomic_block)
            self.assertIsNone(current_workspace_id())
            def read():
                close_old_connections()
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("SET ROLE " + connection.ops.quote_name(self.runtime_role))
                    with workspace_context(self.ws.pk):
                        return Attempt.objects.get(delivery=row).outcome
                finally:
                    connections.close_all()
            with ThreadPoolExecutor(max_workers=1) as pool:
                self.assertEqual(pool.submit(read).result(timeout=15),"claimed")
            self.assertEqual(payload["template"]["components"][0]["parameters"][0]["text"],self.ws.name)
            return "wamid.accepted_fixture"
        self.send.side_effect = observe
        self.assertEqual(self.dispatch(row),"accepted")
        self.assertEqual(self.attempts(row)[0].provider_message_id,"wamid.accepted_fixture")
        self.assertFalse(connection.in_atomic_block)
        self.assertIsNone(current_workspace_id())

    def test_two_concurrent_dispatchers_make_one_request(self):
        row = self.source()
        results = self.concurrent(lambda:self.dispatch(row))
        self.assertTrue(set(results)<={"claimed","accepted"})
        self.assertEqual(len(self.attempts(row)),1)
        self.send.assert_called_once()

    def test_request_replay_never_resends_accepted_message(self):
        row = self.source()
        self.assertEqual(self.dispatch(row),"accepted")
        self.assertEqual(self.dispatch(row),"accepted")
        self.send.assert_called_once()

    def test_timeout_unknown_and_unexpected_transport_error_never_retry(self):
        row = self.source()
        self.send.side_effect = TransportFailure("provider_connection_uncertain")
        self.assertEqual(self.dispatch(row),"unknown")
        self.assertEqual(self.dispatch(row),"unknown")
        self.send.assert_called_once()
        self.assertFalse(self.attempts(row)[0].retryable)

    def test_unexpected_transport_exception_becomes_unknown_with_sanitized_code(self):
        row = self.source()
        self.send.side_effect = RuntimeError("fictional-private-token 919876543210")
        self.assertEqual(self.dispatch(row),"unknown")
        self.assertEqual(self.attempts(row)[0].diagnostic,"unexpected_transport_uncertainty")

    def test_definite_transient_rejection_has_backoff_and_three_attempt_limit(self):
        row = self.source()
        self.send.side_effect = TransportFailure("provider_rejected", outcome=Attempt.Outcome.REJECTED,
                                                retryable=True,http_status=429)
        at = timezone.now()
        with patch("apps.platform_whatsapp.dispatch.timezone.now",return_value=at):
            self.assertEqual(self.dispatch(row),"rejected")
            self.assertEqual(self.dispatch(row),"backoff")
        for minute in (2,5):
            with patch("apps.platform_whatsapp.dispatch.timezone.now",return_value=at+timedelta(minutes=minute)):
                self.assertEqual(self.dispatch(row),"rejected")
        with patch("apps.platform_whatsapp.dispatch.timezone.now",return_value=at+timedelta(minutes=9)):
            self.assertEqual(self.dispatch(row),"rejected")
        self.assertEqual(len(self.attempts(row)),3)
        self.assertEqual(self.send.call_count,3)

    def test_permanent_rejection_never_retries(self):
        row = self.source()
        self.send.side_effect = TransportFailure("provider_rejected",outcome=Attempt.Outcome.REJECTED,http_status=400)
        self.assertEqual(self.dispatch(row),"rejected")
        self.assertEqual(self.dispatch(row),"rejected")
        self.send.assert_called_once()

    def test_consent_revocation_after_claim_cancels_before_request(self):
        row = self.source()
        original = _before_request
        def revoke(workspace_id,attempt_id):
            change_contact(actor=self.owner,action="pause")
            return original(workspace_id,attempt_id)
        with patch("apps.platform_whatsapp.dispatch._before_request",side_effect=revoke):
            self.assertEqual(self.dispatch(row),"cancelled")
        self.send.assert_not_called()

    def test_template_or_configuration_change_after_claim_cancels_before_request(self):
        row = self.source()
        original = _before_request
        def change(workspace_id,attempt_id):
            with override_settings(PLATFORM_WHATSAPP_API_VERSION="v98.0"):
                return original(workspace_id,attempt_id)
        with patch("apps.platform_whatsapp.dispatch._before_request",side_effect=change):
            self.assertEqual(self.dispatch(row),"cancelled")
        self.send.assert_not_called()

    def test_invalid_or_unapproved_template_cannot_claim(self):
        row = self.source()
        with override_settings(PLATFORM_WHATSAPP_TEMPLATES={}):
            with self.assertRaises(ValidationError):
                self.dispatch(row)
        self.assertFalse(self.attempts(row))
        self.send.assert_not_called()

    def test_early_callback_matches_only_after_actual_response_id_is_saved(self):
        row = self.source()
        def early(payload):
            self.assertEqual(self.post_payload(status_payload(status_fact("read",message_id="wamid.accepted_fixture"))).status_code,200)
            with workspace_context(self.ws.pk):
                self.assertFalse(ReceiptLink.objects.exists())
            return "wamid.accepted_fixture"
        self.send.side_effect = early
        self.assertEqual(self.dispatch(row),"read")
        with workspace_context(self.ws.pk):
            self.assertEqual(ReceiptLink.objects.count(),1)

    def test_callbacks_out_of_order_preserve_read_and_retained_failure_conflict(self):
        row = self.source()
        self.dispatch(row)
        for state in ("read","failed","sent","delivered","deleted"):
            self.post_payload(status_payload(status_fact(state,message_id="wamid.accepted_fixture")))
            result = self.reconcile(row)
            self.assertEqual(result["status"],"read")
        self.assertTrue(result["conflict"])
        self.send.assert_called_once()

    def test_late_delivery_after_stop_still_matches_without_an_acknowledgement_send(self):
        row = self.source()
        self.dispatch(row)
        self.post_payload(self.payload("STOP"))
        self.assertEqual(self.post_payload(status_payload(status_fact(message_id="wamid.accepted_fixture"))).status_code,200)
        self.assertEqual(self.reconcile(row)["status"],"delivered")
        self.send.assert_called_once()

    def test_wrong_recipient_or_unmatched_provider_id_never_claims_delivery(self):
        row = self.source()
        self.dispatch(row)
        for fact in (status_fact(message_id="wamid.accepted_fixture",recipient_id="919876543211"),
                     status_fact(message_id="wamid.foreign")):
            self.post_payload(status_payload(fact))
        self.assertEqual(self.reconcile(row)["status"],"accepted")
        with workspace_context(self.ws.pk):
            self.assertFalse(ReceiptLink.objects.exists())

    def test_duplicate_provider_response_id_marks_second_claim_unknown(self):
        first = self.source()
        self.dispatch(first)
        with transaction.atomic():
            second_ws = self.make_workspace("pw03-second-owner-workspace",self.owner)
        self.consent(self.contact,workspace=second_ws)
        second = self.source(workspace=second_ws)
        self.assertEqual(self.dispatch(second),"unknown")
        self.assertEqual(self.attempts(second)[0].diagnostic,"provider_identity_conflict")
        self.assertEqual(self.attempts(first)[0].outcome,"accepted")

    def test_interrupted_claim_is_recovered_as_unknown_and_not_automatically_retried(self):
        row = self.source()
        self.send.side_effect = SystemExit("simulated process interruption")
        with self.assertRaises(SystemExit):
            self.dispatch(row)
        attempt = self.attempts(row)[0]
        with patch("apps.platform_whatsapp.dispatch.timezone.now",return_value=attempt.claimed_at+timedelta(minutes=6)):
            self.assertEqual(self.reconcile(row,recover_stale=True)["status"],"unknown")
            self.assertEqual(self.dispatch(row),"unknown")
        self.send.assert_called_once()

    def test_outer_transaction_scope_owner_role_or_wrong_workspace_never_sends(self):
        row = self.source()
        with transaction.atomic(),self.assertRaises(PermissionDenied):
            self.dispatch(row)
        with workspace_context(self.ws.pk),self.assertRaises(PermissionDenied):
            self.dispatch(row)
        with self.assertRaises(Delivery.DoesNotExist):
            dispatch_one(workspace_id=self.foreign.pk,delivery_id=row.pk)
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
        try:
            with self.assertRaises(PermissionDenied):
                self.dispatch(row)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SET ROLE " + connection.ops.quote_name(self.runtime_role))
        self.send.assert_not_called()

    def test_attempt_and_link_scope_and_completed_evidence_are_database_guarded(self):
        row = self.source()
        self.dispatch(row)
        attempt = self.attempts(row)[0]
        self.post_payload(status_payload(status_fact(message_id="wamid.accepted_fixture")))
        self.reconcile(row)
        with workspace_context(self.ws.pk):
            link = ReceiptLink.objects.get()
            for mutation in (lambda: Attempt.objects.filter(pk=attempt.pk).update(outcome="unknown",provider_message_id=""),
                             lambda: Attempt.objects.filter(pk=attempt.pk).update(template_name="changed"),
                             lambda: Attempt.objects.filter(pk=attempt.pk).delete(),
                             lambda: ReceiptLink.objects.filter(pk=link.pk).delete()):
                with self.assertRaises(DatabaseError),transaction.atomic():
                    mutation()
        self.assertFalse(Attempt.objects.exists())
        self.assertFalse(ReceiptLink.objects.exists())
        values = {f.attname:getattr(attempt,f.attname) for f in attempt._meta.concrete_fields if not f.primary_key}
        values.update(workspace_id=self.foreign.pk,outcome="claimed",provider_message_id="",finished_at=None,http_status=None)
        with workspace_context(self.foreign.pk):
            self.assertFalse(Attempt.objects.filter(pk=attempt.pk).exists())
            with self.assertRaises(DatabaseError),transaction.atomic():
                Attempt.objects.bulk_create([Attempt(**values)])
            with self.assertRaises(DatabaseError),transaction.atomic():
                ReceiptLink.objects.bulk_create([ReceiptLink(workspace=self.foreign,attempt=attempt,receipt=link.receipt)])

    def test_direct_wrong_recipient_receipt_link_is_rejected(self):
        row = self.source()
        self.dispatch(row)
        attempt = self.attempts(row)[0]
        self.post_payload(status_payload(status_fact(message_id="wamid.accepted_fixture",recipient_id="919876543211")))
        receipt = ProviderReceipt.objects.get()
        with workspace_context(self.ws.pk),self.assertRaises(DatabaseError),transaction.atomic():
            ReceiptLink.objects.create(workspace=self.ws,attempt=attempt,receipt=receipt)

    def test_owner_preview_reads_status_without_ingesting_or_sending(self):
        row = self.source()
        self.dispatch(row)
        self.post_payload(status_payload(status_fact(message_id="wamid.accepted_fixture")))
        result = preview_delivery(actor=self.owner,workspace_slug=self.ws.slug,delivery_id=row.pk)
        self.assertIn("delivery unconfirmed",result["status"])
        self.assertFalse(result["can_send"])
        self.reconcile(row)
        result = preview_delivery(actor=self.owner,workspace_slug=self.ws.slug,delivery_id=row.pk)
        self.assertEqual(result["status"],"Delivered")
        self.send.assert_called_once()

    def test_scoped_reconciliation_command_never_sends(self):
        row = self.source()
        self.dispatch(row)
        self.post_payload(status_payload(status_fact(message_id="wamid.accepted_fixture")))
        output = StringIO()
        call_command("reconcile_platform_whatsapp",workspace_id=self.ws.pk,delivery_id=row.pk,stdout=output)
        self.assertIn("delivered",output.getvalue())
        self.send.assert_called_once()
        with self.assertRaises(CommandError):
            call_command("reconcile_platform_whatsapp",workspace_id=0,delivery_id=row.pk,stdout=output)

    def test_database_cannot_claim_a_captured_source(self):
        row = self.source(capture=True)
        with workspace_context(self.ws.pk),self.assertRaises(DatabaseError),transaction.atomic():
            Attempt.objects.create(workspace=self.ws,delivery=row,number=1,
                phone_id="12345",waba_id="67890",sender_fingerprint=row.sender_fingerprint,
                transport_fingerprint="b"*64,content_fingerprint="c"*64,
                template_name="fictional_setup",language="en")

    def test_expired_source_does_not_claim_or_send(self):
        row = self.source()
        with patch("apps.platform_whatsapp.dispatch.timezone.now",return_value=row.expires_at),self.assertRaises(ValidationError):
            self.dispatch(row)
        self.send.assert_not_called()
        self.assertFalse(self.attempts(row))

    def test_transferred_owner_cannot_receive_the_predecessors_queued_message(self):
        from apps.orgs.models import Membership
        from apps.orgs.services.control_plane import transfer_workspace_ownership
        row = self.source()
        Membership.objects.create(company=self.ws,user=self.other,role=self.member_role)
        transfer_workspace_ownership(workspace=self.ws,new_owner=self.other,actor=self.owner,
            previous_owner_role=self.member_role,reason="Fictional PW03 transfer")
        with self.assertRaises(ValidationError):
            self.dispatch(row)
        self.send.assert_not_called()
        self.assertFalse(self.attempts(row))
