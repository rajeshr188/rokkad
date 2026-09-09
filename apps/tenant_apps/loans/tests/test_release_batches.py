import uuid
import time
from datetime import date
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.test import override_settings
from django.urls import reverse

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.testing import WorkspaceTestCase, workspace_role_permissions
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.models import PawnLoan, PawnLoanRelease, PawnReleaseBatch, PawnReleaseBatchLine, LoanNumberSequence
from apps.tenant_apps.loans.services import approve_pawn_loan, disburse_pawn_loan
from apps.tenant_apps.loans.services.product_catalog import _seed_default_loan_products
from apps.tenant_apps.loans.services.release_batches import preview_release_batch, complete_release_batch
from apps.tenant_apps.loans.tests import test_pawn_draft_ui as draft_tests


@override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class ReleaseBatchTests(WorkspaceTestCase):
    _configured_setup = draft_tests.PawnDraftUiTests._configured_setup
    _payload = draft_tests.PawnDraftUiTests._payload

    @classmethod
    def setup_tenant(cls, tenant):
        user = get_user_model().objects.create_user(username="batch-owner")
        tenant.name = "Batch workspace"
        tenant.owner = tenant.creator = user
        tenant.save()
        role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.create(company=tenant, user=user, role=role)

    def setUp(self):
        super().setUp()
        self.enterContext(override_settings(MEDIA_ROOT=self.enterContext(TemporaryDirectory())))
        self.enterContext(patch("django.utils.timezone.localdate", return_value=date(2026, 7, 18)))
        self.owner = self.tenant.owner
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.owner)
        self.product_version = _seed_default_loan_products()[0]
        type(self.product_version).objects.filter(pk=self.product_version.pk).update(status="ACTIVE")
        self.loans = []
        for index in range(2):
            self.party = Party.objects.create(display_name=f"Borrower {index}")
            license, series = self._configured_setup()
            for sequence in LoanNumberSequence.objects.filter(series=series):
                sequence.prefix = f"{index}-{sequence.prefix}"
                sequence.save(update_fields=["prefix"])
            response = self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
            if response.status_code != 302:
                self.fail(str(response.context["form"].errors) if response.context and "form" in response.context else str(response.context))
            loan = PawnLoan.objects.latest("pk")
            approve_pawn_loan(loan.pk, actor=self.owner)
            disburse_pawn_loan(loan.pk, effective_date=date(2026, 7, 18), actor=self.owner)
            self.loans.append(loan)

    def preview(self):
        return preview_release_batch(workspace=self.tenant, actor=self.owner, loan_ids=[loan.pk for loan in self.loans])

    def command(self):
        return dict(workspace=self.tenant, actor=self.owner, request_key=uuid.uuid4(),
                    quote_token=self.preview()["quote_token"], paid_by="Family payer", payment_reference="UPI-123",
                    payment_confirmed=True, collectors=[{
                        "loan_id": loan.pk, "collector_is_borrower": index == 0,
                        "collector_name": "Authorized spouse", "relationship": "Spouse",
                        "authorization_note": "Borrower confirmed collection in person", "handover_confirmed": True,
                    } for index, loan in enumerate(self.loans)])

    def test_complete_and_retry_keep_individual_receipts_collectors_and_exact_total(self):
        command = self.command()
        batch = complete_release_batch(**command)
        self.assertEqual(batch.lines.count(), 2)
        self.assertEqual(PawnLoan.objects.filter(state="CLOSED").count(), 2)
        self.assertEqual(sum(line.release.settlement_amount for line in batch.lines.all()), batch.total_amount)
        self.assertEqual(list(batch.lines.values_list("collector_name", flat=True)), ["Borrower 0", "Authorized spouse"])
        self.assertEqual(complete_release_batch(**command).pk, batch.pk)
        self.assertEqual(PawnLoanRelease.objects.count(), 2)
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        payload = PawnLoanDocumentProjectionBuilder.release_memo(batch.lines.last().release)
        self.assertIn(("Collected by", "Authorized spouse"), payload.details)
        command["paid_by"] = "Changed payer"
        with self.assertRaisesMessage(ValueError, "different details"):
            complete_release_batch(**command)

    def test_later_failure_rolls_back_every_release_event_custody_and_number(self):
        from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full
        command = self.command()
        before = list(LoanNumberSequence.objects.order_by("pk").values())
        calls = []
        def fail_second(*args, **kwargs):
            calls.append(args[0])
            if len(calls) == 2:
                raise ValueError("Second loan blocked")
            return release_pawn_loan_in_full(*args, **kwargs)
        with patch("apps.tenant_apps.loans.services.release_batches.release_pawn_loan_in_full", side_effect=fail_second):
            with self.assertRaisesMessage(ValueError, "Second loan blocked"):
                complete_release_batch(**command)
        self.assertFalse(PawnReleaseBatch.objects.exists())
        self.assertFalse(PawnLoanRelease.objects.exists())
        self.assertEqual(PawnLoan.objects.filter(state="ACTIVE").count(), 2)
        self.assertEqual(before, list(LoanNumberSequence.objects.order_by("pk").values()))
        self.assertFalse(self.loans[0].collateral_items.filter(custody_state="WITH_CUSTOMER").exists())

    def test_expired_and_tampered_quotes_fail_but_completed_retry_survives_expiry(self):
        command = self.command()
        with patch("django.core.signing.time.time", return_value=time.time() + 601):
            with self.assertRaisesMessage(ValueError, "expired"):
                complete_release_batch(**command)
        self.assertFalse(PawnReleaseBatch.objects.exists())
        with self.assertRaisesMessage(ValueError, "invalid"):
            complete_release_batch(**{**command, "quote_token": command["quote_token"] + "tampered"})
        batch = complete_release_batch(**command)
        with patch("django.core.signing.time.time", return_value=time.time() + 601):
            self.assertEqual(complete_release_batch(**command).pk, batch.pk)
        self.assertEqual(PawnLoanRelease.objects.count(), 2)

    def test_stale_quote_missing_handover_and_authorization_fail_without_releases(self):
        command = self.command()
        command["collectors"][1]["authorization_note"] = ""
        with self.assertRaises(ValueError):
            complete_release_batch(**command)
        command = self.command()
        command["collectors"][0]["handover_confirmed"] = False
        with self.assertRaises(ValueError):
            complete_release_batch(**command)
        command = self.command()
        PawnLoan.objects.filter(pk=self.loans[0].pk).update(updated_at="2026-07-18T10:00:00Z")
        with self.assertRaisesMessage(ValueError, "changed"):
            complete_release_batch(**command)
        self.assertFalse(PawnLoanRelease.objects.exists())
        self.assertFalse(PawnReleaseBatch.objects.exists())

    def test_revoked_grants_removed_members_and_cross_workspace_quotes_are_denied(self):
        command = self.command()
        member = get_user_model().objects.create_user(username="batch-staff")
        role, _ = Role.objects.get_or_create(name="Admin")
        Membership.objects.create(company=self.tenant, user=member, role=role)
        command["actor"] = member
        workspace_role_permissions(role, self.tenant).clear()
        with self.assertRaises(PermissionDenied):
            complete_release_batch(**command)
        Membership.objects.filter(company=self.tenant, user=member).delete()
        with self.assertRaises(PermissionDenied):
            complete_release_batch(**command)
        other = Company.objects.create(name="Other batch workspace", schema_name="other-batch", owner=self.owner, creator=self.owner)
        from apps.tenant_apps.loans.services.release_batches import decode_quote
        with self.assertRaises(ValueError):
            decode_quote(command["quote_token"], workspace=other)
        with self.assertRaises(ValueError):
            preview_release_batch(workspace=self.tenant, actor=self.owner, loan_ids=[999999])

    def test_http_preview_completion_history_and_search(self):
        url = reverse("loans:release_batch_create")
        response = self.client.get(reverse("loans:release_batch_search"), {"q": "Borrower"})
        self.assertEqual(len(response.json()["results"]), 2)
        page = self.client.post(url, {"action": "preview", "loans": [loan.pk for loan in self.loans]}, HTTP_HX_REQUEST="true")
        self.assertContains(page, "Total to collect")
        self.assertNotContains(page, "<html")
        header = page.context["confirmation_form"]
        payload = {"action": "complete", "request_key": header["request_key"].value(), "quote_token": header["quote_token"].value(), "paid_by": "Payer", "payment_confirmed": "on"}
        for loan in self.loans:
            payload.update({f"collector_{loan.pk}-loan_id": loan.pk, f"collector_{loan.pk}-collector_type": "borrower", f"collector_{loan.pk}-handover_confirmed": "on"})
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(response.url), "Borrower 1")
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.assertEqual(self.client.get(reverse("loans:release_batch_search")).json()["results"], [])
        self.assertContains(self.client.get(reverse("loans:release_batch_list")), "Payer")

    def test_database_guards_and_restricted_role_isolation(self):
        batch = complete_release_batch(**self.command())
        other = Company.objects.create(name="RLS other", schema_name="batch-rls-other", owner=self.owner, creator=self.owner)
        quoted_role = connection.ops.quote_name("batch_rls_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted_role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON loans_pawnreleasebatch, loans_pawnreleasebatchline, loans_pawnloanrelease TO {quoted_role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted_role}")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {quoted_role}")
            self.assertEqual(PawnReleaseBatch.objects.count(), 1)
            self.assertEqual(PawnReleaseBatchLine.objects.count(), 2)
            from apps.tenancy.context import without_workspace_context
            with without_workspace_context():
                self.assertFalse(PawnReleaseBatch.objects.exists())
                self.assertFalse(PawnReleaseBatchLine.objects.exists())
            self.assertFalse(PawnReleaseBatch.objects.filter(workspace=other).exists())
            for model in (PawnReleaseBatch, PawnReleaseBatchLine):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    model.objects.update(workspace=other)
                with self.assertRaises(DatabaseError), transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(f'DELETE FROM "{model._meta.db_table}"')
            with self.assertRaises(DatabaseError), transaction.atomic():
                PawnReleaseBatch.objects.bulk_create([PawnReleaseBatch(workspace=other, request_key=uuid.uuid4(), request_fingerprint="x" * 64, total_amount=0, paid_by="X", effective_date=date(2026, 7, 18), created_by=self.owner)])
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {quoted_role}")
                cursor.execute(f"DROP ROLE {quoted_role}")
