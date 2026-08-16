import uuid

from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.test import TransactionTestCase

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context

from apps.tenant_apps.notify_v2.models import NotificationEventType


class NotifyV2RLSIsolationTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.runtime_role = f"rokkad_notify_rls_{uuid.uuid4().hex}"
        quoted_role = connection.ops.quote_name(cls.runtime_role)
        event_type_table = connection.ops.quote_name(
            NotificationEventType._meta.db_table
        )
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOBYPASSRLS"
            )
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted_role}")
            cursor.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON {event_type_table} "
                f"TO {quoted_role}"
            )
            cursor.execute(
                f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted_role}"
            )

        owner = get_user_model().objects.create_user(username="notify-rls-owner")
        cls.first_workspace = Company.objects.create(
            schema_name="notify-rls-one",
            name="Notify RLS One",
            owner=owner,
            creator=owner,
        )
        cls.second_workspace = Company.objects.create(
            schema_name="notify-rls-two",
            name="Notify RLS Two",
            owner=owner,
            creator=owner,
        )
        with workspace_context(cls.first_workspace.pk):
            cls.first_event_type_id = NotificationEventType.objects.create(
                key="FIRST_EVENT",
                name="First Event",
                domain=NotificationEventType.Domain.GENERAL,
            ).pk
        with workspace_context(cls.second_workspace.pk):
            cls.second_event_type_id = NotificationEventType.objects.create(
                key="SECOND_EVENT",
                name="Second Event",
                domain=NotificationEventType.Domain.GENERAL,
            ).pk

    @classmethod
    def tearDownClass(cls):
        quoted_role = connection.ops.quote_name(cls.runtime_role)
        with connection.cursor() as cursor:
            cursor.execute(f"DROP OWNED BY {quoted_role}")
            cursor.execute(f"DROP ROLE {quoted_role}")
        super().tearDownClass()

    def _fixture_teardown(self):
        pass

    def _assume_runtime_role(self):
        quoted_role = connection.ops.quote_name(self.runtime_role)
        with connection.cursor() as cursor:
            cursor.execute(f"SET LOCAL ROLE {quoted_role}")

    def test_no_context_and_cross_workspace_reads_are_hidden(self):
        with transaction.atomic():
            self._assume_runtime_role()
            self.assertEqual(NotificationEventType.objects.count(), 0)

        with workspace_context(self.first_workspace.pk):
            self._assume_runtime_role()
            self.assertEqual(
                list(NotificationEventType.objects.values_list("pk", flat=True)),
                [self.first_event_type_id],
            )

    def test_bulk_insert_cannot_spoof_another_workspace(self):
        with workspace_context(self.first_workspace.pk):
            self._assume_runtime_role()
            with self.assertRaises(DatabaseError):
                with transaction.atomic():
                    NotificationEventType.objects.bulk_create(
                        [
                            NotificationEventType(
                                workspace=self.second_workspace,
                                key="FORBIDDEN_EVENT",
                                name="Forbidden Event",
                                domain=NotificationEventType.Domain.GENERAL,
                            )
                        ]
                    )
