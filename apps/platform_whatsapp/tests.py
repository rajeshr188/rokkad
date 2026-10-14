"""Enrollment security, source independence and restricted-role isolation."""
import hashlib
import hmac
import json
import uuid
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import connection, DatabaseError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.orgs.services.control_plane import transfer_workspace_ownership
from apps.subscriptions.models import Invoice, Payment, Subscription, SubscriptionEvent
from apps.tenancy.context import current_workspace_id, workspace_context
from apps.platform_whatsapp.configuration import readiness
from apps.platform_whatsapp.models import Contact, ContactEvent, ConsentEvent, Preference, Suppression, InboundReceipt
from apps.platform_whatsapp.phones import normalize_phone
from apps.platform_whatsapp.services import (begin_enrollment, set_preferences, change_contact, preview, digest,
                       CONSENT_VERSION)

INBOUND = dict(PLATFORM_WHATSAPP_INBOUND_ENABLED=True,
    PLATFORM_WHATSAPP_PHONE_ID="12345", PLATFORM_WHATSAPP_WABA_ID="67890",
    PLATFORM_WHATSAPP_APP_SECRET="fictional-pairing-secret",
    PLATFORM_WHATSAPP_VERIFY_TOKEN="fictional-verify-token",
    PLATFORM_WHATSAPP_SENDER_NUMBER="+919876543210", PLATFORM_WHATSAPP_BASE_URL="https://example.test")

