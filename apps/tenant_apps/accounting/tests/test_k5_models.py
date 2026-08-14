import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, override_settings
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context

from apps.tenant_apps.accounting.models import (
    AccountingBook,
    AccountingOrganization,
    AccountingPeriod,
    AccountingTransaction,
    AccountTransaction,
    ExternalAccount,
    ExternalAccountClassification,
    ExternalAccountPurpose,
    Ledger,
    LedgerTransaction,
    LedgerNodeKind,
    LedgerSide,
    OpenItem,
    OpenItemAllocation,
    PeriodStatus,
    ReportingClass,
    TransactionDiscriminator,
    TransactionBatch,
    Voucher,
    VoucherPurpose,
)
from apps.tenant_apps.accounting.pilot import run_acceptance_pilot
from apps.tenant_apps.accounting.selectors import (
    open_item_outstanding,
    posted_classification_reconciliation,
    posted_external_account_balances,
    posted_financial_statements,
    posted_internal_ledger_balances,
    posted_journal_lines,
    posted_trial_balance,
    posted_unapplied_settlements,
    resolve_external_account_classification,
)
from apps.tenant_apps.accounting.services import (
    append_external_account_classification,
    add_account_transaction,
    add_ledger_transaction,
    allocate_open_item,
    authorize_voucher,
    create_draft_voucher,
    create_open_item,
    correct_posted_batch,
    post_authorized_voucher,
    reverse_posted_batch,
    transition_period,
)


class AccountingRegistrationTests(SimpleTestCase):
    def test_registered_model_surface_through_k5_4(self):
        config = apps.get_app_config("standalone_accounting")

        self.assertEqual(config.name, "apps.tenant_apps.accounting")
        self.assertEqual(
            {model.__name__ for model in config.get_models()},
            {
                "AccountingOrganization",
                "AccountingBook",
                "AccountingPeriod",
                "AccountingPeriodTransition",
                "AccountingSourceDelivery",
                "Ledger",
                "ExternalAccount",
                "ExternalAccountClassification",
                "Voucher",
                "AccountingTransaction",
                "LedgerTransaction",
                "AccountTransaction",
                "TransactionBatch",
                "OpenItem",
                "OpenItemAllocation",
                "VoucherNumberSequence",
            },
        )


