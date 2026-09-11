"""Append reviewed current-date appraisal evidence without changing loan terms."""

from decimal import Decimal, ROUND_DOWN

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.orgs.models import Company
from apps.tenant_apps.loans.models import CollateralAppraisal, LoanRiskSnapshot, PawnLoan, current_tenant_workspace_id
from apps.tenant_apps.rates.facade import RATE_FOUND, get_latest_commodity_valuation_rate
from .action_access import require_loan_action


APPRAISAL_METHODS = (("PHYSICAL_INSPECTION", "Physical inspection"), ("EXTERNAL_REPORT", "External appraisal report"))


@transaction.atomic
def record_collateral_reappraisal(*, loan_id, item_id, actor, appraised_value,
                                  method, evidence_reference, review_notes, expected_version):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PermissionDenied("Reassessment requires an active Workspace.")
    loan = PawnLoan.objects.select_for_update().get(pk=loan_id, workspace_id=workspace_id)
    require_loan_action(loan, actor, "data.edit", "loan.approve")
    if not Company.objects.filter(pk=workspace_id).exists():
        raise PermissionDenied("Reassessment requires an active Workspace.")
    if loan.state != "ACTIVE":
        raise ValidationError("Only active loans can be reassessed.")
    item = loan.collateral_items.select_for_update().get(pk=item_id, workspace_id=workspace_id)
    if item.custody_state not in {"IN_VAULT", "WITH_FUNDING_LENDER"}:
        raise ValidationError("Only collateral held in the vault or with a funding lender can be reassessed.")
    previous = item.appraisals.order_by("-version").first()
    if expected_version != (previous.version if previous else 0):
        raise ValidationError("The appraisal changed while you were reviewing it. Reload and review the latest evidence.")
    now = timezone.now()
    if loan.loan_date > timezone.localdate(now) or (previous and previous.effective_at > now):
        raise ValidationError("Existing evidence is future dated; review it before recording a current reassessment.")
    if method not in dict(APPRAISAL_METHODS) or not evidence_reference.strip() or not review_notes.strip():
        raise ValidationError("Select a method and provide an evidence reference and review reason.")
    context = reappraisal_reference(item, as_of=now)
    appraisal = CollateralAppraisal.objects.create(
        workspace_id=workspace_id, collateral_item=item, version=(previous.version if previous else 0) + 1,
        effective_at=now, appraised_value=appraised_value, method=method,
        status=CollateralAppraisal.Status.APPROVED, evidence_reference=evidence_reference.strip(),
        review_notes=review_notes.strip(), supersedes=previous, created_by=actor,
        valuation_context=context,
    )
    LoanRiskSnapshot.objects.filter(workspace_id=workspace_id, loan_id=loan.pk).exclude(status=LoanRiskSnapshot.Status.ERROR).update(
        status="STALE", error_message="Collateral appraisal changed; reassessment required.")
    return appraisal


def reappraisal_reference(item, *, as_of):
    """Reference observed at this instant; it is not the appraiser's authority."""
    if current_tenant_workspace_id() != item.workspace_id:
        raise PermissionDenied("Appraisal reference requires the matching Workspace.")
    quote = get_latest_commodity_valuation_rate(commodity_code=item.metal, as_of=as_of)
    rate = quote.rate if quote.status == RATE_FOUND else None
    context = {
        "contract": "COLLATERAL_REAPPRAISAL_V1", "net_weight_grams": str(item.net_weight),
        "purity_percentage": str(item.purity_percentage), "metal": item.metal,
        "rate_id": rate.pk if rate else None,
        "rate_effective_at": rate.effective_at.isoformat() if rate else None,
        "buying_price_inr_per_pure_gram": str(rate.buying_rate) if rate else None,
        "suggested_metal_value": None,
    }
    if rate and rate.buying_rate.is_finite() and rate.buying_rate > 0:
        context["suggested_metal_value"] = str((rate.buying_rate * item.net_weight * item.purity_percentage / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_DOWN))
    return context
