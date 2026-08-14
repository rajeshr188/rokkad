from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from apps.tenant_apps.notify_v2.services.whatsapp_integration import (
    _decrypt, _encrypt, set_whatsapp_cloud_integration,
)


class WhatsAppCloudIntegrationTests(TestCase):
    @override_settings(WORKSPACE_SECRET_ENCRYPTION_KEY="lHcKWFYTr7srGTRy2gq31ALX5RzzX_UkI95mGaSeP-8=")
    def test_workspace_secrets_are_encrypted_and_round_trip(self):
        ciphertext = _encrypt("workspace-secret")
        self.assertNotIn("workspace-secret", ciphertext)
        self.assertEqual(_decrypt(ciphertext), "workspace-secret")

    @override_settings(WORKSPACE_SECRET_ENCRYPTION_KEY="")
    def test_missing_master_key_fails_closed(self):
        with self.assertRaises(ImproperlyConfigured):
            _encrypt("workspace-secret")

    @override_settings(WORKSPACE_SECRET_ENCRYPTION_KEY="lHcKWFYTr7srGTRy2gq31ALX5RzzX_UkI95mGaSeP-8=")
    @patch("apps.tenant_apps.notify_v2.services.whatsapp_integration.WhatsAppCloudIntegration")
    def test_blank_secret_update_preserves_existing_ciphertext(self, integration_model):
        integration = SimpleNamespace(
            api_version="v20.0", phone_number_id="old-phone", is_enabled=True,
            updated_by=None, access_token_ciphertext="access-cipher",
            webhook_verify_token_ciphertext="verify-cipher", app_secret_ciphertext="secret-cipher",
            full_clean=MagicMock(), save=MagicMock(),
        )
        integration_model.objects.select_for_update.return_value.filter.return_value.first.return_value = integration
        set_whatsapp_cloud_integration(
            workspace_id=4, actor=None, api_version="v21.0", phone_number_id="new-phone",
            is_enabled=True,
        )
        self.assertEqual(integration.access_token_ciphertext, "access-cipher")
        self.assertEqual(integration.webhook_verify_token_ciphertext, "verify-cipher")
        self.assertEqual(integration.app_secret_ciphertext, "secret-cipher")
        integration.save.assert_called_once()
