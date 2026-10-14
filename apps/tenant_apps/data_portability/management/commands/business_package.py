"""Private manual download/copy, review, and atomic fresh business restoration."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError, ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction, DatabaseError

from apps.tenancy.context import workspace_context
from apps.tenant_apps.data_portability import business_package as package
from apps.tenant_apps.data_portability.contracts import dump


class Command(BaseCommand):
    help = 'Export, preview or confirm a supported private business package into an empty recovery-only Workspace. Does not activate lending or billing.'

    def add_arguments(self, parser):
        parser.add_argument('operation', choices=['export','preview','restore'])
        parser.add_argument('--workspace-id', type=int, required=True)
        parser.add_argument('--actor-id', type=int, required=True)
        parser.add_argument('--directory', required=True)
        parser.add_argument('--expected-sha256')
        parser.add_argument('--review-file')
        parser.add_argument('--confirm', action='store_true')

    def handle(self, *args, **options):
        saved_files, committed = [], False
        try:
            if connection.in_atomic_block:
                raise ValueError('Run business package commands in a fresh process, outside an existing transaction.')
            actor = get_user_model().objects.get(pk=options['actor_id'])
            root, operation = Path(options['directory']).resolve(), options['operation']
            if operation == 'export':
                if root.exists() or not root.parent.is_dir() or options['expected_sha256'] or options['review_file'] or options['confirm']:
                    raise ValueError('Export needs a new directory in a protected existing parent and no restore options.')
                with TemporaryDirectory(prefix='.rokkad-business-', dir=root.parent) as temporary:
                    prepared = Path(temporary)/'prepared'
                    prepared.mkdir(mode=0o700)
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                        with workspace_context(options['workspace_id']):
                            doc = package.write_package(workspace_id=options['workspace_id'], actor=actor, directory=prepared, _consistent_snapshot=True)
                    prepared.rename(root)
                result = dict(profile=package.PROFILE, directory=str(root), sha256=doc['sha256'], counts=doc['counts'], setup_counts=doc['setup_counts'])
            else:
                if not options['expected_sha256'] or not options['review_file']:
                    raise ValueError('Preview/restore require the independently retained checksum and private review file.')
                review_path = Path(options['review_file']).resolve()
                values = dict(workspace_id=options['workspace_id'], actor=actor, directory=root, expected_sha256=options['expected_sha256'])
                if operation == 'preview':
                    if options['confirm'] or review_path.exists() or not review_path.parent.is_dir():
                        raise ValueError('Preview needs a new private review file and no confirmation.')
                    with workspace_context(options['workspace_id']):
                        review = package.preview_package(**values)
                    with review_path.open('x', encoding='utf-8') as stream:
                        stream.write(dump(review))
                    review_path.chmod(0o600)
                    result = dict(review_file=str(review_path), summary=review['summary'])
                else:
                    if not options['confirm']:
                        raise ValueError('Read the review file and explicitly use --confirm before restoration.')
                    review = json.loads(package._read(review_path, package.MAX_FILE))
                    with workspace_context(options['workspace_id']):
                        receipt = package.restore_package(**values, approval=review['approval'], confirmed=True, _outer_saved_files=saved_files)
                    committed = True
                    result = dict(receipt=str(receipt.public_id), counts=receipt.summary['counts'],
                        loans=len(receipt.results), next_step='Review destination licensing/setup, then activate commercial access explicitly.')
            self.stdout.write(dump(result))
        except (OSError, ValueError, KeyError, TypeError, ObjectDoesNotExist, PermissionDenied, ValidationError, DatabaseError) as exc:
            raise CommandError(str(exc)) from exc
        finally:
            if not committed:
                for storage,name in saved_files:
                    storage.delete(name)
