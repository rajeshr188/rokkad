from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "LEGACY MANUAL MAINTENANCE (DISABLED): this command is blocked in runtime; "
        "use documented import/rehearsal workflows instead."
    )

    def handle(self, *args, **options):
        raise CommandError(
            "Legacy command 'do' is disabled. Use explicit Girvi services/commands "
            "or controlled import-rehearsal tooling."
        )
