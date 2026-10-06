"""Companion read-only media audit; private artifacts use the same audit directory."""
import os
import sys
sys.path.insert(0, '/code')
import django
django.setup()
from collections import Counter
import json
from pathlib import Path
from uuid import UUID, uuid5
from django.db import connection, transaction
from django.utils import timezone
from apps.tenancy.context import workspace_context
from apps.orgs.services.storage_inventory import R2Inventory
from apps.tenant_apps.data_portability import linode_run as run, legacy_media
from apps.tenant_apps.data_portability.models import LegacyMediaReceipt, SourceIdentity
from apps.tenant_apps.loans.models import HistoricalLoanImport, HistoricalLoanEvidence, HistoricalLoanAttachment, PawnCollateralPhoto
from apps.tenant_apps.party.models import PartyDocument


def main():
    os.umask(0o077)
    base, out = Path('/evidence'), Path('/audit-output')
    accepted = json.loads((out/'summary.json').read_text())
    manifest = json.loads((base/'package/manifest.json').read_text())
    mapping = json.loads((base/'run/workspace-map.json').read_text())
    refs = {schema:{} for schema in mapping}
    for row in run.read_rows(base/'media/references.jsonl'):
        source=row['source'];key=source['table']+':'+source['source_id']
        run.require(key not in refs[source['schema']], 'Duplicate media source reference.')
        refs[source['schema']][key]=row
    listing_started=timezone.now()
    objects={}
    # Fresh metadata listing only: do not fetch customer images, upload or delete.
    for obj in R2Inventory().objects():
        run.require(obj['key'] not in objects and len(objects)<250000, 'Invalid object listing.')
        objects[obj['key']]=obj['size']
    report=dict(listing_started_at=listing_started.isoformat(),listing_completed_at=timezone.now().isoformat(),
                object_check='Fresh application-prefix key and byte-size listing; not fresh content hashing; not an atomic DB/storage snapshot',workspaces={})
    details=(out/'media-findings.jsonl').open('w')
    run.runtime_guard(accepted['database'])
    with connection.cursor() as cursor:cursor.execute('SET default_transaction_read_only=on')
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        for schema,wid in mapping.items():
            counters,counts=Counter(),Counter()
            def check(condition,code,key):
                if not condition:
                    counters[code]+=1
                    details.write(json.dumps(dict(workspace=schema,source_id=key,code=code))+'\n')
            with workspace_context(wid):
                origins={o.source_id: o for o in HistoricalLoanImport.objects.filter(source_namespace=manifest['namespace']).only('source_id','loan_id','references')}
                photos={p.pk:p for p in PawnCollateralPhoto.objects.filter(workflow_source='LEGACY_IMPORT').select_related('collateral_item')}
                attachments={p.pk:p for p in HistoricalLoanAttachment.objects.all()}
                archive_sources=dict(HistoricalLoanEvidence.objects.filter(source_namespace=manifest['namespace']).values_list('pk','source_id'))
                documents={p.pk:p for p in PartyDocument.objects.filter(title='Legacy customer photograph')}
                parties={s.external_id:s.identity.party_id for s in SourceIdentity.objects.filter(source_system=manifest['workspaces'][schema]['source_system']).select_related('identity')}
                seen=set()
                for receipt in LegacyMediaReceipt.objects.filter(source_system=manifest['workspaces'][schema]['source_system']).iterator(chunk_size=200):
                    key=receipt.source_id;seen.add(key);counts['receipts']+=1
                    evidence=receipt.source_evidence;ref=refs[schema].get(key)
                    check(ref is not None and all(evidence.get(k)==v for k,v in ref.items()),'media_frozen_reference_mismatch',key)
                    check(receipt.evidence_sha256==legacy_media.digest(evidence),'media_receipt_hash_mismatch',key)
                    check(evidence['archive_sha256']==manifest['archive_sha256'] and evidence['namespace']==manifest['namespace'],'media_snapshot_mismatch',key)
                    check(legacy_media.validate_evidence(evidence)==(receipt.source_system,key),'media_source_identity_mismatch',key)
                    target=receipt.target;kind=target['kind'];counts[kind]+=1
                    names=legacy_media.application_names(workspace_id=wid,evidence=evidence,kind=kind)
                    for name in names.values():
                        counts['objects_checked']+=1
                        check(name in objects,'media_object_missing',key)
                        if name in objects:check(objects[name]==evidence['verified_source_file']['byte_size'],'media_object_size_mismatch',key)
                    if kind=='party':
                        external=str(uuid5(uuid5(UUID(manifest['namespace']),schema),'contact_customer:'+evidence['source']['parent_id']))
                        check(target['party_id']==parties.get(external),'media_party_target_mismatch',key)
                        obj=documents.get(target['document_id'])
                        check(target['document_name']==names['file'] and target['profile_name']==names.get('profile',''),'media_target_filename_mismatch',key)
                        check(obj is not None and obj.party_id==target['party_id'] and obj.file.name==names['file'],'media_current_document_changed',key)
                    elif kind=='collateral':
                        origin=origins.get(schema+':girvi_loan:'+evidence['source']['parent_id'])
                        check(origin is not None and origin.references['items'].get(key)==target['item_id'],'media_imported_item_target_mismatch',key)
                        obj=photos.get(target['photo_id'])
                        check(obj is not None and obj.collateral_item_id==target['item_id'] and obj.file.name==names['file'],'media_current_photo_changed',key)
                        check(obj is not None and obj.sha256==evidence['verified_source_file']['sha256'] and obj.source_evidence==evidence,'media_photo_evidence_mismatch',key)
                    elif kind=='archive':
                        obj=attachments.get(target['attachment_id'])
                        check(archive_sources.get(target['evidence_id'])=='girvi_loan:'+evidence['source']['parent_id'],'media_archive_parent_mismatch',key)
                        check(obj is not None and obj.evidence_id==target['evidence_id'] and obj.file.name==names['file'],'media_current_archive_changed',key)
                        check(obj is not None and obj.sha256==evidence['verified_source_file']['sha256'] and obj.source_evidence==evidence,'media_archive_evidence_mismatch',key)
                    else:check(False,'unknown_media_target',key)
                statuses=Counter(r['status'] for r in refs[schema].values())
                expected={k for k,r in refs[schema].items() if r['status']=='EXACT_SOURCE_FILE_PRESERVED'}
                check(seen==expected,'media_receipt_coverage_mismatch','all')
                report['workspaces'][schema]=dict(counts=dict(counts),source_statuses=dict(statuses),findings=dict(counters))
                print(schema+': '+json.dumps(report['workspaces'][schema]),flush=True)
    details.close()
    report['completed_at']=timezone.now().isoformat()
    report['findings_sha256']=run.sha_file(out/'media-findings.jsonl')
    (out/'media-summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print('MEDIA_AUDIT_COMPLETE',flush=True)


if __name__=='__main__':main()
