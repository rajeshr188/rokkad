"""Fixed, reviewed fresh-destination setup contract. Never a native DB importer."""
import json
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from uuid import uuid5

from django.apps import apps
from django.conf import settings
from django.db.models import FileField

from apps.tenant_apps.loans.documents import DocumentLayoutValidator, PrintProfileValidator, DocumentAssetValidator
from .action_access import require_setup_administration
from .servicing_bundle_contract import scalar, require

ROWS = json.loads((Path(settings.BASE_DIR) / 'docs/contracts/fresh-business-setup-v1-rows.json').read_text())
GRAPH_ROWS = json.loads((Path(settings.BASE_DIR) / 'docs/contracts/fresh-business-setup-v2-rows.json').read_text())
MONITORING_ROWS = json.loads((Path(settings.BASE_DIR) / 'docs/contracts/fresh-business-setup-v3-rows.json').read_text())
LIFECYCLE_ROWS = json.loads((Path(settings.BASE_DIR) / 'docs/contracts/fresh-business-setup-v4-rows.json').read_text())
MAX_ROWS = 50000
MAX_BYTES = 16 * 1024 * 1024


def schema(version):
    require(version in (1,2,3,4), 'Unsupported business setup contract version.')
    return {1:ROWS,2:GRAPH_ROWS,3:MONITORING_ROWS,4:LIFECYCLE_ROWS}[version]


def needs_version_four(workspace_id):
    from apps.tenant_apps.loans.models import LoanMonitoringPolicy
    return LoanMonitoringPolicy.objects.filter(workspace_id=workspace_id).exclude(
        scope_action='APPLY', replaces_scheduled=False).exists()


def needs_version_three(workspace_id):
    from apps.tenant_apps.loans.models import LoanMonitoringPolicy
    return LoanMonitoringPolicy.objects.filter(workspace_id=workspace_id).exclude(
        valuation_basis=LoanMonitoringPolicy.ValuationBasis.ORIGINAL_AGREEMENT).exists()


def needs_version_two(workspace_id):
    from apps.tenant_apps.loans import models as loans
    from apps.tenant_apps.rates.models import Rate
    if (loans.PawnStorageLocation.objects.filter(workspace_id=workspace_id).exists()
            or loans.FundingLoanSequence.objects.filter(workspace_id=workspace_id).exists()
            or loans.LoanLicenseRevision.objects.filter(workspace_id=workspace_id,
                kind__in=('VERIFICATION','ATTESTATION','IMPORTED_SOURCE')).exists()):
        return True
    for quote in Rate.objects.filter(workspace_id=workspace_id).select_related('rate_source').iterator():
        current={key:getattr(quote.rate_source,key) for key in ('name','location','tax_included')}
        if quote.portable_source or quote.source_snapshot != current:
            return True
    return False


def models(version=1):
    ROWS = schema(version)
    result = {label: apps.get_model(label) for label in ROWS}
    for label, model in result.items():
        actual = {f.attname for f in model._meta.concrete_fields if f.name != 'workspace'
            and not (f.is_relation and f.related_model._meta.app_label in {'auth','accounts'})}
        if version==1 and label=='rates.Rate':
            actual.discard('portable_source')
        if version<3 and label=='loans.LoanMonitoringPolicy':
            actual.discard('valuation_basis')
        if version<4 and label=='loans.LoanMonitoringPolicy':
            actual -= {'scope_action', 'replaces_scheduled'}
        require(actual == set(ROWS[label]), 'Business setup schema changed; review the published profile before export/restore.')
    return result


def encode_row(label, obj, version=1):
    ROWS = schema(version)
    result = {}
    for key in ROWS[label]:
        value = getattr(obj, key)
        if isinstance(value, (Decimal, UUID)):
            value = str(value)
        elif isinstance(value, (date, datetime)):
            value = value.isoformat()
        elif isinstance(obj._meta.get_field(key.removesuffix('_id')), FileField):
            value = value.name
        result[key] = value
    return result


def validate_tables(tables, version=1):
    ROWS = schema(version)
    require(type(tables) is dict and set(tables) == set(ROWS), 'Unsupported business setup inventory.')
    require(sum(len(rows) for rows in tables.values() if type(rows) is list) <= MAX_ROWS, 'Business setup exceeds 50,000 rows.')
    ids = {}
    for label, fields in ROWS.items():
        require(type(tables[label]) is list, 'Invalid setup table.')
        ids[label] = set()
        for row in tables[label]:
            require(type(row) is dict and set(row) == set(fields), 'Unexpected setup fields: '+label)
            for key, spec in fields.items():
                value = scalar(row[key], spec)
                require(not isinstance(value, str) or spec['max_length'] is None or len(value) <= spec['max_length'], 'Excessive setup text.')
            require(row['id'] not in ids[label], 'Duplicate setup identity.')
            ids[label].add(row['id'])
        require([row['id'] for row in tables[label]] == sorted(ids[label]), 'Setup rows must retain source order.')
    rate_sources = {row['id']:row for row in tables['rates.RateSource']}
    for label, fields in ROWS.items():
        for row in tables[label]:
            for key, spec in fields.items():
                if 'related' in spec and row[key] is not None:
                    require(spec['related'] in ids and row[key] in ids[spec['related']], 'Missing or foreign setup reference.')
            if label == 'loans.LoanLicenseRevision' and version==1:
                require(row['kind'] not in {'VERIFICATION', 'ATTESTATION'},
                    'Verified legacy continuation/owner-attestation setup needs a reviewed transfer adapter; no authority is inferred.')
            if label == 'rates.Rate' and version==1:
                source = rate_sources[row['rate_source_id']]
                require(row['source_snapshot'] ==
                    {k:source[k] for k in ('name','location','tax_included')},
                    'A quote retains legacy/additional or earlier source evidence; a versioned source adapter is required.')
    return tables


