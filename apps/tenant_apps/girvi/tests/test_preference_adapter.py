from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Max
from django.test import TestCase

from apps.orgs.models import Company
from apps.orgs.registries import company_preference_registry
from apps.tenant_apps.girvi.service_modules.preferences import (
    get_disbursal_policy,
    get_interest_rate_for_metal,
    get_loan_accrual_timing,
    get_loan_default_date_preference,
    is_loan_auto_post_accruals_enabled,
    is_loan_backfill_posting_allowed,
    is_loan_catchup_on_receipt_enabled,
    is_loan_catchup_on_release_enabled,
    is_loan_catchup_on_renewal_enabled,
    is_loan_release_fail_closed_on_accrual_error_enabled,
)


class GirviPreferenceAdapterTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="girvi-pref-owner",
            email="girvi-pref-owner@example.com",
            password="pass",
        )
        next_company_id = (
            Company.all_objects.aggregate(max_id=Max("id"))["max_id"] or 0
        ) + 1
        self.workspace = Company(
            id=next_company_id,
            name="Girvi Preference Workspace",
            schema_name=f"girvi_pref_workspace_{next_company_id}",
            owner=self.user,
            creator=self.user,
        )
        self.workspace.auto_create_schema = False
        self.workspace.save()
        self.other_workspace = Company(
            id=next_company_id + 1,
            name="Other Girvi Preference Workspace",
            schema_name=f"girvi_pref_other_{next_company_id + 1}",
            owner=self.user,
            creator=self.user,
        )
        self.other_workspace.auto_create_schema = False
        self.other_workspace.save()

    def test_loan_default_date_reads_legacy_workspace_override_through_service(self):
        company_preference_registry.manager(instance=self.workspace)[
            "Loan__Default_Date"
        ] = "L"

        self.assertEqual(get_loan_default_date_preference(self.workspace), "L")
        self.assertEqual(get_loan_default_date_preference(self.other_workspace), "N")

    def test_interest_rate_reads_legacy_workspace_override_through_service(self):
        manager = company_preference_registry.manager(instance=self.workspace)
        manager["Interest_Rate__gold"] = Decimal("3.50")
        manager["Interest_Rate__silver"] = Decimal("4.75")
        manager["Interest_Rate__other"] = Decimal("9.25")

        self.assertEqual(
            get_interest_rate_for_metal(self.workspace, "Gold"),
            Decimal("3.50"),
        )
        self.assertEqual(
            get_interest_rate_for_metal(self.workspace, "Silver"),
            Decimal("4.75"),
        )
        self.assertEqual(
            get_interest_rate_for_metal(self.workspace, "Diamond"),
            Decimal("9.25"),
        )
        self.assertEqual(
            get_interest_rate_for_metal(self.other_workspace, "Gold"),
            Decimal("2.00"),
        )

    def test_workflow_policy_reads_legacy_workspace_overrides_through_service(self):
        manager = company_preference_registry.manager(instance=self.workspace)
        manager["Loan__Accrual_Timing"] = "BOM"
        manager["Loan__Auto_Post_Accruals"] = False
        manager["Loan__Catchup_On_Receipt"] = False
        manager["Loan__Catchup_On_Release"] = False
        manager["Loan__Release_Fail_Closed_On_Accrual_Error"] = True
        manager["Loan__Catchup_On_Renewal"] = False
        manager["Loan__Allow_Backfill_Posting"] = True

        self.assertEqual(get_loan_accrual_timing(self.workspace), "BOM")
        self.assertFalse(is_loan_auto_post_accruals_enabled(self.workspace))
        self.assertFalse(is_loan_catchup_on_receipt_enabled(self.workspace))
        self.assertFalse(is_loan_catchup_on_release_enabled(self.workspace))
        self.assertTrue(
            is_loan_release_fail_closed_on_accrual_error_enabled(self.workspace)
        )
        self.assertFalse(is_loan_catchup_on_renewal_enabled(self.workspace))
        self.assertTrue(is_loan_backfill_posting_allowed(self.workspace))

        self.assertEqual(get_loan_accrual_timing(self.other_workspace), "EOM")
        self.assertTrue(is_loan_auto_post_accruals_enabled(self.other_workspace))
        self.assertTrue(is_loan_catchup_on_receipt_enabled(self.other_workspace))
        self.assertTrue(is_loan_catchup_on_release_enabled(self.other_workspace))
        self.assertFalse(
            is_loan_release_fail_closed_on_accrual_error_enabled(self.other_workspace)
        )
        self.assertTrue(is_loan_catchup_on_renewal_enabled(self.other_workspace))
        self.assertFalse(is_loan_backfill_posting_allowed(self.other_workspace))

    def test_disbursal_policy_reads_legacy_workspace_overrides_through_service(self):
        manager = company_preference_registry.manager(instance=self.workspace)
        manager["Loan__Disbursal_Deductions_Enabled"] = True
        manager["Loan__Interest_Deduction"] = True
        manager["Loan__Minimum_Document_Charge"] = Decimal("15.00")

        policy = get_disbursal_policy(self.workspace)
        fallback_policy = get_disbursal_policy(self.other_workspace)

        self.assertTrue(policy.loan_disbursal_deductions_enabled)
        self.assertTrue(policy.loan_interest_deduction)
        self.assertEqual(policy.loan_minimum_document_charge, Decimal("15.00"))
        self.assertFalse(fallback_policy.loan_disbursal_deductions_enabled)
        self.assertFalse(fallback_policy.loan_interest_deduction)
        self.assertEqual(
            fallback_policy.loan_minimum_document_charge,
            Decimal("0.00"),
        )
