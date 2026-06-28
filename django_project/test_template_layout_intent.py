from pathlib import Path

from django.test import SimpleTestCase


TEMPLATES_ROOT = Path(__file__).resolve().parent.parent / "templates"


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
        "company/invitation_form.html",
        "company/membership_list.html",
        "company/workspace_leave_confirm.html",
        "dynamic_preferences/form.html",
        "subscriptions/checkout.html",
        "subscriptions/dashboard.html",
        "subscriptions/invoice_detail.html",
        "subscriptions/plan_list.html",
    }

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

    def test_workspace_settings_sidebar_owns_desktop_workspace_admin_links(self):
        management_content = (TEMPLATES_ROOT / "layouts/management.html").read_text(
            encoding="utf-8-sig"
        )
        sidebar_content = (
            TEMPLATES_ROOT / "components/navigation/workspace_settings_sidebar.html"
        ).read_text(encoding="utf-8-sig")

        self.assertIn('workspace_settings_sidebar_variant == "desktop"', sidebar_content)
        for route_name in (
            "workspace_detail",
            "workspace_preferences",
            "team_members_list",
            "team_invite",
            "team_invitations_list",
        ):
            self.assertIn(route_name, sidebar_content)

        desktop_section = management_content.split(
            "{% block workspace_settings_sidebar %}", 1
        )[0]
        for route_name in (
            "workspace_detail",
            "workspace_preferences",
            "team_members_list",
            "team_invite",
            "team_invitations_list",
        ):
            self.assertNotIn(route_name, desktop_section)

        self.assertIn(
            "{% include 'components/navigation/workspace_settings_sidebar.html' %}",
            management_content,
        )
