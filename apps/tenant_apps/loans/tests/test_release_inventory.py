from datetime import date
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.selectors.release_inventory import loan_release_inventory
from . import test_continuation_admissions as admissions


class ReleaseInventoryTests(admissions.AdmissionFixture):
    on = date(2026, 5, 6)

    def test_four_real_admissions_disclose_independent_evidence_without_writes(self):
        with self.scoped():
            before = list(m.PawnLoanEvent.objects.values_list("pk", "payload_fingerprint"))
            with CaptureQueriesContext(connection) as queries:
                report = loan_release_inventory(as_of_date=self.on)
            by_id = {r["loan_id"]: r for r in report["loans"]}
            self.assertEqual(set(by_id), {loan.pk for loan in self.loans})
            self.assertEqual(report["cohorts"]["calculation:SUPPORTED"], 4)
            self.assertEqual(report["census"]["ordinary_states"], {"ACTIVE": 4})
            for loan in self.loans:
                row = by_id[loan.pk]
                self.assertEqual(row["collection_due"], self.remaining + self.monthly)
                self.assertEqual(row["assessment"], "UNASSESSED")
                self.assertEqual(row["valuation"], "UNASSESSED")
                self.assertIn("REPAYMENT", row["servicing_prerequisites"])
            self.assertFalse(by_id[self.opening.pk]["transactions"]["complete"])
            self.assertFalse(by_id[self.opening.pk]["earlier_financial_history_available"])
            self.assertTrue(by_id[self.direct.pk]["earlier_financial_history_available"])
            self.assertFalse(report["action_authorization"])
            self.assertFalse(report["automatic_conversion"])
            self.assertFalse(report["staff_acceptance"])
            self.assertEqual(before, list(m.PawnLoanEvent.objects.values_list("pk", "payload_fingerprint")))
            self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT ", "UPDATE ", "DELETE ")) for q in queries))

    def test_unavailable_contract_is_counted_without_inventing_balance_or_aborting(self):
        from apps.tenant_apps.loans.selectors.continuation import resolve_loan_continuation
        def read(loan, **kwargs):
            if loan.pk == self.opening.pk:
                raise ValueError("Unsupported source checkpoint")
            return resolve_loan_continuation(loan, **kwargs)
        with self.scoped(), patch("apps.tenant_apps.loans.selectors.release_inventory.resolve_loan_continuation", side_effect=read):
            report = loan_release_inventory(as_of_date=self.on)
            row = next(r for r in report["loans"] if r["loan_id"] == self.opening.pk)
            self.assertEqual(report["cohorts"]["calculation:UNAVAILABLE"], 1)
            self.assertNotIn("collection_due", row)
            self.assertEqual(row["servicing_prerequisites"], {})

    def test_summary_matches_full_report_and_other_workspace_is_empty(self):
        with self.scoped():
            full = loan_release_inventory(as_of_date=self.on)
            summary = loan_release_inventory(as_of_date=self.on, summary_only=True)
            self.assertEqual(summary["cohorts"], full["cohorts"])
            self.assertEqual(summary["loans"], [])
        with self.scoped(self.b):
            report = loan_release_inventory(as_of_date=self.on)
            self.assertEqual(report["cohorts"], {})
            self.assertEqual(report["census"]["ordinary_states"], {})

    def test_pre_cutover_history_stays_unavailable_and_later_activity_is_guarded(self):
        with self.scoped():
            report = loan_release_inventory(as_of_date=self.original)
            rows = {r["loan_id"]: r for r in report["loans"]}
            self.assertEqual(rows[self.opening.pk]["calculation"], "UNAVAILABLE")
            self.assertNotIn("recorded_due", rows[self.opening.pk])
            blockers = rows[self.direct.pk]["servicing_prerequisites"]["REPAYMENT"]["blockers"]
            self.assertIn("LATER_ACTIVITY", blockers)

    def test_date_context_and_nested_operator_command_fail_closed(self):
        with self.assertRaises(ValueError):
            loan_release_inventory(as_of_date=self.on)
        with self.scoped():
            with self.assertRaises(ValueError):
                loan_release_inventory(as_of_date=date(9999, 1, 1))
            with self.assertRaisesMessage(CommandError, "outside an existing transaction"):
                call_command("check_loan_release_inventory", workspace_id=self.a.pk, stdout=StringIO())
