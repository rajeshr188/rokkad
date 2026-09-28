import io
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

import environ
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from apps.configuration.email_checks import check_external_email
from apps.configuration.email_readiness import assess_email_configuration
from django_project.email_configuration import email_settings


class EmailConfigurationTests(SimpleTestCase):
    def read_settings(self, **values):
        with patch.dict(os.environ, values, clear=True):
            return email_settings(environ.Env())

    def effective(self, **overrides):
        values = self.read_settings(
            EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
            EMAIL_HOST="email-smtp.ap-south-1.amazonaws.com",
            PLATFORM_EMAIL_REPLY_TO="support@rokkad.com",
            BILLING_EMAIL_REPLY_TO="billing@rokkad.com",
        )
        return SimpleNamespace(**(values | overrides))

    def test_default_captures_even_with_credentials(self):
        values = self.read_settings(EMAIL_HOST_USER="private-user", EMAIL_HOST_PASSWORD="private-password")
        self.assertEqual(values["EMAIL_BACKEND"], "django.core.mail.backends.locmem.EmailBackend")
        self.assertEqual(values["EMAIL_TIMEOUT"], 15)

    def test_false_string_is_not_truthy_and_numbers_are_typed(self):
        values = self.read_settings(EMAIL_USE_TLS="False", EMAIL_USE_SSL="True", EMAIL_PORT="465", EMAIL_TIMEOUT="20")
        self.assertIs(values["EMAIL_USE_TLS"], False)
        self.assertIs(values["EMAIL_USE_SSL"], True)
        self.assertIs(type(values["EMAIL_PORT"]), int)
        self.assertEqual(values["EMAIL_PORT"], 465)
        self.assertEqual(values["EMAIL_TIMEOUT"], 20)

    def test_invalid_transport_settings_fail_early(self):
        for values in (
            {"EMAIL_USE_TLS": "True", "EMAIL_USE_SSL": "True"},
            {"EMAIL_PORT": "0"}, {"EMAIL_PORT": "65536"},
            {"EMAIL_TIMEOUT": "0"}, {"EMAIL_TIMEOUT": "121"},
        ):
            with self.subTest(values=values), self.assertRaises(ImproperlyConfigured):
                self.read_settings(**values)

    def test_good_configuration_is_not_delivery_evidence(self):
        with patch("apps.configuration.email_readiness.settings", self.effective()):
            report = assess_email_configuration()
        self.assertTrue(report["configuration_valid_for_external_mail"])
        self.assertFalse(report["delivery_verified"])
        self.assertEqual(len(report["unverified"]), 4)

    def test_each_capture_backend_blocks_external_readiness(self):
        for backend in ("locmem", "dummy", "console", "filebased"):
            with self.subTest(backend=backend), patch(
                "apps.configuration.email_readiness.settings",
                self.effective(EMAIL_BACKEND=f"django.core.mail.backends.{backend}.EmailBackend"),
            ):
                report = assess_email_configuration()
                self.assertTrue(report["capture_only"])
                self.assertFalse(report["configuration_valid_for_external_mail"])
                self.assertEqual(check_external_email(None)[0].id, "configuration.W001")

    def test_unsafe_runtime_overrides_are_detected(self):
        for values in (
            {"EMAIL_PORT": "587"}, {"EMAIL_USE_TLS": "False"},
            {"EMAIL_USE_TLS": False}, {"EMAIL_USE_SSL": True},
            {"EMAIL_TIMEOUT": None}, {"EMAIL_TIMEOUT": float("inf")},
            {"EMAIL_HOST": "127.0.0.1"},
            {"EMAIL_BACKEND": "unreviewed.Backend"},
            {"PLATFORM_EMAIL_REPLY_TO": ""},
            {"DEFAULT_FROM_EMAIL": "root@localhost"},
            {"BILLING_EMAIL_SENDER": "billing@rokkad.com\r\nBcc: someone@rokkad.com"},
        ):
            with self.subTest(values=values), patch("apps.configuration.email_readiness.settings", self.effective(**values)):
                self.assertFalse(assess_email_configuration()["configuration_valid_for_external_mail"])

    def test_django_mailers_takes_precedence_over_legacy_settings(self):
        with patch("apps.configuration.email_readiness.settings", self.effective(MAILERS={
            "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"},
        })):
            report = assess_email_configuration()
        self.assertEqual(report["configuration_source"], "MAILERS.default")
        self.assertTrue(report["capture_only"])

    def test_mailers_smtp_options_are_inspected(self):
        with patch("apps.configuration.email_readiness.settings", self.effective(MAILERS={
            "default": {"OPTIONS": {"host": "email-smtp.ap-south-1.amazonaws.com", "use_tls": True, "timeout": 15}},
        })):
            self.assertTrue(assess_email_configuration()["configuration_valid_for_external_mail"])

    def test_empty_mailers_is_not_smtp_fallback(self):
        with patch("apps.configuration.email_readiness.settings", self.effective(MAILERS={})):
            self.assertFalse(assess_email_configuration()["configuration_valid_for_external_mail"])

    def test_command_never_discloses_credentials_or_claims_delivery(self):
        output = io.StringIO()
        with patch("apps.configuration.email_readiness.settings", self.effective(
            EMAIL_HOST_USER="SECRET_USER_VALUE", EMAIL_HOST_PASSWORD="SECRET_PASSWORD_VALUE",
        )):
            call_command("check_email_configuration", format="json", stdout=output)
        report = json.loads(output.getvalue())
        self.assertFalse(report["delivery_verified"])
        self.assertNotIn("SECRET_", output.getvalue())

    def test_command_can_enforce_deployment_gate(self):
        with patch("apps.configuration.email_readiness.settings", self.effective(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        )), self.assertRaises(CommandError):
            call_command("check_email_configuration", require_external_config=True, stdout=io.StringIO())
