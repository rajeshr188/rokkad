"""Credential lookup uses the canonical Workspace context and fails closed."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from .services.delivery_service import _whatsapp_cloud_settings


class DeliveryCredentialContextTests(SimpleTestCase):
    @patch(
        "apps.tenant_apps.notify_v2.services.delivery_service.get_whatsapp_cloud_credentials"
    )
    @patch("apps.tenant_apps.notify_v2.services.delivery_service.current_workspace_id")
    def test_uses_current_workspace_id(self, context, credentials):
        context.return_value = 37
        credentials.return_value = SimpleNamespace(
            api_version="v20.0",
            phone_number_id="fixture-id",
            access_token="fixture-token",
        )
        self.assertEqual(
            _whatsapp_cloud_settings(),
            {
                "api_version": "v20.0",
                "phone_number_id": "fixture-id",
                "access_token": "fixture-token",
            },
        )
        credentials.assert_called_once_with(37)

    @patch(
        "apps.tenant_apps.notify_v2.services.delivery_service.get_whatsapp_cloud_credentials"
    )
    @patch(
        "apps.tenant_apps.notify_v2.services.delivery_service.current_workspace_id",
        return_value=None,
    )
    def test_no_workspace_does_not_read_credentials(self, context, credentials):
        self.assertEqual(
            _whatsapp_cloud_settings(),
            {"api_version": "", "phone_number_id": "", "access_token": ""},
        )
        credentials.assert_not_called()
