import hashlib
import json
from datetime import date
from dataclasses import replace

from django.db import transaction
from django.db.models import Count, F, Max, Q
from django.utils import timezone

from apps.tenant_apps.loans.domain import detect_risk_transitions
from apps.tenant_apps.loans.domain import PawnLoanState
from apps.tenant_apps.loans.models import LoanRiskEvent, LoanRiskSnapshot, PawnLoan, current_tenant_workspace_id
from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
from apps.tenant_apps.loans.selectors.delinquency import get_pawn_loan_delinquency
from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure, require_consistent_exposure, _read_financial_inputs
from apps.tenant_apps.loans.selectors.risk import get_pawn_loan_risk_assessment
from apps.tenant_apps.loans.selectors.risk_portfolio import SNAPSHOT_CONTRACT, current_snapshot_filter
from apps.orgs.models import Company


class RiskSnapshotRefreshError(ValueError):
    pass


def require_current_assessment_date(as_of_date: date):
    """The single live projection and its alerts represent today's position."""
    today = timezone.localdate()
    if as_of_date != today:
        raise RiskSnapshotRefreshError(
            f"Live risk assessments can only be refreshed for today ({today.isoformat()}). "
            "Use read-only calculations to inspect another date."
        )


def refresh_loan_risk_snapshot(loan_id: int, *, as_of_date: date):
    require_current_assessment_date(as_of_date)
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise RiskSnapshotRefreshError("Risk refresh requires an explicit Workspace context.")
    _require_active_workspace(workspace_id)
    if not PawnLoan.objects.filter(
        pk=loan_id,
        workspace_id=workspace_id,
        state=PawnLoanState.ACTIVE.value,
    ).exists():
        raise RiskSnapshotRefreshError(
            "Only an active PawnLoan in the current workspace can be assessed."
        )
    before = _source_fingerprint(loan_id, workspace_id, as_of_date)
    exposure = None
    try:
        inputs = _read_financial_inputs(loan_id, as_of_date=as_of_date)
        exposure = get_pawn_loan_exposure(loan_id, as_of_date=as_of_date, _inputs=inputs)
        require_consistent_exposure(exposure)
        delinquency = get_pawn_loan_delinquency(loan_id, as_of_date=as_of_date, _inputs=inputs)
        collateral = get_pawn_loan_collateral_valuation(loan_id, as_of_date=as_of_date, _exposure=exposure)
        from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
        inputs = replace(inputs, transaction_coverage=transaction_completeness(inputs.loan, as_of_date))
        assessment = get_pawn_loan_risk_assessment(loan_id, as_of_date=as_of_date,
            _delinquency=delinquency, _collateral=collateral, _exposure=exposure, _inputs=inputs)
    except Exception as exc:
        _record_error(loan_id, workspace_id, as_of_date, before, exc, exposure=exposure)
        raise RiskSnapshotRefreshError(str(exc)) from exc
    with transaction.atomic():
        loan = PawnLoan.objects.select_for_update().get(pk=loan_id, workspace_id=workspace_id)
        require_current_assessment_date(as_of_date)
        if loan.state != PawnLoanState.ACTIVE.value:
            raise RiskSnapshotRefreshError("Loan is no longer active; assessment discarded.")
        snapshot = LoanRiskSnapshot.objects.select_for_update().filter(loan=loan).first()
        old_projection = _projection(snapshot)
        after = _source_fingerprint(loan_id, workspace_id, as_of_date)
        if before != after:
            if snapshot:
                snapshot.status = LoanRiskSnapshot.Status.STALE if snapshot.assessment_fingerprint else LoanRiskSnapshot.Status.ERROR
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
        values["source_provenance"]["transactions"] = inputs.transaction_coverage.evidence()
        if snapshot is None:
            snapshot = LoanRiskSnapshot.objects.create(loan=loan, **values)
        else:
            for key, value in values.items(): setattr(snapshot, key, value)
            snapshot.save()
        _persist_transitions(snapshot, old_projection, _projection(snapshot))
        return snapshot


