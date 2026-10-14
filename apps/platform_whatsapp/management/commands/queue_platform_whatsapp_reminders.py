from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from apps.orgs.models import Company
from apps.platform_whatsapp.reminders import queue_trial_reminder


class Command(BaseCommand):
    help = "Capture at most one current trial reminder per explicit Workspace; never dispatch."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-ids", type=int, nargs="+", required=True)

    def handle(self, *args, **options):
        ids = options["workspace_ids"]
        if not 1 <= len(ids) <= 100 or len(set(ids)) != len(ids) or any(i <= 0 for i in ids):
            raise CommandError("Provide 1 to 100 distinct positive Workspace IDs.")
        for workspace_id in ids:
            try:
                row = queue_trial_reminder(workspace_id=workspace_id)
            except (PermissionDenied, ValidationError, Company.DoesNotExist):
                raise CommandError("Reminder turn unavailable; check explicit scope and source.") from None
            self.stdout.write(f"Workspace {workspace_id}: {row.pk if row else 'no current reminder'}")
