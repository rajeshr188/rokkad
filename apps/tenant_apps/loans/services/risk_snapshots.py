import hashlib
import json
from datetime import date

from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone

from apps.tenant_apps.loans.domain import detect_risk_transitions
from apps.tenant_apps.loans.domain import PawnLoanState
from apps.tenant_apps.loans.models import LoanRiskEvent, LoanRiskSnapshot, PawnLoan, current_tenant_workspace_id
from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
from apps.tenant_apps.loans.selectors.delinquency import get_pawn_loan_delinquency
from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
from apps.tenant_apps.loans.selectors.risk import get_pawn_loan_risk_assessment


class RiskSnapshotRefreshError(ValueError):
    pass


def refresh_loan_risk_snapshot(loan_id: int, *, as_of_date: date):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise RiskSnapshotRefreshError("Risk refresh requires an active tenant schema.")
    if not PawnLoan.objects.filter(
        pk=loan_id,
        workspace_id=workspace_id,
        state=PawnLoanState.ACTIVE.value,
    ).exists():
        raise RiskSnapshotRefreshError(
            "Only an active PawnLoan in the current workspace can be assessed."
        )
    before = _source_fingerprint(loan_id, workspace_id, as_of_date)
    try:
        exposure = get_pawn_loan_exposure(loan_id, as_of_date=as_of_date)
        delinquency = get_pawn_loan_delinquency(loan_id, as_of_date=as_of_date)
        collateral = get_pawn_loan_collateral_valuation(loan_id, as_of_date=as_of_date)
        assessment = get_pawn_loan_risk_assessment(loan_id, as_of_date=as_of_date)
    except Exception as exc:
        _record_error(loan_id, workspace_id, as_of_date, before, exc)
        raise RiskSnapshotRefreshError(str(exc)) from exc
    with transaction.atomic():
        loan = PawnLoan.objects.select_for_update().get(pk=loan_id, workspace_id=workspace_id)
        snapshot = LoanRiskSnapshot.objects.select_for_update().filter(loan=loan).first()
        old_projection = _projection(snapshot)
        after = _source_fingerprint(loan_id, workspace_id, as_of_date)
        if before != after:
            if snapshot:
                snapshot.status = LoanRiskSnapshot.Status.STALE
                snapshot.error_message = "Source evidence changed during assessment; refresh required."
                snapshot.save(update_fields=("status", "error_message", "updated_at"))
            raise RiskSnapshotRefreshError("Source evidence changed during assessment; retry refresh.")
        values = _snapshot_values(
            workspace_id=workspace_id,
            as_of_date=as_of_date,
            exposure=exposure,
            delinquency=delinquency,
            collateral=collateral,
            assessment=assessment,
            input_fingerprint=after,
            assessed_at=timezone.now(),
        )
        if snapshot is None:
            snapshot = LoanRiskSnapshot.objects.create(loan=loan, **values)
        else:
            for key, value in values.items(): setattr(snapshot, key, value)
            snapshot.save()
        _persist_transitions(snapshot, old_projection, _projection(snapshot))
        return snapshot


def _snapshot_values(*, workspace_id, as_of_date, exposure, delinquency,
                     collateral, assessment, input_fingerprint, assessed_at):
    return dict(
            workspace_id=workspace_id, as_of_date=as_of_date,
            exposure=exposure.total_economic_exposure, due=exposure.due_now.total,
            overdue=exposure.overdue.total, days_past_due=delinquency.assessment.days_past_due,
            days_to_maturity=assessment.days_to_maturity,
            collateral_value=collateral.eligible_collateral_value, ltv_ratio=collateral.ltv.ltv_ratio,
            performance_class=assessment.performance_class, severity=assessment.severity,
            action_hint=assessment.action_hint, flags=list(assessment.flags),
            explanations=list(assessment.explanations), policy_identity=assessment.policy_identity,
            source_provenance={
                "calculation_contract": "LOAN_RISK_SNAPSHOT_V1",
                "policy_identity": assessment.policy_identity,
                "collateral_policy_identity": collateral.compliance_profile,
                "appraisal_ids": sorted(
                    {row.appraisal_id for row in collateral.items
                    if row.appraisal_id is not None
                    }
                ),
                "valuation_rate_ids": sorted(
                    {row.rate_id for row in collateral.items if row.rate_id is not None}
                ),
                "collateral_item_ids": sorted(
                    row.collateral_item_id for row in collateral.items
                ),
            },
            assessment_fingerprint=assessment.fingerprint,
            input_fingerprint=input_fingerprint,
            status=LoanRiskSnapshot.Status.CURRENT, error_message="",
            assessed_at=assessed_at,
        )


