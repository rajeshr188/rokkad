import getpass
import sys

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.platform_mail.operations import suppress_recipient


class Command(BaseCommand):
    help = "Deployment-operator-only suppression with attribution and a request reference."

    def add_arguments(self, parser):
        parser.add_argument("--operator", required=True)
        parser.add_argument("--reference", required=True)
        parser.add_argument("--recipient-stdin", action="store_true")

    def handle(self, *args, **options):
        recipient = sys.stdin.readline().strip() if options["recipient_stdin"] else getpass.getpass("Recipient (hidden): ")
        try:
            _, created = suppress_recipient(operator=options["operator"], recipient=recipient, reference=options["reference"])
        except ValidationError:
            raise CommandError("Suppression refused: check operator identifier, address and request reference.") from None
        self.stdout.write("Recipient suppressed." if created else "Recipient already suppressed; request audited.")
