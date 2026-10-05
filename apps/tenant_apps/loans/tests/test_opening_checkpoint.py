"""Synthetic checkpoint examples, not customer/source-book attestations."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.test import SimpleTestCase, override_settings

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.domain.monthly_contract import RULE, charge_count, period_dates, item_monthly_interest
from apps.tenant_apps.loans.services import opening_checkpoint as checkpoint_contract
from apps.tenant_apps.loans.services.opening_validation import validate_opening
from apps.tenant_apps.loans.services.opening_policy_interest import calculation
from apps.tenant_apps.loans.services.opening_import import preview_opening_import
from apps.tenant_apps.loans.services.opening_export import export_opening
from apps.tenant_apps.loans.services.opening_restore import parse_opening_export, semantic_evidence
from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full
from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
from apps.tenant_apps.loans.selectors.servicing_contract import resolve_servicing_contract, get_servicing_position
from . import test_opening_import as imports, test_opening_restore as restores
from .test_shared_monthly_contract import policy_review


def balance_values(loan, day):
    from apps.tenant_apps.loans.services.history_contract import decimal
    loan.refresh_from_db()
    balance = get_servicing_position(loan, as_of_date=day, operation="NOTICE").balance
    return dict(principal=decimal(balance.principal_outstanding), interest=decimal(balance.interest_outstanding),
                fees=decimal(balance.fees_outstanding))


def checkpoint(review=None, *, original=date(2021, 1, 1), cutover=date(2021, 2, 20),
               original_principal="1000", remaining="800", current_base="900", rate="1", quantum="0.01",
               recognized="9", unpaid="5", current_recognized="9", current_unpaid="5", advances=()):
    doc = deepcopy(review) if review else policy_review(original, cutover, rate, quantum)
    original = date.fromisoformat(doc["terms"]["original_date"])
    doc["profile"] = checkpoint_contract.PROFILE
    doc["terms"].update(rule_id=RULE, interest_basis="OUTSTANDING_AT_PERIOD_START", partial_rule="FULL_MONTH",
                        rounding_scope="PER_ITEM", rounding_mode="HALF_UP", interest_quantum=quantum)
    doc["cutover"]["date"] = cutover.isoformat()
    item = doc["collateral"][0]
    item.update(original_principal=original_principal, remaining_principal=remaining, monthly_rate=rate)
    if item["valuation"].get("date"):
        item["valuation"]["date"] = cutover.isoformat()
    doc["balances"].update(principal=remaining, interest=unpaid)
    doc["obligations"][0].update(principal=remaining, interest=str(Decimal(unpaid) + 100), recognized_interest=unpaid)
    number = charge_count(original, cutover) + 1
    start, end = period_dates(original, number)
    doc["continuation"] = dict(covered_through=cutover.isoformat(), additional_months=number - 1,
        period_number=number, period_start=start.isoformat(), period_end=end.isoformat(),
        bases=[dict(item_id=item["id"], principal_base=current_base)],
        expected_period_interest=str(item_monthly_interest(current_base, rate, quantum)),
        recognized_interest=recognized, recognized_unpaid_interest=unpaid,
        current_period_recognized_interest=current_recognized, current_period_unpaid_interest=current_unpaid,
        advance_coverage=[dict(period_number=n, interest=amount, evidence_reference="Synthetic verified advance")
                        for n, amount in advances],
        next_increase_on=(end + timedelta(days=1)).isoformat(), evidence_reference="Synthetic verified cutover")
    return doc


class OpeningCheckpointMathTests(SimpleTestCase):
    def test_zero_principal_checkpoint_is_explicitly_held_before_writer_arithmetic(self):
        doc = checkpoint(remaining="0")
        result = validate_opening(doc)
        self.assertFalse(result["document_reconciled"])
        self.assertTrue(any(row["field"] == "balances.principal" and row["code"] == "AMOUNT_RANGE"
                            for row in result["issues"]))

    def test_owner_january_example_reduces_charge_base_from_february_second(self):
        # Owner supplied dates/principal: 10,000 on 1 Jan, 1,000 principal paid
        # on 20 Jan. For this arithmetic example ONLY, assume a 2% rate and
        # evidenced first-month advance of 200; these were not source-book facts.
        doc = checkpoint(original=date(2026, 1, 1), cutover=date(2026, 1, 20),
            original_principal="10000", remaining="9000", current_base="10000", rate="2",
            recognized="0", unpaid="0", current_recognized="0", current_unpaid="0", advances=[(1, "200")])
        self.assertTrue(validate_opening(doc)["document_reconciled"], validate_opening(doc))
        self.assertEqual(Decimal(calculation(doc, date(2026, 2, 1))["additional_interest"]), 0)
        self.assertEqual(Decimal(calculation(doc, date(2026, 2, 2))["additional_interest"]), 180)
        doc = checkpoint(original=date(2026, 1, 1), cutover=date(2026, 2, 2),
            original_principal="10000", remaining="9000", current_base="9000", rate="2",
            recognized="180", unpaid="180", current_recognized="180", current_unpaid="180")
        self.assertTrue(validate_opening(doc)["document_reconciled"], validate_opening(doc))
        self.assertEqual(Decimal(calculation(doc, date(2026, 2, 2))["additional_interest"]), 180)

    def test_checkpoint_explanation_does_not_claim_fake_upfront_or_old_rounding(self):
        from django.template.loader import render_to_string
        from apps.tenant_apps.loans.services.opening_continuation import opening_interest_breakdown
        doc = checkpoint()
        text = render_to_string("loans/pawn/_opening_interest_breakdown.html",
            dict(opening_review=doc, opening_interest_breakdown=opening_interest_breakdown(doc, as_of_date=date(2021, 3, 2)),
                 today=date(2021, 3, 2)))
        self.assertIn("Earlier transactions are unavailable", text)
        self.assertIn("saved rounding policy", text)
        self.assertNotIn("First month paid upfront", text)
        self.assertNotIn("rounded once to whole rupees", text)

    def test_published_v3_row_contract_is_frozen_and_keeps_previous_rows(self):
        import json
        from pathlib import Path
        from django.conf import settings
        from apps.tenant_apps.loans.services.opening_contract import CHECKPOINT_PROFILE, ROW_FIELDS_V2
        from apps.tenant_apps.loans.services.history_contract import dump
        published = json.loads((Path(settings.BASE_DIR) / "docs/contracts/loan-opening-export-v3-rows.json").read_text())
        self.assertEqual(published, json.loads(dump(dict(profile=CHECKPOINT_PROFILE, fields=ROW_FIELDS_V2))))

    def test_reduced_principal_continues_without_reconstructing_earlier_receipts(self):
        doc = checkpoint()
        self.assertTrue(validate_opening(doc)["document_reconciled"], validate_opening(doc))
        self.assertEqual(Decimal(calculation(doc, date(2021, 3, 1))["additional_interest"]), 9)
        self.assertEqual(Decimal(calculation(doc, date(2021, 3, 2))["additional_interest"]), 17)

    def test_upfront_april_anniversary_for_reduced_balance(self):
        doc = checkpoint(original=date(2021, 4, 5), cutover=date(2021, 5, 5), original_principal="10000",
            remaining="8000", current_base="10000", rate="2", recognized="0", unpaid="0",
            current_recognized="0", current_unpaid="0", advances=[(1, "200")])
        self.assertTrue(validate_opening(doc)["document_reconciled"], validate_opening(doc))
        self.assertEqual(Decimal(calculation(doc, date(2021, 5, 5))["additional_interest"]), 0)
        self.assertEqual(Decimal(calculation(doc, date(2021, 5, 6))["additional_interest"]), 160)

    def test_first_new_charge_day_preserves_current_base_until_next_anniversary(self):
        doc = checkpoint(original=date(2021, 4, 5), cutover=date(2021, 5, 6), original_principal="10000",
            remaining="7000", current_base="8000", rate="2", recognized="160", unpaid="160",
            current_recognized="160", current_unpaid="160")
        self.assertTrue(validate_opening(doc)["document_reconciled"], validate_opening(doc))
        self.assertEqual(Decimal(calculation(doc, date(2021, 6, 5))["additional_interest"]), 160)
        self.assertEqual(Decimal(calculation(doc, date(2021, 6, 6))["additional_interest"]), 300)

    def test_current_and_future_advance_are_not_recognized_twice(self):
        doc = checkpoint(recognized="0", unpaid="0", current_recognized="0", current_unpaid="0",
                         advances=[(2, "9"), (3, "8")])
        self.assertTrue(validate_opening(doc)["document_reconciled"], validate_opening(doc))
        self.assertEqual(Decimal(calculation(doc, date(2021, 3, 2))["additional_interest"]), 0)
        self.assertEqual(Decimal(calculation(doc, date(2021, 4, 2))["additional_interest"]), 8)

    def test_recognized_and_unpaid_are_distinct_explicit_source_facts(self):
        doc = checkpoint(recognized="73.50", unpaid="15")
        self.assertTrue(validate_opening(doc)["document_reconciled"], validate_opening(doc))
        self.assertEqual(Decimal(calculation(doc, date(2021, 3, 2))["additional_interest"]), Decimal("81.50"))
        with self.assertRaisesMessage(ValueError, "before the opening checkpoint"):
            calculation(doc, date(2021, 2, 19))

    def test_missing_inconsistent_or_guessed_checkpoint_is_held(self):
        for field, value in (("bases", None), ("recognized_interest", None),
                ("current_period_unpaid_interest", None), ("advance_coverage", None),
                ("expected_period_interest", "8"), ("next_increase_on", "2021-03-01"),
                ("recognized_unpaid_interest", "6"), ("current_period_recognized_interest", "8"),
                ("period_number", 3), ("bases", [dict(item_id="unknown", principal_base="900")])):
            doc = checkpoint()
            doc["continuation"][field] = value
            with self.subTest(field=field):
                self.assertFalse(validate_opening(doc)["document_reconciled"])
        doc = checkpoint(current_base="700", recognized="7", current_recognized="7")
        self.assertFalse(validate_opening(doc)["document_reconciled"])

    def test_over_coverage_duplicates_and_past_advances_are_held(self):
        for advances in ([(2, "10")], [(3, "9")], [(3, "8"), (3, "8")], [(1, "1")]):
            with self.subTest(advances=advances):
                self.assertFalse(validate_opening(checkpoint(advances=advances))["document_reconciled"])

    def test_short_month_and_whole_rupee_policy_preserve_original_anchor(self):
        doc = checkpoint(original=date(2024, 1, 31), cutover=date(2024, 2, 29), current_base="1000",
            rate="1.05", quantum="1", recognized="0", unpaid="0", current_recognized="0", current_unpaid="0",
            advances=[(1, "11")])
        self.assertTrue(validate_opening(doc)["document_reconciled"], validate_opening(doc))
        result = calculation(doc, date(2024, 3, 1))
        self.assertEqual(Decimal(result["additional_interest"]), 8)
        self.assertEqual(result["next_increase_on"], "2024-04-01")


class OpeningCheckpointTests(imports.OpeningImportFixture):
    restore = restores.OpeningRestoreTests.restore

    def setUp(self):
        super().setUp()
        from apps.tenant_apps.data_portability.models import SourceIdentity
        from apps.tenant_apps.loans.services.license_series import create_license
        with self.scoped(self.b):
            system = self.review["mapping"]["borrower_source_system"]
            self.commit(self.ready(self.stage(workspace=self.b, system=system), workspace=self.b), workspace=self.b)
            identity = SourceIdentity.objects.get(external_id="old-1")
            licence = create_license(workspace=self.b, actor=self.actor, name="Restore", license_number="OLD-L",
                issued_on=date(2020, 1, 1), expires_on=date(2022, 1, 1))
            series = m.LoanSeries.objects.create(license=licence, name="Restore", code="R")
            product = m.LoanProduct.objects.create(workspace=self.b, code="R", name="Restore")
            version = m.LoanProductVersion.objects.create(product=product, version=1, status="RETIRED",
                repayment_structure="FLEXIBLE_PARTIAL_PAYMENT", amortisation_method="NONE", payment_frequency="FLEXIBLE",
                extra_payment_rule="REDUCE_PRINCIPAL", maximum_tenor_months=12, operational_grace_days=3,
                calculation_contract_version=RULE)
            self.mapping = dict(borrower_id=identity.identity.party_id, revision_id=licence.revisions.get().pk,
                                series_id=series.pk, product_version_id=version.pk)
            m.LoanNumberSequence.objects.create(series=series, document_kind="PAWN_LOAN_RELEASE",
                prefix="R-", width=5, maximum_number=10000)
        self.restore_args = dict(workspace_id=self.b.pk, actor=self.actor, mapping=self.mapping)
        self.review.update(checkpoint(self.review))
        self.setup["policy"]["policy_version"] = 2
        self.setup["policy"]["minimum_first_month"] = False
        for workspace, key in ((self.a, self.review["mapping"]["product_version_id"]),
                               (self.b, self.mapping["product_version_id"])):
            with self.scoped(workspace):
                m.LoanProductVersion.objects.filter(pk=key).update(calculation_contract_version=RULE)

    def test_preview_replay_original_maturity_and_single_truthful_origin(self):
        with self.scoped():
            preview_opening_import(**self.args)
            self.assertFalse(m.PawnLoan.objects.exists())
            origin = self.write()
            self.assertEqual(self.write().pk, origin.pk)
            self.assertEqual(origin.loan.principal_amount, 800)
            self.assertEqual(origin.loan.loan_date, date(2021, 1, 1))
            self.assertEqual(origin.loan.repayment_schedules.get().maturity_date, date(2021, 4, 1))
            self.assertEqual(balance_values(origin.loan, date(2021, 2, 20)),
                             dict(principal="800", interest="5", fees="0"))
            self.assertEqual(list(origin.loan.loan_events.values_list("event_kind", flat=True)), ["MIGRATION_OPENING"])
            self.assertFalse(m.PawnLoanApprovalSnapshot.objects.exists())
            self.assertFalse(m.PawnLoanDisbursalSnapshot.objects.exists())
            contract = resolve_servicing_contract(origin.loan, as_of_date=date(2021, 2, 20))
            self.assertEqual(contract.checkpoint_period_number, 2)
            self.assertEqual(contract.checkpoint_current_recognized_interest, 9)
            self.assertEqual(contract.checkpoint_next_increase_on, date(2021, 3, 2))

    def test_midperiod_payment_retry_and_reversal_restore_checkpoint(self):
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 21)):
            origin = self.write()
            args = dict(amount=205, request_key="partial", actor=self.actor)
            payment = record_pawn_loan_repayment(origin.loan_id, **args)
            self.assertEqual((payment.allocation.interest, payment.allocation.principal), (5, 200))
            self.assertEqual(record_pawn_loan_repayment(origin.loan_id, **args).loan_event.pk, payment.loan_event.pk)
            self.assertEqual(balance_values(origin.loan, date(2021, 3, 1))["interest"], "0")
            self.assertEqual(balance_values(origin.loan, date(2021, 3, 2)), dict(principal="600", interest="6", fees="0"))
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 3, 3)):
            reverse_pawn_loan_event(payment.loan_event.pk, actor=self.actor, reason="Cancelled")
            self.assertEqual(balance_values(origin.loan, date(2021, 3, 3)), dict(principal="800", interest="13", fees="0"))
            from apps.tenant_apps.loans.selectors import get_pawn_loan_exposure
            self.assertEqual(get_pawn_loan_exposure(origin.loan_id, as_of_date=date(2021, 2, 22)).total_economic_exposure, 600)
            self.assertEqual(get_pawn_loan_exposure(origin.loan_id, as_of_date=date(2021, 3, 3)).total_economic_exposure, 813)

    def test_charge_day_payment_and_coupled_accrual_reverse(self):
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 3, 2)):
            origin = self.write()
            payment = record_pawn_loan_repayment(origin.loan_id, amount=213, request_key="charged", actor=self.actor)
            self.assertEqual((payment.allocation.interest, payment.allocation.principal), (13, 200))
            self.assertEqual(balance_values(origin.loan, date(2021, 4, 2)), dict(principal="600", interest="6", fees="0"))
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 3, 3)):
            reverse_pawn_loan_event(payment.loan_event.pk, actor=self.actor, reason="Cancelled")
            self.assertEqual(balance_values(origin.loan, date(2021, 3, 3)), dict(principal="800", interest="13", fees="0"))

    def test_future_advance_conflict_blocks_payment_without_invented_refund(self):
        self.review.update(checkpoint(self.review, recognized="0", unpaid="0", current_recognized="0",
            current_unpaid="0", advances=[(2, "9"), (3, "8")]))
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 21)):
            origin = self.write()
            with self.assertRaisesMessage(ValueError, "future advance exceeds"):
                record_pawn_loan_repayment(origin.loan_id, amount=200, request_key="overcoverage", actor=self.actor)
            self.assertEqual(origin.loan.loan_events.count(), 1)

    def test_release_and_reverse_preserve_checkpoint_and_remaining_interest(self):
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 3, 2)):
            origin = self.write()
            released = release_pawn_loan_in_full(origin.loan_id, settlement_amount=813, request_key="release", actor=self.actor)
            self.assertEqual(balance_values(origin.loan, date(2021, 3, 2))["principal"], "0")
            reverse_pawn_loan_event(released.loan_event.pk, actor=self.actor, reason="Cancelled")
            self.assertEqual(balance_values(origin.loan, date(2021, 3, 2)), dict(principal="800", interest="13", fees="0"))

    def test_paid_checkpoint_export_restore_and_future_continuation(self):
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 21)):
            origin = self.write()
            record_pawn_loan_repayment(origin.loan_id, amount=205, request_key="partial", actor=self.actor)
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 3, 2)):
            content = export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
        source = parse_opening_export(content)
        self.assertEqual(source["manifest"]["profile"], "loan-opening-export/3")
        with self.scoped(self.b), patch("django.utils.timezone.localdate", return_value=date(2021, 3, 2)):
            restored, _ = self.restore(content)
            self.assertEqual(balance_values(restored.loan, date(2021, 4, 2)), dict(principal="600", interest="12", fees="0"))
            again = parse_opening_export(export_opening(workspace_id=self.b.pk, actor=self.actor, loan_id=restored.loan_id))
            self.assertEqual(semantic_evidence(source["evidence"]), semantic_evidence(again["evidence"]))

    def test_unserviced_checkpoint_export_uses_new_profile(self):
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 20)):
            origin = self.write()
            content = export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
        source = parse_opening_export(content)
        self.assertEqual(source["manifest"]["profile"], "loan-opening-export/3")
        self.assertEqual(source["evidence"]["repayment_lines"], [])
        with self.scoped(self.b), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 20)):
            restored, _ = self.restore(content)
            self.assertEqual(balance_values(restored.loan, date(2021, 3, 2))["interest"], "13")

    def test_unknown_checkpoint_and_wrong_policy_cannot_write(self):
        with self.scoped():
            self.review["continuation"]["current_period_unpaid_interest"] = None
            with self.assertRaises(ValueError):
                self.write()
            self.assertFalse(m.PawnLoan.objects.exists())
            self.review["continuation"]["current_period_unpaid_interest"] = "5"
            changed = deepcopy(self.setup)
            changed["policy"]["currency_quantum"] = "1"
            with self.assertRaises(ValueError):
                self.write(setup=changed)
            self.assertFalse(m.PawnLoan.objects.exists())
            with self.assertRaises(PermissionDenied):
                self.write(actor=None)

    def test_remaining_principal_in_paise_is_preserved_under_whole_rupee_interest(self):
        self.review.update(checkpoint(self.review, remaining="800.25", current_base="900.25", quantum="1",
                                     recognized="9", current_recognized="9"))
        self.setup["policy"]["currency_quantum"] = "1"
        with self.scoped():
            origin = self.write()
            self.assertEqual(origin.loan.principal_amount, Decimal("800.25"))
            self.assertEqual(balance_values(origin.loan, date(2021, 3, 2)),
                             dict(principal="800.25", interest="13", fees="0"))

    def test_mixed_origin_raw_dml_is_rejected_in_both_orders_under_restricted_role(self):
        from apps.tenant_apps.loans.services.event_recording import _persist_locked_event
        with self.scoped():
            origin = self.write()
            other = m.PawnLoan.objects.create(workspace=self.a, borrower=origin.loan.borrower,
                license=origin.loan.license, license_revision=origin.loan.license_revision, series=origin.loan.series,
                product_version=origin.loan.product_version, loan_number="OTHER-NATIVE", principal_amount=800,
                loan_date=date(2021, 1, 1), monthly_interest_rate=1, tenure_months=3)
            _persist_locked_event(other, kind="DISBURSAL", effective_date=date(2021, 1, 1),
                payload={"values": {"principal": "800"}}, actor=self.actor)
        role = connection.ops.quote_name("ld04_checkpoint_restricted")
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {role}")
            with self.scoped():
                for kind in ("DISBURSAL", "RENEWAL_OPENING"):
                    with self.subTest(kind=kind), self.assertRaisesMessage(DatabaseError, "cannot coexist"), transaction.atomic():
                        _persist_locked_event(origin.loan, kind=kind, effective_date=date(2021, 2, 20),
                            payload={"values": {"principal": "800"}}, actor=self.actor)
                with self.assertRaisesMessage(DatabaseError, "cannot coexist"), transaction.atomic():
                    _persist_locked_event(other, kind="MIGRATION_OPENING", effective_date=date(2021, 2, 20),
                        payload={"values": {"principal": "800", "interest": "5"}}, actor=self.actor)
                with self.assertRaises(DatabaseError), transaction.atomic():
                    m.PawnLoanEvent.objects.filter(loan=origin.loan).update(payload={})
                self.assertEqual(origin.loan.loan_events.count(), 1)
            with self.scoped(self.b):
                self.assertFalse(m.PawnLoan.objects.filter(pk=origin.loan_id).exists())
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    def test_multiple_rates_and_item_rounding_survive_payment_and_next_period(self):
        first = self.review["collateral"][0]
        first.update(original_principal="500", remaining_principal="400", monthly_rate="1.05")
        second = deepcopy(first)
        second.update(id="second", monthly_rate="2.05")
        self.review["collateral"].append(second)
        self.review["source"]["item_ids"].append("second")
        self.review["terms"]["interest_quantum"] = "1"
        self.setup["policy"]["currency_quantum"] = "1"
        carry = self.review["continuation"]
        carry.update(bases=[dict(item_id=first["id"], principal_base="450"),
                           dict(item_id=second["id"], principal_base="450")],
            expected_period_interest="14", recognized_interest="14", current_period_recognized_interest="14")
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 21)):
            origin = self.write()
            payment = record_pawn_loan_repayment(origin.loan_id, amount=205, request_key="items", actor=self.actor)
            self.assertEqual(payment.item_allocations[0].monthly_interest_rate, Decimal("2.05"))
            self.assertEqual(payment.item_allocations[0].principal_applied, 200)
            # Current period used 450 each; next period uses 400 and 200: 4 + 4.
            self.assertEqual(balance_values(origin.loan, date(2021, 3, 2)), dict(principal="600", interest="8", fees="0"))

    def test_completed_paper_receipt_has_actual_date_and_round_trips(self):
        from apps.tenant_apps.loans.services import paper_repayments as paper
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 3, 2)):
            origin = self.write()
            args = dict(amount="205", received_on=date(2021, 2, 21), receipt_reference="Paper 17",
                        request_key="paper-checkpoint", actor=self.actor)
            preview = paper.preview_paper_repayment(origin.loan_id, **args)
            payment = paper.record_paper_repayment(origin.loan_id, **args,
                review_token=preview.review_token, confirmed_received=True)
            self.assertEqual(payment.loan_event.effective_date, date(2021, 2, 21))
            content = export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
        with self.scoped(self.b), patch("django.utils.timezone.localdate", return_value=date(2021, 3, 2)):
            restored, _ = self.restore(content)
            self.assertEqual(balance_values(restored.loan, date(2021, 3, 2)), dict(principal="600", interest="6", fees="0"))

    def test_old_export_profile_cannot_relabel_checkpoint(self):
        from apps.tenant_apps.loans.services.history_contract import dump
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 20)):
            origin = self.write()
            source = parse_opening_export(export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id))
        source["manifest"]["profile"] = "loan-opening-export/2"
        content = (dump(source["manifest"]) + "\n" + dump(source["evidence"]) + "\n").encode()
        with self.assertRaisesMessage(ValueError, "Checkpoint review requires"):
            parse_opening_export(content)

    @override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_exact_recovery_preserves_checkpoint_rows_and_new_guard_fingerprint(self):
        import hashlib
        from apps.tenant_apps.loans.services import pawn_recovery as recovery
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 3, 2)):
            origin = self.write()
            record_pawn_loan_repayment(origin.loan_id, amount=213, request_key="recovery", actor=self.actor)
            content = recovery.export_archive(workspace=self.a, actor=self.actor)
            sha = hashlib.sha256(content).hexdigest()
            source = recovery._read(content, sha)[0]
            self.assertTrue(connection.settings_dict["NAME"].startswith("test_"))
            connection.check_constraints()
            with connection.cursor() as cursor:
                # Admission/export above use the fixture's restricted runtime
                # role. Exact recovery is explicitly an offline owner operation.
                cursor.execute("RESET ROLE")
                for model in recovery._models():
                    cursor.execute(f'ALTER TABLE "{model._meta.db_table}" DISABLE TRIGGER USER')
                for model in reversed(recovery._models()):
                    cursor.execute(f'DELETE FROM "{model._meta.db_table}" WHERE workspace_id=%s', [self.a.pk])
                connection.check_constraints()
                for model in recovery._models():
                    cursor.execute(f'ALTER TABLE "{model._meta.db_table}" ENABLE TRIGGER USER')
            result = recovery.restore_archive(workspace=self.a, actor=self.actor,
                content=content, expected_sha256=sha, commit=True)
            self.assertTrue(result["committed"])
            again_content = recovery.export_archive(workspace=self.a, actor=self.actor)
            again = recovery._read(again_content, hashlib.sha256(again_content).hexdigest())[0]
            for key in ("tables", "files", "reconciliation", "prerequisites", "schema", "guards_sha256"):
                self.assertEqual(source[key], again[key], key)
            self.assertEqual(balance_values(origin.loan, date(2021, 4, 2)),
                             dict(principal="600", interest="6", fees="0"))
