import time
import uuid
from datetime import date
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import connection, transaction, DatabaseError
from django.urls import reverse

from apps.tenancy.context import without_workspace_context
from apps.tenant_apps.loans.models import PaperClosureTransition, PawnReleaseBatch, PawnLoanRelease, LoanNumberSequence
from apps.tenant_apps.loans.services.paper_closures import preview_paper_closures, complete_paper_closures, set_paper_transition
from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
from apps.tenant_apps.loans.tests.test_release_batches import ReleaseBatchTests
from apps.tenant_apps.loans.tests.test_opening_release import OpeningReleaseFixture


class PaperClosureTests(ReleaseBatchTests):
    def test_fifty_real_loans_preview_and_complete(self):
        from apps.tenant_apps.loans.models import PawnLoan
        from apps.tenant_apps.loans.services import approve_pawn_loan, disburse_pawn_loan
        license, series = self.loans[0].license, self.loans[0].series
        for index in range(48):
            response = self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
            self.assertEqual(response.status_code, 302)
            loan = PawnLoan.objects.latest("pk")
            approve_pawn_loan(loan.pk, actor=self.owner)
            disburse_pawn_loan(loan.pk, effective_date=date(2026, 7, 18), actor=self.owner)
            self.loans.append(loan)
        started = time.monotonic()
        command = self.paper_command()
        preview_seconds = time.monotonic() - started
        started = time.monotonic()
        batch = complete_paper_closures(**command)
        complete_seconds = time.monotonic() - started
        self.assertEqual(batch.lines.count(), 50)
        self.assertEqual(PawnLoan.objects.filter(state="CLOSED").count(), 50)
        self.assertEqual(sum(line.release.settlement_amount for line in batch.lines.all()), batch.total_amount)
        print(f"PAPER_50 preview={preview_seconds:.3f}s complete={complete_seconds:.3f}s")

    def test_staff_permissions_csrf_and_date_change(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        from apps.orgs.models import Membership, Role, Company
        from apps.tenancy.testing import workspace_role_permissions
        member = get_user_model().objects.create_user(username="paper-clerk")
        role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(company=self.tenant, user=member, role=role)
        grants = workspace_role_permissions(role, self.tenant)
        grants.clear()
        grants.add(Permission.objects.get(content_type__app_label="orgs", content_type__model="company", codename="data_view"))
        command = self.paper_command()
        with self.assertRaises(PermissionDenied):
            complete_paper_closures(**{**command, "actor": member})
        self.client.handler.enforce_csrf_checks = True
        url = reverse("workspace_loans:paper_closure_create", kwargs={"workspace_slug": self.tenant.slug})
        self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.client.handler.enforce_csrf_checks = False
        other = Company.objects.create(name="Other paper workspace", schema_name=uuid.uuid4().hex, owner=self.owner, creator=self.owner)
        with self.assertRaises(PermissionDenied):
            complete_paper_closures(**{**command, "workspace": other})
        self.client.force_login(member)
        self.assertEqual(self.client.get(url).status_code, 403)
        settings_url = reverse("workspace_loans:paper_closure_settings", kwargs={"workspace_slug": self.tenant.slug})
        self.assertEqual(self.client.post(settings_url, {"retired": "on"}).status_code, 403)

    def paper_command(self, loans=None, day=date(2026, 7, 18)):
        loans = loans or self.loans
        preview = preview_paper_closures(workspace=self.tenant, actor=self.owner,
            loan_ids=[loan.pk for loan in loans], closure_date=day)
        return dict(workspace=self.tenant, actor=self.owner, request_key=uuid.uuid4(), quote_token=preview["token"],
            confirmed=True, paper_reference="Book 2 / page 7", rows=[dict(loan_id=row["loan"].pk,
                amount=str(row["amount"]), paid_by=row["loan"].borrower.display_name,
                collector_name=row["loan"].borrower.display_name) for row in preview["rows"]])

    def test_backdated_paper_closure_retry_reversal_and_print_evidence(self):
        with patch("django.utils.timezone.localdate", return_value=date(2026, 7, 20)):
            command = self.paper_command()
            batch = complete_paper_closures(**command)
            self.assertEqual(batch.effective_date, date(2026, 7, 18))
            self.assertEqual(batch.mode, "PAPER")
            self.assertEqual(batch.lines.count(), 2)
            self.assertEqual(complete_paper_closures(**command).pk, batch.pk)
            release = batch.lines.first().release
            self.assertIsNone(release.items.get().returned_at)
            self.assertEqual(release.loan_event.payload["release"]["paper_closure"]["date_precision"], "DAY")
            from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
            payload = PawnLoanDocumentProjectionBuilder.release_memo(release)
            self.assertIn(("Paper reference", "Book 2 / page 7"), payload.details)
            reverse_pawn_loan_event(release.loan_event_id, actor=self.owner, reason="Wrong paper line")
            release.loan.refresh_from_db()
            self.assertEqual(release.loan.state, "ACTIVE")
            self.assertEqual(batch.lines.count(), 2)
            self.assertEqual(complete_paper_closures(**command).pk, batch.pk)

    def test_late_failure_rolls_back_numbers_and_first_closure(self):
        command = self.paper_command()
        command["rows"][1]["amount"] = "1"
        before = list(LoanNumberSequence.objects.order_by("pk").values())
        with self.assertRaisesMessage(ValueError, "must equal"):
            complete_paper_closures(**command)
        self.assertFalse(PawnReleaseBatch.objects.exists())
        self.assertFalse(PawnLoanRelease.objects.exists())
        self.assertEqual(before, list(LoanNumberSequence.objects.order_by("pk").values()))

    def test_quote_expiry_stale_dates_and_fifty_one_boundary(self):
        command = self.paper_command()
        with patch("django.core.signing.time.time", return_value=time.time() + 601):
            with self.assertRaisesMessage(ValueError, "expired"):
                complete_paper_closures(**command)
        for day in (date(2026, 7, 17), date(2026, 7, 19)):
            if day.day == 17:
                preview = preview_paper_closures(workspace=self.tenant, actor=self.owner, loan_ids=[self.loans[0].pk], closure_date=day)
                self.assertIn("precede", preview["rows"][0]["error"])
            else:
                with self.assertRaisesMessage(ValueError, "today or earlier"):
                    preview_paper_closures(workspace=self.tenant, actor=self.owner, loan_ids=[self.loans[0].pk], closure_date=day)
        with self.assertRaisesMessage(ValueError, "1–50"):
            preview_paper_closures(workspace=self.tenant, actor=self.owner, loan_ids=list(range(1, 52)), closure_date=date(2026, 7, 18))
        self.loans[0].refresh_from_db()
        self.loans[0].save()
        with self.assertRaisesMessage(ValueError, "changed"):
            complete_paper_closures(**command)

    def test_retirement_rechecks_inflight_review_and_requires_exception(self):
        command = self.paper_command()
        set_paper_transition(workspace=self.tenant, actor=self.owner, system_first_date=date(2026, 7, 18), retired=True, reason="Book reconciled")
        with self.assertRaisesMessage(ValueError, "exception reason"):
            complete_paper_closures(**command)
        preview = preview_paper_closures(workspace=self.tenant, actor=self.owner,
            loan_ids=[self.loans[0].pk], closure_date=date(2026, 7, 18), exception_reason="Late paper discovery")
        command.update(quote_token=preview["token"], rows=command["rows"][:1])
        batch = complete_paper_closures(**command)
        self.assertEqual(batch.exception_reason, "Late paper discovery")

    def test_http_partial_selection_retains_other_rows_and_exports_csv(self):
        url = reverse("workspace_loans:paper_closure_create", kwargs={"workspace_slug": self.tenant.slug})
        self.assertContains(self.client.get(url), "Record paper closures")
        data = {"action": "review", "loans": [str(loan.pk) for loan in self.loans],
            "closure_date": "2026-07-18", "paper_reference": "Page 8", "request_key": str(uuid.uuid4())}
        response = self.client.post(url, data)
        self.assertContains(response, "Check against your paper book")
        self.assertEqual(response.context["rows"][0]["form"]["paid_by"].value(), self.loans[0].borrower.display_name)
        data.update(action="complete", quote_token=response.context["header"]["quote_token"].value(), confirmed="on")
        for index, row in enumerate(response.context["rows"]):
            for name in row["form"].fields:
                if name != "include":
                    data[f'row_{row["loan"].pk}-{name}'] = row["form"][name].value() or ""
            if index == 0:
                data[f'row_{row["loan"].pk}-include'] = "on"
        response = self.client.post(url, data)
        self.assertContains(response, "1 closures recorded")
        self.assertEqual(len(response.context["rows"]), 1)
        self.assertEqual(response.context["rows"][0]["loan"].pk, self.loans[1].pk)
        batch = PawnReleaseBatch.objects.get()
        csv_url = reverse("workspace_loans:paper_closure_csv", kwargs={"workspace_slug": self.tenant.slug, "batch_pk": batch.pk})
        self.assertContains(self.client.get(csv_url), "Page 8")
        guide = reverse("workspace_loans:paper_closure_guide", kwargs={"workspace_slug": self.tenant.slug})
        self.assertContains(self.client.get(guide), "Moving away from paper")

    def test_transition_rls_and_immutable_paper_evidence(self):
        batch = complete_paper_closures(**self.paper_command())
        role = connection.ops.quote_name("paper_rls_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON loans_paperclosuretransition, loans_pawnreleasebatchline TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {role}")
            self.assertEqual(PaperClosureTransition.objects.count(), 1)
            with without_workspace_context():
                self.assertFalse(PaperClosureTransition.objects.exists())
                with self.assertRaises(DatabaseError), transaction.atomic():
                    PaperClosureTransition.objects.bulk_create([PaperClosureTransition(workspace_id=self.tenant.pk)])
            with self.assertRaises(DatabaseError), transaction.atomic():
                batch.lines.update(paid_by="Rewritten payer")
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")


class PaperOpeningTests(OpeningReleaseFixture):
    def test_imported_paper_closure_concession_and_later_event_guard(self):
        self.day = date(2021, 2, 5)
        preview = preview_paper_closures(workspace=self.tenant, actor=self.actor, loan_ids=[self.loan.pk], closure_date=date(2021, 2, 2))
        self.assertEqual(preview["rows"][0]["amount"], 1010)
        command = dict(workspace=self.tenant, actor=self.actor, request_key=uuid.uuid4(), quote_token=preview["token"], confirmed=True,
            rows=[dict(loan_id=self.loan.pk, amount="1005", concession="5", concession_reason="Paper agreement",
                paid_by="Family payer", collector_name=self.loan.borrower.display_name)])
        batch = complete_paper_closures(**command)
        release = batch.lines.get().release
        self.assertEqual(release.interest_concession_amount, 5)
        reverse_pawn_loan_event(release.loan_event_id, actor=self.actor, reason="Wrong date in paper book")
        preview = preview_paper_closures(workspace=self.tenant, actor=self.actor, loan_ids=[self.loan.pk], closure_date=date(2021, 2, 2))
        self.assertIn("Later financial activity", preview["rows"][0]["error"])
