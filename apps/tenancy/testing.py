from django.conf import settings
from django.test import Client, TestCase

from apps.orgs.models import Company, Domain

from .context import workspace_context


class WorkspaceClient(Client):
    def __init__(self, workspace, **defaults):
        domain = workspace.domains.filter(is_primary=True).first()
        if domain is not None:
            defaults.setdefault("HTTP_HOST", domain.domain)
        super().__init__(**defaults)


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
