from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from apps.platform_whatsapp.dispatch import dispatch_one
from apps.platform_whatsapp.models import Delivery


class Command(BaseCommand):
    help = "Dispatch one explicitly scoped non-capture source; dated pilot controls and daily reservations are required."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, required=True)
        parser.add_argument("--delivery-id", type=int, required=True)

    def handle(self, *args, **options):
        if options["workspace_id"] <= 0 or options["delivery_id"] <= 0:
            raise CommandError("Positive Workspace and delivery IDs are required.")
        try:
            status = dispatch_one(workspace_id=options["workspace_id"], delivery_id=options["delivery_id"])
        except (ValidationError, PermissionDenied, Delivery.DoesNotExist):
            raise CommandError("Dispatch unavailable; check source, authority and private readiness diagnostics.") from None
        self.stdout.write(status)
