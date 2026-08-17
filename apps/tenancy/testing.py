from django.conf import settings
from django.test import Client, TestCase
from django.test.client import MULTIPART_CONTENT
from django.urls import reverse

from apps.orgs.models import Company, Domain

from .context import workspace_context


class WorkspaceClient(Client):
    def __init__(self, workspace, **defaults):
        self.workspace = workspace
        domain = workspace.domains.filter(is_primary=True).first()
        if domain is not None:
            defaults.setdefault("HTTP_HOST", domain.domain)
        super().__init__(**defaults)

    def workspace_url(self, url):
        """Return the explicit path-scoped form of a legacy business URL."""
        if not url.startswith("/"):
            raise ValueError("Workspace URLs must be absolute paths.")
        return f"/w/{self.workspace.schema_name}{url}"

    def workspace_get(self, url, data=None, **extra):
        return self.get(self.workspace_url(url), data=data, **extra)

    def workspace_post(self, url, data=None, **extra):
        return self.post(self.workspace_url(url), data=data, **extra)

    def get(self, path, data=None, follow=False, secure=False, *, headers=None, query_params=None, **extra):
        if path.startswith("/loans/"):
            path = self.workspace_url(path)
        return super().get(
            path,
            data=data,
            follow=follow,
            secure=secure,
            headers=headers,
            query_params=query_params,
            **extra,
        )

    def post(self, path, data=None, content_type=MULTIPART_CONTENT, follow=False, secure=False, *, headers=None, query_params=None, **extra):
        if path.startswith("/loans/"):
            path = self.workspace_url(path)
        return super().post(
            path,
            data=data,
            content_type=content_type,
            follow=follow,
            secure=secure,
            headers=headers,
            query_params=query_params,
            **extra,
        )


class WorkspaceTestCase(TestCase):
    """Django test case with one ordinary Workspace and active DB context."""

    tenant = None

    @classmethod
    def get_test_schema_name(cls):
        return "test-workspace"

    @classmethod
    def setup_tenant(cls, tenant):
        pass

    @classmethod
    def get_test_tenant_domain(cls):
        return f"{cls.get_test_schema_name()}.test.com"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tenant = Company(schema_name=cls.get_test_schema_name())
        cls.setup_tenant(cls.tenant)
        cls.tenant.save()
        cls.domain = Domain.objects.create(
            tenant=cls.tenant,
            domain=cls.get_test_tenant_domain(),
            is_primary=True,
        )
        if cls.domain.domain not in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS.append(cls.domain.domain)
            cls._added_allowed_host = True
        else:
            cls._added_allowed_host = False
        cls._workspace_context = workspace_context(cls.tenant.pk)
        cls._workspace_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._workspace_context.__exit__(None, None, None)
        if cls._added_allowed_host:
            settings.ALLOWED_HOSTS.remove(cls.domain.domain)
        super().tearDownClass()

    def make_workspace_client(self):
        return WorkspaceClient(self.tenant)

    def start_active_trial(self):
        """Create real, currently valid commercial state for this Workspace."""
        from apps.subscriptions.models import Plan, Subscription

        plan = Plan.objects.create(
            name=f"Test trial for {self.tenant.schema_name}",
            tier=Plan.PlanTierChoices.STARTER,
            price=0,
            description="Workspace test harness trial",
            trial_days=14,
        )
        return Subscription.objects.create(company=self.tenant, plan=plan)

    def workspace_reverse(self, viewname, *, args=None, kwargs=None):
        """Reverse a business route beneath the explicit Workspace path."""
        url = reverse(viewname, args=args, kwargs=kwargs)
        return f"/w/{self.tenant.schema_name}{url}"

    def assertWorkspaceRedirects(self, response, viewname, *, args=None, kwargs=None, **assertion_kwargs):
        """Assert that a response stays on the canonical Workspace route."""
        return self.assertRedirects(
            response,
            self.workspace_reverse(viewname, args=args, kwargs=kwargs),
            **assertion_kwargs,
        )

    def assertRedirects(self, response, expected_url, *args, **kwargs):
        """Keep legacy Loans expectations honest when the response is canonical."""
        if expected_url.startswith("/loans/") and response.headers.get(
            "Location", ""
        ).startswith(f"/w/{self.tenant.schema_name}/loans/"):
            expected_url = f"/w/{self.tenant.schema_name}{expected_url}"
        return super().assertRedirects(response, expected_url, *args, **kwargs)
