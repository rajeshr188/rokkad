import json
from urllib.parse import urlsplit

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.platform_mail.events import reconcile_sqs_envelope
from apps.platform_mail.transport import aws_client, TransportFailure


class Command(BaseCommand):
    help = "Read a bounded batch of private SES/SNS feedback from the configured SQS queue."

    def handle(self, *args, **options):
        queue = settings.PLATFORM_SES_EVENTS_QUEUE_URL
        parsed = urlsplit(queue)
        expected_host = f"sqs.{settings.PLATFORM_SES_REGION}.amazonaws.com"
        if (parsed.scheme != "https" or parsed.netloc != expected_host or
                not parsed.path.startswith(f"/{settings.PLATFORM_SES_ACCOUNT_ID}/") or
                parsed.query or parsed.fragment):
            raise CommandError("Configure the expected private regional SQS queue URL.")
        try:
            client = aws_client("sqs")
            messages = client.receive_message(QueueUrl=queue, MaxNumberOfMessages=10, WaitTimeSeconds=10).get("Messages", [])
            rejected = 0
            for item in messages:
                try:
                    reconcile_sqs_envelope(json.loads(item["Body"]))
                except (ValueError, TypeError, KeyError, ValidationError):
                    # Leave rejected messages for bounded redrive to the queue's DLQ.
                    self.stderr.write("Rejected event; retained for queue redrive. Inspect privately.")
                    rejected += 1
                    continue
                # Only acknowledge after the database transaction has committed.
                client.delete_message(QueueUrl=queue, ReceiptHandle=item["ReceiptHandle"])
            self.stdout.write(f"Read {len(messages)} event(s).")
            if rejected:
                raise CommandError(f"{rejected} event(s) rejected; operator review required.")
        except (BotoCoreError, ClientError, TransportFailure):
            raise CommandError("SES event queue access failed; check private runtime configuration.") from None
