from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.orgs.services.storage_inventory import reconcile_storage


class Command(BaseCommand):
    help = "Reconcile the configured application media prefix; never delete or download objects."

    def add_arguments(self, parser):
        parser.add_argument("--actor-id", type=int, required=True)

    def handle(self, *args, **options):
        actor = get_user_model().objects.get(pk=options["actor_id"])
        try:
            run = reconcile_storage(actor=actor)
        except Exception as exc:
            # Provider exceptions can contain URLs/request details. Keep unattended logs bounded.
            raise CommandError(f"Inventory failed ({type(exc).__name__}); previous successful usage retained.") from None
        self.stdout.write(f"Storage inventory {run.pk}: complete; no object changes.")
