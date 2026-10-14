from django.core.exceptions import PermissionDenied
from django.core.management.base import BaseCommand, CommandError
from apps.platform_whatsapp.dispatch import reconcile_delivery
from apps.platform_whatsapp.models import Delivery


class Command(BaseCommand):
    help = "Reconcile up to 100 new receipts/attempt for one explicit Workspace/delivery; never sends."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, required=True)
        parser.add_argument("--delivery-id", type=int, required=True)
        parser.add_argument("--recover-stale", action="store_true")

    def handle(self, *args, **options):
        if options["workspace_id"] <= 0 or options["delivery_id"] <= 0:
            raise CommandError("Positive Workspace and delivery IDs are required.")
        try:
            summary = reconcile_delivery(workspace_id=options["workspace_id"], delivery_id=options["delivery_id"],
                                         recover_stale=options["recover_stale"])
        except (PermissionDenied, Delivery.DoesNotExist):
            raise CommandError("Reconciliation requires a restricted role and exact owned source.") from None
        self.stdout.write(summary["status"] + ("; provider conflict needs review" if summary["conflict"] else ""))
