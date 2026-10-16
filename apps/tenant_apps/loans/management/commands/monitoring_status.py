"""Read-only diagnostics in explicitly selected restricted Workspace contexts."""
import json
from dataclasses import asdict
from time import perf_counter

from django.core.management.base import BaseCommand, CommandError
from apps.orgs.models import Company
from apps.tenancy.context import workspace_context, current_workspace_id
from apps.tenant_apps.loans.selectors.monitoring_readiness import get_monitoring_readiness


class Command(BaseCommand):
    help = 'Report monitoring coverage, pending work and configured assignment; never refresh or post.'

    def add_arguments(self, parser):
        parser.add_argument('--workspace-id', type=int, action='append', required=True)

    def handle(self, *args, **options):
        if current_workspace_id() is not None or any(pk < 1 for pk in options['workspace_id']):
            raise CommandError('Use explicit positive Workspace IDs outside an existing Workspace context.')
        for workspace_id in dict.fromkeys(options['workspace_id']):
            started = perf_counter()
            with workspace_context(workspace_id):
                try:
                    workspace = Company.objects.get(pk=workspace_id)
                except Company.DoesNotExist as exc:
                    raise CommandError('Workspace not found.') from exc
                result = get_monitoring_readiness(workspace=workspace)
                self.stdout.write(json.dumps(dict(workspace=workspace_id, lifecycle=workspace.lifecycle_state,
                    assignment=result['assignment'], summary=asdict(result['summary']),
                    pending=result['pending_count'], last_attempt=result['last_attempt'],
                    last_success=result['last_success'], oldest_pending_assessment=result['oldest_pending_assessment'],
                    oldest_unassessed_loan=result['oldest_unassessed_loan'],
                    elapsed_seconds=round(perf_counter()-started,4)), default=str,sort_keys=True))
