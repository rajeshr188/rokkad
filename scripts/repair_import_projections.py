"""Bounded September 30 repairs. Default is read-only; --apply requires a backup.

Run in the reviewed candidate image with restricted production DB credentials.
Mount the private deployment directory at /evidence, this run's output at /repair.
All customer-level evidence stays on the server. No SQL restore or re-import.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
from itertools import batched
sys.path.insert(0, '/code')
import django
django.setup()
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.utils import timezone
from apps.orgs.models import Company
from apps.orgs.audit import AuditLog
from apps.tenancy.context import workspace_context
from apps.tenant_apps.data_portability import linode_run as run
from apps.tenant_apps.data_portability.legacy_dump import parse_copy
from apps.tenant_apps.data_portability.source_particulars import imported_loan_particulars
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.history_contract import digest
from apps.tenant_apps.loans.services.opening_evidence import read_opening_evidence
from apps.tenant_apps.loans.services.opening_repairs import restore_opening_quantities
from apps.tenant_apps.loans.services.license_series import configure_sequence, reserve_sequence_through
from apps.tenant_apps.loans.services.license_continuation import _overlapping_prefixes
from apps.tenant_apps.loans.services.action_access import require_setup_administration, require_workspace_action

PACKAGE = '650becbb16bcd44c2cb9af2281eaeb3d5497dda72a546aaa790b2cc125028400'


def invariant_digest(loan):
    """Exclude only the authorized descriptive column; later servicing is locked."""
    items=list(loan.collateral_items.order_by('pk').values())
    for item in items:item.pop('quantity')
    value={'loan':m.PawnLoan.objects.filter(pk=loan.pk).values().get(), 'items':items,
           'events':list(loan.loan_events.order_by('pk').values()),
           'issues':list(m.LoanDocumentIssue.objects.filter(source_type='PawnLoan',source_id=str(loan.pk)).order_by('pk').values('pk','pdf_hash','source_snapshot'))}
    return digest(json.loads(json.dumps(value,default=str)))


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    base,out=Path('/evidence'),Path('/repair')
    root,manifest=run.load_package(base/'package',PACKAGE)
    run.runtime_guard('rokkad_production_20260924')
    source=base/'import-confidence-20260930/jcl.copy'
    seal=json.loads((base/'import-confidence-20260930/audit-seal.json').read_text())
    assert run.sha_file(source)==seal['private_files']['jcl.copy']['sha256']
    config=next(r for r in run.source_series_configuration(parse_copy(source.read_bytes(),'jcl')) if r['id']=='6')
    assert config['prefix']=='' and config['last_used']==9999
    actor=get_user_model().objects.get(pk=1,email__iexact='rajeshrathodh@gmail.com',is_active=True)
    if args.apply:
        assert (out/'backup-confirmed.json').is_file(), 'A verified server-side backup is required.'
    else:
        with connection.cursor() as cursor:cursor.execute('SET default_transaction_read_only=on')
    report={'at':timezone.now().isoformat(),'mode':'apply' if args.apply else 'read-only','workspaces':{}}
    with workspace_context(1):
        ws=Company.objects.select_for_update().get(pk=1) if args.apply else Company.objects.get(pk=1)
        series=m.LoanSeries.objects.select_related('license').get(pk=5)
        checkpoint=AuditLog.objects.get(company=ws,action='DATA_IMPORT',data__linode_run=PACKAGE,data__phase='setup')
        assert checkpoint.data['mapping']['series']['6']['series_id']==series.pk
        sequences=m.LoanNumberSequence.objects.filter(workspace_id=1,document_kind='PAWN_LOAN')
        if args.apply:sequences=sequences.select_for_update()
        sequences=list(sequences);sequence=next(s for s in sequences if s.series_id==5)
        assert sequence.prefix in ('LEGACY6-','') and sequence.maximum_number==10000
        assert not m.PawnLoan.objects.filter(series=series,historical_import__isnull=True).exists(), 'New native use needs a fresh review.'
        assert not any(s.pk!=sequence.pk and _overlapping_prefixes('',s.prefix) for s in sequences)
        numeric=[int(n) for n in m.PawnLoan.objects.values_list('loan_number',flat=True) if re.fullmatch(r'[0-9]+',n)]
        last=max([config['last_used'],*numeric])
        assert last<=sequence.maximum_number and sequence.next_number<=sequence.maximum_number+1
        before={'prefix':sequence.prefix,'next':sequence.next_number,'width':sequence.width,'maximum':sequence.maximum_number}
        if args.apply:
            if sequence.prefix!='':
                sequence=configure_sequence(series=series,document_kind='PAWN_LOAN',prefix='',width=sequence.width,maximum_number=sequence.maximum_number,actor=actor)
            sequence=reserve_sequence_through(series=series,document_kind='PAWN_LOAN',last_used_number=last,
                evidence_reference='Owner-approved import-confidence repair 2026-09-30; sealed source '+manifest['archive_sha256'],actor=actor)
        report['numbering']={'before':before,'after':{'prefix':sequence.prefix if args.apply else '',
            'next':sequence.next_number if args.apply else max(sequence.next_number,last+1)},'source_last_used':last}
    for schema,wid in {'jcl':1,'jsk':2,'lakshmipawnbroker':3}.items():
        with workspace_context(wid):
            ws=Company.objects.get(pk=wid);require_setup_administration(wid,actor);require_workspace_action(ws,actor,'data.import')
            origins=list(m.HistoricalLoanImport.objects.filter(source_namespace=manifest['namespace']).order_by('pk').values_list('pk','source_sha256'))
        total=changed=already=0
        for group in batched(origins,100):
            with workspace_context(wid):
                for pk,sha in group:
                    origin=m.HistoricalLoanImport.objects.get(pk=pk)
                    loan=m.PawnLoan.objects.select_for_update().get(pk=origin.loan_id) if args.apply else origin.loan
                    assert sha==digest(origin.document)
                    opening=read_opening_evidence(loan,loan.loan_events.get(event_kind='MIGRATION_OPENING'))
                    assert opening['review']==origin.document['review'] and opening['item_mapping']==origin.references['items']
                    items={i.pk:i for i in loan.collateral_items.all()}
                    assert set(items)==set(origin.references['items'].values())
                    missing=0
                    for row in opening['review']['collateral']:
                        current=items[origin.references['items'][row['id']]].quantity
                        assert current is None or current==row['quantity'], 'Conflicting quantity: no overwrite authorized.'
                        total+=1;missing+=int(current is None);already+=int(current is not None)
                    if args.apply:
                        before_hash=invariant_digest(loan)
                        count=restore_opening_quantities(workspace_id=wid,actor=actor,origin_id=pk,expected_sha256=sha)
                        assert count==missing
                        assert before_hash==invariant_digest(loan), 'Financial/custody/issued evidence changed.'
                        changed+=count
                    else:changed+=missing
        report['workspaces'][schema]={'loans':len(origins),'source_quantities':total,
            'filled' if args.apply else 'would_fill':changed,'already_matched':already}
        print(schema+': '+json.dumps(report['workspaces'][schema]),flush=True)
        (out/('applied.json' if args.apply else 'preflight.json')).write_text(json.dumps(report,indent=2))
    with workspace_context(1):
        loan=m.PawnLoan.objects.get(loan_number='C04526')
        details=imported_loan_particulars([loan])[loan.pk]
        assert details['borrower'] and details['address'] and details['tenure_months'] is not None
        report['C04526_retained_particulars_available']=True
        assert not m.PledgeBookBatch.objects.exists(), 'Unexpected permanent print batch; inspect, do not alter it.'
    report['state']='PASS';report['completed_at']=timezone.now().isoformat()
    (out/('applied.json' if args.apply else 'preflight.json')).write_text(json.dumps(report,indent=2))
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
