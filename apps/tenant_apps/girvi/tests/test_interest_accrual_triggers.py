from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.management import CommandError
from django.http import HttpResponseRedirect
from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.girvi.management.commands.accrue_loan_interest import Command
from apps.tenant_apps.girvi.service_modules.release_lifecycle import (
    ReleaseCreateCommand,
    ReleaseCreatePreview,
    ReleaseLifecycleService,
)
from apps.tenant_apps.girvi.service_modules.renewal import (
    LoanRenewalCommand,
    LoanRenewalPreview,
    LoanRenewalService,
)
from apps.tenant_apps.girvi.views.loanpayment import loan_payment_create_view


class InterestAccrualTriggerTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(
            id=1,
            is_authenticated=True,
            profile=SimpleNamespace(workspace=SimpleNamespace()),
        )

    @patch("apps.tenant_apps.girvi.views.loanpayment.reverse", return_value="/girvi/loan/1/")
    @patch("apps.tenant_apps.girvi.views.loanpayment.messages.success")
    @patch("apps.tenant_apps.girvi.service_modules.repayment.GivenLoanPostingService.post_repayment")
    @patch("apps.tenant_apps.girvi.service_modules.repayment.CompanyPreferences")
    @patch("apps.tenant_apps.girvi.views.loanpayment.get_object_or_404")
    def test_payment_view_triggers_interest_catchup_before_receipt(
        self,
        mock_get_object_or_404,
        mock_company_preferences,
        mock_post_repayment,
        _mock_success,
        _mock_reverse,
    ):
        payment = MagicMock(payment_id="PAY-1")
        mock_post_repayment.return_value = (payment, True)
        mock_company_preferences.return_value = SimpleNamespace(loan_catchup_on_receipt=True)

        loan = MagicMock()
        loan.pk = 1
        loan.loan_id = "GL-001"
        loan.create_payment.return_value = payment
        mock_get_object_or_404.return_value = loan

        request = self.factory.post(
            "/girvi/loanpayment/1/create/",
            data={
                "total_amount": "1000.00",
                "payment_date": "2026-04-06T10:30",
                "payment_method": "CASH",
                "reference_number": "REF-1",
                "interest_amount": "100.00",
                "description": "test",
            },
        )
        request.user = self.user
        request.htmx = False

        with patch(
            "apps.tenant_apps.girvi.service_modules.repayment.InterestAccrualService.execute"
        ) as mock_accrue:
            response = loan_payment_create_view.__wrapped__(request, pk=1)

        self.assertIsInstance(response, HttpResponseRedirect)
        mock_accrue.assert_called_once()
        command = mock_accrue.call_args.args[0]
        self.assertEqual(command.loan, loan)
        self.assertEqual(command.trigger_source, "RECEIPT")
        self.assertTrue(command.post_to_accounting)
        mock_post_repayment.assert_called_once()

    def test_release_lifecycle_triggers_interest_catchup_before_release_posting(self):
        loan = SimpleNamespace(loan_id="GL-002", status="Disbursed")
        command = ReleaseCreateCommand(
            loan=loan,
            created_by=self.user,
            release_date="2026-04-06T10:30",
            released_by=None,
        )
        preview = ReleaseCreatePreview(
            is_valid=True,
            loan=loan,
            loan_id="GL-002",
            current_status="Disbursed",
            warnings=[],
            errors=[],
        )

        request_closure = MagicMock()
        request_closure.can_proceed.return_value = True
        complete_closure = MagicMock()
        complete_closure.can_proceed.return_value = True
        flow = SimpleNamespace(
            request_closure=request_closure,
            complete_closure=complete_closure,
        )
        release = MagicMock(release_id="REL-002")

        with patch.object(
            ReleaseLifecycleService,
            "preview",
            return_value=preview,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.transaction.atomic",
            side_effect=lambda: nullcontext(),
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.build_runtime_loan_flow",
            return_value=flow,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.apps.get_model",
            return_value=MagicMock(return_value=release),
        ), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.InterestAccrualService.execute"
        ) as mock_accrue, patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.record_loan_release",
            return_value=(MagicMock(payment_id="PAY-REL"), True),
        ):
            result = ReleaseLifecycleService.execute(command)

        self.assertTrue(result.success)
        mock_accrue.assert_called_once()
        accrual_command = mock_accrue.call_args.args[0]
        self.assertEqual(accrual_command.loan, loan)
        self.assertEqual(accrual_command.trigger_source, "RELEASE")
        self.assertTrue(accrual_command.post_to_accounting)

    def test_renewal_service_triggers_interest_catchup_before_rollover(self):
        service = LoanRenewalService()
        command = LoanRenewalCommand(
            source_loan_id=7,
            renewal_date="2026-04-06T10:30",
            mode="PAY_AND_RENEW",
            interest_paid=Decimal("50.00"),
            principal_paid=Decimal("100.00"),
            created_by=self.user,
        )
        preview = LoanRenewalPreview(
            source_loan_id=7,
            mode="PAY_AND_RENEW",
            outstanding_principal=Decimal("500.00"),
            interest_due=Decimal("50.00"),
            collateral_value=Decimal("1000.00"),
            principal_paid=Decimal("100.00"),
            interest_paid=Decimal("50.00"),
            requested_extra_amount=Decimal("0.00"),
            new_principal=Decimal("400.00"),
            is_valid=True,
            errors=[],
        )

        source_loan = MagicMock()
        source_loan.pk = 7
        source_loan.loan_id = "GL-007"
        source_loan.status = "Disbursed"
        source_loan.get_loan_amount = Decimal("500.00")
        source_loan.loanitems.all.return_value = []

        new_loan = MagicMock()
        new_loan.pk = 8
        new_loan.loan_id = "GL-008"

        request_renewal = MagicMock()
        request_renewal.can_proceed.return_value = True
        source_flow = SimpleNamespace(
            request_renewal=request_renewal,
            complete_renewal=MagicMock(),
        )
        new_flow = SimpleNamespace(
            submit_for_approval=SimpleNamespace(can_proceed=lambda: False),
            approve_loan=SimpleNamespace(can_proceed=lambda: False),
            disburse_loan=SimpleNamespace(can_proceed=lambda: False),
        )

        with patch.object(service, "preview", return_value=preview), patch(
            "apps.tenant_apps.girvi.service_modules.renewal.transaction.atomic",
            side_effect=lambda: nullcontext(),
        ), patch(
            "apps.tenant_apps.girvi.service_modules.renewal.GivenLoan.objects.select_for_update"
        ) as mock_select_for_update, patch(
            "apps.tenant_apps.girvi.service_modules.renewal.GivenLoan.objects.create",
            return_value=new_loan,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.renewal.LoanItem.objects.create"
        ), patch(
            "apps.tenant_apps.girvi.service_modules.renewal.LoanRenewal.objects.create"
        ), patch(
            "apps.tenant_apps.girvi.service_modules.renewal.record_loan_disbursal"
        ), patch(
            "apps.tenant_apps.girvi.service_modules.renewal.InterestAccrualService.execute"
        ) as mock_accrue, patch(
            "apps.tenant_apps.girvi.service_modules.renewal.build_runtime_loan_flow",
            side_effect=[source_flow, new_flow],
        ):
            mock_select_for_update.return_value.get.return_value = source_loan
            result = service.execute(command)

        self.assertTrue(result.success)
        mock_accrue.assert_called_once()
        accrual_command = mock_accrue.call_args.args[0]
        self.assertEqual(accrual_command.loan, source_loan)
        self.assertEqual(accrual_command.trigger_source, "RENEWAL")
        self.assertTrue(accrual_command.post_to_accounting)


