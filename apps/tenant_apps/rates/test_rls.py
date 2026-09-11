import uuid

from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.test import TransactionTestCase

from apps.orgs.models import Company
from apps.tenancy.checks import check_restricted_runtime_role, check_workspace_rls
from apps.tenancy.context import workspace_context

from apps.tenant_apps.rates.models import Rate, RateSource


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
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON rates_rate TO {quoted_role}")
            cursor.execute(
                f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public "
                f"TO {quoted_role}"
            )
        suffix = uuid.uuid4().hex[:10]
        owner = get_user_model().objects.create_user(username=f"rates-rls-owner-{suffix}")
        cls.owner_id = owner.pk
        cls.first_workspace = Company.objects.create(
            schema_name=f"rates-rls-one-{suffix}",
            name="Rates RLS One",
            owner=owner,
            creator=owner,
        )
        cls.second_workspace = Company.objects.create(
            schema_name=f"rates-rls-two-{suffix}",
            name="Rates RLS Two",
            owner=owner,
            creator=owner,
        )
        with workspace_context(cls.first_workspace.pk):
            cls.first_source_id = RateSource.objects.create(
                name="First", location="One"
            ).pk
            cls.first_quote_id = Rate.objects.create(rate_source_id=cls.first_source_id, buying_rate=1, selling_rate=2).pk
        with workspace_context(cls.second_workspace.pk):
            cls.second_source_id = RateSource.objects.create(
                name="Second", location="Two"
            ).pk
            cls.second_quote_id = Rate.objects.create(rate_source_id=cls.second_source_id, buying_rate=3, selling_rate=4).pk

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

    def test_quote_history_is_scoped_and_immutable_under_runtime_role(self):
        with transaction.atomic():
            self._assume_runtime_role()
            self.assertEqual(Rate.objects.count(), 0)
        with workspace_context(self.first_workspace.pk):
            self._assume_runtime_role()
            self.assertEqual(list(Rate.objects.values_list("pk", flat=True)), [self.first_quote_id])
            self.assertEqual(Rate.objects.filter(pk=self.second_quote_id).update(buying_rate=10), 0)
            with self.assertRaises(DatabaseError), transaction.atomic():
                Rate.objects.filter(pk=self.first_quote_id).update(buying_rate=10)
            with self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM rates_rate WHERE id = %s", [self.first_quote_id])

    def test_quote_insert_cannot_use_cross_workspace_source_or_invalid_price(self):
        with workspace_context(self.first_workspace.pk):
            self._assume_runtime_role()
            for source_id, amount in ((self.second_source_id, 1), (self.first_source_id, 0)):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    Rate.objects.bulk_create([Rate(workspace=self.first_workspace, rate_source_id=source_id,
                                                   buying_rate=amount, selling_rate=2)])

    def test_quote_revision_cannot_reference_another_workspace(self):
        with workspace_context(self.first_workspace.pk):
            self._assume_runtime_role()
            with self.assertRaises(DatabaseError), transaction.atomic():
                Rate.objects.bulk_create([Rate(workspace=self.first_workspace, rate_source_id=self.first_source_id,
                    buying_rate=1, selling_rate=2, supersedes_id=self.second_quote_id,
                    recorded_by_id=self.owner_id, reason="Cross-workspace attempt")])
