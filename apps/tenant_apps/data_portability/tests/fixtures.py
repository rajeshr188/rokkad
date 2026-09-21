import copy
import uuid
from contextlib import contextmanager
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import TestCase
from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenant_apps.data_portability import services
from apps.tenant_apps.data_portability.tests.test_portability import CSV, MAPPING

class PortabilityFixture(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.role_sql = connection.ops.quote_name("portability_test_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {cls.role_sql} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {cls.role_sql}")
            cursor.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {cls.role_sql}")
            cursor.execute(f"GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {cls.role_sql}")

    @classmethod
    def tearDownClass(cls):
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute(f"DROP OWNED BY {cls.role_sql}")
            cursor.execute(f"DROP ROLE {cls.role_sql}")
        super().tearDownClass()

    def setUp(self):
        suffix = uuid.uuid4().hex
        self.actor = get_user_model().objects.create_user(username="port-owner-" + suffix)
        self.other_actor = get_user_model().objects.create_user(username="port-other-" + suffix)
        self.a = Company.objects.create(name="Port A " + suffix, schema_name="pa" + suffix, owner=self.actor, creator=self.actor)
        self.b = Company.objects.create(name="Port B " + suffix, schema_name="pb" + suffix, owner=self.actor, creator=self.actor)
        role = Role.objects.get_or_create(name="Owner")[0]
        for workspace in (self.a, self.b):
            Membership.objects.get_or_create(company=workspace, user=self.actor, defaults={"role": role})

    @contextmanager
    def scoped(self, workspace=None):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {self.role_sql}")
            try:
                with workspace_context((workspace or self.a).pk):
                    yield
            finally:
                with connection.cursor() as cursor:
                    cursor.execute("RESET ROLE")

    def stage(self, content=CSV, system="paper", filename="parties.csv", workspace=None):
        return services.stage_import(workspace_id=(workspace or self.a).pk, actor=self.actor,
            content=content, filename=filename, source_system=system)

    def ready(self, batch=None, mapping=None, workspace=None):
        batch = batch or self.stage(workspace=workspace)
        return services.validate_import(workspace_id=(workspace or self.a).pk, actor=self.actor,
            batch_id=batch.public_id, mapping=copy.deepcopy(MAPPING) if mapping is None else mapping)

    def commit(self, batch, workspace=None, **kwargs):
        return services.commit_import(workspace_id=(workspace or self.a).pk, actor=self.actor,
            batch_id=batch.public_id, approval_digest=batch.approval_digest, **kwargs)
