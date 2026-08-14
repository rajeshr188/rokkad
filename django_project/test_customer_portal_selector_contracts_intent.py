from pathlib import Path
from types import SimpleNamespace

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase
from django.urls import Resolver404, resolve, reverse

from apps.tenant_apps.party.portal_access import PortalIdentity
from apps.tenant_apps.party.portal_selectors import (
    get_portal_dashboard_summary,
    get_portal_documents_summary,
    get_portal_invoices_summary,
    get_portal_loans_summary,
    get_portal_payments_summary,
    get_portal_statements_summary,
)
from django_project import tenant_urls, urls


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_UI_ROOT = PROJECT_ROOT / "docs" / "ui"


def _read(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8-sig")


class CustomerPortalSelectorContractsIntentTests(SimpleTestCase):
    def test_phase123_selector_contract_doc_exists(self):
        plan_path = DOCS_UI_ROOT / "customer_portal_selector_contracts_phase12.md"

        self.assertTrue(plan_path.exists())
        content = plan_path.read_text(encoding="utf-8-sig")

        for expected in (
            "Customer Portal Selector Contracts Phase 12",
            "Phase 12.3 defines",
            "PortalIdentity",
            "validate_portal_identity()",
            "get_portal_loans_summary",
            "get_portal_invoices_summary",
            "get_portal_payments_summary",
            "get_portal_documents_summary",
            "get_portal_statements_summary",
            "Phase 12.4",
        ):
            self.assertIn(expected, content)

    def test_phase123_selector_module_defines_fail_closed_contracts(self):
        selectors_source = _read("apps/tenant_apps/party/portal_selectors.py")

        for expected in (
            "PortalLoanSummary",
            "PortalInvoiceSummary",
            "PortalPaymentSummary",
            "PortalDocumentSummary",
            "PortalStatementSummary",
            "PortalDashboardSummary",
            "validate_portal_identity",
            "get_portal_dashboard_summary",
            "get_portal_documents_summary",
        ):
            self.assertIn(expected, selectors_source)

    def test_phase123_selectors_reject_incomplete_identity_before_data_reads(self):
        incomplete_identity = PortalIdentity(
            user=SimpleNamespace(is_authenticated=True),
            workspace=SimpleNamespace(schema_name="acme"),
            party=None,
            access_grant=SimpleNamespace(status="ACTIVE"),
        )

        for selector in (
            get_portal_dashboard_summary,
            get_portal_loans_summary,
            get_portal_invoices_summary,
            get_portal_payments_summary,
            get_portal_documents_summary,
            get_portal_statements_summary,
        ):
            with self.subTest(selector=selector.__name__):
                with self.assertRaisesMessage(PermissionDenied, "party"):
                    selector(incomplete_identity)

    def test_phase123_selectors_require_verified_identity_before_data_reads(self):
        identity = PortalIdentity(
            user=SimpleNamespace(is_authenticated=True),
            workspace=SimpleNamespace(schema_name="acme"),
            party=SimpleNamespace(status="BLOCKED"),
            access_grant=SimpleNamespace(status="ACTIVE"),
        )

        for selector in (
            get_portal_dashboard_summary,
            get_portal_loans_summary,
            get_portal_invoices_summary,
            get_portal_payments_summary,
            get_portal_documents_summary,
            get_portal_statements_summary,
        ):
            with self.subTest(selector=selector.__name__):
                with self.assertRaises(PermissionDenied):
                    selector(identity)

    def test_phase123_target_portal_routes_are_now_tenant_only(self):
        route_map = {
            "customer_portal_dashboard": "/portal/",
            "customer_portal_loans": "/portal/loans/",
            "customer_portal_invoices": "/portal/invoices/",
            "customer_portal_payments": "/portal/payments/",
            "customer_portal_documents": "/portal/documents/",
            "customer_portal_statements": "/portal/statements/",
        }

        for route_name, path in route_map.items():
            with self.subTest(route_name=route_name):
                self.assertEqual(reverse(route_name, urlconf=tenant_urls), path)
                self.assertEqual(resolve(path, urlconf=tenant_urls).url_name, route_name)
            with self.subTest(path=path, urlconf="public"):
                with self.assertRaises(Resolver404):
                    resolve(path, urlconf=urls)

    def test_phase123_project_docs_point_to_selector_phase(self):
        status = _read("docs/STATUS.md")
        memory = _read("docs/AGENT_MEMORY.md")
        audit = _read("docs/ui/saas_information_architecture_audit.md")
        portal_plan = _read("docs/ui/customer_portal_phase12_plan.md")

        for content in (status, memory, audit, portal_plan):
            with self.subTest():
                self.assertIn("Phase 12.3", content)
                self.assertIn("customer_portal_selector_contracts_phase12.md", content)
                self.assertIn("Phase 12.4", content)
