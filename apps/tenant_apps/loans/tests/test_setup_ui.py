import uuid
import io
import json
import fitz
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone
from apps.tenancy.testing import WorkspaceClient, WorkspaceTestCase

from apps.tenant_apps.loans.access import assert_loans_setup_access
from apps.tenant_apps.loans.domain import CollateralCustodyState, CollateralMetal, LoanDocumentKind
from apps.tenant_apps.loans.domain.future_funding import FundingLoanState
from apps.tenant_apps.loans.models import (
    FundingLoan,
    FundingLoanCancellation,
    FundingLoanDraftCollateral,
    FundingLoanDraftTerms,
    FundingLoanSequence,
    LoanChangeLog,
    LoanLicense,
    LoanLicenseRevision,
    LoanMonitoringPolicy,
    LoanDocumentIssue,
    LoanDocumentLayout,
    LoanDocumentLayoutRevision,
    LoanDocumentPrintProfile,
    LoanDocumentPrintProfileRevision,
    LoanNumberSequence,
    LoanProduct,
    LoanProductVersion,
    LoanSeries,
    PawnLoan,
    PawnCollateralItem,
    PawnLoanApprovalSnapshot,
    PawnLoanEconomicPolicy,
    PawnLoanNotice,
    PawnMetalInterestRatePolicy,
    PawnPhysicalVerificationSession,
    PawnStorageLocation,
)
from apps.tenant_apps.loans.views import _license_for_workspace
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.tests.factories import ensure_test_product_version
from apps.orgs.models import Membership, Role
from PIL import Image as PillowImage
from apps.tenant_apps.loans.documents import built_in_print_profile, starter_layout
from apps.tenant_apps.loans.services import (
    LoanDocumentLayoutService,
    LoanDocumentPrintProfileService,
)


