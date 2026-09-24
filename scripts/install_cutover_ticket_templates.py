"""Install reviewed ticket packs on an explicitly bound cutover destination.

Run inside the deployed application with its restricted runtime settings:
python scripts/install_cutover_ticket_templates.py --bundle /private/templates \
    --target /private/template-target.json
See docs/implementation/linode-production-cutover.md for the target contract.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--target', required=True, type=Path)
    args = parser.parse_args()
    import django
    django.setup()
    from django.conf import settings
    from django.db import connection
    from apps.orgs.models import Company
    from apps.tenancy.context import workspace_context
    from apps.tenant_apps.loans.documents import DocumentLayoutValidator, PrintProfileValidator, ConfigurableDocumentRenderer
    from apps.tenant_apps.loans.documents.layouts import ALLOWED_VALUE_FORMATS
    from apps.tenant_apps.loans.documents.packs import import_layout_pack
    from apps.tenant_apps.loans.models import LoanDocumentLayoutRevision, LoanDocumentPrintProfileRevision, LoanSeries
    from apps.tenant_apps.loans.services import LoanDocumentLayoutService, LoanDocumentPrintProfileService
    from apps.tenant_apps.loans.services.ticket_template_activation import use_ticket_template

    target = json.loads(args.target.read_text())
    manifest_bytes = (args.bundle/'manifest.json').read_bytes()
    require(hashlib.sha256(manifest_bytes).hexdigest() == target['manifest_sha256'], 'Bundle manifest changed.')
    require(connection.settings_dict['NAME'] == target['database'], 'Wrong destination database.')
    require(connection.settings_dict['HOST'] == target['database_host'], 'Wrong destination database host.')
    require(settings.STORAGES['default']['OPTIONS']['location'] == target['media_location'], 'Wrong destination storage.')
    require(type(target['rehearsal']) is bool and bool(getattr(settings, 'REHEARSAL_BROWSER', False)) == target['rehearsal'], 'Wrong deployment mode.')
    require('INR_SYMBOL' in ALLOWED_VALUE_FORMATS, 'Deploy the rupee-format application change first.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user')
        role, superuser, bypass = cursor.fetchone()
    require(role == target['runtime_role'] and not superuser and not bypass, 'Use the bound restricted runtime role.')
    manifest = json.loads(manifest_bytes)
    require({row['branch'] for row in manifest['templates']} == {'jcl', 'jsk'}, 'Expected JCL and JSK packs.')
    prepared = []
    # Verify both source files and destination identities before any mutation.
    for row in manifest['templates']:
        binding = target['workspaces'][row['branch']]
        workspace = Company.all_objects.select_related('owner').get(pk=binding['id'], slug=binding['slug'])
        require(target['rehearsal'] or 'rehearsal' not in workspace.slug.lower(), 'Production cannot target a rehearsal workspace.')
        pack = (args.bundle/row['layout_pack']).read_bytes()
        profile_bytes = (args.bundle/row['profile_file']).read_bytes()
        require(hashlib.sha256(pack).hexdigest() == row['pack_sha256'], 'Layout pack checksum mismatch.')
        require(hashlib.sha256(profile_bytes).hexdigest() == row['profile_file_sha256'], 'Paper profile checksum mismatch.')
        prepared.append((row, workspace, pack, json.loads(profile_bytes)))
    for row, workspace, pack, definition in prepared:
        # Each workspace is atomic. A retry reuses matching revisions and assignments.
        with workspace_context(workspace.pk):
            revision = LoanDocumentLayoutRevision.objects.filter(content_hash=row['layout_hash'], state__in=['DRAFT','PUBLISHED']).first()
            if revision is None:
                revision = import_layout_pack(workspace=workspace, content=pack, actor=workspace.owner,
                    name=row['branch'].upper()+' accepted cutover '+row['layout_hash'][:12])
            profile = LoanDocumentPrintProfileRevision.objects.filter(content_hash=row['profile_hash'], state__in=['DRAFT','PUBLISHED']).first()
            if profile is None:
                profile = LoanDocumentPrintProfileService.create_profile(workspace=workspace, document_type='loan_ticket',
                    name=definition['name'], definition=definition, actor=workspace.owner)
            require(revision.content_hash == row['layout_hash'] and profile.content_hash == row['profile_hash'], 'Imported configuration hash mismatch.')
            layout = DocumentLayoutValidator.load(revision.definition)
            paper = PrintProfileValidator.load(profile.definition)
            ConfigurableDocumentRenderer.assert_print_profile_compatible(layout, paper)
            for asset in revision.assets.all():
                with asset.file.open('rb') as stream:
                    require(hashlib.sha256(stream.read()).hexdigest() == asset.sha256, 'Stored background checksum mismatch.')
            use_ticket_template(workspace=workspace, revision=revision, profile_revision=profile, actor=workspace.owner,
                layout_hash=row['layout_hash'], profile_hash=row['profile_hash'])
            count = 0
            for series in LoanSeries.objects.select_related('license'):
                effective = LoanDocumentLayoutService.resolve(workspace=workspace, document_type='loan_ticket', license=series.license, series=series)
                effective_paper = LoanDocumentPrintProfileService.resolve(workspace=workspace, document_type='loan_ticket', series=series)
                require(effective and effective.content_hash == row['layout_hash'] and effective_paper.content_hash == row['profile_hash'],
                    f'Series {series.code} has a conflicting override; review it before opening.')
                count += 1
        print(json.dumps({'branch': row['branch'], 'workspace': workspace.slug, 'layout_revision': revision.pk,
            'profile_revision': profile.pk, 'scope': 'WORKSPACE_DEFAULT', 'series_verified': count}), flush=True)


if __name__ == '__main__':
    main()
