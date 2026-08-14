import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from apps.orgs.models import Company, Domain, Membership, Role
from apps.tenant_apps.accounting import facade
from apps.tenant_apps.accounting.models import (
    AccountingBook, ExternalAccount, ExternalAccountPurpose, Ledger, LedgerSide,
    OpenItemAllocation, ReportingClass,
)
from apps.tenant_apps.accounting.services import (
    allocate_open_item, append_external_account_classification, create_open_item,
)
from apps.tenant_apps.accounting.source_adapter import SalesReceiptEventV1, deliver_sales_receipt_event


class AccountingConcurrencyTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        connection.set_schema_to_public()
        token = uuid.uuid4().hex[:8]
        User = get_user_model()
        cls.owner = User.objects.create_user(username=f"acct-race-owner-{token}")
        cls.admin = User.objects.create_user(username=f"acct-race-admin-{token}")
        cls.member = User.objects.create_user(username=f"acct-race-member-{token}")
        cls.tenant = Company(schema_name=f"accounting_race_{token}", name=f"Accounting Race {token}", owner=cls.owner, creator=cls.owner)
        cls.tenant.save(verbosity=0)
        cls.domain = Domain.objects.create(tenant=cls.tenant, domain=f"{cls.tenant.schema_name}.test.com", is_primary=True)
        for user, role in ((cls.owner, "Owner"), (cls.admin, "Admin"), (cls.member, "Member")):
            Membership.objects.create(user=user, company=cls.tenant, role=Role.objects.get(name=role))
        connection.set_tenant(cls.tenant)
        _, cls.book, _, ledgers = facade.bootstrap(
            actor=cls.owner, workspace=cls.tenant, period_key="FY2026",
            start_date=date(2026, 4, 1), end_date=date(2027, 3, 31),
        )
        cls.ledger = {row.ledger_key: row for row in ledgers}
        cls.customer = ExternalAccount.objects.create(
            book=cls.book, account_key="RACE-CUSTOMER:AR", party_key="RACE-CUSTOMER",
            purpose=ExternalAccountPurpose.CUSTOMER_RECEIVABLE, name="Race Customer",
        )
        append_external_account_classification(
            external_account=cls.customer, version_key="RACE-AR-V1", effective_from=date(2026, 4, 1),
            reporting_ledger=cls.ledger["ACCOUNTS_RECEIVABLE"], reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
        )

    @classmethod
    def tearDownClass(cls):
        connection.set_schema_to_public()
        cls.domain.delete()
        schema = connection.ops.quote_name(cls.tenant.schema_name)
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM orgs_membership WHERE company_id = %s", [cls.tenant.pk])
            cursor.execute("DELETE FROM orgs_company WHERE id = %s", [cls.tenant.pk])
            cursor.execute(f"DROP SCHEMA {schema} CASCADE")
        connection.set_schema_to_public()
        connection.close()
        super().tearDownClass()

    def _fixture_teardown(self):
        pass

    def _cash_event(self, source_id, amount="100"):
        return SalesReceiptEventV1(
            source_system="RACE", source_type="CASH_SALE", source_id=source_id,
            source_version="1", effective_date=date(2026, 8, 7), amount=Decimal(amount),
            debit_ledger_key="CASH", credit_ledger_key="SALES",
        )

    def _deliver(self, event):
        close_old_connections()
        try:
            connection.set_tenant(self.tenant)
            return str(deliver_sales_receipt_event(
                event=event, workspace=self.tenant, maker=self.member,
                authorizer=self.admin, poster=self.owner,
            ).pk)
        finally:
            close_old_connections()

    def test_identical_delivery_replay_serializes_across_connections(self):
        event = self._cash_event(f"SAME-{uuid.uuid4().hex[:8]}")
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self._deliver, (event, event)))
        self.assertEqual(results[0], results[1])

    def test_changed_payload_reuse_allows_only_one_payload(self):
        source = f"CHANGED-{uuid.uuid4().hex[:8]}"
        events = (self._cash_event(source, "100"), self._cash_event(source, "101"))
        def attempt(event):
            try:
                return self._deliver(event)
            except Exception as exc:
                return type(exc).__name__
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, events))
        self.assertEqual(sum(value == "ValidationError" for value in results), 1)

    def test_reversal_replay_serializes_across_connections(self):
        delivery = deliver_sales_receipt_event(
            event=self._cash_event(f"REV-{uuid.uuid4().hex[:8]}"), workspace=self.tenant,
            maker=self.member, authorizer=self.admin, poster=self.owner,
        )
        original_id = delivery.voucher.posting_batch.pk
        key = f"REVERSAL-{uuid.uuid4().hex[:8]}"
        def reverse(_):
            close_old_connections()
            try:
                connection.set_tenant(self.tenant)
                original = self.book.transaction_batches.get(pk=original_id)
                return str(facade.reverse(
                    actor=self.admin, workspace=self.tenant, original=original,
                    voucher_key=key, idempotency_key=f"reverse:{key}",
                    reversal_date=date(2026, 8, 8), reason="Race replay",
                ).pk)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reverse, range(2)))
        self.assertEqual(results[0], results[1])

    def test_competing_allocations_cannot_overallocate(self):
        token = uuid.uuid4().hex[:8]
        def event(kind, source, amount, ledger):
            return SalesReceiptEventV1(
                source_system="RACE", source_type=kind, source_id=source, source_version="1",
                effective_date=date(2026, 8, 7), amount=Decimal(amount), ledger_key=ledger,
                external_account_key="RACE-CUSTOMER:AR",
            )
        invoice = deliver_sales_receipt_event(event=event("CREDIT_SALE", f"INV-{token}", "100", "SALES"), workspace=self.tenant, maker=self.member, authorizer=self.admin, poster=self.owner)
        receipts = [deliver_sales_receipt_event(event=event("CUSTOMER_RECEIPT", f"RCPT-{token}-{i}", "60", "CASH"), workspace=self.tenant, maker=self.member, authorizer=self.admin, poster=self.owner) for i in range(2)]
        origin = invoice.voucher.transactions.get().account_detail
        item = create_open_item(origin_transaction=origin, open_item_key=f"ITEM-{token}", created_by_id=self.member.pk)
        settlement_ids = [row.voucher.transactions.get().account_detail.pk for row in receipts]
        def allocate(settlement_id):
            close_old_connections()
            try:
                connection.set_tenant(self.tenant)
                try:
                    allocate_open_item(
                        settlement_transaction=type(origin).objects.get(pk=settlement_id),
                        open_item=type(item).objects.get(pk=item.pk), sequence=1,
                        amount=Decimal("60"), base_amount=Decimal("60"), created_by_id=self.member.pk,
                    )
                    return "OK"
                except Exception as exc:
                    return type(exc).__name__
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(allocate, settlement_ids))
        self.assertEqual(results.count("OK"), 1)
        self.assertEqual(OpenItemAllocation.objects.filter(open_item=item).count(), 1)
