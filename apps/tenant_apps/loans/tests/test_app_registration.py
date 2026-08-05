from io import StringIO

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase


class LoansAppRegistrationTests(SimpleTestCase):
    databases = {"default"}

    def test_loans_is_registered_as_a_tenant_app(self):
        app_config = apps.get_app_config("loans")

        self.assertEqual(app_config.name, "apps.tenant_apps.loans")
        self.assertEqual(app_config.__class__.__name__, "LoansConfig")
        self.assertIn(
            "apps.tenant_apps.loans.apps.LoansConfig",
            settings.TENANT_APPS,
        )
        self.assertEqual(
            {model.__name__ for model in app_config.get_models()},
            {
                "LoanChangeLog",
                "LoanLicense",
                "LoanNumberSequence",
                "LoanPolicySnapshot",
                "LoanSeries",
                "PawnCollateralItem",
                "PawnCollateralCustodyEvent",
                "PawnLoan",
                "PawnLoanAccountingEvent",
                "PawnLoanAccountingOutbox",
                "PawnLoanApprovalSnapshot",
                "PawnLoanDisbursalSnapshot",
                "PawnLoanAuction",
                "PawnLoanAuctionItem",
                "PawnLoanAuctionReversal",
                "PawnLoanInterestAccrual",
                "PawnLoanInterestAccrualLine",
                "PawnLoanEconomicPolicy",
                "PawnLoanFeePolicy",
                "PawnLoanNotice",
                "PawnLoanRelease",
                "PawnLoanReleaseItem",
                "PawnLoanReleaseReversal",
                "PawnLoanRenewal",
                "PawnLoanRenewalReversal",
                "PawnMetalInterestRatePolicy",
            },
        )

    def test_loans_has_no_pending_model_migrations(self):
        stdout = StringIO()

        call_command(
            "makemigrations",
            "loans",
            check=True,
            dry_run=True,
            stdout=stdout,
            verbosity=1,
        )

        self.assertIn("No changes detected in app 'loans'", stdout.getvalue())
