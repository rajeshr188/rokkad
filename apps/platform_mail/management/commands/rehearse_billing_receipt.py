import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.platform_mail.rehearsal import dispatch_test_receipt, preview_test_receipt


class Command(BaseCommand):
    help = "Preview one addressed Test Mode receipt; --send explicitly claims one attempt. Never scans the queue."

    def add_arguments(self, parser):
        parser.add_argument("--delivery", required=True)
        parser.add_argument("--actor-id", required=True, type=int)
        parser.add_argument("--recipient", required=True)
        parser.add_argument("--reference", required=True)
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--send", action="store_true")
        group.add_argument("--preview-html", type=Path)

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(pk=options["actor_id"], is_active=True)
            kwargs = dict(actor=actor, recipient=options["recipient"], reference=options["reference"])
            if options["send"]:
                status = dispatch_test_receipt(options["delivery"], **kwargs)
                report = {"delivery_id": options["delivery"], "status": status}
            else:
                row, message = preview_test_receipt(options["delivery"], **kwargs)
                if options["preview_html"]:
                    with options["preview_html"].open("x", encoding="utf-8") as output:
                        output.write(message["html"])
                report = {"delivery_id": str(row.pk), "invoice_id": row.invoice_id,
                          "status": row.status, "preview_only": True, "recipient_matches": True}
        except (ObjectDoesNotExist, PermissionDenied, ValidationError, OSError) as exc:
            message = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
            raise CommandError(message) from None
        self.stdout.write(json.dumps(report))