@override_settings(
    ROOT_URLCONF="django_project.workspace_urls",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
)
class LoansSetupUiTests(WorkspaceTestCase):
    test_schema_name = f"loans_setup_{uuid.uuid4().hex[:8]}"
    test_domain = f"loans-setup-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        User = get_user_model()
        owner, _ = User.objects.get_or_create(
            username="loans-setup-owner",
            defaults={"email": "loans-setup-owner@example.com"},
        )
        tenant.name = f"Loans Setup {uuid.uuid4().hex[:8]}"
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
        static_url = patch(
            "django.templatetags.static.StaticNode.handle_simple",
            side_effect=lambda path: f"/static/{path}",
        )
        static_url.start()
        self.addCleanup(static_url.stop)
        self.owner = self.tenant.owner
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.owner)

    def tenant_get(self, url):
        return self.client.workspace_get(url)

    def tenant_post(self, url, data=None):
        return self.client.workspace_post(url, data or {})

    def test_checklist_distinguishes_numbering_from_missing_economics(self):
        license, series = self._configured_setup()
        page = self.tenant_get(reverse("loans:license_list"))
        checks = {step["key"]: step["complete"] for step in page.context["loan_setup"]["steps"]}
        self.assertEqual(checks, {"license": True, "series": True, "economics": False, "product": False, "metal_rates": False})
        self.assertContains(page, "Open Economic Setup")
        self.assertEqual(page.context["next_setup_step"]["key"], "economics")
        self.assertContains(page, "Next setup step")
        self.assertNotContains(page, "Metal buying rates")
        LoanLicense.objects.filter(pk=license.pk).update(issued_on=date(2019, 1, 1), expires_on=date(2020, 1, 1))
        expired = self.tenant_get(reverse("loans:license_list"))
        checks = {step["key"]: step["complete"] for step in expired.context["loan_setup"]["steps"]}
        self.assertFalse(checks["license"])
        self.assertFalse(checks["series"])
        self.assertFalse(expired.context["loan_setup"]["ready"])
        self.assertEqual(expired.context["next_setup_step"]["key"], "license")

    def test_empty_setup_posts_show_linked_errors_without_changes(self):
        license, series = self._configured_setup()
        before_sequences = list(LoanNumberSequence.objects.order_by("pk").values())
        before_revisions = LoanLicenseRevision.objects.count()
        for name, args, field in (
            ("license_create", [], "license_number"),
            ("license_update", [license.pk], "license_number"),
            ("license_renew", [license.pk], "supporting_document"),
            ("series_create", [license.pk], "name"),
            ("series_update", [series.pk], "name"),
        ):
            with self.subTest(name=name):
                response = self.tenant_post(reverse("loans:" + name, args=args), {})
                self.assertContains(response, 'id="form-errors"')
                self.assertTrue(response.context["form"].is_bound)
                self.assertContains(response, f'href="#id_{field}"')
                self.assertContains(response, 'hx-history="false"')
                self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(before_sequences, list(LoanNumberSequence.objects.order_by("pk").values()))
        self.assertEqual(before_revisions, LoanLicenseRevision.objects.count())

    def test_series_service_errors_preserve_input_and_rollback_both_counters(self):
        license, series = self._configured_setup()
        sequence = series.number_sequences.get(document_kind=LoanDocumentKind.PAWN_LOAN_RELEASE.value)
        sequence.next_number = 20
        sequence.save(update_fields=["next_number"])
        before = list(series.number_sequences.order_by("pk").values())
        old_name = series.name
        response = self.tenant_post(reverse("loans:series_update", args=[series.pk]), {
            "name": "Keep this correction", "code": series.code, "is_active": "on",
            "pawn_loan_prefix": "NEW-", "release_prefix": "RETURN-", "number_width": 5,
            "maximum_number": 5,
        })
        self.assertContains(response, 'id="form-errors"')
        self.assertContains(response, "Keep this correction")
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertEqual(before, list(series.number_sequences.order_by("pk").values()))
        series.refresh_from_db()
        self.assertEqual(series.name, old_name)

    def test_setup_forms_hindi_labels_and_document_reselection(self):
        self.client.cookies["django_language"] = "hi"
        response = self.tenant_post(reverse("loans:license_create"), {"name": "Retained name"})
        self.assertContains(response, "Retained name")
        self.assertContains(response, "लाइसेंस विवरण")
        self.assertContains(response, "सहायक दस्तावेज़")
        self.assertContains(response, 'id="id_supporting_document_helptext"')
        self.assertContains(response, 'aria-invalid="true"')

    def test_owner_can_seed_review_activate_and_retire_loan_products(self):
        response = self.tenant_post(reverse("loans:loan_product_seed_defaults"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(LoanProduct.objects.filter(workspace=self.tenant).count(), 4)
        version = LoanProductVersion.objects.get(product__workspace=self.tenant, product__code="GOLD-BULLET")
        page = self.tenant_get(reverse("loans:loan_product_list"))
        self.assertContains(page, "Single-payment bullet")
        self.assertContains(page, "Operational only; DPD date unchanged")
        self.assertContains(page, "Choose your lending products")
        self.assertContains(page, "Enable for new loans", count=4)
        self.assertNotContains(page, "Seed four standard products")
        self.assertNotContains(page, "Catalog active")
        self.assertNotContains(page, 'action="' + reverse("workspace_loans:loan_product_seed_defaults", args=[self.tenant.slug]) + '"')

        response = self.tenant_post(reverse("loans:loan_product_version_activate", args=[version.pk]))
        self.assertEqual(response.status_code, 302)
        version.refresh_from_db()
        self.assertEqual(version.status, "ACTIVE")

        response = self.tenant_post(reverse("loans:loan_product_version_retire", args=[version.pk]))
        self.assertEqual(response.status_code, 302)
        version.refresh_from_db()
        self.assertEqual(version.status, "RETIRED")

    @patch("apps.tenant_apps.loans.web.risk_refresh.refresh_loan_risk_snapshot")
    def test_owner_can_refresh_one_risk_snapshot_with_htmx_redirect(self, refresh):
        license, series = self._configured_setup()
        loan = self._loan(license, series, "PL-RISK-00001", state="ACTIVE")

        response = self.client.post(
            reverse("loans:pawn_risk_refresh_one", args=[loan.pk]),
            {"as_of": "2026-08-13"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Redirect"], reverse("workspace_loans:pawn_risk_portfolio", kwargs={"workspace_slug": self.tenant.slug}))
        refresh.assert_called_once_with(loan.pk, as_of_date=date(2026, 8, 13))

    @patch("apps.tenant_apps.loans.web.risk_refresh.reassess_pawn_loans_batch")
    def test_owner_can_refresh_bounded_due_risk_batch(self, reassess):
        reassess.return_value = {"selected": 2, "current": 2, "errors": []}

        response = self.tenant_post(
            reverse("loans:pawn_risk_refresh_batch"),
            {"as_of": "2026-08-13"},
        )

        self.assertRedirects(
            response,
            reverse("workspace_loans:pawn_risk_portfolio", kwargs={"workspace_slug": self.tenant.slug}),
            fetch_redirect_response=False,
        )
        reassess.assert_called_once_with(
            workspace_id=self.tenant.pk,
            as_of_date=date(2026, 8, 13),
            batch_size=50,
        )

    @patch("apps.tenant_apps.loans.web.risk_refresh.reassess_pawn_loans_batch")
    def test_owner_batch_risk_refresh_uses_htmx_redirect_response(self, reassess):
        reassess.return_value = {"selected": 1, "current": 1, "errors": []}

        response = self.client.post(
            reverse("loans:pawn_risk_refresh_batch"),
            {"as_of": "2026-08-13"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            response["HX-Redirect"],
            reverse("workspace_loans:pawn_risk_portfolio", kwargs={"workspace_slug": self.tenant.slug}),
        )

    @patch("apps.tenant_apps.loans.web.risk_refresh.reassess_pawn_loans_batch")
    def test_member_cannot_refresh_risk_monitoring(self, reassess):
        User = get_user_model()
        member = User.objects.create_user(
            username=f"risk-member-{uuid.uuid4().hex[:8]}",
            email=f"risk-member-{uuid.uuid4().hex[:8]}@example.com",
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(
            user=member,
            company=self.tenant,
            role=member_role,
        )
        member_client = WorkspaceClient(self.tenant)
        member_client.force_login(member)

        response = member_client.post(
            reverse("loans:pawn_risk_refresh_batch"),
            {"as_of": "2026-08-13"},
        )

        self.assertEqual(response.status_code, 403)
        reassess.assert_not_called()

    def test_document_issue_list_filters_and_paginates_immutable_evidence(self):
        def create_issue(sequence, **overrides):
            values = {
                "workspace": self.tenant,
                "document_type": "repayment_receipt",
                "issue_kind": LoanDocumentIssue.Kind.OFFICIAL,
                "source_type": "PawnLoanRepayment",
                "source_id": f"SOURCE-{sequence}",
                "source_fingerprint": f"fingerprint-{sequence}",
                "fixed_renderer_version": "test-v1",
                "payload_schema_version": 1,
                "payload_hash": f"payload-{sequence}",
                "pdf_hash": f"pdf-{sequence}",
                "artifact": SimpleUploadedFile(
                    f"issue-{sequence}.pdf",
                    b"%PDF-1.4 test evidence",
                    content_type="application/pdf",
                ),
                "issued_by": self.owner,
            }
            values.update(overrides)
            return LoanDocumentIssue.objects.create(**values)

        for sequence in range(51):
            create_issue(sequence)

        prior_issue = create_issue(
            "special-original",
            document_type="loan_ticket",
            source_type="PawnLoan",
            source_id="SPECIAL-LOAN",
        )
        special_issue = create_issue(
            "special-regenerated",
            document_type="loan_ticket",
            issue_kind=LoanDocumentIssue.Kind.REGENERATED,
            source_type="PawnLoan",
            source_id="SPECIAL-LOAN",
            prior_issue=prior_issue,
            print_profile_name="Special Profile",
            print_profile_version=1,
            print_profile_hash="profile-special",
            print_profile_source_scope=LoanDocumentIssue.PrintProfileSource.BUILT_IN,
        )
        issued_at = timezone.now() - timedelta(days=2)
        LoanDocumentIssue.objects.filter(pk=special_issue.pk).update(
            issued_at=issued_at
        )

        first_page = self.tenant_get(reverse("loans:document_issue_list"))
        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.context["page_obj"].paginator.count, 53)
        self.assertEqual(len(first_page.context["issues"]), 50)

        receipt_page = self.client.get(
            reverse("loans:document_issue_list"),
            {"document_type": "repayment_receipt"},
        )
        self.assertEqual(receipt_page.context["page_obj"].paginator.count, 51)
        self.assertContains(
            receipt_page,
            "?document_type=repayment_receipt&amp;page=2",
        )
        receipt_page_two = self.client.get(
            reverse("loans:document_issue_list"),
            {"document_type": "repayment_receipt", "page": 2},
        )
        self.assertEqual(len(receipt_page_two.context["issues"]), 1)

        filtered = self.client.get(
            reverse("loans:document_issue_list"),
            {
                "q": "Special Profile",
                "document_type": "loan_ticket",
                "issue_kind": LoanDocumentIssue.Kind.REGENERATED,
                "profile_scope": LoanDocumentIssue.PrintProfileSource.BUILT_IN,
                "issued_date_from": timezone.localdate(issued_at).isoformat(),
                "issued_date_to": timezone.localdate(issued_at).isoformat(),
            },
        )
        self.assertEqual(list(filtered.context["issues"]), [special_issue])
        self.assertContains(filtered, "SPECIAL-LOAN")
        self.assertContains(filtered, "Built-in fallback")

        historical = self.client.get(
            reverse("loans:document_issue_list"),
            {"profile_scope": "NOT_RECORDED"},
        )
        self.assertEqual(historical.context["page_obj"].paginator.count, 52)

    def test_storage_and_verification_worklists_filter_hierarchy_and_paginate(self):
        branches = [
            PawnStorageLocation.objects.create(
                workspace=self.tenant,
                level=PawnStorageLocation.Level.BRANCH,
                code=f"BR-{sequence:03d}",
                name=f"Branch {sequence}",
                created_by=self.owner,
            )
            for sequence in range(51)
        ]
        special_branch = PawnStorageLocation.objects.create(
            workspace=self.tenant,
            level=PawnStorageLocation.Level.BRANCH,
            code="SPECIAL-BRANCH",
            name="Special Branch",
            created_by=self.owner,
        )
        special_vault = PawnStorageLocation.objects.create(
            workspace=self.tenant,
            parent=special_branch,
            level=PawnStorageLocation.Level.VAULT,
            code="SPECIAL-VAULT",
            name="Special Vault",
            created_by=self.owner,
        )
        special_cabinet = PawnStorageLocation.objects.create(
            workspace=self.tenant,
            parent=special_vault,
            level=PawnStorageLocation.Level.CABINET,
            code="SPECIAL-CABINET",
            name="Special Cabinet",
            created_by=self.owner,
        )
        special_box = PawnStorageLocation.objects.create(
            workspace=self.tenant,
            parent=special_cabinet,
            level=PawnStorageLocation.Level.BOX,
            code="SPECIAL-BOX",
            name="Special Box",
            created_by=self.owner,
        )
        special_slot = PawnStorageLocation.objects.create(
            workspace=self.tenant,
            parent=special_box,
            level=PawnStorageLocation.Level.SLOT,
            code="SPECIAL-SLOT",
            name="Special Slot",
            is_active=False,
            created_by=self.owner,
        )

        branch_page = self.client.get(
            reverse("loans:pawn_storage_location_list"),
            {"level": PawnStorageLocation.Level.BRANCH},
        )
        self.assertEqual(branch_page.context["page_obj"].paginator.count, 52)
        self.assertEqual(len(branch_page.context["locations"]), 50)
        self.assertContains(branch_page, "?level=BRANCH&amp;page=2")

        storage_filtered = self.client.get(
            reverse("loans:pawn_storage_location_list"),
            {
                "q": "Special Branch",
                "within": special_branch.pk,
                "level": PawnStorageLocation.Level.SLOT,
                "status": "INACTIVE",
            },
        )
        self.assertEqual(list(storage_filtered.context["locations"]), [special_slot])
        self.assertContains(storage_filtered, "SPECIAL-SLOT")

        for branch in branches:
            PawnPhysicalVerificationSession.objects.create(
                workspace=self.tenant,
                scope_location=branch,
                started_by=self.owner,
            )
        special_session = PawnPhysicalVerificationSession.objects.create(
            workspace=self.tenant,
            scope_location=special_slot,
            status=PawnPhysicalVerificationSession.Status.COMPLETED,
            started_by=self.owner,
            completed_by=self.owner,
            completed_at=timezone.now(),
        )
        started_date = timezone.localdate()

        open_sessions = self.client.get(
            reverse("loans:pawn_physical_verification_list"),
            {"status": PawnPhysicalVerificationSession.Status.OPEN},
        )
        self.assertEqual(open_sessions.context["page_obj"].paginator.count, 51)
        self.assertEqual(len(open_sessions.context["sessions"]), 50)
        self.assertContains(open_sessions, "?status=OPEN&amp;page=2")

        verification_filtered = self.client.get(
            reverse("loans:pawn_physical_verification_list"),
            {
                "q": "Special Branch",
                "within": special_branch.pk,
                "status": PawnPhysicalVerificationSession.Status.COMPLETED,
                "started_date_from": started_date.isoformat(),
                "started_date_to": started_date.isoformat(),
            },
        )
        self.assertEqual(
            list(verification_filtered.context["sessions"]),
            [special_session],
        )
        self.assertContains(verification_filtered, "SPECIAL-SLOT")

    def test_owner_can_complete_license_and_series_setup_without_admin(self):
        response = self.tenant_post(
            reverse("loans:license_create"),
            {
                "name": "Primary Pawn License",
                "license_number": "PBL-UI-1",
                "issuing_authority": "State Authority",
                "issued_on": "2026-01-01",
                "expires_on": "2027-01-01",
                "notes": "",
                "supporting_document": SimpleUploadedFile(
                    "license.pdf",
                    b"%PDF-1.4\n%%EOF",
                    content_type="application/pdf",
                ),
            },
        )
        license = LoanLicense.objects.get(license_number="PBL-UI-1")
        self.assertRedirects(
            response,
            reverse("loans:license_detail", args=[license.pk]),
            fetch_redirect_response=False,
        )

        response = self.tenant_post(
            reverse("loans:series_create", args=[license.pk]),
            {
                "name": "Main Counter",
                "code": "A",
                "is_active": "on",
                "pawn_loan_prefix": "PL-A-",
                "release_prefix": "RL-A-",
                "number_width": 5,
                "maximum_number": 10000,
            },
        )

        self.assertEqual(response.status_code, 302)
        series = LoanSeries.objects.get(license=license, code="A")
        self.assertEqual(series.number_sequences.count(), 2)
        detail = self.tenant_get(reverse("loans:license_detail", args=[license.pk]))
        self.assertContains(detail, "PL-A-00001")
        self.assertContains(detail, "RL-A-00001")
        self.assertContains(detail, "Ready")
        self.assertContains(detail, "Loans Setup")

    def test_direct_series_forms_preserve_counters_and_permissions(self):
        from django.urls import resolve
        license, _ = self._configured_setup()
        create = reverse("workspace_loans:series_create", kwargs={
            "workspace_slug": self.tenant.slug, "license_pk": license.pk,
        })
        detail = reverse("workspace_loans:license_detail", kwargs={
            "workspace_slug": self.tenant.slug, "pk": license.pk,
        })
        self.assertEqual(resolve(create).namespace, "workspace_loans")
        self.assertContains(self.client.get(create), f'action="{create}"')
        payload = {"name": "HTTP series", "code": "HTTP", "is_active": "on",
                   "pawn_loan_prefix": "PL-H-", "release_prefix": "RL-H-",
                   "number_width": 5, "maximum_number": 10000}
        invalid = self.client.post(create, {**payload, "number_width": 0})
        self.assertIn("number_width", invalid.context["form"].errors)
        self.assertFalse(LoanSeries.objects.filter(license=license, code="HTTP").exists())
        self.assertRedirects(self.client.post(create, payload), detail, fetch_redirect_response=False)
        series = LoanSeries.objects.get(license=license, code="HTTP")
        edit = reverse("workspace_loans:series_update", kwargs={
            "workspace_slug": self.tenant.slug, "pk": series.pk,
        })
        self.assertEqual(resolve(edit).namespace, "workspace_loans")
        sequence = series.number_sequences.get(document_kind=LoanDocumentKind.PAWN_LOAN.value)
        sequence.next_number = 7
        sequence.save(update_fields=["next_number"])
        page = self.client.get(edit)
        self.assertContains(page, f'action="{edit}"')
        self.assertEqual(page.context["form"]["pawn_loan_prefix"].value(), "PL-H-")
        self.assertNotContains(page, 'href="/loans/')
        self.assertRedirects(self.client.post(edit, {**payload, "name": "Renamed series"}), detail,
                             fetch_redirect_response=False)
        sequence.refresh_from_db()
        series.refresh_from_db()
        self.assertEqual(series.name, "Renamed series")
        self.assertEqual(sequence.next_number, 7)
        self.assertEqual(series.number_sequences.count(), 2)
        self.assertEqual(series.number_sequences.get(document_kind=LoanDocumentKind.PAWN_LOAN_RELEASE.value).next_number, 1)
        self.client.handler.enforce_csrf_checks = True
        self.assertEqual(self.client.post(edit, payload).status_code, 403)
        self.client.handler.enforce_csrf_checks = False
        viewer = get_user_model().objects.create_user(username="series-route-viewer")
        role, _ = Role.objects.get_or_create(name="Viewer")
        Membership.objects.create(user=viewer, company=self.tenant, role=role)
        self.client.force_login(viewer)
        for target in (create, edit):
            self.assertEqual(self.client.get(target).status_code, 403)
            self.assertEqual(self.client.post(target, payload).status_code, 403)

    def test_detail_preview_does_not_consume_a_number(self):
        license, series = self._configured_setup()
        sequence = LoanNumberSequence.objects.get(
            series=series, document_kind=LoanDocumentKind.PAWN_LOAN.value
        )

        self.tenant_get(reverse("loans:license_detail", args=[license.pk]))
        self.tenant_get(reverse("loans:license_detail", args=[license.pk]))

        sequence.refresh_from_db()
        self.assertEqual(sequence.next_number, 1)

    def test_owner_can_add_workspace_economic_configuration(self):
        response = self.tenant_post(
            reverse("loans:pawn_economics_setup"),
            {
                "action": "configuration",
                "configuration-license": "",
                "configuration-valuation_method": "LATEST_APPRAISAL",
                "configuration-maximum_ltv_ratio": "0.80",
                "configuration-advance_interest_periods": "1",
                "configuration-interest_method": "COMPOUND",
                "configuration-partial_month_method": "SLAB",
                "configuration-partial_month_cutoff_days": "15",
                "configuration-partial_month_lower_fraction": "0.5",
                "configuration-capitalization_interval_periods": "12",
                "configuration-rounding_method": "PER_ACCRUAL_PERIOD",
                "configuration-currency_quantum": "0.01",
                "configuration-gold_monthly_interest_rate": "2",
                "configuration-silver_monthly_interest_rate": "4",
                "configuration-effective_from": "2026-08-05",
            },
        )

        self.assertRedirects(
            response,
            reverse("loans:pawn_economics_setup"),
            fetch_redirect_response=False,
        )
        policy = PawnLoanEconomicPolicy.objects.get()
        self.assertEqual(policy.interest_method, "COMPOUND")
        self.assertEqual(policy.partial_month_method, "SLAB")
        self.assertEqual(PawnMetalInterestRatePolicy.objects.count(), 2)
        page = self.tenant_get(reverse("loans:pawn_economics_setup"))
        self.assertContains(page, "Calculation, fees and monitoring")
        self.assertContains(page, "Gold")
        self.assertContains(page, "Silver")
        self.assertContains(page, "Compound")
        self.assertContains(page, "Slab")

    def test_policy_forms_keep_one_error_summary_and_open_the_failed_section(self):
        import re
        for action in ("configuration", "fee", "monitoring"):
            with self.subTest(action=action):
                page = self.tenant_post(reverse("loans:pawn_economics_setup"), {"action": action})
                self.assertEqual(page.status_code, 200)
                html = page.content.decode()
                self.assertEqual(html.count('id="form-errors"'), 1)
                section = "calculation" if action == "configuration" else action
                self.assertRegex(html, rf'<details[^>]* id="{section}-policy"[^>]*\bopen')
                for target in re.findall(r'href="#(id_[^"]+)"', html):
                    self.assertIn(f'id="{target}"', html)
                self.assertIn("no-store", page["Cache-Control"])
        self.assertFalse(PawnLoanEconomicPolicy.objects.exists())
        self.assertFalse(LoanMonitoringPolicy.objects.exists())
        self.assertContains(self.tenant_post(reverse("loans:pawn_economics_setup")), "Choose which policy to save")

    def test_policy_forms_render_hindi_labels_and_linked_fields(self):
        self.client.cookies["django_language"] = "hi"
        page = self.tenant_get(reverse("loans:pawn_economics_setup"))
        self.assertContains(page, "गणना, शुल्क और निगरानी")
        self.assertContains(page, "सोना: मासिक ब्याज (%)")
        self.assertContains(page, "नीति का लागू क्षेत्र")
        self.assertContains(page, "शुल्क नीति सहेजें")
        self.assertContains(page, "गिरवी का जोखिम और साक्ष्य की उम्र")
        self.assertContains(page, "प्रारंभिक मासिक दरें")
        self.assertContains(page, f'value="{timezone.localdate().isoformat()}"')

    def test_legacy_verification_page_is_explicit_scoped_and_does_not_activate_on_get(self):
        from apps.tenant_apps.loans.services.license_series import create_legacy_license_reference
        legacy = create_legacy_license_reference(workspace=self.tenant, actor=self.owner,
            name="Old license", source_label="813/94", evidence_reference="Source review")
        url = reverse("workspace_loans:license_verify", kwargs={"workspace_slug": self.tenant.slug, "pk": legacy.pk})
        page = self.client.get(url)
        self.assertContains(page, "Verify and enable new lending")
        self.assertContains(page, "final import and numbering review")
        self.assertIn("no-store", page["Cache-Control"])
        invalid = self.client.post(url, {})
        self.assertContains(invalid, 'href="#id_supporting_document"')
        self.assertContains(invalid, 'href="#id_confirmed_complete"')
        legacy.refresh_from_db()
        self.assertFalse(legacy.is_active)
        self.assertEqual(legacy.revisions.count(), 1)
        stranger = get_user_model().objects.create_user(username="verification-outsider")
        self.client.force_login(stranger)
        self.assertIn(self.client.get(url).status_code, (302, 403, 404))

    def test_complete_verification_form_retains_series_and_records_evidence(self):
        import tempfile
        from apps.tenant_apps.loans.services.license_series import create_legacy_license_reference, create_configured_series
        legacy = create_legacy_license_reference(workspace=self.tenant, actor=self.owner,
            name="Old license", source_label="813/94", evidence_reference="Source review")
        series = create_configured_series(license=legacy, name="C", code="C", is_active=True,
            pawn_loan_prefix="C", release_prefix="CR", number_width=5, maximum_number=10000, actor=self.owner)
        url = reverse("workspace_loans:license_verify", kwargs={"workspace_slug": self.tenant.slug, "pk": legacy.pk})
        page = self.client.get(url)
        form = page.context["form"]
        today = timezone.localdate()
        data = {**form.initial, "issued_on": (today - timedelta(days=10)).isoformat(),
            "expires_on": (today + timedelta(days=365)).isoformat(), "issuing_authority": "Test authority",
            "source_sha256": "a" * 64, "source_as_of": today.isoformat(),
            "source_reference": "Final test report", "confirmed_complete": "on",
            "supporting_document": SimpleUploadedFile("test.pdf", b"%PDF-1.4\nfixture")}
        data.update({name: "100" for name, pk in form.counter_names})
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            result = self.client.post(url, data)
            self.assertEqual(result.status_code, 302)
            legacy.refresh_from_db()
            self.assertTrue(legacy.is_active)
            self.assertFalse(legacy.is_legacy_reference)
            self.assertEqual(legacy.revisions.latest("revision_number").kind, "VERIFICATION")
            self.assertEqual(list(series.number_sequences.values_list("next_number", flat=True)), [101, 101])

    def test_owner_can_add_workspace_monitoring_policy(self):
        response = self.tenant_post(
            reverse("loans:pawn_economics_setup"),
            {
                "action": "monitoring",
                "monitoring-license": "",
                "monitoring-effective_from": "2026-08-01",
                "monitoring-compliance_profile": "Owner-approved pilot",
                "monitoring-maturity_warning_days": "30",
                "monitoring-operational_grace_days": "3",
                "monitoring-dpd_watch_threshold": "1",
                "monitoring-dpd_substandard_threshold": "90",
                "monitoring-ltv_warning_ratio": "0.70",
                "monitoring-ltv_breach_ratio": "0.80",
                "monitoring-ltv_critical_ratio": "0.90",
                "monitoring-rate_freshness_days": "7",
                "monitoring-appraisal_freshness_days": "90",
            },
        )

        self.assertRedirects(
            response,
            reverse("loans:pawn_economics_setup"),
            fetch_redirect_response=False,
        )
        policy = LoanMonitoringPolicy.objects.get()
        self.assertEqual(policy.version, 1)
        self.assertEqual(policy.compliance_profile, "Owner-approved pilot")
        page = self.tenant_get(reverse("loans:pawn_economics_setup"))
        self.assertContains(page, "Owner-approved pilot")

    def test_direct_license_routes_keep_scope_forms_and_permissions(self):
        from django.urls import resolve
        license, _ = self._configured_setup()
        def url(action, **kwargs):
            return reverse(f"workspace_loans:license_{action}", kwargs={
                "workspace_slug": self.tenant.slug, **kwargs,
            })
        listing, create = url("list"), url("create")
        detail = url("detail", pk=license.pk)
        edit = url("update", pk=license.pk)
        renew = url("renew", pk=license.pk)
        for target in (listing, create, detail, edit, renew):
            self.assertEqual(resolve(target).namespace, "workspace_loans")
            page = self.client.get(target)
            self.assertEqual(page.status_code, 200)
            self.assertNotContains(page, 'href="/loans/')
            if target in (create, edit, renew):
                self.assertContains(page, f'action="{target}"')
        invalid = self.client.post(create, {"name": "Incomplete license"})
        self.assertTrue(invalid.context["form"].errors)
        self.assertFalse(LoanLicense.objects.filter(name="Incomplete license").exists())
        self.assertContains(self.client.get(edit), 'name="business_name"')
        self.assertContains(self.client.get(edit), 'name="business_address"')
        response = self.client.post(edit, {
            "name": license.name, "license_number": license.license_number,
            "issued_on": "2026-01-01", "expires_on": "2027-01-01",
            "business_name": "Printed Counter Business", "business_address": "12 Business Road\nVellore",
        })
        self.assertRedirects(response, detail, fetch_redirect_response=False)
        license.refresh_from_db()
        self.assertEqual(license.business_name, "Printed Counter Business")
        self.assertEqual(license.revisions.latest("revision_number").business_address, "12 Business Road\nVellore")
        self.assertContains(self.client.get(detail), "Printed Counter Business")
        for action in ("expire", "activate", "expiry_notice_create"):
            target = url(action, pk=license.pk)
            self.assertEqual(self.client.get(target).status_code, 405)
        expire = url("expire", pk=license.pk)
        self.client.handler.enforce_csrf_checks = True
        self.assertEqual(self.client.post(expire).status_code, 403)
        self.client.handler.enforce_csrf_checks = False
        self.assertRedirects(self.client.post(expire), detail, fetch_redirect_response=False)
        license.refresh_from_db()
        self.assertFalse(license.is_active)
        self.assertRedirects(self.client.post(url("activate", pk=license.pk)), detail, fetch_redirect_response=False)
        license.refresh_from_db()
        self.assertTrue(license.is_active)
        with patch("apps.tenant_apps.loans.web.license_setup.create_license_expiry_notice") as alert:
            self.assertRedirects(self.client.post(url("expiry_notice_create", pk=license.pk)), detail,
                                 fetch_redirect_response=False)
            self.assertEqual(alert.call_args.args, (license.pk,))
            self.assertEqual(alert.call_args.kwargs["actor"], self.owner)
        viewer = get_user_model().objects.create_user(username="license-route-viewer")
        role, _ = Role.objects.get_or_create(name="Viewer")
        Membership.objects.create(user=viewer, company=self.tenant, role=role)
        self.client.force_login(viewer)
        for target in (listing, create, detail, edit, renew, url("register_pdf")):
            self.assertEqual(self.client.get(target).status_code, 403)
        self.assertEqual(self.client.post(expire).status_code, 403)

    def test_expiry_is_post_only_and_blocks_readiness_without_deleting_license(self):
        license, _ = self._configured_setup()
        expire_url = reverse("loans:license_expire", args=[license.pk])

        self.assertEqual(self.tenant_get(expire_url).status_code, 405)
        response = self.tenant_post(expire_url)

        self.assertEqual(response.status_code, 302)
        license.refresh_from_db()
        self.assertFalse(license.is_active)
        detail = self.tenant_get(reverse("loans:license_detail", args=[license.pk]))
        self.assertContains(detail, "new drafts blocked")

    def test_owner_can_record_and_download_license_renewal_evidence(self):
        license, _ = self._configured_setup()
        response = self.tenant_post(
            reverse("loans:license_renew", args=[license.pk]),
            {
                "license_number": license.license_number,
                "issuing_authority": "Renewal Authority",
                "issued_on": "2027-01-02",
                "expires_on": "2028-01-01",
                "notes": "Renewed for pilot",
                "supporting_document": SimpleUploadedFile(
                    "renewal.pdf",
                    b"%PDF-1.4\n%%EOF",
                    content_type="application/pdf",
                ),
            },
        )

        self.assertRedirects(
            response,
            reverse("loans:license_detail", args=[license.pk]),
            fetch_redirect_response=False,
        )
        revision = license.revisions.get(kind=LoanLicenseRevision.Kind.RENEWAL)
        download = self.tenant_get(
            reverse(
                "loans:license_revision_document",
                args=[license.pk, revision.pk],
            )
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download["X-Content-Type-Options"], "nosniff")
        self.assertEqual(download.content, b"%PDF-1.4\n%%EOF")

        register = self.tenant_get(reverse("loans:license_register_pdf"))
        self.assertEqual(register.status_code, 200)
        self.assertTrue(register.content.startswith(b"%PDF-"))

    def test_exhausted_sequence_is_visible_and_not_ready(self):
        license, series = self._configured_setup()
        sequence = LoanNumberSequence.objects.get(
            series=series, document_kind=LoanDocumentKind.PAWN_LOAN.value
        )
        sequence.next_number = sequence.maximum_number + 1
        sequence.save(update_fields=["next_number"])

        detail = self.tenant_get(reverse("loans:license_detail", args=[license.pk]))

        self.assertContains(detail, "sequence is exhausted")
        self.assertContains(detail, "Not ready")

    def test_non_member_is_denied_setup_access(self):
        user = get_user_model().objects.create_user(
            username=f"setup-outsider-{uuid.uuid4().hex[:8]}",
            email=f"setup-outsider-{uuid.uuid4().hex[:8]}@example.com",
        )
        request = RequestFactory().get("/loans/setup/")
        request.user = user
        request.workspace = self.tenant

        with self.assertRaises(PermissionDenied):
            assert_loans_setup_access(request)

    def test_workspace_filtered_lookup_fails_closed(self):
        request = RequestFactory().get("/loans/setup/licenses/999/")
        request.loans_workspace = self.tenant
        with patch(
            "apps.tenant_apps.loans.web.license_setup.get_object_or_404"
        ) as get_object_or_404:
            _license_for_workspace(request, 999)

        get_object_or_404.assert_called_once_with(
            LoanLicense, pk=999, workspace=self.tenant
        )

    def test_operations_pages_require_owner_or_admin(self):
        member = get_user_model().objects.create_user(
            username=f"operations-member-{uuid.uuid4().hex[:8]}"
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=member_role)
        self.client.force_login(member)

        self.assertEqual(
            self.tenant_get(reverse("loans:pawn_operations_console")).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:pawn_operations_runbook")).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("workspace_loans:pawn_risk_portfolio", kwargs={"workspace_slug": self.tenant.slug})).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:document_layout_list")).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:document_layout_guide")).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:document_print_profile_list")).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:document_issue_list")).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:pawn_loan_notice_list")).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:document_layout_designer", args=[1])).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:document_layout_overlay_designer", args=[1])).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:funding_loan_read_console")).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:funding_loan_read_detail", args=[1])).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:funding_loan_draft_create")).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:funding_loan_draft_inputs", args=[1])).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_post(reverse("loans:funding_loan_draft_activate", args=[1]), {"confirmation": "ACTIVATE"}).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_post(
                reverse("loans:funding_loan_repayment", args=[1]),
                {
                    "amount": "1.00",
                    "effective_date": "2026-08-08",
                    "request_key": str(uuid.uuid4()),
                },
            ).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_post(
                reverse("loans:funding_loan_begin_settlement", args=[1]), {}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_post(
                reverse("loans:funding_loan_return_collateral", args=[1]),
                {
                    "collateral": ["1"],
                    "effective_date": "2026-08-08",
                    "request_key": str(uuid.uuid4()),
                },
            ).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_post(
                reverse("loans:funding_loan_close", args=[1]),
                {"confirmation": "CLOSE"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_post(
                reverse("loans:funding_loan_reverse_event", args=[1, 1]),
                {
                    "effective_date": "2026-08-08",
                    "reason": "Correction",
                    "request_key": str(uuid.uuid4()),
                },
            ).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:funding_loan_statement_pdf", args=[1])).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_post(reverse("loans:funding_loan_draft_cancel", args=[1]), {"reason": "No"}).status_code,
            403,
        )

    def test_pilot_sensitive_routes_fail_at_the_http_permission_boundary(self):
        member = get_user_model().objects.create_user(
            username=f"pilot-boundary-member-{uuid.uuid4().hex[:8]}"
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=member_role)
        self.client.force_login(member)

        administrator_routes = (
            ("get", reverse("loans:pawn_loan_reverse_event", args=[999, 999])),
            ("get", reverse("loans:pawn_loan_auction_initiate", args=[999])),
            ("post", reverse("loans:pawn_loan_auction_start", args=[999])),
            ("get", reverse("loans:pawn_loan_auction_cancel", args=[999])),
            ("get", reverse("loans:pawn_loan_auction_complete", args=[999])),
            ("get", reverse("loans:pawn_loan_auction_reverse", args=[999])),
            ("get", reverse("loans:pawn_loan_renewal_reverse", args=[999])),
        )
        owner_routes = (
            ("get", reverse("loans:pawn_storage_location_list")),
            ("get", reverse("loans:pawn_storage_location_create")),
            ("get", reverse("loans:pawn_storage_location_label", args=[999])),
            ("get", reverse("loans:pawn_storage_location_scan", args=[uuid.uuid4()])),
            ("get", reverse("loans:pawn_collateral_storage_transfer", args=[999, 999])),
            ("get", reverse("loans:pawn_physical_verification_list")),
            ("get", reverse("loans:pawn_physical_verification_detail", args=[999])),
            ("post", reverse("loans:pawn_physical_verification_complete", args=[999])),
            ("get", reverse("loans:pawn_physical_verification_resolve", args=[999])),
            ("post", reverse("loans:pawn_physical_verification_discrepancy_notice", args=[999])),
        )
        for method, url in administrator_routes + owner_routes:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 403)

        admin = get_user_model().objects.create_user(
            username=f"pilot-boundary-admin-{uuid.uuid4().hex[:8]}"
        )
        admin_role, _ = Role.objects.get_or_create(name="Admin")
        Membership.objects.create(user=admin, company=self.tenant, role=admin_role)
        self.client.force_login(admin)
        for method, url in owner_routes:
            with self.subTest(role="Admin", method=method, url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self.client.get(
                reverse("loans:pawn_loan_auction_initiate", args=[999])
            ).status_code,
            404,
        )

    def test_owner_can_create_funding_draft_with_active_lender_only(self):
        active_lender = Party.objects.create(
            display_name="Active funding lender",
            status=Party.PartyStatus.ACTIVE,
        )
        inactive_lender = Party.objects.create(
            display_name="Inactive funding lender",
            status=Party.PartyStatus.INACTIVE,
        )
        create_url = reverse("loans:funding_loan_draft_create")

        page = self.tenant_get(create_url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Active funding lender")
        self.assertNotContains(page, "Inactive funding lender")

        rejected = self.tenant_post(create_url, {"lender": inactive_lender.pk})
        self.assertEqual(rejected.status_code, 200)
        self.assertContains(rejected, "Select a valid choice")
        self.assertEqual(FundingLoan.objects.filter(workspace=self.tenant).count(), 0)
        self.assertFalse(FundingLoanSequence.objects.filter(workspace=self.tenant).exists())

        response = self.tenant_post(create_url, {"lender": active_lender.pk})
        funding_loan = FundingLoan.objects.get(workspace=self.tenant)

        self.assertRedirects(
            response,
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(funding_loan.funding_number, "FL-000001")
        self.assertEqual(funding_loan.lender, active_lender)
        self.assertEqual(funding_loan.workspace, self.tenant)
        self.assertEqual(funding_loan.created_by, self.owner)

    def test_owner_can_complete_and_cancel_funding_draft_without_activation(self):
        lender = Party.objects.create(
            display_name="Draft completion lender",
            status=Party.PartyStatus.ACTIVE,
        )
        license, series = self._configured_setup()
        eligible_loan = self._loan(license, series, "PL-FUND-1", state="ACTIVE")
        ineligible_loan = self._loan(license, series, "PL-FUND-2", state="DRAFT")
        eligible_item = PawnCollateralItem.objects.create(
            loan=eligible_loan,
            description="Eligible gold chain",
            metal=CollateralMetal.GOLD.value,
            gross_weight=Decimal("10.0000"),
            net_weight=Decimal("9.0000"),
            purity_percentage=Decimal("91.6000"),
            latest_appraised_value=Decimal("10000.00"),
            custody_state=CollateralCustodyState.IN_VAULT.value,
        )
        PawnCollateralItem.objects.create(
            loan=ineligible_loan,
            description="Draft-loan gold ring",
            metal=CollateralMetal.GOLD.value,
            gross_weight=Decimal("5.0000"),
            net_weight=Decimal("4.5000"),
            purity_percentage=Decimal("91.6000"),
            latest_appraised_value=Decimal("5000.00"),
            custody_state=CollateralCustodyState.IN_VAULT.value,
        )
        self.tenant_post(reverse("loans:funding_loan_draft_create"), {"lender": lender.pk})
        funding_loan = FundingLoan.objects.get(workspace=self.tenant)
        inputs_url = reverse("loans:funding_loan_draft_inputs", args=[funding_loan.pk])

        page = self.tenant_get(inputs_url)
        self.assertContains(page, "Eligible gold chain")
        self.assertNotContains(page, "Draft-loan gold ring")

        response = self.tenant_post(
            inputs_url,
            {
                "principal_amount": "7000.00",
                "monthly_interest_rate": "1.500000",
                "activated_on": "2026-08-08",
                "maturity_on": "2026-11-08",
                "maximum_funding_ltv_ratio": "0.800000",
                "currency_quantum": "0.0100",
                "collateral": [eligible_item.pk],
            },
        )
        self.assertRedirects(
            response,
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk]),
            fetch_redirect_response=False,
        )
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.DRAFT.value)
        self.assertTrue(FundingLoanDraftTerms.objects.filter(funding_loan=funding_loan).exists())
        self.assertTrue(FundingLoanDraftCollateral.objects.filter(funding_loan=funding_loan, collateral_item=eligible_item).exists())
        self.assertFalse(hasattr(funding_loan, "terms_snapshot"))
        eligible_item.refresh_from_db()
        self.assertEqual(eligible_item.custody_state, CollateralCustodyState.IN_VAULT.value)

        detail = self.tenant_get(reverse("loans:funding_loan_read_detail", args=[funding_loan.pk]))
        self.assertContains(detail, "pass the current activation policy")
        self.assertContains(detail, "Servicing remains unavailable until activation")

        rejected = self.tenant_post(
            reverse("loans:funding_loan_draft_cancel", args=[funding_loan.pk]),
            {"reason": ""},
        )
        self.assertEqual(rejected.status_code, 302)
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.DRAFT.value)

        self.tenant_post(
            reverse("loans:funding_loan_draft_cancel", args=[funding_loan.pk]),
            {"reason": "Lender withdrew the proposal"},
        )
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.CANCELLED.value)
        cancellation = FundingLoanCancellation.objects.get(funding_loan=funding_loan)
        self.assertEqual(cancellation.reason, "Lender withdrew the proposal")
        self.assertEqual(cancellation.actor, self.owner)

    def test_owner_can_activate_saved_funding_draft_with_exact_confirmation(self):
        lender = Party.objects.create(
            display_name="Activation lender",
            status=Party.PartyStatus.ACTIVE,
        )
        license, series = self._configured_setup()
        pawn_loan = self._loan(license, series, "PL-ACTIVATE", state="ACTIVE")
        collateral = PawnCollateralItem.objects.create(
            loan=pawn_loan,
            description="Activation gold chain",
            metal=CollateralMetal.GOLD.value,
            gross_weight=Decimal("10.0000"),
            net_weight=Decimal("9.0000"),
            purity_percentage=Decimal("91.6000"),
            latest_appraised_value=Decimal("10000.00"),
            custody_state=CollateralCustodyState.IN_VAULT.value,
        )
        self.tenant_post(reverse("loans:funding_loan_draft_create"), {"lender": lender.pk})
        funding_loan = FundingLoan.objects.get(workspace=self.tenant)
        self.tenant_post(
            reverse("loans:funding_loan_draft_inputs", args=[funding_loan.pk]),
            {
                "principal_amount": "7000.00",
                "monthly_interest_rate": "1.500000",
                "activated_on": "2026-08-08",
                "maturity_on": "2026-11-08",
                "maximum_funding_ltv_ratio": "0.800000",
                "currency_quantum": "0.0100",
                "collateral": [collateral.pk],
            },
        )
        activate_url = reverse("loans:funding_loan_draft_activate", args=[funding_loan.pk])

        rejected = self.tenant_post(activate_url, {"confirmation": "activate"})
        self.assertEqual(rejected.status_code, 302)
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.DRAFT.value)
        self.assertEqual(funding_loan.events.count(), 0)

        response = self.tenant_post(activate_url, {"confirmation": "ACTIVATE"})
        self.assertRedirects(
            response,
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk]),
            fetch_redirect_response=False,
        )
        funding_loan.refresh_from_db()
        collateral.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.ACTIVE.value)
        self.assertEqual(funding_loan.events.count(), 1)
        self.assertTrue(hasattr(funding_loan, "terms_snapshot"))
        self.assertTrue(hasattr(funding_loan, "pledge"))
        self.assertEqual(funding_loan.pledge.items.count(), 1)
        self.assertEqual(collateral.custody_state, CollateralCustodyState.WITH_FUNDING_LENDER.value)
        self.assertFalse(FundingLoanDraftTerms.objects.filter(funding_loan=funding_loan).exists())
        self.assertFalse(FundingLoanDraftCollateral.objects.filter(funding_loan=funding_loan).exists())
        detail = self.tenant_get(reverse("loans:funding_loan_read_detail", args=[funding_loan.pk]))
        self.assertContains(detail, "WITH_FUNDING_LENDER")
        self.assertNotContains(detail, "Activate and hand off collateral")

        repayment_url = reverse("loans:funding_loan_repayment", args=[funding_loan.pk])
        rejected = self.tenant_post(
            repayment_url,
            {
                "amount": "7000.01",
                "effective_date": "2026-09-08",
                "request_key": str(uuid.uuid4()),
            },
        )
        self.assertEqual(rejected.status_code, 302)
        self.assertEqual(funding_loan.events.count(), 1)

        request_key = str(uuid.uuid4())
        repayment = {
            "amount": "1000.00",
            "effective_date": "2026-09-08",
            "request_key": request_key,
        }
        self.tenant_post(repayment_url, repayment)
        self.tenant_post(repayment_url, repayment)
        self.assertEqual(funding_loan.events.count(), 2)
        repayment_event = funding_loan.events.get(operation="RECORD_REPAYMENT")
        self.assertEqual(repayment_event.principal_amount, Decimal("1000.0000"))
        self.assertEqual(repayment_event.interest_amount, Decimal("0.0000"))
        self.assertEqual(repayment_event.fee_amount, Decimal("0.0000"))
        self.assertEqual(repayment_event.actor, self.owner)

        for document_url in (
            reverse("loans:funding_loan_agreement_pdf", args=[funding_loan.pk]),
            reverse("loans:funding_loan_statement_pdf", args=[funding_loan.pk]),
            reverse(
                "loans:funding_loan_repayment_receipt_pdf",
                args=[funding_loan.pk, repayment_event.pk],
            ),
        ):
            document = self.tenant_get(document_url)
            self.assertEqual(document.status_code, 200)
            self.assertEqual(document["Content-Type"], "application/pdf")
            self.assertTrue(document.content.startswith(b"%PDF"))
            self.assertTrue(document["X-Rokkad-Verification-ID"])

        statement = self.tenant_get(
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk])
        )
        self.assertContains(statement, "Funding statement")
        self.assertContains(statement, "RECORD_REPAYMENT")
        self.assertContains(statement, "-1000.0000")
        self.assertContains(statement, "6000.0000")
        self.assertContains(statement, self.owner.username)

        correction_key = str(uuid.uuid4())
        correction_payload = {
            "effective_date": "2026-09-09",
            "reason": "Repayment was entered against the wrong source receipt",
            "request_key": correction_key,
        }
        correction_url = reverse(
            "loans:funding_loan_reverse_event",
            args=[funding_loan.pk, repayment_event.pk],
        )
        self.tenant_post(correction_url, correction_payload)
        self.tenant_post(correction_url, correction_payload)
        reversal = funding_loan.events.get(reversal_of=repayment_event)
        self.assertEqual(reversal.reason, correction_payload["reason"])
        self.assertEqual(reversal.actor, self.owner)
        self.assertEqual(funding_loan.events.filter(reversal_of=repayment_event).count(), 1)
        corrected_detail = self.tenant_get(
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk])
        )
        self.assertContains(corrected_detail, "Reversal")
        self.assertContains(corrected_detail, "7000.0000")

        self.tenant_post(
            repayment_url,
            {
                "amount": "1000.00",
                "effective_date": "2026-09-10",
                "request_key": str(uuid.uuid4()),
            },
        )

        active_detail = self.tenant_get(
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk])
        )
        self.assertContains(active_detail, "Settlement readiness")
        self.assertNotContains(active_detail, "Begin settlement review")
        self.assertNotContains(active_detail, "Return selected collateral")
        blocked_return = self.tenant_post(
            reverse("loans:funding_loan_return_collateral", args=[funding_loan.pk]),
            {
                "collateral": [str(collateral.pk)],
                "effective_date": "2026-09-08",
                "request_key": str(uuid.uuid4()),
            },
        )
        self.assertEqual(blocked_return.status_code, 302)
        self.assertEqual(funding_loan.returns.count(), 0)
        collateral.refresh_from_db()
        self.assertEqual(
            collateral.custody_state,
            CollateralCustodyState.WITH_FUNDING_LENDER.value,
        )

        self.tenant_post(
            repayment_url,
            {
                "amount": "6000.00",
                "effective_date": "2026-10-08",
                "request_key": str(uuid.uuid4()),
            },
        )
        settled_detail = self.tenant_get(
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk])
        )
        self.assertContains(settled_detail, "Begin settlement review")

        settlement_url = reverse(
            "loans:funding_loan_begin_settlement", args=[funding_loan.pk]
        )
        self.tenant_post(settlement_url, {})
        self.tenant_post(settlement_url, {})
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.SETTLEMENT_PENDING.value)
        self.assertEqual(funding_loan.updated_by, self.owner)

        pending_detail = self.tenant_get(
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk])
        )
        self.assertContains(pending_detail, "Return selected collateral")
        self.assertNotContains(pending_detail, "Close FundingLoan")
        close_url = reverse("loans:funding_loan_close", args=[funding_loan.pk])
        self.tenant_post(close_url, {"confirmation": "CLOSE"})
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.SETTLEMENT_PENDING.value)
        return_url = reverse(
            "loans:funding_loan_return_collateral", args=[funding_loan.pk]
        )
        return_key = str(uuid.uuid4())
        return_payload = {
            "collateral": [str(collateral.pk)],
            "effective_date": "2026-10-08",
            "request_key": return_key,
        }
        self.tenant_post(return_url, return_payload)
        self.tenant_post(return_url, return_payload)
        collateral.refresh_from_db()
        self.assertEqual(collateral.custody_state, CollateralCustodyState.IN_VAULT.value)
        self.assertEqual(funding_loan.returns.count(), 1)
        funding_return = funding_loan.returns.get()
        self.assertEqual(funding_return.actor, self.owner)
        self.assertEqual(funding_return.items.count(), 1)
        return_receipt = self.tenant_get(
            reverse(
                "loans:funding_loan_return_receipt_pdf",
                args=[funding_loan.pk, funding_return.pk],
            )
        )
        self.assertEqual(return_receipt.status_code, 200)
        self.assertEqual(return_receipt["Content-Type"], "application/pdf")
        self.assertTrue(return_receipt.content.startswith(b"%PDF"))
        self.assertIn(f"FundingReturn:{funding_return.pk}", return_receipt["X-Rokkad-Verification-ID"])

        ready_detail = self.tenant_get(
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk])
        )
        self.assertTrue(ready_detail.context["settlement"].financially_settled)
        self.assertTrue(ready_detail.context["settlement"].collateral_returned)
        self.assertTrue(ready_detail.context["settlement"].closure_ready)
        self.assertContains(ready_detail, "Financially settled:")
        self.assertContains(ready_detail, "Collateral returned:")
        self.assertContains(ready_detail, "RETURN_COLLATERAL")
        self.assertNotContains(ready_detail, "Return selected collateral")
        self.assertContains(ready_detail, "Close FundingLoan")

        self.tenant_post(close_url, {"confirmation": "close"})
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.SETTLEMENT_PENDING.value)
        self.tenant_post(close_url, {"confirmation": "CLOSE"})
        self.tenant_post(close_url, {"confirmation": "CLOSE"})
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.CLOSED.value)
        self.assertEqual(funding_loan.updated_by, self.owner)

        closed_detail = self.tenant_get(
            reverse("loans:funding_loan_read_detail", args=[funding_loan.pk])
        )
        self.assertContains(closed_detail, "CLOSED")
        self.assertNotContains(closed_detail, "Record repayment")
        self.assertNotContains(closed_detail, "Begin settlement review")
        self.assertNotContains(closed_detail, "Return selected collateral")
        self.assertNotContains(closed_detail, "Close FundingLoan")

    def test_owner_can_open_read_only_funding_console_and_detail(self):
        summary = type(
            "Summary",
            (),
            {
                "funding_loan_id": 41,
                "funding_number": "FL-000041",
                "lender_name": "Funding lender",
                "state": "ACTIVE",
                "principal_outstanding": Decimal("7000.0000"),
                "interest_outstanding": Decimal("90.0000"),
                "fees_outstanding": Decimal("10.0000"),
                "total_due": Decimal("7100.0000"),
                "active_collateral_count": 2,
            },
        )()
        finding = type(
            "Finding",
            (),
            {
                "code": "CUSTODY_TIMELINE",
                "funding_loan_id": 41,
                "object_type": "collateral_item",
                "object_id": 9,
                "message": "Latest custody evidence does not match the projection.",
            },
        )()
        detail = type(
            "Detail",
            (),
            {
                "summary": summary,
                "activated_on": date(2026, 8, 8),
                "maturity_on": date(2026, 11, 8),
                "monthly_interest_rate": Decimal("1.500000"),
                "maximum_funding_ltv_ratio": Decimal("0.800000"),
                "collateral": (),
                "timeline": (),
            },
        )()

        with patch(
            "apps.tenant_apps.loans.web.funding.get_funding_loan_summaries",
            return_value=(summary,),
        ), patch(
            "apps.tenant_apps.loans.web.funding.get_funding_loan_integrity_findings",
            return_value=(finding,),
        ):
            response = self.tenant_get(reverse("loans:funding_loan_read_console"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "FundingLoan read console")
        self.assertContains(response, "FL-000041")
        self.assertContains(response, "CUSTODY_TIMELINE")
        self.assertContains(response, "Controlled MVP preview")

        with patch(
            "apps.tenant_apps.loans.web.funding.get_funding_loan_detail",
            return_value=detail,
        ):
            response = self.tenant_get(
                reverse("loans:funding_loan_read_detail", args=[41])
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Funding lender")
        self.assertContains(response, "Operational balance")

    def test_funding_read_detail_returns_404_for_unknown_workspace_loan(self):
        response = self.tenant_get(
            reverse("loans:funding_loan_read_detail", args=[999999])
        )

        self.assertEqual(response.status_code, 404)

    def test_owner_can_open_document_layout_starter_guide(self):
        response = self.tenant_get(reverse("loans:document_layout_guide"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Layout and print profile responsibilities")
        self.assertContains(response, "Print profile owns")
        self.assertContains(response, "Resolution order:")
        self.assertContains(response, "Series &rarr; License &rarr; Workspace")
        self.assertContains(response, "Profile resolution:")
        self.assertContains(response, "Series &rarr; Workspace")
        self.assertContains(response, "Issued documents")
        self.assertContains(response, "?print_profile=legacy")

    def test_owner_can_create_publish_and_assign_starter_ticket_layout(self):
        response = self.tenant_post(
            reverse("loans:document_layout_create"),
            {"name": "Counter ticket", "document_type": "loan_ticket"},
        )
        revision = LoanDocumentLayoutRevision.objects.select_related("layout").get(
            layout__name="Counter ticket"
        )
        self.assertEqual(revision.definition["schema_version"], 3)
        self.assertEqual(revision.definition["layout_mode"], "FLOW")
        self.assertNotIn("copy_mode", revision.definition)
        self.assertNotIn("sheet", revision.definition)
        self.assertRedirects(
            response,
            reverse("loans:document_layout_detail", args=[revision.pk]),
            fetch_redirect_response=False,
        )
        detail = self.tenant_get(
            reverse("loans:document_layout_detail", args=[revision.pk])
        )
        self.assertContains(detail, "Structured layout definition")
        self.assertContains(detail, "Publish and freeze")
        self.assertContains(detail, "Visual Flow editor")

        downgrade = self.tenant_post(
            reverse("loans:document_layout_update", args=[revision.pk]),
            {"definition": json.dumps(
                starter_layout("loan_ticket", schema_version=2).canonical_dict()
            )},
        )
        self.assertEqual(downgrade.status_code, 302)
        revision.refresh_from_db()
        self.assertEqual(revision.definition["schema_version"], 3)

        designer = self.tenant_get(
            reverse("loans:document_layout_designer", args=[revision.pk])
        )
        self.assertEqual(designer.status_code, 200)
        self.assertContains(designer, "Body blocks")
        add_block = self.tenant_post(
            reverse("loans:document_layout_designer", args=[revision.pk]),
            {
                "operation": "add_block", "block_type": "SPACER",
                "binding": "", "bindings": [], "text": "", "height_mm": 9,
            },
        )
        self.assertEqual(add_block.status_code, 302)
        revision.refresh_from_db()
        self.assertEqual(revision.definition["blocks"][-1]["type"], "spacer")
        save_settings = self.tenant_post(
            reverse("loans:document_layout_designer", args=[revision.pk]),
            {
                "operation": "save_settings", "page_size": "A5", "margin_mm": 10,
                "primary_color": "#7c2d12", "border_color": "#d6d3d1",
                "font_family": "HELVETICA", "body_font_size_pt": 9,
                "heading_font_size_pt": 16,
            },
        )
        self.assertEqual(save_settings.status_code, 302)
        revision.refresh_from_db()
        self.assertEqual(revision.definition["page_size"], "A5")
        self.assertEqual(revision.definition["page"]["margin_mm"], 10)

        definition = starter_layout("loan_ticket", schema_version=3).canonical_dict()
        definition["name"] = "Updated counter ticket"
        update = self.tenant_post(
            reverse("loans:document_layout_update", args=[revision.pk]),
            {"definition": json.dumps(definition)},
        )
        self.assertEqual(update.status_code, 302)
        revision.refresh_from_db()
        self.assertEqual(revision.definition["name"], "Updated counter ticket")

        image_buffer = io.BytesIO()
        PillowImage.new("RGB", (20, 20), color="blue").save(image_buffer, format="PNG")
        upload = self.client.post(
            reverse("loans:document_layout_asset_add", args=[revision.pk]),
            {
                "key": "business.logo",
                "kind": "IMAGE",
                "file": SimpleUploadedFile("logo.png", image_buffer.getvalue(), content_type="image/png"),
            },
        )
        self.assertEqual(upload.status_code, 302)
        self.assertTrue(revision.assets.filter(key="business.logo").exists())

        response = self.tenant_post(
            reverse("loans:document_layout_publish", args=[revision.pk])
        )
        self.assertEqual(response.status_code, 302)
        revision.refresh_from_db()
        self.assertEqual(revision.state, "PUBLISHED")

        response = self.tenant_post(
            reverse("loans:document_layout_assign", args=[revision.pk]),
            {"license": "", "series": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(revision.assignments.filter(is_active=True).exists())

    def test_owner_can_create_absolute_overlay_starter_draft(self):
        response = self.tenant_post(
            reverse("loans:document_layout_create"),
            {
                "name": "Existing form ticket", "document_type": "loan_ticket",
                "layout_mode": "ABSOLUTE_OVERLAY",
            },
        )

        revision = LoanDocumentLayoutRevision.objects.get(layout__name="Existing form ticket")
        self.assertRedirects(
            response, reverse("loans:document_layout_detail", args=[revision.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(revision.definition["layout_mode"], "ABSOLUTE_OVERLAY")
        self.assertEqual(revision.definition["background_asset_key"], "form.background")
        detail = self.tenant_get(reverse("loans:document_layout_detail", args=[revision.pk]))
        self.assertNotContains(detail, "Visual Flow editor")
        self.assertContains(detail, "Visual overlay editor")

        pdf = fitz.open()
        page = pdf.new_page()
        page.insert_text((30, 30), "FORM BACKGROUND")
        background_bytes = pdf.tobytes()
        pdf.close()
        upload = self.client.post(
            reverse("loans:document_layout_asset_add", args=[revision.pk]),
            {
                "key": "form.background", "kind": "BACKGROUND",
                "file": SimpleUploadedFile("form.pdf", background_bytes, content_type="application/pdf"),
            },
        )
        self.assertEqual(upload.status_code, 302)
        editor_url = reverse("loans:document_layout_overlay_designer", args=[revision.pk])
        editor = self.tenant_get(editor_url)
        self.assertEqual(editor.status_code, 200)
        self.assertContains(editor, "Drag a rectangle")
        self.assertContains(editor, "Physical paper, imposition, sequence, and duplex behavior belong to Print profiles")
        self.assertNotContains(editor, "Legacy copy mode")
        self.assertNotContains(editor, "Sheet composition")
        background = self.tenant_get(
            reverse("loans:document_layout_overlay_background", args=[revision.pk])
        )
        self.assertEqual(background.status_code, 200)
        self.assertEqual(background["Content-Type"], "image/png")

        title = revision.definition["blocks"][0]
        move = self.tenant_post(editor_url, {
            "operation": "save_block", "index": 0, "block_type": "title",
            "binding": "", "asset_key": "", "text": title.get("text", ""),
            "x_mm": 20, "y_mm": title["y_mm"], "width_mm": title["width_mm"],
            "height_mm": title["height_mm"], "font_size_pt": title["font_size_pt"],
            "align": title["align"],
        })
        self.assertEqual(move.status_code, 302)
        revision.refresh_from_db()
        self.assertEqual(revision.definition["blocks"][0]["x_mm"], 20)

    def test_precision_overlay_editor_saves_value_only_fractional_frames_without_background(self):
        response = self.tenant_post(reverse("loans:document_layout_create"), {
            "name": "Precision stationery", "document_type": "loan_ticket",
            "layout_mode": "ABSOLUTE_OVERLAY", "precision_overlay": "on",
        })
        self.assertEqual(response.status_code, 302)
        revision = LoanDocumentLayoutRevision.objects.get(layout__name="Precision stationery")
        self.assertEqual(revision.definition["schema_version"], 4)
        self.assertEqual(revision.definition["background_asset_key"], "")
        editor_url = reverse("loans:document_layout_overlay_designer", args=[revision.pk])
        editor = self.tenant_get(editor_url)
        self.assertContains(editor, "This template prints without a background")
        self.assertContains(editor, 'step="0.1"')
        self.assertContains(editor, "Value only")
        self.assertTrue(editor.context["can_preview"])
        index, block = next((i, b) for i, b in enumerate(revision.definition["blocks"]) if b["binding"] == "loan.number")
        response = self.tenant_post(editor_url, {
            "operation": "save_block", "index": index, "block_type": "field",
            "binding": "loan.number", "x_mm": "10.1", "y_mm": "25.2",
            "width_mm": "90.3", "height_mm": "8.4", "font_size_pt": block["font_size_pt"],
            "align": "LEFT", "copy_scope": "BOTH", "value_display": "VALUE_ONLY",
            "field_label": "Ticket",
        })
        self.assertEqual(response.status_code, 302)
        revision.refresh_from_db()
        block = revision.definition["blocks"][index]
        self.assertEqual(block["x_mm"], 10.1)
        self.assertEqual(block["height_mm"], 8.4)
        self.assertFalse(block["show_label"])
        self.assertEqual(block["field_label"], "Ticket")
        editor = self.tenant_get(editor_url)
        self.assertContains(editor, 'data-x="10.1"')
        self.assertContains(editor, 'value="VALUE_ONLY" selected')
        self.tenant_post(editor_url, {"operation": "save_settings", "page_size": "A4"})
        revision.refresh_from_db()
        self.assertEqual(revision.definition["background_asset_key"], "")
        published = LoanDocumentLayoutService.publish(revision=revision, actor=self.owner)
        self.assertEqual(published.state, "PUBLISHED")

        license, series = self._configured_setup()
        loan = self._loan(license, series, "PL-PRECISE-00001", state="APPROVED")
        PawnLoanApprovalSnapshot.objects.create(
            loan=loan, version=1, approved_by=self.owner,
            fingerprint="precision-approved-fixture",
            payload={
                "loan_number": loan.loan_number, "loan_date": str(loan.loan_date),
                "principal_amount": str(loan.principal_amount),
                "monthly_interest_rate": str(loan.monthly_interest_rate),
                "tenure_months": loan.tenure_months, "borrower_id": loan.borrower_id,
                "collateral": [],
            },
        )
        LoanDocumentLayoutService.assign(
            revision=published, workspace=self.tenant, license=license, series=series, actor=self.owner,
        )
        preview = self.tenant_get(
            f"{reverse('loans:document_layout_preview', args=[revision.pk])}?loan={loan.pk}"
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview["X-Rokkad-Preview"], "true")
        url = reverse("loans:pawn_loan_ticket_pdf", args=[loan.pk])
        first = self.tenant_get(url)
        self.assertEqual(first.status_code, 200)
        issue = LoanDocumentIssue.objects.get(pk=first["X-Rokkad-Document-Issue"])
        self.assertEqual(issue.revision_id, published.pk)
        self.assertEqual(issue.layout_hash, published.content_hash)
        replacement = LoanDocumentLayoutService.clone_revision(revision=published, actor=self.owner)
        definition = replacement.definition
        definition["blocks"][index]["show_label"] = True
        replacement = LoanDocumentLayoutService.update_draft(
            revision=replacement, definition=definition, actor=self.owner,
        )
        replacement = LoanDocumentLayoutService.publish(revision=replacement, actor=self.owner)
        LoanDocumentLayoutService.assign(
            revision=replacement, workspace=self.tenant, license=license, series=series, actor=self.owner,
        )
        reprint = self.tenant_get(url)
        self.assertEqual(reprint.content, first.content)
        self.assertEqual(reprint["X-Rokkad-Document-Issue"], first["X-Rokkad-Document-Issue"])

    def test_preprinted_profile_preview_issue_and_reprint_keep_guides_unofficial(self):
        from apps.orgs.models import Company
        from apps.tenancy.context import workspace_context, without_workspace_context

        license, series = self._configured_setup()
        loan = self._loan(license, series, "PL-STOCK-00001", state="APPROVED")
        PawnLoanApprovalSnapshot.objects.create(
            loan=loan, version=1, approved_by=self.owner, fingerprint="stock-approved-fixture",
            payload={"loan_number": loan.loan_number, "loan_date": str(loan.loan_date),
                     "principal_amount": str(loan.principal_amount), "monthly_interest_rate": str(loan.monthly_interest_rate),
                     "tenure_months": loan.tenure_months, "borrower_id": loan.borrower_id, "collateral": []},
        )
        definition = starter_layout("loan_ticket", schema_version=4, layout_mode="ABSOLUTE_OVERLAY").canonical_dict()
        definition["background_asset_key"] = "guide"
        revision = LoanDocumentLayoutService.create_layout(workspace=self.tenant, document_type="loan_ticket", name="Guide ticket", definition=definition, actor=self.owner)
        with fitz.open() as pdf:
            pdf.new_page().insert_text((30, 20), "GUIDE-ONLY-MARKER")
            LoanDocumentLayoutService.add_asset(revision=revision, key="guide", kind="BACKGROUND", content=pdf.tobytes(), filename="guide.pdf", actor=self.owner)
        editor_url = reverse("loans:document_layout_overlay_designer", args=[revision.pk])
        self.assertContains(self.tenant_get(editor_url), "Design preview")
        self.tenant_post(editor_url, {
            "operation": "save_block", "index": 0, "block_type": "title", "text": "Spaced ticket",
            "x_mm": 10, "y_mm": 8, "width_mm": 190, "height_mm": 20,
            "font_size_pt": 10, "align": "LEFT", "copy_scope": "BOTH", "padding_pt": "6", "leading_pt": "12",
        })
        revision.refresh_from_db()
        self.assertEqual(revision.definition["blocks"][0]["padding_pt"], 6)
        self.assertEqual(revision.definition["blocks"][0]["leading_pt"], 12)
        self.assertContains(self.tenant_get(editor_url), 'name="leading_pt" step="0.1" min="6" max="48" value="12"')
        create = self.tenant_post(reverse("loans:document_print_profile_create"), {
            "name": "Preprinted counter", "composition": "A5_BOTH_SIMPLEX", "stock_mode": "PREPRINTED",
            "scaling_policy": "FIT_PRINTABLE_AREA", "flip_edge_guidance": "NOT_APPLICABLE",
        })
        self.assertEqual(create.status_code, 302)
        profile = LoanDocumentPrintProfileRevision.objects.get(profile__name="Preprinted counter")
        self.assertEqual(profile.definition["stock_mode"], "PREPRINTED")
        detail = self.tenant_get(reverse("loans:document_print_profile_detail", args=[profile.pk]))
        self.assertContains(detail, 'value="PREPRINTED" selected')
        self.tenant_post(reverse("loans:document_print_profile_update", args=[profile.pk]), {
            "composition": "A5_BOTH_SIMPLEX", "stock_mode": "PREPRINTED",
            "scaling_policy": "FIT_PRINTABLE_AREA", "flip_edge_guidance": "NOT_APPLICABLE",
        })
        profile.refresh_from_db()
        self.assertEqual(profile.definition["schema_version"], 2)
        self.assertEqual(profile.definition["stock_mode"], "PREPRINTED")
        preview_url = reverse("loans:document_layout_preview", args=[revision.pk])
        for mode in ("design", "print"):
            response = self.tenant_get(f"{preview_url}?loan={loan.pk}&profile={profile.pk}&mode={mode}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["X-Rokkad-Preview-Mode"], mode)
            self.assertIn("no-store", response["Cache-Control"])
            with fitz.open(stream=response.content, filetype="pdf") as pdf:
                self.assertEqual("GUIDE-ONLY-MARKER" in pdf[0].get_text(), mode == "design")
        self.assertFalse(LoanDocumentIssue.objects.filter(source_id=str(loan.pk)).exists())
        revision = LoanDocumentLayoutService.publish(revision=revision, actor=self.owner)
        LoanDocumentLayoutService.assign(revision=revision, workspace=self.tenant, license=license, series=series, actor=self.owner)
        profile = LoanDocumentPrintProfileService.publish(revision=profile, actor=self.owner)
        LoanDocumentPrintProfileService.assign(revision=profile, workspace=self.tenant, series=series, actor=self.owner)
        resolved = self.tenant_get(f"{preview_url}?loan={loan.pk}")
        with fitz.open(stream=resolved.content, filetype="pdf") as pdf:
            self.assertNotIn("GUIDE-ONLY-MARKER", pdf[0].get_text())
        profile_preview = reverse("loans:document_print_profile_preview", args=[profile.pk])
        design = self.tenant_get(f"{profile_preview}?layout={revision.pk}&loan={loan.pk}&mode=design")
        self.assertEqual(design.status_code, 200)
        self.assertEqual(design["X-Rokkad-Preview-Mode"], "design")
        url = reverse("loans:pawn_loan_ticket_pdf", args=[loan.pk])
        official = self.tenant_get(f"{url}?mode=design")
        self.assertEqual(official.status_code, 200)
        with fitz.open(stream=official.content, filetype="pdf") as pdf:
            self.assertNotIn("GUIDE-ONLY-MARKER", pdf[0].get_text())
            self.assertNotIn("DESIGN PREVIEW", pdf[0].get_text())
        replacement = LoanDocumentPrintProfileService.clone_revision(revision=profile, actor=self.owner)
        replacement = LoanDocumentPrintProfileService.update_draft(revision=replacement, definition={**replacement.definition, "stock_mode": "PLAIN"}, actor=self.owner)
        replacement = LoanDocumentPrintProfileService.publish(revision=replacement, actor=self.owner)
        LoanDocumentPrintProfileService.assign(revision=replacement, workspace=self.tenant, series=series, actor=self.owner)
        self.assertEqual(self.tenant_get(url).content, official.content)
        other = Company.objects.create(name="Other stationery workspace", schema_name="other-stationery", owner=self.owner, creator=self.owner)
        with without_workspace_context(), workspace_context(other.pk):
            Membership.objects.create(user=self.owner, company=other, role=Role.objects.get(name="Owner"))
            foreign = LoanDocumentPrintProfileService.create_profile(workspace=other, document_type="loan_ticket", name="Private guide profile", definition={**built_in_print_profile().canonical_dict(), "name": "Private guide profile"}, actor=self.owner)
        self.assertEqual(self.tenant_get(f"{preview_url}?loan={loan.pk}&profile={foreign.pk}&mode=design").status_code, 404)
        self.assertNotContains(self.tenant_get(editor_url), "Private guide profile")

    def test_published_ticket_layout_drives_official_issue_and_reprint(self):
        license, series = self._configured_setup()
        loan = self._loan(license, series, "PL-DOC-00001", state="APPROVED")
        approval_payload = {
            "loan_number": loan.loan_number,
            "loan_date": str(loan.loan_date),
            "principal_amount": str(loan.principal_amount),
            "monthly_interest_rate": str(loan.monthly_interest_rate),
            "tenure_months": loan.tenure_months,
            "borrower_id": loan.borrower_id,
            "collateral": [],
        }
        PawnLoanApprovalSnapshot.objects.create(
            loan=loan,
            version=1,
            payload=approval_payload,
            fingerprint="ui-approval-fingerprint",
            approved_by=self.owner,
        )
        revision = LoanDocumentLayoutService.create_layout(
            workspace=self.tenant,
            document_type="loan_ticket",
            name=f"Issued ticket {uuid.uuid4().hex[:6]}",
            definition=starter_layout("loan_ticket").canonical_dict(),
            actor=self.owner,
        )
        revision = LoanDocumentLayoutService.publish(
            revision=revision, actor=self.owner
        )
        LoanDocumentLayoutService.assign(
            revision=revision,
            workspace=self.tenant,
            license=license,
            series=series,
            actor=self.owner,
        )

        preview = self.tenant_get(
            f"{reverse('loans:document_layout_preview', args=[revision.pk])}?loan={loan.pk}"
        )
        test_print = self.tenant_get(
            f"{reverse('loans:document_layout_preview', args=[revision.pk])}?loan={loan.pk}&download=1"
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview["X-Rokkad-Preview"], "true")
        self.assertIn(b"PREVIEW / NOT AN OFFICIAL ISSUE", preview.content)
        self.assertTrue(test_print["Content-Disposition"].startswith("attachment"))

        url = reverse("loans:pawn_loan_ticket_pdf", args=[loan.pk])
        first = self.tenant_get(url)
        second = self.tenant_get(url)

        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.content.startswith(b"%PDF"))
        self.assertEqual(first["X-Rokkad-Document-Issue"], second["X-Rokkad-Document-Issue"])
        self.assertEqual(first["X-Rokkad-Print-Profile"], "Built-in A5 Both Simplex")
        self.assertEqual(first["X-Rokkad-Print-Profile-Hash"], second["X-Rokkad-Print-Profile-Hash"])
        self.assertEqual(LoanDocumentIssue.objects.filter(source_id=str(loan.pk)).count(), 1)
        issue = LoanDocumentIssue.objects.get(source_id=str(loan.pk))
        self.assertEqual(issue.print_profile_source_scope, "BUILT_IN")
        self.assertEqual(issue.print_profile_hash, first["X-Rokkad-Print-Profile-Hash"])
        evidence = self.tenant_get(
            reverse("loans:document_issue_detail", args=[issue.pk])
        )
        self.assertContains(evidence, "Built-in A5 Both Simplex")
        artifact = self.tenant_get(
            reverse("loans:document_issue_artifact", args=[issue.pk])
        )
        self.assertEqual(artifact.content, first.content)
        self.assertEqual(artifact["X-Rokkad-PDF-Hash"], issue.pdf_hash)

        profile_definition = built_in_print_profile(
            "A4_SIDE_BY_SIDE"
        ).canonical_dict()
        profile_definition["name"] = "Series counter A4"
        profile_revision = LoanDocumentPrintProfileService.create_profile(
            workspace=self.tenant,
            document_type="loan_ticket",
            name="Series counter A4",
            definition=profile_definition,
            actor=self.owner,
        )
        profile_revision = LoanDocumentPrintProfileService.publish(
            revision=profile_revision, actor=self.owner
        )
        LoanDocumentPrintProfileService.assign(
            revision=profile_revision,
            workspace=self.tenant,
            series=series,
            actor=self.owner,
        )

        unchanged_reprint = self.tenant_get(url)
        self.assertEqual(
            unchanged_reprint["X-Rokkad-Document-Issue"],
            first["X-Rokkad-Document-Issue"],
        )
        self.assertEqual(unchanged_reprint.content, first.content)

        PawnLoanApprovalSnapshot.objects.create(
            loan=loan,
            version=2,
            payload=approval_payload,
            fingerprint="ui-approval-fingerprint-2",
            approved_by=self.owner,
        )
        future = self.tenant_get(url)
        self.assertEqual(future.status_code, 200)
        self.assertNotEqual(
            future["X-Rokkad-Document-Issue"], first["X-Rokkad-Document-Issue"]
        )
        self.assertEqual(future["X-Rokkad-Print-Profile"], "Series counter A4")
        future_issue = LoanDocumentIssue.objects.get(
            pk=future["X-Rokkad-Document-Issue"]
        )
        self.assertEqual(future_issue.print_profile_source_scope, "SERIES")
        self.assertEqual(
            future_issue.print_profile_revision_id, profile_revision.pk
        )
        future_pdf = fitz.open(stream=future.content, filetype="pdf")
        self.assertEqual(len(future_pdf), 1)
        self.assertGreater(future_pdf[0].rect.width, future_pdf[0].rect.height)
        future_pdf.close()

        PawnLoanApprovalSnapshot.objects.create(
            loan=loan,
            version=3,
            payload=approval_payload,
            fingerprint="ui-approval-fingerprint-3",
            approved_by=self.owner,
        )
        legacy = self.tenant_get(f"{url}?print_profile=legacy")
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(
            legacy["X-Rokkad-Print-Profile"],
            "Legacy embedded Legacy Original",
        )
        legacy_issue = LoanDocumentIssue.objects.get(
            pk=legacy["X-Rokkad-Document-Issue"]
        )
        self.assertEqual(
            legacy_issue.print_profile_source_scope, "LEGACY_LAYOUT"
        )

        fixed = self.tenant_get(f"{url}?renderer=fixed")
        self.assertEqual(fixed.status_code, 200)
        self.assertNotIn("X-Rokkad-Document-Issue", fixed)

        clone_response = self.tenant_post(
            reverse("loans:document_layout_clone", args=[revision.pk])
        )
        self.assertEqual(clone_response.status_code, 302)
        self.assertTrue(revision.layout.revisions.filter(version=2, state="DRAFT").exists())
        retire_response = self.tenant_post(
            reverse("loans:document_layout_retire", args=[revision.pk])
        )
        self.assertEqual(retire_response.status_code, 302)
        revision.refresh_from_db()
        self.assertEqual(revision.state, "RETIRED")

    def test_schema_v3_ticket_issue_requires_and_records_resolved_profile(self):
        license, series = self._configured_setup()
        loan = self._loan(license, series, "PL-DOC-V3-00001", state="APPROVED")
        PawnLoanApprovalSnapshot.objects.create(
            loan=loan,
            version=1,
            payload={
                "loan_number": loan.loan_number,
                "loan_date": str(loan.loan_date),
                "principal_amount": str(loan.principal_amount),
                "monthly_interest_rate": str(loan.monthly_interest_rate),
                "tenure_months": loan.tenure_months,
                "borrower_id": loan.borrower_id,
                "collateral": [],
            },
            fingerprint="schema-v3-approval-fingerprint",
            approved_by=self.owner,
        )
        revision = LoanDocumentLayoutService.create_layout(
            workspace=self.tenant,
            document_type="loan_ticket",
            name=f"Logical ticket {uuid.uuid4().hex[:6]}",
            definition=starter_layout(
                "loan_ticket", schema_version=3
            ).canonical_dict(),
            actor=self.owner,
        )
        revision = LoanDocumentLayoutService.publish(
            revision=revision, actor=self.owner
        )
        LoanDocumentLayoutService.assign(
            revision=revision,
            workspace=self.tenant,
            license=license,
            series=series,
            actor=self.owner,
        )

        ticket_url = reverse("loans:pawn_loan_ticket_pdf", args=[loan.pk])
        blocked_legacy = self.tenant_get(f"{ticket_url}?print_profile=legacy")
        self.assertEqual(blocked_legacy.status_code, 409)
        self.assertContains(
            blocked_legacy, "no embedded physical composition", status_code=409
        )
        self.assertFalse(LoanDocumentIssue.objects.filter(source_id=str(loan.pk)).exists())

        response = self.tenant_get(ticket_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Rokkad-Print-Profile"], "Built-in A5 Both Simplex")
        issue = LoanDocumentIssue.objects.get(source_id=str(loan.pk))
        self.assertEqual(issue.revision_id, revision.pk)
        self.assertEqual(issue.print_profile_source_scope, "BUILT_IN")
        self.assertTrue(issue.print_profile_hash)

    def test_owner_can_manage_assign_preview_and_retire_print_profile(self):
        license, series = self._configured_setup()
        loan = self._loan(license, series, "PL-PROFILE-00001", state="APPROVED")
        PawnLoanApprovalSnapshot.objects.create(
            loan=loan,
            version=1,
            payload={
                "loan_number": loan.loan_number,
                "loan_date": str(loan.loan_date),
                "principal_amount": str(loan.principal_amount),
                "monthly_interest_rate": str(loan.monthly_interest_rate),
                "tenure_months": loan.tenure_months,
                "borrower_id": loan.borrower_id,
                "collateral": [],
            },
            fingerprint="profile-ui-approval",
            approved_by=self.owner,
        )
        layout_definition = starter_layout("loan_ticket").canonical_dict()
        layout_definition["copy_mode"] = "ORIGINAL_DUPLICATE"
        layout_revision = LoanDocumentLayoutService.create_layout(
            workspace=self.tenant,
            document_type="loan_ticket",
            name=f"Profile preview layout {uuid.uuid4().hex[:6]}",
            definition=layout_definition,
            actor=self.owner,
        )
        layout_revision = LoanDocumentLayoutService.publish(
            revision=layout_revision, actor=self.owner
        )
        LoanDocumentLayoutService.assign(
            revision=layout_revision,
            workspace=self.tenant,
            series=series,
            actor=self.owner,
        )

        create = self.tenant_post(
            reverse("loans:document_print_profile_create"),
            {
                "name": "Front counter profile",
                "composition": "A5_BOTH_SIMPLEX",
                "scaling_policy": "FIT_PRINTABLE_AREA",
                "flip_edge_guidance": "NOT_APPLICABLE",
                "printer_guidance": "Load A5 paper in tray 2.",
            },
        )
        profile_revision = LoanDocumentPrintProfileRevision.objects.get(
            profile__name="Front counter profile", version=1
        )
        self.assertRedirects(
            create,
            reverse(
                "loans:document_print_profile_detail",
                args=[profile_revision.pk],
            ),
            fetch_redirect_response=False,
        )
        detail = self.tenant_get(
            reverse("loans:document_print_profile_detail", args=[profile_revision.pk])
        )
        self.assertContains(detail, "Front counter profile")
        self.assertContains(detail, "Preview and test print")

        preview_url = reverse(
            "loans:document_print_profile_preview", args=[profile_revision.pk]
        )
        preview = self.tenant_get(
            f"{preview_url}?layout={layout_revision.pk}&loan={loan.pk}"
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview["X-Rokkad-Preview"], "true")
        self.assertEqual(preview["X-Rokkad-Print-Profile"], "Front counter profile")
        preview_pdf = fitz.open(stream=preview.content, filetype="pdf")
        self.assertEqual(len(preview_pdf), 2)
        preview_pdf.close()

        update = self.tenant_post(
            reverse("loans:document_print_profile_update", args=[profile_revision.pk]),
            {
                "composition": "A4_SIDE_BY_SIDE",
                "scaling_policy": "FIT_PRINTABLE_AREA",
                "flip_edge_guidance": "NOT_APPLICABLE",
                "printer_guidance": "Use landscape A4.",
            },
        )
        self.assertEqual(update.status_code, 302)
        profile_revision.refresh_from_db()
        self.assertEqual(
            profile_revision.definition["composition"], "A4_SIDE_BY_SIDE"
        )

        self.tenant_post(
            reverse("loans:document_print_profile_publish", args=[profile_revision.pk])
        )
        profile_revision.refresh_from_db()
        self.assertEqual(profile_revision.state, "PUBLISHED")
        assign = self.tenant_post(
            reverse("loans:document_print_profile_assign", args=[profile_revision.pk]),
            {"series": series.pk},
        )
        self.assertEqual(assign.status_code, 302)
        self.assertTrue(
            profile_revision.assignments.filter(
                series=series, is_active=True
            ).exists()
        )

        test_print = self.tenant_get(
            f"{preview_url}?layout={layout_revision.pk}&loan={loan.pk}&download=1"
        )
        self.assertTrue(test_print["Content-Disposition"].startswith("attachment"))
        test_pdf = fitz.open(stream=test_print.content, filetype="pdf")
        self.assertEqual(len(test_pdf), 1)
        self.assertGreater(test_pdf[0].rect.width, test_pdf[0].rect.height)
        test_pdf.close()

        clone = self.tenant_post(
            reverse("loans:document_print_profile_clone", args=[profile_revision.pk])
        )
        cloned_revision = LoanDocumentPrintProfileRevision.objects.get(
            profile=profile_revision.profile, version=2
        )
        self.assertRedirects(
            clone,
            reverse(
                "loans:document_print_profile_detail", args=[cloned_revision.pk]
            ),
            fetch_redirect_response=False,
        )
        self.assertEqual(cloned_revision.state, "DRAFT")

        self.tenant_post(
            reverse("loans:document_print_profile_retire", args=[profile_revision.pk])
        )
        profile_revision.refresh_from_db()
        self.assertEqual(profile_revision.state, "RETIRED")
        self.assertFalse(profile_revision.assignments.filter(is_active=True).exists())
        self.assertEqual(
            LoanDocumentPrintProfile.objects.filter(
                workspace=self.tenant, name="Front counter profile"
            ).count(),
            1,
        )

    def test_signature_editor_confirms_each_copy_rechecks_artwork_and_adds_frames(self):
        from apps.tenant_apps.loans.documents import DocumentLayoutValidator
        from apps.tenant_apps.loans.documents.integrity import _includes_required_ticket_signatures
        definition = starter_layout("loan_ticket", schema_version=4, layout_mode="ABSOLUTE_OVERLAY").canonical_dict()
        definition["background_asset_key"] = "stock"
        revision = LoanDocumentLayoutService.create_layout(workspace=self.tenant, document_type="loan_ticket", name="Signature choices", definition=definition, actor=self.owner)
        with fitz.open() as pdf:
            pdf.new_page().insert_text((30, 30), "Borrower and pawnbroker signatures on stationery")
            content = pdf.tobytes()
        for key in ("stock", "changed"):
            LoanDocumentLayoutService.add_asset(revision=revision, key=key, kind="BACKGROUND", content=content, filename="stock.pdf", actor=self.owner)
        url = reverse("loans:document_layout_overlay_designer", args=[revision.pk])
        self.assertContains(self.tenant_get(url), "Save paper and signature choices")
        choices = {"operation": "save_signature_areas", "original_source": "BACKGROUND", "duplicate_source": "FRAMES", "require_interest_rate": "on"}
        self.tenant_post(url, choices)
        revision.refresh_from_db()
        self.assertNotIn("signature_areas", revision.definition)
        self.tenant_post(url, {**choices, "original_confirmed": "on"})
        revision.refresh_from_db()
        self.assertEqual(set(revision.definition["signature_areas"]), {"ORIGINAL"})
        self.assertTrue(all(b["copy_scope"] == "DUPLICATE" for b in revision.definition["blocks"] if b["type"] == "signature"))
        # Both copies now use the background; the original's unchanged evidence
        # needs no redundant confirmation while the duplicate is being changed.
        choices.update(duplicate_source="BACKGROUND", duplicate_confirmed="on")
        self.tenant_post(url, choices)
        revision.refresh_from_db()
        self.assertFalse(any(b["type"] == "signature" for b in revision.definition["blocks"]))
        self.assertTrue(_includes_required_ticket_signatures(DocumentLayoutValidator.load(revision.definition)))
        from apps.tenant_apps.loans.documents.packs import export_layout_pack, import_layout_pack
        imported = import_layout_pack(workspace=self.tenant, content=export_layout_pack(revision), actor=self.owner, name="Imported signature choices")
        self.assertEqual(imported.definition["signature_areas"], revision.definition["signature_areas"])
        LoanDocumentLayoutService.publish(revision=imported, actor=self.owner)
        definition = revision.definition
        definition["background_asset_key"] = "changed"
        revision = LoanDocumentLayoutService.update_draft(revision=revision, definition=definition, actor=self.owner)
        self.assertContains(self.tenant_get(url), "confirm both signature areas again")
        with self.assertRaisesMessage(ValueError, "confirm both signature areas again"):
            LoanDocumentLayoutService.publish(revision=revision, actor=self.owner)
        # A failed reconfirmation changes neither the draft nor its stored hash.
        before = revision.content_hash
        self.tenant_post(url, choices)
        revision.refresh_from_db()
        self.assertEqual(revision.content_hash, before)
        self.tenant_post(url, {**choices, "original_confirmed": "on"})
        revision.refresh_from_db()
        self.assertEqual(revision.definition["signature_areas"]["ORIGINAL"]["asset_key"], "changed")
        self.tenant_post(url, {"operation": "save_signature_areas", "original_source": "FRAMES", "duplicate_source": "FRAMES"})
        revision.refresh_from_db()
        self.assertNotIn("signature_areas", revision.definition)
        signatures = [b for b in revision.definition["blocks"] if b["type"] == "signature"]
        self.assertEqual(len(signatures), 4)
        self.assertFalse(revision.definition["require_interest_rate"])
        self.assertTrue(_includes_required_ticket_signatures(DocumentLayoutValidator.load(revision.definition)))
        published = LoanDocumentLayoutService.publish(revision=revision, actor=self.owner)
        self.tenant_post(url, choices)
        published.refresh_from_db()
        self.assertEqual(published.definition, revision.definition)
        viewer = get_user_model().objects.create_user(username="signature-viewer")
        role, _ = Role.objects.get_or_create(name="Viewer")
        Membership.objects.create(user=viewer, company=self.tenant, role=role)
        self.client.force_login(viewer)
        self.assertEqual(self.tenant_post(url, choices).status_code, 403)

    def test_editor_records_preprinted_business_name_confirmation(self):
        definition = starter_layout('loan_ticket', schema_version=4, layout_mode='ABSOLUTE_OVERLAY').canonical_dict()
        revision = LoanDocumentLayoutService.create_layout(workspace=self.tenant, document_type='loan_ticket',
            name='Preprinted business details', definition=definition, actor=self.owner)
        url = reverse('loans:document_layout_overlay_designer', args=[revision.pk])
        response = self.tenant_post(url, {'operation':'save_signature_areas', 'original_source':'FRAMES',
            'duplicate_source':'FRAMES', 'require_interest_rate':'on', 'business_name_preprinted':'on'})
        self.assertEqual(response.status_code, 302)
        revision.refresh_from_db()
        self.assertTrue(revision.definition['business_name_preprinted'])
        self.assertTrue(self.tenant_get(url).context['signature_form'].initial['business_name_preprinted'])
        definition = revision.definition
        definition['blocks'] = [b for b in definition['blocks'] if b.get('binding') not in {'workspace.name','license.business_name'}]
        LoanDocumentLayoutService.update_draft(revision=revision, definition=definition, actor=self.owner)
        revision.refresh_from_db()
        before = revision.content_hash
        # Removing the confirmation cannot silently waive the missing name.
        self.tenant_post(url, {'operation':'save_signature_areas','original_source':'FRAMES',
            'duplicate_source':'FRAMES','require_interest_rate':'on'})
        revision.refresh_from_db()
        self.assertEqual(revision.content_hash, before)

    def test_signature_editor_duplicate_canvas_uses_its_own_background(self):
        definition = starter_layout("loan_ticket", schema_version=4, layout_mode="ABSOLUTE_OVERLAY").canonical_dict()
        definition["surfaces"] = {"backgrounds": {"original_front": "original", "duplicate_front": "duplicate"}}
        revision = LoanDocumentLayoutService.create_layout(workspace=self.tenant, document_type="loan_ticket", name="Copy backgrounds", definition=definition, actor=self.owner)
        for key in ("original", "duplicate"):
            with fitz.open() as pdf:
                pdf.new_page().insert_text((40, 40), key)
                LoanDocumentLayoutService.add_asset(revision=revision, key=key, kind="BACKGROUND", content=pdf.tobytes(), filename=key + ".pdf", actor=self.owner)
        url = reverse("loans:document_layout_overlay_designer", args=[revision.pk])
        response = self.tenant_get(url + "?copy=DUPLICATE")
        self.assertEqual(response.context["selected_copy"], "DUPLICATE")
        self.assertEqual(response.context["preview_background_key"], "duplicate")
        self.assertContains(response, "Duplicate background preview")
        background = reverse("loans:document_layout_overlay_background", args=[revision.pk])
        original, duplicate = self.tenant_get(background), self.tenant_get(background + "?copy=DUPLICATE")
        self.assertEqual(original.status_code, 200)
        self.assertEqual(duplicate.status_code, 200)
        self.assertNotEqual(original.content, duplicate.content)
        self.assertIn("no-store", duplicate["Cache-Control"])

    def _rich_ticket_fixture(self):
        import hashlib
        from django.core.files.base import ContentFile
        from apps.tenant_apps.loans.models import PawnCollateralPhoto
        from apps.tenant_apps.party.models import PartyAddress

        license, series = self._configured_setup()
        from apps.tenant_apps.loans.services import update_license
        license = update_license(license, actor=self.owner, business_name="Sample Pawnbrokers",
                                 business_address="12 Business Road\nVellore")
        loan = self._loan(license, series, "RICH-19")
        borrower = loan.borrower
        borrower.display_name = "Asha"
        borrower.relation_label, borrower.relation_name = "DAUGHTER_OF", "Ram"
        borrower.primary_phone = "9000000001"
        image = io.BytesIO()
        PillowImage.new("RGB", (80, 60), "blue").save(image, format="PNG")
        content = image.getvalue()
        borrower.profile_photo.save("customer.png", ContentFile(content), save=False)
        borrower.save()
        address = PartyAddress.objects.create(party=borrower, address_type="HOME", line1="10 Test Street", city="Test City", is_default=True)
        item = PawnCollateralItem.objects.create(loan=loan, description="Test ring", metal="GOLD", gross_weight=2, net_weight=2, purity_percentage=90)
        photo = PawnCollateralPhoto(collateral_item=item, original_filename="approved.png", mime_type="image/png", sha256=hashlib.sha256(content).hexdigest(), byte_size=len(content), workflow_source="DRAFT")
        photo.file.save("approved.png", ContentFile(content), save=False)
        photo.save()
        source = {"loan_number": loan.loan_number, "loan_date": str(loan.loan_date), "principal_amount": "10000.25", "monthly_interest_rate": "2", "tenure_months": 3, "borrower_id": borrower.pk,
                  "collateral": [{"item_id": item.pk, "description": "Test ring", "metal": "GOLD", "net_weight": "2.0000", "purity_percentage": "90", "latest_appraised_value": "12000.00", "photo_evidence": [{"photo_id": photo.pk, "sha256": photo.sha256}]}]}
        PawnLoanApprovalSnapshot.objects.create(loan=loan, version=1, payload=source, fingerprint="rich-ticket-evidence", approved_by=self.owner)
        loan.state = "APPROVED"
        loan.save()
        definition = starter_layout("loan_ticket", schema_version=4, layout_mode="ABSOLUTE_OVERLAY").canonical_dict()
        next(block for block in definition["blocks"] if block.get("binding") == "workspace.name")["binding"] = "license.business_name"
        next(block for block in definition["blocks"] if block["type"] == "table")["height_mm"] = 30
        definition["blocks"].extend([
            {"type": "field", "binding": "borrower.contact_block", "show_label": False, "x_mm": 10, "y_mm": 145, "width_mm": 90, "height_mm": 35, "font_size_pt": 8},
            {"type": "image", "binding": "borrower.photo", "x_mm": 110, "y_mm": 145, "width_mm": 30, "height_mm": 30},
            {"type": "image", "binding": "collateral.first_approved_photo", "x_mm": 150, "y_mm": 145, "width_mm": 30, "height_mm": 30},
            {"type": "field", "binding": "loan.principal_words", "x_mm": 10, "y_mm": 183, "width_mm": 180, "height_mm": 15, "font_size_pt": 8},
            {"type": "field", "binding": "license.business_address", "show_label": False, "x_mm": 10, "y_mm": 205, "width_mm": 180, "height_mm": 20, "font_size_pt": 10},
        ])
        revision = LoanDocumentLayoutService.create_layout(workspace=self.tenant, document_type="loan_ticket", name="Rich ticket", definition=definition, actor=self.owner)
        revision = LoanDocumentLayoutService.publish(revision=revision, actor=self.owner)
        LoanDocumentLayoutService.assign(revision=revision, workspace=self.tenant, license=license, series=series, actor=self.owner)
        return loan, revision, photo, address

    def test_rich_ticket_snapshots_contact_and_approved_photos_and_reprints_without_sources(self):
        from apps.tenant_apps.loans.documents.packs import export_layout_pack
        from apps.tenant_apps.loans.services.ticket_documents import prepare_ticket_document
        from apps.tenant_apps.loans.documents import DocumentLayoutValidator

        loan, revision, photo, address = self._rich_ticket_fixture()
        prepared = prepare_ticket_document(loan=loan, layout=DocumentLayoutValidator.load(revision.definition), actor=self.owner)
        self.assertEqual(prepared.source_snapshot["fields"]["loan.principal_words"], "Ten thousand rupees and twenty-five paise only")
        self.assertEqual(prepared.source_snapshot["media"]["collateral.first_approved_photo"]["sha256"], photo.sha256)
        url = reverse("loans:pawn_loan_ticket_pdf", args=[loan.pk])
        first = self.tenant_get(url)
        self.assertEqual(first.status_code, 200)
        issue = LoanDocumentIssue.objects.get(pk=first["X-Rokkad-Document-Issue"])
        self.assertEqual(issue.source_snapshot["customer"]["address_id"], address.pk)
        self.assertEqual(issue.payload_schema_version, 2)
        self.assertEqual(issue.source_snapshot["fields"]["license.business_name"], "Sample Pawnbrokers")
        self.assertEqual(issue.source_snapshot["fields"]["license.business_address"], "12 Business Road\nVellore")
        self.assertEqual(issue.source_snapshot["verification_id"], first["X-Rokkad-Verification-ID"])
        generated_at = issue.source_snapshot["fields"]["document.generated_at"]
        capture = timezone.datetime.fromisoformat(issue.source_snapshot["captured_at"])
        local_capture = timezone.localtime(capture, timezone.get_default_timezone())
        self.assertEqual(generated_at, local_capture.strftime("%d-%m-%Y %H:%M:%S IST (UTC+05:30)"))
        evidence = self.tenant_get(reverse("loans:document_issue_detail", args=[issue.pk]))
        for value in ("Captured at first issue", "10 Test Street", "loans-setup-owner", photo.sha256, issue.source_snapshot["verification_id"]):
            self.assertContains(evidence, value)
        self.assertIn("no-store", evidence["Cache-Control"])
        self.assertNotContains(evidence, photo.file.name)
        history = self.tenant_get(f"{reverse('loans:document_issue_list')}?loan={loan.pk}&q=RICH-19")
        self.assertEqual(history.context["page_obj"].paginator.count, 1)
        self.assertIn("no-store", history["Cache-Control"])
        self.assertEqual(self.tenant_get(f"{reverse('loans:document_issue_list')}?loan={loan.pk}0").context["page_obj"].paginator.count, 0)
        with fitz.open(stream=first.content, filetype="pdf") as pdf:
            for page in pdf:
                self.assertIn("Generated: " + generated_at, page.get_text())
            self.assertIn("10 Test Street", pdf[0].get_text())
            self.assertIn("Sample Pawnbrokers", pdf[0].get_text())
            self.assertIn("12 Business Road", pdf[0].get_text())
            self.assertGreaterEqual(len(pdf[0].get_images()), 1)
            self.assertNotIn("rich-ticket-evidence", pdf[0].get_text())
        self.assertFalse(revision.assets.exists())
        import zipfile
        with zipfile.ZipFile(io.BytesIO(export_layout_pack(revision))) as archive:
            self.assertEqual(archive.namelist(), ["manifest.json"])
            self.assertNotIn("10 Test Street", archive.read("manifest.json").decode())
        loan.borrower.display_name = "Changed customer"
        loan.borrower.save()
        from apps.tenant_apps.loans.services import update_license
        update_license(loan.license, actor=self.owner, business_name="Changed Pawnbrokers", business_address="New address")
        with patch("apps.tenant_apps.loans.web.loan_documents.PawnLoanDocumentProjectionBuilder.loan_ticket", side_effect=AssertionError("Reprint rebuilt mutable facts")), patch("apps.tenant_apps.loans.services.ticket_documents._photo_asset", side_effect=AssertionError("Reprint fetched media")), patch("apps.tenant_apps.loans.services.ticket_documents.timezone.now", return_value=capture + timedelta(days=1)):
            self.assertEqual(self.tenant_get(url).content, first.content)
            self.assertContains(self.tenant_get(reverse("loans:document_issue_detail", args=[issue.pk])), "10 Test Street")
        issue.refresh_from_db()
        self.assertEqual(issue.source_snapshot["fields"]["borrower.name"], "Asha")

    def test_license_business_fields_block_issue_when_blank_but_preview_explains(self):
        from apps.tenant_apps.loans.services.ticket_documents import prepare_ticket_document
        from apps.tenant_apps.loans.documents import DocumentLayoutValidator
        loan, revision, _, _ = self._rich_ticket_fixture()
        loan.license.business_address = ""
        layout = DocumentLayoutValidator.load(revision.definition)
        with self.assertRaisesMessage(ValueError, "printed business name and address"):
            prepare_ticket_document(loan=loan, layout=layout, actor=self.owner)
        prepared = prepare_ticket_document(loan=loan, layout=layout, actor=self.owner, preview=True)
        self.assertEqual(prepared.source_snapshot["fields"]["license.business_address"], "[License business address not configured]")

    def test_rich_ticket_address_selection_does_not_mutate_party_defaults(self):
        from apps.tenant_apps.party.models import PartyAddress
        loan, revision, photo, address = self._rich_ticket_fixture()
        address.is_default = False
        address.save()
        second = PartyAddress.objects.create(party=loan.borrower, address_type="HOME", line1="20 Other Street", city="Other City")
        url = reverse("loans:pawn_loan_ticket_pdf", args=[loan.pk])
        response = self.tenant_get(url)
        self.assertContains(response, "Choose customer address", status_code=409)
        self.assertFalse(LoanDocumentIssue.objects.filter(source_id=str(loan.pk)).exists())
        self.assertEqual(self.tenant_get(f"{url}?address=999999999").status_code, 409)
        response = self.tenant_get(f"{url}?address={second.pk}")
        self.assertEqual(response.status_code, 200)
        issue = LoanDocumentIssue.objects.get(pk=response["X-Rokkad-Document-Issue"])
        self.assertEqual(issue.source_snapshot["customer"]["address_id"], second.pk)
        self.assertFalse(loan.borrower.addresses.filter(is_default=True).exists())

    def test_unreadable_or_changed_photo_blocks_issue_but_preview_has_placeholder(self):
        loan, revision, photo, address = self._rich_ticket_fixture()
        with photo.file.storage.open(photo.file.name, "wb") as file:
            file.write(b"corrupt-selected-photo")
        url = reverse("loans:pawn_loan_ticket_pdf", args=[loan.pk])
        self.assertEqual(self.tenant_get(url).status_code, 409)
        self.assertFalse(LoanDocumentIssue.objects.filter(source_id=str(loan.pk)).exists())
        preview = self.tenant_get(f"{reverse('loans:document_layout_preview', args=[revision.pk])}?loan={loan.pk}")
        self.assertEqual(preview.status_code, 200)
        with fitz.open(stream=preview.content, filetype="pdf") as pdf:
            self.assertIn("Photo unavailable", pdf[0].get_text())

    def test_post_approval_photo_is_not_substituted_for_selected_approved_photo(self):
        from django.core.files.base import ContentFile
        from apps.tenant_apps.loans.models import PawnCollateralPhoto
        from apps.tenant_apps.loans.services.ticket_documents import prepare_ticket_document
        from apps.tenant_apps.loans.documents import DocumentLayoutValidator
        import hashlib
        loan, revision, photo, address = self._rich_ticket_fixture()
        image = io.BytesIO()
        PillowImage.new("RGB", (80, 60), "red").save(image, format="PNG")
        content = image.getvalue()
        later = PawnCollateralPhoto(collateral_item=photo.collateral_item, original_filename="later.png", mime_type="image/png", sha256=hashlib.sha256(content).hexdigest(), byte_size=len(content), workflow_source="POST_APPROVAL")
        later.file.save("later.png", ContentFile(content), save=False)
        later.save()
        prepared = prepare_ticket_document(loan=loan, layout=DocumentLayoutValidator.load(revision.definition), actor=self.owner)
        self.assertEqual(prepared.source_snapshot["media"]["collateral.first_approved_photo"]["photo_id"], photo.pk)
        self.assertNotEqual(prepared.source_snapshot["media"]["collateral.first_approved_photo"]["sha256"], later.sha256)

    def test_optional_photo_allows_absence_but_never_unreadable_selected_media(self):
        from apps.tenant_apps.loans.documents import DocumentLayoutValidator, DocumentAssetError
        from apps.tenant_apps.loans.services.ticket_documents import prepare_ticket_document
        loan, revision, photo, address = self._rich_ticket_fixture()
        loan.borrower.profile_photo = ""
        loan.borrower.save()
        definition = revision.definition
        with self.assertRaisesMessage(DocumentAssetError, "absent"):
            prepare_ticket_document(loan=loan, layout=DocumentLayoutValidator.load(definition), actor=self.owner)
        for block in definition["blocks"]:
            if block.get("binding") in {"borrower.photo", "collateral.first_approved_photo"}:
                block["optional_photo"] = True
        layout = DocumentLayoutValidator.load(definition)
        prepared = prepare_ticket_document(loan=loan, layout=layout, actor=self.owner)
        self.assertEqual(prepared.source_snapshot["media"]["borrower.photo"]["status"], "ABSENT")
        with photo.file.storage.open(photo.file.name, "wb") as file:
            file.write(b"broken")
        with self.assertRaisesMessage(DocumentAssetError, "unavailable"):
            prepare_ticket_document(loan=loan, layout=layout, actor=self.owner)

    def test_approved_photo_reference_cannot_point_at_another_collateral_item(self):
        import copy
        from apps.tenant_apps.loans.documents import DocumentLayoutValidator, DocumentAssetError
        from apps.tenant_apps.loans.services.ticket_documents import prepare_ticket_document
        loan, revision, photo, address = self._rich_ticket_fixture()
        source = copy.deepcopy(loan.approval_snapshots.get().payload)
        # Valid photo ID/checksum, wrong item identity: no fallback or cross-item read.
        source["collateral"][0]["item_id"] += 100000
        PawnLoanApprovalSnapshot.objects.create(loan=loan, version=2, payload=source, fingerprint="wrong-photo-item", approved_by=self.owner)
        with self.assertRaisesMessage(DocumentAssetError, "unavailable"):
            prepare_ticket_document(loan=loan, layout=DocumentLayoutValidator.load(revision.definition), actor=self.owner)

    def test_document_evidence_is_admin_scoped_and_corrupt_artifacts_are_not_served(self):
        from apps.orgs.models import Company
        from apps.tenancy.context import workspace_context, without_workspace_context
        loan, revision, photo, address = self._rich_ticket_fixture()
        ticket_url = reverse("loans:pawn_loan_ticket_pdf", args=[loan.pk])
        response = self.tenant_get(ticket_url)
        issue = LoanDocumentIssue.objects.get(pk=response["X-Rokkad-Document-Issue"])
        detail_url = reverse("loans:document_issue_detail", args=[issue.pk])
        artifact_url = reverse("loans:document_issue_artifact", args=[issue.pk])
        member = get_user_model().objects.create_user(username=f"evidence-member-{uuid.uuid4().hex[:8]}")
        role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=role)
        self.client.force_login(member)
        for url in (detail_url, artifact_url, reverse("loans:document_issue_list")):
            self.assertEqual(self.tenant_get(url).status_code, 403)
        self.client.force_login(self.owner)
        other = Company.objects.create(name="Private evidence workspace", schema_name=f"evidence-{uuid.uuid4().hex[:8]}", owner=self.owner, creator=self.owner)
        with without_workspace_context(), workspace_context(other.pk):
            foreign = LoanDocumentIssue.objects.create(workspace=other, document_type="loan_ticket", source_type="PawnLoan",
                source_id="PRIVATE-SOURCE", source_fingerprint="private-evidence", payload_schema_version=1,
                payload_hash="a" * 64, pdf_hash="b" * 64, artifact="private-evidence.pdf", issued_by=self.owner)
        for name in ("document_issue_detail", "document_issue_artifact"):
            self.assertEqual(self.tenant_get(reverse(f"loans:{name}", args=[foreign.pk])).status_code, 404)
        self.assertNotContains(self.tenant_get(reverse("loans:document_issue_list")), "PRIVATE-SOURCE")
        with issue.artifact.storage.open(issue.artifact.name, "wb") as file:
            file.write(b"altered-artifact-must-not-be-served")
        for url in (ticket_url, artifact_url):
            response = self.tenant_get(url)
            self.assertContains(response, "checksum does not match", status_code=409)
            self.assertNotIn(b"altered-artifact-must-not-be-served", response.content)
            self.assertIn("no-store", response["Cache-Control"])
        # Evidence remains inspectable even when the retained file is unavailable.
        self.assertContains(self.tenant_get(detail_url), issue.pdf_hash)
        with patch("django.core.files.storage.FileSystemStorage.open", side_effect=OSError("private-host-secret")):
            response = self.tenant_get(artifact_url)
            self.assertContains(response, "Stored PDF is unavailable", status_code=409)
            self.assertNotIn(b"private-host-secret", response.content)

    def _activation_pair(self, *, stock="PLAIN", composition="LEGACY_BOTH_SIMPLEX"):
        revision = LoanDocumentLayoutService.create_layout(
            workspace=self.tenant, document_type="loan_ticket", name=uuid.uuid4().hex,
            definition=starter_layout("loan_ticket", schema_version=4, layout_mode="ABSOLUTE_OVERLAY").canonical_dict(), actor=self.owner)
        definition = built_in_print_profile(composition).canonical_dict()
        definition.update(name=uuid.uuid4().hex, schema_version=2, stock_mode=stock)
        profile = LoanDocumentPrintProfileService.create_profile(workspace=self.tenant,
            document_type="loan_ticket", name=definition["name"], definition=definition, actor=self.owner)
        return revision, profile

    def _activate_pair(self, revision, profile, series=None, **changes):
        data = {"profile": profile.pk, "series": series.pk if series else "",
                "layout_hash": revision.content_hash, "profile_hash": profile.content_hash, **changes}
        return self.tenant_post(reverse("loans:ticket_template_use", args=[revision.pk]), data)

    def test_use_template_publishes_pair_once_and_get_is_read_only(self):
        from apps.tenant_apps.loans.models import LoanDocumentLayoutAssignment, LoanDocumentPrintProfileAssignment
        revision, profile = self._activation_pair()
        url = reverse("loans:ticket_template_use", args=[revision.pk])
        page = self.tenant_get(f"{url}?profile={profile.pk}")
        self.assertContains(page, "Use this template")
        self.assertContains(page, "Plain paper")
        self.assertContains(page, "Original")
        self.assertContains(page, "Duplicate")
        self.assertNotContains(page, "ORIGINAL_FRONT")
        self.assertIn("no-store", page["Cache-Control"])
        self.assertFalse(LoanDocumentLayoutAssignment.objects.filter(workspace=self.tenant).exists())
        revision.refresh_from_db()
        self.assertEqual(revision.state, "DRAFT")
        for _ in range(2):
            self.assertEqual(self._activate_pair(revision, profile).status_code, 302)
        revision.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual((revision.state, profile.state), ("PUBLISHED", "PUBLISHED"))
        self.assertEqual(LoanDocumentLayoutAssignment.objects.filter(workspace=self.tenant).count(), 1)
        self.assertEqual(LoanDocumentPrintProfileAssignment.objects.filter(workspace=self.tenant).count(), 1)
        self.assertEqual(LoanDocumentLayoutService.resolve(workspace=self.tenant, document_type="loan_ticket"), revision)
        self.assertEqual(LoanDocumentPrintProfileService.resolve(workspace=self.tenant, document_type="loan_ticket").revision, profile)

    def test_use_template_clone_edit_activate_preserves_old_pdf_and_new_issue_uses_pair(self):
        license, series = self._configured_setup()
        old, old_profile = self._activation_pair()
        self.assertEqual(self._activate_pair(old, old_profile, series).status_code, 302)
        def approved_loan(number):
            loan = self._loan(license, series, number, state="APPROVED")
            PawnLoanApprovalSnapshot.objects.create(loan=loan, version=1, approved_by=self.owner,
                fingerprint=uuid.uuid4().hex, payload={"loan_number": number, "loan_date": str(loan.loan_date),
                    "principal_amount": str(loan.principal_amount), "monthly_interest_rate": str(loan.monthly_interest_rate),
                    "tenure_months": loan.tenure_months, "borrower_id": loan.borrower_id, "collateral": []})
            return loan
        first_loan = approved_loan("ACT-001")
        old_url = reverse("loans:pawn_loan_ticket_pdf", args=[first_loan.pk])
        first = self.tenant_get(old_url)
        self.assertEqual(first.status_code, 200)
        old_issue = LoanDocumentIssue.objects.get(pk=first["X-Rokkad-Document-Issue"])
        before_snapshot, before_hash = old_issue.source_snapshot, old_issue.pdf_hash
        self.assertEqual(self.tenant_post(reverse("loans:document_layout_clone", args=[old.pk])).status_code, 302)
        new = old.layout.revisions.order_by("-version").first()
        block = new.definition["blocks"][0]
        edited = self.tenant_post(reverse("loans:document_layout_overlay_designer", args=[new.pk]), {
            "operation": "save_block", "index": 0, "block_type": "title", "text": "Replacement ticket heading",
            "x_mm": block["x_mm"], "y_mm": block["y_mm"], "width_mm": block["width_mm"], "height_mm": block["height_mm"],
            "font_size_pt": 10, "align": "LEFT", "copy_scope": "BOTH",
        })
        self.assertEqual(edited.status_code, 302)
        new.refresh_from_db()
        new_profile = LoanDocumentPrintProfileService.clone_revision(revision=old_profile, actor=self.owner)
        new_profile = LoanDocumentPrintProfileService.update_draft(revision=new_profile, actor=self.owner,
            definition={**new_profile.definition, "stock_mode": "PREPRINTED"})
        preview = self.tenant_get(f"{reverse('loans:document_layout_preview', args=[new.pk])}?profile={new_profile.pk}&loan={first_loan.pk}")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(self._activate_pair(new, new_profile, series).status_code, 302)
        reprint = self.tenant_get(old_url)
        self.assertEqual(first.content, reprint.content)
        self.assertEqual(first["X-Rokkad-Document-Issue"], reprint["X-Rokkad-Document-Issue"])
        old_issue.refresh_from_db()
        self.assertEqual((old_issue.source_snapshot, old_issue.pdf_hash, old_issue.revision_id, old_issue.print_profile_revision_id),
                         (before_snapshot, before_hash, old.pk, old_profile.pk))
        second = self.tenant_get(reverse("loans:pawn_loan_ticket_pdf", args=[approved_loan("ACT-002").pk]))
        self.assertEqual(second.status_code, 200)
        issue = LoanDocumentIssue.objects.get(pk=second["X-Rokkad-Document-Issue"])
        self.assertEqual((issue.revision_id, issue.print_profile_revision_id), (new.pk, new_profile.pk))
        with fitz.open(stream=second.content, filetype="pdf") as pdf:
            self.assertIn("Replacement ticket heading", pdf[0].get_text())

    def test_use_template_rolls_back_publication_assignment_and_audit_on_profile_failure(self):
        from apps.orgs.audit import AuditLog
        from apps.tenant_apps.loans.models import LoanDocumentLayoutAssignment, LoanDocumentPrintProfileAssignment
        old, old_profile = self._activation_pair()
        self.assertEqual(self._activate_pair(old, old_profile).status_code, 302)
        revision, profile = self._activation_pair(composition="LEGACY_ORIGINAL")
        audits = AuditLog.objects.count()
        layouts = list(LoanDocumentLayoutAssignment.objects.filter(workspace=self.tenant).values())
        profiles = list(LoanDocumentPrintProfileAssignment.objects.filter(workspace=self.tenant).values())
        response = self._activate_pair(revision, profile)
        self.assertContains(response, "must include Original and Duplicate")
        revision.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual((revision.state, profile.state), ("DRAFT", "DRAFT"))
        self.assertEqual(audits, AuditLog.objects.count())
        self.assertEqual(layouts, list(LoanDocumentLayoutAssignment.objects.filter(workspace=self.tenant).values()))
        self.assertEqual(profiles, list(LoanDocumentPrintProfileAssignment.objects.filter(workspace=self.tenant).values()))

    def test_use_template_rejects_stale_review_and_retired_revisions(self):
        revision, profile = self._activation_pair()
        for changes in ({"layout_hash": "stale"}, {"profile_hash": "stale"}):
            self.assertContains(self._activate_pair(revision, profile, **changes), "changed. Review the selection again")
        revision.refresh_from_db()
        self.assertEqual(revision.state, "DRAFT")
        self.assertEqual(self._activate_pair(revision, profile).status_code, 302)
        LoanDocumentLayoutService.retire(revision=revision, actor=self.owner)
        self.assertEqual(self._activate_pair(revision, profile).status_code, 404)

    def test_use_template_preserves_overrides_and_rejects_incompatible_effective_pair(self):
        license, series = self._configured_setup()
        override, override_profile = self._activation_pair()
        self.assertEqual(self._activate_pair(override, override_profile, series).status_code, 302)
        default, default_profile = self._activation_pair(stock="PREPRINTED")
        default = LoanDocumentLayoutService.configure_ticket_signatures(revision=default, actor=self.owner,
            sources={"ORIGINAL": "PREPRINTED", "DUPLICATE": "PREPRINTED"},
            confirmed={"ORIGINAL": True, "DUPLICATE": True})
        self.assertEqual(self._activate_pair(default, default_profile).status_code, 302)
        self.assertEqual(LoanDocumentLayoutService.resolve(workspace=self.tenant, document_type="loan_ticket", license=license, series=series), override)
        # Keep the series' plain-paper profile override, remove only its layout.
        LoanDocumentLayoutService.retire(revision=override, actor=self.owner)
        response = self._activate_pair(default, default_profile)
        self.assertContains(response, "incompatible override")
        # A series activation deliberately replaces both overrides and repairs it.
        self.assertEqual(self._activate_pair(default, default_profile, series).status_code, 302)

    def test_use_template_requires_setup_permission_and_csrf(self):
        from apps.tenant_apps.loans.services.ticket_template_activation import use_ticket_template
        revision, profile = self._activation_pair()
        csrf_client = WorkspaceClient(self.tenant, enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        url = reverse("loans:ticket_template_use", args=[revision.pk])
        self.assertEqual(csrf_client.workspace_post(url, {"profile": profile.pk}).status_code, 403)
        viewer = get_user_model().objects.create_user(username=uuid.uuid4().hex)
        role, _ = Role.objects.get_or_create(name="Viewer")
        Membership.objects.create(user=viewer, company=self.tenant, role=role)
        self.client.force_login(viewer)
        self.assertEqual(self.tenant_get(url).status_code, 403)
        self.assertEqual(self._activate_pair(revision, profile).status_code, 403)
        with self.assertRaises(PermissionDenied):
            use_ticket_template(workspace=self.tenant, revision=revision, profile_revision=profile,
                actor=viewer, layout_hash=revision.content_hash, profile_hash=profile.content_hash)
        revision.refresh_from_db()
        self.assertEqual(revision.state, "DRAFT")

    def test_use_template_hindi_and_cross_workspace_choices(self):
        from django.core.exceptions import ObjectDoesNotExist
        from apps.orgs.models import Company
        from apps.tenancy.context import without_workspace_context, workspace_context
        from apps.tenant_apps.loans.services.ticket_template_activation import use_ticket_template
        revision, profile = self._activation_pair()
        foreign_workspace = Company.objects.create(name="Private template workspace", schema_name=uuid.uuid4().hex,
            owner=self.owner, creator=self.owner)
        with without_workspace_context(), workspace_context(foreign_workspace.pk):
            Membership.objects.create(user=self.owner, company=foreign_workspace, role=Role.objects.get(name="Owner"))
            foreign = LoanDocumentPrintProfileService.create_profile(workspace=foreign_workspace, document_type="loan_ticket",
                name="Private paper settings", definition={**profile.definition, "name": "Private paper settings"}, actor=self.owner)
            foreign_layout = LoanDocumentLayoutService.create_layout(workspace=foreign_workspace, document_type="loan_ticket",
                name="Private ticket", definition=revision.definition, actor=self.owner)
            foreign_license = LoanLicense.objects.create(workspace=foreign_workspace, name="Private", license_number="PRIVATE",
                issued_on=date(2026, 1, 1), expires_on=date(2027, 1, 1))
            foreign_series = LoanSeries.objects.create(license=foreign_license, name="Private series", code="PRIVATE")
        url = reverse("loans:ticket_template_use", args=[revision.pk])
        self.assertNotContains(self.tenant_get(url), "Private paper settings")
        self.assertEqual(self.tenant_get(reverse("loans:ticket_template_use", args=[foreign_layout.pk])).status_code, 404)
        for other_profile, other_series in ((foreign, None), (profile, foreign_series)):
            response = self._activate_pair(revision, other_profile, other_series)
            self.assertTrue(response.context["form"].errors)
            with self.assertRaises(ObjectDoesNotExist):
                use_ticket_template(workspace=self.tenant, revision=revision, profile_revision=other_profile,
                    series=other_series, actor=self.owner, layout_hash=revision.content_hash, profile_hash=other_profile.content_hash)
        self.client.cookies["django_language"] = "hi"
        self.assertContains(self.tenant_get(f"{url}?profile={profile.pk}"), "इस टेम्पलेट का उपयोग करें")
        revision.refresh_from_db()
        self.assertEqual(revision.state, "DRAFT")

    def _configured_setup(self):
        license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="Configured License",
            license_number=f"PBL-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
            created_by=self.owner,
        )
        series = LoanSeries.objects.create(
            license=license, name="Main", code="A"
        )
        for kind, prefix in (
            (LoanDocumentKind.PAWN_LOAN.value, "PL-A-"),
            (LoanDocumentKind.PAWN_LOAN_RELEASE.value, "RL-A-"),
        ):
            LoanNumberSequence.objects.create(
                series=series,
                document_kind=kind,
                prefix=prefix,
                width=5,
                maximum_number=10000,
            )
        return license, series

    def _loan(self, license, series, number, *, state="DRAFT"):
        return PawnLoan.objects.create(
            workspace=self.tenant,
            product_version=ensure_test_product_version(self.tenant),
            license=license,
            series=series,
            borrower=Party.objects.create(display_name=f"Borrower {number}"),
            loan_number=number,
            state=state,
            principal_amount=Decimal("10000.00"),
            monthly_interest_rate=Decimal("2.000000"),
            loan_date=date(2026, 8, 1),
            created_by=self.owner,
            updated_by=self.owner,
        )
