"""Cloud request classification: all provider IO is mocked."""
import json
from unittest.mock import patch

import requests
from django.db import connection
from django.test import SimpleTestCase, override_settings

from .configuration import transport_blockers
from .intents import TEMPLATE_REVISION
from .models import Attempt
from .tests import INBOUND
from .transport import send_cloud, TransportFailure

SEND = {**INBOUND, "PLATFORM_WHATSAPP_RETENTION_REFERENCE": "fictional-policy-1",
    "PLATFORM_WHATSAPP_SUPPORT_MONITOR": "fictional-support-monitor", "PLATFORM_WHATSAPP_DISPATCH_ENABLED": True,
    "PLATFORM_WHATSAPP_ACCESS_TOKEN": "fictional-private-token", "PLATFORM_WHATSAPP_API_VERSION": "v99.0",
    "PLATFORM_WHATSAPP_TEMPLATES": {purpose: {"name": "fictional_"+purpose, "language": "en",
        "revision": TEMPLATE_REVISION, "approved": True} for purpose in ("setup", "trial", "paid")}}
PAYLOAD = {"messaging_product": "whatsapp", "to": "919876543210", "type": "template",
           "template": {"name": "fictional_setup", "language": {"code": "en"}}}


@override_settings(**SEND)
class TransportTests(SimpleTestCase):
    def provider(self, status=200, data=None, raw=None):
        factory = patch("apps.platform_whatsapp.transport.requests.Session").start()
        self.addCleanup(patch.stopall)
        session = factory.return_value.__enter__.return_value
        response = session.post.return_value.__enter__.return_value
        response.status_code = status
        response.iter_content.return_value = [raw if raw is not None else json.dumps(data).encode()]
        return session

    def send(self):
        with patch("apps.platform_whatsapp.configuration.release_blockers", return_value=[]):
            return send_cloud(PAYLOAD)

    def test_complete_configuration_cannot_bypass_missing_release_controls(self):
        session = self.provider(data={"messages": [{"id": "wamid.actual_fixture"}]})
        self.assertIn("dated_pilot_controls_required", transport_blockers())
        with self.assertRaises(TransportFailure) as error:
            send_cloud(PAYLOAD)
        self.assertEqual(error.exception.outcome, Attempt.Outcome.CANCELLED)
        session.post.assert_not_called()

    def test_request_requires_no_outer_transaction(self):
        session = self.provider(data={"messages": [{"id": "wamid.actual_fixture"}]})
        with patch.object(connection, "in_atomic_block", True), self.assertRaises(TransportFailure):
            self.send()
        session.post.assert_not_called()

    def test_real_format_id_records_acceptance_and_uses_one_fixed_endpoint(self):
        session = self.provider(data={"messages": [{"id": "wamid.actual_fixture"}],
                                      "contacts": [{"wa_id": PAYLOAD["to"]}]})
        self.assertEqual(self.send(), "wamid.actual_fixture")
        session.post.assert_called_once()
        args, kwargs = session.post.call_args
        self.assertEqual(args[0], "https://graph.facebook.com/v99.0/12345/messages")
        self.assertEqual(kwargs["timeout"], (5, 20))
        self.assertFalse(kwargs["allow_redirects"])
        self.assertTrue(kwargs["stream"])
        self.assertFalse(session.trust_env)
        self.assertEqual(session.mount.call_args.args[1].max_retries.total, 0)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer fictional-private-token")

    def test_missing_synthetic_or_malformed_ids_are_unknown_not_success(self):
        for message in ({}, {"id": ""}, {"id": "invented-uuid"}, {"id": "wamid. bad"}, {"id": "wamid."+"a"*250}):
            with self.subTest(message=message):
                self.provider(data={"messages": [message]})
                with self.assertRaises(TransportFailure) as error:
                    self.send()
                self.assertEqual(error.exception.outcome, Attempt.Outcome.UNKNOWN)
                self.assertFalse(error.exception.retryable)

    def test_multiple_ids_or_wrong_recipient_are_unknown(self):
        for data in ({"messages": [{"id": "wamid.one"}, {"id": "wamid.two"}]},
                     {"messages": [{"id": "wamid.one"}], "contacts": [{"wa_id": "919876543211"}]}):
            self.provider(data=data)
            with self.assertRaises(TransportFailure) as error:
                self.send()
            self.assertEqual(error.exception.outcome, Attempt.Outcome.UNKNOWN)

    def test_non_json_or_oversized_success_is_unknown(self):
        for raw in (b"not json", b"x"*65537, b"[]"):
            self.provider(raw=raw)
            with self.assertRaises(TransportFailure) as error:
                self.send()
            self.assertEqual(error.exception.outcome, Attempt.Outcome.UNKNOWN)

    def test_structured_rejection_is_definite_and_bounded_transient_is_retryable(self):
        for status, transient, retryable in ((400, False, False), (429, False, True), (400, True, True)):
            self.provider(status=status, data={"error": {"code": 123, "is_transient": transient,
                                                       "message": "private details not retained"}})
            with self.assertRaises(TransportFailure) as error:
                self.send()
            self.assertEqual(error.exception.outcome, Attempt.Outcome.REJECTED)
            self.assertEqual(error.exception.retryable, retryable)
            self.assertEqual(str(error.exception), "provider_rejected")

    def test_server_errors_redirects_and_unclassified_rejections_are_unknown(self):
        for status,data in ((503,{"error": {"code": 123}}), (302,{}), (400,{"error": {"code": "bad"}}),
                            (400,{"messages": [{"id": "wamid.conflict"}], "error": {"code": 123}}),
                            (200,{"messages": [{"id": "wamid.conflict"}], "error": {"code": 123}})):
            self.provider(status=status, data=data)
            with self.assertRaises(TransportFailure) as error:
                self.send()
            self.assertEqual(error.exception.outcome, Attempt.Outcome.UNKNOWN)
            self.assertFalse(error.exception.retryable)

    def test_connection_timeout_and_exception_text_remain_private(self):
        session = self.provider(data={})
        for exception in (requests.Timeout("fictional-private-token"), requests.ConnectionError("919876543210")):
            session.post.side_effect = exception
            with self.assertRaises(TransportFailure) as error:
                self.send()
            self.assertEqual(str(error.exception), "provider_connection_uncertain")
            self.assertEqual(error.exception.outcome, Attempt.Outcome.UNKNOWN)

    def test_disabled_or_invalid_version_never_issues_a_request(self):
        session = self.provider(data={})
        for changes in ({"PLATFORM_WHATSAPP_DISPATCH_ENABLED": False},
                        {"PLATFORM_WHATSAPP_API_VERSION": "../../elsewhere"},
                        {"PLATFORM_WHATSAPP_ACCESS_TOKEN": "bad\nheader"}):
            with override_settings(**changes), self.assertRaises(TransportFailure):
                self.send()
        session.post.assert_not_called()
