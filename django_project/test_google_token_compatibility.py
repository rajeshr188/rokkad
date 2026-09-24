"""Exercise the Google/allauth/JWT boundary without contacting a provider."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from django.test import SimpleTestCase

from allauth.socialaccount.providers.google.views import _verify_and_decode
from allauth.socialaccount.providers.oauth2.client import OAuth2Error


class GoogleTokenCompatibilityTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-only")])
        now = datetime.now(timezone.utc)
        certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(cls.key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=1)).sign(cls.key, hashes.SHA256()))
        cls.certificate = certificate.public_bytes(serialization.Encoding.PEM).decode()

    def setUp(self):
        self.app = SimpleNamespace(client_id="google-client-test-only")
        self.claims = {"iss": "https://accounts.google.com", "aud": self.app.client_id,
                       "sub": "google-subject-test-only", "email": "owner@example.test",
                       "email_verified": True, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
        adapter = MagicMock()
        session = adapter.get_requests_session.return_value.__enter__.return_value
        session.get.return_value.json.return_value = {"test-key": self.certificate}
        self.patch = patch("allauth.socialaccount.internal.jwtkit.get_adapter", return_value=adapter)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def token(self, **changes):
        return jwt.encode(self.claims | changes, self.key, algorithm="RS256", headers={"kid": "test-key"})

    def test_google_rsa_token_preserves_verified_identity(self):
        data = _verify_and_decode(self.app, self.token())
        self.assertEqual(data["sub"], self.claims["sub"])
        self.assertEqual(data["email"], self.claims["email"])
        self.assertIs(data["email_verified"], True)

    def test_wrong_audience_issuer_and_expiry_are_rejected(self):
        for changes in ({"aud": "another-client"}, {"iss": "https://other.example.test"},
                        {"exp": datetime.now(timezone.utc) - timedelta(minutes=1)}):
            with self.subTest(changes=changes), self.assertRaises(OAuth2Error):
                _verify_and_decode(self.app, self.token(**changes))

    def test_foreign_signing_key_is_rejected(self):
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = jwt.encode(self.claims, other_key, algorithm="RS256", headers={"kid": "test-key"})
        with self.assertRaises(OAuth2Error):
            _verify_and_decode(self.app, token)

    def test_hmac_token_cannot_use_the_google_rsa_key(self):
        token = jwt.encode(self.claims, "test-only-secret-" * 4, algorithm="HS256", headers={"kid": "test-key"})
        # PyJWT rejects an RSA key object supplied to HMAC with TypeError;
        # allauth normalizes PyJWTError only. Neither may yield an identity.
        with self.assertRaises((OAuth2Error, TypeError)):
            _verify_and_decode(self.app, token)

    def test_tls_token_exchange_still_checks_identity_claims(self):
        self.assertEqual(_verify_and_decode(self.app, self.token(), verify_signature=False)["sub"], self.claims["sub"])
        for changes in ({"aud": "another-client"}, {"iss": "https://other.example.test"},
                        {"exp": datetime.now(timezone.utc) - timedelta(minutes=1)}):
            with self.subTest(changes=changes), self.assertRaises(OAuth2Error):
                _verify_and_decode(self.app, self.token(**changes), verify_signature=False)
