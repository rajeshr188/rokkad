import uuid
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.loans.domain import LoanDocumentKind
from apps.tenant_apps.loans.models import LoanLicense
from apps.tenant_apps.loans.services import (
    LicenseSeriesError,
    activate_license,
    assert_series_can_issue,
    configure_sequence,
    create_license,
    create_series,
    expire_license,
    update_license,
)


class LicenseSeriesServiceTests(TenantTestCase):
    test_schema_name = f"loans_license_{uuid.uuid4().hex[:8]}"
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
            username="loans-license-owner",
            defaults={"email": "loans-license-owner@example.com"},
        )
        tenant.name = f"Loans License {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = get_user_model().objects.create_user(
            username=f"license-user-{uuid.uuid4().hex[:8]}",
            email=f"license-user-{uuid.uuid4().hex[:8]}@example.com",
        )

    def _create_license(self, *, number="PBL-1", expires_on=date(2027, 1, 1)):
        return create_license(
            workspace=self.tenant,
            name="Pawn Broker License",
            license_number=number,
            issued_on=date(2026, 1, 1),
            expires_on=expires_on,
            actor=self.user,
        )

    def test_workspace_can_have_multiple_active_licenses_and_series(self):
        first = self._create_license(number="PBL-1")
        second = self._create_license(number="PBL-2")
        first_series = create_series(license=first, name="Main", code="A")
        second_series = create_series(license=second, name="Main", code="A")

        self.assertTrue(first.is_active)
        self.assertTrue(second.is_active)
        self.assertEqual(first_series.workspace_id, self.tenant.pk)
        self.assertEqual(second_series.workspace_id, self.tenant.pk)

    def test_license_updates_are_guarded_and_track_actor(self):
        license = self._create_license()

        update_license(license, actor=self.user, name="Updated License")

        license.refresh_from_db()
        self.assertEqual(license.name, "Updated License")
        self.assertEqual(license.updated_by, self.user)
        with self.assertRaises(LicenseSeriesError):
            update_license(license, actor=self.user, is_active=False)

    def test_expired_license_remains_readable_but_cannot_issue_or_reactivate(self):
        license = self._create_license(expires_on=date(2026, 6, 30))
        series = create_series(license=license, name="Main", code="A")

        with self.assertRaisesRegex(LicenseSeriesError, "expired"):
            assert_series_can_issue(series, as_of_date=date(2026, 7, 1))
        expire_license(license, actor=self.user)
        self.assertTrue(LoanLicense.objects.filter(pk=license.pk).exists())
        with self.assertRaisesRegex(LicenseSeriesError, "expired"):
            activate_license(license, actor=self.user, as_of_date=date(2026, 7, 1))

    def test_inactive_license_and_series_each_block_issuance(self):
        license = self._create_license()
        series = create_series(license=license, name="Main", code="A")
        expire_license(license, actor=self.user)
        with self.assertRaisesRegex(LicenseSeriesError, "inactive"):
            assert_series_can_issue(series, as_of_date=date(2026, 6, 1))

        activate_license(license, actor=self.user, as_of_date=date(2026, 6, 1))
        series.is_active = False
        series.save(update_fields=["is_active"])
        with self.assertRaisesRegex(LicenseSeriesError, "series is inactive"):
            assert_series_can_issue(series, as_of_date=date(2026, 6, 1))

    @patch("apps.tenant_apps.loans.services.license_series.AuditLog.log")
    def test_sequence_configuration_is_guarded_and_audited(self, audit_log):
        license = self._create_license()
        series = create_series(license=license, name="Main", code="A")

        sequence = configure_sequence(
            series=series,
            document_kind=LoanDocumentKind.PAWN_LOAN,
            prefix="PL-A-",
            width=6,
            maximum_number=10000,
            actor=self.user,
        )
        configure_sequence(
            series=series,
            document_kind=LoanDocumentKind.PAWN_LOAN,
            prefix="PL-NEW-",
            width=7,
            maximum_number=20000,
            actor=self.user,
        )

        sequence.refresh_from_db()
        self.assertEqual(sequence.prefix, "PL-NEW-")
        self.assertEqual(sequence.updated_by, self.user)
        self.assertEqual(audit_log.call_count, 2)
        self.assertTrue(audit_log.call_args.kwargs["data"]["old"])
        self.assertEqual(audit_log.call_args.kwargs["company"], self.tenant)

    def test_sequence_maximum_cannot_move_below_next_number(self):
        license = self._create_license()
        series = create_series(license=license, name="Main", code="A")
        with patch("apps.tenant_apps.loans.services.license_series.AuditLog.log"):
            sequence = configure_sequence(
                series=series,
                document_kind=LoanDocumentKind.PAWN_LOAN,
                prefix="PL-",
                maximum_number=10,
                actor=self.user,
            )
            sequence.next_number = 8
            sequence.save(update_fields=["next_number"])
            with self.assertRaises(ValidationError):
                configure_sequence(
                    series=series,
                    document_kind=LoanDocumentKind.PAWN_LOAN,
                    prefix="PL-",
                    maximum_number=7,
                    actor=self.user,
                )