class EnrollmentFixture:
    def setUp(self):
        role = connection.ops.quote_name("pw01_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        users = get_user_model().objects
        self.owner = users.create_user(username="wa-owner")
        self.other = users.create_user(username="wa-other")
        self.staff = users.create_user(username="wa-staff")
        self.admin = users.create_superuser(username="wa-admin", email="wa-admin@example.test", password="fixture")
        self.ws = self.make_workspace("wa-first", self.owner)
        self.foreign = self.make_workspace("wa-second", self.other)
        self.member_role = Role.objects.get_or_create(name="Member")[0]
        Membership.objects.create(user=self.staff, company=self.ws, role=self.member_role)
        self.url = reverse("platform_whatsapp_preferences")
        self.callback = reverse("platform_whatsapp_webhook")
        self.client.force_login(self.owner)

    def make_workspace(self, slug, owner):
        workspace = Company.all_objects.create(name=slug, schema_name=slug, owner=owner, creator=owner)
        Membership.objects.create(user=owner, company=workspace, role=Role.objects.get_or_create(name="Owner")[0])
        return workspace

    def enroll(self, actor=None, phone="+919876543210"):
        return begin_enrollment(actor=actor or self.owner, phone=phone)

    def consent(self, contact, actor=None, workspace=None, **categories):
        return set_preferences(actor=actor or self.owner, workspace_slug=(workspace or self.ws).slug,
            contact_revision=contact.revision,
            categories={"setup": True, "subscription": True, "service": False, **categories})

    def payload(self, code, *, phone="919876543210", message_id=None, at=None):
        return {"object": "whatsapp_business_account", "entry": [{"id": "67890", "changes": [{
            "field": "messages", "value": {"metadata": {"phone_number_id": "12345"},
                "messages": [{"id": message_id or uuid.uuid4().hex, "from": phone, "type": "text",
                    "timestamp": str(int((at or timezone.now()).timestamp())), "text": {"body": code}}]}}]}]}

    def post_payload(self, payload, secret="fictional-pairing-secret"):
        body = json.dumps(payload).encode()
        signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return self.client.post(self.callback, body, content_type="application/json",
                                HTTP_X_HUB_SIGNATURE_256=signature)

    def paired(self):
        contact, code = self.enroll()
        self.consent(contact)
        with override_settings(**INBOUND):
            response = self.post_payload(self.payload(code))
        self.assertEqual(response.status_code, 200)
        contact.refresh_from_db()
        self.assertEqual(contact.state, Contact.State.VERIFIED)
        return contact

@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class EnrollmentTests(EnrollmentFixture, TestCase):
    def test_phone_validation_rejects_notes_extensions_and_invalid_numbers(self):
        self.assertEqual(normalize_phone("98765 43210"), "+919876543210")
        for value in ("call 9876543210", "+919876543210 ext 4", "123", "-", ""):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                normalize_phone(value)

    def test_get_is_private_no_mutation_no_inferred_contact_or_consent(self):
        before = (Contact.objects.count(), ContactEvent.objects.count())
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertContains(response, "Preview only")
        self.assertEqual(before, (Contact.objects.count(), ContactEvent.objects.count()))
        self.assertIsNone(current_workspace_id())

    def test_http_enrollment_accepts_lazy_request_user_and_shows_code_once(self):
        response = self.client.post(self.url, {"action": "enroll", "phone": "9876543210"})
        self.assertEqual(response.status_code, 200)
        code = response.context["pairing_code"]
        contact = Contact.objects.get(user=self.owner)
        self.assertEqual(contact.challenge_hash, digest(code))
        self.assertNotIn(code, contact.challenge_hash)
        self.assertFalse(Preference.objects.exists())
        self.assertContains(response, "Pairing reception is not configured yet")
        self.assertNotContains(self.client.get(self.url), code)

    def test_members_outsiders_and_platform_override_cannot_enroll_as_owner(self):
        for actor in (self.staff, self.admin):
            with self.subTest(actor=actor.pk), self.assertRaises(PermissionDenied):
                self.enroll(actor=actor)
        self.assertFalse(Contact.objects.exists())

    def test_actorless_inactive_and_scoped_account_actions_denied(self):
        with self.assertRaises(PermissionDenied):
            begin_enrollment(actor=None, phone="+919876543210")
        self.owner.is_active = False
        with self.assertRaises(PermissionDenied):
            self.enroll()
        self.owner.is_active = True
        with workspace_context(self.ws.pk), self.assertRaises(PermissionDenied):
            self.enroll()

    def test_challenge_reissue_and_hourly_requests_are_limited(self):
        contact, _ = self.enroll()
        with self.assertRaises(ValidationError):
            self.enroll()
        for n in range(4):
            Contact.objects.filter(pk=contact.pk).update(challenge_issued_at=timezone.now()-timedelta(minutes=2))
            self.enroll()
        Contact.objects.filter(pk=contact.pk).update(challenge_issued_at=timezone.now()-timedelta(minutes=2))
        with self.assertRaises(ValidationError):
            self.enroll()

    def test_number_cannot_be_bound_to_two_accounts(self):
        self.enroll()
        with self.assertRaises(ValidationError):
            self.enroll(actor=self.other)
        self.assertEqual(Contact.objects.count(), 1)

    def test_preferences_are_explicit_and_have_immutable_evidence(self):
        contact, _ = self.enroll()
        self.consent(contact, setup=False, subscription=False)
        with workspace_context(self.ws.pk):
            preference = Preference.objects.get(workspace=self.ws)
            self.assertFalse(preference.setup)
            self.assertFalse(preference.subscription)
            self.assertEqual(preference.consent_version, CONSENT_VERSION)
            evidence = ConsentEvent.objects.get()
            with self.assertRaises(DatabaseError), transaction.atomic():
                ConsentEvent.objects.filter(pk=evidence.pk).update(setup=True)
            with self.assertRaises(DatabaseError), transaction.atomic():
                ConsentEvent.objects.filter(pk=evidence.pk).delete()
        with self.assertRaises(DatabaseError), transaction.atomic():
            ContactEvent.objects.update(kind="forged")

    def test_preferences_reject_foreign_owner_and_admin_override(self):
        contact, _ = self.enroll()
        for actor, workspace in ((self.owner, self.foreign), (self.admin, self.ws)):
            with self.subTest(actor=actor.pk), self.assertRaises(PermissionDenied):
                self.consent(contact, actor=actor, workspace=workspace)
        self.assertFalse(Preference.objects.exists())

    def test_preferences_reject_unknown_categories_and_stale_contact_revision(self):
        contact, _ = self.enroll()
        with self.assertRaises(ValidationError):
            self.consent(contact, marketing=True)
        with self.assertRaises(ValidationError):
            set_preferences(actor=self.owner, workspace_slug=self.ws.slug, categories={"setup": True},
                            contact_revision=contact.revision+1)
        self.assertFalse(Preference.objects.exists())

    def test_signed_exact_sender_pairing_is_single_use(self):
        contact, code = self.enroll()
        payload = self.payload(code)
        with override_settings(**INBOUND):
            self.assertEqual(self.post_payload(payload).status_code, 200)
            self.assertEqual(self.post_payload(payload).status_code, 200)
            self.assertEqual(self.post_payload(self.payload(code)).status_code, 200)
        contact.refresh_from_db()
        self.assertEqual(contact.state, Contact.State.VERIFIED)
        self.assertEqual(contact.challenge_hash, "")
        self.assertEqual(ContactEvent.objects.filter(kind="provider_paired").count(), 1)

    def test_wrong_signature_wrong_sender_and_wrong_waba_fail_before_mutation(self):
        contact, code = self.enroll()
        with override_settings(**INBOUND):
            self.assertEqual(self.post_payload(self.payload(code), secret="forged").status_code, 403)
            payload = self.payload(code)
            payload["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = "other"
            self.assertEqual(self.post_payload(payload).status_code, 400)
            payload = self.payload(code)
            payload["entry"][0]["id"] = "other"
            self.assertEqual(self.post_payload(payload).status_code, 400)
        contact.refresh_from_db()
        self.assertEqual(contact.state, Contact.State.PENDING)
        self.assertFalse(InboundReceipt.objects.exists())

    def test_disabled_receiver_and_get_verification_do_not_pair(self):
        contact, code = self.enroll()
        self.assertEqual(self.post_payload(self.payload(code)).status_code, 503)
        with override_settings(**INBOUND):
            self.assertEqual(self.client.get(self.callback, {"hub.mode": "subscribe",
                "hub.verify_token": "fictional-verify-token", "hub.challenge": "fixture-challenge"}).content,
                b"fixture-challenge")
            self.assertEqual(self.client.get(self.callback, {"hub.verify_token": "bad"}).status_code, 403)
        contact.refresh_from_db()
        self.assertEqual(contact.state, Contact.State.PENDING)

    def test_code_must_come_from_entered_number(self):
        contact, code = self.enroll()
        with override_settings(**INBOUND):
            self.assertEqual(self.post_payload(self.payload(code, phone="919876543211")).status_code, 200)
        contact.refresh_from_db()
        self.assertEqual(contact.state, Contact.State.PENDING)
        self.assertEqual(contact.match_failures, 0)

    def test_five_bad_codes_invalidate_challenge(self):
        contact, code = self.enroll()
        with override_settings(**INBOUND):
            for _ in range(5):
                self.assertEqual(self.post_payload(self.payload("bad-code")).status_code, 200)
            self.post_payload(self.payload(code))
        contact.refresh_from_db()
        self.assertEqual(contact.state, Contact.State.PENDING)
        self.assertEqual(contact.challenge_hash, "")

    def test_expired_or_preissued_messages_cannot_pair(self):
        contact, code = self.enroll()
        with override_settings(**INBOUND):
            self.post_payload(self.payload(code, at=timezone.now()-timedelta(hours=1)))
            Contact.objects.filter(pk=contact.pk).update(challenge_expires_at=timezone.now()-timedelta(seconds=1))
            self.post_payload(self.payload(code))
        contact.refresh_from_db()
        self.assertEqual(contact.state, Contact.State.PENDING)

    def test_sender_rotation_invalidates_contact_eligibility(self):
        self.paired()
        with override_settings(**INBOUND):
            self.assertTrue(preview(actor=self.owner, workspace_slug=self.ws.slug, category="setup")["eligible"])
            with override_settings(PLATFORM_WHATSAPP_VERSION="rotated"):
                self.assertFalse(preview(actor=self.owner, workspace_slug=self.ws.slug, category="setup")["eligible"])

    def test_stop_suppresses_all_workspaces_and_start_does_not_restore(self):
        contact = self.paired()
        another = self.make_workspace("wa-another", self.owner)
        self.consent(contact, workspace=another)
        payload = self.payload("STOP")
        with override_settings(**INBOUND):
            self.post_payload(payload)
            self.post_payload(payload)
            self.post_payload(self.payload("START"))
            for workspace in (self.ws, another):
                self.assertFalse(preview(actor=self.owner, workspace_slug=workspace.slug, category="setup")["eligible"])
        contact.refresh_from_db()
        self.assertEqual(contact.state, Contact.State.PAUSED)
        self.assertEqual(Suppression.objects.count(), 1)
        self.assertEqual(ContactEvent.objects.filter(kind="provider_opt_out").count(), 1)

    def test_number_change_invalidates_consent_and_old_code(self):
        contact, old_code = self.enroll()
        self.consent(contact)
        Contact.objects.filter(pk=contact.pk).update(challenge_issued_at=timezone.now()-timedelta(minutes=2))
        new, new_code = self.enroll(phone="+919876543211")
        with override_settings(**INBOUND):
            self.post_payload(self.payload(old_code))
            self.post_payload(self.payload(new_code, phone="919876543211"))
            self.assertFalse(preview(actor=self.owner, workspace_slug=self.ws.slug, category="setup")["eligible"])
            self.consent(new)
            self.assertTrue(preview(actor=self.owner, workspace_slug=self.ws.slug, category="setup")["eligible"])

    def test_pause_and_disconnect_need_new_pairing_and_release_phone_binding(self):
        contact = self.paired()
        change_contact(actor=self.owner, action="pause")
        with override_settings(**INBOUND):
            self.assertFalse(preview(actor=self.owner, workspace_slug=self.ws.slug, category="setup")["eligible"])
        change_contact(actor=self.owner, action="disconnect")
        contact.refresh_from_db()
        self.assertEqual(contact.phone, "")
        self.assertIsNone(contact.verified_at)
        self.enroll(actor=self.other)

    def test_ownership_transfer_does_not_inherit_consent(self):
        contact = self.paired()
        Membership.objects.create(user=self.other, company=self.ws, role=self.member_role)
        transfer_workspace_ownership(workspace=self.ws, new_owner=self.other, actor=self.owner,
            previous_owner_role=self.member_role, reason="Fictional ownership transfer")
        with override_settings(**INBOUND):
            with self.assertRaises(PermissionDenied):
                preview(actor=self.owner, workspace_slug=self.ws.slug, category="setup")
            new, code = self.enroll(actor=self.other, phone="+919876543211")
            self.post_payload(self.payload(code, phone="919876543211"))
            self.assertFalse(preview(actor=self.other, workspace_slug=self.ws.slug, category="setup")["eligible"])
            self.consent(new, actor=self.other)
            self.assertTrue(preview(actor=self.other, workspace_slug=self.ws.slug, category="setup")["eligible"])

    def test_rls_hides_preferences_globally_and_blocks_cross_workspace_dml(self):
        contact, _ = self.enroll()
        self.consent(contact)
        self.assertFalse(Preference.objects.exists())
        self.assertFalse(ConsentEvent.objects.exists())
        with workspace_context(self.foreign.pk):
            self.assertFalse(Preference.objects.filter(workspace=self.ws).exists())
            with self.assertRaises(DatabaseError), transaction.atomic():
                Preference.objects.bulk_create([Preference(workspace=self.ws, contact=contact,
                    contact_revision=contact.revision, consent_version=CONSENT_VERSION)])
            with self.assertRaises(DatabaseError), transaction.atomic():
                ConsentEvent.objects.bulk_create([ConsentEvent(workspace=self.ws, contact=contact,
                    actor=self.owner, contact_revision=1, consent_version=CONSENT_VERSION,
                    setup=True, subscription=False, service=False)])

    def test_database_rejects_other_owners_contact_within_visible_workspace(self):
        contact, _ = self.enroll(actor=self.other)
        with workspace_context(self.ws.pk), self.assertRaises(DatabaseError), transaction.atomic():
            Preference.objects.create(workspace=self.ws, contact=contact, contact_revision=1,
                                      consent_version=CONSENT_VERSION)

    def test_payload_is_fully_validated_before_any_mutation(self):
        contact, code = self.enroll()
        payload = self.payload(code)
        payload["entry"].append({"id": "forged", "changes": []})
        with override_settings(**INBOUND):
            self.assertEqual(self.post_payload(payload).status_code, 400)
            self.assertEqual(self.client.post(self.callback, b"{}", content_type="application/json",
                HTTP_X_HUB_SIGNATURE_256="sha256=bad").status_code, 403)
        contact.refresh_from_db()
        self.assertEqual(contact.state, Contact.State.PENDING)
        self.assertFalse(InboundReceipt.objects.exists())

    def test_preview_is_read_only_escapes_workspace_name_and_never_enables_sending(self):
        self.paired()
        Company.all_objects.filter(pk=self.ws.pk).update(name="<script>alert(1)</script>")
        before = ContactEvent.objects.count()
        with override_settings(**INBOUND):
            response = self.client.post(self.url, {"action": "preview", "workspace_slug": self.ws.slug, "category": "setup"})
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.context["preview"]["can_send"])
            self.assertTrue(response.context["preview"]["eligible"])
            self.assertNotContains(response, "<script>alert(1)</script>")
            self.assertNotContains(response, INBOUND["PLATFORM_WHATSAPP_APP_SECRET"])
        self.assertEqual(ContactEvent.objects.count(), before)
        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(Subscription.objects.exists())
        self.assertFalse(SubscriptionEvent.objects.exists())

    def test_preferences_remain_available_when_workspace_is_suspended_or_unactivated(self):
        contact, _ = self.enroll()
        Company.all_objects.filter(pk=self.ws.pk).update(lifecycle_state="SUSPENDED")
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.consent(contact, setup=False, subscription=False, service=False)
        self.assertFalse(Subscription.objects.exists())

    def test_csrf_is_required_for_account_mutations_but_not_signed_provider_messages(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.url, {"action": "enroll", "phone": "9876543210"}).status_code, 403)
        self.assertEqual(self.client.put(self.url, {}).status_code, 405)
        self.assertEqual(self.client.delete(self.callback).status_code, 405)

    def test_anonymous_account_access_redirects_and_foreign_preview_is_denied(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url, {"action": "preview",
            "workspace_slug": self.foreign.slug, "category": "setup"}).status_code, 403)

    def test_readiness_and_command_do_not_disclose_or_claim_provider_acceptance(self):
        with override_settings(**INBOUND):
            report = readiness()
            self.assertTrue(report["inbound_ready"])
            self.assertFalse(report["can_send"])
            output = StringIO()
            call_command("check_platform_whatsapp", stdout=output)
            self.assertIn("outbound delivery unavailable", output.getvalue())
            self.assertNotIn(INBOUND["PLATFORM_WHATSAPP_APP_SECRET"], output.getvalue())
            self.assertNotIn(INBOUND["PLATFORM_WHATSAPP_VERIFY_TOKEN"], output.getvalue())

    def test_malformed_signed_messages_and_non_ascii_signature_fail_closed(self):
        contact, code = self.enroll()
        with override_settings(**INBOUND):
            payload = self.payload(code)
            payload["entry"][0]["changes"][0]["value"]["messages"] = [None]
            self.assertEqual(self.post_payload(payload).status_code, 400)
            self.assertEqual(self.client.post(self.callback, b"{}", content_type="application/json",
                HTTP_X_HUB_SIGNATURE_256="sha256=\u092c").status_code, 403)
        contact.refresh_from_db()
        self.assertEqual(contact.state, Contact.State.PENDING)
        self.assertFalse(InboundReceipt.objects.exists())

    def test_optout_requires_fresh_pairing_and_reviewed_categories_to_resume(self):
        self.paired()
        with override_settings(**INBOUND):
            self.post_payload(self.payload("STOP"))
            Contact.objects.filter(user=self.owner).update(challenge_issued_at=timezone.now()-timedelta(minutes=2))
            contact, code = self.enroll()
            self.post_payload(self.payload(code))
            self.assertFalse(preview(actor=self.owner, workspace_slug=self.ws.slug, category="setup")["eligible"])
            self.consent(contact)
            self.assertTrue(preview(actor=self.owner, workspace_slug=self.ws.slug, category="setup")["eligible"])

    def test_account_settings_links_to_optional_owner_preferences(self):
        response = self.client.get(reverse("account_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.url)
        self.assertFalse(Contact.objects.exists())

    def test_checked_choices_are_recorded_and_unchecked_choices_are_revoked(self):
        contact, _ = self.enroll()
        data = {"action": "preferences", "workspace_slug": self.ws.slug,
                "contact_revision": contact.revision, "setup": "on"}
        self.assertEqual(self.client.post(self.url, data).status_code, 200)
        with workspace_context(self.ws.pk):
            self.assertTrue(Preference.objects.get().setup)
        data.pop("setup")
        self.assertEqual(self.client.post(self.url, data).status_code, 200)
        with workspace_context(self.ws.pk):
            self.assertFalse(Preference.objects.get().setup)
            self.assertEqual(ConsentEvent.objects.count(), 2)
