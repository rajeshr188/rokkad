from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse
from import_export.exceptions import ImportError as ResourceImportError

from apps.orgs.access import normalize_action
from apps.orgs.models import Company, Membership, WorkspaceRoleGrant
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.data_portability.tests.fixtures import PortabilityFixture
from apps.tenant_apps.loans.models import LoanLicense, LoanSeries, PawnLoan, PawnLoanEvent
from apps.tenant_apps.loans.tests.factories import ensure_test_product_version
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.rates.models import RateSource

from apps.tenant_apps.utils.importing.forms import ImportForm, _tenant_model_choices, tenant_app_configs
from apps.tenant_apps.utils.importing.views import (
    _find_tenant_model, _import_resource_for_model, _export_resource_for_model, import_data,
)


class TenantImportRegistryTests(SimpleTestCase):
    def test_app_config_class_entries_resolve_to_installed_labels(self):
        configs = {config.label: config for config in tenant_app_configs()}
        self.assertEqual(configs["loans"].name, "apps.tenant_apps.loans")
        self.assertEqual(configs["party"].name, "apps.tenant_apps.party")
        self.assertEqual(configs["notify_v2"].name, "apps.tenant_apps.notify_v2")
        self.assertEqual(configs["rates"].name, "apps.tenant_apps.rates")
        self.assertEqual(set(configs), {"loans", "party", "notify_v2", "rates"})

    def test_model_choices_and_lookup_accept_app_config_class_settings(self):
        choices = dict(_tenant_model_choices())
        model, app_path = _find_tenant_model("PawnLoan")
        self.assertIn("PawnLoan", choices)
        self.assertEqual(model._meta.app_label, "loans")
        self.assertEqual(app_path, "apps.tenant_apps.loans")

    def test_every_loans_model_is_excluded_from_import_but_remains_exportable(self):
        choices = dict(ImportForm().fields["model_name"].choices)
        exports = dict(_tenant_model_choices())
        self.assertIn("RateSource", choices)
        self.assertIn("Party", choices)
        for model in apps.get_app_config("loans").get_models():
            with self.subTest(model=model.__name__):
                self.assertNotIn(model.__name__, choices)
                self.assertIn(model.__name__, exports)
                with self.assertRaises(PermissionDenied):
                    _import_resource_for_model(model)
        self.assertIs(_export_resource_for_model(PawnLoan)._meta.model, PawnLoan)


