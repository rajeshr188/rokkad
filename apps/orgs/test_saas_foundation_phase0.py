import json
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase

from apps.orgs.middleware_v2 import SecureWorkspaceMiddleware


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8-sig")


class SaasFoundationPhase0CharacterizationTests(SimpleTestCase):
    """Lock the inspected baseline before the accepted safety changes begin."""

    def test_hard_delete_is_retired_from_company_model_and_admin(self):
        self.assertFalse(hasattr(settings, "ALLOW_COMPANY_HARD_DELETE"))
        admin_source = _read("apps/orgs/admin.py")
        self.assertNotIn("def hard_delete_companies", admin_source)
        self.assertNotIn('"hard_delete_companies"', admin_source)
        self.assertIn("return False", admin_source)

    def test_email_verification_is_currently_optional(self):
        self.assertEqual(settings.ACCOUNT_EMAIL_VERIFICATION, "optional")

    def test_middleware_does_not_select_profile_workspace_as_fallback(self):
        middleware = SecureWorkspaceMiddleware(get_response=lambda request: None)
        profile_workspace = SimpleNamespace(schema_name="tenant_from_profile")

        workspace, source = middleware._select_workspace_candidate(
            domain_workspace=None,
            path_workspace=None,
            profile_workspace=profile_workspace,
        )

        self.assertIsNone(workspace)
        self.assertEqual(source, "public")

    def test_membership_validation_precedes_tenant_context_switch(self):
        source = _read("apps/orgs/middleware_v2.py")
        validation = source.index("validation = self._validate_workspace_access")
        switch = source.index("self._set_workspace_context(request, workspace)", validation)
        self.assertLess(validation, switch)

    def test_domain_path_mismatch_is_checked_before_tenant_switch(self):
        source = _read("apps/orgs/middleware_v2.py")
        mismatch = source.index("domain_workspace.id != path_workspace.id")
        switch = source.index("self._set_workspace_context(request, workspace)")
        self.assertLess(mismatch, switch)

    def test_subscription_access_is_separate_from_workspace_middleware(self):
        workspace_middleware = _read("apps/orgs/middleware_v2.py")
        subscription_middleware = _read("django_project/middleware.py")

        self.assertNotIn("subscription_access_service.evaluate_access", workspace_middleware)
        self.assertIn("class SubscriptionValidationMiddleware", subscription_middleware)
        self.assertIn("effective_billing_state", subscription_middleware)
        self.assertNotIn("SubscriptionAccessService", subscription_middleware)


class SaasFoundationInventoryCommandTests(SimpleTestCase):
    def test_json_output_is_read_only_and_reports_integrity_count(self):
        inventory = {
            "schema": "public",
            "read_only": True,
            "companies": {
                "owner_missing_membership": 1,
                "owner_without_owner_role": 2,
            },
            "memberships": {"null_role": 3},
            "invitations": {
                "orphan_pending_bridge": 6,
                "case_variant_pending_groups": 7,
            },
        }
        stdout = StringIO()

        with patch(
            "apps.orgs.management.commands.check_saas_foundation.collect_saas_foundation_inventory",
            return_value=inventory,
        ):
            call_command("check_saas_foundation", as_json=True, stdout=stdout)

        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["integrity_finding_count"], 13)

    def test_fail_on_findings_exits_nonzero(self):
        inventory = {
            "schema": "public",
            "read_only": True,
            "companies": {
                "owner_missing_membership": 1,
                "owner_without_owner_role": 0,
            },
            "memberships": {"null_role": 0},
            "invitations": {
                "orphan_pending_bridge": 0,
                "case_variant_pending_groups": 0,
            },
        }

        with patch(
            "apps.orgs.management.commands.check_saas_foundation.collect_saas_foundation_inventory",
            return_value=inventory,
        ):
            with self.assertRaises(SystemExit):
                call_command(
                    "check_saas_foundation",
                    fail_on_findings=True,
                    stdout=StringIO(),
                )
