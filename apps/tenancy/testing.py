from django.conf import settings
from django.test import Client, TestCase
from django.test.client import MULTIPART_CONTENT
from django.urls import reverse

from apps.orgs.models import Company, Domain

from .context import workspace_context


def historical_migration_database(test_case, before, sources):
    """Rehearse populated upgrades in a new test DB, never downgrade the suite DB."""
    from contextlib import contextmanager
    from copy import deepcopy
    from uuid import uuid4
    from django.db import connection, connections, transaction
    from django.db.migrations.executor import MigrationExecutor
    from django.db.models import JSONField
    from psycopg2 import sql
    from psycopg2.extras import Json

    @contextmanager
    def isolated():
        if connection.vendor != "postgresql" or connection.in_atomic_block:
            raise ValueError("Historical migration rehearsal requires an owner test connection outside a transaction.")
        if not connection.settings_dict["NAME"].startswith("test_"):
            raise ValueError("Historical migration rehearsal is confined to Django test databases.")
        alias = "migration_rehearsal_" + uuid4().hex
        database = "test_" + alias
        configuration = deepcopy(connection.settings_dict)
        configuration["NAME"] = database
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(database)))
        connections.databases[alias] = configuration
        target = connections[alias]
        case_class = type(test_case)
        allowed = case_class.databases
        case_class.databases = allowed | {alias}
        try:
            executor = MigrationExecutor(target)
            # Older RunPython migrations predate multi-database support and use
            # the default alias. Confine those reads/writes to this new DB too.
            source_connection = connections["default"]
            connections["default"] = target
            try:
                executor.migrate(before)
            finally:
                connections["default"] = source_connection
            historical_apps = executor.loader.project_state(before).apps
            ordered, mapped = [], {}

            def collect(model, pk):
                key = (model._meta.label_lower, pk)
                if key in mapped:
                    return mapped[key]
                mapped[key] = pk
                fields = list(model._meta.concrete_fields)
                with connection.cursor() as cursor:
                    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", [model._meta.db_table])
                    available = {row[0] for row in cursor.fetchall()}
                present = [field for field in fields if field.column in available]
                columns = [field.column for field in present]
                query = sql.SQL("SELECT {} FROM {} WHERE {}=%s").format(
                    sql.SQL(",").join(map(sql.Identifier, columns)),
                    sql.Identifier(model._meta.db_table), sql.Identifier(model._meta.pk.column),
                )
                with connection.cursor() as cursor:
                    cursor.execute(query, [pk])
                    values = cursor.fetchone()
                if values is None:
                    raise ValueError("Historical fixture prerequisite is missing.")
                retained = dict(zip(columns, values, strict=True))
                values = [retained[field.column] if field.column in retained else field.get_default() for field in fields]
                if model._meta.label_lower == "orgs.role":
                    # Ownership migrations seed global roles in the empty DB.
                    existing = model.objects.using(alias).filter(name=retained["name"]).first()
                    if existing is not None:
                        mapped[key] = existing.pk
                        return existing.pk
                for index, (field, value) in enumerate(zip(fields, values, strict=True)):
                    if field.is_relation and value is not None:
                        values[index] = collect(field.related_model, value)
                ordered.append((model, fields, values))
                return pk

            for source in sources:
                collect(historical_apps.get_model(source._meta.app_label, source._meta.model_name), source.pk)
            with transaction.atomic(using=alias), target.cursor() as cursor:
                for model, fields, values in ordered:
                    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                        sql.Identifier(model._meta.db_table),
                        sql.SQL(",").join(sql.Identifier(field.column) for field in fields),
                        sql.SQL(",").join(sql.Placeholder() for field in fields),
                    )
                    cursor.execute(query, [Json(value) if isinstance(field, JSONField) and value is not None else value
                        for field, value in zip(fields, values, strict=True)])
            yield target, historical_apps
        finally:
            target.close()
            del connections[alias]
            del connections.databases[alias]
            case_class.databases = allowed
            # Only the uniquely named database created above is ever removed.
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))

    return isolated()


def start_workspace_trial(workspace):
    """Create real commercial access for HTTP and rendered-action tests."""
    from apps.subscriptions.models import Plan, Subscription

    plan = Plan.objects.create(
        name=f"Test trial for {workspace.slug}",
        tier=Plan.PlanTierChoices.STARTER, price=0,
        description="Workspace test harness trial", trial_days=14,
    )
    return Subscription.objects.create(company=workspace, plan=plan)


def expire_workspace_trial(workspace, *, days_ago=8):
    """Arrange commercial expiry in boundary tests without app-owned billing imports."""
    from datetime import timedelta
    from django.utils import timezone
    from apps.subscriptions.models import Subscription

    Subscription.objects.filter(company=workspace).update(
        trial_end_date=timezone.now() - timedelta(days=days_ago)
    )


def set_workspace_trial_end(workspace, *, ends_at):
    """Arrange a test clock without business apps importing billing internals."""
    from apps.subscriptions.models import Subscription

    Subscription.objects.filter(company=workspace).update(trial_end_date=ends_at)


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
        return f"/w/{self.workspace.slug}{url}"

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
        return start_workspace_trial(self.tenant)

    def workspace_reverse(self, viewname, *, args=None, kwargs=None):
        """Reverse a business route beneath the explicit Workspace path."""
        url = reverse(viewname, args=args, kwargs=kwargs)
        return f"/w/{self.tenant.slug}{url}"

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
        ).startswith(f"/w/{self.tenant.slug}/loans/"):
            expected_url = f"/w/{self.tenant.slug}{expected_url}"
        return super().assertRedirects(response, expected_url, *args, **kwargs)


class WorkspaceRoleTestGrants:
    """Explicit fixture writes to local grants, never global template mutation."""
    def __init__(self, role, workspace):
        from apps.orgs.services.workspace_roles import ensure_workspace_role
        self.workspace = workspace
        self.profile = ensure_workspace_role(workspace.pk, role.pk)

    def add(self, *permissions):
        from apps.orgs.models import WorkspaceRoleGrant
        with workspace_context(self.workspace.pk):
            for permission in permissions:
                WorkspaceRoleGrant.objects.get_or_create(workspace=self.workspace,
                    workspace_role=self.profile, permission=permission)

    def remove(self, *permissions):
        with workspace_context(self.workspace.pk):
            self.profile.grants.filter(permission_id__in=[p.pk for p in permissions]).delete()

    def clear(self):
        with workspace_context(self.workspace.pk):
            self.profile.grants.all().delete()

    def set(self, permissions):
        self.clear()
        self.add(*permissions)


def workspace_role_permissions(role, workspace):
    return WorkspaceRoleTestGrants(role, workspace)
