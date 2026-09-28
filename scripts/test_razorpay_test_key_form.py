import threading
import unittest
from unittest.mock import Mock, patch

import requests

from scripts import razorpay_test_key_form as entry


class KeyFormTests(unittest.TestCase):
    def setUp(self):
        self.save = Mock()
        self.server = entry.FormServer(self.save)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.session = requests.Session()
        self.session.trust_env = False
        self.status = patch.object(entry, "status").start()

    def tearDown(self):
        patch.stopall()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.session.close()

    def post(self, **changes):
        data = {"token": self.server.token, "key_id": "rzp_test_synthetic", "key_secret": "synthetic-secret"}
        data.update(changes.pop("data", {}))
        return self.session.post(self.server.origin + "/submit", data=data,
                                 headers={"Origin": changes.get("origin", self.server.origin)}, timeout=3)

    def test_live_key_never_contacts_provider_or_saves(self):
        with patch.object(entry.requests, "Session") as provider:
            response = self.post(data={"key_id": "rzp_live_synthetic"})
        self.assertEqual(response.status_code, 400)
        provider.assert_not_called()
        self.save.assert_not_called()
        self.assertNotIn("synthetic-secret", response.text)

    def test_cross_origin_and_invalid_token_never_verify(self):
        with patch.object(entry, "verify") as verify:
            self.assertEqual(self.post(origin="https://example.test").status_code, 403)
            self.assertEqual(self.post(data={"token": "wrong"}).status_code, 400)
        verify.assert_not_called()
        self.save.assert_not_called()

    def test_success_saves_once_and_page_never_echoes_credentials(self):
        with patch.object(entry, "verify", return_value=True):
            response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.server.done)
        self.save.assert_called_once_with("rzp_test_synthetic", "synthetic-secret")
        self.assertNotIn("synthetic-secret", response.text)
        self.assertNotIn("rzp_test_synthetic", response.text)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["Referrer-Policy"], "same-origin")
        self.status.assert_called_with("verified_and_saved")

    def test_failure_does_not_save_or_echo_exception(self):
        self.save.side_effect = RuntimeError("synthetic-secret")
        with patch.object(entry, "verify", return_value=True):
            response = self.post()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("synthetic-secret", response.text)
        self.assertFalse(self.server.done)

    def test_provider_request_is_fixed_read_only_and_redirects_disabled(self):
        with patch.object(entry.requests, "Session") as factory:
            session = factory.return_value.__enter__.return_value
            session.get.return_value.status_code = 200
            session.get.return_value.json.return_value = {"entity": "collection", "items": []}
            self.assertTrue(entry.verify("rzp_test_synthetic", "synthetic-secret"))
            session.get.assert_called_once_with("https://api.razorpay.com/v1/payments?count=1",
                auth=("rzp_test_synthetic", "synthetic-secret"), timeout=(10, 20), allow_redirects=False)
            self.assertFalse(session.trust_env)


if __name__ == "__main__":
    unittest.main()