def rebuild_current_risk_snapshots(*, as_of_date: date, loan_ids=None):
    workspace_id = current_tenant_workspace_id()
    queryset = PawnLoan.objects.filter(workspace_id=workspace_id).order_by("pk")
    if loan_ids is not None: queryset = queryset.filter(pk__in=loan_ids)
    results = {"current": 0, "errors": []}
    for loan_id in queryset.values_list("pk", flat=True).iterator():
        try:
            refresh_loan_risk_snapshot(loan_id, as_of_date=as_of_date); results["current"] += 1
        except RiskSnapshotRefreshError as exc:
            results["errors"].append({"loan_id": loan_id, "error": str(exc)})
    return results


def reassess_pawn_loans_batch(*, workspace_id: int, as_of_date: date, batch_size=100):
    batch_size = int(batch_size)
    if not 1 <= batch_size <= 1000:
        raise RiskSnapshotRefreshError("Batch size must be between 1 and 1000.")
    active_workspace_id = current_tenant_workspace_id()
    if active_workspace_id is None or int(workspace_id) != int(active_workspace_id):
        raise RiskSnapshotRefreshError("Explicit workspace does not match the active tenant schema.")
    with transaction.atomic():
        current_loan_ids = LoanRiskSnapshot.objects.filter(
            workspace_id=workspace_id,
            status=LoanRiskSnapshot.Status.CURRENT,
            as_of_date__gte=as_of_date,
        ).values("loan_id")
        candidate_ids = tuple(
            PawnLoan.objects.select_for_update(skip_locked=True)
            .filter(workspace_id=workspace_id, state=PawnLoanState.ACTIVE.value)
            .exclude(pk__in=current_loan_ids)
            .order_by("pk").values_list("pk", flat=True)[:batch_size]
        )
        result = {"selected": len(candidate_ids), "current": 0, "errors": []}
        for loan_id in candidate_ids:
            try:
                refresh_loan_risk_snapshot(loan_id, as_of_date=as_of_date)
                result["current"] += 1
            except RiskSnapshotRefreshError as exc:
                result["errors"].append({"loan_id": loan_id, "error": str(exc)})
        return result


def _record_error(loan_id, workspace_id, as_of_date, fingerprint, exc):
    with transaction.atomic():
        loan = PawnLoan.objects.select_for_update().get(pk=loan_id, workspace_id=workspace_id)
        existing = LoanRiskSnapshot.objects.select_for_update().filter(loan=loan).first()
        old_projection = _projection(existing)
        snapshot, _ = LoanRiskSnapshot.objects.update_or_create(loan=loan, defaults={"workspace_id": workspace_id, "as_of_date": as_of_date, "status": LoanRiskSnapshot.Status.ERROR, "input_fingerprint": fingerprint, "error_message": str(exc)})
        _persist_transitions(snapshot, old_projection, _projection(snapshot))


def _projection(snapshot):
    if snapshot is None: return None
    return {
        "status": snapshot.status, "days_past_due": snapshot.days_past_due,
        "performance_class": snapshot.performance_class, "severity": snapshot.severity,
        "policy_identity": snapshot.policy_identity, "flags": tuple(snapshot.flags or ()),
        "assessment_fingerprint": snapshot.assessment_fingerprint,
    }


