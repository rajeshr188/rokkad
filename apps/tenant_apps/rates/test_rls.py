import uuid

from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.test import TransactionTestCase

from apps.orgs.models import Company
from apps.tenancy.checks import check_restricted_runtime_role, check_workspace_rls
from apps.tenancy.context import workspace_context

from .models import RateSource


class RateRLSIsolationTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.runtime_role = f"rokkad_rls_test_{uuid.uuid4().hex}"
        quoted_role = connection.ops.quote_name(cls.runtime_role)
        rate_source_table = connection.ops.quote_name(RateSource._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOBYPASSRLS"
            )
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted_role}")
            cursor.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON {rate_source_table} "
                f"TO {quoted_role}"
            )
            cursor.execute(
                f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public "
                f"TO {quoted_role}"
            )
        owner = get_user_model().objects.create_user(username="rates-rls-owner")
        cls.first_workspace = Company.objects.create(
            schema_name="rates-rls-one",
            name="Rates RLS One",
            owner=owner,
            creator=owner,
        )
        cls.second_workspace = Company.objects.create(
            schema_name="rates-rls-two",
            name="Rates RLS Two",
            owner=owner,
            creator=owner,
        )
        with workspace_context(cls.first_workspace.pk):
            cls.first_source_id = RateSource.objects.create(
                name="First", location="One"
            ).pk
        with workspace_context(cls.second_workspace.pk):
            cls.second_source_id = RateSource.objects.create(
                name="Second", location="Two"
            ).pk

    @classmethod
    def tearDownClass(cls):
        quoted_role = connection.ops.quote_name(cls.runtime_role)
        with connection.cursor() as cursor:
            cursor.execute(f"DROP OWNED BY {quoted_role}")
            cursor.execute(f"DROP ROLE {quoted_role}")
        super().tearDownClass()

    def _fixture_teardown(self):
        # Class fixtures and the temporary cluster role must survive every case.
        pass

    def _assume_runtime_role(self):
        quoted_role = connection.ops.quote_name(self.runtime_role)
        with connection.cursor() as cursor:
            cursor.execute(f"SET LOCAL ROLE {quoted_role}")

    def test_policy_is_enabled_and_forced(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT relrowsecurity, relforcerowsecurity
                FROM pg_class
                WHERE oid = %s::regclass
                """,
                [RateSource._meta.db_table],
            )
            self.assertEqual(cursor.fetchone(), (True, True))
        self.assertEqual(check_workspace_rls(None, databases=["default"]), [])

    def test_temporary_runtime_role_passes_deployment_safety_check(self):
        with transaction.atomic():
            self._assume_runtime_role()
            self.assertEqual(
                check_restricted_runtime_role(None, databases=["default"]), []
            )

    def test_missing_context_exposes_no_rows(self):
        with transaction.atomic():
            self._assume_runtime_role()
            self.assertEqual(RateSource.objects.count(), 0)

    def test_select_update_and_delete_are_workspace_isolated(self):
        with workspace_context(self.first_workspace.pk):
            self._assume_runtime_role()
            self.assertEqual(
                list(RateSource.objects.values_list("pk", flat=True)),
                [self.first_source_id],
            )
            self.assertEqual(RateSource.objects.update(location="Updated"), 1)
            self.assertEqual(
                RateSource.objects.filter(pk=self.second_source_id).delete()[0], 0
            )

        with workspace_context(self.second_workspace.pk):
            self._assume_runtime_role()
            self.assertEqual(RateSource.objects.get().location, "Two")

    def test_insert_for_another_workspace_fails(self):
        with workspace_context(self.first_workspace.pk):
            self._assume_runtime_role()
            with self.assertRaises(DatabaseError):
                with transaction.atomic():
                    RateSource.objects.bulk_create(
                        [
                            RateSource(
                                workspace=self.second_workspace,
                                name="Forbidden",
                                location="Elsewhere",
                            )
                        ]
                    )

    def test_raw_sql_obeys_workspace_policy(self):
        with workspace_context(self.second_workspace.pk):
            self._assume_runtime_role()
            with connection.cursor() as cursor:
                cursor.execute(
                    f'SELECT id FROM "{RateSource._meta.db_table}" ORDER BY id'
                )
                self.assertEqual(cursor.fetchall(), [(self.second_source_id,)])
