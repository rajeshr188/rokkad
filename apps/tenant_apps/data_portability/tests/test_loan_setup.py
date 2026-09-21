import uuid
from datetime import date
from types import SimpleNamespace

from django.core.exceptions import PermissionDenied
from django.test import Client, override_settings
from django.urls import reverse

from apps.orgs.models import Company, Membership, Role, WorkspaceRoleGrant
from apps.tenancy import testing
from apps.tenant_apps.loans.models import LoanSeries, LoanProduct, LoanProductVersion, LoanNumberSequence, PawnLoan
from apps.tenant_apps.loans.services.license_series import create_license
from apps.tenant_apps.loans.services.history_setup import preview_history_setup, HistorySetupError
from apps.tenant_apps.data_portability.loan_setup import HistorySetupForm
from .fixtures import PortabilityFixture


@override_settings(ALLOWED_HOSTS=["testserver"], STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class LoanSetupTests(PortabilityFixture):
    def setUp(self):
        super().setUp()
        with self.scoped():
            self.license = create_license(workspace=self.a, actor=self.actor, name="Historical", license_number="OLD-L",
                issued_on=date(2020, 1, 1), expires_on=date(2021, 12, 31))
            self.revision = self.license.revisions.get()
            self.series = LoanSeries.objects.create(license=self.license, name="Old series", code="OLD", is_active=False)
            product = LoanProduct.objects.create(workspace=self.a, code="HIST", name="Historical flexible")
            self.product = LoanProductVersion.objects.create(product=product, version=1, status="RETIRED",
                repayment_structure="FLEXIBLE_PARTIAL_PAYMENT", amortisation_method="NONE", payment_frequency="FLEXIBLE",
                minimum_tenor_months=1, maximum_tenor_months=12, operational_grace_days=3,
                extra_payment_rule="REDUCE_PRINCIPAL", calculation_contract_version="TEST-V1")
            self.sequence = LoanNumberSequence.objects.create(series=self.series, document_kind="PAWN_LOAN",
                prefix="LIVE-", width=5, next_number=19, maximum_number=1000)
        self.args = dict(workspace_id=self.a.pk, actor=self.actor, revision_id=self.revision.pk,
            series_id=self.series.pk, product_version_id=self.product.pk, source_namespace=uuid.uuid4(),
            source_loan_id="loan-001", source_loan_number="001", source_license_number="OLD-L",
            disbursed_on=date(2021, 1, 1), tenure_months=3, calculation_contract_version="TEST-V1", operational_grace_days=3)

    def preview(self, **changes):
        return preview_history_setup(**{**self.args, **changes})

    def test_active_and_released_number_previews_are_stable_without_writes(self):
        with self.scoped():
            first = self.preview()
            second = self.preview(source_release_id="release-001", source_release_number="R-001")
            self.assertEqual(first["numbers"][0], second["numbers"][0])
            self.assertEqual(second, self.preview(source_release_id="release-001", source_release_number="R-001"))
            self.assertEqual(len(second["numbers"]), 2)
            self.assertNotEqual(second["numbers"][0]["local_number"], second["numbers"][1]["local_number"])
            self.assertTrue(all(len(row["local_number"]) <= 64 for row in second["numbers"]))
            self.assertEqual(first["numbers"][0]["source_number"], "001")
            self.sequence.refresh_from_db()
            self.assertEqual(self.sequence.next_number, 19)
            self.assertFalse(PawnLoan.objects.exists())
            self.assertEqual(self.product.status, "RETIRED")
            self.assertFalse(self.series.is_active)

    def test_historical_setup_mismatches_fail_closed(self):
        with self.scoped():
            for changes in ({"source_license_number": "OTHER"}, {"disbursed_on": date(2022, 1, 1)},
                            {"calculation_contract_version": "OTHER"}, {"operational_grace_days": 4},
                            {"tenure_months": 13}, {"source_release_id": "partial"},
                            {"source_loan_id": " padded "}, {"source_namespace": "bad"},
                            {"disbursed_on": date(2099, 1, 1)}):
                with self.subTest(changes=changes), self.assertRaises(HistorySetupError): self.preview(**changes)
            LoanProductVersion.objects.filter(pk=self.product.pk).update(status="DRAFT")
            with self.assertRaises(HistorySetupError): self.preview()

    def test_wrong_series_and_foreign_workspace_ids_are_rejected(self):
        with self.scoped():
            other = create_license(workspace=self.a, actor=self.actor, name="Other", license_number="OTHER",
                issued_on=date(2020, 1, 1), expires_on=date(2022, 1, 1))
            series = LoanSeries.objects.create(license=other, name="Other", code="OTHER")
            with self.assertRaises(HistorySetupError): self.preview(series_id=series.pk)
        with self.scoped(self.b):
            with self.assertRaises(HistorySetupError): self.preview(workspace_id=self.b.pk)
            form = HistorySetupForm(workspace_id=self.b.pk)
            self.assertFalse(form.fields["revision_id"].queryset.exists())
            self.assertFalse(form.fields["product_version_id"].queryset.exists())

    def test_context_owner_lifecycle_and_permissions_are_checked_every_time(self):
        with self.assertRaises(PermissionDenied): self.preview()
        with self.scoped():
            Membership.objects.create(company=self.a, user=self.other_actor, role=Role.objects.get_or_create(name="Owner")[0])
            with self.assertRaises(PermissionDenied): self.preview(actor=self.other_actor)
            self.preview()
            Company.all_objects.filter(pk=self.a.pk).update(lifecycle_state="ARCHIVED")
            with self.assertRaises(PermissionDenied): self.preview()

    def test_revoked_import_permission_denies_preparation(self):
        with self.scoped():
            membership = Membership.objects.get(company=self.a, user=self.actor)
            WorkspaceRoleGrant.objects.filter(workspace_id=self.a.pk, workspace_role__role_id=membership.role_id,
                permission__codename="data_import").delete()
            with self.assertRaises(PermissionDenied): self.preview()

    def test_number_is_source_identity_based_not_source_display_number(self):
        with self.scoped():
            first = self.preview()["numbers"][0]["local_number"]
            self.assertEqual(first, self.preview(source_loan_number="renamed")["numbers"][0]["local_number"])
            self.assertNotEqual(first, self.preview(source_namespace=uuid.uuid4())["numbers"][0]["local_number"])
            self.assertNotEqual(first, self.preview(source_loan_id="loan-002")["numbers"][0]["local_number"])

    def test_existing_number_collision_is_not_claimed_as_idempotent_replay(self):
        from apps.tenant_apps.party.models import Party
        with self.scoped():
            number = self.preview()["numbers"][0]["local_number"]
            party = Party.objects.create(display_name="Existing borrower")
            PawnLoan.objects.create(workspace=self.a, license=self.license, license_revision=self.revision,
                series=self.series, product_version=self.product, borrower=party, loan_number=number,
                principal_amount=1000, monthly_interest_rate=1)
            with self.assertRaisesMessage(HistorySetupError, "already exists"): self.preview()

    def test_future_sequence_overlap_is_checked_without_allocating(self):
        from unittest.mock import patch
        with self.scoped(), patch("apps.tenant_apps.loans.services.history_setup._number", return_value="LIVE-00019"):
            with self.assertRaisesMessage(HistorySetupError, "future numbering range"): self.preview()
            self.sequence.refresh_from_db()
            self.assertEqual(self.sequence.next_number, 19)

    def test_ui_requires_csrf_preserves_source_numbers_and_explains_preparation_only(self):
        testing.WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=self.a))
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        url = reverse("workspace_portability:loan_setup", kwargs={"workspace_slug": self.a.slug})
        response = client.get(url)
        self.assertContains(response, "Upload a canonical JSONL file")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(client.post(url, {}).status_code, 403)
        values = {k: str(v) for k, v in self.args.items() if k not in {"actor", "workspace_id"}}
        values["csrfmiddlewaretoken"] = client.cookies["csrftoken"].value
        response = client.post(url, values)
        self.assertContains(response, "Setup checks passed")
        self.assertContains(response, "previews, not reservations")
        self.assertContains(response, ">001</td>")