@override_settings(ALLOWED_HOSTS=["testserver"], STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class GenericImportBoundaryTests(PortabilityFixture):
    def request(self, *, workspace=None, actor=None, model="RateSource", content=None):
        request = RequestFactory().post("/data-tools/import/", {
            "model_name": model,
            "import_file": SimpleUploadedFile("rows.csv", content or b"id,name,location\n,Test,Town\n"),
        })
        request.workspace = workspace or self.a
        request.user = actor or self.actor
        return request

    def test_permission_revocation_is_checked_before_resource_or_file_parsing(self):
        with self.scoped():
            member = Membership.objects.get(company=self.a, user=self.actor)
            for action in ("data.view", "data.import", "workspace.settings.manage"):
                with self.subTest(action=action), transaction.atomic():
                    grants = WorkspaceRoleGrant.objects.filter(
                        workspace=self.a, workspace_role__role_id=member.role_id,
                    ).select_related("permission")
                    ids = [g.pk for g in grants if normalize_action(g.permission.codename) == action]
                    self.assertTrue(ids)
                    WorkspaceRoleGrant.objects.filter(pk__in=ids).delete()
                    with patch("apps.tenant_apps.utils.importing.views.Dataset") as parser:
                        with self.assertRaises(PermissionDenied):
                            import_data(self.request())
                        parser.assert_not_called()
                    transaction.set_rollback(True)

    def test_missing_mismatched_context_and_nonmember_are_denied(self):
        with self.assertRaises(PermissionDenied):
            import_data(self.request())
        with self.scoped():
            for request in (self.request(workspace=self.b), self.request(actor=self.other_actor)):
                with self.assertRaises(PermissionDenied):
                    import_data(request)

    def test_inactive_workspace_denied_even_with_grants(self):
        with self.scoped():
            self.a.lifecycle_state = Company.LifecycleState.ARCHIVED
            with self.assertRaises(PermissionDenied):
                import_data(self.request())

    def test_forged_loans_names_never_parse_source(self):
        with self.scoped(), patch("apps.tenant_apps.utils.importing.views.Dataset") as parser:
            for model in apps.get_app_config("loans").get_models():
                with self.subTest(model=model.__name__), self.assertRaises(PermissionDenied):
                    import_data(self.request(model=model.__name__, content=b"invalid source"))
            parser.assert_not_called()
            self.assertFalse(PawnLoan.objects.exists())
            self.assertFalse(PawnLoanEvent.objects.exists())

    def test_renamed_role_keeps_access_from_grants(self):
        member = Membership.objects.get(company=self.a, user=self.actor)
        member.role.name = "Custom import operators"
        member.role.save(update_fields=["name"])
        with self.scoped():
            source = RateSource.objects.create(name="Original", location="Town")
            response = import_data(self.request(content=f"id,name,location\n{source.pk},Updated,Town\n".encode()))
            self.assertEqual(response.status_code, 200)
            source.refresh_from_db()
            self.assertEqual(source.name, "Updated")

    def test_nonfinancial_import_is_atomic_and_workspace_scoped(self):
        with self.scoped():
            source = RateSource.objects.create(name="Original", location="Town")
            response = import_data(self.request(content=f"id,name,location\n{source.pk},Updated,Town\n".encode()))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(RateSource.objects.get(name="Updated").workspace_id, self.a.pk)
            # A late failure must undo an earlier successful row in the same file.
            content = f"id,name,location\n{source.pk},Changed,Town\n,Bad,".encode() + b"x" * 100 + b"\n"
            with self.assertRaises(ResourceImportError):
                import_data(self.request(content=content))
            source.refresh_from_db()
            self.assertEqual(source.name, "Updated")
        with self.scoped(self.b):
            self.assertFalse(RateSource.objects.filter(pk=source.pk).exists())
            with self.assertRaises(ResourceImportError):
                import_data(self.request(workspace=self.b,
                    content=f"id,workspace,name,location\n{source.pk},{self.a.pk},Foreign,Town\n".encode()))
        with self.scoped():
            source.refresh_from_db()
            self.assertEqual(source.name, "Updated")

    def test_existing_generic_create_sequence_reset_is_denied_and_rolled_back(self):
        # Characterize the pre-existing library limitation without granting a
        # runtime role permission to reset shared sequences.
        with self.scoped():
            with self.assertRaisesRegex(ResourceImportError, "permission denied for sequence"):
                import_data(self.request())
            self.assertFalse(RateSource.objects.filter(name="Test").exists())

    def test_http_forgery_cannot_update_existing_loan_and_csrf_remains_required(self):
        WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=self.a))
        with self.scoped():
            license = LoanLicense.objects.create(workspace=self.a, name="Original", license_number="A",
                issued_on=date(2020, 1, 1), expires_on=date(2030, 1, 1))
            series = LoanSeries.objects.create(license=license, name="A", code="A")
            loan = PawnLoan.objects.create(workspace=self.a, license=license, series=series,
                borrower=Party.objects.create(display_name="Borrower"),
                product_version=ensure_test_product_version(self.a), loan_number="A1",
                principal_amount=1000, monthly_interest_rate=1)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        url = reverse("workspace_slug_data_tools_import", kwargs={"workspace_slug": self.a.slug})
        with self.scoped():
            response = client.get(url)
            self.assertContains(response, "reviewed Loans import workflow")
            self.assertNotContains(response, 'value="PawnLoan"')
            self.assertEqual(client.post(url, {"model_name": "PawnLoan"}).status_code, 403)
            response = client.post(url, {
                "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
                "model_name": "PawnLoan",
                "import_file": SimpleUploadedFile("loans.csv", f"id,state\n{loan.pk},CLOSED\n".encode()),
            })
            self.assertEqual(response.status_code, 403)
            loan.refresh_from_db()
            self.assertEqual(loan.state, "DRAFT")
            self.assertFalse(PawnLoanEvent.objects.exists())
