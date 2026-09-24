import copy
import json
from datetime import date
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import Client, override_settings
from django.urls import reverse

from apps.orgs.audit import AuditLog
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.history_contract import HistoryError, digest, parse
from apps.tenant_apps.loans.services.history_export import export_history
from apps.tenant_apps.loans.services.opening_export import export_opening, export_loan_data, PROFILE
from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full
from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
from apps.tenant_apps.loans.tests.test_opening_import import OpeningImportFixture


class OpeningExportTests(OpeningImportFixture):
    def download(self, origin):
        content = export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
        manifest, evidence = [json.loads(line) for line in content.splitlines()]
        self.assertEqual(manifest["sha256"], digest(evidence))
        self.assertEqual(manifest["profile"], PROFILE)
        return content, manifest, evidence

    def test_opening_export_preserves_review_without_fabricating_origination(self):
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 2)):
            origin = self.write()
            before = copy.deepcopy(origin.document)
            content, manifest, evidence = self.download(origin)
            self.assertEqual(manifest["financial_history_from"], "2021-01-20")
            self.assertEqual(manifest["history_before_cutover"], "UNAVAILABLE")
            self.assertTrue(manifest["restore_supported"])
            self.assertEqual(evidence["origin"]["document"], before)
            self.assertEqual(evidence["recorded_balance"], {"principal": "1000", "interest": "0", "fees": "0"})
            self.assertEqual(evidence["collection_preview"]["additional_interest"], "10")
            self.assertEqual([row["event_kind"] for row in evidence["events"]], ["MIGRATION_OPENING"])
            self.assertEqual(evidence["items"][0]["metal"], "BRONZE")
            self.assertIsNone(evidence["items"][0]["gross_weight"])
            self.assertEqual(evidence["appraisals"][0]["method"], "MIGRATION_REVIEW")
            self.assertEqual(len(evidence["schedules"]), 1)
            self.assertEqual(evidence["custody_events"], [])
            self.assertEqual(evidence["source_verifications"], [])
            self.assertEqual(self.download(origin)[0], content)
            self.assertEqual(m.PawnLoanEvent.objects.count(), 1)
            self.assertFalse(m.PawnLoanDisbursalSnapshot.objects.exists())
            self.assertTrue(AuditLog.objects.filter(action="DATA_EXPORT", company=self.a, data__profile=PROFILE).exists())

    def test_release_concession_reversal_and_second_release_keep_complete_evidence(self):
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 2)):
            origin = self.write()
            released = release_pawn_loan_in_full(origin.loan_id, settlement_amount=1005, interest_concession=5,
                concession_reason="Accepted shortfall", request_key="first", actor=self.actor)
            _, _, evidence = self.download(origin)
            self.assertEqual(evidence["recorded_balance"], {"principal": "0", "interest": "0", "fees": "0"})
            self.assertEqual(evidence["interest_conceded"], "5")
            self.assertEqual(evidence["releases"][0]["settlement_amount"], "1005")
            self.assertEqual(evidence["accruals"][0]["recognized_interest"], "10")
            self.assertEqual(len(evidence["closing_lines"]), 1)
            self.assertEqual(len(evidence["custody_events"]), 1)
            self.assertEqual(len(evidence["allocations"]), 2)
            self.assertEqual(len(evidence["schedule_changes"]), 1)
            self.assertEqual(evidence["collection_preview"]["additional_interest"], "0")
            reverse_pawn_loan_event(released.loan_event.pk, actor=self.actor, reason="Cancelled return")
            _, _, evidence = self.download(origin)
            self.assertEqual(evidence["recorded_balance"]["principal"], "1000")
            self.assertEqual(evidence["interest_conceded"], "0")
            self.assertEqual(len(evidence["release_reversals"]), 1)
            reversal = evidence["release_reversals"][0]
            self.assertIsNotNone(reversal["catch_up_reversal_event_id"])
            self.assertEqual(len(evidence["custody_events"]), 2)
            release_pawn_loan_in_full(origin.loan_id, settlement_amount=1010, request_key="second", actor=self.actor)
            content, _, evidence = self.download(origin)
            self.assertEqual(len(evidence["events"]), 7)
            self.assertEqual(len(evidence["releases"]), 2)
            # The agreed aggregate calculation has no fabricated item accrual lines.
            self.assertEqual(evidence["accrual_lines"], [])
            # Retrying the original command is safe, but is NOT snapshot restoration.
            self.assertEqual(self.write().pk, origin.pk)
            self.assertEqual(self.download(origin)[0], content)
            self.assertEqual(m.PawnLoan.objects.count(), 1)

    def test_first_month_release_has_no_invented_catch_up(self):
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 1, 21)):
            origin = self.write()
            release_pawn_loan_in_full(origin.loan_id, settlement_amount=1000, request_key="covered", actor=self.actor)
            _, _, evidence = self.download(origin)
            self.assertEqual(evidence["accruals"], [])
            self.assertIsNone(evidence["releases"][0]["catch_up_accrual_id"])
            self.assertEqual(len(evidence["events"]), 2)

    def test_strict_history_import_and_export_do_not_claim_opening_history_is_complete(self):
        with self.scoped():
            origin = self.write()
            content, _, _ = self.download(origin)
            with self.assertRaisesMessage(HistoryError, "dedicated opening restore command"):
                parse(content)
            with self.assertRaises(HistoryError):
                export_history(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
            selected, filename = export_loan_data(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
            self.assertEqual(selected, content)
            self.assertEqual(filename, "loan-opening.jsonl")

    def test_access_is_checked_before_lookup_and_other_workspace_cannot_export(self):
        with self.scoped():
            origin = self.write()
            for actor in (None, self.other_actor):
                with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                    export_loan_data(workspace_id=self.a.pk, actor=actor, loan_id=origin.loan_id)
            with self.assertRaises(PermissionDenied):
                export_opening(workspace_id=self.a.pk, actor=self.other_actor, loan_id=99999999)
        with self.scoped(self.b), self.assertRaises(m.PawnLoan.DoesNotExist):
            export_loan_data(workspace_id=self.b.pk, actor=self.actor, loan_id=origin.loan_id)
        from apps.orgs.models import Membership, WorkspaceRoleGrant
        with self.scoped():
            membership = Membership.objects.get(company=self.a, user=self.actor)
            WorkspaceRoleGrant.objects.filter(workspace_id=self.a.pk, workspace_role__role_id=membership.role_id,
                permission__codename="data_export").delete()
            with self.assertRaises(PermissionDenied):
                export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)

    def test_bounded_export_failure_does_not_log_success_or_change_loan(self):
        with self.scoped():
            origin = self.write()
            with patch("apps.tenant_apps.loans.services.opening_export.MAX_BYTES", 20), self.assertRaisesMessage(HistoryError, "5 MiB"):
                self.download(origin)
            self.assertFalse(AuditLog.objects.filter(action="DATA_EXPORT", company=self.a).exists())
            self.assertEqual(m.PawnLoanEvent.objects.count(), 1)
            with patch("apps.tenant_apps.loans.services.opening_export.MAX_RECORDS", 1), self.assertRaises(HistoryError):
                self.download(origin)

    def test_changed_collateral_and_inconsistent_custody_fail_closed(self):
        with self.scoped():
            origin = self.write()
            item = origin.loan.collateral_items.get()
            m.PawnCollateralItem.objects.filter(pk=item.pk).update(description="Changed after review")
            with self.assertRaisesMessage(HistoryError, "collateral facts have changed"):
                self.download(origin)
            m.PawnCollateralItem.objects.filter(pk=item.pk).update(description=item.description, custody_state="WITH_CUSTOMER")
            with self.assertRaisesMessage(HistoryError, "custody disagree"):
                self.download(origin)
            self.assertFalse(AuditLog.objects.filter(action="DATA_EXPORT", company=self.a).exists())

    @override_settings(ALLOWED_HOSTS=["testserver"], SECURE_SSL_REDIRECT=False, STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_browser_download_requires_post_csrf_and_uses_opening_filename(self):
        from types import SimpleNamespace
        from apps.tenancy.testing import WorkspaceTestCase
        WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=self.a))
        with self.scoped():
            origin = self.write()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        url = reverse("workspace_portability:loan_export", kwargs={"workspace_slug": self.a.slug, "loan_id": origin.loan_id})
        self.assertEqual(client.get(url).status_code, 405)
        self.assertEqual(client.post(url).status_code, 403)
        page = reverse("workspace_portability:loan_upload", kwargs={"workspace_slug": self.a.slug})
        self.assertEqual(client.get(page).status_code, 200)
        response = client.post(url, {"csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        self.assertEqual(response.status_code, 200)
        self.assertIn("loan-opening.jsonl", response["Content-Disposition"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertTrue(json.loads(response.content.splitlines()[0])["restore_supported"])
        # Subscription read-only mode preserves the authorized POST/CSRF export.
        from apps.tenancy.testing import expire_workspace_trial
        expire_workspace_trial(self.a)
        response = client.post(url, {"csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        self.assertEqual(response.status_code, 200)
        self.assertIn("loan-opening.jsonl", response["Content-Disposition"])
