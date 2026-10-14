"""Read-only explicit pilot preflight; never activates flags or sends a message."""
import json
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.core.management.base import BaseCommand,CommandError
from django.core.serializers.json import DjangoJSONEncoder
from apps.orgs.models import Company
from apps.platform_whatsapp.dispatch import _standalone
from apps.platform_whatsapp.diagnostics import pilot_preflight

class Command(BaseCommand):
    help="Read-only owner/source/configuration check for one explicit setup pilot."
    def add_arguments(self,parser):
        parser.add_argument("--actor-id",type=int,required=True)
        parser.add_argument("--workspace-slug",required=True)
        parser.add_argument("--owner-email",required=True)
    def handle(self,*args,**options):
        try:
            _standalone()
            actor=get_user_model().objects.get(pk=options["actor_id"])
            report=pilot_preflight(actor=actor,workspace_slug=options["workspace_slug"],owner_email=options["owner_email"])
        except (PermissionDenied,ValidationError,Company.DoesNotExist,get_user_model().DoesNotExist):
            raise CommandError("Pilot preflight unavailable; verify runtime role, actor and explicit owner/Workspace.") from None
        self.stdout.write(json.dumps(report,cls=DjangoJSONEncoder,indent=2))
