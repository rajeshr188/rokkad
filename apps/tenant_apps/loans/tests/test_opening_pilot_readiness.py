import copy
from datetime import date
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, override_settings

from apps.orgs.audit import AuditLog
from apps.tenancy.testing import start_workspace_trial
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.opening_import import adopt_opening_source_number, preview_opening_import
from apps.tenant_apps.loans.services.pawn_release import preview_pawn_loan_full_release, release_pawn_loan_in_full
from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
from apps.tenant_apps.loans.tests.test_opening_import import OpeningImportFixture
from apps.tenant_apps.loans.web.pawn_reads import pawn_loan_detail


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class OpeningPilotReadinessTests(OpeningImportFixture):
    def adopt(self, loan, **kwargs):
        return adopt_opening_source_number(**dict(workspace_id=self.a.pk, actor=self.actor,
            loan_id=loan.pk, **kwargs))

    def test_original_number_is_explicitly_previewed_and_committed_without_consuming_sequence(self):
        self.setup["local_loan_number"] = self.review["source"]["number"]
        with self.scoped():
            preview = preview_opening_import(**self.args)
            self.assertEqual(preview["summary"]["loan_number"], self.review["source"]["number"])
            origin = self.write()
            self.assertEqual(origin.loan.loan_number, self.review["source"]["number"])
            self.assertEqual(self.write().pk, origin.pk)
            self.sequence.refresh_from_db()
            self.assertEqual(self.sequence.next_number, 1)

    def test_number_adoption_keeps_immutable_origin_and_events_and_is_idempotent(self):
        with self.scoped():
            origin = self.write()
            original = copy.deepcopy(origin.document)
            events = list(origin.loan.loan_events.values())
            loan = self.adopt(origin.loan)
            self.assertEqual(loan.loan_number, self.review["source"]["number"])
            self.assertEqual(self.adopt(loan).pk, loan.pk)
            origin.refresh_from_db()
            self.assertEqual(origin.document, original)
            self.assertEqual(list(loan.loan_events.values()), events)
            self.assertEqual(self.write().pk, origin.pk)
            self.assertEqual(AuditLog.objects.filter(company=self.a,
                data__operation="ADOPT_OPENING_SOURCE_NUMBER").count(), 1)

    def test_number_adoption_enforces_owner_workspace_and_future_sequence_boundaries(self):
        with self.scoped():
            origin = self.write()
            with self.assertRaises(PermissionDenied):
                adopt_opening_source_number(workspace_id=self.a.pk, actor=self.other_actor, loan_id=origin.loan_id)
            with self.assertRaises(PermissionDenied):
                adopt_opening_source_number(workspace_id=self.b.pk, actor=self.actor, loan_id=origin.loan_id)
            self.review["source"]["number"] = "H-00001"
            self.setup["local_loan_number"] = "H-00001"
            self.review["source"]["loan_id"] = "girvi_loan:other"
            with self.assertRaisesMessage(ValueError, "future numbering range"):
                preview_opening_import(**self.args)

    def test_number_adoption_rejects_collision_and_issued_label(self):
        with self.scoped():
            origin = self.write()
            other = copy.deepcopy(self.review)
            other["source"]["loan_id"] = "girvi_loan:other"
            other_origin = self.write(review=other)
            self.adopt(other_origin.loan)
            with self.assertRaisesMessage(ValueError, "number already exists"):
                self.adopt(origin.loan)
            m.PawnCollateralLabelIssue.objects.create(workspace=self.a,
                collateral_item=other_origin.loan.collateral_items.get(), action="PRINT",
                qr_target="/loan/", payload_sha256="a" * 64, issued_by=self.actor)
            # Idempotent retry of the already adopted number remains harmless.
            self.assertEqual(self.adopt(other_origin.loan).pk, other_origin.loan_id)

    def test_number_adoption_rejects_printed_evidence(self):
        with self.scoped():
            origin = self.write()
            m.PawnCollateralLabelIssue.objects.create(workspace=self.a,
                collateral_item=origin.loan.collateral_items.get(), action="PRINT",
                qr_target="/loan/", payload_sha256="a" * 64, issued_by=self.actor)
            with self.assertRaisesMessage(ValueError, "Issued documents"):
                self.adopt(origin.loan)

    def test_opening_page_guides_full_release_without_native_accrual_warning(self):
        start_workspace_trial(self.a)
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 2)):
            origin = self.write()
            self.adopt(origin.loan)
            request = RequestFactory().get("/loan/")
            request.user, request.workspace, request.session = self.actor, self.a, {}
            response = pawn_loan_detail(request, origin.loan_id)
            html = response.content.decode()
            self.assertEqual(response.status_code, 200)
            self.assertIn("Collect and release", html)
            self.assertIn("Amount to collect for full release", html)
            self.assertIn("Imported balance and history", html)
            self.assertNotIn("Accrual preview unavailable", html)
            self.assertNotIn(">Repayment</a>", html)
            self.assertNotIn(">Accrue interest</a>", html)
            self.assertNotIn(">Release and renew</a>", html)

    def test_readable_number_survives_release_concession_and_reversal(self):
        self.review["collateral"][0]["valuation"] = dict(status="UNVERIFIED",
            source_amount=None, source_date=None, evidence_reference="No dated appraisal")
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 2)):
            origin = self.write()
            loan = self.adopt(origin.loan)
            quote = preview_pawn_loan_full_release(loan.pk)
            self.assertFalse(quote.blockers)
            result = release_pawn_loan_in_full(loan.pk, actor=self.actor, request_key="pilot-release",
                settlement_amount=quote.minimum_settlement - 5, interest_concession=5,
                concession_reason="Approved rehearsal concession")
            loan.refresh_from_db()
            self.assertEqual(loan.state, "CLOSED")
            self.assertEqual(loan.loan_number, self.review["source"]["number"])
            reverse_pawn_loan_event(result.loan_event.pk, actor=self.actor, reason="Rehearsal reversal")
            loan.refresh_from_db()
            self.assertEqual(loan.state, "ACTIVE")
            self.assertEqual(preview_pawn_loan_full_release(loan.pk).minimum_settlement, quote.minimum_settlement)