def _snapshot_values(*, workspace_id, as_of_date, exposure, delinquency,
                     collateral, assessment, input_fingerprint, assessed_at):
    require_consistent_exposure(exposure)
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
                "calculation_contract": SNAPSHOT_CONTRACT,
                "financial": _financial_evidence(exposure),
                "valuation": {
                    "method": collateral.valuation_method,
                    "method_label": collateral.valuation_method_label,
                    "basis": collateral.valuation_basis,
                    "original_method": collateral.original_valuation_method,
                    "monitoring_policy_id": collateral.monitoring_policy_id,
                    "rate_freshness_days": collateral.rate_freshness_days,
                    "appraisal_freshness_days": collateral.appraisal_freshness_days,
                },
                "coverage": {
                    "exposure": str(collateral.ltv.exposure),
                    "basis": exposure.ltv_basis_label,
                    "headroom": str(collateral.ltv.headroom) if collateral.ltv.headroom is not None else None,
                    "shortfall": str(collateral.ltv.full_shortfall) if collateral.ltv.full_shortfall is not None else None,
                    "status": collateral.ltv.status,
                    "blockers": list(collateral.ltv.blockers),
                },
                "evidence": [
                    {"item_id": row.collateral_item_id,
                     "rate_at": row.rate_effective_at.isoformat() if row.rate_effective_at else None,
                     "appraisal_at": row.appraisal_effective_at.isoformat() if row.appraisal_effective_at else None,
                     "rate_status": row.rate_status, "appraisal_status": row.appraisal_status,
                     "messages": list(row.blocker_messages)}
                    for row in collateral.items
                ],
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


def _financial_evidence(exposure):
    return {
        "projected_interest": format(exposure.projected_interest, "f"),
        "recorded_total_due": format(exposure.recorded_total_due, "f"),
        "integrity_findings": list(exposure.integrity_findings),
        "calculation_status": "INCONSISTENT" if exposure.integrity_findings else "SUPPORTED",
        "principal_history_basis": exposure.principal_history_basis,
        "history_from": exposure.financial_history_from.isoformat() if exposure.financial_history_from else None,
        "servicing_profile": exposure.servicing_profile,
    }


def rebuild_current_risk_snapshots(*, as_of_date: date, loan_ids=None):
    require_current_assessment_date(as_of_date)
    workspace_id = current_tenant_workspace_id()
    queryset = PawnLoan.objects.filter(workspace_id=workspace_id, state=PawnLoanState.ACTIVE.value).order_by("pk")
    if loan_ids is not None: queryset = queryset.filter(pk__in=loan_ids)
    results = {"current": 0, "errors": []}
    for loan_id in queryset.values_list("pk", flat=True).iterator():
        try:
            refresh_loan_risk_snapshot(loan_id, as_of_date=as_of_date); results["current"] += 1
        except RiskSnapshotRefreshError as exc:
            results["errors"].append({"loan_id": loan_id, "error": str(exc)})
    return results


def reassess_pawn_loans_batch(*, workspace_id: int, as_of_date: date, batch_size=100, loan_ids=None):
    batch_size = int(batch_size)
    if not 1 <= batch_size <= 1000:
        raise RiskSnapshotRefreshError("Batch size must be between 1 and 1000.")
    active_workspace_id = current_tenant_workspace_id()
    if active_workspace_id is None or int(workspace_id) != int(active_workspace_id):
        raise RiskSnapshotRefreshError("Explicit workspace does not match the active tenant schema.")
    require_current_assessment_date(as_of_date)
    _require_active_workspace(workspace_id)
    with transaction.atomic():
        candidates = _pending_loans(
            PawnLoan.objects.select_for_update(skip_locked=True, of=("self",)),
            workspace_id, as_of_date,
        )
        if loan_ids is not None:
            candidates = candidates.filter(pk__in=loan_ids)
        candidate_ids = tuple(candidates.values_list("pk", flat=True)[:batch_size])
        result = {"selected": len(candidate_ids), "current": 0, "errors": []}
        for loan_id in candidate_ids:
            try:
                refresh_loan_risk_snapshot(loan_id, as_of_date=as_of_date)
                result["current"] += 1
            except RiskSnapshotRefreshError as exc:
                result["errors"].append({"loan_id": loan_id, "error": str(exc)})
        return result


def _pending_loans(queryset, workspace_id, as_of_date):
    current_ids = LoanRiskSnapshot.objects.filter(
        current_snapshot_filter(as_of_date), workspace_id=workspace_id,
    ).values("loan_id")
    return (queryset.filter(workspace_id=workspace_id, state=PawnLoanState.ACTIVE.value)
        .exclude(pk__in=current_ids)
        .order_by(F("risk_snapshot__updated_at").asc(nulls_first=True), "pk"))


def _require_active_workspace(workspace_id):
    if not Company.objects.filter(pk=workspace_id, lifecycle_state=Company.LifecycleState.ACTIVE).exists():
        raise RiskSnapshotRefreshError("Risk refresh requires an ACTIVE Workspace.")
    from apps.subscriptions.access_policy import require_business_write
    require_business_write(Company.objects.get(pk=workspace_id))


