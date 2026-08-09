import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import override_settings
from django.urls import reverse
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from apps.orgs.models import Membership, Role
from apps.tenant_apps.accounting import facade
from apps.tenant_apps.accounting.models import (
    AccountingSourceDelivery,
    ExternalAccount,
    ExternalAccountPurpose,
    OpenItem,
    Ledger,
    LedgerSide,
    PeriodStatus,
    ReportingClass,
    Voucher,
    VoucherPurpose,
    SourceDeliveryStatus,
)
from apps.tenant_apps.accounting.services import append_external_account_classification
from apps.tenant_apps.accounting.source_adapter import SalesReceiptEventV1, deliver_sales_receipt_event
from apps.tenant_apps.accounting.selectors import (
    open_item_outstanding,
    posted_external_account_balances,
    posted_trial_balance,
    posted_unapplied_settlements,
)
from apps.tenant_apps.accounting.diagnostics import accounting_integrity_findings
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.accounting.feature_flags import (
    get_accounting_activation_state,
    set_accounting_successor_enabled,
)


@override_settings(
    ROOT_URLCONF="django_project.tenant_urls",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
)
class AccountingFacadeTests(TenantTestCase):
    test_schema_name = f"accounting_pilot_{uuid.uuid4().hex[:8]}"
    test_domain = f"accounting-pilot-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = get_user_model().objects.get_or_create(
            username="accounting-k7-owner",
            defaults={"email": "accounting-k7-owner@example.com"},
        )
        tenant.name = f"Accounting K7 {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        static_url = patch(
            "django.templatetags.static.StaticNode.handle_simple",
            side_effect=lambda path: f"/static/{path}",
        )
        static_url.start()
        self.addCleanup(static_url.stop)
        users = get_user_model().objects
        self.owner = self.tenant.owner
        self.admin = users.create_user(username=f"k7-admin-{uuid.uuid4().hex[:6]}")
        self.member = users.create_user(username=f"k7-member-{uuid.uuid4().hex[:6]}")
        self.outsider = users.create_user(username=f"k7-outside-{uuid.uuid4().hex[:6]}")
        for user, role_name in (
            (self.owner, "Owner"),
            (self.admin, "Admin"),
            (self.member, "Member"),
        ):
            Membership.objects.get_or_create(
                user=user,
                company=self.tenant,
                defaults={"role": Role.objects.get(name=role_name)},
            )
        _organization, self.book, _period, ledgers = facade.bootstrap(
            actor=self.owner,
            workspace=self.tenant,
            period_key="AUG-2026",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
        )
        ledger_by_key = {ledger.ledger_key: ledger for ledger in ledgers}
        self.cash = ledger_by_key["CASH"]
        self.sales = ledger_by_key["SALES"]
        self.receivable = ledger_by_key["ACCOUNTS_RECEIVABLE"]
        self.customer = ExternalAccount.objects.create(
            book=self.book, account_key="CUSTOMER-1:AR", party_key="CUSTOMER-1",
            purpose=ExternalAccountPurpose.CUSTOMER_RECEIVABLE, name="Customer One",
        )
        append_external_account_classification(
            external_account=self.customer, version_key="AR-V1",
            effective_from=date(2026, 1, 1), reporting_ledger=self.receivable,
            reporting_class=ReportingClass.ASSET, normal_side=LedgerSide.DEBIT,
        )

    def _draft(self, *, actor=None, key="K7-V-1"):
        actor = actor or self.member
        voucher = facade.create_draft(
            actor=actor,
            workspace=self.tenant,
            book=self.book,
            voucher_key=key,
            voucher_number=f"2026-{key}",
            idempotency_key=f"source:{key}",
            effective_date=date(2026, 8, 7),
            source_system="K7_TEST",
            source_type="CASH_SALE",
            source_id=key,
            source_version="1",
            rule_key="CASH_SALE_V1",
            rule_version="1",
            purpose=VoucherPurpose.ORDINARY,
        )
        facade.add_ledger_line(
            actor=actor,
            workspace=self.tenant,
            voucher=voucher,
            sequence=1,
            debit_ledger=self.cash,
            credit_ledger=self.sales,
            amount=Decimal("100"),
            currency="INR",
            base_amount=Decimal("100"),
            base_currency="INR",
            exchange_rate=Decimal("1"),
            rate_source="BOOK_BASE_CURRENCY",
        )
        return voucher

    def test_member_prepares_draft_but_cannot_authorize(self):
        voucher = self._draft()

        self.assertEqual(voucher.voucher_number, "PRIMARY-2026-000001")
        self.assertEqual(voucher.created_by_id, self.member.pk)
        self.assertIn(f"user:{self.member.pk}", voucher.created_by_identity)

        with self.assertRaises(PermissionDenied):
            facade.authorize(actor=self.member, workspace=self.tenant, voucher=voucher)

    def test_authorize_and_post_use_server_time_and_distinct_actors(self):
        voucher = self._draft()
        stale_voucher = Voucher.objects.get(pk=voucher.pk)
        authorized_at = datetime(2026, 8, 7, 9, 30, tzinfo=timezone.utc)
        posted_at = datetime(2026, 8, 7, 9, 31, tzinfo=timezone.utc)

        with patch.object(facade.timezone, "now", return_value=authorized_at):
            authorized = facade.authorize(
                actor=self.admin, workspace=self.tenant, voucher=voucher
            )
        with self.assertRaises(PermissionDenied):
            facade.post(actor=self.admin, workspace=self.tenant, voucher=authorized)
        with self.assertRaises(PermissionDenied):
            facade.post(actor=self.admin, workspace=self.tenant, voucher=stale_voucher)
        with patch.object(facade.timezone, "now", return_value=posted_at):
            batch = facade.post(
                actor=self.owner, workspace=self.tenant, voucher=authorized
            )

        self.assertEqual(authorized.authorized_by_id, self.admin.pk)
        self.assertIn(f"user:{self.admin.pk}", authorized.authorized_by_identity)
        self.assertEqual(authorized.authorized_at, authorized_at)
        self.assertEqual(batch.posted_by_id, self.owner.pk)
        self.assertIn(f"user:{self.owner.pk}", batch.posted_by_identity)
        self.assertEqual(batch.posted_at, posted_at)

    def test_numbering_is_automatic_sequential_and_creator_evidence_is_immutable(self):
        first = self._draft(key="NUMBER-1")
        second = self._draft(key="NUMBER-2")

        self.assertEqual(first.voucher_number, "PRIMARY-2026-000001")
        self.assertEqual(second.voucher_number, "PRIMARY-2026-000002")
        with self.assertRaises(DatabaseError), transaction.atomic():
            Voucher.objects.filter(pk=first.pk).update(created_by_identity="tampered")

    def test_nonmember_and_wrong_tenant_are_denied(self):
        with self.assertRaises(PermissionDenied):
            facade.create_draft(
                actor=self.outsider,
                workspace=self.tenant,
                book=self.book,
                voucher_key="DENIED",
            )
        wrong_workspace = SimpleNamespace(schema_name="another_tenant")
        with self.assertRaises(PermissionDenied):
            facade.create_draft(
                actor=self.owner,
                workspace=wrong_workspace,
                book=self.book,
                voucher_key="WRONG-TENANT",
            )

    def test_reversal_requires_actor_other_than_original_poster(self):
        voucher = self._draft(key="K7-REV-1")
        authorized = facade.authorize(
            actor=self.admin, workspace=self.tenant, voucher=voucher
        )
        original = facade.post(
            actor=self.owner, workspace=self.tenant, voucher=authorized
        )
        reversal_args = {
            "workspace": self.tenant,
            "original": original,
            "voucher_key": "K7-REV-1-R1",
            "voucher_number": "2026-K7-REV-1-R1",
            "idempotency_key": "reverse:K7-REV-1",
            "reversal_date": date(2026, 8, 7),
            "reason": "Correct synthetic entry",
        }

        with self.assertRaises(PermissionDenied):
            facade.reverse(actor=self.owner, **reversal_args)
        reversal = facade.reverse(actor=self.admin, **reversal_args)

        self.assertEqual(reversal.reversal_of, original)
        self.assertEqual(reversal.posted_by_id, self.admin.pk)

    def test_period_lifecycle_is_authorized_audited_and_ordered(self):
        period = self.book.periods.get(period_key="AUG-2026")
        with self.assertRaises(PermissionDenied):
            facade.change_period(
                actor=self.member, workspace=self.tenant, period=period,
                to_status=PeriodStatus.CLOSED,
            )
        closed, evidence = facade.change_period(
            actor=self.admin, workspace=self.tenant, period=period,
            to_status=PeriodStatus.CLOSED,
        )
        self.assertEqual(evidence.actor_id, self.admin.pk)
        reopened, _ = facade.change_period(
            actor=self.owner, workspace=self.tenant, period=closed,
            to_status=PeriodStatus.ADJUSTMENT_ONLY, reason="Year-end adjustment",
        )
        facade.change_period(
            actor=self.admin, workspace=self.tenant, period=reopened,
            to_status=PeriodStatus.CLOSED,
        )
        locked, _ = facade.change_period(
            actor=self.owner, workspace=self.tenant, period=reopened,
            to_status=PeriodStatus.LOCKED,
        )
        self.assertEqual(locked.status, PeriodStatus.LOCKED)
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.book.periods.filter(pk=locked.pk).update(status=PeriodStatus.CLOSED)

    def test_mvp_bootstrap_is_idempotent_and_minimal(self):
        args = dict(
            actor=self.owner, workspace=self.tenant, period_key="FY2027",
            start_date=date(2027, 4, 1), end_date=date(2028, 3, 31),
        )
        first = facade.bootstrap(**args)
        second = facade.bootstrap(**args)

        self.assertEqual(first[1].pk, second[1].pk)
        self.assertEqual(
            {ledger.ledger_key for ledger in first[3]},
            {"CASH", "ACCOUNTS_RECEIVABLE", "SALES"},
        )

    def test_source_adapter_posts_exact_replay_and_rejects_changed_payload(self):
        event = SalesReceiptEventV1(
            source_system="SALES_MVP", source_type="CASH_SALE", source_id="SALE-1",
            source_version="1", effective_date=date(2026, 8, 7), amount=Decimal("250"),
            debit_ledger_key="CASH", credit_ledger_key="SALES",
        )
        args = dict(event=event, workspace=self.tenant, maker=self.member,
                    authorizer=self.admin, poster=self.owner)
        first = deliver_sales_receipt_event(**args)
        replay = deliver_sales_receipt_event(**args)

        self.assertEqual(first.pk, replay.pk)
        self.assertEqual(first.status, SourceDeliveryStatus.POSTED)
        self.assertEqual(self.book.vouchers.count(), 1)
        with self.assertRaises(ValidationError):
            deliver_sales_receipt_event(**{**args, "event": replace(event, amount=Decimal("251"))})

    def test_source_adapter_persists_failure_without_partial_voucher(self):
        event = SalesReceiptEventV1(
            source_system="SALES_MVP", source_type="CASH_SALE", source_id="SALE-FAIL",
            source_version="1", effective_date=date(2026, 8, 7), amount=Decimal("10"),
            debit_ledger_key="MISSING", credit_ledger_key="SALES",
        )
        with self.assertRaises(Ledger.DoesNotExist):
            deliver_sales_receipt_event(
                event=event, workspace=self.tenant, maker=self.member,
                authorizer=self.admin, poster=self.owner,
            )
        delivery = AccountingSourceDelivery.objects.get(source_id="SALE-FAIL")
        self.assertEqual(delivery.status, SourceDeliveryStatus.FAILED)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertEqual(self.book.vouchers.count(), 0)
        self.assertEqual(
            [finding.code for finding in accounting_integrity_findings()],
            ["FAILED_DELIVERY"],
        )

    def test_source_adapter_posts_credit_sale_and_customer_receipt(self):
        common = dict(
            source_system="SALES_MVP", source_version="1",
            effective_date=date(2026, 8, 7), currency="INR",
            external_account_key="CUSTOMER-1:AR",
        )
        credit = SalesReceiptEventV1(
            **common, source_type="CREDIT_SALE", source_id="INV-1",
            amount=Decimal("100"), ledger_key="SALES", open_item_key="INV-1",
            due_date=date(2026, 9, 7),
        )
        receipt = SalesReceiptEventV1(
            **common, source_type="CUSTOMER_RECEIPT", source_id="RCPT-1",
            amount=Decimal("40"), ledger_key="CASH", open_item_key="INV-1",
            allocation_amount=Decimal("40"),
        )
        for event in (credit, receipt):
            deliver_sales_receipt_event(
                event=event, workspace=self.tenant, maker=self.member,
                authorizer=self.admin, poster=self.owner,
            )
        balances = {
            row.key: row.signed_base_amount
            for row in posted_external_account_balances(book=self.book)
        }
        self.assertEqual(balances["CUSTOMER-1:AR"], Decimal("60"))
        item = OpenItem.objects.get(book=self.book, open_item_key="INV-1")
        self.assertEqual(open_item_outstanding(item).amount, Decimal("60"))
        self.assertEqual(list(posted_unapplied_settlements(book=self.book)), [])

    def test_accounting_activation_is_off_by_default_and_auditable(self):
        self.assertFalse(get_accounting_activation_state(self.tenant).enabled)

        enabled = set_accounting_successor_enabled(
            self.tenant, enabled=True, actor=self.owner
        )
        self.assertTrue(enabled.enabled)

        disabled = set_accounting_successor_enabled(
            self.tenant, enabled=False, actor=self.owner
        )
        self.assertFalse(disabled.enabled)

    def test_accounting_activation_fails_closed_for_member_or_readiness_blocker(self):
        with self.assertRaises(PermissionDenied):
            set_accounting_successor_enabled(
                self.tenant, enabled=True, actor=self.member
            )

        self.cash.is_active = False
        self.cash.save(update_fields=("is_active",))
        with self.assertRaises(ValidationError):
            set_accounting_successor_enabled(
                self.tenant, enabled=True, actor=self.owner
            )

    def test_visual_dashboard_and_reports_render_while_gate_is_disabled(self):
        client = TenantClient(self.tenant)
        client.force_login(self.owner)

        dashboard = client.get(reverse("accounting:dashboard"))
        reports = client.get(reverse("accounting:reports"))

        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Ready but disabled")
        self.assertContains(dashboard, "Standalone Accounting")
        self.assertEqual(reports.status_code, 200)
        self.assertContains(reports, "Trial balance")

    def test_visual_workspace_rejects_non_member(self):
        client = TenantClient(self.tenant)
        client.force_login(self.outsider)

        response = client.get(reverse("accounting:dashboard"))

        self.assertEqual(response.status_code, 302)

    def test_visual_credit_sale_requires_real_maker_authorizer_and_poster(self):
        set_accounting_successor_enabled(self.tenant, enabled=True, actor=self.owner)
        party = Party.objects.create(display_name="Visual Team Customer")
        maker_client = TenantClient(self.tenant)
        maker_client.force_login(self.member)
        created = maker_client.post(reverse("accounting:transaction_create"), {
            "transaction_type": "CREDIT_SALE",
            "source_id": "UI-INV-1",
            "effective_date": "2026-08-07",
            "amount": "125.00",
            "party": str(party.pk),
            "new_party_name": "",
            "narration": "Visual workflow invoice",
        })
        voucher = Voucher.objects.get(source_system="ACCOUNTING_UI", source_id="UI-INV-1")
        self.assertEqual(created.status_code, 302)
        self.assertEqual(voucher.state, "DRAFT")

        maker_cannot_authorize = maker_client.post(
            reverse("accounting:voucher_authorize", args=(voucher.pk,))
        )
        self.assertEqual(maker_cannot_authorize.status_code, 403)

        authorizer_client = TenantClient(self.tenant)
        authorizer_client.force_login(self.admin)
        self.assertEqual(authorizer_client.post(
            reverse("accounting:voucher_authorize", args=(voucher.pk,))
        ).status_code, 302)
        voucher.refresh_from_db()
        self.assertEqual(voucher.state, "AUTHORIZED")

        poster_client = TenantClient(self.tenant)
        poster_client.force_login(self.owner)
        self.assertEqual(poster_client.post(
            reverse("accounting:voucher_post", args=(voucher.pk,))
        ).status_code, 302)
        voucher.refresh_from_db()
        self.assertEqual(voucher.state, "POSTED")
        self.assertTrue(OpenItem.objects.filter(
            book=self.book, open_item_key="UI-INV-1"
        ).exists())

    def test_owner_operated_visual_sale_posts_and_creates_customer_inline(self):
        set_accounting_successor_enabled(self.tenant, enabled=True, actor=self.owner)
        client = TenantClient(self.tenant)
        client.force_login(self.owner)

        response = client.post(reverse("accounting:transaction_create"), {
            "transaction_type": "CREDIT_SALE",
            "source_id": "OWNER-INV-1",
            "effective_date": "2026-08-07",
            "amount": "225.00",
            "party": "",
            "new_party_name": "Owner Mode Customer",
            "narration": "Owner operated invoice",
        })

        self.assertEqual(response.status_code, 302)
        voucher = Voucher.objects.get(source_system="ACCOUNTING_UI", source_id="OWNER-INV-1")
        self.assertEqual(voucher.state, "POSTED")
        self.assertEqual(voucher.created_by_id, self.owner.pk)
        self.assertEqual(voucher.authorized_by_id, self.owner.pk)
        self.assertEqual(voucher.posting_batch.posted_by_id, self.owner.pk)
        party = Party.objects.get(display_name="Owner Mode Customer")
        self.assertTrue(ExternalAccount.objects.filter(
            book=self.book, party=party,
            purpose=ExternalAccountPurpose.CUSTOMER_RECEIVABLE,
        ).exists())
        self.assertTrue(OpenItem.objects.filter(
            book=self.book, open_item_key="OWNER-INV-1"
        ).exists())

    def test_owner_can_visually_reverse_own_posting_without_unposting(self):
        set_accounting_successor_enabled(self.tenant, enabled=True, actor=self.owner)
        client = TenantClient(self.tenant)
        client.force_login(self.owner)
        client.post(reverse("accounting:transaction_create"), {
            "transaction_type": "CASH_SALE",
            "source_id": "OWNER-CASH-REV-1",
            "effective_date": "2026-08-07",
            "amount": "75.00",
            "party": "",
            "new_party_name": "",
            "narration": "Cash sale to reverse",
        })
        voucher = Voucher.objects.get(source_id="OWNER-CASH-REV-1")

        response = client.post(reverse("accounting:voucher_reverse", args=(voucher.pk,)), {
            "reversal_date": "2026-08-07",
            "reason": "Owner entered the wrong sale",
            "confirmation": "REVERSE",
        })

        self.assertEqual(response.status_code, 302)
        voucher.refresh_from_db()
        reversal = voucher.posting_batch.reversal_batches.get()
        self.assertEqual(reversal.posted_by_id, self.owner.pk)
        self.assertEqual(reversal.reversal_reason, "Owner entered the wrong sale")
        self.assertEqual(voucher.state, "POSTED")
        self.assertEqual(posted_trial_balance(book=self.book).signed_total, Decimal("0"))
