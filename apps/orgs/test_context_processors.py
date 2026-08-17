from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.orgs.context_processors import theme_processor


class ThemeProcessorTests(SimpleTestCase):
    def test_authenticated_public_request_without_workspace_uses_defaults(self):
        request = SimpleNamespace(
            user=SimpleNamespace(is_authenticated=True),
            workspace=None,
            tenant=None,
        )

        self.assertEqual(theme_processor(request), {"theme": "", "logo": None})

    def test_workspace_theme_is_used_when_context_exists(self):
        workspace = SimpleNamespace(theme="#123456", logo="logo.png")
        request = SimpleNamespace(
            user=SimpleNamespace(is_authenticated=True),
            workspace=workspace,
            tenant=None,
        )

        self.assertEqual(
            theme_processor(request),
            {"theme": "#123456", "logo": "logo.png"},
        )

    def test_legacy_tenant_alias_is_not_independent_authority(self):
        workspace = SimpleNamespace(theme="#abcdef", logo=None)
        request = SimpleNamespace(
            user=SimpleNamespace(is_authenticated=True),
            tenant=workspace,
        )

        self.assertEqual(
            theme_processor(request),
            {"theme": "", "logo": None},
        )