def _record_error(loan_id, workspace_id, as_of_date, fingerprint, exc, *, exposure=None):
    with transaction.atomic():
        loan = PawnLoan.objects.select_for_update().get(pk=loan_id, workspace_id=workspace_id)
        require_current_assessment_date(as_of_date)
        if loan.state != PawnLoanState.ACTIVE.value:
            return  # A concurrent closure ends monitoring, including error attempts.
        existing = LoanRiskSnapshot.objects.select_for_update().filter(loan=loan).first()
        old_projection = _projection(existing)
        snapshot, _ = LoanRiskSnapshot.objects.update_or_create(loan=loan, defaults={
            "workspace_id": workspace_id, "as_of_date": as_of_date,
            "status": LoanRiskSnapshot.Status.ERROR, "input_fingerprint": fingerprint,
            "error_message": str(exc), "assessment_fingerprint": "",
            "exposure": None, "due": None, "overdue": None, "days_past_due": None,
            "days_to_maturity": None, "collateral_value": None, "ltv_ratio": None,
            "performance_class": "UNKNOWN", "severity": "HIGH", "action_hint": "PRIORITY_REVIEW",
            "flags": [], "explanations": [str(exc)], "assessed_at": timezone.now(),
            "source_provenance": {
                "calculation_contract": SNAPSHOT_CONTRACT,
                "financial": _financial_evidence(exposure) if exposure is not None else {"calculation_status": "FAILED"},
                "coverage": {"status": "UNKNOWN", "blockers": ["ASSESSMENT_FAILED"]},
            },
        })
        _persist_transitions(snapshot, old_projection, _projection(snapshot))


def _projection(snapshot):
    if snapshot is None: return None
    return {
        "status": snapshot.status, "days_past_due": snapshot.days_past_due,
        "performance_class": snapshot.performance_class, "severity": snapshot.severity,
        "policy_identity": snapshot.policy_identity, "flags": tuple(snapshot.flags or ()),
        "assessment_fingerprint": snapshot.assessment_fingerprint,
        "ltv_ratio": snapshot.ltv_ratio,
    }


def _persist_transitions(snapshot, old, new):
    old_fp = old.get("assessment_fingerprint", "") if old else ""
    new_fp = new.get("assessment_fingerprint", "") if new else ""
    previous_event_id = LoanRiskEvent.objects.filter(
        workspace_id=snapshot.workspace_id, loan_id=snapshot.loan_id,
    ).order_by("-pk").values_list("pk", flat=True).first()
    transitions_and_events = []
    for transition in detect_risk_transitions(old, new):
        material = json.dumps({"type": transition.event_type, "old_fp": old_fp, "new_fp": new_fp, "old": transition.old_value, "new": transition.new_value, "as_of": snapshot.as_of_date.isoformat(), "previous_event_id": previous_event_id}, sort_keys=True, default=str, separators=(",", ":"))
        trigger = hashlib.sha256(material.encode()).hexdigest()
        event, _ = LoanRiskEvent.objects.get_or_create(
            workspace_id=snapshot.workspace_id, loan_id=snapshot.loan_id, trigger_key=trigger,
            defaults={"snapshot": snapshot, "event_type": transition.event_type, "as_of_date": snapshot.as_of_date, "old_value": {"value": transition.old_value}, "new_value": {"value": transition.new_value}, "old_fingerprint": old_fp, "new_fingerprint": new_fp, "policy_identity": snapshot.policy_identity, "metadata": {"projection_status": snapshot.status, "previous_event_id": previous_event_id}},
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
    corrections = PawnLoan.objects.get(pk=loan_id, workspace_id=workspace_id).change_log.filter(
        event_kind="COLLATERAL_CORRECTED").aggregate(count=Count("pk"), max_pk=Max("pk"))
    if corrections["count"]:
        payload["collateral_corrections"] = corrections
    from apps.tenant_apps.loans.models import LoanTransactionReview
    payload["transaction_reviews"] = LoanTransactionReview.objects.filter(loan_id=loan_id).aggregate(count=Count("pk"), max_pk=Max("pk"))
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
        "BRONZE": Rate.Metal.BRONZE,
    }
    applicable_metals = {
        rate_metals[metal]
        for metal in item_queryset.values_list("metal", flat=True).distinct()
        if metal in rate_metals
    }
    payload["rates"] = Rate.objects.filter(workspace_id=workspace_id).filter(
        Q(metal__in=applicable_metals, currency=Rate.Currency.INR,
          purity=Rate.Purity.K24, effective_at__date__lte=as_of_date)
        | Q(supersedes__metal__in=applicable_metals, supersedes__currency=Rate.Currency.INR,
            supersedes__purity=Rate.Purity.K24, supersedes__effective_at__date__lte=as_of_date)
    ).aggregate(count=Count("pk"), max_pk=Max("pk"), latest=Max("timestamp"))
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()
