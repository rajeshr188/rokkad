"""SES API transport. SDK retries are disabled to preserve uncertain outcomes."""
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

from .models import Delivery


class TransportFailure(Exception):
    def __init__(self, code, *, outcome=Delivery.Status.FAILED, retryable=False):
        self.code, self.outcome, self.retryable = code, outcome, retryable
        super().__init__(code)


def aws_client(service):
    # Never fall through to the R2 keys or an ambient administrator credential.
    if not all((settings.PLATFORM_SES_REGION, settings.PLATFORM_SES_ACCESS_KEY_ID,
                settings.PLATFORM_SES_SECRET_ACCESS_KEY)):
        raise TransportFailure("ses_credentials_missing")
    return boto3.client(
        service, region_name=settings.PLATFORM_SES_REGION,
        aws_access_key_id=settings.PLATFORM_SES_ACCESS_KEY_ID,
        aws_secret_access_key=settings.PLATFORM_SES_SECRET_ACCESS_KEY,
        config=Config(connect_timeout=5, read_timeout=20, retries={"total_max_attempts": 1}),
    )


def send_ses(message, *, delivery_id, attempt_id):
    if not settings.PLATFORM_SES_CONFIGURATION_SET:
        raise TransportFailure("ses_configuration_set_missing")
    try:
        response = aws_client("sesv2").send_email(
            FromEmailAddress=message["sender"], ReplyToAddresses=[message["reply_to"]],
            Destination={"ToAddresses": [message["recipient"]]},
            Content={"Simple": {
                "Subject": {"Data": message["subject"], "Charset": "UTF-8"},
                "Body": {"Text": {"Data": message["text"], "Charset": "UTF-8"},
                         "Html": {"Data": message["html"], "Charset": "UTF-8"}},
            }}, ConfigurationSetName=settings.PLATFORM_SES_CONFIGURATION_SET,
            EmailTags=[{"Name": "rokkad_delivery", "Value": str(delivery_id)},
                       {"Name": "rokkad_attempt", "Value": str(attempt_id)}],
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"TooManyRequestsException", "Throttling", "ThrottlingException", "LimitExceededException"}:
            raise TransportFailure("ses_throttled", retryable=True) from None
        if code in {"MessageRejected", "MailFromDomainNotVerifiedException", "BadRequestException",
                    "NotFoundException", "SendingPausedException", "AccountSuspendedException",
                    "AccessDeniedException", "AccessDenied", "InvalidClientTokenId", "SignatureDoesNotMatch"}:
            raise TransportFailure("ses_rejected") from None
        raise TransportFailure("ses_acceptance_uncertain", outcome=Delivery.Status.UNKNOWN) from None
    except BotoCoreError:
        raise TransportFailure("ses_connection_uncertain", outcome=Delivery.Status.UNKNOWN) from None
    message_id = response.get("MessageId")
    if not isinstance(message_id, str) or not message_id or len(message_id) > 255:
        raise TransportFailure("ses_missing_message_id", outcome=Delivery.Status.UNKNOWN)
    return message_id
