import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache.backends.locmem import LocMemCache
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import override_settings
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase

from apps.configuration.services import PreferenceService
from apps.tenant_apps.dea.models import AccountingPeriod, PaymentVoucher, Voucher
from apps.tenant_apps.girvi.models import (
    GirviPostingOutboxEvent,
    GirviPostingOutboxStatus,
    GivenLoan,
    License,
    LoanItem,
    LoanRepayment,
    RepledgeHistory,
    Series,
    TakenLoan,
)
from apps.tenant_apps.girvi.models.accrual import AccrualStatus, AccrualTriggerSource
from apps.tenant_apps.girvi.models.custody_tracking import ItemCustodyStatus
from apps.tenant_apps.girvi.models import LoanLifecycleState
from apps.tenant_apps.girvi.service_modules.creation import (
    LoanCreateCommand,
    LoanCreationService,
    LoanItemCreateInput,
)
from apps.tenant_apps.girvi.service_modules.payment import record_loan_disbursal
from apps.tenant_apps.girvi.service_modules.release_lifecycle import (
    ReleaseCreateCommand,
    ReleaseLifecycleService,
)
from apps.tenant_apps.girvi.service_modules.repayment import (
    GivenLoanRepaymentService,
    RepaymentCommand,
    TakenLoanRepaymentService,
)
from apps.tenant_apps.girvi.selectors import build_loan_settlement_balance
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.party.services.customer_bridge import ensure_party_customer