class InterestAccrualCommandTests(SimpleTestCase):
    def test_management_command_imports(self):
        from apps.tenant_apps.girvi.management.commands.accrue_loan_interest import Command

        self.assertTrue(hasattr(Command, "handle"))

    def test_backfill_mode_uses_backfill_trigger_source(self):
        command = Command()
        tenant = SimpleNamespace(schema_name="tenant1")
        loan = SimpleNamespace(loan_id="GL-900", created_by=None)

        with patch.object(command, "_tenant_queryset", return_value=[tenant]), patch.object(
            command, "_loan_queryset", return_value=[loan]
        ), patch(
            "apps.tenant_apps.girvi.management.commands.accrue_loan_interest.tenant_context",
            side_effect=lambda _tenant: nullcontext(),
        ), patch(
            "apps.tenant_apps.girvi.management.commands.accrue_loan_interest.InterestAccrualService.execute",
            return_value=SimpleNamespace(
                success=True,
                created_count=0,
                total_created_amount=Decimal("0.00"),
                message="No new interest accrual periods were due.",
            ),
        ) as mock_execute:
            summary = command.handle(
                as_of_date="2026-04-06",
                schema=None,
                loan_id=None,
                trigger_source="SCHEDULED",
                dry_run=False,
                skip_accounting=True,
                backfill=True,
            )

        self.assertEqual(summary["tenants_processed"], 1)
        accrual_command = mock_execute.call_args.args[0]
        self.assertEqual(accrual_command.trigger_source, "BACKFILL")
        self.assertIn("Backfill", accrual_command.notes)

    def test_backfill_requires_as_of_date_not_in_future(self):
        command = Command()

        with self.assertRaises(CommandError):
            command.handle(
                as_of_date="3026-01-01",
                schema=None,
                loan_id=None,
                trigger_source="SCHEDULED",
                dry_run=True,
                skip_accounting=True,
                backfill=True,
            )

    def test_scheduled_run_respects_eom_company_preference(self):
        command = Command()
        tenant = SimpleNamespace(schema_name="tenant1")
        loan = SimpleNamespace(loan_id="GL-901", created_by=None)

        with patch.object(command, "_tenant_queryset", return_value=[tenant]), patch.object(
            command, "_loan_queryset", return_value=[loan]
        ), patch(
            "apps.tenant_apps.girvi.management.commands.accrue_loan_interest.CompanyPreferences",
            return_value=SimpleNamespace(loan_accrual_timing="EOM"),
        ), patch(
            "apps.tenant_apps.girvi.management.commands.accrue_loan_interest.tenant_context",
            side_effect=lambda _tenant: nullcontext(),
        ), patch(
            "apps.tenant_apps.girvi.management.commands.accrue_loan_interest.InterestAccrualService.execute"
        ) as mock_execute:
            summary = command.handle(
                as_of_date="2026-04-06",
                schema=None,
                loan_id=None,
                trigger_source="SCHEDULED",
                dry_run=False,
                skip_accounting=True,
                backfill=False,
                respect_timing=True,
            )

        self.assertEqual(summary["timing_skips"], 1)
        mock_execute.assert_not_called()

    def test_scheduled_run_allows_bom_on_first_day(self):
        command = Command()
        tenant = SimpleNamespace(schema_name="tenant1")
        loan = SimpleNamespace(loan_id="GL-902", created_by=None)

        with patch.object(command, "_tenant_queryset", return_value=[tenant]), patch.object(
            command, "_loan_queryset", return_value=[loan]
        ), patch(
            "apps.tenant_apps.girvi.management.commands.accrue_loan_interest.CompanyPreferences",
            return_value=SimpleNamespace(loan_accrual_timing="BOM"),
        ), patch(
            "apps.tenant_apps.girvi.management.commands.accrue_loan_interest.tenant_context",
            side_effect=lambda _tenant: nullcontext(),
        ), patch(
            "apps.tenant_apps.girvi.management.commands.accrue_loan_interest.InterestAccrualService.execute",
            return_value=SimpleNamespace(
                success=True,
                created_count=0,
                total_created_amount=Decimal("0.00"),
                message="No new interest accrual periods were due.",
            ),
        ) as mock_execute:
            command.handle(
                as_of_date="2026-04-01",
                schema=None,
                loan_id=None,
                trigger_source="SCHEDULED",
                dry_run=False,
                skip_accounting=True,
                backfill=False,
                respect_timing=True,
            )

        mock_execute.assert_called_once()
