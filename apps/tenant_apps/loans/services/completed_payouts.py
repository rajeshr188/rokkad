"""Reuse an unpaid draft's identity for reviewed completed-payout admission."""
from decimal import Decimal

from .action_access import require_loan_action
from apps.tenant_apps.loans import models as m


def draft_source(workspace, actor, draft_id):
    loan = m.PawnLoan.objects.select_for_update(of=("self",)).select_related(
        "license", "series", "borrower", "product_version").get(pk=draft_id, workspace=workspace)
    require_loan_action(loan, actor, "data.edit", "loan.disburse")
    return loan


def require_unpaid_draft(loan):
    if loan.state not in ("DRAFT", "APPROVED") or loan.loan_events.exists() or loan.disbursal_snapshots.exists():
        raise ValueError("Completed payout admission requires an unpaid draft with no financial origin. Use the existing loan's correction workflow for posted history.")
    if loan.collateral_items.exclude(custody_state="IN_VAULT").exists():
        raise ValueError("Review the draft's collateral custody before completed payout admission.")
    if loan.collateral_items.filter(renewed_from__isnull=False).exists():
        raise ValueError("A linked renewal draft requires its renewal workflow.")


def source_evidence(loan):
    """Bind review to saved draft facts, genuine approvals and issued copies."""
    from .recorded_history import _digest
    fields = ("id", "borrower_id", "license_id", "license_revision_id", "series_id", "product_version_id",
        "loan_number", "loan_date", "principal_amount", "monthly_interest_rate", "tenure_months", "state",
        "creation_submission_id", "policy_snapshot_id", "updated_at")
    items = list(loan.collateral_items.select_for_update().order_by("pk"))
    material = dict(loan={name: str(getattr(loan, name)) for name in fields},
        items=[{field.name: str(getattr(item, field.attname)) for field in item._meta.concrete_fields} for item in items],
        approvals=list(loan.approval_snapshots.order_by("pk").values("id", "fingerprint")),
        photos=list(m.PawnCollateralPhoto.objects.filter(collateral_item__loan=loan).order_by("pk").values_list("pk", "sha256")),
        documents=list(m.LoanDocumentIssue.objects.filter(workspace_id=loan.workspace_id,
            source_type="PawnLoan", source_id=str(loan.pk)).order_by("pk").values_list("pk", "source_fingerprint")))
    return dict(loan_id=loan.pk, original_state=loan.state, source_sha256=_digest(material),
        item_ids=[item.pk for item in items], retained_approvals=material["approvals"])


def apply_actual_contract(loan, data, *, actor):
    """No quotes, policy lookup, number reissue, item replacement or fake approval."""
    from .recorded_items import contract_items
    require_unpaid_draft(loan)
    if (data["borrower_id"], data["series_id"], data["product_version_id"], data["number"], data["date"]) != (
            loan.borrower_id, loan.series_id, loan.product_version_id, loan.loan_number, loan.loan_date.isoformat()):
        raise ValueError("Keep this draft's customer, series, product, number and original date. Correct its identity explicitly before recording a payout.")
    facts = contract_items(data)
    items = list(loan.collateral_items.select_for_update().order_by("pk"))
    if not items or len(items) != len(facts):
        raise ValueError("Keep this draft's collateral items; correct item membership explicitly before admission.")
    frozen = loan.approval_snapshots.exists()
    actual = dict(principal_amount=Decimal(data["principal"]), monthly_interest_rate=Decimal(data["rate"]), tenure_months=data["tenure"])
    if frozen and any(getattr(loan, name) != value for name, value in actual.items()):
        raise ValueError("Actual terms differ from retained approval evidence. Reconcile the draft explicitly before admission.")
    for item, row in zip(items, facts, strict=True):
        values = dict(description=row["description"], metal=row["metal"], quantity=row["quantity"],
            gross_weight=Decimal(row["gross_weight"]), net_weight=Decimal(row["net_weight"]),
            purity_percentage=Decimal(row["purity"]), allocated_principal=Decimal(row["principal"]),
            monthly_interest_rate=Decimal(row["rate"]))
        if frozen and any(getattr(item, name) != value for name, value in values.items()):
            raise ValueError("Actual collateral terms differ from retained approval evidence. Reconcile that evidence before admission.")
        for name, value in values.items():
            setattr(item, name, value)
        item.full_clean()
        item.save(update_fields=[*values, "updated_at"])
    for name, value in actual.items():
        setattr(loan, name, value)
    loan.updated_by = actor
    loan.full_clean()
    loan.save(update_fields=[*actual, "updated_by", "updated_at"])
    return items
