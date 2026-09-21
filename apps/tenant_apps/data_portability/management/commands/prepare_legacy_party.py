from django.core.management.base import BaseCommand, CommandError

from apps.tenant_apps.data_portability.legacy_dump import inspect_archive
from apps.tenant_apps.data_portability.legacy_party_preparation import build_party_preparation, write_party_preparation
from apps.tenant_apps.data_portability.legacy_profiles import PROFILES, get_profile
from apps.tenant_apps.data_portability.parsers import PortabilityError


class Command(BaseCommand):
    help = "Prepare chunked Party staging JSONL from one reviewed Linode source schema. No database writes."
    requires_system_checks = []
    requires_migrations_checks = False

    def add_arguments(self, parser):
        parser.add_argument("--dump", required=True)
        parser.add_argument("--pg-restore", default="pg_restore")
        parser.add_argument("--source-schema", required=True)
        parser.add_argument("--source-namespace", required=True)
        parser.add_argument("--source-profile", choices=sorted(PROFILES), required=True)
        parser.add_argument("--output-dir", required=True)

    def handle(self, *args, **options):
        try:
            if get_profile(options["source_profile"]).schema != options["source_schema"]:
                raise PortabilityError("--source-profile must match --source-schema.")
            extracted = inspect_archive(options["dump"], schema=options["source_schema"], pg_restore=options["pg_restore"])
            prepared = build_party_preparation(extracted, schema=options["source_schema"],
                                               source_namespace=options["source_namespace"], source_profile=options["source_profile"])
            output = write_party_preparation(options["output_dir"], prepared)
            self.stdout.write(f"Prepared {sum(prepared['counts'].values())} Party source records; {len(prepared['review'])} review items. Nothing staged or imported.")
            self.stdout.write(str((output / "review.json").resolve()))
        except PortabilityError as exc:
            raise CommandError(str(exc)) from exc
