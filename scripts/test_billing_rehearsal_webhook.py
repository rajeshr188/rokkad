import hashlib
import hmac
from io import BytesIO
import unittest
from unittest.mock import Mock

from scripts.billing_rehearsal_webhook import CALLBACK_PATH, MAX_BODY, callback_only


class CallbackBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.downstream = Mock(return_value=[b"ok"])
        self.app = callback_only(self.downstream, "fixture")
        raw = b'{"event":"payment.authorized"}'
        self.environ = {"PATH_INFO": CALLBACK_PATH, "REQUEST_METHOD": "POST",
            "QUERY_STRING": "", "CONTENT_LENGTH": str(len(raw)), "wsgi.input": BytesIO(raw),
            "HTTP_X_RAZORPAY_SIGNATURE": hmac.new(b"fixture", raw, hashlib.sha256).hexdigest(),
            "HTTP_X_RAZORPAY_EVENT_ID": "event_fixture", "HTTP_HOST": "public.example.test",
            "HTTP_COOKIE": "session=private", "HTTP_AUTHORIZATION": "Bearer private",
            "HTTP_X_FORWARDED_HOST": "other-workspace.example.test"}

    def test_preserves_signed_bytes_but_discards_browser_auth_and_workspace_hosts(self):
        self.assertEqual(self.app(self.environ, Mock()), [b"ok"])
        forwarded = self.downstream.call_args.args[0]
        self.assertEqual(forwarded["wsgi.input"].read(), b'{"event":"payment.authorized"}')
        self.assertEqual(forwarded["HTTP_HOST"], "127.0.0.1")
        self.assertEqual(forwarded["HTTP_X_RAZORPAY_EVENT_ID"], "event_fixture")
        for key in ("HTTP_COOKIE", "HTTP_AUTHORIZATION", "HTTP_X_FORWARDED_HOST"):
            self.assertNotIn(key, forwarded)

    def test_rejects_unrelated_paths_methods_and_queries(self):
        for key, value in (("PATH_INFO", "/"), ("PATH_INFO", "/accounts/login/"),
                           ("REQUEST_METHOD", "GET"), ("QUERY_STRING", "next=/")):
            with self.subTest(key=key, value=value):
                response = Mock()
                self.assertEqual(self.app({**self.environ, key:value}, response), [b""])
                self.assertEqual(response.call_args.args[0], "404 Not Found")
        self.downstream.assert_not_called()

    def test_rejects_unsigned_malformed_and_oversized_requests(self):
        for key, value in (("HTTP_X_RAZORPAY_SIGNATURE", "invalid"),
                           ("HTTP_X_RAZORPAY_SIGNATURE", "\u20b9"),
                           ("CONTENT_LENGTH", "unknown"), ("CONTENT_LENGTH", str(MAX_BODY + 1)),
                           ("CONTENT_LENGTH", "0"), ("HTTP_TRANSFER_ENCODING", "chunked")):
            with self.subTest(key=key, value=value):
                response = Mock()
                self.environ["wsgi.input"].seek(0)
                self.assertEqual(self.app({**self.environ, key:value}, response), [b""])
                self.assertTrue(response.call_args.args[0].startswith(("400", "413")))
        self.downstream.assert_not_called()


if __name__ == "__main__":
    unittest.main()
