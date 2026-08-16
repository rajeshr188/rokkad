from django.db import migrations


LOAN_MODELS = (
    "FundingLoanCancellation",
    "FundingLoanDraftCollateral",
    "FundingLoanDraftTerms",
    "FundingLoanEvent",
    "FundingLoanTermsSnapshot",
    "FundingPledgeItem",
    "FundingPledgeReversal",
    "FundingReturnItem",
    "FundingReturnReversal",
    "LoanChangeLog",
    "LoanDocumentLayoutRevision",
    "LoanDocumentPrintProfileRevision",
    "LoanLicenseRevision",
    "LoanNumberSequence",
    "LoanPolicySnapshot",
    "LoanProductVersion",
    "LoanSeries",
    "PawnCollateralCustodyEvent",
    "PawnCollateralItem",
    "PawnCollateralLabelIssue",
    "PawnCollateralPhoto",
    "PawnCollateralStorageMovement",
    "PawnLoanApprovalSnapshot",
    "PawnLoanAuctionItem",
    "PawnLoanAuctionReversal",
    "PawnLoanDisbursalSnapshot",
    "PawnLoanEvent",
    "PawnLoanInterestAccrual",
    "PawnLoanInterestAccrualLine",
    "PawnLoanPrincipalClosingLine",
    "PawnLoanPrincipalOpeningLine",
    "PawnLoanReleaseItem",
    "PawnLoanReleaseReversal",
    "PawnLoanRenewalReversal",
    "PawnLoanRepaymentAllocationLine",
    "PawnPhysicalVerificationExpectation",
    "PawnPhysicalVerificationObservation",
    "PawnPhysicalVerificationResolution",
)


def backfill_workspace(apps, schema_editor):
    tenant = getattr(schema_editor.connection, "tenant", None)
    workspace_id = getattr(tenant, "pk", None)
    if not workspace_id:
        has_unowned_rows = any(
            apps.get_model("loans", model_name).objects.filter(
                workspace_id__isnull=True
            ).exists()
            for model_name in LOAN_MODELS
        )
        if not has_unowned_rows:
            return
        raise RuntimeError(
            "Loans Workspace backfill found unowned rows without an explicit "
            "tenant Workspace."
        )

    for model_name in LOAN_MODELS:
        apps.get_model("loans", model_name).objects.filter(
            workspace_id__isnull=True
        ).update(workspace_id=workspace_id)


class Migration(migrations.Migration):
    dependencies = [("loans", "0064_fundingloancancellation_workspace_and_more")]

    operations = [migrations.RunPython(backfill_workspace, migrations.RunPython.noop)]
