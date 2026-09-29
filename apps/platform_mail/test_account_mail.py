import json
import re
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from urllib.parse import urlsplit
from uuid import uuid4

from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress, EmailConfirmationHMAC
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, IntegrityError, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone

from .account_mail import enqueue_account_email
from .models import AccountEmail, Attempt, Delivery, Suppression
from .services import dispatch_one, render_delivery, retry_delivery, source_problem, recipient_hash
from .tests import MAIL_SETTINGS


@override_settings(**MAIL_SETTINGS, ACCOUNT_EMAIL_ENABLED=True, SECURE_SSL_REDIRECT=False,
                   ACCOUNT_ADAPTER="apps.platform_mail.adapter.AccountAdapter",
                   STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                             "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class AccountMailTests(TestCase):
    def setUp(self):
        cache.clear()
        role = connection.ops.quote_name("account_mail_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        self.user = get_user_model().objects.create_user(
            username="account-mail", email="account@example.test", password="Fictional-Password-8174!")
        self.address = EmailAddress.objects.create(user=self.user, email=self.user.email, primary=True)

    def enqueue(self, kind=AccountEmail.Kind.VERIFICATION):
        return enqueue_account_email(user=self.user, email=self.address.email,
                                     email_address=self.address, kind=kind)

    def link(self, row):
        return re.search(r"https://\S+", render_delivery(row)["text"])[0]

    def test_signup_queues_verification_and_post_login_link_confirms_account(self):
        response = self.client.post(reverse("account_signup"), {
            "email": "signup@example.test", "username": "signup-mail",
            "password1": "Fictional-Signup-8194!", "password2": "Fictional-Signup-8194!"})
        self.assertEqual(response.status_code, 302)
        row = Delivery.objects.get(recipient="signup@example.test")
        self.assertEqual(source_problem(row), "")
        self.assertEqual(row.account_email.kind, "verification")
        path = urlsplit(self.link(row)).path
        self.assertEqual(self.client.post(path).status_code, 302)
        self.assertTrue(EmailAddress.objects.get(email=row.recipient).verified)
        self.assertEqual(dispatch_one(row.pk, capture=True), Delivery.Status.CANCELLED)
        self.assertFalse(Attempt.objects.exists())

    def test_password_reset_post_queues_and_rendered_link_changes_password_once(self):
        self.address.verified = True
        self.address.save()
        response = self.client.post(reverse("account_reset_password"), {"email": self.user.email})
        self.assertEqual(response.status_code, 302)
        row = Delivery.objects.get()
        self.assertEqual(row.account_email.kind, "password_reset")
        path = urlsplit(self.link(row)).path
        response = self.client.get(path)
        self.assertEqual(response.status_code, 302)
        response = self.client.post(response.url, {
            "password1": "Fictional-New-Password-9174!", "password2": "Fictional-New-Password-9174!"})
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Fictional-New-Password-9174!"))
        from allauth.account import app_settings
        self.assertFalse(app_settings.PASSWORD_RESET_TOKEN_GENERATOR().check_token(
            self.user, resolve(path).kwargs["key"]))

    def test_unknown_reset_has_same_public_redirect_without_queue(self):
        unknown = self.client.post(reverse("account_reset_password"), {"email": "absent@example.test"})
        self.assertFalse(Delivery.objects.exists())
        known = self.client.post(reverse("account_reset_password"), {"email": self.user.email})
        self.assertEqual((unknown.status_code, unknown.url), (known.status_code, known.url))
        self.assertEqual(Delivery.objects.count(), 1)

    def test_duplicate_pending_requests_coalesce_and_rollback_leaves_no_intent(self):
        row = self.enqueue()
        self.assertEqual(self.enqueue().pk, row.pk)
        with self.assertRaises(RuntimeError), transaction.atomic():
            self.enqueue(AccountEmail.Kind.PASSWORD_RESET)
            raise RuntimeError("rollback")
        self.assertEqual(AccountEmail.objects.count(), 1)
        self.assertEqual(Delivery.objects.count(), 1)

    def test_unknown_acceptance_is_not_automatically_requeued(self):
        row = self.enqueue()
        Delivery.objects.filter(pk=row.pk).update(status=Delivery.Status.UNKNOWN)
        self.assertEqual(self.enqueue().pk, row.pk)
        with self.assertRaises(PermissionDenied):
            retry_delivery(row.pk, actor=self.user)
        self.assertEqual(dispatch_one(row.pk), Delivery.Status.UNKNOWN)
        self.assertFalse(Attempt.objects.exists())

    def test_raw_token_password_context_and_request_host_are_not_persisted(self):
        get_adapter().send_password_reset_mail(self.user, self.user.email, {
            "key": "must-not-store", "password_reset_url": "https://evil.example/must-not-store"})
        row = Delivery.objects.get()
        snapshot = json.dumps({"source": list(AccountEmail.objects.values()),
                               "delivery": list(Delivery.objects.values())}, default=str)
        for secret in ("must-not-store", "evil.example", self.user.password, self.link(row)):
            self.assertNotIn(secret, snapshot)
        self.assertTrue(self.link(row).startswith("https://rokkad.example/"))

    def test_changed_password_or_login_cancels_pending_reset(self):
        for change in ({"password": "different-password-hash"}, {"last_login": timezone.now()}):
            with self.subTest(change=list(change)):
                row = self.enqueue(AccountEmail.Kind.PASSWORD_RESET)
                get_user_model().objects.filter(pk=self.user.pk).update(**change)
                self.assertEqual(dispatch_one(row.pk, capture=True), Delivery.Status.CANCELLED)
        self.assertFalse(Attempt.objects.exists())

    def test_deleted_changed_or_verified_address_cancels_verification(self):
        row = self.enqueue()
        self.address.delete()
        self.assertEqual(dispatch_one(row.pk, capture=True), Delivery.Status.CANCELLED)
        self.address = EmailAddress.objects.create(user=self.user, email=self.user.email)
        row = self.enqueue()
        self.address.email = "changed@example.test"
        self.address.save()
        self.assertEqual(dispatch_one(row.pk, capture=True), Delivery.Status.CANCELLED)
        row = self.enqueue()
        self.address.verified = True
        self.address.save()
        self.assertEqual(dispatch_one(row.pk, capture=True), Delivery.Status.CANCELLED)

    def test_expired_inactive_and_suppressed_requests_never_send(self):
        row = self.enqueue()
        Delivery.objects.filter(pk=row.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        with patch("apps.platform_mail.transport.send_ses") as send:
            self.assertEqual(dispatch_one(row.pk), Delivery.Status.CANCELLED)
            row = self.enqueue()
            self.user.is_active = False
            self.user.save()
            self.assertEqual(dispatch_one(row.pk), Delivery.Status.CANCELLED)
            self.user.is_active = True
            self.user.save()
            row = self.enqueue()
            Suppression.objects.create(recipient_hash=recipient_hash(self.user.email), reason="complaint")
            self.assertEqual(dispatch_one(row.pk), Delivery.Status.SUPPRESSED)
            send.assert_not_called()
        self.assertFalse(Attempt.objects.exists())

    def test_scope_and_gate_protect_invitation_worker_and_account_send(self):
        row = self.enqueue()
        call_command("dispatch_platform_mail", capture=True, invitations_only=True, stdout=StringIO())
        row.refresh_from_db()
        self.assertEqual(row.status, "queued")
        with self.assertRaisesMessage(CommandError, "outside invitation-only scope"):
            call_command("dispatch_platform_mail", capture=True, invitations_only=True,
                         delivery=str(row.pk), stdout=StringIO())
        with override_settings(ACCOUNT_EMAIL_ENABLED=False), self.assertRaisesMessage(ValidationError, "disabled"):
            dispatch_one(row.pk)
        with patch("apps.platform_mail.transport.send_ses", return_value="ses-account") as send, \
                patch("apps.platform_mail.management.commands.dispatch_platform_mail.time.sleep"):
            call_command("dispatch_platform_mail", send=True, accounts_only=True, stdout=StringIO())
            call_command("dispatch_platform_mail", send=True, accounts_only=True, stdout=StringIO())
            send.assert_called_once()
        self.assertEqual(Attempt.objects.get().delivery_id, row.pk)

    def test_source_database_constraint_and_cross_user_recipient_guard(self):
        row = self.enqueue()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Delivery.objects.create(key="no-source")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Delivery.objects.filter(pk=row.pk).update(account_email=None)
        other = get_user_model().objects.create_user(username="other-mail", email="other@example.test")
        self.assertIsNone(enqueue_account_email(user=other, email=self.address.email,
            email_address=self.address, kind=AccountEmail.Kind.VERIFICATION))
        self.assertEqual(AccountEmail.objects.count(), 1)

    def test_disabled_adapter_keeps_legacy_mail_hook_and_signup_policy(self):
        adapter = get_adapter()
        with override_settings(ACCOUNT_EMAIL_ENABLED=False), \
                patch("allauth.account.adapter.DefaultAccountAdapter.send_confirmation_mail") as legacy:
            adapter.send_confirmation_mail(None, EmailConfirmationHMAC(self.address), True)
            legacy.assert_called_once()
        self.assertFalse(Delivery.objects.exists())
        from django.test import RequestFactory
        request = RequestFactory().get("/")
        request.session = {}
        with override_settings(INVITATIONS_INVITATION_ONLY=True):
            self.assertFalse(adapter.is_open_for_signup(request))
            request.session["account_verified_email"] = self.user.email
            self.assertTrue(adapter.is_open_for_signup(request))

    def test_code_flows_fail_closed(self):
        with override_settings(ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED=True):
            with self.assertRaises(ValidationError):
                self.enqueue()
        self.assertFalse(AccountEmail.objects.exists())


@override_settings(**MAIL_SETTINGS, ACCOUNT_EMAIL_ENABLED=True)
class ConcurrentAccountRequestsTests(TransactionTestCase):
    def test_concurrent_requests_create_one_committed_intent_under_restricted_role(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        user = get_user_model().objects.create_user(username="concurrent-account", email="race@example.test")
        address = EmailAddress.objects.create(user=user, email=user.email)
        role = connection.ops.quote_name("account_mail_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        barrier = Barrier(2)
        def run():
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET ROLE {role}")
                barrier.wait(timeout=10)
                return enqueue_account_email(user=user, email=user.email, email_address=address,
                                              kind=AccountEmail.Kind.VERIFICATION).pk
            finally:
                connections.close_all()
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: run(), range(2)))
            self.assertEqual(results[0], results[1])
            self.assertEqual(AccountEmail.objects.count(), 1)
            self.assertEqual(Delivery.objects.count(), 1)
        finally:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")