User = get_user_model()


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "girvi-tenant-workflow-tests",
        }
    }
)
class GivenLoanTenantWorkflowIntegrationTests(TenantTestCase):
    test_schema_name = f"girvi_flow_{uuid.uuid4().hex[:8]}"
    test_domain = f"{test_schema_name}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = User.objects.get_or_create(
            username="girvi-flow-owner",
            defaults={"email": "girvi-flow-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"girvi-flow-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        PreferenceService.set_workspace(
            self.tenant,
            "accounting__integration_mode",
            "DEA",
        )
        resolver_cache = patch(
            "apps.tenant_apps.dea.posting.resolver.cache",
            LocMemCache("girvi-tenant-workflow-tests", {}),
        )
        resolver_cache.start()
        self.addCleanup(resolver_cache.stop)
        self.user = User.objects.create_user(
            username=f"girvi-flow-user-{uuid.uuid4().hex[:8]}",
            email=f"girvi-flow-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            is_staff=True,
            is_superuser=True,
        )
        today = timezone.localdate()
        AccountingPeriod.objects.create(
            name="Girvi tenant workflow period",
            start_date=today - timedelta(days=90),
            end_date=today + timedelta(days=1),
        )
        self.party = Party.objects.create(display_name="Tenant Flow Borrower")
        self.customer = ensure_party_customer(
            self.party,
            created_by=self.user,
        )["customer"]
        license_record = License.objects.create(
            name="Tenant Workflow License",
            license_number=f"TWL-{uuid.uuid4().hex[:8]}",
        )
        self.series = Series.objects.create(
            license=license_record,
            name="A",
            prefix="A",
            max_limit=5,
            loan_type="Given",
        )
        self.taken_series = Series.objects.create(
            license=license_record,
            name="T",
            prefix="T",
            max_limit=5,
            loan_type="Taken",
        )

    def _create_given_loan(self):
        loan_date = timezone.now() - timedelta(days=40)
        with patch(
            "apps.tenant_apps.girvi.services.RateCacheService.get_rate_or_none",
            return_value=Decimal("1000.00"),
        ):
            creation = LoanCreationService.execute(
                LoanCreateCommand(
                    borrower=self.customer,
                    borrower_party=self.party,
                    series=self.series,
                    loan_date=loan_date,
                    tenure=12,
                    interest_type="Simple",
                    created_by=self.user,
                    initial_items=[
                        LoanItemCreateInput(
                            itemdesc="Gold ring",
                            itemtype="Gold",
                            quantity=1,
                            weight=Decimal("2.000"),
                            purity=Decimal("75.00"),
                            loanamount=Decimal("1000.00"),
                            interestrate=Decimal("2.00"),
                        )
                    ],
                )
            )
        self.assertTrue(creation.success, creation.errors)
        return GivenLoan.objects.select_related("borrower", "borrower_party").get(
            pk=creation.loan.pk
        )

    def _posted_accounting_voucher_for(self, payment):
        payment_type = ContentType.objects.get_for_model(PaymentVoucher)
        return Voucher.objects.get(
            doc_content_type=payment_type,
            doc_object_id=payment.pk,
            status="POSTED",
        )

    def _create_taken_loan(self):
        given_loan = self._create_given_loan()
        taken_loan = TakenLoan.objects.create(
            loan_id=f"T{uuid.uuid4().hex[:7]}",
            series=self.taken_series,
            lender=self.customer,
            original_loan=given_loan,
            loan_date=timezone.now(),
        )
        RepledgeHistory.objects.create(
            loan_item=given_loan.loanitems.get(),
            taken_loan=taken_loan,
            repledged_amount=Decimal("800.00"),
            item_value_at_repledge=Decimal("1000.00"),
        )
        return taken_loan

    def _taken_repayment_command(self, loan, *, idempotency_key):
        return RepaymentCommand(
            loan=loan,
            cleaned_data={
                "total_amount": Decimal("100.00"),
                "interest_amount": Decimal("0.00"),
                "payment_date": timezone.now(),
                "payment_method": "CASH",
                "reference_number": "",
                "idempotency_key": idempotency_key,
                "description": "Taken loan principal repayment",
                "is_final_payment": False,
            },
            created_by=self.user,
            workspace=self.tenant,
        )

    def test_create_disburse_repay_and_release_in_one_tenant_schema(self):
        loan = self._create_given_loan()
        self.assertEqual(loan.borrower, self.customer)
        self.assertEqual(loan.borrower_party, self.party)
        self.assertEqual(loan.loanitems.count(), 1)
        self.assertTrue(loan.loan_id.startswith("A"))

        loan.status = LoanLifecycleState.APPROVED
        loan.save(update_fields=["status"])
        disbursal, disbursal_created = record_loan_disbursal(loan, self.user)
        loan.status = LoanLifecycleState.ACTIVE_CURRENT
        loan.save(update_fields=["status"])

        self.assertTrue(disbursal_created)
        self.assertTrue(disbursal.posted)
        self.assertTrue(
            self._posted_accounting_voucher_for(disbursal).journal_entries.exists()
        )

        with patch(
            "apps.tenant_apps.girvi.service_modules.repayment.is_loan_catchup_on_receipt_enabled",
            return_value=False,
        ):
            repayment = GivenLoanRepaymentService.execute(
                RepaymentCommand(
                    loan=loan,
                    cleaned_data={
                        "total_amount": Decimal("100.00"),
                        "interest_amount": Decimal("20.00"),
                        "payment_date": timezone.now(),
                        "payment_method": "CASH",
                        "reference_number": "",
                        "idempotency_key": "tenant-flow-repayment",
                        "description": "Part payment before release",
                        "is_final_payment": False,
                    },
                    created_by=self.user,
                )
            )

        self.assertTrue(repayment.accounting_posted, repayment.errors)
        self.assertTrue(repayment.payment_created)
        repayment.payment.refresh_from_db()
        self.assertEqual(repayment.payment.principal_amount.amount, Decimal("80.00"))
        self.assertEqual(repayment.payment.interest_amount.amount, Decimal("20.00"))
        self.assertTrue(
            self._posted_accounting_voucher_for(repayment.payment).journal_entries.exists()
        )

        with patch(
            "apps.tenant_apps.girvi.service_modules.repayment.is_loan_catchup_on_receipt_enabled",
            return_value=False,
        ):
            duplicate_repayment = GivenLoanRepaymentService.execute(
                RepaymentCommand(
                    loan=loan,
                    cleaned_data={
                        "total_amount": Decimal("100.00"),
                        "interest_amount": Decimal("20.00"),
                        "payment_date": repayment.payment.payment_date,
                        "payment_method": "CASH",
                        "reference_number": "",
                        "idempotency_key": "tenant-flow-repayment",
                        "description": "Part payment before release",
                        "is_final_payment": False,
                    },
                    created_by=self.user,
                )
            )
            distinct_repayment = GivenLoanRepaymentService.execute(
                RepaymentCommand(
                    loan=loan,
                    cleaned_data={
                        "total_amount": Decimal("50.00"),
                        "interest_amount": Decimal("0.00"),
                        "payment_date": timezone.now(),
                        "payment_method": "CASH",
                        "reference_number": "",
                        "idempotency_key": "tenant-flow-repayment-2",
                        "description": "Second valid principal payment",
                        "is_final_payment": False,
                    },
                    created_by=self.user,
                )
            )

        self.assertFalse(duplicate_repayment.payment_created)
        self.assertEqual(duplicate_repayment.payment.pk, repayment.payment.pk)
        self.assertTrue(distinct_repayment.payment_created)
        self.assertNotEqual(distinct_repayment.payment.pk, repayment.payment.pk)

        release_result = ReleaseLifecycleService.execute(
            ReleaseCreateCommand(
                loan=loan,
                created_by=self.user,
                release_date=timezone.now(),
                released_by=self.customer,
            )
        )

        self.assertTrue(release_result.success, release_result.errors)
        release_result.release.refresh_from_db()
        loan.refresh_from_db()
        item = LoanItem.objects.get(loan=loan)
        self.assertEqual(loan.status, LoanLifecycleState.CLOSED)
        self.assertEqual(item.custody_status, ItemCustodyStatus.WITH_CUSTOMER)
        self.assertEqual(release_result.release.settlement_basis, "ACCRUAL_ROWS")
        self.assertGreater(release_result.release.settlement_total_amount, Decimal("0.00"))
        self.assertTrue(
            loan.interest_accruals.filter(
                trigger_source=AccrualTriggerSource.RELEASE,
                status=AccrualStatus.POSTED,
            ).exists()
        )
        self.assertIsNotNone(release_result.payment)
        self.assertTrue(release_result.payment.posted)
        self.assertTrue(
            self._posted_accounting_voucher_for(
                release_result.payment
            ).journal_entries.exists()
        )

    def test_deferred_disbursal_records_one_pending_event_without_dea_payment(self):
        PreferenceService.set_workspace(
            self.tenant,
            "accounting__integration_mode",
            "DEFERRED",
        )
        loan = self._create_given_loan()

        first, first_created = record_loan_disbursal(loan, self.user)
        repeated, repeated_created = record_loan_disbursal(loan, self.user)

        self.assertTrue(first_created)
        self.assertFalse(repeated_created)
        self.assertEqual(first.pk, repeated.pk)
        self.assertEqual(first.status, GirviPostingOutboxStatus.PENDING)
        self.assertEqual(first.event_type, "DISBURSAL")
        self.assertEqual(first.source_model, "givenloan")
        self.assertEqual(first.source_pk, str(loan.pk))
        self.assertEqual(first.payload["event_key"], "disbursal")
        self.assertEqual(first.payload["source"]["pk"], str(loan.pk))
        self.assertEqual(
            GirviPostingOutboxEvent.objects.filter(source_pk=str(loan.pk)).count(),
            1,
        )
        self.assertFalse(PaymentVoucher.objects.filter(source_object_id=loan.pk).exists())

    def test_deferred_takenloan_activation_records_one_pending_event_without_dea_payment(self):
        PreferenceService.set_workspace(
            self.tenant,
            "accounting__integration_mode",
            "DEFERRED",
        )
        given_loan = self._create_given_loan()
        item = given_loan.loanitems.get()
        taken_loan = TakenLoan.objects.create(
            loan_id="T00001",
            series=self.taken_series,
            lender=self.customer,
            original_loan=given_loan,
            loan_date=timezone.now(),
        )
        RepledgeHistory.objects.create(
            loan_item=item,
            taken_loan=taken_loan,
            repledged_amount=Decimal("800.00"),
            item_value_at_repledge=Decimal("1000.00"),
        )

        first, first_created = record_loan_disbursal(taken_loan, self.user)
        repeated, repeated_created = record_loan_disbursal(taken_loan, self.user)

        self.assertTrue(first_created)
        self.assertFalse(repeated_created)
        self.assertEqual(first.pk, repeated.pk)
        self.assertEqual(first.status, GirviPostingOutboxStatus.PENDING)
        self.assertEqual(first.event_type, "TAKEN_LOAN_ACTIVATION")
        self.assertEqual(first.source_model, "takenloan")
        self.assertEqual(first.source_pk, str(taken_loan.pk))
        self.assertEqual(first.payload["event_key"], "taken_loan_activation")
        self.assertEqual(
            first.payload["economic_payload"]["principal_amount"],
            "800.00",
        )
        self.assertEqual(
            GirviPostingOutboxEvent.objects.filter(
                source_model="takenloan",
                source_pk=str(taken_loan.pk),
            ).count(),
            1,
        )
        taken_loan_type = ContentType.objects.get_for_model(TakenLoan)
        self.assertFalse(
            PaymentVoucher.objects.filter(
                source_content_type=taken_loan_type,
                source_object_id=taken_loan.pk,
            ).exists()
        )

    def test_dea_takenloan_repayment_records_evidence_and_counts_linked_voucher_once(self):
        taken_loan = self._create_taken_loan()
        command = self._taken_repayment_command(
            taken_loan,
            idempotency_key="tenant-taken-dea-repayment",
        )

        with patch(
            "apps.tenant_apps.girvi.service_modules.repayment.post_payment_voucher"
        ) as mock_post:
            result = TakenLoanRepaymentService.execute(command)
            duplicate = TakenLoanRepaymentService.execute(command)

        self.assertTrue(result.repayment_created, result.errors)
        self.assertTrue(result.accounting_posted, result.errors)
        self.assertIsNotNone(result.payment)
        self.assertEqual(result.repayment.accounting_voucher_pk, result.payment.pk)
        self.assertFalse(duplicate.repayment_created)
        self.assertEqual(duplicate.repayment.pk, result.repayment.pk)
        mock_post.assert_called_once_with(result.payment, self.user)
        self.assertEqual(LoanRepayment.objects.filter(taken_loan=taken_loan).count(), 1)
        settlement = build_loan_settlement_balance(taken_loan, loan_kind="taken")
        self.assertEqual(settlement.principal_paid, Decimal("100.00"))
        self.assertEqual(settlement.total_paid, Decimal("100.00"))

    def test_deferred_takenloan_repayment_records_evidence_and_pending_event_only(self):
        PreferenceService.set_workspace(
            self.tenant,
            "accounting__integration_mode",
            "DEFERRED",
        )
        taken_loan = self._create_taken_loan()
        command = self._taken_repayment_command(
            taken_loan,
            idempotency_key="tenant-taken-deferred-repayment",
        )

        result = TakenLoanRepaymentService.execute(command)
        duplicate = TakenLoanRepaymentService.execute(command)
        conflicting_command = self._taken_repayment_command(
            taken_loan,
            idempotency_key="tenant-taken-deferred-repayment",
        )
        conflicting_command.cleaned_data["payment_date"] = command.cleaned_data[
            "payment_date"
        ]
        conflicting_command.cleaned_data["total_amount"] = Decimal("101.00")
        conflict = TakenLoanRepaymentService.execute(conflicting_command)

        self.assertTrue(result.repayment_created, result.errors)
        self.assertFalse(result.accounting_posted)
        self.assertIsNone(result.payment)
        self.assertFalse(duplicate.repayment_created)
        self.assertEqual(duplicate.repayment.pk, result.repayment.pk)
        self.assertEqual(
            conflict.errors,
            [
                "Repayment reference was already used with different details: "
                "total_amount, principal_amount."
            ],
        )
        event = GirviPostingOutboxEvent.objects.get(
            source_model="loanrepayment",
            source_pk=str(result.repayment.pk),
        )
        self.assertEqual(event.event_type, "TAKEN_LOAN_REPAYMENT")
        self.assertEqual(event.status, GirviPostingOutboxStatus.PENDING)
        self.assertEqual(event.payload["event_key"], "taken_loan_repayment")
        self.assertEqual(event.payload["economic_payload"]["total_amount"], "100.00")
        taken_loan_type = ContentType.objects.get_for_model(TakenLoan)
        self.assertFalse(
            PaymentVoucher.objects.filter(
                source_content_type=taken_loan_type,
                source_object_id=taken_loan.pk,
                direction="PAYMENT",
            ).exists()
        )
        settlement = build_loan_settlement_balance(taken_loan, loan_kind="taken")
        self.assertEqual(settlement.principal_paid, Decimal("100.00"))
        self.assertEqual(settlement.total_paid, Decimal("100.00"))

    def test_takenloan_repayment_evidence_rejects_bulk_mutation_and_invalid_reversal(self):
        PreferenceService.set_workspace(
            self.tenant,
            "accounting__integration_mode",
            "DEFERRED",
        )
        taken_loan = self._create_taken_loan()
        result = TakenLoanRepaymentService.execute(
            self._taken_repayment_command(
                taken_loan,
                idempotency_key="tenant-taken-immutable-repayment",
            )
        )
        repayment = result.repayment

        with self.assertRaises(DatabaseError), transaction.atomic():
            LoanRepayment.objects.filter(pk=repayment.pk).update(
                total_amount=Decimal("99.00")
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            LoanRepayment.objects.filter(pk=repayment.pk).delete()
        with self.assertRaises(ValidationError):
            LoanRepayment.objects.create(
                taken_loan=taken_loan,
                direction=repayment.direction,
                total_amount=Decimal("99.00"),
                principal_amount=Decimal("99.00"),
                interest_amount=Decimal("0.00"),
                payment_date=timezone.now(),
                payment_method="CASH",
                reference_number="invalid-reversal",
                created_by=self.user,
                reversal_of=repayment,
            )