def export_setup(*, workspace_id, actor, save_file, version=1):
    ROWS = schema(version)
    # Financial export authorization is checked by the package orchestrator.
    tables = {label: [] for label in ROWS}
    count = 0
    for label, model in models(version).items():
        for obj in model.objects.filter(workspace_id=workspace_id).order_by('pk').iterator():
            if version<4 and label == 'loans.LoanMonitoringPolicy':
                require(obj.scope_action == 'APPLY' and not obj.replaces_scheduled,
                    'Monitoring lifecycle evidence needs business setup profile 4.')
            if version<3 and label == 'loans.LoanMonitoringPolicy':
                require(obj.valuation_basis == 'ORIGINAL_AGREEMENT',
                    'Explicit current monitoring valuation needs a newer business setup profile; versions 1 and 2 cannot retain it.')
            count += 1
            require(count <= MAX_ROWS, 'Business setup exceeds 50,000 rows.')
            row = encode_row(label, obj, version)
            if version==1 and label=='rates.Rate':
                require(not obj.portable_source, 'Imported quote provenance requires package version 2.')
            for key, spec in ROWS[label].items():
                if spec['type'] == 'FileField' and row[key]:
                    field = getattr(obj, key)
                    claim = save_file(field)
                    require(claim['sha256'] == row['sha256'] and claim['bytes'] == row['byte_size'], 'Setup media differs from frozen evidence.')
                    row[key] = claim['sha256']
            tables[label].append(row)
    return validate_tables(tables,version)


def restore_setup(*, workspace_id, actor, tables, load_file, save_file, version=1, namespace=None):
    ROWS = schema(version)
    """Remap only this published inventory, with existing model/DB guards enabled.

    raw insert preserves immutable original dates after full validation. Source
    PKs/actors are not local identities. Files are assigned destination names.
    Licences remain disabled until ordinary destination setup review.
    """
    require_setup_administration(workspace_id, actor)
    validate_tables(tables,version)
    require(version==1 or namespace is not None, 'Wider setup requires its source namespace.')
    refs, revisions = {}, []
    def finish_revisions():
        for revision, state in revisions:
            if type(revision).__name__ == 'LoanDocumentLayoutRevision' and state != 'DRAFT':
                parsed = DocumentLayoutValidator.load(revision.definition)
                assets = {asset.key:asset for asset in revision.assets.all()}
                required = {block.asset_key for block in parsed.all_blocks() if block.asset_key} | set(parsed.background_asset_keys())
                require(required <= set(assets), 'Published layout lacks required assets.')
                parsed.validate_signature_backgrounds(assets)
            revision.state = state
            revision.save_base(raw=True, update_fields=['state'])
        revisions.clear()
    for label, model in models(version).items():
        refs[label] = {}
        if label.endswith('Assignment'):
            finish_revisions()
        for row in tables[label]:
            values = {}
            for key, spec in ROWS[label].items():
                if key == 'id':
                    continue
                value = scalar(row[key], spec)
                if 'related' in spec and value is not None:
                    require(value in refs.get(spec['related'], {}), 'Setup dependency order is invalid.')
                    value = refs[spec['related']][value].pk
                values[key] = value
            if label == 'loans.LoanLicense':
                values['is_active'] = False
            if version<3 and label=='loans.LoanMonitoringPolicy':
                # Older contracts mean preserve the saved loan method; do not
                # let a later model default reinterpret that published meaning.
                values['valuation_basis']='ORIGINAL_AGREEMENT'
            if version<4 and label=='loans.LoanMonitoringPolicy':
                values.update(scope_action='APPLY', replaces_scheduled=False)
            if version>=2 and label=='loans.LoanLicenseRevision':
                license=refs['loans.LoanLicense'][row['license_id']]
                if row['kind']!='LEGACY_REFERENCE' or not license.is_legacy_reference:
                    from .portable_licence_evidence import source_evidence
                    values['kind']='IMPORTED_SOURCE'
                    values['verification_evidence']=source_evidence(namespace=namespace,row=row)
            if version>=2 and label=='rates.Rate':
                from apps.tenant_apps.rates.portable_quotes import source_evidence
                values['portable_source']=source_evidence(namespace=namespace,row=row)
            if label=='loans.PawnStorageLocation':
                values['public_id']=uuid5(UUID(str(namespace)),f'portable-storage:{workspace_id}:{row["id"]}')
            desired_state = values.get('state') if label in {'loans.LoanDocumentLayoutRevision','loans.LoanDocumentPrintProfileRevision'} else None
            if desired_state:
                values['state'] = 'DRAFT'
                validator = DocumentLayoutValidator if label.endswith('LayoutRevision') else PrintProfileValidator
                parsed = validator.load(values['definition'])
                require(parsed.content_hash == values['content_hash'], 'Setup document definition hash differs.')
            obj = model(workspace_id=workspace_id, **values)
            for field in model._meta.concrete_fields:
                if field.is_relation and field.related_model._meta.app_label in {'auth','accounts'}:
                    setattr(obj, field.attname, actor.pk)
                if isinstance(field, FileField) and getattr(obj, field.name).name:
                    checksum = getattr(obj, field.name).name
                    data = load_file(checksum)
                    if label == 'loans.LoanDocumentAsset':
                        validated = DocumentAssetValidator.validate(key=obj.key, kind=obj.kind, content=data, workspace_id=workspace_id)
                        require(validated.sha256 == obj.sha256, 'Template asset differs.')
                    save_file(getattr(obj, field.name), data)
            obj.full_clean()
            obj.save_base(raw=True, force_insert=True)
            refs[label][row['id']] = obj
            if desired_state:
                revisions.append((obj, desired_state))
    finish_revisions()
    return refs
