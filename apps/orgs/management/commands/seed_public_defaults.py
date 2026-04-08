from django.core.management import call_command
from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context


class Command(BaseCommand):
    help = "Seed public-schema defaults (roles, permissions)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-permissions",
            action="store_true",
            help="Skip permissions and role setup command.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding public schema defaults"))

        with schema_context("public"):
            if options["skip_permissions"]:
                self.stdout.write("Skipped permissions/roles seeding")
            else:
                # Reuse existing setup command to keep behavior consistent.
                call_command("setup_permissions")

        self.stdout.write(self.style.SUCCESS("Public schema seeding completed"))