class AccountingMasterModelTests(TenantTestCase):
    test_schema_name = f"accounting_pilot_{uuid.uuid4().hex[:8]}"
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
            username="accounting-k5-owner",
            defaults={"email": "accounting-k5-owner@example.com"},
        )
        tenant.name = f"Accounting K5 {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.organization = AccountingOrganization.objects.create(
            organization_key="ORG-1",
            name="Organization One",
            external_tenant_key=self.tenant.schema_name,
        )
        self.book = AccountingBook.objects.create(
            organization=self.organization,
            book_key="PRIMARY",
            name="Primary INR Book",
            base_currency="inr",
            decimal_places=2,
        )

    def create_ledger(self, *, key, code, parent=None, node_kind=LedgerNodeKind.POSTING):
        return Ledger.objects.create(
            book=self.book,
            ledger_key=key,
            code=code,
            name=key.replace("_", " ").title(),
            parent=parent,
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
            node_kind=node_kind,
        )

    def create_voucher(self, *, key="V-1", effective_date=date(2026, 8, 7)):
        return create_draft_voucher(
            book=self.book,
            voucher_key=key,
            idempotency_key=f"source:{key}",
            effective_date=effective_date,
            source_system="TEST",
            source_type="SCENARIO",
            source_id=key,
            source_version="1",
            rule_key="TEST_RULE",
            rule_version="1",
            purpose=VoucherPurpose.ORDINARY,
        )

    def test_book_normalizes_currency_and_is_unique_inside_organization(self):
        self.assertEqual(self.book.base_currency, "INR")
        with self.assertRaises(ValidationError):
            AccountingBook.objects.create(
                organization=self.organization,
                book_key="PRIMARY",
                name="Duplicate",
                base_currency="INR",
            )

    def test_period_ranges_cannot_overlap_inside_one_book(self):
        AccountingPeriod.objects.create(
            book=self.book,
            period_key="AUG-1",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 15),
            status=PeriodStatus.OPEN,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            AccountingPeriod.objects.create(
                book=self.book,
                period_key="AUG-2",
                start_date=date(2026, 8, 15),
                end_date=date(2026, 8, 31),
                status=PeriodStatus.OPEN,
            )

    def test_period_status_requires_close_and_lock_evidence(self):
        with self.assertRaises(ValidationError):
            AccountingPeriod.objects.create(
                book=self.book,
                period_key="CLOSED-WITHOUT-EVIDENCE",
                start_date=date(2026, 7, 1),
                end_date=date(2026, 7, 31),
                status=PeriodStatus.CLOSED,
            )
        with self.assertRaises(ValidationError):
            AccountingPeriod.objects.create(
                book=self.book,
                period_key="LOCKED-WITHOUT-EVIDENCE",
                start_date=date(2026, 6, 1),
                end_date=date(2026, 6, 30),
                status=PeriodStatus.LOCKED,
            )

    def test_only_intermediate_same_book_parent_is_valid(self):
        root = self.create_ledger(
            key="ASSETS",
            code="1000",
            node_kind=LedgerNodeKind.INTERMEDIATE,
        )
        cash = self.create_ledger(key="CASH", code="1100", parent=root)
        self.assertEqual(cash.parent, root)

        other_organization = AccountingOrganization.objects.create(
            organization_key="ORG-2", name="Organization Two"
        )
        other_book = AccountingBook.objects.create(
            organization=other_organization,
            book_key="PRIMARY",
            name="Other Book",
            base_currency="INR",
        )
        with self.assertRaises(ValidationError):
            Ledger.objects.create(
                book=other_book,
                ledger_key="BAD_CHILD",
                code="1200",
                name="Bad Child",
                parent=root,
                reporting_class=ReportingClass.ASSET,
                normal_side=LedgerSide.DEBIT,
                node_kind=LedgerNodeKind.POSTING,
            )

    def test_database_trigger_blocks_cycle_when_model_validation_is_bypassed(self):
        root = self.create_ledger(
            key="ROOT", code="2000", node_kind=LedgerNodeKind.INTERMEDIATE
        )
        child = self.create_ledger(
            key="CHILD",
            code="2100",
            parent=root,
            node_kind=LedgerNodeKind.INTERMEDIATE,
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            Ledger.objects.filter(pk=root.pk).update(parent_id=child.pk)

    def test_database_trigger_blocks_children_under_posting_ledger(self):
        posting_parent = self.create_ledger(key="CASH", code="3000")
        invalid_child = Ledger(
            book=self.book,
            ledger_key="PETTY_CASH",
            code="3100",
            name="Petty Cash",
            parent=posting_parent,
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
            node_kind=LedgerNodeKind.POSTING,
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            Ledger.objects.bulk_create([invalid_child])

    def test_models_exist_only_in_tenant_schema(self):
        tenant_table = AccountingOrganization._meta.db_table
        self.assertIn(tenant_table, connection.introspection.table_names())

        with schema_context("public"):
            self.assertNotIn(tenant_table, connection.introspection.table_names())

    def test_external_accounts_are_book_owned_and_purpose_specific(self):
        receivable = ExternalAccount.objects.create(
            book=self.book,
            account_key="PARTY-1:AR",
            party_key="PARTY-1",
            purpose=ExternalAccountPurpose.CUSTOMER_RECEIVABLE,
            name="Party One Receivable",
        )
        payable = ExternalAccount.objects.create(
            book=self.book,
            account_key="PARTY-1:AP",
            party_key="PARTY-1",
            purpose=ExternalAccountPurpose.SUPPLIER_PAYABLE,
            name="Party One Payable",
        )

        self.assertNotEqual(receivable.purpose, payable.purpose)
        self.assertEqual(receivable.party_key, payable.party_key)
        with self.assertRaises(ValidationError):
            ExternalAccount.objects.create(
                book=self.book,
                account_key=receivable.account_key,
                party_key="PARTY-OTHER",
                purpose=ExternalAccountPurpose.CUSTOMER_RECEIVABLE,
                name="Duplicate Key",
            )

    def test_append_closes_current_version_and_selector_is_date_aware(self):
        account = ExternalAccount.objects.create(
            book=self.book,
            account_key="CUSTOMER-ABC:AR",
            party_key="CUSTOMER-ABC",
            purpose=ExternalAccountPurpose.CUSTOMER_RECEIVABLE,
            name="ABC Receivable",
        )
        ar = self.create_ledger(key="AR", code="4000")
        other_receivable = self.create_ledger(key="OTHER_AR", code="4100")
        first = append_external_account_classification(
            external_account=account,
            version_key="AR-V1",
            effective_from=date(2026, 1, 1),
            reporting_ledger=ar,
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
        )
        second = append_external_account_classification(
            external_account=account,
            version_key="AR-V2",
            effective_from=date(2026, 7, 1),
            reporting_ledger=other_receivable,
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
        )
        first.refresh_from_db()

        self.assertEqual(first.effective_to, date(2026, 6, 30))
        self.assertEqual(
            resolve_external_account_classification(
                external_account=account, effective_date=date(2026, 6, 30)
            ),
            first,
        )
        self.assertEqual(
            resolve_external_account_classification(
                external_account=account, effective_date=date(2026, 7, 1)
            ),
            second,
        )
        with self.assertRaises(ValidationError):
            resolve_external_account_classification(
                external_account=account, effective_date=date(2025, 12, 31)
            )

    def test_classification_ranges_cannot_overlap_when_validation_is_bypassed(self):
        account = ExternalAccount.objects.create(
            book=self.book,
            account_key="CUSTOMER-OVERLAP:AR",
            party_key="CUSTOMER-OVERLAP",
            purpose=ExternalAccountPurpose.CUSTOMER_RECEIVABLE,
            name="Overlap Customer",
        )
        ar = self.create_ledger(key="AR_OVERLAP", code="4200")
        ExternalAccountClassification.objects.create(
            external_account=account,
            version_key="OVERLAP-V1",
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            reporting_ledger=ar,
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
        )
        overlapping = ExternalAccountClassification(
            external_account=account,
            version_key="OVERLAP-V2",
            effective_from=date(2026, 6, 30),
            reporting_ledger=ar,
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ExternalAccountClassification.objects.bulk_create([overlapping])

    def test_database_trigger_enforces_book_and_reporting_ledger_contract(self):
        account = ExternalAccount.objects.create(
            book=self.book,
            account_key="CUSTOMER-GUARD:AR",
            party_key="CUSTOMER-GUARD",
            purpose=ExternalAccountPurpose.CUSTOMER_RECEIVABLE,
            name="Guard Customer",
        )
        other_org = AccountingOrganization.objects.create(
            organization_key="ORG-GUARD", name="Guard Other"
        )
        other_book = AccountingBook.objects.create(
            organization=other_org,
            book_key="OTHER",
            name="Other",
            base_currency="INR",
        )
        other_ledger = Ledger.objects.create(
            book=other_book,
            ledger_key="OTHER_AR",
            code="5000",
            name="Other AR",
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
            node_kind=LedgerNodeKind.POSTING,
        )
        invalid = ExternalAccountClassification(
            external_account=account,
            version_key="INVALID-BOOK",
            effective_from=date(2026, 1, 1),
            reporting_ledger=other_ledger,
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            ExternalAccountClassification.objects.bulk_create([invalid])

    def test_classification_core_is_immutable_and_relations_are_protected(self):
        account = ExternalAccount.objects.create(
            book=self.book,
            account_key="CUSTOMER-LOCKED:AR",
            party_key="CUSTOMER-LOCKED",
            purpose=ExternalAccountPurpose.CUSTOMER_RECEIVABLE,
            name="Locked Customer",
        )
        ar = self.create_ledger(key="AR_LOCKED", code="4300")
        version = append_external_account_classification(
            external_account=account,
            version_key="LOCKED-V1",
            effective_from=date(2026, 1, 1),
            reporting_ledger=ar,
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            ExternalAccountClassification.objects.filter(pk=version.pk).update(
                reporting_class=ReportingClass.LIABILITY
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            ExternalAccountClassification.objects.filter(pk=version.pk).delete()
        with self.assertRaises(ProtectedError):
            account.delete()
        with self.assertRaises(ProtectedError):
            ar.delete()

    def test_draft_voucher_persists_complete_ledger_and_account_atomic_pairs(self):
        cash = self.create_ledger(key="CASH_TX", code="6000")
        revenue = self.create_ledger(
            key="REVENUE_TX", code="6100"
        )
        voucher = self.create_voucher()
        ledger_base = add_ledger_transaction(
            voucher=voucher,
            sequence=1,
            debit_ledger=cash,
            credit_ledger=revenue,
            amount=Decimal("100.00"),
            currency="INR",
            base_amount=Decimal("100.00"),
            base_currency="INR",
            exchange_rate=Decimal("1"),
            rate_source="BOOK_BASE_CURRENCY",
        )

        customer = ExternalAccount.objects.create(
            book=self.book,
            account_key="CUSTOMER-TX:AR",
            party_key="CUSTOMER-TX",
            purpose=ExternalAccountPurpose.CUSTOMER_RECEIVABLE,
            name="Transaction Customer",
        )
        ar = self.create_ledger(key="AR_TX", code="6200")
        append_external_account_classification(
            external_account=customer,
            version_key="AR-TX-V1",
            effective_from=date(2026, 1, 1),
            reporting_ledger=ar,
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
        )
        account_base = add_account_transaction(
            voucher=voucher,
            sequence=2,
            ledger=revenue,
            external_account=customer,
            ledger_side=LedgerSide.CREDIT,
            amount=Decimal("50.00"),
            currency="INR",
            base_amount=Decimal("50.00"),
            base_currency="INR",
            exchange_rate=Decimal("1"),
            rate_source="BOOK_BASE_CURRENCY",
        )

        self.assertEqual(ledger_base.discriminator, TransactionDiscriminator.LEDGER)
        self.assertEqual(ledger_base.ledger_detail.debit_ledger, cash)
        self.assertEqual(account_base.discriminator, TransactionDiscriminator.ACCOUNT)
        self.assertEqual(account_base.account_detail.external_account, customer)
        self.assertEqual(
            account_base.account_detail.classification.version_key, "AR-TX-V1"
        )

    def test_deferred_constraint_rejects_base_without_exactly_one_subtype(self):
        voucher = self.create_voucher(key="V-INCOMPLETE")
        with self.assertRaises(DatabaseError), transaction.atomic():
            AccountingTransaction.objects.create(
                voucher=voucher,
                sequence=1,
                discriminator=TransactionDiscriminator.LEDGER,
                amount=Decimal("10"),
                currency="INR",
                base_amount=Decimal("10"),
                base_currency="INR",
                exchange_rate=Decimal("1"),
                rate_source="BOOK_BASE_CURRENCY",
            )
            # TenantTestCase owns an outer transaction, so force the deferred
            # invariant at this savepoint rather than waiting for test teardown.
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET CONSTRAINTS acct_tx_subtype_base_guard IMMEDIATE"
                )

    def test_database_guards_reject_wrong_discriminator_and_cross_book_ledger(self):
        cash = self.create_ledger(key="CASH_GUARD_TX", code="6300")
        revenue = self.create_ledger(key="REVENUE_GUARD_TX", code="6400")
        voucher = self.create_voucher(key="V-GUARD-TX")
        with self.assertRaises(DatabaseError), transaction.atomic():
            base = AccountingTransaction.objects.create(
                voucher=voucher,
                sequence=1,
                discriminator=TransactionDiscriminator.ACCOUNT,
                amount=Decimal("10"),
                currency="INR",
                base_amount=Decimal("10"),
                base_currency="INR",
                exchange_rate=Decimal("1"),
                rate_source="BOOK_BASE_CURRENCY",
            )
            LedgerTransaction.objects.bulk_create(
                [LedgerTransaction(transaction=base, debit_ledger=cash, credit_ledger=revenue)]
            )

        other_org = AccountingOrganization.objects.create(
            organization_key="ORG-TX-OTHER", name="Transaction Other"
        )
        other_book = AccountingBook.objects.create(
            organization=other_org,
            book_key="OTHER-TX",
            name="Other Transaction Book",
            base_currency="INR",
        )
        other_ledger = Ledger.objects.create(
            book=other_book,
            ledger_key="OTHER_CASH_TX",
            code="6500",
            name="Other Cash",
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
            node_kind=LedgerNodeKind.POSTING,
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            base = AccountingTransaction.objects.create(
                voucher=voucher,
                sequence=2,
                discriminator=TransactionDiscriminator.LEDGER,
                amount=Decimal("10"),
                currency="INR",
                base_amount=Decimal("10"),
                base_currency="INR",
                exchange_rate=Decimal("1"),
                rate_source="BOOK_BASE_CURRENCY",
            )
            LedgerTransaction.objects.bulk_create(
                [
                    LedgerTransaction(
                        transaction=base,
                        debit_ledger=cash,
                        credit_ledger=other_ledger,
                    )
                ]
            )

    def test_database_currency_guard_rejects_incorrect_base_conversion(self):
        voucher = self.create_voucher(key="V-FX-BAD")
        with self.assertRaises(DatabaseError), transaction.atomic():
            AccountingTransaction.objects.bulk_create(
                [
                    AccountingTransaction(
                        voucher=voucher,
                        sequence=1,
                        discriminator=TransactionDiscriminator.LEDGER,
                        amount=Decimal("10"),
                        currency="USD",
                        base_amount=Decimal("829.99"),
                        base_currency="INR",
                        exchange_rate=Decimal("83"),
                        rate_source="RBI:2026-08-07",
                    )
                ]
            )

    def test_authorization_freezes_voucher_and_transaction_mutation(self):
        cash = self.create_ledger(key="CASH_AUTH", code="6600")
        revenue = self.create_ledger(key="REVENUE_AUTH", code="6700")
        voucher = self.create_voucher(key="V-AUTH")
        base = add_ledger_transaction(
            voucher=voucher,
            sequence=1,
            debit_ledger=cash,
            credit_ledger=revenue,
            amount=Decimal("100"),
            currency="INR",
            base_amount=Decimal("100"),
            base_currency="INR",
            exchange_rate=Decimal("1"),
            rate_source="BOOK_BASE_CURRENCY",
        )
        authorized = authorize_voucher(
            voucher=voucher,
            actor_id=101,
            authorized_at=datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(authorized.state, "AUTHORIZED")
        with self.assertRaises(DatabaseError), transaction.atomic():
            AccountingTransaction.objects.filter(pk=base.pk).update(
                amount=Decimal("101"), base_amount=Decimal("101")
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            Voucher.objects.filter(pk=voucher.pk).update(source_version="2")

    def test_classification_cannot_close_before_existing_voucher_date(self):
        account = ExternalAccount.objects.create(
            book=self.book,
            account_key="CUSTOMER-FROZEN:AR",
            party_key="CUSTOMER-FROZEN",
            purpose=ExternalAccountPurpose.CUSTOMER_RECEIVABLE,
            name="Frozen Classification Customer",
        )
        ar = self.create_ledger(key="AR_FROZEN", code="6800")
        revenue = self.create_ledger(key="REVENUE_FROZEN", code="6900")
        append_external_account_classification(
            external_account=account,
            version_key="FROZEN-V1",
            effective_from=date(2026, 1, 1),
            reporting_ledger=ar,
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
        )
        voucher = self.create_voucher(
            key="V-FROZEN-CLASS", effective_date=date(2026, 8, 7)
        )
        add_account_transaction(
            voucher=voucher,
            sequence=1,
            ledger=revenue,
            external_account=account,
            ledger_side=LedgerSide.CREDIT,
            amount=Decimal("100"),
            currency="INR",
            base_amount=Decimal("100"),
            base_currency="INR",
            exchange_rate=Decimal("1"),
            rate_source="BOOK_BASE_CURRENCY",
        )
        with self.assertRaises(DatabaseError):
            append_external_account_classification(
                external_account=account,
                version_key="FROZEN-V2",
                effective_from=date(2026, 7, 1),
                reporting_ledger=ar,
                reporting_class=ReportingClass.ASSET,
                normal_side=LedgerSide.DEBIT,
            )

    def _authorized_ledger_voucher(self, *, key="V-POST"):
        AccountingPeriod.objects.create(
            book=self.book,
            period_key=f"AUG-{key}",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
            status=PeriodStatus.OPEN,
        )
        cash = self.create_ledger(key=f"CASH_{key}", code="7000")
        revenue = self.create_ledger(key=f"REVENUE_{key}", code="7100")
        voucher = self.create_voucher(key=key)
        add_ledger_transaction(
            voucher=voucher,
            sequence=1,
            debit_ledger=cash,
            credit_ledger=revenue,
            amount=Decimal("125.00"),
            currency="INR",
            base_amount=Decimal("125.00"),
            base_currency="INR",
            exchange_rate=Decimal("1"),
            rate_source="BOOK_BASE_CURRENCY",
        )
        return authorize_voucher(
            voucher=voucher,
            actor_id=101,
            authorized_at=datetime(2026, 8, 7, 9, 0, tzinfo=timezone.utc),
        )

    def test_posting_creates_one_batch_and_exact_replay_returns_it(self):
        voucher = self._authorized_ledger_voucher()
        batch = post_authorized_voucher(
            voucher=voucher,
            actor_id=202,
            posted_at=datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc),
        )
        voucher.refresh_from_db()
        replay = post_authorized_voucher(
            voucher=voucher,
            actor_id=999,
            posted_at=datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(voucher.state, "POSTED")
        self.assertEqual(voucher.fingerprint, batch.fingerprint)
        self.assertEqual(replay.pk, batch.pk)
        self.assertEqual(replay.posted_by_id, 202)
        self.assertEqual(TransactionBatch.objects.filter(voucher=voucher).count(), 1)

    def test_posting_rejects_draft_and_nonpermitted_period(self):
        draft = self.create_voucher(key="V-DRAFT-POST")
        with self.assertRaises(ValidationError):
            post_authorized_voucher(
                voucher=draft,
                actor_id=202,
                posted_at=datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc),
            )

        voucher = self._authorized_ledger_voucher(key="V-CLOSED-POST")
        period = AccountingPeriod.objects.get(book=self.book)
        transition_period(
            period=period,
            to_status=PeriodStatus.CLOSED,
            actor_id=101,
            actor_identity="user:101",
            occurred_at=datetime(2026, 8, 7, 9, 30, tzinfo=timezone.utc),
        )
        with self.assertRaises(ValidationError):
            post_authorized_voucher(
                voucher=voucher,
                actor_id=202,
                posted_at=datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc),
            )

    def test_database_requires_posted_state_and_batch_as_one_commit(self):
        voucher = self._authorized_ledger_voucher(key="V-NO-BATCH")
        with self.assertRaises(DatabaseError), transaction.atomic():
            Voucher.objects.filter(pk=voucher.pk).update(
                state="POSTED", fingerprint="a" * 64
            )
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET CONSTRAINTS acct_voucher_batch_voucher_guard IMMEDIATE"
                )

    def test_posted_voucher_and_batch_are_database_immutable(self):
        voucher = self._authorized_ledger_voucher(key="V-IMMUTABLE-POST")
        batch = post_authorized_voucher(
            voucher=voucher,
            actor_id=202,
            posted_at=datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc),
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            TransactionBatch.objects.filter(pk=batch.pk).update(posted_by_id=303)
        with self.assertRaises(DatabaseError), transaction.atomic():
            Voucher.objects.filter(pk=voucher.pk).update(narration="changed")

    def test_reversal_is_new_exact_opposite_evidence_and_replays(self):
        original_voucher = self._authorized_ledger_voucher(key="V-REV-ORIGINAL")
        original = post_authorized_voucher(
            voucher=original_voucher,
            actor_id=202,
            posted_at=datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc),
        )
        reversal = reverse_posted_batch(
            original=original,
            voucher_key="V-REV-ORIGINAL-R1",
            idempotency_key="reverse:V-REV-ORIGINAL:1",
            reversal_date=date(2026, 8, 8),
            actor_id=303,
            occurred_at=datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc),
            reason="Incorrect source amount",
        )
        replay = reverse_posted_batch(
            original=original,
            voucher_key="ignored-on-replay",
            idempotency_key="reverse:V-REV-ORIGINAL:1",
            reversal_date=date(2026, 8, 8),
            actor_id=999,
            occurred_at=datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc),
            reason="Incorrect source amount",
        )

        source_detail = original.voucher.transactions.get().ledger_detail
        reversed_detail = reversal.voucher.transactions.get().ledger_detail
        self.assertEqual(reversal.reversal_of, original)
        self.assertEqual(reversal.reversal_reason, "Incorrect source amount")
        self.assertEqual(reversed_detail.debit_ledger, source_detail.credit_ledger)
        self.assertEqual(reversed_detail.credit_ledger, source_detail.debit_ledger)
        self.assertEqual(replay.pk, reversal.pk)
        original.voucher.refresh_from_db()
        self.assertEqual(original.voucher.state, "POSTED")

    def test_reversal_rejects_second_distinct_attempt_and_reversal_of_reversal(self):
        voucher = self._authorized_ledger_voucher(key="V-REV-ONCE")
        original = post_authorized_voucher(
            voucher=voucher,
            actor_id=202,
            posted_at=datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc),
        )
        reversal = reverse_posted_batch(
            original=original,
            voucher_key="V-REV-ONCE-R1",
            idempotency_key="reverse:once:1",
            reversal_date=date(2026, 8, 8),
            actor_id=303,
            occurred_at=datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc),
            reason="Wrong event",
        )
        with self.assertRaises(ValidationError):
            reverse_posted_batch(
                original=original,
                voucher_key="V-REV-ONCE-R2",
                idempotency_key="reverse:once:2",
                reversal_date=date(2026, 8, 8),
                actor_id=303,
                occurred_at=datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc),
                reason="Second attempt",
            )
        with self.assertRaises(ValidationError):
            reverse_posted_batch(
                original=reversal,
                voucher_key="V-REV-OF-REV",
                idempotency_key="reverse:of-reverse",
                reversal_date=date(2026, 8, 9),
                actor_id=303,
                occurred_at=datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc),
                reason="Not permitted",
            )

    def test_account_reversal_preserves_original_classification_version(self):
        AccountingPeriod.objects.create(
            book=self.book,
            period_key="AUG-ACCOUNT-REV",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
            status=PeriodStatus.OPEN,
        )
        account = ExternalAccount.objects.create(
            book=self.book,
            account_key="CUSTOMER-REV:AR",
            party_key="CUSTOMER-REV",
            purpose=ExternalAccountPurpose.CUSTOMER_RECEIVABLE,
            name="Reversal Customer",
        )
        ar = self.create_ledger(key="AR_REV", code="7200")
        other_ar = self.create_ledger(key="OTHER_AR_REV", code="7300")
        revenue = self.create_ledger(key="REVENUE_ACCOUNT_REV", code="7400")
        original_classification = append_external_account_classification(
            external_account=account,
            version_key="AR-REV-V1",
            effective_from=date(2026, 1, 1),
            reporting_ledger=ar,
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
        )
        voucher = self.create_voucher(key="V-ACCOUNT-REV")
        add_account_transaction(
            voucher=voucher,
            sequence=1,
            ledger=revenue,
            external_account=account,
            ledger_side=LedgerSide.CREDIT,
            amount=Decimal("80"),
            currency="INR",
            base_amount=Decimal("80"),
            base_currency="INR",
            exchange_rate=Decimal("1"),
            rate_source="BOOK_BASE_CURRENCY",
        )
        authorize_voucher(
            voucher=voucher,
            actor_id=101,
            authorized_at=datetime(2026, 8, 7, 9, 0, tzinfo=timezone.utc),
        )
        original = post_authorized_voucher(
            voucher=voucher,
            actor_id=202,
            posted_at=datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc),
        )
        append_external_account_classification(
            external_account=account,
            version_key="AR-REV-V2",
            effective_from=date(2026, 9, 1),
            reporting_ledger=other_ar,
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
        )
        AccountingPeriod.objects.create(
            book=self.book,
            period_key="SEP-ACCOUNT-REV",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
            status=PeriodStatus.OPEN,
        )
        reversal = reverse_posted_batch(
            original=original,
            voucher_key="V-ACCOUNT-REV-R1",
            idempotency_key="reverse:account:1",
            reversal_date=date(2026, 9, 2),
            actor_id=303,
            occurred_at=datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc),
            reason="Reverse after reclassification",
        )
        detail = reversal.voucher.transactions.get().account_detail
        self.assertEqual(detail.classification, original_classification)
        self.assertEqual(detail.ledger_side, LedgerSide.DEBIT)

    def test_correction_posts_reversal_and_authorized_replacement_atomically(self):
        original_voucher = self._authorized_ledger_voucher(key="V-CORRECT-ORIGINAL")
        original = post_authorized_voucher(
            voucher=original_voucher,
            actor_id=202,
            posted_at=datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc),
        )
        cash = self.create_ledger(key="CASH_CORRECTED", code="7500")
        revenue = self.create_ledger(key="REVENUE_CORRECTED", code="7600")
        replacement = create_draft_voucher(
            book=self.book,
            voucher_key="V-CORRECT-REPLACEMENT",
            idempotency_key="correct:replacement:1",
            effective_date=date(2026, 8, 8),
            source_system="TEST",
            source_type="CORRECTION",
            source_id="V-CORRECT-ORIGINAL",
            source_version="2",
            rule_key="TEST_RULE",
            rule_version="2",
            correction_group_key="CORRECTION-GROUP-1",
        )
        add_ledger_transaction(
            voucher=replacement,
            sequence=1,
            debit_ledger=cash,
            credit_ledger=revenue,
            amount=Decimal("120"),
            currency="INR",
            base_amount=Decimal("120"),
            base_currency="INR",
            exchange_rate=Decimal("1"),
            rate_source="BOOK_BASE_CURRENCY",
        )
        authorize_voucher(
            voucher=replacement,
            actor_id=303,
            authorized_at=datetime(2026, 8, 8, 9, 0, tzinfo=timezone.utc),
        )
        reversal, corrected = correct_posted_batch(
            original=original,
            replacement_voucher=replacement,
            reversal_voucher_key="V-CORRECT-REVERSAL",
            reversal_idempotency_key="correct:reversal:1",
            correction_date=date(2026, 8, 8),
            actor_id=303,
            occurred_at=datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc),
            reason="Correct the amount",
            correction_group_key="CORRECTION-GROUP-1",
        )
        self.assertEqual(reversal.reversal_of, original)
        self.assertEqual(reversal.correction_group_key, "CORRECTION-GROUP-1")
        self.assertEqual(corrected.correction_group_key, "CORRECTION-GROUP-1")
        self.assertEqual(corrected.voucher.state, "POSTED")

    def _posted_open_item_pair(self):
        AccountingPeriod.objects.create(
            book=self.book,
            period_key="AUG-SETTLEMENT",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
            status=PeriodStatus.OPEN,
        )
        customer = ExternalAccount.objects.create(
            book=self.book,
            account_key="CUSTOMER-SETTLEMENT:AR",
            party_key="CUSTOMER-SETTLEMENT",
            purpose=ExternalAccountPurpose.CUSTOMER_RECEIVABLE,
            name="Settlement Customer",
        )
        ar = self.create_ledger(key="AR_SETTLEMENT", code="7700")
        revenue = self.create_ledger(key="REVENUE_SETTLEMENT", code="7800")
        cash = self.create_ledger(key="CASH_SETTLEMENT", code="7900")
        append_external_account_classification(
            external_account=customer,
            version_key="AR-SETTLEMENT-V1",
            effective_from=date(2026, 1, 1),
            reporting_ledger=ar,
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
        )
        invoice = self.create_voucher(key="V-INVOICE-SETTLEMENT")
        invoice_base = add_account_transaction(
            voucher=invoice,
            sequence=1,
            ledger=revenue,
            external_account=customer,
            ledger_side=LedgerSide.CREDIT,
            amount=Decimal("1000"),
            currency="INR",
            base_amount=Decimal("1000"),
            base_currency="INR",
            exchange_rate=Decimal("1"),
            rate_source="BOOK_BASE_CURRENCY",
        )
        authorize_voucher(
            voucher=invoice,
            actor_id=101,
            authorized_at=datetime(2026, 8, 7, 9, 0, tzinfo=timezone.utc),
        )
        post_authorized_voucher(
            voucher=invoice,
            actor_id=202,
            posted_at=datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc),
        )
        receipt = self.create_voucher(key="V-RECEIPT-SETTLEMENT")
        receipt_base = add_account_transaction(
            voucher=receipt,
            sequence=1,
            ledger=cash,
            external_account=customer,
            ledger_side=LedgerSide.DEBIT,
            amount=Decimal("600"),
            currency="INR",
            base_amount=Decimal("600"),
            base_currency="INR",
            exchange_rate=Decimal("1"),
            rate_source="BOOK_BASE_CURRENCY",
        )
        authorize_voucher(
            voucher=receipt,
            actor_id=101,
            authorized_at=datetime(2026, 8, 7, 11, 0, tzinfo=timezone.utc),
        )
        post_authorized_voucher(
            voucher=receipt,
            actor_id=202,
            posted_at=datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc),
        )
        return invoice_base.account_detail, receipt_base.account_detail

    def test_partial_allocation_is_nonfinancial_and_reports_outstanding(self):
        origin, settlement = self._posted_open_item_pair()
        financial_count = AccountingTransaction.objects.count()
        item = create_open_item(
            origin_transaction=origin,
            open_item_key="INVOICE-SETTLEMENT-1",
            created_by_id=101,
            due_date=date(2026, 8, 31),
        )
        allocation = allocate_open_item(
            settlement_transaction=settlement,
            open_item=item,
            sequence=1,
            amount=Decimal("400"),
            base_amount=Decimal("400"),
            created_by_id=101,
        )
        outstanding = open_item_outstanding(item)
        unapplied = posted_unapplied_settlements(book=self.book)

        self.assertEqual(allocation.currency, "INR")
        self.assertEqual(outstanding.amount, Decimal("600"))
        self.assertEqual(outstanding.base_amount, Decimal("600"))
        self.assertEqual(len(unapplied), 1)
        self.assertEqual(unapplied[0].voucher_key, "V-RECEIPT-SETTLEMENT")
        self.assertEqual(unapplied[0].amount, Decimal("600"))
        self.assertEqual(unapplied[0].allocated_amount, Decimal("400"))
        self.assertEqual(unapplied[0].unapplied_amount, Decimal("200"))
        self.assertEqual(AccountingTransaction.objects.count(), financial_count)

    def test_allocation_rejects_overallocation_and_is_database_immutable(self):
        origin, settlement = self._posted_open_item_pair()
        item = create_open_item(
            origin_transaction=origin,
            open_item_key="INVOICE-SETTLEMENT-OVER",
            created_by_id=101,
        )
        allocation = allocate_open_item(
            settlement_transaction=settlement,
            open_item=item,
            sequence=1,
            amount=Decimal("600"),
            base_amount=Decimal("600"),
            created_by_id=101,
        )
        with self.assertRaises(ValidationError):
            allocate_open_item(
                settlement_transaction=settlement,
                open_item=item,
                sequence=2,
                amount=Decimal("1"),
                base_amount=Decimal("1"),
                created_by_id=101,
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            OpenItemAllocation.objects.filter(pk=allocation.pk).update(
                amount=Decimal("500"), base_amount=Decimal("500")
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            OpenItem.objects.filter(pk=item.pk).delete()

    def test_database_guard_rejects_cross_account_allocation(self):
        origin, settlement = self._posted_open_item_pair()
        item = create_open_item(
            origin_transaction=origin,
            open_item_key="INVOICE-SETTLEMENT-CROSS",
            created_by_id=101,
        )
        other = ExternalAccount.objects.create(
            book=self.book,
            account_key="OTHER-SETTLEMENT:AR",
            party_key="OTHER-SETTLEMENT",
            purpose=ExternalAccountPurpose.CUSTOMER_RECEIVABLE,
            name="Other Settlement Customer",
        )
        other_ar = self.create_ledger(key="OTHER_AR_SETTLEMENT", code="8000")
        append_external_account_classification(
            external_account=other,
            version_key="OTHER-AR-V1",
            effective_from=date(2026, 1, 1),
            reporting_ledger=other_ar,
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
        )
        other_receipt = self.create_voucher(key="V-OTHER-RECEIPT-SETTLEMENT")
        other_base = add_account_transaction(
            voucher=other_receipt,
            sequence=1,
            ledger=Ledger.objects.get(book=self.book, ledger_key="CASH_SETTLEMENT"),
            external_account=other,
            ledger_side=LedgerSide.DEBIT,
            amount=Decimal("10"),
            currency="INR",
            base_amount=Decimal("10"),
            base_currency="INR",
            exchange_rate=Decimal("1"),
            rate_source="BOOK_BASE_CURRENCY",
        )
        authorize_voucher(
            voucher=other_receipt,
            actor_id=101,
            authorized_at=datetime(2026, 8, 7, 13, 0, tzinfo=timezone.utc),
        )
        post_authorized_voucher(
            voucher=other_receipt,
            actor_id=202,
            posted_at=datetime(2026, 8, 7, 14, 0, tzinfo=timezone.utc),
        )
        # Bulk creation verifies that cross-account protection does not depend
        # on model clean() or the settlement service.
        with self.assertRaises(DatabaseError), transaction.atomic():
            OpenItemAllocation.objects.bulk_create(
                [
                    OpenItemAllocation(
                        settlement_transaction=other_base.account_detail,
                        open_item=item,
                        sequence=1,
                        amount=Decimal("10"),
                        currency="INR",
                        base_amount=Decimal("10"),
                        base_currency="INR",
                        created_by_id=101,
                    )
                ]
            )

    def test_reversing_settlement_restores_outstanding_with_compensation(self):
        origin, settlement = self._posted_open_item_pair()
        item = create_open_item(
            origin_transaction=origin,
            open_item_key="INVOICE-SETTLEMENT-REVERSAL",
            created_by_id=101,
        )
        original_allocation = allocate_open_item(
            settlement_transaction=settlement,
            open_item=item,
            sequence=1,
            amount=Decimal("400"),
            base_amount=Decimal("400"),
            created_by_id=101,
        )
        reversal = reverse_posted_batch(
            original=settlement.transaction.voucher.posting_batch,
            voucher_key="V-RECEIPT-SETTLEMENT-R1",
            idempotency_key="reverse:settlement:receipt:1",
            reversal_date=date(2026, 8, 8),
            actor_id=303,
            occurred_at=datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc),
            reason="Receipt was entered against the wrong bank event",
        )
        compensation = OpenItemAllocation.objects.get(reversal_of=original_allocation)
        outstanding = open_item_outstanding(item)

        self.assertEqual(compensation.settlement_transaction.transaction.voucher, reversal.voucher)
        self.assertEqual(compensation.amount, original_allocation.amount)
        self.assertEqual(outstanding.amount, Decimal("1000"))
        self.assertEqual(outstanding.base_amount, Decimal("1000"))
        self.assertEqual(item.allocations.count(), 2)

    def test_persisted_mvp_reports_derive_from_posted_transaction_truth(self):
        AccountingPeriod.objects.create(
            book=self.book,
            period_key="AUG-REPORTING",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
            status=PeriodStatus.OPEN,
        )

        def report_ledger(key, code, reporting_class, normal_side):
            return Ledger.objects.create(
                book=self.book,
                ledger_key=key,
                code=code,
                name=key,
                reporting_class=reporting_class,
                normal_side=normal_side,
                node_kind=LedgerNodeKind.POSTING,
            )

        cash = report_ledger("REPORT_CASH", "8100", ReportingClass.ASSET, LedgerSide.DEBIT)
        inventory = report_ledger(
            "REPORT_INVENTORY", "8200", ReportingClass.ASSET, LedgerSide.DEBIT
        )
        ar = report_ledger("REPORT_AR", "8300", ReportingClass.ASSET, LedgerSide.DEBIT)
        revenue = report_ledger(
            "REPORT_REVENUE", "8400", ReportingClass.REVENUE, LedgerSide.CREDIT
        )
        cost = report_ledger(
            "REPORT_COST", "8500", ReportingClass.EXPENSE, LedgerSide.DEBIT
        )
        customer = ExternalAccount.objects.create(
            book=self.book,
            account_key="REPORT-CUSTOMER:AR",
            party_key="REPORT-CUSTOMER",
            purpose=ExternalAccountPurpose.CUSTOMER_RECEIVABLE,
            name="Report Customer",
        )
        append_external_account_classification(
            external_account=customer,
            version_key="REPORT-AR-V1",
            effective_from=date(2026, 1, 1),
            reporting_ledger=ar,
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
        )
        sale = self.create_voucher(key="V-REPORT-SALE")
        add_account_transaction(
            voucher=sale,
            sequence=1,
            ledger=revenue,
            external_account=customer,
            ledger_side=LedgerSide.CREDIT,
            amount=Decimal("1000"),
            currency="INR",
            base_amount=Decimal("1000"),
            base_currency="INR",
            exchange_rate=Decimal("1"),
            rate_source="BOOK_BASE_CURRENCY",
        )
        add_ledger_transaction(
            voucher=sale,
            sequence=2,
            debit_ledger=cost,
            credit_ledger=inventory,
            amount=Decimal("700"),
            currency="INR",
            base_amount=Decimal("700"),
            base_currency="INR",
            exchange_rate=Decimal("1"),
            rate_source="BOOK_BASE_CURRENCY",
        )
        authorize_voucher(
            voucher=sale,
            actor_id=101,
            authorized_at=datetime(2026, 8, 7, 9, 0, tzinfo=timezone.utc),
        )
        post_authorized_voucher(
            voucher=sale,
            actor_id=202,
            posted_at=datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc),
        )
        receipt = self.create_voucher(key="V-REPORT-RECEIPT")
        add_account_transaction(
            voucher=receipt,
            sequence=1,
            ledger=cash,
            external_account=customer,
            ledger_side=LedgerSide.DEBIT,
            amount=Decimal("400"),
            currency="INR",
            base_amount=Decimal("400"),
            base_currency="INR",
            exchange_rate=Decimal("1"),
            rate_source="BOOK_BASE_CURRENCY",
        )
        authorize_voucher(
            voucher=receipt,
            actor_id=101,
            authorized_at=datetime(2026, 8, 7, 11, 0, tzinfo=timezone.utc),
        )
        post_authorized_voucher(
            voucher=receipt,
            actor_id=202,
            posted_at=datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc),
        )
        draft = self.create_voucher(key="V-REPORT-DRAFT-EXCLUDED")
        add_ledger_transaction(
            voucher=draft,
            sequence=1,
            debit_ledger=cash,
            credit_ledger=revenue,
            amount=Decimal("999"),
            currency="INR",
            base_amount=Decimal("999"),
            base_currency="INR",
            exchange_rate=Decimal("1"),
            rate_source="BOOK_BASE_CURRENCY",
        )
        financial_rows_before = AccountingTransaction.objects.count()

        lines = posted_journal_lines(book=self.book)
        internal = {row.key: row.signed_base_amount for row in posted_internal_ledger_balances(book=self.book)}
        external = {row.key: row.signed_base_amount for row in posted_external_account_balances(book=self.book)}
        trial = posted_trial_balance(book=self.book)
        trial_rows = {row.key: row.signed_base_amount for row in trial.rows}
        statements = posted_financial_statements(book=self.book)
        reconciliation = posted_classification_reconciliation(book=self.book)

        self.assertEqual(len(lines), 6)
        self.assertEqual(internal["REPORT_REVENUE"], Decimal("-1000"))
        self.assertEqual(internal["REPORT_CASH"], Decimal("400"))
        self.assertEqual(external["REPORT-CUSTOMER:AR"], Decimal("600"))
        self.assertEqual(trial.signed_total, Decimal("0"))
        self.assertEqual(trial_rows["REPORT_AR"], Decimal("600"))
        self.assertEqual(statements.current_period_result, Decimal("300"))
        self.assertEqual(statements.balance_sheet_signed_total, Decimal("0"))
        self.assertEqual(reconciliation[0].difference, Decimal("0"))
        self.assertEqual(AccountingTransaction.objects.count(), financial_rows_before)

    @override_settings(DEBUG=True)
    def test_guarded_acceptance_pilot_is_balanced_and_idempotent(self):
        first = run_acceptance_pilot(actor_id=101)
        replay = run_acceptance_pilot(actor_id=101)

        self.assertEqual(first, replay)
        self.assertEqual(first["voucher_count"], 5)
        self.assertEqual(first["journal_line_count"], 10)
        self.assertEqual(first["trial_balance_total"], "0E-8")
        self.assertEqual(first["balance_sheet_total"], "0E-8")
        self.assertEqual(first["classification_difference"], "0E-8")
        self.assertEqual(first["current_period_result"], "1900.00000000")
        self.assertEqual(first["open_item_outstanding"], "600.00000000")
        self.assertEqual(
            first["unapplied_settlements"],
            [
                {
                    "voucher_number": "PILOT-2026-0003",
                    "external_account": "PILOT_CUSTOMER:AR",
                    "received": "600.00000000",
                    "allocated": "400.00000000",
                    "unapplied": "200.00000000",
                    "currency": "INR",
                }
            ],
        )
