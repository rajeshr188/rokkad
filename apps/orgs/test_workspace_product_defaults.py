"""Workspace creation prepares only draft products, atomically and under RLS."""
from types import SimpleNamespace
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory, TestCase

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company, Domain, Membership, Role
from apps.orgs.services import control_plane
from apps.tenancy.context import current_workspace_id, workspace_context
from apps.tenant_apps.loans.models import LoanProduct, LoanProductVersion
from apps.tenant_apps.loans.services.product_catalog import seed_default_loan_products


class WorkspaceProductDefaultsTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="product-onboarding-owner")
        Role.objects.get_or_create(name="Owner")
        self.request = RequestFactory().post("/onboarding/company/", HTTP_HOST="testserver")
        self.request.user = self.owner
        # All creation and adversarial reads execute as a restricted runtime role.
        role = connection.ops.quote_name("products_test_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        # TestCase rolls back the role definition and grants along with its rows.

    def create_workspace(self, creator, name):
        form = SimpleNamespace(save=lambda commit: Company(name=name))
        result = creator(form=form, user=self.owner, request=self.request)
        return result[0] if isinstance(result, tuple) else result

    def test_both_creation_paths_prepare_isolated_drafts_and_clear_context(self):
        product_ids = []
        for creator, name in (
            (control_plane.create_workspace_from_form, "Products ordinary"),
            (control_plane.create_onboarding_workspace_from_form, "Products onboarding"),
        ):
            workspace = self.create_workspace(creator, name)
            self.assertIsNone(current_workspace_id())
            self.assertFalse(LoanProduct.objects.exists())
            with workspace_context(workspace.pk):
                self.assertEqual(LoanProduct.objects.count(), 4)
                versions = list(LoanProductVersion.objects.all())
                self.assertEqual(len(versions), 4)
                self.assertEqual({v.status for v in versions}, {"DRAFT"})
                self.assertEqual({v.workspace_id for v in versions}, {workspace.pk})
                self.assertEqual({v.created_by_id for v in versions}, {self.owner.pk})
                self.assertFalse(LoanProduct.objects.filter(pk__in=product_ids).exists())
                product_ids.extend(LoanProduct.objects.values_list("pk", flat=True))
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('app.workspace_id', true)")
                self.assertIn(cursor.fetchone()[0], (None, ""))

    def test_product_failure_rolls_back_workspace_domain_membership_and_audit(self):
        before = {model: model.objects.count() for model in (Company, Domain, Membership, AuditLog)}

        def fail_after_preparation(**kwargs):
            seed_default_loan_products(**kwargs)
            raise RuntimeError("Draft preparation failed")

        for creator in (control_plane.create_workspace_from_form, control_plane.create_onboarding_workspace_from_form):
            with patch("apps.tenant_apps.loans.services.product_catalog.seed_default_loan_products", side_effect=fail_after_preparation):
                with self.assertRaisesMessage(RuntimeError, "Draft preparation failed"):
                    self.create_workspace(creator, "Failed product preparation")
            self.assertIsNone(current_workspace_id())
            for model, count in before.items():
                self.assertEqual(model.objects.count(), count)
