"""Read-only source-fact, numbering and mutable-Party follow-up to import audit."""
import os
import sys
sys.path.insert(0, '/code')
import django
django.setup()
from collections import Counter
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import re
from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone
from apps.tenancy.context import workspace_context
from apps.orgs.audit import AuditLog
from apps.tenant_apps.data_portability import linode_run as run, contracts, child_contracts
from apps.tenant_apps.data_portability.legacy_dump import parse_copy
from apps.tenant_apps.data_portability.legacy_party_preparation import build_party_preparation
from apps.tenant_apps.data_portability.legacy_profiles import CORRECTIONS
from apps.tenant_apps.data_portability.models import ImportRow, SourceIdentity, ChildSourceIdentity
from apps.tenant_apps.loans import models as loans
from apps.tenant_apps.loans.services.event_recording import _fingerprint
from apps.tenant_apps.party.models import Party, PartyAddress, PartyContactMethod


def main():
    os.umask(0o077)
    base,out=Path('/evidence'),Path('/audit-output')
    summary=json.loads((out/'summary.json').read_text())
    manifest=json.loads((base/'package/manifest.json').read_text())
    mapping=json.loads((base/'run/workspace-map.json').read_text())
    findings=[json.loads(l) for l in (out/'findings.jsonl').open()]
    details=(out/'followup-findings.jsonl').open('w')
    report={'started_at':timezone.now().isoformat(),'workspaces':{}}
    run.runtime_guard(summary['database'])
    with connection.cursor() as c:c.execute('SET default_transaction_read_only=on')
    with transaction.atomic():
        with connection.cursor() as c:c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        for schema,wid in mapping.items():
            counts,exceptions=Counter(),Counter()
            def check(ok,code,key):
                if not ok:
                    exceptions[code]+=1;details.write(json.dumps(dict(workspace=schema,code=code,key=key))+'\n')
            raw=parse_copy((out/(schema+'.copy')).read_bytes(),schema)
            extracted={'tables':raw,'source_schema':schema,'archive_sha256':manifest['archive_sha256']}
            prepared=build_party_preparation(extracted,schema=schema,source_namespace=manifest['namespace'],source_profile=run.SCHEMAS[schema])
            expected={p:{r['id']:r for r in records} for p,records in prepared['records'].items()}
            for kind in ('openings','closed'):
                for document in run.read_rows(base/'package'/schema/(kind+'.jsonl')):
                    records=document['source_evidence']['records'] if kind=='openings' else document['source_records']
                    for row in records:
                        if 'source' not in row:continue
                        src=row['source'];correction=src.get('correction')
                        fact=dict(raw[src['table']][src['id']])
                        if correction:
                            approved=next((r for r in CORRECTIONS if all(correction.get(k)==v for k,v in r.items())),None)
                            check(approved is not None,'unrecognized_source_correction',src['external_id'])
                            if approved:
                                check(fact[approved['field']] in (approved['original'],approved['corrected']),'source_correction_input_mismatch',src['external_id'])
                                fact[approved['field']]=approved['corrected']
                        check(row['facts']==fact,'retained_source_facts_mismatch',src['external_id'])
                        counts['source_record_occurrences_checked']+=1
                        if correction:counts['source_record_occurrences_with_approved_correction']+=1
            with workspace_context(wid):
                meta=manifest['workspaces'][schema]
                accepted_rows={}
                # Avoid repeating potentially large batch mapping/summary JSON for
                # every row; only the profile identifier is needed from the batch.
                rows_query=ImportRow.objects.filter(batch__source_system=meta['source_system'],batch__state='COMPLETED').select_related('batch').only('id','external_id','raw','committed_at','batch_id','batch__id','batch__contract_version')
                for row in rows_query.iterator(chunk_size=200):
                    accepted_rows.setdefault((row.batch.contract_version,row.external_id),[]).append(row)
                for entry in meta['party_batches']:
                    profile=entry['profile']
                    for row in run.read_rows(base/'package'/entry['path']):
                        check(row==expected[profile].get(row['id']),'source_party_preparation_mismatch',row['id'])
                        matches=accepted_rows.get((profile,row['id']),[])
                        check(any(r.raw==row and r.committed_at is not None for r in matches),'committed_party_input_missing',row['id'])
                        counts['source_party_inputs_checked']+=1
                # Bound live numbers against all source records (including archives/exclusions)
                # and all subsequently created records; do not reset any counter.
                setup=AuditLog.objects.get(company_id=wid,action='DATA_IMPORT',data__linode_run=summary['package_sha256'],data__phase='setup').data['mapping']
                for source in run.source_series_configuration(raw):
                    sid=setup['series'][source['id']]['series_id']
                    seq=loans.LoanNumberSequence.objects.get(series_id=sid,document_kind='PAWN_LOAN')
                    values=[int(m[1]) for n in loans.PawnLoan.objects.values_list('loan_number',flat=True) if (m:=re.fullmatch(re.escape(seq.prefix)+r'([0-9]+)',n))]
                    check(seq.prefix==source['prefix'],'series_prefix_mismatch',source['id'])
                    check(seq.next_number>max([source['last_used'],*values]),'sequence_reuses_recorded_number',source['id'])
                    counts['series_sequences_checked']+=1
                check(not loans.PawnLoan.objects.exclude(license_id=F('series__license_id')).exists(),'loan_series_license_mismatch','all')
                check(not loans.PawnLoan.objects.exclude(license_id=F('license_revision__license_id')).exists(),'loan_revision_license_mismatch','all')
                for event in loans.PawnLoanEvent.objects.filter(loan__historical_import__source_namespace=manifest['namespace']).iterator(chunk_size=500):
                    check(event.payload_fingerprint==_fingerprint(event.payload),'event_fingerprint_mismatch',event.pk)
                    counts['imported_loan_event_fingerprints_checked']+=1
                for origin in loans.HistoricalLoanImport.objects.filter(source_namespace=manifest['namespace']).select_related('loan').prefetch_related('loan__collateral_items','loan__loan_events').iterator(chunk_size=100):
                    review=origin.document['review'];key=origin.source_id
                    opening=next(e for e in origin.loan.loan_events.all() if e.event_kind=='MIGRATION_OPENING')
                    check(opening.payload['opening']['review']==review and opening.payload['opening']['item_mapping']==origin.references['items'],'event_review_differs_from_accepted_input',key)
                    check(origin.loan.principal_amount==Decimal(review['balances']['principal']) and origin.loan.tenure_months==origin.document['setup']['tenure_months'],'loan_original_terms_mismatch',key)
                    by_pk={i.pk:i for i in origin.loan.collateral_items.all()}
                    for item in review['collateral']:
                        current=by_pk[origin.references['items'][item['id']]]
                        quantity=item.get('quantity')
                        if quantity is not None:
                            counts['retained_source_quantities']+=1
                            if current.quantity is None:
                                counts['retained_quantity_missing_in_operational_column']+=1
                            else:check(Decimal(current.quantity)==Decimal(str(quantity)),'operational_quantity_mismatch',key)
                traced=[]
                for changed in (r for r in findings if r['workspace']==schema and r['code']=='mutable_party_changed_requires_trace'):
                    profile=changed['profile'];pk=changed['pk']
                    model={contracts.PROFILE:Party,child_contracts.CONTACT:PartyContactMethod,child_contracts.ADDRESS:PartyAddress}[profile]
                    obj=model.objects.get(pk=pk)
                    rows=accepted_rows[(profile,changed['source_id'])]
                    committed=max(r.committed_at for r in rows if r.committed_at)
                    logs=list(AuditLog.objects.filter(company_id=wid,content_type__app_label='party',content_type__model=model._meta.model_name,object_id=pk,timestamp__gt=committed).values('action','user_id','timestamp','data'))
                    value=dict(profile=profile,fields=changed['fields'],modified_after_import=obj.updated_at>committed,
                               updated_by_present=bool(getattr(obj,'updated_by_id',None)),matching_object_audit_count=len(logs))
                    traced.append(value)
                    details.write(json.dumps(dict(workspace=schema,code='mutable_change_trace',pk=pk,source_id=changed['source_id'],**value,
                                                 audit_shapes=[{'action':a['action'],'actor_present':bool(a['user_id']),'keys':list(a['data'])} for a in logs]),default=str)+'\n')
                report['workspaces'][schema]=dict(counts=dict(counts),findings=dict(exceptions),mutable_change_traces=traced)
                print(schema+': '+json.dumps(report['workspaces'][schema]),flush=True)
            del raw,prepared,expected,accepted_rows
    details.close()
    report['completed_at']=timezone.now().isoformat()
    (out/'followup-summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print('FOLLOWUP_COMPLETE',flush=True)


if __name__=='__main__':main()
