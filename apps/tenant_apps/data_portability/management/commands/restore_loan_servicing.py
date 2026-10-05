"""Preview/confirmed cross-Workspace admission of bounded servicing evidence."""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.services.history_contract import dump, _pairs
from apps.tenant_apps.loans.services.servicing_bundle import restore_servicing_bundle, _access
from apps.tenant_apps.loans.services.servicing_bundle_contract import MAX_BYTES


class Command(BaseCommand):
    help = 'Preview a loan-servicing.zip admission. Commit requires the exact reviewed checksum and explicit destination mappings.'

    def add_arguments(self, parser):
        parser.add_argument('--workspace-id', required=True, type=int)
        parser.add_argument('--actor-id', required=True, type=int)
        parser.add_argument('--source', required=True)
        parser.add_argument('--mapping', required=True, help='JSON object keyed by source loan ID: borrower_id, revision_id, series_id, product_version_id.')
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--expected-sha256')

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(pk=options['actor_id'])
            with workspace_context(options['workspace_id']):
                _access(options['workspace_id'], actor)
                if bool(options['commit']) != bool(options['expected_sha256']):
                    raise ValueError('Commit requires --commit and the exact preview --expected-sha256; omit both for preview.')
                with Path(options['source']).open('rb') as stream:
                    content = stream.read(MAX_BYTES+1)
                with Path(options['mapping']).open('rb') as stream:
                    raw_mapping = stream.read(64*1024+1)
                if len(raw_mapping) > 64*1024:
                    raise ValueError('Destination mapping exceeds 64 KiB.')
                mapping = json.loads(raw_mapping, object_pairs_hook=_pairs)
                result = restore_servicing_bundle(workspace_id=options['workspace_id'], actor=actor,
                    content=content, mapping=mapping, expected_sha256=options['expected_sha256'], confirmed=options['commit'])
            self.stdout.write(dump(result))
        except (OSError, ValueError, ObjectDoesNotExist, PermissionDenied, ValidationError, DatabaseError) as exc:
            raise CommandError(str(exc)) from exc
