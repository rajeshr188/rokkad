import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection, transaction
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.utils import timezone

from apps.orgs.models import Membership, Role
from apps.tenancy.testing import WorkspaceTestCase, workspace_role_permissions
from apps.tenant_apps.loans.domain.valuation_freshness import evidence_freshness
from apps.tenant_apps.loans.models import CollateralAppraisal, LoanLicense, LoanNumberSequence, LoanSeries, LoanMonitoringPolicy, PawnLoan, PawnCollateralItem
from apps.tenant_apps.loans.services import (CollateralDraftInput, CreatePawnDraftCommand, create_pawn_draft,
    append_collateral_photo, approve_pawn_loan, disburse_pawn_loan, create_pawn_loan_economic_policy,
    create_pawn_metal_interest_rate_policy)
from apps.tenant_apps.loans.services.product_catalog import _seed_default_loan_products
from apps.tenant_apps.loans.services.collateral_reappraisal import record_collateral_reappraisal
from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
from apps.tenant_apps.loans.selectors.monitoring_policy import LoanRiskAssessmentError
from apps.tenant_apps.loans.web.reappraisal import collateral_reappraisal
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.rates.models import Rate, RateSource


class FreshnessBoundaryTests(SimpleTestCase):
    def test_age_limit_is_inclusive_and_zero_means_same_day(self):
        today = timezone.localdate()
        for age, limit, expected in ((7, 7, "CURRENT"), (8, 7, "STALE"), (0, 0, "CURRENT"), (1, 0, "STALE"), (-1, 7, "FUTURE")):
            self.assertEqual(evidence_freshness(value=1, effective_date=today - timedelta(days=age), as_of_date=today, maximum_age_days=limit), (expected, age))


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class CollateralReappraisalTests(WorkspaceTestCase):
    @classmethod
    def get_test_schema_name(cls):
        return "collateral-reappraisal"

    @classmethod
    def setup_tenant(cls, tenant):
        cls.actor = get_user_model().objects.create_user(username="reappraisal-owner")
        tenant.name = "Reappraisal"
        tenant.owner = tenant.creator = cls.actor
        tenant.save()
        Membership.objects.create(user=cls.actor, company=tenant, role=Role.objects.get_or_create(name="Owner")[0])

    def make_loan(self, method="LOWER_OF_CALCULATED_AND_APPRAISAL", *, product_index=0):
        self.today = timezone.localdate()
        loan_date = self.today - timedelta(days=100)
        borrower = Party.objects.create(display_name="Borrower")
        license = LoanLicense.objects.create(workspace=self.tenant, name="Main", license_number=uuid.uuid4().hex, issued_on=loan_date, expires_on=self.today + timedelta(days=365))
        series = LoanSeries.objects.create(license=license, name="Main", code="A")
        LoanNumberSequence.objects.create(series=series, document_kind="PAWN_LOAN", prefix="PL-", width=5, maximum_number=10000)
        product = _seed_default_loan_products()[product_index]
        type(product).objects.filter(pk=product.pk).update(status="ACTIVE")
        create_pawn_loan_economic_policy(workspace=self.tenant, license=license, valuation_method=method, maximum_ltv_ratio=Decimal("0.8"), advance_interest_periods=0, effective_from=loan_date, actor=self.actor)
        create_pawn_metal_interest_rate_policy(workspace=self.tenant, license=license, metal="GOLD", monthly_interest_rate=Decimal("2"), effective_from=loan_date, actor=self.actor)
        self.source = RateSource.objects.create(name="Market", location="Local")
        self.quote = Rate.objects.create(rate_source=self.source, buying_rate=3000, selling_rate=3100, effective_at=timezone.now() - timedelta(days=100))
        self.loan = create_pawn_draft(CreatePawnDraftCommand(workspace_id=self.tenant.pk, borrower_id=borrower.pk, license_id=license.pk,
            series_id=series.pk, product_version_id=product.pk, principal_amount=Decimal("1000"), monthly_interest_rate=Decimal("2"), loan_date=loan_date, tenure_months=12,
            collateral=(CollateralDraftInput(description="Gold ring", metal="GOLD", gross_weight=Decimal("1"), net_weight=Decimal("1"), purity_percentage=Decimal("100"), latest_appraised_value=Decimal("2000"), allocated_principal=Decimal("1000")),)), actor=self.actor)
        self.item = self.loan.collateral_items.get()
        append_collateral_photo(self.item.pk, upload=SimpleUploadedFile("ring.jpg", b"\xff\xd8\xff\xe0evidence", content_type="image/jpeg"), actor=self.actor)
        self.approval = approve_pawn_loan(self.loan.pk, actor=self.actor)
        disburse_pawn_loan(self.loan.pk, effective_date=loan_date, actor=self.actor)
        self.original = self.item.appraisals.get()
        self.policy = LoanMonitoringPolicy.objects.create(workspace=self.tenant, version=1, effective_from=loan_date, compliance_profile="test",
            ltv_warning_ratio=Decimal("0.7"), ltv_breach_ratio=Decimal("0.8"), ltv_critical_ratio=Decimal("0.9"),
            eligible_custody_states=["IN_VAULT", "WITH_FUNDING_LENDER"], severity_mapping={"strategy": "derived-v1"}, created_by=self.actor)

    def reassess(self, **changes):
        data = dict(loan_id=self.loan.pk, item_id=self.item.pk, actor=self.actor, appraised_value=Decimal("2500"),
            method="PHYSICAL_INSPECTION", evidence_reference="Inspection 100", review_notes="Rechecked condition and value", expected_version=1)
        data.update(changes)
        return record_collateral_reappraisal(**data)

    def valuation(self):
        return get_pawn_loan_collateral_valuation(self.loan.pk, as_of_date=self.today)

    def test_schedule_allocations_are_two_reads_and_keep_reversal_dates(self):
        from apps.tenant_apps.loans.selectors.obligation_state import calculate_obligation_state_as_of
        from apps.tenant_apps.loans.services import record_pawn_loan_repayment, reverse_pawn_loan_event
        self.make_loan(product_index=1)
        schedule = self.loan.repayment_schedules.get()
        self.assertEqual(schedule.obligations.count(), 12)
        with self.assertNumQueries(2):
            before = calculate_obligation_state_as_of(schedule, self.today)
        yesterday = calculate_obligation_state_as_of(schedule, self.today - timedelta(days=1))
        payment = record_pawn_loan_repayment(self.loan.pk, amount="100", request_key="prefetch-payment", actor=self.actor)
        with self.assertNumQueries(2):
            paid = calculate_obligation_state_as_of(schedule, self.today)
        self.assertEqual(before.remaining.total - paid.remaining.total, Decimal("100"))
        self.assertEqual(calculate_obligation_state_as_of(schedule, self.today - timedelta(days=1)), yesterday)
        reverse_pawn_loan_event(payment.loan_event.pk, reason="Test repayment correction", actor=self.actor)
        with self.assertNumQueries(2):
            self.assertEqual(calculate_obligation_state_as_of(schedule, self.today), before)

    def test_stale_evidence_is_unknown_and_new_evidence_restores_coverage(self):
        self.make_loan()
        stale = self.valuation()
        self.assertIsNone(stale.eligible_collateral_value)
        self.assertIn("STALE_RATE", stale.ltv.blockers)
        self.assertIn("STALE_APPRAISAL", stale.ltv.blockers)
        self.assertEqual(stale.items[0].calculated_value, Decimal("3000"))
        fresh = Rate.objects.create(rate_source=self.source, buying_rate=3200, selling_rate=3300)
        self.assertIsNone(self.valuation().eligible_collateral_value)
        snapshot = refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
        appraisal = self.reassess()
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, "STALE")
        self.assertEqual(self.valuation().eligible_collateral_value, Decimal("2500"))
        self.assertEqual(appraisal.valuation_context["rate_id"], fresh.pk)
        self.assertEqual(Decimal(appraisal.valuation_context["suggested_metal_value"]), Decimal("3200"))
        self.assertEqual(appraisal.supersedes_id, self.original.pk)
        self.item.refresh_from_db()
        self.assertEqual(self.item.latest_appraised_value, Decimal("2000"))
        original_payload = self.approval.payload
        self.approval.refresh_from_db()
        self.assertEqual(self.approval.payload, original_payload)
        old = get_pawn_loan_collateral_valuation(self.loan.pk, as_of_date=self.today - timedelta(days=99))
        self.assertEqual(old.items[0].appraisal_id, self.original.pk)

    def test_appraisal_only_does_not_require_a_fresh_quote(self):
        self.make_loan("LATEST_APPRAISAL")
        self.reassess()
        result = self.valuation()
        self.assertEqual(result.eligible_collateral_value, Decimal("2500"))
        self.assertEqual(result.items[0].rate_status, "STALE")
        self.assertNotIn("STALE_RATE", result.ltv.blockers)

    def test_calculated_only_does_not_require_a_fresh_appraisal(self):
        self.make_loan("CALCULATED_METAL_VALUE")
        Rate.objects.create(rate_source=self.source, buying_rate=3200, selling_rate=3300)
        self.assertEqual(self.valuation().eligible_collateral_value, Decimal("3200"))

    def test_missing_monitoring_policy_fails_closed(self):
        self.make_loan()
        with patch("apps.tenant_apps.loans.selectors.collateral_valuation.resolve_monitoring_policy", side_effect=LoanRiskAssessmentError("No policy")):
            self.assertIn("MONITORING_POLICY_UNAVAILABLE", self.valuation().ltv.blockers)

    def test_permissions_stale_submission_and_lifecycle_are_enforced(self):
        self.make_loan()
        with self.assertRaises(PermissionDenied):
            self.reassess(actor=None)
        with self.assertRaises(ValidationError):
            self.reassess(review_notes="")
        self.reassess()
        with self.assertRaises(ValidationError):
            self.reassess()
        self.assertEqual(self.item.appraisals.count(), 2)
        PawnLoan.objects.filter(pk=self.loan.pk).update(state="CLOSED")
        with self.assertRaises(ValidationError):
            self.reassess(expected_version=2)

    def test_restricted_runtime_cannot_change_or_cross_link_appraisal_evidence(self):
        self.make_loan()
        other_item = PawnCollateralItem.objects.create(loan=self.loan, description="Other item", metal="GOLD", gross_weight=1, net_weight=1, purity_percentage=100)
        role = connection.ops.quote_name("reappraisal_rls_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        try:
            for sql, params in (("UPDATE loans_collateralappraisal SET appraised_value=1 WHERE id=%s", [self.original.pk]),
                                ("DELETE FROM loans_collateralappraisal WHERE id=%s", [self.original.pk])):
                with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute(sql, params)
            with self.assertRaises(DatabaseError), transaction.atomic():
                CollateralAppraisal.objects.bulk_create([CollateralAppraisal(workspace_id=self.tenant.pk + 10000,
                    collateral_item=self.item, version=2, appraised_value=1, method="MANUAL", effective_at=timezone.now())])
            with self.assertRaises(DatabaseError), transaction.atomic():
                CollateralAppraisal.objects.bulk_create([CollateralAppraisal(workspace=self.tenant,
                    collateral_item=other_item, supersedes=self.original, version=1, appraised_value=1, method="MANUAL", effective_at=timezone.now())])
            appraisal = self.reassess()
            self.assertEqual(appraisal.created_by, self.actor)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    def test_form_get_is_read_only_and_post_records_one_review(self):
        self.make_loan()
        request = RequestFactory().get("/reappraise/")
        request.workspace, request.user = self.tenant, self.actor
        response = collateral_reappraisal(request, self.loan.pk, self.item.pk)
        self.assertContains(response, "Appraisal history")
        self.assertEqual(self.item.appraisals.count(), 1)
        request = RequestFactory().post("/reappraise/", dict(appraised_value="2500", method="PHYSICAL_INSPECTION", evidence_reference="Inspection 100", review_notes="Rechecked", expected_version=1))
        request.workspace, request.user = self.tenant, self.actor
        response = collateral_reappraisal(request, self.loan.pk, self.item.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.item.appraisals.count(), 2)

    def test_view_only_member_can_read_history_but_cannot_approve(self):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from apps.orgs.models import Company
        self.make_loan()
        viewer = get_user_model().objects.create_user(username="appraisal-viewer")
        role = Role.objects.create(name="AppraisalViewer-" + uuid.uuid4().hex[:8])
        permission, _ = Permission.objects.get_or_create(content_type=ContentType.objects.get_for_model(Company), codename="data_view", defaults={"name": "View data"})
        workspace_role_permissions(role, self.tenant).add(permission)
        Membership.objects.create(user=viewer, company=self.tenant, role=role)
        request = RequestFactory().get("/reappraise/")
        request.workspace, request.user = self.tenant, viewer
        response = collateral_reappraisal(request, self.loan.pk, self.item.pk)
        self.assertContains(response, "Appraisal history")
        self.assertNotContains(response, ">Approve new appraisal</button>")
        self.assertEqual(response["Cache-Control"], "no-store")
        request.method = "POST"
        with self.assertRaises(PermissionDenied):
            collateral_reappraisal(request, self.loan.pk, self.item.pk)
        with self.assertRaises(PermissionDenied):
            self.reassess(actor=viewer)
