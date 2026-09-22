import copy
import uuid
from decimal import Decimal
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.test import override_settings
from django.urls import reverse

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import without_workspace_context, workspace_context
from apps.tenancy.testing import WorkspaceTestCase, workspace_role_permissions
from apps.tenant_apps.loans.models import LoanNumberSequence, PawnLoanEvent, PawnLoanRelease
from apps.tenant_apps.loans.selectors import get_pawn_loan_balance
from apps.tenant_apps.loans.services import finalize_pawn_loan_accrual, preview_pawn_loan_full_release, release_pawn_loan_in_full, reverse_pawn_loan_event
from apps.tenant_apps.loans.tests import test_collateral_reappraisal as fixtures


@override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class ReleaseConcessionTests(WorkspaceTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        cls.actor = get_user_model().objects.create_user(username="concession-owner")
        tenant.name = "Concession workspace"
        tenant.owner = tenant.creator = cls.actor
        tenant.save()
        Membership.objects.create(company=tenant, user=cls.actor, role=Role.objects.get_or_create(name="Owner")[0])

    def setUp(self):
        super().setUp()
        self.enterContext(override_settings(MEDIA_ROOT=self.enterContext(TemporaryDirectory())))
        fixtures.CollateralReappraisalTests.make_loan(self, method="LATEST_APPRAISAL", age_days=40, product_index=2)
        LoanNumberSequence.objects.create(series=self.loan.series, document_kind="PAWN_LOAN_RELEASE",
                                         prefix="R-", width=5, maximum_number=10000)
        finalize_pawn_loan_accrual(self.loan.pk, period_number=1, actor=self.actor)
        self.quote = preview_pawn_loan_full_release(self.loan.pk)
        self.assertGreaterEqual(self.quote.fees_and_interest_settlement, 5)

    def command(self, **changes):
        values = dict(settlement_amount=self.quote.minimum_settlement - Decimal("5"),
                      interest_concession=Decimal("5"), concession_reason="Accepted interest shortfall",
                      request_key="concession-release", actor=self.actor)
        values.update(changes)
        return release_pawn_loan_in_full(self.loan.pk, **values)

    def test_release_records_cash_and_loss_separately_and_closes(self):
        result = self.command()
        balance = get_pawn_loan_balance(self.loan.pk, as_of_date=self.today)
        self.assertEqual(balance.interest_conceded, 5)
        self.assertEqual(balance.interest_paid, result.release.interest_amount)
        self.assertEqual(balance.interest_paid + balance.interest_conceded, balance.interest_accrued)
        self.assertEqual(balance.principal_paid, 1000)
        self.assertEqual(balance.total_due, 0)
        self.assertTrue(balance.closure_ready)
        self.assertEqual(result.release.settlement_amount, result.release.principal_amount + result.release.interest_amount + result.release.fee_amount)
        self.assertEqual(result.release.interest_concession_reason, "Accepted interest shortfall")
        self.assertEqual(result.loan_event.created_by_id, self.actor.pk)
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        memo = PawnLoanDocumentProjectionBuilder.release_memo(result.release)
        self.assertIn(("Interest lost / concession", "INR 5.00"), memo.details)
        self.assertIn("INR 5.00 forgone: Accepted interest shortfall", dict(memo.details)["Interest settled"])
        from apps.tenant_apps.loans.documents import ConfigurableDocumentRenderer, starter_layout
        import fitz
        rendered = ConfigurableDocumentRenderer.render(memo, starter_layout("release_memo"))
        with fitz.open(stream=rendered.pdf, filetype="pdf") as pdf:
            text = " ".join(page.get_text() for page in pdf)
        self.assertIn("INR 5.00 forgone", text)
        self.assertIn("Accepted interest shortfall", text)

    def test_reversal_restores_interest_cash_principal_and_custody(self):
        before = get_pawn_loan_balance(self.loan.pk, as_of_date=self.today)
        result = self.command()
        frozen = copy.deepcopy(result.loan_event.payload)
        reversal = reverse_pawn_loan_event(result.loan_event.pk, actor=self.actor, reason="Customer did not take collateral")
        after = get_pawn_loan_balance(self.loan.pk, as_of_date=self.today)
        self.assertEqual(after.interest_conceded, 0)
        self.assertEqual(after.interest_paid, before.interest_paid)
        self.assertEqual(after.interest_outstanding, before.interest_outstanding)
        self.assertEqual(after.principal_outstanding, before.principal_outstanding)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, "ACTIVE")
        self.assertFalse(self.loan.collateral_items.exclude(custody_state="IN_VAULT").exists())
        result.loan_event.refresh_from_db()
        self.assertEqual(result.loan_event.payload, frozen)
        self.assertEqual(reversal.reversal_event.payload["values"]["interest_concession"], "5")
        self.assertTrue(reverse_pawn_loan_event(result.loan_event.pk, actor=self.actor, reason="Customer did not take collateral").already_reversed)

    def test_retry_requires_same_amount_concession_reason_and_authority(self):
        first = self.command()
        self.assertEqual(self.command().release.pk, first.release.pk)
        for changes in ({"interest_concession": 4}, {"concession_reason": "Changed"},
                        {"settlement_amount": self.quote.minimum_settlement}):
            with self.subTest(changes=changes), self.assertRaisesMessage(ValueError, "different amount or concession"):
                self.command(**changes)
        with self.assertRaises(PermissionDenied):
            self.command(actor=None)
        self.assertEqual(PawnLoanRelease.objects.count(), 1)

    def test_invalid_loss_or_cash_cannot_reduce_principal_or_silently_settle(self):
        for changes in ({"interest_concession": -1}, {"interest_concession": "NaN"},
                        {"interest_concession": "Infinity"}, {"interest_concession": "1e20"},
                        {"interest_concession": "0.001"}, {"concession_reason": ""},
                        {"concession_reason": "x" * 256},
                        {"settlement_amount": self.quote.minimum_settlement + 1, "interest_concession": 0, "concession_reason": ""},
                        {"settlement_amount": 0, "interest_concession": self.quote.minimum_settlement},
                        {"interest_concession": 0, "concession_reason": ""}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.command(**changes)
        self.assertFalse(PawnLoanRelease.objects.exists())
        self.assertFalse(self.loan.collateral_items.filter(custody_state="WITH_CUSTOMER").exists())

    def test_release_permission_alone_does_not_authorize_concession(self):
        user = get_user_model().objects.create_user(username="release-only-concession")
        role = Role.objects.create(name="Release without concessions")
        Membership.objects.create(company=self.tenant, user=user, role=role)
        grants = Permission.objects.filter(content_type__app_label="orgs", content_type__model="company", codename__in=["data_view", "loan_release"])
        workspace_role_permissions(role, self.tenant).set(grants)
        with self.assertRaises(PermissionDenied):
            self.command(actor=user)
        self.assertFalse(PawnLoanRelease.objects.exists())
        result = self.command(actor=user, settlement_amount=self.quote.minimum_settlement,
                              interest_concession=0, concession_reason="")
        self.assertEqual(result.release.interest_concession_amount, 0)

    def test_later_failure_rolls_back_concession_and_cash_evidence(self):
        before = self.loan.loan_events.count()
        numbers = list(LoanNumberSequence.objects.order_by("pk").values())
        with patch("apps.tenant_apps.loans.services.pawn_release.remove_collateral_from_storage", side_effect=ValueError("Handoff failed")):
            with self.assertRaisesMessage(ValueError, "Handoff failed"):
                self.command()
        self.assertEqual(self.loan.loan_events.count(), before)
        self.assertEqual(list(LoanNumberSequence.objects.order_by("pk").values()), numbers)
        self.assertFalse(PawnLoanRelease.objects.exists())
        self.assertEqual(get_pawn_loan_balance(self.loan.pk, as_of_date=self.today).interest_conceded, 0)

    def test_release_review_errors_and_hindi_do_not_record_collection(self):
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        url = reverse("workspace_loans:pawn_loan_release_full", args=[self.tenant.slug, self.loan.pk])
        before = self.loan.loan_events.count()
        response = client.get(url)
        self.assertContains(response, "Already included in interest and fees above. Do not add it again.")
        self.assertContains(response, "2. Match the collateral")
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertContains(response, 'hx-history="false"')
        response = client.post(url, {})
        self.assertTrue(response.context["form"].is_bound)
        self.assertContains(response, 'href="#id_settlement_amount"')
        self.assertContains(response, 'href="#id_confirm_collateral_handoff"')
        self.assertNotContains(response, 'href="#id_request_key"')
        response = client.post(url, {"request_key": "retained-release-key",
            "settlement_amount": "995.00", "interest_concession": "5", "concession_reason": ""})
        self.assertContains(response, 'value="retained-release-key"')
        self.assertContains(response, 'href="#id_concession_reason"')
        client.cookies["django_language"] = "hi"
        response = client.get(url)
        self.assertContains(response, "वसूली और पूर्ण मुक्ति की पुष्टि करें")
        self.assertEqual(self.loan.loan_events.count(), before)
        self.assertFalse(PawnLoanRelease.objects.exists())
        self.assertFalse(self.loan.collateral_items.filter(custody_state="WITH_CUSTOMER").exists())
        with patch("apps.tenant_apps.loans.web.pawn_release_actions.preview_pawn_loan_full_release", side_effect=ValueError("Settlement unavailable")):
            response = client.get(url)
        self.assertContains(response, "Settlement unavailable")
        self.assertFalse(response.context["release_available"])

    def test_release_staff_cannot_submit_a_hidden_concession(self):
        self.start_active_trial()
        staff = get_user_model().objects.create_user(username="release-form-staff")
        role = Role.objects.create(name="Release form role")
        Membership.objects.create(company=self.tenant, user=staff, role=role)
        workspace_role_permissions(role, self.tenant).set(Permission.objects.filter(
            content_type__app_label="orgs", content_type__model="company",
            codename__in=["data_view", "loan_release"]))
        client = self.make_workspace_client()
        client.force_login(staff)
        url = reverse("workspace_loans:pawn_loan_release_full", args=[self.tenant.slug, self.loan.pk])
        response = client.get(url)
        self.assertFalse(response.context["can_concede_interest"])
        self.assertNotContains(response, 'name="interest_concession"')
        before = self.loan.loan_events.count()
        response = client.post(url, {"request_key": "forged-ui-concession",
            "settlement_amount": format(self.quote.minimum_settlement - 5, ".2f"),
            "interest_concession": "5", "concession_reason": "Not authorized",
            "confirm_collateral_handoff": "on"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.loan.loan_events.count(), before)
        self.assertFalse(PawnLoanRelease.objects.exists())

    def test_http_form_and_release_detail_show_concession(self):
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        url = reverse("workspace_loans:pawn_loan_release_full", kwargs={"workspace_slug": self.tenant.slug, "pk": self.loan.pk})
        self.assertContains(client.get(url), "Interest lost / concession")
        response = client.post(url, {"settlement_amount": format(self.quote.minimum_settlement - 5, ".2f"),
            "interest_concession": "5", "concession_reason": "Accepted & reviewed", "request_key": "http-concession",
            "confirm_collateral_handoff": "on"})
        self.assertEqual(response.status_code, 302, response.context["form"].errors if response.context else "")
        release = PawnLoanRelease.objects.get()
        page = client.get(reverse("workspace_loans:pawn_release_detail", kwargs={"workspace_slug": self.tenant.slug, "release_pk": release.pk}))
        self.assertContains(page, "Interest lost / concession")
        self.assertContains(page, "Accepted &amp; reviewed")

    def test_strict_history_export_does_not_drop_concession(self):
        self.command()
        from apps.tenant_apps.loans.services.history_export import export_history
        with self.assertRaisesMessage(ValueError, "Interest concessions require a wider history profile"):
            export_history(workspace_id=self.tenant.pk, actor=self.actor, loan_id=self.loan.pk)

    def test_all_interest_can_be_conceded_but_cash_still_pays_principal_and_fees(self):
        before = get_pawn_loan_balance(self.loan.pk, as_of_date=self.today)
        concession = self.quote.fees_and_interest_settlement - before.fees_outstanding
        result = self.command(interest_concession=concession,
                              settlement_amount=self.quote.minimum_settlement - concession)
        self.assertEqual(result.release.interest_amount, 0)
        self.assertEqual(result.release.settlement_amount, before.principal_outstanding + before.fees_outstanding)
        self.assertEqual(get_pawn_loan_balance(self.loan.pk, as_of_date=self.today).total_due, 0)

    def test_concession_evidence_is_immutable_and_isolated_under_restricted_role(self):
        result = self.command()
        other = Company.objects.create(name="Other", schema_name="concession-other", owner=self.actor, creator=self.actor)
        quoted = connection.ops.quote_name("concession_rls_" + uuid.uuid4().hex)
        connection.check_constraints()
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {quoted} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT SELECT, UPDATE, DELETE ON loans_pawnloan, loans_pawnloanevent, loans_pawnloanrelease TO {quoted}")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {quoted}")
            self.assertTrue(PawnLoanEvent.objects.filter(pk=result.loan_event.pk).exists())
            for model in (PawnLoanEvent, PawnLoanRelease):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(f'DELETE FROM "{model._meta.db_table}"')
            with self.assertRaises(DatabaseError), transaction.atomic():
                PawnLoanEvent.objects.filter(pk=result.loan_event.pk).update(payload={"values": {"interest_concession": "0"}})
            with self.assertRaises(DatabaseError), transaction.atomic():
                PawnLoanRelease.objects.filter(pk=result.release.pk).update(interest_amount=0)
            with without_workspace_context():
                self.assertFalse(PawnLoanEvent.objects.exists())
                with workspace_context(other.pk):
                    self.assertFalse(PawnLoanEvent.objects.filter(pk=result.loan_event.pk).exists())
                    self.assertFalse(PawnLoanRelease.objects.filter(pk=result.release.pk).exists())
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {quoted}")
                cursor.execute(f"DROP ROLE {quoted}")
