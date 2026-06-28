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
