"""Exact authenticated global ingestion; no guessed Workspace from chat/provider IDs."""
from datetime import timedelta
from django.core.exceptions import PermissionDenied
from apps.tenancy.context import workspace_context
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from .receipts import parse_status, record_receipt
from .models import ProviderReceipt, ReceiptLink, Attempt, Contact, InboundReceipt
from .tests import EnrollmentFixture, INBOUND
from .test_intents import STORAGE


def status_payload(*statuses):
    return {"object": "whatsapp_business_account", "entry": [{"id": "67890", "changes": [{"field": "messages",
        "value": {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "12345"},
                  "statuses": list(statuses)}}]}]}


def status_fact(status="delivered", message_id="wamid.fixture_status", **changes):
    return {"id": message_id, "recipient_id": "919876543210", "status": status,
            "timestamp": str(int(timezone.now().timestamp())), **changes}


@override_settings(**INBOUND, STORAGES=STORAGE)
class ReceiptTests(EnrollmentFixture, TestCase):
    def test_signed_unmatched_receipt_is_durable_before_ack_and_replay_is_deduplicated(self):
        payload = status_payload(status_fact())
        self.assertEqual(self.post_payload(payload).status_code, 200)
        self.assertEqual(self.post_payload(payload).status_code, 200)
        self.assertEqual(ProviderReceipt.objects.count(), 1)
        self.assertFalse(Attempt.objects.exists())
        self.assertFalse(ReceiptLink.objects.exists())
        self.assertFalse(Contact.objects.exists())

    def test_receipt_retains_only_numeric_error_and_bounded_pricing_facts(self):
        self.post_payload(status_payload(status_fact("failed", errors=[{"code": 131026,
            "message": "fictional phone/address in raw provider details", "error_data": {"details": "private"}}],
            pricing={"category": "utility", "pricing_model": "PMP", "billable": True,
                     "secret_extra": "discard"})))
        row = ProviderReceipt.objects.get()
        self.assertEqual(row.error_codes, [131026])
        self.assertEqual((row.pricing_category,row.pricing_model,row.billable), ("utility","PMP",True))
        self.assertNotIn("919876543210", str(row.__dict__))
        self.assertNotIn("private", str(row.__dict__))
        self.assertNotIn("discard", str(row.__dict__))

    def test_wrong_hmac_sender_or_waba_is_rejected_without_receipt(self):
        payload = status_payload(status_fact())
        self.assertEqual(self.post_payload(payload, secret="wrong").status_code, 403)
        payload["entry"][0]["id"] = "wrong"
        self.assertEqual(self.post_payload(payload).status_code, 400)
        payload["entry"][0]["id"] = "67890"
        payload["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = "foreign"
        self.assertEqual(self.post_payload(payload).status_code, 400)
        self.assertFalse(ProviderReceipt.objects.exists())

    def test_future_invalid_or_overlong_status_fails_whole_batch(self):
        for changes in ({"timestamp": str(int((timezone.now()+timedelta(minutes=6)).timestamp()))},
                        {"id": "invented"}, {"status": "unknown"}, {"recipient_id": "bad"},
                        {"errors": [{"code": True}]}, {"errors": [{"code": "private"}]},
                        {"pricing": {"billable": "yes"}}, {"pricing": {"category": "x"*33}}):
            with self.subTest(changes=changes):
                self.assertEqual(self.post_payload(status_payload(status_fact(),status_fact(**changes))).status_code,400)
        self.assertFalse(ProviderReceipt.objects.exists())

    def test_partial_invalid_batch_never_applies_valid_stop(self):
        contact = self.paired()
        before = InboundReceipt.objects.count()
        payload = self.payload("STOP")
        payload["entry"][0]["changes"][0]["value"]["statuses"] = [status_fact(),status_fact(id="invalid")]
        self.assertEqual(self.post_payload(payload).status_code,400)
        contact.refresh_from_db()
        self.assertEqual(contact.state, Contact.State.VERIFIED)
        self.assertEqual(InboundReceipt.objects.count(),before)
        self.assertFalse(ProviderReceipt.objects.exists())

    def test_wrong_field_product_or_container_is_rejected(self):
        for field,product in (("other","whatsapp"),("messages","other")):
            payload = status_payload(status_fact())
            payload["entry"][0]["changes"][0]["field"] = field
            payload["entry"][0]["changes"][0]["value"]["messaging_product"] = product
            self.assertEqual(self.post_payload(payload).status_code,400)
        payload = status_payload(status_fact())
        payload["entry"][0]["changes"][0]["value"]["statuses"] = "not a list"
        self.assertEqual(self.post_payload(payload).status_code,400)
        self.assertFalse(ProviderReceipt.objects.exists())

    def test_receipts_are_immutable_through_bulk_dml(self):
        self.post_payload(status_payload(status_fact()))
        row = ProviderReceipt.objects.get()
        for mutation in (lambda: ProviderReceipt.objects.filter(pk=row.pk).update(status="read"),
                         lambda: ProviderReceipt.objects.filter(pk=row.pk).delete()):
            with self.assertRaises(DatabaseError),transaction.atomic():
                mutation()

    def test_combined_status_and_text_bound_is_twenty(self):
        self.assertEqual(self.post_payload(status_payload(*[status_fact(message_id="wamid."+str(n)) for n in range(21)])).status_code,400)
        self.assertFalse(ProviderReceipt.objects.exists())

    def test_deleted_receipt_is_evidence_without_claiming_delivery(self):
        self.assertEqual(self.post_payload(status_payload(status_fact("deleted"))).status_code,200)
        self.assertEqual(ProviderReceipt.objects.get().status,"deleted")

    def test_receipt_ingestion_cannot_inherit_a_workspace_context(self):
        facts = parse_status(status_fact(),phone_id="12345",waba_id="67890")
        with workspace_context(self.ws.pk),self.assertRaises(PermissionDenied):
            record_receipt(facts)
        self.assertFalse(ProviderReceipt.objects.exists())

    def test_unknown_pricing_preserves_delivery_proof_without_raw_category(self):
        self.assertEqual(self.post_payload(status_payload(status_fact(pricing={"category":"future_category","pricing_model":"future_model","billable":True}))).status_code,200)
        row=ProviderReceipt.objects.get()
        self.assertEqual(row.pricing_category,"unknown")
        self.assertEqual(row.pricing_model,"unknown")
