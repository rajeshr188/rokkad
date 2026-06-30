from pathlib import Path

from django.test import SimpleTestCase


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_ROOT = PROJECT_ROOT / "templates"
STATIC_ROOT = PROJECT_ROOT / "static"


def _template_files():
    return sorted(TEMPLATES_ROOT.rglob("*.html"))


def _relative(path):
    return path.relative_to(TEMPLATES_ROOT).as_posix()


def _extends_line(path):
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if stripped.startswith("{% extends "):
            return stripped
    return ""


class SaaSTemplateLayoutIntentTests(SimpleTestCase):
    WORKSPACE_SETTINGS_TEMPLATES = {
        "company/company_delete_confirm.html",
        "company/company_detail.html",
        "company/company_invitations_list.html",
        "company/company_preferences.html",
        "company/workspace_setup.html",
        "company/invitation_form.html",
        "company/membership_list.html",
        "company/workspace_leave_confirm.html",
        "dynamic_preferences/form.html",
        "subscriptions/checkout.html",
        "subscriptions/dashboard.html",
        "subscriptions/invoice_detail.html",
        "subscriptions/plan_list.html",
    }
    SETUP_COMPONENT_TEMPLATES = {
        "components/setup/setup_checklist_task.html",
    }

    def test_shell_aliases_extend_their_intended_layouts(self):
        alias_contracts = {
            "base_public.html": 'extends "layouts/base.html"',
            "base_auth.html": 'extends "layouts/base.html"',
            "base_global.html": 'extends "layouts/management.html"',
            "base_workspace_settings.html": 'extends "layouts/management.html"',
            "base_tenant.html": 'extends "layouts/workspace.html"',
            "base_customer_portal.html": 'extends "layouts/base.html"',
        }

        for rel_path, expected_extends in alias_contracts.items():
            with self.subTest(rel_path=rel_path):
                self.assertIn(expected_extends, _extends_line(TEMPLATES_ROOT / rel_path))

    def test_shell_aliases_own_only_their_expected_static_stylesheets(self):
        public_alias = (TEMPLATES_ROOT / "base_public.html").read_text(
            encoding="utf-8-sig"
        )
        auth_alias = (TEMPLATES_ROOT / "base_auth.html").read_text(
            encoding="utf-8-sig"
        )
        global_alias = (TEMPLATES_ROOT / "base_global.html").read_text(
            encoding="utf-8-sig"
        )
        settings_alias = (TEMPLATES_ROOT / "base_workspace_settings.html").read_text(
            encoding="utf-8-sig"
        )
        tenant_alias = (TEMPLATES_ROOT / "base_tenant.html").read_text(
            encoding="utf-8-sig"
        )
        customer_portal_alias = (TEMPLATES_ROOT / "base_customer_portal.html").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("{% static 'css/public.css' %}", public_alias)
        self.assertIn("public-shell", public_alias)
        self.assertIn("{% static 'css/public.css' %}", auth_alias)
        self.assertIn("auth-shell", auth_alias)
        self.assertIn("{% static 'css/workspace.css' %}", tenant_alias)

        for content in (public_alias, auth_alias):
            with self.subTest(shell="public_or_auth"):
                self.assertNotIn("css/management.css", content)
                self.assertNotIn("css/workspace.css", content)

        for content in (global_alias, settings_alias, customer_portal_alias):
            with self.subTest(shell="management_or_portal_alias"):
                self.assertNotIn("css/public.css", content)
                self.assertNotIn("css/workspace.css", content)

        self.assertNotIn("css/public.css", tenant_alias)
        self.assertNotIn("css/management.css", tenant_alias)

    def test_shell_layouts_do_not_reintroduce_inline_style_blocks(self):
        shell_templates = (
            "base_public.html",
            "base_auth.html",
            "base_global.html",
            "base_workspace_settings.html",
            "base_tenant.html",
            "base_customer_portal.html",
            "layouts/management.html",
            "layouts/workspace.html",
            "components/navigation/workspace_switcher.html",
            "components/navigation/workspace_manager_sidebar.html",
            "components/navigation/workspace_settings_sidebar.html",
            "components/navigation/account_sidebar.html",
            "components/navigation/sidebar.html",
        )

        for rel_path in shell_templates:
            content = (TEMPLATES_ROOT / rel_path).read_text(encoding="utf-8-sig")
            with self.subTest(rel_path=rel_path):
                self.assertNotIn("<style>", content)
                self.assertNotIn("</style>", content)

    def test_known_root_shell_inline_style_debt_stays_documented(self):
        base_layout = (TEMPLATES_ROOT / "layouts/base.html").read_text(
            encoding="utf-8-sig"
        )
        main_nav = (TEMPLATES_ROOT / "components/navigation/main_nav.html").read_text(
            encoding="utf-8-sig"
        )
        phase8_plan = (
            PROJECT_ROOT / "docs" / "ui" / "phase8_regression_consolidation_plan.md"
        ).read_text(encoding="utf-8-sig")

        self.assertIn("Dropdown Submenu Styling", base_layout)
        self.assertIn("<style>", base_layout)
        self.assertIn(".modern-nav", main_nav)
        self.assertIn("<style>", main_nav)
        self.assertIn("root `layouts/base.html` and `main_nav.html` inline style debt", phase8_plan)

    def test_direct_low_level_base_extends_are_infrastructure_only(self):
        allowed = {
            "_base.html",
            "allauth/layouts/base.html",
            "base_auth.html",
            "base_customer_portal.html",
            "base_public.html",
            "layouts/management.html",
            "layouts/workspace.html",
            "slick_reporting/base.html",
        }
        violations = []

        for path in _template_files():
            rel_path = _relative(path)
            line = _extends_line(path)
            if "layouts/base.html" in line and rel_path not in allowed:
                violations.append(f"{rel_path}: {line}")

        self.assertEqual(violations, [])

    def test_direct_management_and_workspace_extends_are_aliases_only(self):
        allowed = {
            "base_global.html",
            "base_tenant.html",
            "base_workspace_settings.html",
        }
        violations = []

        for path in _template_files():
            rel_path = _relative(path)
            line = _extends_line(path)
            if (
                "layouts/management.html" in line
                or "layouts/workspace.html" in line
            ) and rel_path not in allowed:
                violations.append(f"{rel_path}: {line}")

        self.assertEqual(violations, [])

    def test_tenant_alias_children_use_workspace_content_block(self):
        violations = []

        for path in _template_files():
            line = _extends_line(path)
            if "base_tenant.html" not in line:
                continue
            content = path.read_text(encoding="utf-8-sig")
            if "{% block content %}" in content or "{%block content%}" in content:
                violations.append(_relative(path))
            if "{% block workspace_content %}" not in content and "{%block workspace_content%}" not in content:
                violations.append(f"{_relative(path)}: missing workspace_content")

        self.assertEqual(violations, [])

    def test_management_alias_children_use_mgmt_content_block(self):
        violations = []

        for path in _template_files():
            if _relative(path) in self.SETUP_COMPONENT_TEMPLATES:
                continue
            line = _extends_line(path)
            if "base_global.html" not in line and "base_workspace_settings.html" not in line:
                continue
            content = path.read_text(encoding="utf-8-sig")
            if "{% block content %}" in content or "{%block content%}" in content:
                violations.append(_relative(path))
            if "{% block mgmt_content %}" not in content and "{%block mgmt_content%}" not in content:
                violations.append(f"{_relative(path)}: missing mgmt_content")

        self.assertEqual(violations, [])

    def test_workspace_settings_templates_use_settings_alias(self):
        violations = []

        for rel_path in self.WORKSPACE_SETTINGS_TEMPLATES:
            line = _extends_line(TEMPLATES_ROOT / rel_path)
            if "base_workspace_settings.html" not in line:
                violations.append(f"{rel_path}: {line}")

        self.assertEqual(violations, [])

    def test_management_layout_exposes_workspace_settings_include_points(self):
        content = (TEMPLATES_ROOT / "layouts/management.html").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("{% block workspace_settings_sidebar %}", content)
        self.assertIn("{% block mobile_workspace_settings_sidebar %}", content)
        self.assertIn(
            "{% include 'components/navigation/workspace_settings_sidebar.html' with workspace_settings_sidebar_variant=\"desktop\" %}",
            content,
        )
        self.assertIn(
            "{% include 'components/navigation/workspace_settings_sidebar.html' with workspace_settings_sidebar_variant=\"mobile\" %}",
            content,
        )

    def test_workspace_settings_sidebar_owns_workspace_admin_links(self):
        management_content = (TEMPLATES_ROOT / "layouts/management.html").read_text(
            encoding="utf-8-sig"
        )
        sidebar_content = (
            TEMPLATES_ROOT / "components/navigation/workspace_settings_sidebar.html"
        ).read_text(encoding="utf-8-sig")

        self.assertIn('workspace_settings_sidebar_variant == "desktop"', sidebar_content)
        self.assertIn('workspace_settings_sidebar_variant == "mobile"', sidebar_content)
        self.assertIn("role_name == 'Admin'", sidebar_content)
        self.assertIn("role_name == 'Superuser'", sidebar_content)
        for route_fragment in (
            "{% url 'workspace_settings_home' workspace_id=ew.id %}",
            "{% url 'workspace_settings_setup' workspace_id=ew.id %}",
            "{% url 'workspace_settings_preferences' workspace_id=ew.id %}",
            "{% url 'workspace_settings_team' workspace_id=ew.id %}",
            "{% url 'workspace_settings_invite' workspace_id=ew.id %}",
            "{% url 'workspace_settings_invitations' workspace_id=ew.id %}",
        ):
            self.assertIn(route_fragment, sidebar_content)

        for route_name in (
            "workspace_detail",
            "workspace_setup",
            "workspace_preferences",
            "team_members_list",
            "team_invite",
            "team_invitations_list",
        ):
            self.assertIn(route_name, sidebar_content)

        desktop_section = management_content.split(
            "{% block workspace_settings_sidebar %}", 1
        )[0]
        mobile_section = management_content.split(
            "{% block mobile_workspace_settings_sidebar %}", 1
        )[0]
        for route_name in (
            "workspace_detail",
            "workspace_setup",
            "workspace_preferences",
            "team_members_list",
            "team_invite",
            "team_invitations_list",
        ):
            self.assertNotIn(route_name, desktop_section)
            self.assertNotIn(route_name, mobile_section)

        self.assertIn(
            "{% include 'components/navigation/workspace_settings_sidebar.html' with workspace_settings_sidebar_variant=\"desktop\" %}",
            management_content,
        )
        self.assertIn(
            "{% include 'components/navigation/workspace_settings_sidebar.html' with workspace_settings_sidebar_variant=\"mobile\" %}",
            management_content,
        )

    def test_account_sidebar_owns_account_management_links(self):
        management_content = (TEMPLATES_ROOT / "layouts/management.html").read_text(
            encoding="utf-8-sig"
        )
        sidebar_content = (
            TEMPLATES_ROOT / "components/navigation/account_sidebar.html"
        ).read_text(encoding="utf-8-sig")

        self.assertIn('account_sidebar_variant == "desktop"', sidebar_content)
        self.assertIn('account_sidebar_variant == "mobile"', sidebar_content)
        for route_fragment in (
            "{% url 'app_invitations' %}",
            "{% url 'subscriptions:dashboard' %}",
            "{% url 'account_settings' %}",
            "{% url 'profile' %}",
        ):
            self.assertIn(route_fragment, sidebar_content)
            self.assertNotIn(route_fragment, management_content)
        self.assertIn("team_invitations", sidebar_content)

        self.assertIn("{% block account_sidebar %}", management_content)
        self.assertIn("{% block mobile_account_sidebar %}", management_content)
        self.assertIn(
            "{% include 'components/navigation/account_sidebar.html' with account_sidebar_variant=\"desktop\" %}",
            management_content,
        )
        self.assertIn(
            "{% include 'components/navigation/account_sidebar.html' with account_sidebar_variant=\"mobile\" %}",
            management_content,
        )

    def test_workspace_manager_sidebar_owns_workspace_manager_links(self):
        management_content = (TEMPLATES_ROOT / "layouts/management.html").read_text(
            encoding="utf-8-sig"
        )
        sidebar_content = (
            TEMPLATES_ROOT / "components/navigation/workspace_manager_sidebar.html"
        ).read_text(encoding="utf-8-sig")

        self.assertIn('workspace_manager_sidebar_variant == "desktop"', sidebar_content)
        self.assertIn('workspace_manager_sidebar_variant == "mobile"', sidebar_content)
        for route_fragment in (
            "{% url 'app_workspaces' %}",
            "{% url 'app_workspace_create' %}",
        ):
            self.assertIn(route_fragment, sidebar_content)
            self.assertNotIn(route_fragment, management_content)
        for legacy_route_name in ("workspace_selector", "workspace_create"):
            self.assertIn(legacy_route_name, sidebar_content)

        self.assertIn("{% block workspace_manager_sidebar %}", management_content)
        self.assertIn("{% block mobile_workspace_manager_sidebar %}", management_content)
        self.assertIn(
            "{% include 'components/navigation/workspace_manager_sidebar.html' with workspace_manager_sidebar_variant=\"desktop\" %}",
            management_content,
        )
        self.assertIn(
            "{% include 'components/navigation/workspace_manager_sidebar.html' with workspace_manager_sidebar_variant=\"mobile\" %}",
            management_content,
        )

    def test_management_layout_comments_stay_current(self):
        content = (TEMPLATES_ROOT / "layouts/management.html").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("Control-plane layout for account and workspace management", content)
        self.assertNotIn("Duplicate sidebar content", content)
        self.assertNotIn("â", content)

    def test_management_layout_uses_restrained_visual_contract(self):
        content = (TEMPLATES_ROOT / "layouts/management.html").read_text(
            encoding="utf-8-sig"
        )
        base_content = (TEMPLATES_ROOT / "layouts/base.html").read_text(
            encoding="utf-8-sig"
        )
        css_content = (STATIC_ROOT / "css" / "management.css").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("{% load static orgs_tags %}", content)
        self.assertIn("{% static 'css/management.css' %}", content)
        self.assertNotIn("<style>", content)
        self.assertNotIn("</style>", content)
        self.assertIn(".mgmt-nav-link", css_content)
        self.assertIn(".mgmt-section-title", css_content)
        self.assertIn(".mgmt-offcanvas", css_content)
        self.assertIn("{% block main_wrapper_class %}container-lg mt-4{% endblock %}", base_content)
        self.assertIn(
            "{% block main_wrapper_class %}container-fluid p-0 mt-0{% endblock %}",
            content,
        )
        self.assertIn("background: #1f2937", css_content)
        self.assertIn("box-shadow: inset 3px 0 0 #0f766e", css_content)
        self.assertNotIn("linear-gradient(90deg, #7c3aed", content)
        self.assertNotIn("linear-gradient(90deg, #7c3aed", css_content)
        self.assertNotIn("style=\"background:#f8f7ff", content)
        self.assertNotIn("style=\"color:#7c3aed", content)

    def test_management_sidebar_partials_share_visual_link_class(self):
        partials = (
            "components/navigation/workspace_manager_sidebar.html",
            "components/navigation/workspace_settings_sidebar.html",
            "components/navigation/account_sidebar.html",
        )

        for partial in partials:
            with self.subTest(partial=partial):
                content = (TEMPLATES_ROOT / partial).read_text(encoding="utf-8-sig")
                self.assertIn("mgmt-nav-link", content)
                self.assertNotIn("nav-link py-2", content)

    def test_workspace_layout_and_sidebar_use_static_visual_contract(self):
        workspace_layout = (TEMPLATES_ROOT / "layouts/workspace.html").read_text(
            encoding="utf-8-sig"
        )
        tenant_alias = (TEMPLATES_ROOT / "base_tenant.html").read_text(
            encoding="utf-8-sig"
        )
        sidebar = (TEMPLATES_ROOT / "components/navigation/sidebar.html").read_text(
            encoding="utf-8-sig"
        )
        workspace_css = (STATIC_ROOT / "css" / "workspace.css").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("{% static 'css/workspace.css' %}", tenant_alias)
        self.assertIn("workspace-shell", workspace_layout)
        self.assertIn("workspace-context-bar", workspace_layout)
        self.assertIn("workspace-sidebar", workspace_layout)
        self.assertIn("workspace-content", workspace_layout)
        self.assertNotIn("<style>", workspace_layout)
        self.assertNotIn("</style>", workspace_layout)

        self.assertIn("workspace-sidebar-wrapper", sidebar)
        self.assertIn("workspace-identity", sidebar)
        self.assertIn("workspace-nav-link", sidebar)
        self.assertIn("workspace-nav-section-title", sidebar)
        self.assertNotIn("<style>", sidebar)
        self.assertNotIn("</style>", sidebar)
        self.assertNotIn('class="nav-link', sidebar)

        for expected in (
            ".workspace-context-bar",
            ".workspace-nav-link",
            ".tenant-stat-grid",
            ".tenant-quick-action",
            ".tenant-panel",
        ):
            self.assertIn(expected, workspace_css)
