from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction

from apps.tenant_apps.notify_v2.models import WhatsAppCloudIntegration


class WhatsAppIntegrationError(ValueError):
    pass


@dataclass(frozen=True)
class WhatsAppCloudCredentials:
    api_version: str
    phone_number_id: str
    access_token: str
    webhook_verify_token: str
    app_secret: str


def _cipher():
    key = (getattr(settings, "WORKSPACE_SECRET_ENCRYPTION_KEY", "") or "").strip()
    if not key:
        raise ImproperlyConfigured("WORKSPACE_SECRET_ENCRYPTION_KEY is not configured.")
    try:
        return Fernet(key.encode())
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured("WORKSPACE_SECRET_ENCRYPTION_KEY is not a valid Fernet key.") from exc


def _encrypt(value):
    return _cipher().encrypt(value.strip().encode()).decode()


def _decrypt(value):
    try:
        return _cipher().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise WhatsAppIntegrationError("Workspace WhatsApp credentials cannot be decrypted.") from exc


def get_whatsapp_cloud_integration(workspace_id):
    return WhatsAppCloudIntegration.objects.filter(workspace_id=workspace_id).first()


def get_whatsapp_cloud_credentials(workspace_id, *, require_enabled=True):
    integration = get_whatsapp_cloud_integration(workspace_id)
    if integration is None or (require_enabled and not integration.is_enabled):
        return None
    return WhatsAppCloudCredentials(
        api_version=integration.api_version,
        phone_number_id=integration.phone_number_id,
        access_token=_decrypt(integration.access_token_ciphertext),
        webhook_verify_token=_decrypt(integration.webhook_verify_token_ciphertext),
        app_secret=_decrypt(integration.app_secret_ciphertext),
    )


@transaction.atomic
def set_whatsapp_cloud_integration(
    *, workspace_id, actor, api_version, phone_number_id, access_token="",
    webhook_verify_token="", app_secret="", is_enabled=False,
):
    integration = WhatsAppCloudIntegration.objects.select_for_update().filter(
        workspace_id=workspace_id
    ).first()
    if integration is None and not all((access_token, webhook_verify_token, app_secret)):
        raise WhatsAppIntegrationError("All three secrets are required for initial setup.")
    if integration is None:
        integration = WhatsAppCloudIntegration(workspace_id=workspace_id)
    integration.api_version = api_version.strip()
    integration.phone_number_id = phone_number_id.strip()
    integration.is_enabled = is_enabled
    integration.updated_by = actor
    if access_token:
        integration.access_token_ciphertext = _encrypt(access_token)
    if webhook_verify_token:
        integration.webhook_verify_token_ciphertext = _encrypt(webhook_verify_token)
    if app_secret:
        integration.app_secret_ciphertext = _encrypt(app_secret)
    if not integration.api_version or not integration.phone_number_id:
        raise WhatsAppIntegrationError("API version and phone-number ID are required.")
    integration.full_clean()
    integration.save()
    return integration


__all__ = [
    "WhatsAppCloudCredentials", "WhatsAppIntegrationError",
    "get_whatsapp_cloud_credentials", "get_whatsapp_cloud_integration",
    "set_whatsapp_cloud_integration",
]
