from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.orgs.middleware_v2 import SecureWorkspaceMiddleware


class PlatformOverrideAuditContractTests(SimpleTestCase):
    def test_explicit_platform_override_is_audited_after_context_establishment(self):
        middleware = SecureWorkspaceMiddleware(lambda request: None)
        workspace = SimpleNamespace(id=19, schema_name="audit-ws", name="Audit WS")
        actor = SimpleNamespace(
            id=7,
            email="platform@example.com",
            is_authenticated=True,
            is_superuser=True,
        )
        request = SimpleNamespace(
            path="/w/audit-ws/loans/",
            user=actor,
            META={},
        )
        access = SimpleNamespace(platform_override=True, membership=None)

        def establish_context(target_request, target_workspace):
            target_request.workspace = target_workspace

        with (
            patch.object(middleware, "_is_exempt_url", return_value=False),
            patch.object(middleware, "_resolve_workspace_from_domain", return_value=None),
            patch.object(middleware, "_resolve_workspace_from_path", return_value=workspace),
            patch.object(
                middleware,
                "_validate_workspace_access",
                return_value={"allowed": True, "access": access},
            ),
            patch.object(
                middleware, "_set_workspace_context", side_effect=establish_context
            ) as set_context,
            patch.object(middleware, "_log_access") as generic_access_log,
            patch("apps.orgs.middleware_v2.AuditLog.log") as audit_log,
        ):
            response = middleware.process_request(request)

        self.assertIsNone(response)
        self.assertIs(request.workspace, workspace)
        self.assertEqual(request.workspace_resolution_source, "path")
        set_context.assert_called_once_with(request, workspace)
        generic_access_log.assert_not_called()
        audit_log.assert_called_once_with(
            action="WORKSPACE_ACCESS",
            user=actor,
            company=workspace,
            description="Platform override access to workspace Audit WS",
            request=request,
            success=True,
            data={
                "workspace_id": 19,
                "path": "/w/audit-ws/loans/",
                "resolution_source": "path",
                "platform_override": True,
            },
        )
