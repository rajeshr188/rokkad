from django.core.management.base import BaseCommand
from apps.platform_whatsapp.configuration import readiness


class Command(BaseCommand):
    help = "Report offline platform WhatsApp readiness without provider calls or secret output."

    def handle(self, *args, **options):
        report = readiness()
        self.stdout.write("Mode: preview; outbound delivery unavailable")
        self.stdout.write("Inbound pairing: " + ("configured" if report["inbound_ready"] else "disabled / incomplete"))
        for problem in report["blockers"]:
            self.stdout.write("- " + problem)
