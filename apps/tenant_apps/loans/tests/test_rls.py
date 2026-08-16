import uuid
from datetime import date

from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.test import TransactionTestCase

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context

from ..models import LoanLicense, LoanSeries


class LoansRLSIsolationTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.runtime_role = f"rokkad_loans_rls_{uuid.uuid4().hex}"
        quoted_role = connection.ops.quote_name(cls.runtime_role)
        tables = ", ".join(
            connection.ops.quote_name(model._meta.db_table)
            for model in (LoanLicense, LoanSeries)
        )
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOBYPASSRLS"
            )
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted_role}")
            cursor.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tables} TO {quoted_role}"
            )
            cursor.execute(
                f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted_role}"
            )

        owner = get_user_model().objects.create_user(username="loans-rls-owner")
        cls.first_workspace = Company.objects.create(
            schema_name="loans-rls-one",
            name="Loans RLS One",
            owner=owner,
            creator=owner,
        )
        cls.second_workspace = Company.objects.create(
            schema_name="loans-rls-two",
            name="Loans RLS Two",
            owner=owner,
            creator=owner,
        )
        with workspace_context(cls.first_workspace.pk):
            cls.first_license = LoanLicense.objects.create(
                workspace=cls.first_workspace,
                name="First License",
                license_number="RLS-FIRST",
                issued_on=date(2026, 1, 1),
                expires_on=date(2027, 1, 1),
            )
            cls.first_series_id = LoanSeries.objects.create(
                license=cls.first_license,
                name="First Series",
                code="FIRST",
            ).pk
        with workspace_context(cls.second_workspace.pk):
            cls.second_license = LoanLicense.objects.create(
                workspace=cls.second_workspace,
                name="Second License",
                license_number="RLS-SECOND",
                issued_on=date(2026, 1, 1),
                expires_on=date(2027, 1, 1),
            )

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

    def test_root_and_child_rows_are_hidden_without_context(self):
        with transaction.atomic():
            self._assume_runtime_role()
            self.assertEqual(LoanLicense.objects.count(), 0)
            self.assertEqual(LoanSeries.objects.count(), 0)

        with workspace_context(self.first_workspace.pk):
            self._assume_runtime_role()
            self.assertEqual(
                list(LoanLicense.objects.values_list("pk", flat=True)),
                [self.first_license.pk],
            )
            self.assertEqual(
                list(LoanSeries.objects.values_list("pk", flat=True)),
                [self.first_series_id],
            )

    def test_bulk_child_insert_cannot_spoof_another_workspace(self):
        with workspace_context(self.first_workspace.pk):
            self._assume_runtime_role()
            with self.assertRaises(DatabaseError):
                with transaction.atomic():
                    LoanSeries.objects.bulk_create(
                        [
                            LoanSeries(
                                workspace=self.second_workspace,
                                license=self.second_license,
                                name="Forbidden Series",
                                code="FORBIDDEN",
                            )
                        ]
                    )
