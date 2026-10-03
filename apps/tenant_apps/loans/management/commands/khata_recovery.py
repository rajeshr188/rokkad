"""Trusted native backup and exact-identity offline recovery."""
import hashlib
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from apps.orgs.models import Company
from apps.tenant_apps.loans.services.khata_recovery import export_archive, restore_archive, MAX_BYTES


class Command(BaseCommand):
    help = "Export a native khata backup or preview/confirm an empty-destination offline recovery."

    def add_arguments(self, parser):
        parser.add_argument("mode", choices=("export", "restore"))
        parser.add_argument("--workspace", required=True, help="Original Workspace slug")
        parser.add_argument("--actor", required=True, type=int, help="Authorized Workspace owner/member user ID")
        parser.add_argument("--file", required=True, help="Private ZIP path")
        parser.add_argument("--sha256", help="Independently retained SHA-256, required for restore")
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--confirm-workspace", help="Repeat the Workspace slug to commit restore")

    def handle(self, *args, **options):
        try:
            workspace = Company.objects.get(slug=options["workspace"])
            actor = get_user_model().objects.get(pk=options["actor"])
            path = Path(options["file"])
            if options["mode"] == "export":
                if options["commit"]:
                    raise ValueError("--commit applies only to restore.")
                content = export_archive(workspace=workspace, actor=actor)
                # Never overwrite an existing backup.
                with path.open("xb") as output:
                    output.write(content)
                result = dict(file=str(path), sha256=hashlib.sha256(content).hexdigest(), bytes=len(content))
            else:
                if settings.SETTINGS_MODULE != "django_project.settings.migration":
                    raise ValueError("Offline restore must use --settings django_project.settings.migration.")
                if options["commit"] and options["confirm_workspace"] != workspace.slug:
                    raise ValueError("Commit requires --confirm-workspace with the original Workspace slug.")
                if path.stat().st_size > MAX_BYTES:
                    raise ValueError("Archive exceeds the bounded recovery size.")
                result = restore_archive(workspace=workspace, actor=actor, content=path.read_bytes(),
                    expected_sha256=options["sha256"], commit=options["commit"])
            self.stdout.write(json.dumps(result, sort_keys=True, indent=2))
        except (ValueError, OSError, DatabaseError, Company.DoesNotExist, get_user_model().DoesNotExist) as exc:
            raise CommandError(str(exc)) from exc
