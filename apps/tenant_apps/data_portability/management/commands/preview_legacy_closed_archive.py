from zoneinfo import ZoneInfoNotFoundError

from django.core.management.base import BaseCommand, CommandError

from apps.tenant_apps.data_portability.legacy_archive_preview import write_report
from apps.tenant_apps.data_portability.legacy_dump import inspect_archive
from apps.tenant_apps.data_portability.legacy_preview import build_preview, encode
from apps.tenant_apps.data_portability.parsers import PortabilityError


class Command(BaseCommand):
    help = "Prepare unaccepted closed-loan archive evidence offline; no database access."
    requires_system_checks = []
    requires_migrations_checks = False

    def add_arguments(self, parser):
        for name in ("dump", "source-schema", "source-namespace", "business-timezone", "review-date", "output-dir"):
            parser.add_argument("--" + name, required=True)
        parser.add_argument("--pg-restore", default="pg_restore")
        parser.add_argument("--owner-profile", choices=["jcl-owner/1", "jcl-owner/2"])

    def handle(self, *args, **options):
        try:
            extracted = inspect_archive(options["dump"], schema=options["source_schema"], pg_restore=options["pg_restore"])
            summary, records = build_preview(extracted, schema=options["source_schema"], source_namespace=options["source_namespace"])
            report = write_report(options["output_dir"], summary, records, **{
                key: options[key] for key in ("business_timezone", "review_date", "owner_profile")})
            self.stdout.write(encode(report["counts"]))
        except (PortabilityError, OSError, ValueError, ZoneInfoNotFoundError) as exc:
            raise CommandError(str(exc)) from exc
