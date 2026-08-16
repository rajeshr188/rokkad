import uuid

from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.test import TransactionTestCase

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context

from ..models import Party


class PartyRLSIsolationTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.runtime_role = f"rokkad_party_rls_{uuid.uuid4().hex}"
        quoted_role = connection.ops.quote_name(cls.runtime_role)
        party_table = connection.ops.quote_name(Party._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOBYPASSRLS"
            )
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted_role}")
            cursor.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON {party_table} TO {quoted_role}"
            )
            cursor.execute(
                f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted_role}"
            )

        owner = get_user_model().objects.create_user(username="party-rls-owner")
        cls.first_workspace = Company.objects.create(
            schema_name="party-rls-one",
            name="Party RLS One",
            owner=owner,
            creator=owner,
        )
        cls.second_workspace = Company.objects.create(
            schema_name="party-rls-two",
            name="Party RLS Two",
            owner=owner,
            creator=owner,
        )
        with workspace_context(cls.first_workspace.pk):
            cls.first_party_id = Party.objects.create(display_name="First Party").pk
        with workspace_context(cls.second_workspace.pk):
            cls.second_party_id = Party.objects.create(display_name="Second Party").pk

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
            self.assertEqual(Party.objects.count(), 0)

        with workspace_context(self.first_workspace.pk):
            self._assume_runtime_role()
            self.assertEqual(
                list(Party.objects.values_list("pk", flat=True)),
                [self.first_party_id],
            )

    def test_bulk_insert_cannot_spoof_another_workspace(self):
        with workspace_context(self.first_workspace.pk):
            self._assume_runtime_role()
            with self.assertRaises(DatabaseError):
                with transaction.atomic():
                    Party.objects.bulk_create(
                        [
                            Party(
                                workspace=self.second_workspace,
                                display_name="Forbidden Party",
                            )
                        ]
                    )
