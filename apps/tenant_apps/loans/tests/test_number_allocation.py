import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.color import no_style
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from apps.orgs.models import Membership, Role
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
        role, _ = Role.objects.get_or_create(name="Admin")
        Membership.objects.get_or_create(user=self.user, company=self.tenant, defaults={"role": role})
        license = create_license(
            workspace=self.tenant,
            name="Pawn Broker License",
            license_number=f"PBL-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
            actor=self.user,
        )
        self.series = create_series(license=license, name="Main", code="A", actor=self.user)
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

    def test_unprefixed_historical_continuation_survives_validation_and_never_rewinds(self):
        from apps.tenant_apps.loans.services.license_series import reserve_sequence_through
        from apps.tenant_apps.loans.web.license_forms import LoanSeriesSetupForm

        form = LoanSeriesSetupForm(data={"name": "Unnamed", "code": "NUM",
            "is_active": True, "pawn_loan_prefix": "", "release_prefix": "",
            "number_width": 5, "maximum_number": 10000})
        self.assertTrue(form.is_valid(), form.errors)
        sequence = configure_sequence(series=self.series, document_kind=LoanDocumentKind.PAWN_LOAN,
            prefix="", width=5, maximum_number=10000, actor=self.user)
        sequence.full_clean()
        kwargs = dict(series=self.series, document_kind=LoanDocumentKind.PAWN_LOAN,
            last_used_number=6702, evidence_reference="Complete reviewed source register", actor=self.user)
        reserve_sequence_through(**kwargs)
        for _ in range(2):
            self.assertEqual(preview_number(series=self.series, document_kind=LoanDocumentKind.PAWN_LOAN).value, "06703")
        self.assertEqual(allocate_pawn_loan_number(series=self.series, actor=self.user).value, "06703")
        reserve_sequence_through(**kwargs)
        self.assertEqual(preview_number(series=self.series, document_kind=LoanDocumentKind.PAWN_LOAN).value, "06704")
        self.assertEqual(preview_number(series=self.series, document_kind=LoanDocumentKind.PAWN_LOAN_RELEASE).value, "RL-A-0001")

    def test_historical_reservation_continues_without_consuming_or_rewinding(self):
        from apps.orgs.audit import AuditLog
        from apps.tenant_apps.loans.services.license_series import reserve_sequence_through
        kwargs = dict(series=self.series, document_kind=LoanDocumentKind.PAWN_LOAN,
                      last_used_number=2, evidence_reference="Reviewed source register", actor=self.user)
        reserve_sequence_through(**kwargs)
        self.assertEqual(preview_number(series=self.series, document_kind=LoanDocumentKind.PAWN_LOAN).value, "PL-A-0003")
        reserve_sequence_through(**kwargs)
        self.assertEqual(allocate_pawn_loan_number(series=self.series, actor=self.user).value, "PL-A-0003")
        reserve_sequence_through(**kwargs)
        with self.assertRaises(SequenceExhaustedError):
            allocate_pawn_loan_number(series=self.series, actor=self.user)
        self.assertEqual(preview_number(series=self.series, document_kind=LoanDocumentKind.PAWN_LOAN_RELEASE).value, "RL-A-0001")
        self.assertEqual(AuditLog.objects.filter(company=self.tenant,
            data__entity="loan_number_sequence_reservation").count(), 1)

    def test_historical_reservation_can_mark_series_exhausted(self):
        from apps.tenant_apps.loans.services.license_series import reserve_sequence_through
        reserve_sequence_through(series=self.series, document_kind=LoanDocumentKind.PAWN_LOAN,
            last_used_number=3, evidence_reference="Reviewed source register", actor=self.user)
        with self.assertRaises(SequenceExhaustedError):
            allocate_pawn_loan_number(series=self.series, actor=self.user)

    def test_historical_reservation_rejects_invalid_evidence_and_range(self):
        from apps.tenant_apps.loans.services.license_series import reserve_sequence_through, LicenseSeriesError
        for last, reference in ((True, "review"), (-1, "review"), (4, "review"), (2, ""), (2, "bad\nreference")):
            with self.subTest(last=last, reference=reference), self.assertRaises(LicenseSeriesError):
                reserve_sequence_through(series=self.series, document_kind=LoanDocumentKind.PAWN_LOAN,
                    last_used_number=last, evidence_reference=reference, actor=self.user)
        self.assertEqual(preview_number(series=self.series, document_kind=LoanDocumentKind.PAWN_LOAN).counter, 1)

    def test_historical_reservation_requires_actor_and_matching_workspace(self):
        from django.core.exceptions import PermissionDenied
        from apps.tenant_apps.loans.services.license_series import reserve_sequence_through, LicenseSeriesError
        kwargs = dict(series=self.series, document_kind=LoanDocumentKind.PAWN_LOAN,
                      last_used_number=2, evidence_reference="review")
        with self.assertRaises(PermissionDenied):
            reserve_sequence_through(**kwargs, actor=None)
        from copy import copy
        other_series = copy(self.series)
        other_series.workspace_id = self.tenant.pk + 999999
        with self.assertRaises(LicenseSeriesError):
            reserve_sequence_through(**{**kwargs, "series": other_series}, actor=self.user)

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
            role, _ = Role.objects.get_or_create(name="Admin")
            Membership.objects.get_or_create(user=self.user, company=self.tenant, defaults={"role": role})
            license = create_license(
                workspace=self.tenant,
                name="Concurrent License",
                license_number=f"PBL-C-{uuid.uuid4().hex[:8]}",
                issued_on=date(2026, 1, 1),
                expires_on=date(2027, 1, 1),
                actor=self.user,
            )
            self.series = create_series(license=license, name="Concurrent", code="C", actor=self.user)
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

    def test_owner_stop_serializes_with_allocation_from_a_stale_series(self):
        from threading import Event
        from apps.tenant_apps.loans.services.license_series import set_series_active, LicenseSeriesError
        stopped, loaded, commit_stop = Event(), Event(), Event()

        def stop():
            close_old_connections()
            try:
                with workspace_context(self.tenant.pk):
                    set_series_active(self.series, is_active=False, actor=self.user)
                    stopped.set()
                    assert commit_stop.wait(10)
            finally:
                close_old_connections()

        def allocate_stale():
            close_old_connections()
            try:
                with workspace_context(self.tenant.pk):
                    stale = self.series.__class__.objects.get(pk=self.series.pk)
                    self.assertTrue(stale.is_active)
                    loaded.set()
                    try:
                        allocate_pawn_loan_number(series=stale, actor=self.user)
                    except LicenseSeriesError as exc:
                        return str(exc)
                    raise AssertionError("The stopped series issued a number.")
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            stop_future = executor.submit(stop)
            try:
                self.assertTrue(stopped.wait(10))
                issue_future = executor.submit(allocate_stale)
                self.assertTrue(loaded.wait(10))
            finally:
                commit_stop.set()
            stop_future.result(timeout=15)
            self.assertIn("stopped for new loans", issue_future.result(timeout=15))
        with workspace_context(self.tenant.pk):
            self.assertEqual(self.series.number_sequences.get(document_kind="PAWN_LOAN").next_number, 1)

    def test_concurrent_batch_split_confirmations_return_the_same_drafts(self):
        from threading import Barrier
        from decimal import Decimal
        from apps.tenancy.testing import start_workspace_trial
        from apps.tenant_apps.party.models import Party
        from apps.tenant_apps.loans.models import PawnLoan, PawnLoanEconomicPolicy, PawnMetalInterestRatePolicy
        from apps.tenant_apps.loans.services.product_catalog import _seed_default_loan_products
        from apps.tenant_apps.loans.services.pawn_drafts import create_pawn_draft, CreatePawnDraftCommand, CollateralDraftInput
        from apps.tenant_apps.loans.services.pawn_draft_split import preview_pawn_draft_split, split_pawn_draft
        with workspace_context(self.tenant.pk):
            start_workspace_trial(self.tenant)
            borrower = Party.objects.create(display_name="Concurrent split borrower")
            product = _seed_default_loan_products()[0]
            type(product).objects.filter(pk=product.pk).update(status="ACTIVE")
            PawnLoanEconomicPolicy.objects.create(workspace=self.tenant, license=self.series.license,
                valuation_method="LATEST_APPRAISAL", maximum_ltv_ratio=Decimal("0.8"),
                advance_interest_periods=1, effective_from=date(2026, 1, 1))
            PawnMetalInterestRatePolicy.objects.create(workspace=self.tenant, license=self.series.license,
                metal="GOLD", monthly_interest_rate=2, effective_from=date(2026, 1, 1))
            source = create_pawn_draft(CreatePawnDraftCommand(
                workspace_id=self.tenant.pk, borrower_id=borrower.pk, license_id=self.series.license_id,
                series_id=self.series.pk, product_version_id=product.pk,
                principal_amount=Decimal("3000"), monthly_interest_rate=Decimal("2"),
                loan_date=date(2026, 7, 18), tenure_months=3,
                collateral=tuple(CollateralDraftInput(description=f"Ring {index}", metal="GOLD",
                    gross_weight=Decimal("10"), net_weight=Decimal("9"), purity_percentage=Decimal("91.6"),
                    latest_appraised_value=Decimal("50000"), allocated_principal=Decimal("1000"))
                    for index in range(3)),
            ), actor=self.user)
            arguments = dict(collateral_item_ids=tuple(source.collateral_items.order_by("pk").values_list("pk", flat=True))[1:],
                series=self.series, product_version=product, loan_date=source.loan_date,
                tenure_months=3, split_each=True)
            preview = preview_pawn_draft_split(source.pk, **arguments)
        ready = Barrier(2)
        def confirm(_):
            close_old_connections()
            try:
                with workspace_context(self.tenant.pk):
                    ready.wait(timeout=10)
                    return tuple(loan.pk for loan in split_pawn_draft(source.pk, **arguments,
                        expected_fingerprint=preview.fingerprint, actor=self.user))
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(confirm, index) for index in range(2)]
            results = [future.result(timeout=25) for future in futures]
        self.assertEqual(results[0], results[1])
        with workspace_context(self.tenant.pk):
            self.assertEqual(PawnLoan.objects.filter(borrower=borrower).count(), 3)
            self.assertEqual(self.series.number_sequences.get(document_kind="PAWN_LOAN").next_number, 4)
            # This class intentionally skips database flush. Remove only this
            # test's unpaid fixture graph so --keepdb cannot leak draft rows
            # into owner-backed tests whose assertions count all loans.
            from apps.tenant_apps.loans.models import LoanChangeLog, PawnCollateralItem
            fixture_ids = (source.pk, *results[0])
            LoanChangeLog.objects.filter(loan_id__in=fixture_ids).delete()
            PawnCollateralItem.objects.filter(loan_id__in=fixture_ids).delete()
            PawnLoan.objects.filter(pk__in=fixture_ids).delete()
