from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain import (
    LoanAmortisationMethod,
    LoanRepaymentStructure,
    RepaymentScheduleInput,
    ScheduleRateTranche,
)
from apps.tenant_apps.loans.services import (
    RepaymentScheduleError,
    generate_repayment_schedule,
    generate_shortened_installment_schedule,
)


class RepaymentScheduleTests(SimpleTestCase):
    def value(self, structure, *, amortisation="NONE", rate="1", tenure=12, tranches=()):
        return RepaymentScheduleInput(
            repayment_structure=structure,
            amortisation_method=amortisation,
            disbursed_on=date(2028, 1, 31),
            principal=Decimal("120000.00"),
            monthly_interest_rate=Decimal(rate),
            tenure_months=tenure,
            rate_tranches=tranches,
        )

    def test_single_and_flexible_bullets_settle_at_maturity(self):
        for structure in (
            LoanRepaymentStructure.SINGLE_PAYMENT_BULLET,
            LoanRepaymentStructure.FLEXIBLE_PARTIAL_PAYMENT,
        ):
            with self.subTest(structure=structure):
                schedule = generate_repayment_schedule(self.value(structure))
                self.assertEqual(schedule.maturity_date, date(2029, 1, 31))
                self.assertEqual(len(schedule.repayments), 1)
                self.assertEqual(schedule.repayments[0].principal_due, Decimal("120000.00"))
                self.assertEqual(schedule.contractual_interest, Decimal("14400.00"))
                self.assertEqual(schedule.total_repayable, Decimal("134400.00"))

    def test_periodic_interest_bullet_recovers_original_day_after_leap_clamp(self):
        schedule = generate_repayment_schedule(
            self.value(LoanRepaymentStructure.PERIODIC_INTEREST_BULLET)
        )

        self.assertEqual(schedule.repayments[0].due_date, date(2028, 2, 29))
        self.assertEqual(schedule.repayments[1].due_date, date(2028, 3, 31))
        self.assertTrue(all(row.interest_due == Decimal("1200.00") for row in schedule.repayments))
        self.assertTrue(all(row.principal_due == 0 for row in schedule.repayments[:-1]))
        self.assertEqual(schedule.repayments[-1].principal_due, Decimal("120000.00"))

    def test_mixed_rate_tranches_reconcile_bullet_interest(self):
        schedule = generate_repayment_schedule(self.value(
            LoanRepaymentStructure.SINGLE_PAYMENT_BULLET,
            tenure=3,
            tranches=(
                ScheduleRateTranche(Decimal("70000.00"), Decimal("1.00")),
                ScheduleRateTranche(Decimal("50000.00"), Decimal("2.00")),
            ),
        ))
        self.assertEqual(schedule.contractual_interest, Decimal("5100.00"))

    def test_emi_reconciles_principal_and_absorbs_residue_in_final_payment(self):
        schedule = generate_repayment_schedule(self.value(
            LoanRepaymentStructure.INSTALLMENT,
            amortisation=LoanAmortisationMethod.EMI,
        ))

        self.assertEqual(len(schedule.repayments), 12)
        self.assertEqual(sum(row.principal_due for row in schedule.repayments), Decimal("120000.00"))
        self.assertTrue(all(row.closing_principal >= 0 for row in schedule.repayments))
        self.assertEqual(schedule.repayments[-1].closing_principal, Decimal("0.00"))
        self.assertEqual(schedule.repayments[0].total_due, Decimal("10661.85"))

    def test_equal_principal_matches_owner_examples(self):
        schedule = generate_repayment_schedule(self.value(
            LoanRepaymentStructure.INSTALLMENT,
            amortisation=LoanAmortisationMethod.EQUAL_PRINCIPAL,
        ))
        self.assertEqual(schedule.repayments[0].total_due, Decimal("11200.00"))
        self.assertEqual(schedule.repayments[1].total_due, Decimal("11100.00"))
        self.assertEqual(schedule.repayments[-1].total_due, Decimal("10100.00"))
        self.assertEqual(sum(row.principal_due for row in schedule.repayments), Decimal("120000.00"))

    def test_zero_rate_and_deterministic_fingerprint(self):
        value = self.value(
            LoanRepaymentStructure.INSTALLMENT,
            amortisation=LoanAmortisationMethod.EMI,
            rate="0",
        )
        first = generate_repayment_schedule(value)
        second = generate_repayment_schedule(value)
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(first.contractual_interest, Decimal("0.00"))
        self.assertEqual(sum(row.principal_due for row in first.repayments), Decimal("120000.00"))

    def test_rejects_non_reconciling_tranches_and_legacy_contract(self):
        with self.assertRaises(RepaymentScheduleError):
            generate_repayment_schedule(self.value(
                LoanRepaymentStructure.SINGLE_PAYMENT_BULLET,
                tranches=(ScheduleRateTranche(Decimal("1.00"), Decimal("1")),),
            ))
        with self.assertRaises(RepaymentScheduleError):
            generate_repayment_schedule(self.value(LoanRepaymentStructure.LEGACY_UNSPECIFIED))

    def test_extra_principal_keeps_emi_and_shortens_tenure(self):
        original = generate_repayment_schedule(self.value(
            LoanRepaymentStructure.INSTALLMENT,
            amortisation=LoanAmortisationMethod.EMI,
        ))
        shortened = generate_shortened_installment_schedule(
            RepaymentScheduleInput(
                repayment_structure=LoanRepaymentStructure.INSTALLMENT,
                amortisation_method=LoanAmortisationMethod.EMI,
                disbursed_on=date(2028, 2, 15),
                principal=Decimal("90000.00"),
                monthly_interest_rate=Decimal("1"),
                tenure_months=12,
            ),
            emi_payment=original.repayments[0].total_due,
        )

        self.assertLess(len(shortened.repayments), len(original.repayments))
        self.assertEqual(shortened.repayments[0].total_due, original.repayments[0].total_due)
        self.assertEqual(shortened.repayments[-1].closing_principal, Decimal("0.00"))
        self.assertEqual(sum(row.principal_due for row in shortened.repayments), Decimal("90000.00"))