def _persist_transitions(snapshot, old, new):
    old_fp = old.get("assessment_fingerprint", "") if old else ""
    new_fp = new.get("assessment_fingerprint", "") if new else ""
    transitions_and_events = []
    for transition in detect_risk_transitions(old, new):
        material = json.dumps({"type": transition.event_type, "old_fp": old_fp, "new_fp": new_fp, "old": transition.old_value, "new": transition.new_value, "as_of": snapshot.as_of_date.isoformat()}, sort_keys=True, default=str, separators=(",", ":"))
        trigger = hashlib.sha256(material.encode()).hexdigest()
        event, _ = LoanRiskEvent.objects.get_or_create(
            workspace_id=snapshot.workspace_id, loan_id=snapshot.loan_id, trigger_key=trigger,
            defaults={"snapshot": snapshot, "event_type": transition.event_type, "as_of_date": snapshot.as_of_date, "old_value": {"value": transition.old_value}, "new_value": {"value": transition.new_value}, "old_fingerprint": old_fp, "new_fingerprint": new_fp, "policy_identity": snapshot.policy_identity, "metadata": {"projection_status": snapshot.status}},
        )
        transitions_and_events.append((transition, event))
    from apps.tenant_apps.loans.services.risk_alerts import sync_risk_alerts
    sync_risk_alerts(snapshot, transitions_and_events)


def _source_fingerprint(loan_id, workspace_id, as_of_date):
    loan = PawnLoan.objects.filter(pk=loan_id, workspace_id=workspace_id).values(
        "pk", "state", "loan_date", "tenure_months", "product_version_id", "license_id",
        "updated_at"
    ).get()
    loan["policy_snapshot_id"] = (
        PawnLoan.objects.filter(pk=loan_id)
        .values_list("policy_snapshot__pk", flat=True)
        .get()
    )
    payload = {"as_of": as_of_date.isoformat(), "loan": {k: str(v) for k, v in loan.items()}}
    model = PawnLoan
    for name, relation in (("events", model.loan_events.rel.related_model), ("schedules", model.repayment_schedules.rel.related_model), ("obligations", model.repayment_obligations.rel.related_model), ("allocations", model.obligation_allocations.rel.related_model), ("schedule_changes", model.repayment_schedule_changes.rel.related_model)):
        values = relation.objects.filter(loan_id=loan_id).aggregate(count=Count("pk"), max_pk=Max("pk"))
        payload[name] = values
    item_model = model.collateral_items.rel.related_model
    item_queryset = item_model.objects.filter(loan_id=loan_id)
    payload["items"] = item_queryset.aggregate(count=Count("pk"), max_pk=Max("pk"), last_update=Max("updated_at"))
    from apps.tenant_apps.loans.models import CollateralAppraisal, LoanMonitoringPolicy
    from apps.tenant_apps.rates.models import Rate
    payload["appraisals"] = CollateralAppraisal.objects.filter(
        collateral_item__loan_id=loan_id,
        effective_at__date__lte=as_of_date,
        status=CollateralAppraisal.Status.APPROVED,
    ).aggregate(count=Count("pk"), max_pk=Max("pk"))
    payload["policies"] = LoanMonitoringPolicy.objects.filter(
        workspace_id=workspace_id,
        effective_from__lte=as_of_date,
    ).filter(
        Q(license_id=loan["license_id"]) | Q(license_id__isnull=True)
    ).filter(
        Q(effective_until__isnull=True) | Q(effective_until__gte=as_of_date)
    ).aggregate(count=Count("pk"), max_pk=Max("pk"))
    rate_metals = {
        "GOLD": Rate.Metal.GOLD,
        "SILVER": Rate.Metal.SILVER,
    }
    applicable_metals = {
        rate_metals[metal]
        for metal in item_queryset.values_list("metal", flat=True).distinct()
        if metal in rate_metals
    }
    payload["rates"] = Rate.objects.filter(
        metal__in=applicable_metals,
        currency=Rate.Currency.INR,
        purity=Rate.Purity.K24,
        timestamp__date__lte=as_of_date,
    ).aggregate(count=Count("pk"), max_pk=Max("pk"), latest=Max("timestamp"))
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()
