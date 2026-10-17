"""Concrete next steps explain existing holds without granting a correction."""

from django.db.models import Q
from django.urls import reverse

from apps.tenant_apps.loans import models as m


def correction_next_steps(loan, blockers):
    if not blockers:
        return []
    detail = reverse(
        "workspace_loans:pawn_loan_detail",
        kwargs={"workspace_slug": loan.workspace.slug, "pk": loan.pk},
    )
    rows = []
    relations = m.PawnLoanRenewal.objects.filter(
        Q(source_loan=loan) | Q(successor_loan=loan)
    ).select_related("source_loan", "successor_loan")
    for relation in relations:
        other = (
            relation.successor_loan
            if relation.source_loan_id == loan.pk
            else relation.source_loan
        )
        rows.append(
            dict(
                label=f"Review linked agreement {other.loan_number}",
                message="Check the original and successor agreements together, including retained settlement and collateral facts. An independent correction cannot reconcile both loans.",
                url=reverse(
                    "workspace_loans:pawn_loan_detail",
                    kwargs={"workspace_slug": loan.workspace.slug, "pk": other.pk},
                ),
            )
        )
    if (
        m.FundingPledgeItem.objects.filter(collateral_item__loan=loan).exists()
        or m.FundingLoanDraftCollateral.objects.filter(
            collateral_item__loan=loan
        ).exists()
    ):
        rows.append(
            dict(
                label="Review the connected funding records",
                message="Identify the pledged or reserved items and reconcile the linked agreement before attempting an independent correction.",
                url=detail + "#business-events",
            )
        )
    if loan.auctions.exists():
        rows.append(
            dict(
                label="Review the auction and settlement history",
                message="Preserve notices, disposal and recovery facts. The connected history needs an administrator's supported reconciliation.",
                url=detail + "#business-events",
            )
        )
    if loan.collateral_items.exclude(custody_state="IN_VAULT").exists():
        rows.append(
            dict(
                label="Review collateral custody",
                message="Check the actual item location and return evidence. A fact correction does not record a new movement or customer handover.",
                url=detail + "#collateral-gallery",
            )
        )
    if not rows:
        if loan.state == "DRAFT":
            rows.append(
                dict(
                    label="Correct the preparation draft",
                    message="No posted fact correction is needed for an unposted draft. Review borrower, date, principal and collateral in its editor. A wrong register/product uses the reviewed replacement action on draft detail.",
                    url=reverse(
                        "workspace_loans:pawn_loan_update",
                        kwargs={"workspace_slug": loan.workspace.slug, "pk": loan.pk},
                    ),
                )
            )
        elif loan.state == "APPROVED":
            rows.append(
                dict(
                    label="Review the approved loan",
                    message="Return an unpaid approved loan to draft through its supported action before correcting preparation facts. Retain its genuine approval and issued history.",
                    url=detail,
                )
            )
        else:
            rows.append(
                dict(
                    label="Review the saved agreement and source evidence",
                    message="Check the frozen calculation rule and available history. Use the supported agreement/checkpoint review; an unsupported history needs a concrete reconciliation. Changing entry mode or today's setup cannot remove this hold.",
                    url=detail + "#loan-documents-title",
                )
            )
    return rows


def draft_replacement_link(loan):
    row = (
        loan.change_log.filter(
            Q(metadata__has_key="draft_replacement_out")
            | Q(metadata__has_key="draft_replacement_in")
        )
        .order_by("-pk")
        .first()
    )
    if row is None:
        return None
    outgoing = "draft_replacement_out" in row.metadata
    facts = row.metadata.get(
        "draft_replacement_out", row.metadata.get("draft_replacement_in", {})
    ).get("source", {})
    if (
        facts.get("workspace_id") != loan.workspace_id
        or facts.get("old_loan_id" if outgoing else "new_loan_id") != loan.pk
    ):
        return None
    other = m.PawnLoan.objects.filter(
        workspace_id=loan.workspace_id,
        pk=facts["new_loan_id" if outgoing else "old_loan_id"],
    ).first()
    return dict(other=other, outgoing=outgoing) if other else None
