import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.color import no_style
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenancy.context import workspace_context

from apps.orgs.models import Company, Domain
from apps.onboarding.models import OnboardingProgress
from accounts.models import UserProfile
from apps.tenant_apps.loans.domain import LoanDocumentKind
from apps.tenant_apps.loans.services import (
    SequenceExhaustedError,
    allocate_pawn_loan_number,
    allocate_release_number,
    configure_sequence,
    create_license,
    create_series,
    preview_number,
)


class NumberAllocationTests(WorkspaceTestCase):
    test_schema_name = f"loans_number_{uuid.uuid4().hex[:8]}"
    test_domain = f"{test_schema_name}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        User = get_user_model()
        owner, _ = User.objects.get_or_create(
            username="loans-number-owner",
            defaults={"email": "loans-number-owner@example.com"},
        )
        tenant.name = f"Loans Number {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(
            username=f"number-user-{uuid.uuid4().hex[:8]}",
            email=f"number-user-{uuid.uuid4().hex[:8]}@example.com",
        )
        license = create_license(
            workspace=self.tenant,
            name="Pawn Broker License",
            license_number=f"PBL-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
            actor=self.user,
        )
        self.series = create_series(license=license, name="Main", code="A")
        configure_sequence(
            series=self.series,
            document_kind=LoanDocumentKind.PAWN_LOAN,
            prefix="PL-A-",
            width=4,
            maximum_number=3,
            actor=self.user,
        )
        configure_sequence(
            series=self.series,
            document_kind=LoanDocumentKind.PAWN_LOAN_RELEASE,
            prefix="RL-A-",
            width=4,
            maximum_number=3,
            actor=self.user,
        )

    def test_preview_is_non_consuming(self):
        first = preview_number(
            series=self.series, document_kind=LoanDocumentKind.PAWN_LOAN
        )
        second = preview_number(
            series=self.series, document_kind=LoanDocumentKind.PAWN_LOAN
        )

        self.assertEqual(first.value, "PL-A-0001")
        self.assertEqual(second, first)

    def test_allocations_are_unique_and_a_committed_gap_is_not_reused(self):
        abandoned = allocate_pawn_loan_number(series=self.series, actor=self.user)
        used = allocate_pawn_loan_number(series=self.series, actor=self.user)

        self.assertEqual(abandoned.value, "PL-A-0001")
        self.assertEqual(used.value, "PL-A-0002")
        self.assertNotEqual(abandoned.value, used.value)

    def test_loan_and_release_sequences_advance_independently(self):
        loan = allocate_pawn_loan_number(series=self.series, actor=self.user)
        release = allocate_release_number(series=self.series, actor=self.user)

        self.assertEqual(loan.value, "PL-A-0001")
        self.assertEqual(release.value, "RL-A-0001")

    def test_maximum_is_allocated_once_then_fails_closed(self):
        values = [
            allocate_pawn_loan_number(series=self.series, actor=self.user).value
            for _ in range(3)
        ]

        self.assertEqual(values[-1], "PL-A-0003")
        with self.assertRaisesRegex(SequenceExhaustedError, "new series"):
            allocate_pawn_loan_number(series=self.series, actor=self.user)
        with self.assertRaises(SequenceExhaustedError):
            preview_number(
                series=self.series,
                document_kind=LoanDocumentKind.PAWN_LOAN,
            )


class NumberAllocationConcurrencyTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        User = get_user_model()
        with connection.cursor() as cursor:
            for sql in connection.ops.sequence_reset_sql(
                no_style(),
                [User, UserProfile, OnboardingProgress, Company, Domain],
            ):
                cursor.execute(sql)
        owner, _ = User.objects.get_or_create(
            username="loans-concurrency-owner",
            defaults={"email": "loans-concurrency-owner@example.com"},
        )
        cls.owner = owner
        cls.tenant = Company(
            schema_name=f"loans_concurrent_{uuid.uuid4().hex[:8]}",
            name=f"Loans Number Concurrency {uuid.uuid4().hex[:8]}",
            owner=owner,
            creator=owner,
        )
        cls.tenant.save()
        cls.domain = Domain.objects.create(
            tenant=cls.tenant,
            domain=f"{cls.tenant.schema_name}.test.com",
            is_primary=True,
        )

    @classmethod
    def tearDownClass(cls):
        # The shared test database is destroyed after the suite. These
        # concurrency fixtures intentionally skip per-test flush and cannot
        # bypass the production Workspace-retention/protected-FK contract.
        super().tearDownClass()

    def _fixture_teardown(self):
        # The tenant schema is dropped in tearDownClass; flushing the mixed
        # public/tenant test database cannot safely order legacy M2M tables.
        pass

    def setUp(self):
        context = workspace_context(self.tenant.pk)
        context.__enter__()
        try:
            self.user = get_user_model().objects.create_user(
                username=f"concurrency-user-{uuid.uuid4().hex[:8]}",
                email=f"concurrency-user-{uuid.uuid4().hex[:8]}@example.com",
            )
            license = create_license(
                workspace=self.tenant,
                name="Concurrent License",
                license_number=f"PBL-C-{uuid.uuid4().hex[:8]}",
                issued_on=date(2026, 1, 1),
                expires_on=date(2027, 1, 1),
                actor=self.user,
            )
            self.series = create_series(license=license, name="Concurrent", code="C")
            configure_sequence(
                series=self.series,
                document_kind=LoanDocumentKind.PAWN_LOAN,
                prefix="PL-C-",
                width=4,
                maximum_number=10,
                actor=self.user,
            )
        finally:
            context.__exit__(None, None, None)

    def test_concurrent_allocations_serialize_on_the_sequence_row(self):
        series_id = self.series.pk

        def allocate_in_own_connection(_):
            close_old_connections()
            try:
                with workspace_context(self.tenant.pk):
                    series = self.series.__class__.objects.get(pk=series_id)
                    return allocate_pawn_loan_number(series=series).value
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            values = list(executor.map(allocate_in_own_connection, range(2)))

        self.assertEqual(sorted(values), ["PL-C-0001", "PL-C-0002"])
