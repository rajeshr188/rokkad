import uuid
from datetime import date

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import override_settings
from django.urls import reverse
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from apps.orgs.models import Membership, Role
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models import (
    Account,
    AccountType,
    AccountType_Ext,
    AccountTransaction,
    AccountingPeriod,
    BusinessEventDraft,
    Commodity,
    CommodityAccount,
    CommodityMovement,
    EntityType,
    ExposureLine,
    JournalEntry,
    Ledger,
    LedgerTransaction,
    PaymentVoucher,
    RateFixing,
    TransactionType_DE,
    Voucher,
    VoucherLine,
)
from apps.tenant_apps.party.models import Party


User = get_user_model()


@override_settings(ROOT_URLCONF="django_project.tenant_urls")
class BusinessEventScaffoldViewTests(TenantTestCase):
    test_schema_name = f"dea_business_events_{uuid.uuid4().hex[:8]}"
    test_domain = f"dea-business-events-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = User.objects.get_or_create(
            username="dea-business-event-owner",
            defaults={"email": "dea-business-event-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-business-event-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner
        tenant.save()
        owner_role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.get_or_create(
            user=owner,
            company=tenant,
            defaults={"role": owner_role},
        )

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.client = TenantClient(self.tenant)
        self.user = User.objects.get(username="dea-business-event-owner")
        self.client.login(username="dea-business-event-owner", password="testpass123")

    def _login_as_member(self):
        member = User.objects.create_user(
            username=f"dea-business-event-member-{uuid.uuid4().hex[:8]}",
            email=f"dea-business-event-member-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=member_role)
        self.client.logout()
        self.client.login(username=member.username, password="testpass123")
        return member

    def test_business_events_dashboard_lists_non_posting_workflow_scaffolds(self):
        before = self._side_effect_counts()

        response = self.client.get(reverse("dea_business_events_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Business Events")
        self.assertContains(response, "Fixed Purchase")
        self.assertContains(response, "Unfixed Purchase")
        self.assertContains(response, "Purchase Rate Fixing")
        self.assertContains(response, "Fixed Sale")
        self.assertContains(response, "Unfixed Sale")
        self.assertContains(response, "Sale Rate Fixing")
        self.assertContains(response, "Receipt From Customer")
        self.assertContains(response, "Payment To Supplier")
        self.assertContains(response, "Issue Metal To Karigar")
        self.assertContains(response, "Receive Metal From Karigar")
        self.assertContains(response, reverse("dea_karigar_movement_preview"))
        self.assertContains(response, reverse("dea_fixed_purchase_preview"))
        self.assertContains(response, reverse("dea_unfixed_purchase_preview"))
        self.assertContains(response, reverse("dea_purchase_rate_fixing_preview"))
        self.assertContains(response, reverse("dea_sale_rate_fixing_preview"))
        self.assertContains(response, reverse("dea_monetary_settlement_preview"))
        self.assertContains(response, reverse("dea_fixed_sale_preview"))
        self.assertContains(response, reverse("dea_unfixed_sale_preview"))
        self.assertContains(response, "Open preview")
        self.assertContains(response, reverse("dea_metal_balance_report"))
        self.assertContains(response, reverse("dea_exposure_report"))
        self.assertEqual(self._side_effect_counts(), before)

    def test_business_events_dashboard_rejects_post(self):
        response = self.client.post(reverse("dea_business_events_dashboard"))

        self.assertEqual(response.status_code, 405)

    def test_business_events_dashboard_lists_recent_fixed_purchase_drafts_and_results(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_fixed_purchase_preview"),
            data=self._fixed_purchase_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get()
        before_dashboard = self._side_effect_counts()

        draft_response = self.client.get(reverse("dea_business_events_dashboard"))

        self.assertEqual(draft_response.status_code, 200)
        self.assertContains(draft_response, "Recent Fixed Purchases")
        self.assertContains(draft_response, "SUP-BILL-001")
        self.assertContains(draft_response, "Previewed")
        self.assertContains(draft_response, "Not posted")
        self.assertContains(
            draft_response,
            reverse("dea_fixed_purchase_detail", kwargs={"draft_id": draft.pk}),
        )
        self.assertEqual(self._side_effect_counts(), before_dashboard)

        self.client.post(
            reverse("dea_fixed_purchase_confirm", kwargs={"draft_id": draft.pk})
        )
        posted_response = self.client.get(reverse("dea_business_events_dashboard"))

        self.assertEqual(posted_response.status_code, 200)
        self.assertContains(posted_response, "SUP-BILL-001")
        self.assertContains(posted_response, "Posted")

    def test_business_events_dashboard_lists_recent_unfixed_purchase_drafts(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_unfixed_purchase_preview"),
            data=self._unfixed_purchase_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.UNFIXED_PURCHASE,
        )
        before_dashboard = self._side_effect_counts()

        response = self.client.get(reverse("dea_business_events_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recent Unfixed Purchases")
        self.assertContains(response, "UNFIXED-SUP-BILL-001")
        self.assertContains(response, "Preview Supplier Party")
        self.assertContains(response, "Previewed")
        self.assertContains(response, "Not posted")
        self.assertContains(
            response,
            reverse("dea_unfixed_purchase_detail", kwargs={"draft_id": draft.pk}),
        )
        self.assertEqual(self._side_effect_counts(), before_dashboard)

    def test_business_events_dashboard_lists_recent_fixed_sale_drafts_and_results(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_fixed_sale_preview"),
            data=self._fixed_sale_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.FIXED_SALE,
        )
        before_dashboard = self._side_effect_counts()

        draft_response = self.client.get(reverse("dea_business_events_dashboard"))

        self.assertEqual(draft_response.status_code, 200)
        self.assertContains(draft_response, "Recent Fixed Sales")
        self.assertContains(draft_response, "SALE-BILL-001")
        self.assertContains(draft_response, "Previewed")
        self.assertContains(draft_response, "Not posted")
        self.assertContains(
            draft_response,
            reverse("dea_fixed_sale_detail", kwargs={"draft_id": draft.pk}),
        )
        self.assertEqual(self._side_effect_counts(), before_dashboard)

        self.client.post(
            reverse("dea_fixed_sale_confirm", kwargs={"draft_id": draft.pk})
        )
        posted_response = self.client.get(reverse("dea_business_events_dashboard"))

        self.assertEqual(posted_response.status_code, 200)
        self.assertContains(posted_response, "SALE-BILL-001")
        self.assertContains(posted_response, "Posted")

    def test_business_events_dashboard_lists_recent_unfixed_sale_drafts(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_unfixed_sale_preview"),
            data=self._unfixed_sale_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.UNFIXED_SALE,
        )
        before_dashboard = self._side_effect_counts()

        response = self.client.get(reverse("dea_business_events_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recent Unfixed Sales")
        self.assertContains(response, "UNFIXED-SALE-BILL-001")
        self.assertContains(response, "Preview Customer Party")
        self.assertContains(response, "Previewed")
        self.assertContains(response, "Not posted")
        self.assertContains(
            response,
            reverse("dea_unfixed_sale_detail", kwargs={"draft_id": draft.pk}),
        )
        self.assertEqual(self._side_effect_counts(), before_dashboard)

    def test_business_events_dashboard_lists_recent_karigar_movement_drafts(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_karigar_movement_preview"),
            data=self._karigar_issue_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.KARIGAR_ISSUE,
        )
        before_dashboard = self._side_effect_counts()

        response = self.client.get(reverse("dea_business_events_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recent Karigar Custody")
        self.assertContains(response, "KARIGAR-ISSUE-001")
        self.assertContains(response, "Preview Karigar")
        self.assertContains(response, "Previewed")
        self.assertContains(response, "Not posted")
        self.assertContains(
            response,
            reverse("dea_karigar_movement_detail", kwargs={"draft_id": draft.pk}),
        )
        self.assertEqual(self._side_effect_counts(), before_dashboard)

    def test_dashboards_link_to_business_events_scaffold(self):
        dashboard = self.client.get(reverse("dea_dashboard"))
        enhanced = self.client.get(reverse("dea_dashboard_enhanced"))

        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(enhanced.status_code, 200)
        self.assertContains(dashboard, reverse("dea_business_events_dashboard"))
        self.assertContains(enhanced, reverse("dea_business_events_dashboard"))

    def test_owner_dashboards_include_accountant_manual_tools(self):
        dashboard = self.client.get(reverse("dea_dashboard"))
        enhanced = self.client.get(reverse("dea_dashboard_enhanced"))

        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(enhanced.status_code, 200)
        self.assertContains(dashboard, reverse("dea_voucher_hub"))
        self.assertContains(dashboard, reverse("dea_period_list"))
        self.assertContains(enhanced, reverse("dea_voucher_hub"))
        self.assertContains(enhanced, reverse("dea_period_list"))
        self.assertContains(enhanced, reverse("dea_voucher_list"))

    def test_member_dashboards_hide_accountant_manual_tools(self):
        self._login_as_member()

        dashboard = self.client.get(reverse("dea_dashboard"))
        enhanced = self.client.get(reverse("dea_dashboard_enhanced"))

        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(enhanced.status_code, 200)
        self.assertContains(dashboard, reverse("dea_business_events_dashboard"))
        self.assertContains(enhanced, reverse("dea_business_events_dashboard"))
        self.assertNotContains(dashboard, reverse("dea_voucher_hub"))
        self.assertNotContains(dashboard, reverse("dea_period_list"))
        self.assertNotContains(dashboard, reverse("dea_journal_entry_voucher_list"))
        self.assertNotContains(dashboard, reverse("dea_voucher_list"))
        self.assertNotContains(enhanced, reverse("dea_voucher_hub"))
        self.assertNotContains(enhanced, reverse("dea_period_list"))
        self.assertNotContains(enhanced, reverse("dea_journal_entry_voucher_list"))
        self.assertNotContains(enhanced, reverse("dea_voucher_list"))
        self.assertNotContains(enhanced, reverse("dea_chart_of_accounts"))

    def test_sidebar_links_to_business_events_scaffold(self):
        response = self.client.get(reverse("dea_business_events_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Business Events")
        self.assertContains(response, reverse("dea_business_events_dashboard"))
        self.assertContains(response, reverse("dea_reports_hub"))
        self.assertContains(response, reverse("dea_metal_balance_report"))

    def test_owner_sidebar_includes_accountant_legacy_tools(self):
        response = self.client.get(reverse("dea_business_events_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Accounting Tools")
        self.assertContains(response, reverse("dea_voucher_hub"))
        self.assertContains(response, reverse("dea_payment_list"))
        self.assertContains(response, reverse("dea_expense_list"))
        self.assertContains(response, reverse("dea_journal_entry_voucher_list"))
        self.assertContains(response, reverse("dea_opening_balance_wizard"))
        self.assertContains(response, reverse("dea_period_list"))
        self.assertContains(response, reverse("dea_journal_entries_list"))

    def test_fixed_purchase_preview_get_is_side_effect_free(self):
        before = self._side_effect_counts()

        response = self.client.get(reverse("dea_fixed_purchase_preview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fixed Purchase")
        self.assertContains(response, "Submit the form to generate a read-only preview")
        self.assertContains(response, "Confirm posting")
        self.assertEqual(self._side_effect_counts(), before)

    def test_unfixed_purchase_preview_get_is_side_effect_free(self):
        before = self._side_effect_counts()

        response = self.client.get(reverse("dea_unfixed_purchase_preview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unfixed Purchase")
        self.assertContains(response, "Submit the form to generate a read-only preview")
        self.assertContains(response, "Confirm posting")
        self.assertEqual(self._side_effect_counts(), before)

    def test_purchase_rate_fixing_preview_get_is_side_effect_free(self):
        before = self._side_effect_counts()

        response = self.client.get(reverse("dea_purchase_rate_fixing_preview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Purchase Rate Fixing")
        self.assertContains(
            response,
            "Submit the form to generate a read-only purchase rate-fixing preview",
        )
        self.assertContains(response, "Confirm posting")
        self.assertEqual(self._side_effect_counts(), before)

    def test_fixed_sale_preview_get_is_side_effect_free(self):
        before = self._side_effect_counts()

        response = self.client.get(reverse("dea_fixed_sale_preview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fixed Sale")
        self.assertContains(
            response,
            "Submit the form to generate a read-only fixed sale preview",
        )
        self.assertContains(response, "Confirm posting")
        self.assertEqual(self._side_effect_counts(), before)

    def test_unfixed_sale_preview_get_is_side_effect_free(self):
        before = self._side_effect_counts()

        response = self.client.get(reverse("dea_unfixed_sale_preview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unfixed Sale")
        self.assertContains(
            response,
            "Submit the form to generate a read-only unfixed sale preview",
        )
        self.assertContains(response, "Confirm posting")
        self.assertEqual(self._side_effect_counts(), before)

    def test_monetary_settlement_preview_get_is_side_effect_free(self):
        before = self._side_effect_counts()

        response = self.client.get(reverse("dea_monetary_settlement_preview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Receipt / Payment Preview")
        self.assertContains(
            response,
            "Submit the form to generate a read-only receipt/payment preview",
        )
        self.assertContains(response, "Confirm posting")
        self.assertEqual(self._side_effect_counts(), before)

    def test_karigar_movement_preview_get_is_side_effect_free(self):
        before = self._side_effect_counts()

        response = self.client.get(reverse("dea_karigar_movement_preview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Karigar Custody")
        self.assertContains(
            response,
            "Submit the form to generate a read-only karigar custody preview",
        )
        self.assertContains(response, "Confirm posting")
        self.assertEqual(self._side_effect_counts(), before)

    def test_fixed_purchase_preview_post_renders_impacts_without_posting(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_fixed_purchase_preview"),
            data=self._fixed_purchase_preview_data(deps),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Accounting Impact")
        self.assertContains(response, "Commodity Impact")
        self.assertContains(response, "Draft source")
        self.assertContains(response, "Dr")
        self.assertContains(response, "Cr")
        self.assertContains(response, "PURCHASE_RECEIPT")
        self.assertContains(response, "FIXED")
        self.assertContains(response, "Preview key")
        self.assertContains(response, "Posting Readiness")
        self.assertContains(response, "Ready for future confirm")
        self.assertContains(response, "Open accounting period")
        self.assertContains(response, "No posted fixed-purchase voucher for this draft")
        self.assertContains(response, "Confirm fixed purchase posting")
        self.assertContains(response, "Inventory lot/costing integration is not in this MVP slice")
        self.assertEqual(self._side_effect_counts(), before)
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.FIXED_PURCHASE,
            source_reference="SUP-BILL-001",
        )
        self.assertEqual(draft.status, BusinessEventDraft.Status.PREVIEWED)
        self.assertEqual(draft.normalized_payload["money_amount"], "620000.00")
        self.assertEqual(draft.preview_payload["commodity_impact"]["fine_weight"], "100.000")
        self.assertEqual(draft.created_by, self.user)
        self.assertEqual(draft.updated_by, self.user)

    def test_unfixed_purchase_preview_post_renders_exposure_without_posting(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_unfixed_purchase_preview"),
            data=self._unfixed_purchase_preview_data(deps),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Accounting Impact")
        self.assertContains(response, "Commodity Impact")
        self.assertContains(response, "Exposure Impact")
        self.assertContains(response, "Draft source")
        self.assertContains(response, "No final monetary payable is created")
        self.assertContains(response, "PURCHASE_RECEIPT")
        self.assertContains(response, "UNFIXED")
        self.assertContains(response, "PURCHASE")
        self.assertContains(response, "Open fine weight")
        self.assertContains(response, "Preview key")
        self.assertContains(response, "Posting Readiness")
        self.assertContains(response, "Ready for future confirm")
        self.assertContains(response, "Supplier party exists and is active")
        self.assertContains(response, "No posted unfixed-purchase voucher for this draft")
        self.assertContains(response, "Confirm unfixed purchase posting")
        self.assertContains(response, "Inventory lot/costing integration is not in this MVP slice")
        self.assertEqual(self._side_effect_counts(), before)
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.UNFIXED_PURCHASE,
            source_reference="UNFIXED-SUP-BILL-001",
        )
        self.assertEqual(draft.status, BusinessEventDraft.Status.PREVIEWED)
        self.assertEqual(draft.normalized_payload["fine_weight"], "100.000")
        self.assertEqual(draft.normalized_payload["last_valuation_rate"], "6200.0000")
        self.assertEqual(draft.preview_payload["accounting_impact"]["creates_financial_posting"], False)
        self.assertEqual(draft.preview_payload["exposure_impact"]["creates_exposure"], True)
        self.assertEqual(draft.created_by, self.user)
        self.assertEqual(draft.updated_by, self.user)

    def test_purchase_rate_fixing_preview_post_renders_impacts_without_posting(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        exposure = self._create_unfixed_purchase_exposure(deps)
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_purchase_rate_fixing_preview"),
            data=self._purchase_rate_fixing_preview_data(deps, exposure),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Purchase Rate Fixing")
        self.assertContains(response, "Accounting Impact")
        self.assertContains(response, "Exposure Impact")
        self.assertContains(response, "Commodity Impact")
        self.assertContains(response, "Draft source")
        self.assertContains(response, "PRF-001")
        self.assertContains(response, "Posting Readiness")
        self.assertContains(response, "Ready for future confirm")
        self.assertContains(response, "Draft source saved")
        self.assertContains(response, "Payload hash matches preview")
        self.assertContains(response, "Open purchase exposure")
        self.assertContains(response, "Supplier monetary account is compatible")
        self.assertContains(response, "Dr")
        self.assertContains(response, "Cr")
        self.assertContains(response, "INR 310000.00")
        self.assertContains(response, "PARTIALLY_FIXED")
        self.assertContains(response, "Rate fixing does not create a physical metal movement")
        self.assertEqual(self._side_effect_counts(), before)
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.PURCHASE_RATE_FIXING,
            source_reference="PRF-001",
        )
        self.assertEqual(draft.status, BusinessEventDraft.Status.PREVIEWED)
        self.assertEqual(draft.normalized_payload["fine_weight"], "50.000")
        self.assertEqual(draft.normalized_payload["rate"], "6200.0000")
        self.assertEqual(draft.preview_payload["exposure_impact"]["open_fine_weight_after"], "50.000")
        self.assertEqual(draft.created_by, self.user)
        self.assertEqual(draft.updated_by, self.user)

    def test_sale_rate_fixing_preview_get_is_side_effect_free(self):
        before = self._side_effect_counts()

        response = self.client.get(reverse("dea_sale_rate_fixing_preview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sale Rate Fixing")
        self.assertContains(response, "Preview")
        self.assertContains(response, "Confirm posting")
        self.assertEqual(self._side_effect_counts(), before)

    def test_sale_rate_fixing_preview_post_renders_impacts_without_posting(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        exposure = self._create_unfixed_sale_exposure(deps)
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_sale_rate_fixing_preview"),
            data=self._sale_rate_fixing_preview_data(deps, exposure),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sale Rate Fixing")
        self.assertContains(response, "Accounting Impact")
        self.assertContains(response, "Exposure Impact")
        self.assertContains(response, "Commodity Impact")
        self.assertContains(response, "Draft source")
        self.assertContains(response, "SRF-001")
        self.assertContains(response, "Posting Readiness")
        self.assertContains(response, "Ready for future confirm")
        self.assertContains(response, "Draft source saved")
        self.assertContains(response, "Payload hash matches preview")
        self.assertContains(response, "Open sale exposure")
        self.assertContains(response, "Customer monetary account is compatible")
        self.assertContains(response, "Dr")
        self.assertContains(response, "Cr")
        self.assertContains(response, "INR 350000.00")
        self.assertContains(response, "PARTIALLY_FIXED")
        self.assertContains(response, "Rate fixing does not create a physical metal movement")
        self.assertEqual(self._side_effect_counts(), before)
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.SALE_RATE_FIXING,
            source_reference="SRF-001",
        )
        self.assertEqual(draft.status, BusinessEventDraft.Status.PREVIEWED)
        self.assertEqual(draft.normalized_payload["fine_weight"], "50.000")
        self.assertEqual(draft.normalized_payload["rate"], "7000.0000")
        self.assertEqual(draft.preview_payload["exposure_impact"]["open_fine_weight_after"], "50.000")
        self.assertEqual(draft.created_by, self.user)
        self.assertEqual(draft.updated_by, self.user)

    def test_customer_receipt_preview_post_renders_impacts_without_posting(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_monetary_settlement_preview"),
            data=self._customer_receipt_preview_data(deps),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Receipt / Payment Preview")
        self.assertContains(response, "Customer receipt")
        self.assertContains(response, "Accounting Impact")
        self.assertContains(response, "Payment Impact")
        self.assertContains(response, "Commodity Impact")
        self.assertContains(response, "Draft source")
        self.assertContains(response, "SETTLE-REC-001")
        self.assertContains(response, "Posting Readiness")
        self.assertContains(response, "Ready for future confirm")
        self.assertContains(response, "Cash/bank ledger exists")
        self.assertContains(response, "Dr")
        self.assertContains(response, "Cr")
        self.assertContains(response, "INR 25000.00")
        self.assertContains(response, "Normal monetary receipt/payment creates no commodity movement")
        self.assertEqual(self._side_effect_counts(), before)
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.CUSTOMER_RECEIPT,
            source_reference="SETTLE-REC-001",
        )
        self.assertEqual(draft.status, BusinessEventDraft.Status.PREVIEWED)
        self.assertEqual(draft.normalized_payload["money_amount"], "25000.00")
        self.assertEqual(draft.normalized_payload["settlement_type"], "CUSTOMER_RECEIPT")
        self.assertEqual(draft.preview_payload["payment_impact"]["direction"], "RECEIPT")
        self.assertEqual(draft.created_by, self.user)
        self.assertEqual(draft.updated_by, self.user)

    def test_supplier_payment_preview_post_renders_impacts_without_posting(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_monetary_settlement_preview"),
            data=self._supplier_payment_preview_data(deps),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Receipt / Payment Preview")
        self.assertContains(response, "Supplier payment")
        self.assertContains(response, "Accounting Impact")
        self.assertContains(response, "Payment Impact")
        self.assertContains(response, "Commodity Impact")
        self.assertContains(response, "SETTLE-PAY-001")
        self.assertContains(response, "INR 18000.00")
        self.assertContains(response, "PAYMENT")
        self.assertContains(response, "Normal monetary receipt/payment creates no commodity movement")
        self.assertEqual(self._side_effect_counts(), before)
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.SUPPLIER_PAYMENT,
            source_reference="SETTLE-PAY-001",
        )
        self.assertEqual(draft.status, BusinessEventDraft.Status.PREVIEWED)
        self.assertEqual(draft.normalized_payload["money_amount"], "18000.00")
        self.assertEqual(draft.normalized_payload["settlement_type"], "SUPPLIER_PAYMENT")
        self.assertEqual(draft.preview_payload["payment_impact"]["direction"], "PAYMENT")
        self.assertEqual(draft.created_by, self.user)
        self.assertEqual(draft.updated_by, self.user)

    def test_karigar_issue_preview_post_renders_custody_impact_without_posting(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_karigar_movement_preview"),
            data=self._karigar_issue_preview_data(deps),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Karigar Custody")
        self.assertContains(response, "Karigar issue")
        self.assertContains(response, "Accounting Impact")
        self.assertContains(response, "Commodity Impact")
        self.assertContains(response, "Exposure Impact")
        self.assertContains(response, "Draft source")
        self.assertContains(response, "KARIGAR-ISSUE-001")
        self.assertContains(response, "Posting Readiness")
        self.assertContains(response, "Ready for future confirm")
        self.assertContains(response, "Issue destination is selected karigar custody")
        self.assertContains(response, "KARIGAR_ISSUE")
        self.assertContains(response, "NOT_APPLICABLE")
        self.assertContains(response, "Karigar custody movement is commodity-only")
        self.assertContains(response, "does not create fixed/unfixed exposure")
        self.assertEqual(self._side_effect_counts(), before)
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.KARIGAR_ISSUE,
            source_reference="KARIGAR-ISSUE-001",
        )
        self.assertEqual(draft.status, BusinessEventDraft.Status.PREVIEWED)
        self.assertEqual(draft.normalized_payload["movement_type"], "KARIGAR_ISSUE")
        self.assertEqual(draft.normalized_payload["fine_weight"], "25.000")
        self.assertEqual(draft.preview_payload["accounting_impact"]["creates_financial_posting"], False)
        self.assertEqual(draft.preview_payload["exposure_impact"]["creates_exposure"], False)
        self.assertEqual(draft.created_by, self.user)
        self.assertEqual(draft.updated_by, self.user)

    def test_karigar_receipt_preview_post_renders_custody_impact_without_posting(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_karigar_movement_preview"),
            data=self._karigar_receipt_preview_data(deps),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Karigar receipt")
        self.assertContains(response, "KARIGAR-RECEIPT-001")
        self.assertContains(response, "Receipt source is selected karigar custody")
        self.assertContains(response, "KARIGAR_RECEIPT")
        self.assertContains(response, "Karigar custody movement is commodity-only")
        self.assertEqual(self._side_effect_counts(), before)
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.KARIGAR_RECEIPT,
            source_reference="KARIGAR-RECEIPT-001",
        )
        self.assertEqual(draft.status, BusinessEventDraft.Status.PREVIEWED)
        self.assertEqual(draft.normalized_payload["movement_type"], "KARIGAR_RECEIPT")
        self.assertEqual(draft.normalized_payload["fine_weight"], "20.000")
        self.assertEqual(draft.preview_payload["commodity_impact"]["movement_type"], "KARIGAR_RECEIPT")
        self.assertEqual(draft.created_by, self.user)
        self.assertEqual(draft.updated_by, self.user)

    def test_fixed_sale_preview_post_renders_impacts_without_posting(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_fixed_sale_preview"),
            data=self._fixed_sale_preview_data(deps),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fixed Sale")
        self.assertContains(response, "Accounting Impact")
        self.assertContains(response, "Commodity Impact")
        self.assertContains(response, "Draft source")
        self.assertContains(response, "SALE-BILL-001")
        self.assertContains(response, "Posting Readiness")
        self.assertContains(response, "Ready for future confirm")
        self.assertContains(response, "Draft source saved")
        self.assertContains(response, "Payload hash matches preview")
        self.assertContains(response, "Customer account exists")
        self.assertContains(response, "Source commodity account is active and matches commodity")
        self.assertContains(response, "Dr")
        self.assertContains(response, "Cr")
        self.assertContains(response, "SALE_ISSUE")
        self.assertContains(response, "FIXED")
        self.assertContains(response, "Preview key")
        self.assertContains(response, "INR 700000.00")
        self.assertContains(response, "Exposure created: False")
        self.assertContains(response, "Confirm fixed sale posting")
        self.assertContains(response, "View draft detail")
        self.assertContains(response, "Inventory lot/costing and COGS integration is not in this MVP slice")
        self.assertEqual(self._side_effect_counts(), before)
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.FIXED_SALE,
            source_reference="SALE-BILL-001",
        )
        self.assertContains(
            response,
            reverse("dea_fixed_sale_detail", kwargs={"draft_id": draft.pk}),
        )
        self.assertEqual(draft.status, BusinessEventDraft.Status.PREVIEWED)
        self.assertEqual(draft.normalized_payload["money_amount"], "700000.00")
        self.assertEqual(draft.normalized_payload["fine_weight"], "100.000")
        self.assertEqual(draft.preview_payload["commodity_impact"]["movement_type"], "SALE_ISSUE")
        self.assertEqual(draft.created_by, self.user)
        self.assertEqual(draft.updated_by, self.user)

    def test_unfixed_sale_preview_post_renders_exposure_without_posting(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_unfixed_sale_preview"),
            data=self._unfixed_sale_preview_data(deps),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unfixed Sale")
        self.assertContains(response, "Accounting Impact")
        self.assertContains(response, "Commodity Impact")
        self.assertContains(response, "Exposure Impact")
        self.assertContains(response, "Draft source")
        self.assertContains(response, "UNFIXED-SALE-BILL-001")
        self.assertContains(response, "No final monetary receivable or revenue is created")
        self.assertContains(response, "SALE_ISSUE")
        self.assertContains(response, "UNFIXED")
        self.assertContains(response, "SALE")
        self.assertContains(response, "Open fine weight")
        self.assertContains(response, "Preview key")
        self.assertContains(response, "Posting Readiness")
        self.assertContains(response, "Ready for future confirm")
        self.assertContains(response, "Customer party exists and is active")
        self.assertContains(response, "No posted unfixed-sale voucher for this draft")
        self.assertContains(response, "Confirm posting is intentionally disabled")
        self.assertContains(response, "View draft detail")
        self.assertContains(response, "Inventory lot/costing and COGS integration is not in this MVP slice")
        self.assertEqual(self._side_effect_counts(), before)
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.UNFIXED_SALE,
            source_reference="UNFIXED-SALE-BILL-001",
        )
        self.assertContains(
            response,
            reverse("dea_unfixed_sale_detail", kwargs={"draft_id": draft.pk}),
        )
        self.assertEqual(draft.status, BusinessEventDraft.Status.PREVIEWED)
        self.assertEqual(draft.normalized_payload["fine_weight"], "100.000")
        self.assertEqual(draft.normalized_payload["last_valuation_rate"], "7000.0000")
        self.assertEqual(draft.preview_payload["accounting_impact"]["creates_financial_posting"], False)
        self.assertEqual(draft.preview_payload["commodity_impact"]["movement_type"], "SALE_ISSUE")
        self.assertEqual(draft.preview_payload["exposure_impact"]["creates_exposure"], True)
        self.assertEqual(draft.preview_payload["exposure_impact"]["side"], "SALE")
        self.assertEqual(draft.created_by, self.user)
        self.assertEqual(draft.updated_by, self.user)

    def test_fixed_purchase_confirm_post_is_disabled_and_side_effect_free(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_fixed_purchase_preview"),
            data={
                **self._fixed_purchase_preview_data(deps),
                "action": "confirm",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Confirm posting is disabled", status_code=400)
        self.assertEqual(self._side_effect_counts(), before)
        self.assertEqual(BusinessEventDraft.objects.count(), 0)

    def test_unfixed_purchase_confirm_post_is_disabled_and_side_effect_free(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_unfixed_purchase_preview"),
            data={
                **self._unfixed_purchase_preview_data(deps),
                "action": "confirm",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Confirm posting is disabled", status_code=400)
        self.assertEqual(self._side_effect_counts(), before)
        self.assertEqual(BusinessEventDraft.objects.count(), 0)

    def test_purchase_rate_fixing_confirm_post_is_disabled_and_side_effect_free(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        exposure = self._create_unfixed_purchase_exposure(deps)
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_purchase_rate_fixing_preview"),
            data={
                **self._purchase_rate_fixing_preview_data(deps, exposure),
                "action": "confirm",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Confirm posting is disabled", status_code=400)
        self.assertEqual(self._side_effect_counts(), before)

    def test_sale_rate_fixing_confirm_post_is_disabled_and_side_effect_free(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        exposure = self._create_unfixed_sale_exposure(deps)
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_sale_rate_fixing_preview"),
            data={
                **self._sale_rate_fixing_preview_data(deps, exposure),
                "action": "confirm",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Confirm posting is disabled", status_code=400)
        self.assertEqual(self._side_effect_counts(), before)

    def test_monetary_settlement_confirm_post_is_disabled_and_side_effect_free(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_monetary_settlement_preview"),
            data={
                **self._customer_receipt_preview_data(deps),
                "action": "confirm",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Confirm posting is disabled", status_code=400)
        self.assertEqual(self._side_effect_counts(), before)
        self.assertEqual(BusinessEventDraft.objects.count(), 0)

    def test_karigar_movement_confirm_post_is_disabled_and_side_effect_free(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_karigar_movement_preview"),
            data={
                **self._karigar_issue_preview_data(deps),
                "action": "confirm",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Confirm posting is disabled", status_code=400)
        self.assertEqual(self._side_effect_counts(), before)
        self.assertEqual(BusinessEventDraft.objects.count(), 0)

    def test_monetary_settlement_detail_shows_readiness_and_repreview_link(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_monetary_settlement_preview"),
            data=self._customer_receipt_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.CUSTOMER_RECEIPT,
        )
        before = self._side_effect_counts()

        response = self.client.get(
            reverse("dea_monetary_settlement_detail", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Receipt / Payment Result")
        self.assertContains(response, "SETTLE-REC-001")
        self.assertContains(response, "Customer receipt")
        self.assertContains(response, "Not posted")
        self.assertContains(response, "Posting Readiness")
        self.assertContains(response, "Ready for future confirm")
        self.assertContains(response, "Cash/bank ledger exists")
        self.assertContains(response, "Settlement reference captured")
        self.assertContains(response, "Accounting Impact")
        self.assertContains(response, "Payment Impact")
        self.assertContains(response, "RECEIPT")
        self.assertContains(response, "Normal monetary receipt/payment creates no commodity movement")
        self.assertContains(response, "Re-preview receipt/payment")
        self.assertEqual(self._side_effect_counts(), before)

    def test_karigar_movement_detail_shows_readiness_and_no_financial_rows(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_karigar_movement_preview"),
            data=self._karigar_issue_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.KARIGAR_ISSUE,
        )
        before = self._side_effect_counts()

        response = self.client.get(
            reverse("dea_karigar_movement_detail", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Karigar Custody Result")
        self.assertContains(response, "KARIGAR-ISSUE-001")
        self.assertContains(response, "Karigar issue")
        self.assertContains(response, "Not posted")
        self.assertContains(response, "Posting Readiness")
        self.assertContains(response, "Ready to post")
        self.assertContains(response, "Issue destination is selected karigar custody")
        self.assertContains(response, "Accounting Impact")
        self.assertContains(response, "Commodity Impact")
        self.assertContains(response, "KARIGAR_ISSUE")
        self.assertContains(response, "Karigar custody movement is commodity-only")
        self.assertContains(response, "Confirm karigar custody posting")
        self.assertEqual(self._side_effect_counts(), before)

    def test_karigar_movement_confirm_endpoint_posts_from_previewed_draft(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_karigar_movement_preview"),
            data=self._karigar_issue_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.KARIGAR_ISSUE,
        )

        response = self.client.post(
            reverse("dea_karigar_movement_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertRedirects(
            response,
            reverse("dea_karigar_movement_detail", kwargs={"draft_id": draft.pk}),
        )
        self.assertEqual(
            self._side_effect_counts(),
            {
                "vouchers": 1,
                "voucher_lines": 0,
                "journal_entries": 0,
                "ledger_transactions": 0,
                "account_transactions": 0,
                "payment_vouchers": 0,
                "commodity_movements": 1,
                "exposures": 0,
                "rate_fixings": 0,
            },
        )

        movement = CommodityMovement.objects.get()
        self.assertEqual(movement.movement_type, CommodityMovement.MovementType.KARIGAR_ISSUE)
        self.assertEqual(movement.from_account, deps["vault"])
        self.assertEqual(movement.to_account, deps["karigar_custody"])

        detail = self.client.get(
            reverse("dea_karigar_movement_detail", kwargs={"draft_id": draft.pk})
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Karigar Custody Result")
        self.assertContains(detail, "Posted")
        self.assertContains(detail, "Voucher")
        self.assertContains(detail, "Commodity Impact")
        self.assertContains(detail, "KARIGAR_ISSUE")
        self.assertContains(detail, "Karigar custody movement is commodity-only")

    def test_karigar_movement_confirm_endpoint_is_idempotent_for_duplicate_submit(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_karigar_movement_preview"),
            data=self._karigar_receipt_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.KARIGAR_RECEIPT,
        )

        first = self.client.post(
            reverse("dea_karigar_movement_confirm", kwargs={"draft_id": draft.pk})
        )
        second = self.client.post(
            reverse("dea_karigar_movement_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)
        self.assertEqual(PaymentVoucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 0)
        self.assertEqual(RateFixing.objects.count(), 0)

    def test_karigar_movement_confirm_endpoint_rejects_member_role(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_karigar_movement_preview"),
            data=self._karigar_issue_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.KARIGAR_ISSUE,
        )
        member = User.objects.create_user(
            username=f"dea-business-event-member-{uuid.uuid4().hex[:8]}",
            email=f"dea-business-event-member-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=member_role)
        self.client.logout()
        self.client.login(username=member.username, password="testpass123")

        response = self.client.post(
            reverse("dea_karigar_movement_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)

    def test_business_events_dashboard_links_to_monetary_settlement_detail(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_monetary_settlement_preview"),
            data=self._supplier_payment_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.SUPPLIER_PAYMENT,
        )
        before = self._side_effect_counts()

        response = self.client.get(reverse("dea_business_events_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recent Receipts / Payments")
        self.assertContains(response, "SETTLE-PAY-001")
        self.assertContains(response, "Not posted")
        self.assertContains(
            response,
            reverse("dea_monetary_settlement_detail", kwargs={"draft_id": draft.pk}),
        )
        self.assertEqual(self._side_effect_counts(), before)

    def test_monetary_settlement_confirm_endpoint_posts_from_previewed_draft(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_monetary_settlement_preview"),
            data=self._customer_receipt_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.CUSTOMER_RECEIPT,
        )

        response = self.client.post(
            reverse("dea_monetary_settlement_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertRedirects(
            response,
            reverse("dea_monetary_settlement_detail", kwargs={"draft_id": draft.pk}),
        )
        self.assertEqual(
            self._side_effect_counts(),
            {
                "vouchers": 1,
                "voucher_lines": 2,
                "journal_entries": 1,
                "ledger_transactions": 1,
                "account_transactions": 1,
                "payment_vouchers": 1,
                "commodity_movements": 0,
                "exposures": 0,
                "rate_fixings": 0,
            },
        )

        detail = self.client.get(
            reverse("dea_monetary_settlement_detail", kwargs={"draft_id": draft.pk})
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Receipt / Payment Result")
        self.assertContains(detail, "Posted")
        self.assertContains(detail, "Payment voucher")
        self.assertContains(detail, "Voucher")
        self.assertContains(detail, "Journal entry")
        self.assertContains(detail, "Accounting Impact")
        self.assertContains(detail, "Payment Impact")
        self.assertContains(detail, "Commodity Impact")
        self.assertContains(detail, "Normal monetary receipt/payment creates no commodity movement")
        self.assertContains(detail, "RECEIPT")

    def test_monetary_settlement_confirm_endpoint_is_idempotent_for_duplicate_submit(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_monetary_settlement_preview"),
            data=self._supplier_payment_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.SUPPLIER_PAYMENT,
        )

        first = self.client.post(
            reverse("dea_monetary_settlement_confirm", kwargs={"draft_id": draft.pk})
        )
        second = self.client.post(
            reverse("dea_monetary_settlement_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(PaymentVoucher.objects.count(), 1)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.count(), 2)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(LedgerTransaction.objects.count(), 1)
        self.assertEqual(AccountTransaction.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(ExposureLine.objects.count(), 0)
        self.assertEqual(RateFixing.objects.count(), 0)

    def test_monetary_settlement_confirm_endpoint_rejects_member_role(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_monetary_settlement_preview"),
            data=self._customer_receipt_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.CUSTOMER_RECEIPT,
        )
        member = User.objects.create_user(
            username=f"dea-business-event-member-{uuid.uuid4().hex[:8]}",
            email=f"dea-business-event-member-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=member_role)
        self.client.logout()
        self.client.login(username=member.username, password="testpass123")

        response = self.client.post(
            reverse("dea_monetary_settlement_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(PaymentVoucher.objects.count(), 0)
        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)

    def test_fixed_sale_confirm_post_is_disabled_and_side_effect_free(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_fixed_sale_preview"),
            data={
                **self._fixed_sale_preview_data(deps),
                "action": "confirm",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Confirm posting is disabled", status_code=400)
        self.assertEqual(self._side_effect_counts(), before)
        self.assertEqual(BusinessEventDraft.objects.count(), 0)

    def test_unfixed_sale_confirm_post_is_disabled_and_side_effect_free(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_unfixed_sale_preview"),
            data={
                **self._unfixed_sale_preview_data(deps),
                "action": "confirm",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Confirm posting is disabled", status_code=400)
        self.assertEqual(self._side_effect_counts(), before)
        self.assertEqual(BusinessEventDraft.objects.count(), 0)

    def test_fixed_purchase_preview_updates_existing_draft_for_same_reference(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_fixed_purchase_preview"),
            data=self._fixed_purchase_preview_data(deps),
        )
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_fixed_purchase_preview"),
            data={
                **self._fixed_purchase_preview_data(deps),
                "money_amount": "621000.00",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(BusinessEventDraft.objects.count(), 1)
        draft = BusinessEventDraft.objects.get()
        self.assertEqual(draft.normalized_payload["money_amount"], "621000.00")
        self.assertEqual(draft.preview_payload["accounting_impact"]["debits"][0]["amount"], "621000.00")
        self.assertEqual(self._side_effect_counts(), before)

    def test_fixed_purchase_readiness_blocks_when_period_is_missing(self):
        deps = self._seed_fixed_purchase_preview_dependencies(create_period=False)
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_fixed_purchase_preview"),
            data=self._fixed_purchase_preview_data(deps),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Posting Readiness")
        self.assertContains(response, "Blocked")
        self.assertContains(response, "No accounting period contains this event date")
        self.assertEqual(self._side_effect_counts(), before)
        self.assertEqual(BusinessEventDraft.objects.count(), 1)

    def test_unfixed_purchase_readiness_blocks_when_period_is_missing(self):
        deps = self._seed_fixed_purchase_preview_dependencies(create_period=False)
        before = self._side_effect_counts()

        response = self.client.post(
            reverse("dea_unfixed_purchase_preview"),
            data=self._unfixed_purchase_preview_data(deps),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Posting Readiness")
        self.assertContains(response, "Blocked")
        self.assertContains(response, "No accounting period contains this event date")
        self.assertEqual(self._side_effect_counts(), before)
        self.assertEqual(BusinessEventDraft.objects.count(), 1)

    def test_unfixed_sale_detail_shows_readiness_and_impacts_without_posting(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_unfixed_sale_preview"),
            data=self._unfixed_sale_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.UNFIXED_SALE,
        )
        before = self._side_effect_counts()

        response = self.client.get(
            reverse("dea_unfixed_sale_detail", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unfixed Sale Result")
        self.assertContains(response, "UNFIXED-SALE-BILL-001")
        self.assertContains(response, "Preview Customer Party")
        self.assertContains(response, "Not posted")
        self.assertContains(response, "Posting Readiness")
        self.assertContains(response, "Ready for future confirm")
        self.assertContains(response, "Customer party exists and is active")
        self.assertContains(response, "No posted unfixed-sale voucher for this draft")
        self.assertContains(response, "Accounting Impact")
        self.assertContains(response, "No final monetary receivable or revenue is created")
        self.assertContains(response, "Commodity Impact")
        self.assertContains(response, "SALE_ISSUE")
        self.assertContains(response, "Exposure Impact")
        self.assertContains(response, "SALE")
        self.assertContains(response, "Re-preview unfixed sale")
        self.assertEqual(self._side_effect_counts(), before)

    def test_fixed_purchase_detail_shows_repreview_link_when_readiness_is_blocked(self):
        deps = self._seed_fixed_purchase_preview_dependencies(create_period=False)
        self.client.post(
            reverse("dea_fixed_purchase_preview"),
            data=self._fixed_purchase_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get()
        before = self._side_effect_counts()

        response = self.client.get(
            reverse("dea_fixed_purchase_detail", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Posting Readiness")
        self.assertContains(response, "No accounting period contains this event date")
        self.assertContains(response, "Re-preview fixed purchase")
        self.assertContains(response, reverse("dea_fixed_purchase_preview"))
        self.assertEqual(self._side_effect_counts(), before)

    def test_unfixed_purchase_detail_shows_readiness_and_repreview_link(self):
        deps = self._seed_fixed_purchase_preview_dependencies(create_period=False)
        self.client.post(
            reverse("dea_unfixed_purchase_preview"),
            data=self._unfixed_purchase_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.UNFIXED_PURCHASE,
        )
        before = self._side_effect_counts()

        response = self.client.get(
            reverse("dea_unfixed_purchase_detail", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unfixed Purchase Result")
        self.assertContains(response, "Not posted")
        self.assertContains(response, "Posting Readiness")
        self.assertContains(response, "No accounting period contains this event date")
        self.assertContains(response, "Re-preview unfixed purchase")
        self.assertContains(response, reverse("dea_unfixed_purchase_preview"))
        self.assertContains(response, "No final monetary payable is created")
        self.assertContains(response, "Exposure Impact")
        self.assertEqual(self._side_effect_counts(), before)

    def test_purchase_rate_fixing_detail_shows_readiness_and_repreview_link(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        exposure = self._create_unfixed_purchase_exposure(deps)
        self.client.post(
            reverse("dea_purchase_rate_fixing_preview"),
            data=self._purchase_rate_fixing_preview_data(deps, exposure),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.PURCHASE_RATE_FIXING,
        )
        before = self._side_effect_counts()

        response = self.client.get(
            reverse("dea_purchase_rate_fixing_detail", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Purchase Rate Fixing Result")
        self.assertContains(response, "Not posted")
        self.assertContains(response, "Posting Readiness")
        self.assertContains(response, "Ready for future confirm")
        self.assertContains(response, "Confirm purchase rate fixing")
        self.assertContains(response, "Re-preview rate fixing")
        self.assertContains(response, "Rate fixing does not create a physical metal movement")
        self.assertEqual(self._side_effect_counts(), before)

    def test_fixed_sale_detail_shows_readiness_and_repreview_link(self):
        deps = self._seed_fixed_purchase_preview_dependencies(create_period=False)
        self.client.post(
            reverse("dea_fixed_sale_preview"),
            data=self._fixed_sale_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.FIXED_SALE,
        )
        before = self._side_effect_counts()

        response = self.client.get(
            reverse("dea_fixed_sale_detail", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fixed Sale Result")
        self.assertContains(response, "Not posted")
        self.assertContains(response, "Posting Readiness")
        self.assertContains(response, "No accounting period contains this event date")
        self.assertContains(response, "Re-preview fixed sale")
        self.assertContains(response, reverse("dea_fixed_sale_preview"))
        self.assertContains(response, "No posted accounting rows yet")
        self.assertContains(response, "No posted commodity movement yet")
        self.assertEqual(self._side_effect_counts(), before)

    def test_fixed_purchase_confirm_endpoint_posts_from_previewed_draft(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_fixed_purchase_preview"),
            data=self._fixed_purchase_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get()

        response = self.client.post(
            reverse("dea_fixed_purchase_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertRedirects(
            response,
            reverse("dea_fixed_purchase_detail", kwargs={"draft_id": draft.pk}),
        )
        self.assertEqual(
            self._side_effect_counts(),
            {
                "vouchers": 1,
                "voucher_lines": 2,
                "journal_entries": 1,
                "ledger_transactions": 1,
                "account_transactions": 1,
                "payment_vouchers": 0,
                "commodity_movements": 1,
                "exposures": 0,
                "rate_fixings": 0,
            },
        )

        detail = self.client.get(
            reverse("dea_fixed_purchase_detail", kwargs={"draft_id": draft.pk})
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Fixed Purchase Result")
        self.assertContains(detail, "Posted")
        self.assertContains(detail, "Voucher")
        self.assertContains(detail, "Journal entry")
        self.assertContains(detail, "Accounting Impact")
        self.assertContains(detail, "Commodity Impact")
        self.assertContains(detail, "PURCHASE_RECEIPT")

    def test_fixed_purchase_confirm_endpoint_is_idempotent_for_duplicate_submit(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_fixed_purchase_preview"),
            data=self._fixed_purchase_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get()

        first = self.client.post(
            reverse("dea_fixed_purchase_confirm", kwargs={"draft_id": draft.pk})
        )
        second = self.client.post(
            reverse("dea_fixed_purchase_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)

    def test_fixed_purchase_confirm_endpoint_rejects_member_role(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_fixed_purchase_preview"),
            data=self._fixed_purchase_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get()
        member = User.objects.create_user(
            username=f"dea-business-event-member-{uuid.uuid4().hex[:8]}",
            email=f"dea-business-event-member-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=member_role)
        self.client.logout()
        self.client.login(username=member.username, password="testpass123")

        response = self.client.post(
            reverse("dea_fixed_purchase_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)

    def test_unfixed_purchase_confirm_endpoint_posts_from_previewed_draft(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_unfixed_purchase_preview"),
            data=self._unfixed_purchase_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.UNFIXED_PURCHASE,
        )

        response = self.client.post(
            reverse("dea_unfixed_purchase_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertRedirects(
            response,
            reverse("dea_unfixed_purchase_detail", kwargs={"draft_id": draft.pk}),
        )
        self.assertEqual(
            self._side_effect_counts(),
            {
                "vouchers": 1,
                "voucher_lines": 0,
                "journal_entries": 0,
                "ledger_transactions": 0,
                "account_transactions": 0,
                "payment_vouchers": 0,
                "commodity_movements": 1,
                "exposures": 1,
                "rate_fixings": 0,
            },
        )

        detail = self.client.get(
            reverse("dea_unfixed_purchase_detail", kwargs={"draft_id": draft.pk})
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Unfixed Purchase Result")
        self.assertContains(detail, "Posted")
        self.assertContains(detail, "Voucher")
        self.assertContains(detail, "Commodity Impact")
        self.assertContains(detail, "Exposure Impact")
        self.assertContains(detail, "PURCHASE_RECEIPT")
        self.assertContains(detail, "UNFIXED")
        self.assertContains(detail, "PURCHASE")

    def test_unfixed_purchase_confirm_endpoint_is_idempotent_for_duplicate_submit(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_unfixed_purchase_preview"),
            data=self._unfixed_purchase_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.UNFIXED_PURCHASE,
        )

        first = self.client.post(
            reverse("dea_unfixed_purchase_confirm", kwargs={"draft_id": draft.pk})
        )
        second = self.client.post(
            reverse("dea_unfixed_purchase_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 1)

    def test_unfixed_purchase_confirm_endpoint_rejects_member_role(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_unfixed_purchase_preview"),
            data=self._unfixed_purchase_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.UNFIXED_PURCHASE,
        )
        member = User.objects.create_user(
            username=f"dea-business-event-member-{uuid.uuid4().hex[:8]}",
            email=f"dea-business-event-member-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=member_role)
        self.client.logout()
        self.client.login(username=member.username, password="testpass123")

        response = self.client.post(
            reverse("dea_unfixed_purchase_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(ExposureLine.objects.count(), 0)

    def test_purchase_rate_fixing_confirm_endpoint_posts_from_previewed_draft(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        exposure = self._create_unfixed_purchase_exposure(deps)
        self.client.post(
            reverse("dea_purchase_rate_fixing_preview"),
            data=self._purchase_rate_fixing_preview_data(deps, exposure),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.PURCHASE_RATE_FIXING,
        )

        response = self.client.post(
            reverse("dea_purchase_rate_fixing_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertRedirects(
            response,
            reverse("dea_purchase_rate_fixing_detail", kwargs={"draft_id": draft.pk}),
        )
        self.assertEqual(
            self._side_effect_counts(),
            {
                "vouchers": 2,
                "voucher_lines": 2,
                "journal_entries": 1,
                "ledger_transactions": 1,
                "account_transactions": 1,
                "payment_vouchers": 0,
                "commodity_movements": 1,
                "exposures": 1,
                "rate_fixings": 1,
            },
        )
        exposure.refresh_from_db()
        self.assertEqual(str(exposure.open_fine_weight), "50.000")

        detail = self.client.get(
            reverse("dea_purchase_rate_fixing_detail", kwargs={"draft_id": draft.pk})
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Purchase Rate Fixing Result")
        self.assertContains(detail, "Posted")
        self.assertContains(detail, "Rate fixing")
        self.assertContains(detail, "Voucher")
        self.assertContains(detail, "Journal entry")
        self.assertContains(detail, "Accounting Impact")
        self.assertContains(detail, "Exposure Impact")
        self.assertContains(detail, "PARTIALLY_FIXED")

    def test_purchase_rate_fixing_confirm_endpoint_is_idempotent_for_duplicate_submit(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        exposure = self._create_unfixed_purchase_exposure(deps)
        self.client.post(
            reverse("dea_purchase_rate_fixing_preview"),
            data=self._purchase_rate_fixing_preview_data(deps, exposure),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.PURCHASE_RATE_FIXING,
        )

        first = self.client.post(
            reverse("dea_purchase_rate_fixing_confirm", kwargs={"draft_id": draft.pk})
        )
        second = self.client.post(
            reverse("dea_purchase_rate_fixing_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(Voucher.objects.count(), 2)
        self.assertEqual(VoucherLine.objects.count(), 2)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(LedgerTransaction.objects.count(), 1)
        self.assertEqual(AccountTransaction.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 1)
        self.assertEqual(RateFixing.objects.count(), 1)

    def test_purchase_rate_fixing_confirm_endpoint_rejects_member_role(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        exposure = self._create_unfixed_purchase_exposure(deps)
        self.client.post(
            reverse("dea_purchase_rate_fixing_preview"),
            data=self._purchase_rate_fixing_preview_data(deps, exposure),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.PURCHASE_RATE_FIXING,
        )
        member = User.objects.create_user(
            username=f"dea-business-event-member-{uuid.uuid4().hex[:8]}",
            email=f"dea-business-event-member-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=member_role)
        self.client.logout()
        self.client.login(username=member.username, password="testpass123")

        response = self.client.post(
            reverse("dea_purchase_rate_fixing_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 1)
        self.assertEqual(RateFixing.objects.count(), 0)

    def test_sale_rate_fixing_confirm_endpoint_posts_from_previewed_draft(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        exposure = self._create_unfixed_sale_exposure(deps)
        self.client.post(
            reverse("dea_sale_rate_fixing_preview"),
            data=self._sale_rate_fixing_preview_data(deps, exposure),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.SALE_RATE_FIXING,
        )

        response = self.client.post(
            reverse("dea_sale_rate_fixing_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertRedirects(
            response,
            reverse("dea_sale_rate_fixing_detail", kwargs={"draft_id": draft.pk}),
        )
        self.assertEqual(
            self._side_effect_counts(),
            {
                "vouchers": 2,
                "voucher_lines": 2,
                "journal_entries": 1,
                "ledger_transactions": 1,
                "account_transactions": 1,
                "payment_vouchers": 0,
                "commodity_movements": 1,
                "exposures": 1,
                "rate_fixings": 1,
            },
        )
        exposure.refresh_from_db()
        self.assertEqual(str(exposure.open_fine_weight), "50.000")

        detail = self.client.get(
            reverse("dea_sale_rate_fixing_detail", kwargs={"draft_id": draft.pk})
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Sale Rate Fixing Result")
        self.assertContains(detail, "Posted")
        self.assertContains(detail, "Rate fixing")
        self.assertContains(detail, "Voucher")
        self.assertContains(detail, "Journal entry")
        self.assertContains(detail, "Accounting Impact")
        self.assertContains(detail, "Exposure Impact")
        self.assertContains(detail, "PARTIALLY_FIXED")

    def test_sale_rate_fixing_confirm_endpoint_is_idempotent_for_duplicate_submit(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        exposure = self._create_unfixed_sale_exposure(deps)
        self.client.post(
            reverse("dea_sale_rate_fixing_preview"),
            data=self._sale_rate_fixing_preview_data(deps, exposure),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.SALE_RATE_FIXING,
        )

        first = self.client.post(
            reverse("dea_sale_rate_fixing_confirm", kwargs={"draft_id": draft.pk})
        )
        second = self.client.post(
            reverse("dea_sale_rate_fixing_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(Voucher.objects.count(), 2)
        self.assertEqual(VoucherLine.objects.count(), 2)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(LedgerTransaction.objects.count(), 1)
        self.assertEqual(AccountTransaction.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 1)
        self.assertEqual(RateFixing.objects.count(), 1)

    def test_sale_rate_fixing_confirm_endpoint_rejects_member_role(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        exposure = self._create_unfixed_sale_exposure(deps)
        self.client.post(
            reverse("dea_sale_rate_fixing_preview"),
            data=self._sale_rate_fixing_preview_data(deps, exposure),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.SALE_RATE_FIXING,
        )
        member = User.objects.create_user(
            username=f"dea-business-event-member-{uuid.uuid4().hex[:8]}",
            email=f"dea-business-event-member-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=member_role)
        self.client.logout()
        self.client.login(username=member.username, password="testpass123")

        response = self.client.post(
            reverse("dea_sale_rate_fixing_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 1)
        self.assertEqual(RateFixing.objects.count(), 0)

    def test_fixed_sale_confirm_endpoint_posts_from_previewed_draft(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_fixed_sale_preview"),
            data=self._fixed_sale_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.FIXED_SALE,
        )

        response = self.client.post(
            reverse("dea_fixed_sale_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertRedirects(
            response,
            reverse("dea_fixed_sale_detail", kwargs={"draft_id": draft.pk}),
        )
        self.assertEqual(
            self._side_effect_counts(),
            {
                "vouchers": 1,
                "voucher_lines": 2,
                "journal_entries": 1,
                "ledger_transactions": 1,
                "account_transactions": 1,
                "payment_vouchers": 0,
                "commodity_movements": 1,
                "exposures": 0,
                "rate_fixings": 0,
            },
        )

        detail = self.client.get(
            reverse("dea_fixed_sale_detail", kwargs={"draft_id": draft.pk})
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Fixed Sale Result")
        self.assertContains(detail, "Posted")
        self.assertContains(detail, "Voucher")
        self.assertContains(detail, "Journal entry")
        self.assertContains(detail, "Accounting Impact")
        self.assertContains(detail, "Commodity Impact")
        self.assertContains(detail, "SALE_ISSUE")
        self.assertContains(detail, "External customer / delivered out")

    def test_fixed_sale_confirm_endpoint_is_idempotent_for_duplicate_submit(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_fixed_sale_preview"),
            data=self._fixed_sale_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.FIXED_SALE,
        )

        first = self.client.post(
            reverse("dea_fixed_sale_confirm", kwargs={"draft_id": draft.pk})
        )
        second = self.client.post(
            reverse("dea_fixed_sale_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.count(), 2)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(LedgerTransaction.objects.count(), 1)
        self.assertEqual(AccountTransaction.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 0)
        self.assertEqual(RateFixing.objects.count(), 0)

    def test_fixed_sale_confirm_endpoint_rejects_member_role(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_fixed_sale_preview"),
            data=self._fixed_sale_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.FIXED_SALE,
        )
        member = User.objects.create_user(
            username=f"dea-business-event-member-{uuid.uuid4().hex[:8]}",
            email=f"dea-business-event-member-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=member_role)
        self.client.logout()
        self.client.login(username=member.username, password="testpass123")

        response = self.client.post(
            reverse("dea_fixed_sale_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)

    def test_unfixed_sale_confirm_endpoint_posts_from_previewed_draft(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_unfixed_sale_preview"),
            data=self._unfixed_sale_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.UNFIXED_SALE,
        )

        response = self.client.post(
            reverse("dea_unfixed_sale_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertRedirects(
            response,
            reverse("dea_unfixed_sale_detail", kwargs={"draft_id": draft.pk}),
        )
        self.assertEqual(
            self._side_effect_counts(),
            {
                "vouchers": 1,
                "voucher_lines": 0,
                "journal_entries": 0,
                "ledger_transactions": 0,
                "account_transactions": 0,
                "payment_vouchers": 0,
                "commodity_movements": 1,
                "exposures": 1,
                "rate_fixings": 0,
            },
        )

        detail = self.client.get(
            reverse("dea_unfixed_sale_detail", kwargs={"draft_id": draft.pk})
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Unfixed Sale Result")
        self.assertContains(detail, "Posted")
        self.assertContains(detail, "Voucher")
        self.assertContains(detail, "Commodity Impact")
        self.assertContains(detail, "Exposure Impact")
        self.assertContains(detail, "SALE_ISSUE")
        self.assertContains(detail, "UNFIXED")
        self.assertContains(detail, "SALE")

    def test_unfixed_sale_confirm_endpoint_is_idempotent_for_duplicate_submit(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_unfixed_sale_preview"),
            data=self._unfixed_sale_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.UNFIXED_SALE,
        )

        first = self.client.post(
            reverse("dea_unfixed_sale_confirm", kwargs={"draft_id": draft.pk})
        )
        second = self.client.post(
            reverse("dea_unfixed_sale_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)
        self.assertEqual(PaymentVoucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 1)
        self.assertEqual(RateFixing.objects.count(), 0)

    def test_unfixed_sale_confirm_endpoint_rejects_member_role(self):
        deps = self._seed_fixed_purchase_preview_dependencies()
        self.client.post(
            reverse("dea_unfixed_sale_preview"),
            data=self._unfixed_sale_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.UNFIXED_SALE,
        )
        member = User.objects.create_user(
            username=f"dea-business-event-member-{uuid.uuid4().hex[:8]}",
            email=f"dea-business-event-member-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=member_role)
        self.client.logout()
        self.client.login(username=member.username, password="testpass123")

        response = self.client.post(
            reverse("dea_unfixed_sale_confirm", kwargs={"draft_id": draft.pk})
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(ExposureLine.objects.count(), 0)

    def _side_effect_counts(self):
        return {
            "vouchers": Voucher.objects.count(),
            "voucher_lines": VoucherLine.objects.count(),
            "journal_entries": JournalEntry.objects.count(),
            "ledger_transactions": LedgerTransaction.objects.count(),
            "account_transactions": AccountTransaction.objects.count(),
            "payment_vouchers": PaymentVoucher.objects.count(),
            "commodity_movements": CommodityMovement.objects.count(),
            "exposures": ExposureLine.objects.count(),
            "rate_fixings": RateFixing.objects.count(),
        }

    def _seed_fixed_purchase_preview_dependencies(self, *, create_period=True):
        if create_period:
            AccountingPeriod.objects.get_or_create(
                name="FY 2026",
                defaults={
                    "start_date": date(2026, 4, 1),
                    "end_date": date(2027, 3, 31),
                    "status": AccountingPeriod.PeriodStatus.OPEN,
                },
            )
        dr, _ = TransactionType_DE.objects.get_or_create(
            XactTypeCode="Dr",
            defaults={"name": "Debit"},
        )
        cr, _ = TransactionType_DE.objects.get_or_create(
            XactTypeCode="Cr",
            defaults={"name": "Credit"},
        )
        asset_type, _ = AccountType.objects.get_or_create(
            AccountType="Asset",
            defaults={"description": "Asset"},
        )
        liability_type, _ = AccountType.objects.get_or_create(
            AccountType="Liability",
            defaults={"description": "Liability"},
        )
        revenue_type, _ = AccountType.objects.get_or_create(
            AccountType="Revenue",
            defaults={"description": "Revenue"},
        )
        debtor_type, _ = AccountType_Ext.objects.get_or_create(
            XactTypeCode=dr,
            description="Debtor",
        )
        creditor_type, _ = AccountType_Ext.objects.get_or_create(
            XactTypeCode=cr,
            description="Creditor",
        )
        entity, _ = EntityType.objects.get_or_create(name="Organisation")
        person_entity, _ = EntityType.objects.get_or_create(name="Person")
        inventory_ledger, _ = Ledger.objects.get_or_create(
            name="Preview Inventory",
            defaults={"AccountType": asset_type, "code": "PREV_INV"},
        )
        payable_ledger, _ = Ledger.objects.get_or_create(
            name="Preview Payable",
            defaults={"AccountType": liability_type, "code": "PREV_PAY"},
        )
        receivable_ledger, _ = Ledger.objects.get_or_create(
            name="Preview Receivable",
            defaults={"AccountType": asset_type, "code": "PREV_AR"},
        )
        cash_ledger, _ = Ledger.objects.get_or_create(
            name="Preview Cash",
            defaults={"AccountType": asset_type, "code": "PREV_CASH"},
        )
        revenue_ledger, _ = Ledger.objects.get_or_create(
            name="Preview Revenue",
            defaults={"AccountType": revenue_type, "code": "PREV_REV"},
        )
        supplier_customer = Customer.objects.create(
            firstname="Preview",
            lastname="Supplier",
            customer_type=Customer.CustomerType.Supplier,
        )
        customer = Customer.objects.create(
            firstname="Preview",
            lastname="Buyer",
            customer_type=Customer.CustomerType.Retail,
        )
        supplier_account = Account.objects.create(
            contact=supplier_customer,
            entity=entity,
            AccountType_Ext=creditor_type,
        )
        customer_account = Account.objects.create(
            contact=customer,
            entity=person_entity,
            AccountType_Ext=debtor_type,
        )
        commodity = Commodity.objects.create(code="GOLD", name="Gold")
        party = Party.objects.create(display_name="Preview Supplier Party")
        customer_party = Party.objects.create(display_name="Preview Customer Party")
        karigar_party = Party.objects.create(display_name="Preview Karigar")
        supplier_commodity_account = CommodityAccount.objects.create(
            code="PREVIEW_GOLD_SUPPLIER",
            name="Preview gold supplier",
            commodity=commodity,
            purpose=CommodityAccount.Purpose.PARTY_PAYABLE,
            party=party,
        )
        vault = CommodityAccount.objects.create(
            code="PREVIEW_GOLD_VAULT",
            name="Preview gold vault",
            commodity=commodity,
            purpose=CommodityAccount.Purpose.VAULT,
        )
        karigar_custody = CommodityAccount.objects.create(
            code="PREVIEW_GOLD_KARIGAR",
            name="Preview gold karigar custody",
            commodity=commodity,
            purpose=CommodityAccount.Purpose.KARIGAR_CUSTODY,
            party=karigar_party,
        )
        return {
            "supplier_account": supplier_account,
            "customer_account": customer_account,
            "inventory_ledger": inventory_ledger,
            "payable_ledger": payable_ledger,
            "receivable_ledger": receivable_ledger,
            "cash_ledger": cash_ledger,
            "revenue_ledger": revenue_ledger,
            "commodity": commodity,
            "party": party,
            "customer_party": customer_party,
            "karigar_party": karigar_party,
            "supplier_commodity_account": supplier_commodity_account,
            "vault": vault,
            "karigar_custody": karigar_custody,
        }

    def _fixed_purchase_preview_data(self, deps):
        return {
            "action": "preview",
            "source_reference": "SUP-BILL-001",
            "purchase_date": date(2026, 6, 24).isoformat(),
            "supplier_account": str(deps["supplier_account"].pk),
            "inventory_ledger": str(deps["inventory_ledger"].pk),
            "payable_ledger": str(deps["payable_ledger"].pk),
            "commodity": str(deps["commodity"].pk),
            "gross_weight": "100.000",
            "purity": "1.000000",
            "fine_weight": "100.000",
            "from_commodity_account": str(deps["supplier_commodity_account"].pk),
            "to_commodity_account": str(deps["vault"].pk),
            "money_amount": "620000.00",
            "currency": "INR",
            "narration": "Preview fixed purchase",
        }

    def _unfixed_purchase_preview_data(self, deps):
        return {
            "action": "preview",
            "source_reference": "UNFIXED-SUP-BILL-001",
            "purchase_date": date(2026, 6, 24).isoformat(),
            "party": str(deps["party"].pk),
            "commodity": str(deps["commodity"].pk),
            "gross_weight": "100.000",
            "purity": "1.000000",
            "fine_weight": "100.000",
            "from_commodity_account": str(deps["supplier_commodity_account"].pk),
            "to_commodity_account": str(deps["vault"].pk),
            "rate_basis": "Fix at next morning market rate",
            "valuation_currency": "INR",
            "last_valuation_rate": "6200.0000",
            "narration": "Preview unfixed purchase",
        }

    def _purchase_rate_fixing_preview_data(self, deps, exposure):
        return {
            "action": "preview",
            "source_reference": "PRF-001",
            "exposure": str(exposure.pk),
            "fixing_date": date(2026, 6, 24).isoformat(),
            "fine_weight": "50.000",
            "rate": "6200.0000",
            "supplier_account": str(deps["supplier_account"].pk),
            "inventory_ledger": str(deps["inventory_ledger"].pk),
            "payable_ledger": str(deps["payable_ledger"].pk),
            "currency": "INR",
            "narration": "Preview purchase rate fixing",
        }

    def _sale_rate_fixing_preview_data(self, deps, exposure):
        return {
            "action": "preview",
            "source_reference": "SRF-001",
            "exposure": str(exposure.pk),
            "fixing_date": date(2026, 6, 24).isoformat(),
            "fine_weight": "50.000",
            "rate": "7000.0000",
            "customer_account": str(deps["customer_account"].pk),
            "receivable_ledger": str(deps["receivable_ledger"].pk),
            "revenue_ledger": str(deps["revenue_ledger"].pk),
            "currency": "INR",
            "narration": "Preview sale rate fixing",
        }

    def _customer_receipt_preview_data(self, deps):
        return {
            "action": "preview",
            "settlement_type": "CUSTOMER_RECEIPT",
            "source_reference": "SETTLE-REC-001",
            "event_date": date(2026, 6, 24).isoformat(),
            "party_account": str(deps["customer_account"].pk),
            "cash_or_bank_ledger": str(deps["cash_ledger"].pk),
            "counterparty_ledger": str(deps["receivable_ledger"].pk),
            "money_amount": "25000.00",
            "reference_number": "RCPT-001",
            "currency": "INR",
            "payment_method": "CASH",
            "narration": "Preview customer receipt",
        }

    def _supplier_payment_preview_data(self, deps):
        return {
            "action": "preview",
            "settlement_type": "SUPPLIER_PAYMENT",
            "source_reference": "SETTLE-PAY-001",
            "event_date": date(2026, 6, 24).isoformat(),
            "party_account": str(deps["supplier_account"].pk),
            "cash_or_bank_ledger": str(deps["cash_ledger"].pk),
            "counterparty_ledger": str(deps["payable_ledger"].pk),
            "money_amount": "18000.00",
            "reference_number": "PAY-001",
            "currency": "INR",
            "payment_method": "BANK",
            "narration": "Preview supplier payment",
        }

    def _karigar_issue_preview_data(self, deps):
        return {
            "action": "preview",
            "movement_type": "KARIGAR_ISSUE",
            "source_reference": "KARIGAR-ISSUE-001",
            "event_date": date(2026, 6, 24).isoformat(),
            "karigar": str(deps["karigar_party"].pk),
            "commodity": str(deps["commodity"].pk),
            "gross_weight": "25.000",
            "purity": "1.000000",
            "fine_weight": "25.000",
            "from_commodity_account": str(deps["vault"].pk),
            "to_commodity_account": str(deps["karigar_custody"].pk),
            "narration": "Preview karigar issue",
        }

    def _karigar_receipt_preview_data(self, deps):
        return {
            "action": "preview",
            "movement_type": "KARIGAR_RECEIPT",
            "source_reference": "KARIGAR-RECEIPT-001",
            "event_date": date(2026, 6, 24).isoformat(),
            "karigar": str(deps["karigar_party"].pk),
            "commodity": str(deps["commodity"].pk),
            "gross_weight": "20.000",
            "purity": "1.000000",
            "fine_weight": "20.000",
            "from_commodity_account": str(deps["karigar_custody"].pk),
            "to_commodity_account": str(deps["vault"].pk),
            "narration": "Preview karigar receipt",
        }

    def _fixed_sale_preview_data(self, deps):
        return {
            "action": "preview",
            "source_reference": "SALE-BILL-001",
            "sale_date": date(2026, 6, 24).isoformat(),
            "customer_account": str(deps["customer_account"].pk),
            "receivable_ledger": str(deps["receivable_ledger"].pk),
            "revenue_ledger": str(deps["revenue_ledger"].pk),
            "commodity": str(deps["commodity"].pk),
            "gross_weight": "100.000",
            "purity": "1.000000",
            "fine_weight": "100.000",
            "from_commodity_account": str(deps["vault"].pk),
            "money_amount": "700000.00",
            "currency": "INR",
            "narration": "Preview fixed sale",
        }

    def _unfixed_sale_preview_data(self, deps):
        return {
            "action": "preview",
            "source_reference": "UNFIXED-SALE-BILL-001",
            "sale_date": date(2026, 6, 24).isoformat(),
            "party": str(deps["customer_party"].pk),
            "commodity": str(deps["commodity"].pk),
            "gross_weight": "100.000",
            "purity": "1.000000",
            "fine_weight": "100.000",
            "from_commodity_account": str(deps["vault"].pk),
            "rate_basis": "Fix at customer confirmation rate",
            "valuation_currency": "INR",
            "last_valuation_rate": "7000.0000",
            "narration": "Preview unfixed sale",
        }

    def _create_unfixed_purchase_exposure(self, deps):
        self.client.post(
            reverse("dea_unfixed_purchase_preview"),
            data=self._unfixed_purchase_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.UNFIXED_PURCHASE,
        )
        self.client.post(
            reverse("dea_unfixed_purchase_confirm", kwargs={"draft_id": draft.pk})
        )
        return ExposureLine.objects.get()

    def _create_unfixed_sale_exposure(self, deps):
        self.client.post(
            reverse("dea_unfixed_sale_preview"),
            data=self._unfixed_sale_preview_data(deps),
        )
        draft = BusinessEventDraft.objects.get(
            event_type=BusinessEventDraft.EventType.UNFIXED_SALE,
        )
        self.client.post(
            reverse("dea_unfixed_sale_confirm", kwargs={"draft_id": draft.pk})
        )
        return ExposureLine.objects.get()
