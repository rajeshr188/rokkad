import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.orgs.models import Company
from apps.tenant_apps.loans.services.khata_readiness import assess_readiness


class Command(BaseCommand):
    help = "Read-only khata software checks and manual pilot acceptance gates; never activates a Workspace."

    def add_arguments(self, parser):
        parser.add_argument("--workspace", required=True)
        parser.add_argument("--actor", required=True, type=int)

    def handle(self, *args, **options):
        try:
            report = assess_readiness(workspace=Company.objects.get(slug=options["workspace"]),
                actor=get_user_model().objects.get(pk=options["actor"]))
        except (ValueError, Company.DoesNotExist, get_user_model().DoesNotExist) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
        if not report["software_ready"]:
            raise CommandError("Khata software readiness has failing checks; pilot activation is not authorized.")
