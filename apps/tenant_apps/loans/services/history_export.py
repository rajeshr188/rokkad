"""Canonical export of the supported financial/custody history, never a full archive."""
from copy import deepcopy
from datetime import date
import uuid

from django.db import transaction
from django.utils import timezone

from apps.orgs.access import resolve_workspace_access
from apps.orgs.models import Company
from apps.orgs.audit import AuditLog
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.selectors.balances import calculate_pawn_loan_balance
from .history_contract import encode, validate, decimal, money, HistoryError, MANIFEST, POLICY, digest
from .history_setup import require_history_setup_access


def _amounts(balance):
    return {"principal":decimal(balance.principal_outstanding),"interest":decimal(balance.interest_outstanding),"fees":decimal(balance.fees_outstanding)}


@transaction.atomic
def export_history(*, workspace_id, actor, loan_id):
    try:
        return _export_history(workspace_id=workspace_id, actor=actor, loan_id=loan_id)
    except (KeyError, TypeError) as exc:
        raise HistoryError("Frozen source evidence is incomplete or invalid for this profile.") from exc


def _export_history(*, workspace_id, actor, loan_id):
    workspace=require_history_setup_access(workspace_id,actor,read_only=True)
    resolve_workspace_access(actor=actor,workspace=workspace).require("data.export")
    Company.all_objects.select_for_update().get(pk=workspace_id)
    workspace=require_history_setup_access(workspace_id,actor,read_only=True)
    resolve_workspace_access(actor=actor,workspace=workspace).require("data.export")
    loan=m.PawnLoan.objects.select_for_update(of=("self",)).select_related("product_version","license_revision","policy_snapshot","disbursal_snapshot__approval_snapshot").get(workspace_id=workspace_id,pk=loan_id)
    if loan.state not in {"ACTIVE","CLOSED"}: raise HistoryError("Only active or fully released histories are supported.")
    product=loan.product_version
    if product.repayment_structure!="FLEXIBLE_PARTIAL_PAYMENT" or product.amortisation_method!="NONE" or product.payment_frequency!="FLEXIBLE" or product.extra_payment_rule!="REDUCE_PRINCIPAL":
        raise HistoryError("This product structure is outside loan-history/1.")
    # Lock existing mutable collateral and the aggregate before taking its materialized snapshot.
    items=list(loan.collateral_items.select_for_update().order_by("pk"))
    events=list(loan.loan_events.select_for_update().order_by("effective_date","pk"))
    if any(e.payload.get("release", {}).get("paper_closure") for e in events):
        raise HistoryError("Paper closures include date-only handovers and per-row evidence not supported by this restore profile. Use release records and the paper batch CSV; database backups retain full evidence.")
    if not items or len(items)>20 or not events or len(events)>240: raise HistoryError("History exceeds profile bounds or lacks evidence.")
    if any(e.event_kind == "MIGRATION_OPENING" for e in events):
        raise HistoryError("Opening-position loans require an opening-aware export; loan-history/1 cannot claim complete origination history.")
    if any(e.event_kind not in {"DISBURSAL","REPAYMENT","INTEREST_ACCRUAL","RELEASE_RECEIPT"} for e in events):
        raise HistoryError("History contains unsupported capitalization, reversal, renewal or auction events.")
    if any(money(e.payload.get("values", {}).get("interest_concession", "0")) != 0 for e in events):
        raise HistoryError("Interest concessions require a wider history profile; loan-history/1 cannot omit interest lost.")
    if any(i.renewed_from_id or i.current_storage_location_id or i.custody_state not in {"IN_VAULT","WITH_CUSTOMER"} for i in items):
        raise HistoryError("Connected renewal, funding or storage-location history is outside this profile.")
    if any(i.funding_pledge_items.exists() or i.storage_movements.exists() for i in items):
        raise HistoryError("Funding or storage movement history requires a wider portability profile.")
    origin=m.HistoricalLoanImport.objects.filter(workspace_id=workspace_id,loan=loan).first()
    from apps.tenant_apps.data_portability.models import WorkspaceNamespace,PartyIdentity
    namespace,_=WorkspaceNamespace.objects.get_or_create(workspace_id=workspace_id)
    def identity(kind, pk): return str(uuid.uuid5(namespace.public_id,f"{kind}:{pk}"))
    def source_actor(pk):
        if pk is None: raise HistoryError("Required original actor evidence is missing.")
        return identity("actor",pk)
    if origin:
        document=deepcopy(origin.document)
        source=document["loan"]
        item_ids={pk:key for key,pk in origin.references["items"].items()}
        event_ids={pk:key for key,pk in origin.references["events"].items()}
        original_events={row["id"]:row for row in source["events"]}
        if set(item_ids)!=set(i.pk for i in items): raise HistoryError("Collateral membership changed; this export profile cannot omit it.")
    else:
        if loan.license_revision_id is None: raise HistoryError("Original licence revision is missing.")
        try: snapshot=loan.disbursal_snapshot; policy=loan.policy_snapshot
        except (m.PawnLoanDisbursalSnapshot.DoesNotExist,m.LoanPolicySnapshot.DoesNotExist) as exc: raise HistoryError("Frozen disbursal evidence is required.") from exc
        if snapshot is None or policy is None: raise HistoryError("Frozen disbursal evidence is required.")
        approval=snapshot.approval_snapshot
        frozen={row["item_id"]:row for row in approval.payload.get("collateral",[])}
        tranches={int(row["collateral_item_id"]):row for row in snapshot.evidence.get("tranches",[])}
        if set(frozen)!=set(i.pk for i in items) or set(tranches)!=set(frozen): raise HistoryError("Frozen approval and tranche coverage is incomplete.")
        party,_=PartyIdentity.objects.get_or_create(workspace_id=workspace_id,party=loan.borrower)
        item_ids={i.pk:str(i.public_id) for i in items}; event_ids={}; original_events={}
        policy_values={key:getattr(policy,key) for key in POLICY['properties']}
        for key,val in policy_values.items():
            if hasattr(val,'as_tuple'): policy_values[key]=decimal(val)
        collateral=[]
        quotes=approval.payload.get("origination_rates",{}).get("quotes",{})
        for item in items:
            row=frozen[item.pk]; tranche=tranches[item.pk]
            quote=quotes.get(item.metal,{})
            market=quote.get("buying_rate")
            if policy.valuation_method!="LATEST_APPRAISAL" and market is None: raise HistoryError("Historical market quote evidence is missing.")
            collateral.append(dict(id=item_ids[item.pk],description=row["description"],metal=row["metal"],gross_weight=row["gross_weight"],
                net_weight=row["net_weight"],purity=row["purity_percentage"],principal=tranche["allocated_principal"],monthly_rate=tranche["monthly_interest_rate"],
                metal_rate=market,appraised_value=tranche.get("latest_appraised_value"),valuation_reference="approval:"+approval.fingerprint))
        schedule=loan.repayment_schedules.get(version=1)
        source=dict(id=identity("loan",loan.pk),number=loan.loan_number,state=loan.state,
            borrower=dict(source_system="rokkad:"+str(namespace.public_id),id=str(party.public_id)),licence_number=loan.license_revision.license_number,
            disbursed_on=loan.loan_date.isoformat(),tenure_months=loan.tenure_months,calculation_contract=product.calculation_contract_version,
            grace_days=product.operational_grace_days,approval=dict(at=approval.approved_at.isoformat(),actor=source_actor(approval.approved_by_id),reference="approval:"+approval.fingerprint),
            policy=policy_values,collateral=collateral,
            disbursal=dict(advance_periods=snapshot.advance_interest_periods,
                fees=[dict(code=f["code"],name=f["name"],kind=f["calculation_type"],value=f["policy_value"],deducted=f["deducted_at_disbursal"]) for f in snapshot.evidence.get("fees",[])],
                principal=decimal(snapshot.gross_principal),monthly_interest=decimal(snapshot.monthly_interest),advance_interest=decimal(snapshot.advance_interest),
                deducted_fees=decimal(snapshot.deducted_fees),net_cash=decimal(snapshot.net_disbursed)),
            schedule=dict(maturity=schedule.maturity_date.isoformat(),principal=decimal(schedule.principal),interest=decimal(schedule.contractual_interest),
                obligations=[dict(sequence=o.sequence,due=o.due_date.isoformat(),principal=decimal(o.principal_due),interest=decimal(o.interest_due)) for o in schedule.obligations.order_by("sequence")]),events=[],cutover={})
        document=dict(manifest=dict(profile="loan-history/1",namespace=str(namespace.public_id),as_of=timezone.localdate().isoformat(),coverage="PARTIAL",
            exclusions=MANIFEST["properties"]["exclusions"]["const"]),loan=source)
    if loan.loan_date.isoformat()!=source["disbursed_on"] or loan.tenure_months!=source["tenure_months"] or money(source["disbursal"]["principal"])!=loan.principal_amount:
        raise HistoryError("Loan terms changed from frozen source evidence.")
    source_items={row["id"]:row for row in source["collateral"]}
    for item in items:
        row=source_items[item_ids[item.pk]]
        if item.description!=row["description"] or item.metal!=row["metal"] or any(money(row[k])!=getattr(item,f) for k,f in (("gross_weight","gross_weight"),("net_weight","net_weight"),("purity","purity_percentage"),("principal","allocated_principal"),("monthly_rate","monthly_interest_rate"))):
            raise HistoryError("Collateral changed from frozen history.")
    accruals=list(loan.interest_accruals.order_by("period_number"))
    if any(a.loan_event_id is None for a in accruals): raise HistoryError("This history contains accrual evidence without a source event; it needs a wider export profile.")
    accrual_map={a.loan_event_id:a for a in accruals}
    prefix=[]; output=[]
    for event in events:
        prefix.append(event)
        key=event_ids.get(event.pk,identity("event",event.pk))
        values=event.payload.get("values",{})
        balance=calculate_pawn_loan_balance(loan,events=prefix,collateral_items=items,policy_snapshot=loan.policy_snapshot,as_of_date=event.effective_date,pending_delivery_blocks=False)
        row=dict(id=key,kind=event.event_kind,date=event.effective_date.isoformat(),actor=event.payload.get("historical_source",{}).get("actor") or source_actor(event.created_by_id),
            principal=decimal(values.get("principal",0)),interest=decimal(values.get("interest",0)),fees=decimal(values.get("fees",0)),balance=_amounts(balance),allocations=[],accrual=None,release=None)
        if event.event_kind in {"REPAYMENT","RELEASE_RECEIPT"}:
            lines=(event.repayment_allocation_lines if hasattr(event,"repayment_allocation_lines") else m.PawnLoanRepaymentAllocationLine.objects.filter(loan_event=event)) if event.event_kind=="REPAYMENT" else m.PawnLoanPrincipalClosingLine.objects.filter(loan_event=event)
            row["allocations"]=[dict(item=item_ids[line.collateral_item_id],before=decimal(line.balance_before),principal=decimal(line.principal_applied if event.event_kind=="REPAYMENT" else line.principal_settled),after=decimal(line.balance_after)) for line in lines.order_by("allocation_order")]
        if event.event_kind=="INTEREST_ACCRUAL":
            a=accrual_map.get(event.pk)
            if a is None: raise HistoryError("Accrual event has no period evidence.")
            row["accrual"]=dict(period=a.period_number,start=a.period_start.isoformat(),end=a.period_end.isoformat(),fraction=decimal(a.period_fraction),base=decimal(a.calculation_base),unrounded=decimal(a.unrounded_interest),recognized=decimal(a.recognized_interest))
        if event.event_kind=="RELEASE_RECEIPT":
            release=m.PawnLoanRelease.objects.get(loan_event=event)
            release_items=list(release.items.order_by("collateral_item_id"))
            if set(i.collateral_item_id for i in release_items)!=set(item_ids) or not release_items or len({i.returned_at for i in release_items})!=1:
                raise HistoryError("Full custody return evidence is incomplete or outside this profile.")
            if key in original_events:
                row["release"]=deepcopy(original_events[key]["release"])
            else:
                valuations=[]
                for item in release_items:
                    value=item.valuation_snapshot.get("valuation_amount", item.valuation_snapshot.get("value"))
                    if value is None: raise HistoryError("Release valuation evidence is missing.")
                    valuations.append(dict(item=item_ids[item.collateral_item_id],value=decimal(value)))
                row["release"]=dict(number=release.release_number,returned_at=timezone.localtime(release_items[0].returned_at).isoformat(),collector=None,valuation=valuations)
        output.append(row)
    source["events"]=output; source["state"]=loan.state
    # Preserve the original cutover for an unchanged imported graph. New native events extend it.
    if not origin or set(event_ids)!=set(e.pk for e in events):
        document["manifest"]["as_of"]=max(timezone.localdate(),events[-1].effective_date).isoformat()
    cutoff=date.fromisoformat(document["manifest"]["as_of"])
    source["cutover"]=_amounts(calculate_pawn_loan_balance(loan,events=events,collateral_items=items,policy_snapshot=loan.policy_snapshot,as_of_date=cutoff,pending_delivery_blocks=False))
    if (loan.state=="CLOSED") != (events[-1].event_kind=="RELEASE_RECEIPT") or any(i.custody_state!=("WITH_CUSTOMER" if loan.state=="CLOSED" else "IN_VAULT") for i in items):
        raise HistoryError("Loan state and custody history disagree.")
    from .history_import import _chronology
    _chronology(document)
    validate(document)
    content = encode(document)
    AuditLog.log("DATA_EXPORT", company=workspace, user=actor, description="Exported partial canonical loan history.",
        data={"loan":loan.pk,"profile":"loan-history/1","sha256":digest(document)})
    return content
