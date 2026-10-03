"""Read-only, post-cutover audit of the sealed three-branch Linode import.

Operator-only script, run with the deployed code and restricted runtime DB role.
Paths are supplied by the private server launcher; output contains private IDs.
Never run replay/commit or write audit evidence into the application database.
"""
import argparse
from collections import Counter
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN
import json
import os
from pathlib import Path
import sys
from uuid import UUID, uuid5

sys.path.insert(0, '/code')
import django
django.setup()

from django.db import connection, transaction
from django.db.models import Count
from django.utils import timezone
from apps.tenancy.context import workspace_context
from apps.orgs.audit import AuditLog
from apps.tenant_apps.data_portability import linode_run as run, contracts, child_contracts, legacy_opening, legacy_media
from apps.tenant_apps.data_portability.legacy_dump import parse_copy
from apps.tenant_apps.data_portability.models import SourceIdentity, ChildSourceIdentity, LoanHistoryBatch, LegacyMediaReceipt
from apps.tenant_apps.loans import models as loans
from apps.tenant_apps.loans.services.history_contract import digest
from apps.tenant_apps.loans.services.archive_contract import review_document
from apps.tenant_apps.loans.services.opening_evidence import read_opening_evidence
from apps.tenant_apps.loans.services.opening_continuation import preview_opening_collection, opening_interest_breakdown
from apps.tenant_apps.loans.selectors.balances import calculate_pawn_loan_balance
from apps.tenant_apps.party.models import Party, PartyAddress, PartyContactMethod, PartyDocument


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--package-sha256', required=True)
    parser.add_argument('--database', required=True)
    args = parser.parse_args()
    base, out = Path(args.evidence), Path(args.output)
    os.umask(0o077)
    root, manifest = run.load_package(base / 'package', args.package_sha256)
    source_sha = run.sha_file(base / 'source/source.dump')
    run.require(source_sha == manifest['archive_sha256'], 'Source archive hash differs.')
    mapping = json.loads((base / 'run/workspace-map.json').read_text())
    run.validate_workspace_map(mapping)
    run.require(json.loads((base / 'run/binding.json').read_text()) == {
        'package_sha256': args.package_sha256, 'database': args.database, 'workspaces': mapping}, 'Binding differs.')
    report = dict(started_at=timezone.now().isoformat(), package_sha256=args.package_sha256,
                  source_sha256=source_sha, package_files=len(manifest['files']), workspaces={},
                  database=args.database, scope='Frozen import and current canonical readers; no business writes')
    details = (out / 'findings.jsonl').open('w', encoding='utf-8')
    scope, counters = '', Counter()

    def finding(code, key, **extra):
        counters[code] += 1
        details.write(json.dumps(dict(workspace=scope, code=code, source_id=key, **extra), default=str) + '\n')

    def check(condition, code, key):
        if not condition:
            finding(code, key)

    # Hash-preserved source is freshly extracted by pg_restore in an offline container.
    # Its output is parsed as inert COPY text; SQL is never restored/executed.
    indexes = {}
    for schema in mapping:
        extracted = {'tables': parse_copy((out / f'{schema}.copy').read_bytes(), schema)}
        indexes[schema] = run.source_index(extracted)
        old = json.loads((root / schema / 'source-index.json').read_text())
        run.require(not any(run.compare_index(old, indexes[schema]).values()), 'Fresh source index differs.')
        del extracted
    report['fresh_source_indexes_match'] = True
    print('Source archive, sealed inputs and all three freshly extracted source indexes match.', flush=True)

    run.runtime_guard(args.database)
    with connection.cursor() as cursor:
        cursor.execute('SET default_transaction_read_only = on')
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            cursor.execute('SET LOCAL statement_timeout = %s', ['60s'])
            cursor.execute('SELECT current_user, current_setting(\'transaction_read_only\'), current_setting(\'transaction_isolation\'), transaction_timestamp()')
            role, readonly, isolation, snapshot = cursor.fetchone()
        run.require(readonly == 'on' and isolation == 'repeatable read', 'Read-only snapshot not established.')
        report['snapshot'] = dict(role=role, read_only=readonly, isolation=isolation, at=snapshot.isoformat())
        for schema, wid in mapping.items():
            scope, counters = schema, Counter()
            meta, source_index = manifest['workspaces'][schema], indexes[schema]
            summary = dict(workspace_id=wid)
            report['workspaces'][schema] = summary
            with workspace_context(wid):
                checkpoint = AuditLog.objects.get(company_id=wid, action='DATA_IMPORT', data__linode_run=args.package_sha256, data__phase='setup')
                check(checkpoint.data['config_sha256'] == digest(json.loads((root/schema/'setup.json').read_text())), 'setup_hash_mismatch', 'setup')
                masters = {s.external_id: s for s in SourceIdentity.objects.filter(source_system=meta['source_system']).select_related('identity__party')}
                kids = {(s.profile,s.external_id):s for s in ChildSourceIdentity.objects.filter(source_system=meta['source_system']).select_related('identity__contact','identity__address')}
                expected_counts, party_changes = Counter(), Counter()
                for entry in meta['party_batches']:
                    profile = entry['profile']
                    for raw in run.read_rows(root / entry['path']):
                        canonical, issues = (contracts.validate_record(raw, canonical_source=True) if profile == contracts.PROFILE
                            else child_contracts.validate_child(raw, canonical_source=True, profile=profile))
                        check(not any(i['severity']=='ERROR' for i in issues), 'invalid_packaged_party', raw['id'])
                        expected_counts[profile] += 1
                        source = masters.get(raw['id']) if profile == contracts.PROFILE else kids.get((profile,raw['id']))
                        if source is None:
                            finding('missing_party_identity', raw['id']); continue
                        check(source.accepted_digest == contracts.source_digest(canonical), 'accepted_party_digest_mismatch', raw['id'])
                        if profile == contracts.PROFILE:
                            obj = source.identity.party
                            fields = [k for k in contracts.FIELDS if k not in {'primary_phone','primary_email'}]
                            current = contracts.semantic(obj)
                        else:
                            obj = source.identity.contact if profile == child_contracts.CONTACT else source.identity.address
                            check(source.identity.parent_id == masters[raw['party_external_id']].identity_id, 'party_parent_mismatch',raw['id'])
                            if obj is None:
                                finding('current_child_missing',raw['id']); continue
                            fields, current = child_contracts.fields(profile), child_contracts.semantic(profile,obj)
                        changed = [k for k in fields if current[k] != canonical[k]]
                        if changed:
                            party_changes[profile] += 1
                            finding('mutable_party_changed_requires_trace',raw['id'],profile=profile,pk=obj.pk,fields=changed,
                                    updated_at=getattr(obj,'updated_at',None),updated_by=getattr(obj,'updated_by_id',None))
                check(dict(expected_counts)==meta['party_counts'], 'party_package_count_mismatch', 'counts')
                check(len(masters)==expected_counts[contracts.PROFILE], 'master_alias_count_mismatch','counts')
                check(len(kids)==sum(expected_counts[p] for p in (child_contracts.CONTACT,child_contracts.ADDRESS)), 'child_alias_count_mismatch','counts')
                check(len({s.identity_id for s in masters.values()}) == len(masters), 'distinct_parties_merged','counts')
                check(len({s.identity_id for s in kids.values()}) == len(kids), 'distinct_children_merged','counts')
                summary['accepted_party_counts'] = dict(expected_counts)
                summary['mutable_party_changes'] = dict(party_changes)
                summary['current_party_counts'] = dict(parties=Party.objects.count(),contacts=PartyContactMethod.objects.count(),addresses=PartyAddress.objects.count())
                expected = {}
                for row in run.read_rows(root/schema/'openings.jsonl'):
                    review = row['opening']['review']
                    external = str(uuid5(uuid5(UUID(manifest['namespace']),schema),review['mapping']['borrower_external_id']))
                    document = run.rebind_opening(row,workspace_id=wid,borrower_id=masters[external].identity.party_id,setup_map=checkpoint.data['mapping'])
                    key = document['review']['source']['loan_id']
                    check(key not in expected,'duplicate_packaged_opening',key)
                    expected[key]=(document,row['source_evidence'])
                batches = {b.source_sha256:b for b in LoanHistoryBatch.objects.filter(profile=legacy_opening.PROFILE,state='COMPLETED')}
                origins = loans.HistoricalLoanImport.objects.filter(source_namespace=manifest['namespace']).select_related('loan__policy_snapshot').prefetch_related('loan__loan_events','loan__collateral_items','loan__repayment_schedules__obligations')
                seen, states, event_counts, coverage = set(),Counter(),Counter(),Counter()
                opening_totals = {k:Decimal(0) for k in ('principal','interest','fees')}
                current_totals = {k:Decimal(0) for k in opening_totals}
                for origin in origins.iterator(chunk_size=100):
                    key = origin.document['review']['source']['loan_id']
                    if key not in expected:
                        finding('unexpected_imported_opening',key);continue
                    check(key not in seen,'duplicate_admitted_opening',key);seen.add(key)
                    document,evidence = expected[key]
                    check(origin.document==document and origin.source_sha256==digest(document),'frozen_opening_mismatch',key)
                    batch=batches.get(origin.source_sha256)
                    check(batch is not None and batch.result_id==origin.pk and batch.document=={'opening':document,'source_evidence':evidence},'opening_source_batch_mismatch',key)
                    for rec in evidence['records']:
                        check(rec['source_sha256']==source_index.get(rec['source']['external_id']),'opening_source_record_mismatch',key)
                    review,loan=document['review'],origin.loan
                    check(loan.loan_number==review['source']['number'] and loan.borrower_id==review['mapping']['borrower_id'],'loan_identity_mismatch',key)
                    check(str(loan.loan_date)==review['terms']['original_date'],'original_date_mismatch',key)
                    events=tuple(loan.loan_events.all()); opening=[e for e in events if e.event_kind=='MIGRATION_OPENING']
                    check(len(opening)==1,'opening_event_count_mismatch',key)
                    items={i.pk:i for i in loan.collateral_items.all()}
                    check(len(items)==len(review['collateral']),'collateral_count_mismatch',key)
                    for row in review['collateral']:
                        item=items.get(origin.references['items'][row['id']])
                        check(item is not None and item.description==row['description'] and item.metal==row['metal']
                            and item.gross_weight is None and item.net_weight==Decimal(row['net_weight'])
                            and item.purity_percentage==Decimal(row['purity']) and item.allocated_principal==Decimal(row['remaining_principal'])
                            and item.monthly_interest_rate==Decimal(row['monthly_rate']),'collateral_economics_mismatch',key)
                    later=[e for e in events if e.event_kind!='MIGRATION_OPENING']
                    states[loan.state]+=1;event_counts.update(e.event_kind for e in later)
                    if later:
                        coverage['loans_with_later_events']+=1
                    if any(not e.created_by_id for e in later):
                        finding('later_event_missing_actor',key)
                    if loan.state!='ACTIVE' and not later:
                        finding('changed_state_without_later_event',key)
                    if any(i.custody_state!='IN_VAULT' for i in items.values()) and not later:
                        finding('changed_custody_without_later_event',key)
                    cutover=date.fromisoformat(review['cutover']['date'])
                    try:
                        read_opening_evidence(loan,opening[0])
                        for label, selected, day, totals in [('opening',tuple(opening),cutover,opening_totals),('current',events,timezone.localdate(),current_totals)]:
                            bal=calculate_pawn_loan_balance(loan,events=selected,collateral_items=tuple(items.values()),policy_snapshot=loan.policy_snapshot,as_of_date=day,pending_delivery_blocks=False)
                            for field in totals:
                                value=getattr(bal,field+'_outstanding');totals[field]+=value
                                if label=='opening':check(value==Decimal(review['balances'][field]),'opening_balance_mismatch',key)
                            coverage[label+'_balances_read']+=1
                        continuation=preview_opening_collection(loan,events=tuple(opening),as_of_date=cutover)
                        boundary=preview_opening_collection(loan,events=tuple(opening),as_of_date=continuation.next_increase_on)
                        breakdown=opening_interest_breakdown(review,as_of_date=continuation.next_increase_on)
                        check(continuation.additional_interest==0 and breakdown['charge_months']==review['continuation']['additional_months']+1
                              and boundary.baseline_as_of==(continuation.monthly_interest_unrounded*breakdown['charge_months']).quantize(Decimal('1'),rounding=ROUND_HALF_EVEN),'interest_boundary_mismatch',key)
                        preview_opening_collection(loan,events=events,as_of_date=timezone.localdate())
                        coverage['interest_readers_passed']+=1
                    except Exception as exc:
                        finding('reader_exception',key,error_type=type(exc).__name__,message=str(exc))
                    wanted=sorted((o['due'],Decimal(o['principal']),Decimal(o['interest'])) for o in review['obligations'])
                    check(any(sorted((str(o.due_date),o.principal_due,o.interest_due) for o in s.obligations.all())==wanted for s in loan.repayment_schedules.all()),'original_schedule_missing',key)
                    coverage['tenure_'+evidence['maturity_review']['basis']]+=1
                    coverage['has_retained_borrower_record']+=int(any(r['source']['table']=='contact_customer' for r in evidence['records']))
                    coverage['loans_with_unknown_original_valuation']+=int(any(r['valuation'].get('date')!=review['terms']['original_date'] for r in review['collateral']))
                    if schema=='jcl' and loan.loan_number=='C04526':
                        summary['C04526']=dict(frozen_opening_matches=origin.document==document,source_records_match=all(r['source_sha256']==source_index.get(r['source']['external_id']) for r in evidence['records']),
                            source_borrower_record_present=any(r['source']['table']=='contact_customer' for r in evidence['records']),current_borrower_address_count=PartyAddress.objects.filter(party_id=loan.borrower_id).count(),
                            tenure_basis=evidence['maturity_review']['basis'],original_valuations_known=all(r['valuation'].get('date')==review['terms']['original_date'] for r in review['collateral']),
                            quantity_recorded=all(r.get('quantity') is not None for r in review['collateral']),gross_weight_recorded=all(r.get('gross_weight') is not None for r in review['collateral']))
                for key in set(expected)-seen:finding('missing_imported_opening',key)
                summary.update(openings=len(seen),imported_states=dict(states),later_events=dict(event_counts),coverage=dict(coverage),opening_totals={k:str(v) for k,v in opening_totals.items()},current_imported_totals={k:str(v) for k,v in current_totals.items()})
                closed_ids=set()
                archive_supplements=Counter()
                # Only bounded batches of full archived documents in memory.
                from itertools import batched
                for group in batched(run.read_rows(root/schema/'closed.jsonl'),200):
                    actual={e.source_id:e for e in loans.HistoricalLoanEvidence.objects.filter(source_namespace=manifest['namespace'],source_id__in=[d['source']['loan_id'] for d in group])}
                    for document in group:
                        key=document['source']['loan_id'];check(key not in closed_ids,'duplicate_packaged_archive',key);closed_ids.add(key)
                        e=actual.get(key)
                        check(e is not None and e.document==document and e.source_sha256==digest(document) and e.review==review_document(document),'closed_evidence_mismatch',key)
                        check(e is not None and e.source_system==meta['source_system'],'archive_provenance_mismatch',key)
                        for rec in document['source_records']:
                            if 'source' in rec:
                                check(rec.get('source_sha256')==source_index.get(rec['source']['external_id']),'archive_source_record_mismatch',key)
                            else:
                                # Adapter/owner decisions are supplements, not source rows.
                                # Exact document/hash equality above covers their preservation.
                                archive_supplements['owner_decision' if 'owner_decision' in rec else 'adapter_interpretation']+=1
                check(loans.HistoricalLoanEvidence.objects.filter(source_namespace=manifest['namespace']).count()==len(closed_ids),'archive_cohort_count_mismatch','counts')
                excluded={r['source_id'] for r in run.read_rows(root/schema/'excluded.jsonl')}
                source_ids={k for k in source_index if k.startswith('girvi_loan:')}
                partition=not(seen&closed_ids or seen&excluded or closed_ids&excluded) and seen|closed_ids|excluded==source_ids
                check(partition,'source_partition_mismatch','all')
                summary.update(closed=len(closed_ids),excluded=len(excluded),archive_supplements=dict(archive_supplements),all_source_ids_accounted_once=partition,native_loan_count=loans.PawnLoan.objects.exclude(pk__in=origins.values('loan_id')).count())
                duplicates=list(loans.PawnLoan.objects.values('series_id','loan_number').annotate(n=Count('id')).filter(n__gt=1))
                check(not duplicates,'duplicate_operational_numbers','all')
                summary['findings']=dict(counters)
                print(schema+': '+json.dumps(summary,default=str),flush=True)
                with connection.cursor() as cursor:
                    for model in (Party,loans.PawnLoan,loans.PawnLoanEvent,loans.HistoricalLoanEvidence,LegacyMediaReceipt):
                        cursor.execute('SELECT count(*) FROM '+connection.ops.quote_name(model._meta.db_table)+' WHERE workspace_id<>%s',[wid])
                        run.require(cursor.fetchone()[0]==0,'Cross-workspace exposure.')
        with connection.cursor() as cursor:
            for model in (Party,loans.PawnLoan,loans.HistoricalLoanEvidence):
                cursor.execute('SELECT count(*) FROM '+connection.ops.quote_name(model._meta.db_table))
                run.require(cursor.fetchone()[0]==0,'Missing-context exposure.')
        report['rls_read_checks_passed']=True
    details.close()
    report['completed_at']=timezone.now().isoformat()
    report['findings_sha256']=run.sha_file(out/'findings.jsonl')
    (out/'summary.json').write_text(json.dumps(report,indent=2,default=str)+'\n')
    print('AUDIT_COMPLETE '+json.dumps(dict(completed_at=report['completed_at'],findings_sha256=report['findings_sha256'])),flush=True)


if __name__=='__main__':
    main()
