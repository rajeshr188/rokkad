from pathlib import Path

from django.test import SimpleTestCase
from django.urls import Resolver404, resolve, reverse

from django_project import tenant_urls


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_UI_ROOT = PROJECT_ROOT / "docs" / "ui"


def _read(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8-sig")


class TenantRouteCanonicalizationIntentTests(SimpleTestCase):
    def test_phase131_plan_records_alias_not_replacement_reality(self):
        plan_path = DOCS_UI_ROOT / "tenant_route_canonicalization_phase13_plan.md"

        self.assertTrue(plan_path.exists())
        content = plan_path.read_text(encoding="utf-8-sig")

        for expected in (
            "Tenant Route Canonicalization Phase 13 Plan",
            "aliases, not as full canonical replacements",
            "/dea/",
            "/party/",
            "/girvi/",
            "Phase 11 completed route availability",
            "did not remove legacy tenant roots",
            "Phase 13.2",
        ):
            self.assertIn(expected, content)

    def test_phase131_legacy_tenant_roots_are_still_active_compatibility_routes(self):
        path_cases = {
            "/party/": "party_list",
            "/girvi/deletemultiple/": "girvi_loan_deletemultiple",
            "/product/": "product_product_home",
            "/dea/": "dea_home",
        }

        for path, route_name in path_cases.items():
            with self.subTest(path=path):
                self.assertEqual(resolve(path, urlconf=tenant_urls).url_name, route_name)

    def test_phase131_slug_routes_are_entry_aliases_not_full_app_remounts_yet(self):
        route_cases = {
            "workspace_slug_parties": "/w/acme/parties/",
            "workspace_slug_loans": "/w/acme/loans/",
            "workspace_slug_inventory": "/w/acme/inventory/",
            "workspace_slug_accounting": "/w/acme/accounting/",
            "workspace_slug_operations": "/w/acme/operations/",
            "workspace_slug_reports": "/w/acme/reports/",
        }

        for route_name, path in route_cases.items():
            with self.subTest(route_name=route_name):
                self.assertEqual(reverse(route_name, kwargs={"workspace_slug": "acme"}), path)
                self.assertEqual(resolve(path, urlconf=tenant_urls).url_name, route_name)

        shared_urlpatterns = _read("django_project/shared_urlpatterns.py")
        org_views = _read("apps/orgs/views.py")
        self.assertIn("CANONICAL_WORKSPACE_SLUG_URLPATTERNS", shared_urlpatterns)

        parties_section = org_views.split("def workspace_slug_parties", 1)[1].split(
            "def workspace_slug_loans", 1
        )[0]
        loans_section = org_views.split("def workspace_slug_loans", 1)[1].split(
            "def workspace_slug_inventory", 1
        )[0]
        inventory_section = org_views.split("def workspace_slug_inventory", 1)[1].split(
            "def workspace_slug_accounting", 1
        )[0]
        accounting_section = org_views.split("def workspace_slug_accounting", 1)[1].split(
            "def workspace_slug_operations", 1
        )[0]
        self.assertIn("party_list(request)", parties_section)
        self.assertNotIn('redirect("party:party_list")', parties_section)
        self.assertIn("girvi_dashboard(request)", loans_section)
        self.assertNotIn('redirect("girvi:girvi_dashboard")', loans_section)
        self.assertIn("product_home(request)", inventory_section)
        self.assertNotIn('redirect("product_product_home")', inventory_section)
        self.assertIn("dea_home(request)", accounting_section)
        self.assertNotIn('redirect("dea_home")', accounting_section)

    def test_phase131_project_docs_no_longer_overclaim_full_canonicalization(self):
        status = _read("docs/STATUS.md")
        memory = _read("docs/AGENT_MEMORY.md")
        audit = _read("docs/ui/saas_information_architecture_audit.md")
        phase11_review = _read("docs/ui/workspace_slug_phase11_review.md")

        for content in (status, memory, audit, phase11_review):
            with self.subTest():
                self.assertIn("Phase 13", content)
                self.assertIn("tenant_route_canonicalization_phase13_plan.md", content)
                self.assertIn("tenant roots", content)

    def test_phase132_visible_tenant_entry_links_use_slug_aliases(self):
        sidebar = _read("templates/components/navigation/sidebar.html")
        dashboard = _read("templates/company/workspace_dashboard.html")
        plan = _read("docs/ui/tenant_route_canonicalization_phase13_plan.md")

        for expected in (
            "Status: complete",
            "workspace_slug_operations",
            "workspace_slug_reports",
            "workspace_slug_commodity",
            "workspace_slug_accounting",
            "Legacy tenant roots remain active",
            "Phase 13.3",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, plan + sidebar + dashboard)

        for legacy_entry in (
            "{% url 'dea_business_events_dashboard' %}",
            "{% url 'dea_reports_hub' %}",
            "{% url 'dea_commodity_list' %}",
            "{% url 'dea_dashboard' %}",
        ):
            with self.subTest(legacy_entry=legacy_entry):
                self.assertNotIn(legacy_entry, sidebar + dashboard)

    def test_phase133_parties_slug_entry_direct_renders_existing_party_list(self):
        org_views = _read("apps/orgs/views.py")
        plan = _read("docs/ui/tenant_route_canonicalization_phase13_plan.md")

        parties_section = org_views.split("def workspace_slug_parties", 1)[1].split(
            "def workspace_slug_loans", 1
        )[0]

        self.assertIn("Phase 13.3", plan)
        self.assertIn("Status: complete for the low-risk entrypoint set", plan)
        self.assertIn("/w/<workspace_slug>/parties/", plan)
        self.assertIn("from apps.tenant_apps.party.views import party_list", parties_section)
        self.assertIn("return party_list(request)", parties_section)
        self.assertNotIn('return redirect("party:party_list")', parties_section)

    def test_phase133_inventory_slug_entry_direct_renders_existing_product_home(self):
        org_views = _read("apps/orgs/views.py")
        plan = _read("docs/ui/tenant_route_canonicalization_phase13_plan.md")

        inventory_section = org_views.split("def workspace_slug_inventory", 1)[1].split(
            "def workspace_slug_accounting", 1
        )[0]

        self.assertIn("Phase 13.3", plan)
        self.assertIn("/w/<workspace_slug>/inventory/", plan)
        self.assertIn("Product entrypoint policy", plan)
        self.assertIn(
            "from apps.tenant_apps.product.views.home import home as product_home",
            inventory_section,
        )
        self.assertIn("return product_home(request)", inventory_section)
        self.assertNotIn('return redirect("product_product_home")', inventory_section)

    def test_phase133_loans_slug_entry_direct_renders_existing_girvi_dashboard(self):
        org_views = _read("apps/orgs/views.py")
        plan = _read("docs/ui/tenant_route_canonicalization_phase13_plan.md")

        loans_section = org_views.split("def workspace_slug_loans", 1)[1].split(
            "def workspace_slug_inventory", 1
        )[0]

        self.assertIn("Phase 13.3", plan)
        self.assertIn("/w/<workspace_slug>/loans/", plan)
        self.assertIn("Girvi workspace access guard", plan)
        self.assertIn(
            "from apps.tenant_apps.girvi.views.dashboard import girvi_dashboard",
            loans_section,
        )
        self.assertIn("return girvi_dashboard(request)", loans_section)
        self.assertNotIn('return redirect("girvi:girvi_dashboard")', loans_section)

    def test_phase133_accounting_slug_entry_direct_renders_existing_dea_home(self):
        org_views = _read("apps/orgs/views.py")
        plan = _read("docs/ui/tenant_route_canonicalization_phase13_plan.md")

        accounting_section = org_views.split("def workspace_slug_accounting", 1)[1].split(
            "def workspace_slug_operations", 1
        )[0]

        self.assertIn("Phase 13.3", plan)
        self.assertIn("/w/<workspace_slug>/accounting/", plan)
        self.assertIn("DEA home view", plan)
        self.assertIn(
            "from apps.tenant_apps.dea.views.common import home as dea_home",
            accounting_section,
        )
        self.assertIn("return dea_home(request)", accounting_section)
        self.assertNotIn('return redirect("dea_home")', accounting_section)

    def test_phase134_deep_link_plan_exists_before_nested_remounts(self):
        plan = _read("docs/ui/tenant_deep_link_canonicalization_phase13_4_plan.md")
        shared_urlpatterns = _read("django_project/shared_urlpatterns.py")

        for expected in (
            "Tenant Deep-Link Canonicalization Phase 13.4 Plan",
            "planning and guard phase",
            "Do not include full app URLConfs under `/w/<workspace_slug>/...` yet",
            "Do not remove legacy tenant roots",
            "Party",
            "Product And Inventory",
            "Rates",
            "Notify And Notify V2",
            "Data Tools",
            "Girvi",
            "DEA",
            "Phase 13.5a",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, plan)

        self.assertIn("Recommended first deep-link module", plan)
        self.assertIn("/w/<workspace_slug>/parties/<pk>/", plan)
        self.assertIn("Customer portal `/portal/...` remains out of scope", plan)

        forbidden_remounts = (
            'include("apps.tenant_apps.party.urls")',
            'include("apps.tenant_apps.product.urls")',
            'include("apps.tenant_apps.girvi.urls")',
            'include("apps.tenant_apps.dea.urls")',
        )
        slug_urlpatterns = shared_urlpatterns.split(
            "CANONICAL_WORKSPACE_SLUG_URLPATTERNS", 1
        )[1]
        for forbidden in forbidden_remounts:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, slug_urlpatterns)

    def test_phase141_party_read_only_deep_aliases_direct_render_existing_views(self):
        route_cases = {
            "workspace_slug_party_create": (
                {"workspace_slug": "acme"},
                "/w/acme/parties/new/",
                "from apps.tenant_apps.party.views import party_create",
                "return party_create(request)",
            ),
            "workspace_slug_party_detail": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/parties/7/",
                "from apps.tenant_apps.party.views import party_detail",
                "return party_detail(request, pk=pk)",
            ),
            "workspace_slug_party_update": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/parties/7/edit/",
                "from apps.tenant_apps.party.views import party_update",
                "return party_update(request, pk=pk)",
            ),
            "workspace_slug_party_merge": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/parties/7/merge/",
                "from apps.tenant_apps.party.views import party_merge",
                "return party_merge(request, pk=pk)",
            ),
        }

        org_views = _read("apps/orgs/views.py")

        for route_name, (kwargs, path, import_line, return_line) in route_cases.items():
            with self.subTest(route_name=route_name):
                self.assertEqual(reverse(route_name, kwargs=kwargs), path)
                self.assertEqual(resolve(path, urlconf=tenant_urls).url_name, route_name)
                self.assertIn(f"def {route_name}", org_views)
                self.assertIn(import_line, org_views)
                self.assertIn(return_line, org_views)

    def test_phase135a_party_nested_mutation_aliases_remain_absent(self):
        absent_paths = (
            "/w/acme/parties/7/contacts/save/",
            "/w/acme/parties/7/addresses/save/",
            "/w/acme/parties/7/identifiers/save/",
            "/w/acme/parties/7/documents/save/",
            "/w/acme/parties/7/roles/add/",
        )

        for path in absent_paths:
            with self.subTest(path=path):
                with self.assertRaises(Resolver404):
                    resolve(path, urlconf=tenant_urls)

    def test_phase142_party_visible_get_links_prefer_slug_routes(self):
        template_cases = {
            "templates/party/list.html": (
                "workspace_slug_party_create",
                "workspace_slug_party_detail",
                "workspace_slug_party_update",
            ),
            "templates/party/form.html": (
                "workspace_slug_party_detail",
                "workspace_slug_parties",
            ),
            "templates/party/detail.html": (
                "workspace_slug_parties",
                "workspace_slug_party_detail",
                "workspace_slug_party_update",
            ),
            "templates/party/customer_convert.html": ("workspace_slug_parties",),
        }

        for template_path, expected_routes in template_cases.items():
            content = _read(template_path)
            with self.subTest(template_path=template_path):
                for route_name in expected_routes:
                    self.assertIn(route_name, content)

        detail = _read("templates/party/detail.html")
        for legacy_mutation_route in (
            "party:party_contact_add",
            "party:party_address_add",
            "party:party_identifier_add",
            "party:party_document_add",
            "party:party_role_add",
        ):
            with self.subTest(legacy_mutation_route=legacy_mutation_route):
                self.assertIn(legacy_mutation_route, detail)

    def test_phase142_low_risk_read_only_module_aliases_resolve(self):
        route_cases = {
            "workspace_slug_inventory_products": (
                {"workspace_slug": "acme"},
                "/w/acme/inventory/products/",
                "product_list(request)",
            ),
            "workspace_slug_inventory_product_detail": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/inventory/products/7/",
                "product_detail(request, pk=pk)",
            ),
            "workspace_slug_inventory_stock": (
                {"workspace_slug": "acme"},
                "/w/acme/inventory/stock/",
                "stock_list(request)",
            ),
            "workspace_slug_inventory_stock_detail": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/inventory/stock/7/",
                "StockDetailView.as_view()(request, pk=pk)",
            ),
            "workspace_slug_inventory_stock_audit": (
                {"workspace_slug": "acme"},
                "/w/acme/inventory/stock/audit/",
                "audit_stock(request)",
            ),
            "workspace_slug_inventory_transactions": (
                {"workspace_slug": "acme"},
                "/w/acme/inventory/transactions/",
                "StockTransactionListView.as_view()(request)",
            ),
            "workspace_slug_inventory_statements": (
                {"workspace_slug": "acme"},
                "/w/acme/inventory/statements/",
                "StockStatementListView.as_view()(request)",
            ),
            "workspace_slug_rates": (
                {"workspace_slug": "acme"},
                "/w/acme/rates/",
                "rate_list(request)",
            ),
            "workspace_slug_rate_detail": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/rates/7/",
                "rate_detail(request, pk=pk)",
            ),
            "workspace_slug_rate_sources": (
                {"workspace_slug": "acme"},
                "/w/acme/rates/sources/",
                "ratesource_list(request)",
            ),
            "workspace_slug_rate_source_detail": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/rates/sources/7/",
                "ratesource_detail(request, pk=pk)",
            ),
            "workspace_slug_notifications": (
                {"workspace_slug": "acme"},
                "/w/acme/notifications/",
                "notification_list(request)",
            ),
            "workspace_slug_notification_detail": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/notifications/7/",
                "notification_detail(request, pk=pk)",
            ),
            "workspace_slug_notice_groups": (
                {"workspace_slug": "acme"},
                "/w/acme/notifications/notice-groups/",
                "noticegroup_list(request)",
            ),
            "workspace_slug_notice_group_detail": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/notifications/notice-groups/7/",
                "noticegroup_detail(request, pk=pk)",
            ),
            "workspace_slug_data_tools_export": (
                {"workspace_slug": "acme"},
                "/w/acme/data-tools/export/",
                "export_form(request)",
            ),
            "workspace_slug_data_tools_export_data": (
                {
                    "workspace_slug": "acme",
                    "model_name": "Party",
                    "export_format": "csv",
                },
                "/w/acme/data-tools/export/Party/csv/",
                "export_data(request, model_name=model_name, export_format=export_format)",
            ),
        }

        org_views = _read("apps/orgs/views.py")

        for route_name, (kwargs, path, delegate_call) in route_cases.items():
            with self.subTest(route_name=route_name):
                self.assertEqual(reverse(route_name, kwargs=kwargs), path)
                self.assertEqual(resolve(path, urlconf=tenant_urls).url_name, route_name)
                self.assertIn(f"def {route_name}", org_views)
                self.assertIn(delegate_call, org_views)

    def test_phase142_low_risk_mutation_aliases_remain_absent(self):
        absent_paths = (
            "/w/acme/inventory/products/7/update/",
            "/w/acme/inventory/stock/create/",
            "/w/acme/rates/new/",
            "/w/acme/rates/7/edit/",
            "/w/acme/notifications/create/",
            "/w/acme/notifications/7/delete/",
            "/w/acme/data-tools/import/",
        )

        for path in absent_paths:
            with self.subTest(path=path):
                with self.assertRaises(Resolver404):
                    resolve(path, urlconf=tenant_urls)

    def test_phase15_girvi_read_only_loan_aliases_resolve(self):
        route_cases = {
            "workspace_slug_loan_list": (
                {"workspace_slug": "acme"},
                "/w/acme/loans/list/",
                "loan_list(request)",
            ),
            "workspace_slug_loan_table": (
                {"workspace_slug": "acme"},
                "/w/acme/loans/table/",
                "loan_table_partial(request)",
            ),
            "workspace_slug_loan_detail": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/loans/7/",
                "loan_detail(request, pk=pk)",
            ),
            "workspace_slug_loan_detail_items": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/loans/7/items/",
                "loan_detail_items_tab(request, pk=pk)",
            ),
            "workspace_slug_loan_detail_payments": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/loans/7/payments/",
                "loan_detail_payments_tab(request, pk=pk)",
            ),
            "workspace_slug_loan_detail_transactions": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/loans/7/transactions/",
                "loan_detail_transactions_tab(request, pk=pk)",
            ),
            "workspace_slug_loan_detail_statement": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/loans/7/statement/",
                "loan_detail_statement_tab(request, pk=pk)",
            ),
            "workspace_slug_loan_detail_notices": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/loans/7/notices/",
                "loan_detail_notices_tab(request, pk=pk)",
            ),
            "workspace_slug_loan_detail_release": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/loans/7/release/",
                "loan_detail_release_tab(request, pk=pk)",
            ),
            "workspace_slug_loan_pdf": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/loans/7/pdf/",
                "print_loan(request, pk=pk)",
            ),
            "workspace_slug_loan_report": (
                {"workspace_slug": "acme"},
                "/w/acme/loans/reports/time-series/",
                "LoanTimeSeriesReport.as_view()(request)",
            ),
            "workspace_slug_loan_by_customer_report": (
                {"workspace_slug": "acme"},
                "/w/acme/loans/reports/by-customer/",
                "LoanByCustomerReport.as_view()(request)",
            ),
            "workspace_slug_loan_crosstab_report": (
                {"workspace_slug": "acme"},
                "/w/acme/loans/reports/crosstab/",
                "LoanCrosstabReport.as_view()(request)",
            ),
            "workspace_slug_loan_list_report": (
                {"workspace_slug": "acme"},
                "/w/acme/loans/reports/list/",
                "LoanListReport.as_view()(request)",
            ),
            "workspace_slug_loan_reconciliation_report": (
                {"workspace_slug": "acme"},
                "/w/acme/loans/reports/reconciliation/",
                "loan_accounting_reconciliation_report(request)",
            ),
            "workspace_slug_loan_operational_controls_report": (
                {"workspace_slug": "acme"},
                "/w/acme/loans/reports/operational-controls/",
                "loan_operational_controls_report(request)",
            ),
        }

        org_views = _read("apps/orgs/views.py")

        for route_name, (kwargs, path, delegate_call) in route_cases.items():
            with self.subTest(route_name=route_name):
                self.assertEqual(reverse(route_name, kwargs=kwargs), path)
                self.assertEqual(resolve(path, urlconf=tenant_urls).url_name, route_name)
                self.assertIn(f"def {route_name}", org_views)
                self.assertIn(delegate_call, org_views)

    def test_phase15_girvi_mutation_aliases_remain_absent(self):
        absent_paths = (
            "/w/acme/loans/create/",
            "/w/acme/loans/7/update/",
            "/w/acme/loans/7/delete/",
            "/w/acme/loans/7/renew/",
            "/w/acme/loans/7/repayment/create/",
            "/w/acme/loans/releases/create/",
            "/w/acme/loans/7/transition/",
            "/w/acme/loans/custody/repledge/create/",
            "/w/acme/loans/operations-console/",
        )

        for path in absent_paths:
            with self.subTest(path=path):
                with self.assertRaises(Resolver404):
                    resolve(path, urlconf=tenant_urls)

    def test_phase13_review_closes_safe_boundary_not_full_remount(self):
        review = _read("docs/ui/tenant_route_canonicalization_phase13_review.md")

        for expected in (
            "Phase 13 is complete at the safe compatibility boundary",
            "does not remove legacy tenant roots",
            "does not remount full tenant app",
            "Party read-only deep aliases",
            "Nested Party mutation aliases remain absent by design",
            "direct-render Party deep aliases",
            "Product/Inventory",
            "Girvi deep aliases",
            "DEA deep aliases",
            "Start the next route-canonicalization phase",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, review)
