import uuid
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.db import connection
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import Resolver404, resolve, reverse
from django_tenants.test.cases import TenantTestCase
from moneyed import Money

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models import (
    CashFlowDirection,
    PaymentType,
    PaymentVoucher,
    SalesInvoiceVoucher,
)
from apps.tenant_apps.party.models import Party, PartyDocument, PartyPortalAccess
from apps.tenant_apps.party.portal_access import (
    PortalIdentityDenied,
    resolve_portal_identity,
)
from apps.tenant_apps.party.portal_selectors import (
    get_portal_documents_summary,
    get_portal_invoices_summary,
    get_portal_loans_summary,
    get_portal_payments_summary,
    get_portal_statements_summary,
)
from apps.tenant_apps.party.portal_views import (
    portal_dashboard,
    portal_invoices,
    portal_loans,
    portal_payments,
    portal_statements,
)
from apps.tenant_apps.party.services.portal_access import (
    PortalAccessLifecycleError,
    activate_portal_access,
    revoke_portal_access,
    suspend_portal_access,
)
from django_project import tenant_urls, urls


User = get_user_model()

TEST_STORAGES = {
    **settings.STORAGES,
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


class PartyPortalAccessTests(TenantTestCase):
    test_schema_name = f"party_portal_{uuid.uuid4().hex[:8]}"
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
            username="party-portal-owner",
            defaults={"email": "party-portal-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"party-portal-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username=f"portal-user-{uuid.uuid4().hex[:8]}",
            email="portal-user@example.com",
            password="testpass123",
        )
        self.party = Party.objects.create(display_name="Portal Customer")
        self.other_party = Party.objects.create(display_name="Other Customer")
        self.factory = RequestFactory()

    def _request(self):
        request = type("Request", (), {})()
        request.user = self.user
        request.tenant = self.tenant
        return request

    def _view_request(self, path="/portal/"):
        request = self.factory.get(path, HTTP_HOST=self.test_domain)
        request.user = self.user
        request.tenant = self.tenant
        request.LANGUAGE_CODE = settings.LANGUAGE_CODE
        return request

    def _customer_for_party(self, party, *, first_name):
        return Customer.objects.create(
            firstname=f"{first_name}-{uuid.uuid4().hex[:8]}",
            lastname="Portal",
            customer_type=Customer.CustomerType.Retail,
            party=party,
        )

    def _sales_invoice(self, *, party, amount, received=0):
        return SalesInvoiceVoucher.objects.create(
            party=party,
            subtotal=Money(amount, "INR"),
            taxable_amount=Money(amount, "INR"),
            total_amount=Money(amount, "INR"),
            received_amount=Money(received, "INR"),
            description=f"Portal invoice {party.pk}",
            auto_post_to_accounting=False,
        )

    def _receipt_for_invoice(self, invoice, *, amount):
        return PaymentVoucher.objects.create(
            source_content_type=ContentType.objects.get_for_model(SalesInvoiceVoucher),
            source_object_id=invoice.pk,
            total_amount=Money(amount, "INR"),
            payment_type=PaymentType.RECEIPT,
            direction=CashFlowDirection.RECEIPT,
            description=f"Portal receipt {invoice.pk}",
            auto_post_to_accounting=False,
        )

    def _loan_series(self):
        license_record = License.objects.create(
            name=f"Portal License {uuid.uuid4().hex[:8]}",
            license_number=f"PL-{uuid.uuid4().hex[:8]}",
        )
        given_series = Series.objects.create(
            license=license_record,
            name=f"Given {uuid.uuid4().hex[:6]}",
            prefix="PG",
            loan_type=Series.LoanType.GIVEN,
        )
        taken_series = Series.objects.create(
            license=license_record,
            name=f"Taken {uuid.uuid4().hex[:6]}",
            prefix="PT",
            loan_type=Series.LoanType.TAKEN,
        )
        return given_series, taken_series

    def _given_loan_for_party(self, *, party, customer, series, loan_id, amount):
        loan = GivenLoan.objects.create(
            loan_id=loan_id,
            series=series,
            borrower=customer,
            borrower_party=party,
            status="Draft",
        )
        LoanItem.objects.create(
            loan=loan,
            itemtype="Gold",
            quantity=1,
            weight=Decimal("10.000"),
            purity=Decimal("91.60"),
            loanamount=Decimal(str(amount)),
            interestrate=Decimal("2.00"),
            itemdesc=f"Portal item {loan_id}",
        )
        loan.status = "ActiveCurrent"
        loan.save(update_fields=["status"])
        return loan

    def _taken_loan_for_party(self, *, party, customer, series, loan_id):
        return TakenLoan.objects.create(
            loan_id=loan_id,
            series=series,
            lender=customer,
            lender_party=party,
            status="Active",
        )

    def test_active_party_portal_access_resolves_identity(self):
        grant = PartyPortalAccess.objects.create(
            party=self.party,
            user=self.user,
            status=PartyPortalAccess.Status.ACTIVE,
        )

        identity = resolve_portal_identity(self._request())

        self.assertEqual(identity.party, self.party)
        self.assertEqual(identity.access_grant, grant)
        self.assertEqual(identity.workspace, self.tenant)

    def test_inactive_party_portal_access_fails_closed(self):
        PartyPortalAccess.objects.create(
            party=self.party,
            user=self.user,
            status=PartyPortalAccess.Status.INVITED,
        )

        with self.assertRaises(PortalIdentityDenied):
            resolve_portal_identity(self._request())

    def test_portal_access_lifecycle_activate_logs_and_enables_identity(self):
        grant = PartyPortalAccess.objects.create(
            party=self.party,
            user=self.user,
            status=PartyPortalAccess.Status.INVITED,
        )

        with patch(
            "apps.tenant_apps.party.services.portal_access.AuditLog.log"
        ) as audit_log:
            result = activate_portal_access(
                grant,
                actor=self.user,
                request=self._request(),
            )

        grant.refresh_from_db()
        identity = resolve_portal_identity(self._request())
        self.assertTrue(result.changed)
        self.assertEqual(grant.status, PartyPortalAccess.Status.ACTIVE)
        self.assertIsNotNone(grant.activated_at)
        self.assertEqual(identity.access_grant, grant)
        audit_log.assert_called_once()
        self.assertEqual(audit_log.call_args.args[0], "PARTY_PORTAL_ACCESS_ACTIVATE")
        self.assertEqual(audit_log.call_args.kwargs["company"], self.tenant)
        self.assertEqual(
            audit_log.call_args.kwargs["data"]["previous_status"],
            PartyPortalAccess.Status.INVITED,
        )

    def test_portal_access_lifecycle_suspend_logs_and_disables_identity(self):
        grant = PartyPortalAccess.objects.create(
            party=self.party,
            user=self.user,
            status=PartyPortalAccess.Status.ACTIVE,
        )

        with patch(
            "apps.tenant_apps.party.services.portal_access.AuditLog.log"
        ) as audit_log:
            result = suspend_portal_access(
                grant,
                actor=self.user,
                request=self._request(),
            )

        grant.refresh_from_db()
        self.assertTrue(result.changed)
        self.assertEqual(grant.status, PartyPortalAccess.Status.SUSPENDED)
        with self.assertRaises(PortalIdentityDenied):
            resolve_portal_identity(self._request())
        audit_log.assert_called_once()
        self.assertEqual(audit_log.call_args.args[0], "PARTY_PORTAL_ACCESS_SUSPEND")

    def test_portal_access_lifecycle_revoke_logs_and_blocks_reactivation(self):
        grant = PartyPortalAccess.objects.create(
            party=self.party,
            user=self.user,
            status=PartyPortalAccess.Status.ACTIVE,
        )

        with patch(
            "apps.tenant_apps.party.services.portal_access.AuditLog.log"
        ) as audit_log:
            result = revoke_portal_access(
                grant,
                actor=self.user,
                request=self._request(),
            )

        grant.refresh_from_db()
        self.assertTrue(result.changed)
        self.assertEqual(grant.status, PartyPortalAccess.Status.REVOKED)
        self.assertIsNotNone(grant.revoked_at)
        with self.assertRaises(PortalIdentityDenied):
            resolve_portal_identity(self._request())
        with self.assertRaises(PortalAccessLifecycleError):
            activate_portal_access(grant, actor=self.user, request=self._request())
        audit_log.assert_called_once()
        self.assertEqual(audit_log.call_args.args[0], "PARTY_PORTAL_ACCESS_REVOKE")

    def test_document_selector_only_returns_granted_party_documents(self):
        grant = PartyPortalAccess.objects.create(
            party=self.party,
            user=self.user,
            status=PartyPortalAccess.Status.ACTIVE,
        )
        own_document = PartyDocument.objects.create(
            party=self.party,
            document_type=PartyDocument.DocumentType.KYC,
            title="Own KYC",
        )
        PartyDocument.objects.create(
            party=self.other_party,
            document_type=PartyDocument.DocumentType.KYC,
            title="Other KYC",
        )
        identity = resolve_portal_identity(self._request())

        summary = get_portal_documents_summary(identity)

        self.assertEqual(identity.access_grant, grant)
        self.assertEqual(summary.total_count, 1)
        self.assertEqual(summary.items, (own_document,))

    def test_invoice_payment_and_statement_selectors_stay_party_scoped(self):
        PartyPortalAccess.objects.create(
            party=self.party,
            user=self.user,
            status=PartyPortalAccess.Status.ACTIVE,
        )
        own_invoice = self._sales_invoice(
            party=self.party,
            amount=100,
        )
        other_invoice = self._sales_invoice(
            party=self.other_party,
            amount=900,
        )
        own_payment = self._receipt_for_invoice(own_invoice, amount=25)
        self._receipt_for_invoice(other_invoice, amount=900)
        identity = resolve_portal_identity(self._request())

        invoice_summary = get_portal_invoices_summary(identity)
        payment_summary = get_portal_payments_summary(identity)
        statement_summary = get_portal_statements_summary(identity)

        self.assertEqual(invoice_summary.total_count, 1)
        self.assertEqual(invoice_summary.unpaid_count, 1)
        self.assertEqual(invoice_summary.outstanding_amount, Money(100, "INR").amount)
        self.assertEqual(invoice_summary.items, (own_invoice,))
        self.assertEqual(payment_summary.total_count, 1)
        self.assertEqual(payment_summary.total_amount, Money(25, "INR").amount)
        self.assertEqual(payment_summary.items, (own_payment,))
        self.assertEqual(statement_summary.closing_balance, Money(75, "INR").amount)

    def _retired_girvi_loan_selector_contract(self):
        PartyPortalAccess.objects.create(
            party=self.party,
            user=self.user,
            status=PartyPortalAccess.Status.ACTIVE,
        )
        customer = self._customer_for_party(self.party, first_name="Borrower")
        other_customer = self._customer_for_party(self.other_party, first_name="OtherBorrower")
        given_series, taken_series = self._loan_series()
        self._given_loan_for_party(
            party=self.party,
            customer=customer,
            series=given_series,
            loan_id=f"PG-{uuid.uuid4().hex[:8]}",
            amount=1000,
        )
        self._taken_loan_for_party(
            party=self.party,
            customer=customer,
            series=taken_series,
            loan_id=f"PT-{uuid.uuid4().hex[:8]}",
        )
        self._given_loan_for_party(
            party=self.other_party,
            customer=other_customer,
            series=given_series,
            loan_id=f"PG-{uuid.uuid4().hex[:8]}",
            amount=9000,
        )
        identity = resolve_portal_identity(self._request())

        summary = get_portal_loans_summary(identity)
        self.assertEqual(summary.active_count, 0)
        self.assertEqual(summary.closed_count, 0)
        self.assertEqual(summary.total_count, 0)
        self.assertEqual(summary.items, ())

    @override_settings(STORAGES=TEST_STORAGES)
    def test_portal_read_pages_render_without_staff_navigation_or_cross_party_data(self):
        PartyPortalAccess.objects.create(
            party=self.party,
            user=self.user,
            status=PartyPortalAccess.Status.ACTIVE,
        )
        own_invoice = self._sales_invoice(
            party=self.party,
            amount=125,
        )
        other_invoice = self._sales_invoice(
            party=self.other_party,
            amount=950,
        )
        payment = self._receipt_for_invoice(own_invoice, amount=50)
        self._receipt_for_invoice(other_invoice, amount=950)

        render_targets = (
            (portal_dashboard, "/portal/", "Overview"),
            (portal_invoices, "/portal/invoices/", own_invoice.invoice_number),
            (portal_payments, "/portal/payments/", payment.payment_id),
            (portal_statements, "/portal/statements/", "Closing balance"),
        )
        for view, path, expected in render_targets:
            with self.subTest(path=path):
                response = view(self._view_request(path))
                content = response.content.decode()
                self.assertEqual(response.status_code, 200)
                self.assertIn(expected, content)
                self.assertIn("Portal Customer", content)
                self.assertNotIn(other_invoice.invoice_number, content)
                self.assertNotIn("workspace-sidebar", content)
                self.assertNotIn("Account &amp; Workspace Management", content)

    @override_settings(STORAGES=TEST_STORAGES)
    def _retired_portal_girvi_loans_page(self):
        PartyPortalAccess.objects.create(
            party=self.party,
            user=self.user,
            status=PartyPortalAccess.Status.ACTIVE,
        )
        customer = self._customer_for_party(self.party, first_name="LoanRender")
        other_customer = self._customer_for_party(self.other_party, first_name="LoanHidden")
        given_series, _taken_series = self._loan_series()
        own_loan = self._given_loan_for_party(
            party=self.party,
            customer=customer,
            series=given_series,
            loan_id=f"PG-{uuid.uuid4().hex[:8]}",
            amount=700,
        )
        other_loan = self._given_loan_for_party(
            party=self.other_party,
            customer=other_customer,
            series=given_series,
            loan_id=f"PG-{uuid.uuid4().hex[:8]}",
            amount=1700,
        )

        response = portal_loans(self._view_request("/portal/loans/"))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn(own_loan.loan_id, content)
        self.assertIn("Portal Customer", content)
        self.assertNotIn(other_loan.loan_id, content)
        self.assertNotIn("workspace-sidebar", content)
        self.assertNotIn("Account &amp; Workspace Management", content)


class PartyPortalRouteIntentTests(SimpleTestCase):
    def test_portal_routes_are_tenant_only(self):
        expected_routes = {
            "customer_portal_dashboard": "/portal/",
            "customer_portal_loans": "/portal/loans/",
            "customer_portal_invoices": "/portal/invoices/",
            "customer_portal_payments": "/portal/payments/",
            "customer_portal_documents": "/portal/documents/",
            "customer_portal_statements": "/portal/statements/",
        }
        for route_name, path in expected_routes.items():
            with self.subTest(route_name=route_name):
                self.assertEqual(reverse(route_name, urlconf=tenant_urls), path)
                self.assertEqual(resolve(path, urlconf=tenant_urls).url_name, route_name)
                with self.assertRaises(Resolver404):
                    resolve(path, urlconf=urls)
