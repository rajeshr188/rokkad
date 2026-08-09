import json

from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import get_tenant_model, schema_context

from ...pilot import run_acceptance_pilot


class Command(BaseCommand):
    help = "Run the guarded synthetic standalone-accounting acceptance pilot."

    def add_arguments(self, parser):
        parser.add_argument("--schema", required=True)
        parser.add_argument("--actor-id", required=True, type=int)
        parser.add_argument("--confirm-synthetic", action="store_true")

    def handle(self, *args, **options):
        schema = options["schema"]
        if not options["confirm_synthetic"]:
            raise CommandError("Pass --confirm-synthetic to acknowledge synthetic writes.")
        if not schema.startswith("accounting_pilot_"):
            raise CommandError("Schema must start with accounting_pilot_.")
        tenant = get_tenant_model().objects.filter(schema_name=schema).first()
        if tenant is None:
            raise CommandError(f"Tenant schema {schema!r} does not exist.")
        if options["actor_id"] != tenant.owner_id:
            raise CommandError("Sandbox actor must be the dedicated tenant owner.")
        with schema_context(schema):
            result = run_acceptance_pilot(actor_id=options["actor_id"])
        self.stdout.write(self.style.SUCCESS(json.dumps(result, indent=2, sort_keys=True)))
