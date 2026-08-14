from dataclasses import dataclass
from decimal import Decimal

from dynamic_preferences.registries import global_preferences_registry

from apps.configuration.services import PreferenceService
from apps.orgs.models import CompanyPreferenceModel
from apps.orgs.registries import company_preference_registry


LEGACY_GIRVI_DEFAULTS = {
    "Loan__Default_Date": "N",
    "Loan__Interest_Deduction": False,
    "Loan__Haircut": Decimal("75.00"),
    "Interest_Rate__gold": Decimal("2.00"),
    "Interest_Rate__silver": Decimal("4.00"),
    "Interest_Rate__other": Decimal("8.00"),
    "Loan__Accrual_Timing": "EOM",
    "Loan__Auto_Post_Accruals": True,
    "Loan__Catchup_On_Receipt": True,
    "Loan__Catchup_On_Release": True,
    "Loan__Release_Fail_Closed_On_Accrual_Error": False,
    "Loan__Catchup_On_Renewal": True,
    "Loan__Allow_Backfill_Posting": False,
    "Loan__Disbursal_Deductions_Enabled": False,
    "Loan__Minimum_Document_Charge": Decimal("0.00"),
}


@dataclass(frozen=True)
class GirviDisbursalPolicy:
    loan_disbursal_deductions_enabled: bool
    loan_interest_deduction: bool
    loan_minimum_document_charge: Decimal


def get_legacy_girvi_preference(workspace, key):
    if workspace is not None and not hasattr(workspace, "_meta"):
        workspace = None
    return PreferenceService.get_workspace_from_registry(
        workspace=workspace,
        key=key,
        workspace_registry=company_preference_registry,
        workspace_preference_model=CompanyPreferenceModel,
        global_registry=global_preferences_registry,
        default=LEGACY_GIRVI_DEFAULTS.get(key),
    )


def get_loan_default_date_preference(workspace):
    return get_legacy_girvi_preference(workspace, "Loan__Default_Date")


def get_interest_rate_for_metal(workspace, metal):
    normalized_metal = str(metal or "").strip().lower()
    if normalized_metal == "gold":
        return get_legacy_girvi_preference(workspace, "Interest_Rate__gold")
    if normalized_metal == "silver":
        return get_legacy_girvi_preference(workspace, "Interest_Rate__silver")
    return get_legacy_girvi_preference(workspace, "Interest_Rate__other")


def is_loan_catchup_on_receipt_enabled(workspace):
    return bool(get_legacy_girvi_preference(workspace, "Loan__Catchup_On_Receipt"))


def is_loan_catchup_on_release_enabled(workspace):
    return bool(get_legacy_girvi_preference(workspace, "Loan__Catchup_On_Release"))


def is_loan_release_fail_closed_on_accrual_error_enabled(workspace):
    return bool(
        get_legacy_girvi_preference(
            workspace,
            "Loan__Release_Fail_Closed_On_Accrual_Error",
        )
    )


def is_loan_catchup_on_renewal_enabled(workspace):
    return bool(get_legacy_girvi_preference(workspace, "Loan__Catchup_On_Renewal"))


def get_loan_accrual_timing(workspace):
    return str(get_legacy_girvi_preference(workspace, "Loan__Accrual_Timing") or "EOM")


def is_loan_auto_post_accruals_enabled(workspace):
    return bool(get_legacy_girvi_preference(workspace, "Loan__Auto_Post_Accruals"))


def is_loan_backfill_posting_allowed(workspace):
    return bool(get_legacy_girvi_preference(workspace, "Loan__Allow_Backfill_Posting"))


def get_disbursal_policy(workspace):
    return GirviDisbursalPolicy(
        loan_disbursal_deductions_enabled=bool(
            get_legacy_girvi_preference(
                workspace,
                "Loan__Disbursal_Deductions_Enabled",
            )
        ),
        loan_interest_deduction=bool(
            get_legacy_girvi_preference(workspace, "Loan__Interest_Deduction")
        ),
        loan_minimum_document_charge=Decimal(
            str(
                get_legacy_girvi_preference(
                    workspace,
                    "Loan__Minimum_Document_Charge",
                )
                or Decimal("0.00")
            )
        ),
    )
