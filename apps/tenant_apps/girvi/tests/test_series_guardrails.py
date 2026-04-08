"""
Test Suite for Series Guardrails Feature

Run with:
    python manage.py test tests.test_series_guardrails

Or run specific tests:
    python manage.py test tests.test_series_guardrails.SeriesGuardrailsTestCase.test_loan_count_threshold
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.tenant_apps.girvi.models import Series, License, GivenLoan
from apps.tenant_apps.contact.models import Customer

User = get_user_model()


class SeriesGuardrailsTestCase(TestCase):
    """Test Series guardrails functionality"""

    def setUp(self):
        """Create test data"""
        # Create user and workspace
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123"
        )

        # Create license
        self.license = License.objects.create(
            name="Test License",
            license_number="TEST123",
            type="PBL",
            status="ACTIVE",
            shopname="Test Shop",
            business_type="PAWNBROKER",
        )

        # Create series
        self.series = Series.objects.create(
            license=self.license,
            name="TEST",
            prefix="T",
            max_limit=5,
            loan_type="Given",
            is_active=True,
        )

        # Create customer
        self.customer = Customer.objects.create(
            name="Test Customer",
            phone="9999999999",
            workspace=self.user.profile.workspace,
        )

    def test_series_creation(self):
        """Test that series is created with default guardrail values"""
        self.assertEqual(self.series.name, "TEST")
        self.assertIsNone(self.series.loan_count_threshold)
        self.assertIsNone(self.series.loan_amount_threshold)
        self.assertEqual(self.series.deactivation_rule, "NONE")
        self.assertFalse(self.series.deactivated_for_loans)
        self.assertFalse(self.series.deactivated_for_releases)

    def test_loan_count_threshold_check(self):
        """Test loan count threshold checking"""
        self.series.loan_count_threshold = 2
        self.series.save()

        # Initially not exceeded
        self.assertFalse(self.series.is_loan_count_exceeded())
        self.assertEqual(self.series.get_current_loan_count(), 0)

    def test_loan_amount_threshold_check(self):
        """Test loan amount threshold checking"""
        self.series.loan_amount_threshold = Decimal("10000")
        self.series.save()

        # Initially not exceeded
        self.assertFalse(self.series.is_loan_amount_exceeded())
        self.assertEqual(self.series.get_current_loan_amount(), Decimal("0"))

    def test_can_create_loan_when_active(self):
        """Test that loans can be created when series is active"""
        self.assertTrue(self.series.can_create_loan())
        self.assertFalse(self.series.deactivated_for_loans)

    def test_can_create_loan_when_deactivated(self):
        """Test that loans cannot be created when deactivated"""
        self.series.deactivated_for_loans = True
        self.series.save()

        self.assertFalse(self.series.can_create_loan())

    def test_can_create_loan_when_inactive(self):
        """Test that loans cannot be created when series is inactive"""
        self.series.is_active = False
        self.series.save()

        self.assertFalse(self.series.can_create_loan())

    def test_can_create_release_when_active(self):
        """Test that releases can be created when series is active"""
        self.assertTrue(self.series.can_create_release())
        self.assertFalse(self.series.deactivated_for_releases)

    def test_can_create_release_when_deactivated(self):
        """Test that releases cannot be created when deactivated"""
        self.series.deactivated_for_releases = True
        self.series.save()

        self.assertFalse(self.series.can_create_release())

    def test_deactivation_rule_loans_only(self):
        """Test LOANS_ONLY deactivation rule"""
        self.series.deactivation_rule = Series.DeactivationRule.LOANS_ONLY
        self.series.deactivated_for_loans = True
        self.series.save()

        self.assertFalse(self.series.can_create_loan())
        self.assertTrue(self.series.can_create_release())

    def test_deactivation_rule_releases_only(self):
        """Test RELEASES_ONLY deactivation rule"""
        self.series.deactivation_rule = Series.DeactivationRule.RELEASES_ONLY
        self.series.deactivated_for_releases = True
        self.series.save()

        self.assertTrue(self.series.can_create_loan())
        self.assertFalse(self.series.can_create_release())

    def test_deactivation_rule_both(self):
        """Test BOTH deactivation rule"""
        self.series.deactivation_rule = Series.DeactivationRule.BOTH
        self.series.deactivated_for_loans = True
        self.series.deactivated_for_releases = True
        self.series.save()

        self.assertFalse(self.series.can_create_loan())
        self.assertFalse(self.series.can_create_release())

    def test_get_guardrail_status(self):
        """Test get_guardrail_status method"""
        self.series.loan_count_threshold = 100
        self.series.loan_amount_threshold = Decimal("500000")
        self.series.deactivation_rule = Series.DeactivationRule.LOANS_ONLY
        self.series.save()

        status = self.series.get_guardrail_status()

        self.assertEqual(status["series_id"], self.series.pk)
        self.assertEqual(status["loan_count_threshold"], 100)
        self.assertEqual(status["loan_amount_threshold"], Decimal("500000"))
        self.assertEqual(status["deactivation_rule"], Series.DeactivationRule.LOANS_ONLY)
        self.assertTrue(status["can_create_loan"])
        self.assertTrue(status["can_create_release"])

    def test_manager_active_for_loans(self):
        """Test active_for_loans manager method"""
        # Create deactivated series
        deactivated_series = Series.objects.create(
            license=self.license,
            name="DEACTIVATED",
            prefix="D",
            deactivated_for_loans=True,
        )

        active_series = Series.objects.active_for_loans()

        self.assertIn(self.series, active_series)
        self.assertNotIn(deactivated_series, active_series)

    def test_manager_active_for_releases(self):
        """Test active_for_releases manager method"""
        # Create deactivated series
        deactivated_series = Series.objects.create(
            license=self.license,
            name="DEACTIVATED",
            prefix="D",
            deactivated_for_releases=True,
        )

        active_series = Series.objects.active_for_releases()

        self.assertIn(self.series, active_series)
        self.assertNotIn(deactivated_series, active_series)

    def test_check_and_apply_deactivation_no_thresholds(self):
        """Test that no deactivation occurs when thresholds not configured"""
        was_deactivated, reason = self.series.check_and_apply_deactivation()

        self.assertFalse(was_deactivated)
        self.assertEqual(reason, "")

    def test_string_representation(self):
        """Test series string representation"""
        expected = f"{self.series.prefix}-{self.series.name}"
        self.assertEqual(str(self.series), expected)


class SeriesGuardrailsIntegrationTestCase(TestCase):
    """Integration tests for guardrails with actual loan creation"""

    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(
            username="testuser2",
            password="testpass123"
        )

        self.license = License.objects.create(
            name="Integration Test License",
            license_number="INT123",
            type="PBL",
            status="ACTIVE",
            shopname="Integration Test Shop",
            business_type="PAWNBROKER",
        )

        self.series = Series.objects.create(
            license=self.license,
            name="INTEGRATION",
            prefix="I",
            is_active=True,
        )

        self.customer = Customer.objects.create(
            name="Integration Test Customer",
            phone="8888888888",
            workspace=self.user.profile.workspace,
        )

    def test_series_with_configuration(self):
        """Test series with guardrail configuration"""
        self.series.loan_count_threshold = 100
        self.series.loan_amount_threshold = Decimal("1000000")
        self.series.deactivation_rule = Series.DeactivationRule.LOANS_ONLY
        self.series.save()

        self.assertEqual(self.series.loan_count_threshold, 100)
        self.assertEqual(self.series.loan_amount_threshold, Decimal("1000000"))
        self.assertEqual(
            self.series.deactivation_rule,
            Series.DeactivationRule.LOANS_ONLY
        )


if __name__ == "__main__":
    import unittest
    unittest.main()
