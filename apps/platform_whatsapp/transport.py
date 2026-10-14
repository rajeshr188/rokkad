"""One bounded Meta Cloud request. No redirects, ambient proxies or HTTP retries."""
import json
import re

import requests
from django.conf import settings
from django.db import connection
from requests.adapters import HTTPAdapter

from .configuration import transport_blockers
from .models import Attempt

MAX_RESPONSE_BYTES = 65536
MESSAGE_ID = re.compile(r"wamid\.[A-Za-z0-9_=/+.-]{1,249}")


class TransportFailure(Exception):
    def __init__(self, code, *, outcome=Attempt.Outcome.UNKNOWN, retryable=False, http_status=None):
        self.code, self.outcome, self.retryable, self.http_status = code, outcome, retryable, http_status
        super().__init__(code)


def valid_message_id(value):
    return isinstance(value, str) and MESSAGE_ID.fullmatch(value) is not None


def send_cloud(payload):
    if connection.in_atomic_block or transport_blockers():
        raise TransportFailure("transport_unavailable", outcome=Attempt.Outcome.CANCELLED)
    if not isinstance(payload, dict) or payload.get("type") != "template" or payload.get("messaging_product") != "whatsapp":
        raise TransportFailure("invalid_template_request", outcome=Attempt.Outcome.CANCELLED)
    endpoint = ("https://graph.facebook.com/" + settings.PLATFORM_WHATSAPP_API_VERSION + "/" +
                settings.PLATFORM_WHATSAPP_PHONE_ID + "/messages")
    try:
        with requests.Session() as session:
            session.trust_env = False
            session.mount("https://", HTTPAdapter(max_retries=0))
            with session.post(endpoint, json=payload,
                    headers={"Authorization": "Bearer " + settings.PLATFORM_WHATSAPP_ACCESS_TOKEN},
                    timeout=(5, 20), allow_redirects=False, stream=True) as response:
                chunks, size = [], 0
                for chunk in response.iter_content(chunk_size=4096):
                    size += len(chunk)
                    if size > MAX_RESPONSE_BYTES:
                        raise TransportFailure("provider_response_too_large", http_status=response.status_code)
                    chunks.append(chunk)
                try:
                    data = json.loads(b"".join(chunks))
                except (ValueError, UnicodeDecodeError):
                    raise TransportFailure("invalid_provider_response", http_status=response.status_code) from None
                if not isinstance(data, dict):
                    raise TransportFailure("invalid_provider_response", http_status=response.status_code)
                messages = data.get("messages")
                if response.status_code == 200 and not data.get("error") and isinstance(messages, list) and len(messages) == 1:
                    message_id = messages[0].get("id") if isinstance(messages[0], dict) else None
                    if valid_message_id(message_id):
                        contacts = data.get("contacts")
                        if contacts is not None and (not isinstance(contacts, list) or len(contacts) != 1
                                or not isinstance(contacts[0], dict) or contacts[0].get("wa_id") != payload["to"]):
                            raise TransportFailure("provider_recipient_uncertain", http_status=200)
                        return message_id
                error = data.get("error")
                if (400 <= response.status_code < 500 and not messages and isinstance(error, dict)
                        and type(error.get("code")) is int and 0 <= error["code"] <= 2147483647):
                    raise TransportFailure("provider_rejected", outcome=Attempt.Outcome.REJECTED,
                        retryable=response.status_code == 429 or error.get("is_transient") is True,
                        http_status=response.status_code)
                raise TransportFailure("provider_acceptance_uncertain", http_status=response.status_code)
    except TransportFailure:
        raise
    except (requests.RequestException, OSError, ValueError, KeyError, TypeError):
        # Never persist/log exception text, tokens, recipient or raw provider bodies.
        raise TransportFailure("provider_connection_uncertain") from None
