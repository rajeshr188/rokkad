import copy
import json
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, transaction
from django.core.management import call_command, CommandError

from apps.orgs.audit import AuditLog
from apps.tenant_apps.data_portability.models import SourceIdentity
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.history_contract import HistoryError, digest, dump
from apps.tenant_apps.loans.services.license_series import create_license
from apps.tenant_apps.loans.services.opening_export import export_opening
from apps.tenant_apps.loans.services.opening_restore import (
    parse_opening_export, preview_opening_restore, commit_opening_restore, semantic_evidence,
)
from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full
from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
from apps.tenant_apps.loans.services.history_import import balance_values
from apps.tenant_apps.loans.tests.test_opening_import import OpeningImportFixture


class OpeningRestoreTests(OpeningImportFixture):
    def test_mixed_item_rates_allocate_highest_first_and_restore_every_line(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        from apps.tenant_apps.loans.selectors import get_pawn_loan_exposure
        self.review["collateral"][0].update(original_principal="500", remaining_principal="500")
        second = copy.deepcopy(self.review["collateral"][0])
        second.update(id="second-item", monthly_rate="2")
        self.review["collateral"].append(second)
        self.review["source"]["item_ids"].append("second-item")
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 2)):
            origin = self.write()
            first = record_pawn_loan_repayment(origin.loan_id, amount=215, request_key="partial", actor=self.actor)
            self.assertEqual([(r.monthly_interest_rate, r.principal_applied) for r in first.item_allocations], [(2, 200), (1, 0)])
            self.assertEqual(get_pawn_loan_exposure(origin.loan_id, as_of_date=date(2021, 3, 2)).total_economic_exposure, 811)
            record_pawn_loan_repayment(origin.loan_id, amount=300, request_key="second", actor=self.actor)
            self.assertEqual(get_pawn_loan_exposure(origin.loan_id, as_of_date=date(2021, 3, 2)).total_economic_exposure, 505)
            content = export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
        with self.scoped(self.b):
            restored, _ = self.restore(content)
            self.assertEqual(m.PawnLoanRepaymentAllocationLine.objects.count(), 4)

    def test_payment_export_restore_reconciles_allocations_and_later_release(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        from apps.tenant_apps.loans.services.pawn_release import preview_pawn_loan_full_release
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 2)):
            origin = self.write()
            record_pawn_loan_repayment(origin.loan_id, amount=210, request_key="partial", actor=self.actor)
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 3, 2)):
            record_pawn_loan_repayment(origin.loan_id, amount=8, request_key="interest", actor=self.actor)
            content = export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
        source = parse_opening_export(content)
        self.assertEqual(source["manifest"]["profile"], "loan-opening-export/2")
        self.assertEqual(len(source["evidence"]["repayment_lines"]), 1)
        with self.scoped(self.b), patch("django.utils.timezone.localdate", return_value=date(2021, 3, 2)):
            restored, _ = self.restore(content)
            self.assertEqual(m.PawnLoanRepaymentAllocationLine.objects.get().principal_applied, 200)
            self.assertEqual(preview_pawn_loan_full_release(restored.loan_id).minimum_settlement, 800)
            again = parse_opening_export(export_opening(workspace_id=self.b.pk, actor=self.actor, loan_id=restored.loan_id))
            self.assertEqual(semantic_evidence(source["evidence"]), semantic_evidence(again["evidence"]))

    def test_reversed_payment_and_release_round_trip(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 2)):
            origin = self.write()
            payment = record_pawn_loan_repayment(origin.loan_id, amount=210, request_key="wrong", actor=self.actor)
            reverse_pawn_loan_event(payment.loan_event.pk, actor=self.actor, reason="Correct collection")
            record_pawn_loan_repayment(origin.loan_id, amount=110, request_key="right", actor=self.actor)
            release_pawn_loan_in_full(origin.loan_id, settlement_amount=900, request_key="release", actor=self.actor)
            content = export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
        with self.scoped(self.b):
            restored, _ = self.restore(content)
            self.assertEqual(restored.loan.state, "CLOSED")

    def test_fully_paid_but_held_opening_round_trip(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 2)):
            origin = self.write()
            record_pawn_loan_repayment(origin.loan_id, amount=1010, request_key="paid", actor=self.actor)
            content = export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
        with self.scoped(self.b):
            restored, _ = self.restore(content)
            self.assertEqual(restored.loan.state, "ACTIVE")
            self.assertEqual(restored.loan.collateral_items.get().custody_state, "IN_VAULT")

    def test_payment_allocation_tamper_rolls_back_restore(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 2)):
            origin = self.write()
            record_pawn_loan_repayment(origin.loan_id, amount=210, request_key="partial", actor=self.actor)
            content = export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
        manifest, evidence = [json.loads(row) for row in content.splitlines()]
        evidence["repayment_lines"][0]["principal_applied"] = "201"
        manifest["sha256"] = digest(evidence)
        tampered = (dump(manifest) + "\n" + dump(evidence) + "\n").encode()
        with self.scoped(self.b):
            with self.assertRaises(HistoryError):
                self.restore(tampered)
            self.assertFalse(m.PawnLoan.objects.exists())

    def restore_frozen_v1(self, name):
        from .test_opening_contract import FIXTURES
        content = (FIXTURES / f"opening-export-v1-{name}.jsonl").read_bytes()
        source = parse_opening_export(content)
        with self.scoped(self.b):
            origin, _ = self.restore(content)
            with patch("django.utils.timezone.localdate", return_value=date.fromisoformat(source["manifest"]["as_of"])):
                restored = parse_opening_export(export_opening(
                    workspace_id=self.b.pk, actor=self.actor, loan_id=origin.loan_id))
            self.assertEqual(semantic_evidence(restored["evidence"]), semantic_evidence(source["evidence"]))
            self.assertEqual(origin.references["restore"]["document"], source)

    def test_frozen_v1_active_export_restores_unknown_evidence(self):
        self.legacy_gaps()
        self.restore_frozen_v1("active")

    def test_frozen_v1_servicing_export_restores_release_reversal_and_concession(self):
        self.restore_frozen_v1("servicing")

    def legacy_gaps(self):
        from apps.tenant_apps.loans.services.license_series import create_legacy_license_reference
        self.review["collateral"][0]["valuation"] = {"status": "UNVERIFIED", "source_amount": "2345",
            "source_date": None, "evidence_reference": "Owner confirms old undated value"}
        self.setup["legacy_license_evidence"] = "Owner confirms source was a grouping without validity"
        for workspace in (self.a, self.b):
            with self.scoped(workspace):
                license = create_legacy_license_reference(workspace=workspace, actor=self.actor,
                    name="Old source group", source_label="OLD-GROUP", evidence_reference=self.setup["legacy_license_evidence"])
                series = m.LoanSeries.objects.create(license=license, name="Legacy series", code="LG")
                m.LoanNumberSequence.objects.create(series=series, document_kind="PAWN_LOAN_RELEASE",
                    prefix="LG-", width=5, maximum_number=10000)
                if workspace == self.a:
                    self.review["mapping"].update(licence_revision_id=license.revisions.get().pk, series_id=series.pk)
                    self.setup["source_license_number"] = "OLD-GROUP"
                else:
                    self.mapping.update(revision_id=license.revisions.get().pk, series_id=series.pk)

    def test_unverified_values_and_legacy_reference_release_reverse_export_restore(self):
        self.legacy_gaps()
        self.check_round_trip("released_again")
        with self.scoped(self.b):
            loan = m.PawnLoan.objects.get()
            self.assertTrue(loan.license.is_legacy_reference)
            self.assertIsNone(loan.license.expires_on)
            self.assertFalse(m.CollateralAppraisal.objects.exists())
            self.assertEqual(loan.state, "CLOSED")

    def test_first_appraisal_after_unknown_opening_is_restored_and_ltv_stays_unknown_before_it(self):
        from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
        self.legacy_gaps()
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 2)):
            origin = self.write()
            value = get_pawn_loan_collateral_valuation(origin.loan_id, as_of_date=date(2021, 1, 21))
            self.assertIsNone(value.eligible_collateral_value)
            self.assertIsNone(value.items[0].appraisal_value)
            self.assertIn("MISSING_APPRAISAL", value.items[0].blockers)
            m.CollateralAppraisal.objects.create(workspace=self.a, collateral_item=origin.loan.collateral_items.get(),
                version=1, effective_at=datetime(2021, 1, 25, tzinfo=dt_timezone.utc), appraised_value=3000,
                method="STAFF_REVIEW", evidence_reference="Actual later dated assessment", created_by=self.actor)
            content = export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
        with self.scoped(self.b):
            self.restore(content)
            self.assertEqual(m.CollateralAppraisal.objects.get().appraised_value, Decimal("3000"))

    def setUp(self):
        super().setUp()
        with self.scoped(self.b):
            self.commit(self.ready(self.stage(workspace=self.b, system=self.review["mapping"]["borrower_source_system"]), workspace=self.b), workspace=self.b)
            identity = SourceIdentity.objects.get(external_id="old-1")
            licence = create_license(workspace=self.b, actor=self.actor, name="Restore", license_number="OLD-L",
                issued_on=date(2020, 1, 1), expires_on=date(2022, 1, 1))
            series = m.LoanSeries.objects.create(license=licence, name="Restore", code="R")
            product = m.LoanProduct.objects.create(workspace=self.b, code="R", name="Restore")
            version = m.LoanProductVersion.objects.create(product=product, version=1, status="RETIRED",
                repayment_structure="FLEXIBLE_PARTIAL_PAYMENT", amortisation_method="NONE", payment_frequency="FLEXIBLE",
                extra_payment_rule="REDUCE_PRINCIPAL", maximum_tenor_months=12, operational_grace_days=3,
                calculation_contract_version=self.review["terms"]["rule_id"])
            self.mapping = dict(borrower_id=identity.identity.party_id, revision_id=licence.revisions.get().pk,
                series_id=series.pk, product_version_id=version.pk)
            self.counter = m.LoanNumberSequence.objects.create(series=series, document_kind="PAWN_LOAN_RELEASE",
                prefix="R-", width=5, maximum_number=10000)
        self.restore_args = dict(workspace_id=self.b.pk, actor=self.actor, mapping=self.mapping)

    def source(self, state="opening"):
        day = date(2021, 1, 21) if state == "covered" else date(2021, 2, 2)
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=day):
            origin = self.write()
            if state != "opening":
                release = release_pawn_loan_in_full(origin.loan_id, settlement_amount=1000 if state == "covered" else 1005,
                    interest_concession=0 if state == "covered" else 5,
                    concession_reason="" if state == "covered" else "Accepted shortfall", request_key="first", actor=self.actor)
                if state in {"reversed", "released_again"}:
                    reverse_pawn_loan_event(release.loan_event.pk, actor=self.actor, reason="Cancelled return")
                if state == "released_again":
                    release_pawn_loan_in_full(origin.loan_id, settlement_amount=1010, request_key="second", actor=self.actor)
            return export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)

    def restore(self, content):
        preview = preview_opening_restore(**self.restore_args, content=content)
        self.assertFalse(m.PawnLoan.objects.exists())
        self.assertFalse(m.PawnLoanEvent.objects.exists())
        return commit_opening_restore(**self.restore_args, content=content, expected_sha256=preview["sha256"], confirmed=True)

    def test_current_rate_based_first_appraisal_preserves_source_quote_on_restore(self):
        from apps.tenant_apps.rates.models import Rate, RateSource
        from apps.tenant_apps.loans.services.collateral_reappraisal import record_collateral_reappraisal
        self.legacy_gaps()
        self.review["collateral"][0]["metal"] = "GOLD"
        with self.scoped():
            origin = self.write()
            m.LoanMonitoringPolicy.objects.create(workspace=self.a, version=1,
                effective_from=date(2021, 1, 1), compliance_profile="test",
                ltv_warning_ratio=Decimal("0.75"), ltv_breach_ratio=Decimal("0.8"),
                ltv_critical_ratio=Decimal("1"), eligible_custody_states=["IN_VAULT"],
                severity_mapping={"strategy": "derived-v1"})
            source = RateSource.objects.create(workspace=self.a, name="Reviewed business rate", location="Test")
            item = origin.loan.collateral_items.get()
            rate = Rate.objects.create(workspace=self.a, rate_source=source, metal=item.metal.title(),
                buying_rate=Decimal("15500"), selling_rate=Decimal("15500"))
            expected = (rate.buying_rate * item.net_weight * item.purity_percentage / 100).quantize(Decimal("0.01"))
            appraisal = record_collateral_reappraisal(loan_id=origin.loan_id, item_id=item.pk, actor=self.actor,
                appraised_value=expected, method="RATE_BASED", evidence_reference="Reviewed current quote",
                review_notes="Recorded weight and purity", expected_version=0, expected_rate_id=rate.pk)
            content = export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
        with self.scoped(self.b):
            restored, _ = self.restore(content)
            actual = restored.loan.collateral_items.get().appraisals.get()
            self.assertEqual(actual.method, "RATE_BASED")
            self.assertEqual(actual.appraised_value, appraisal.appraised_value)
            self.assertEqual(actual.valuation_context["rate_id"], rate.pk)
            self.assertEqual(actual.valuation_context["source_workspace_id"], self.a.pk)
            self.assertEqual(actual.valuation_context["valuation_basis"], "RATE_BASED")

    def check_round_trip(self, state):
        content = self.source(state)
        source = parse_opening_export(content)
        with self.scoped(self.b):
            origin, summary = self.restore(content)
            self.assertEqual(origin.references["restore"]["document"], source)
            self.assertEqual(summary["balance"], source["evidence"]["recorded_balance"])
            self.assertEqual(summary["state"], source["evidence"]["loan"]["state"])
            self.counter.refresh_from_db()
            self.assertEqual(self.counter.next_number, 1)
            with patch("django.utils.timezone.localdate", return_value=date.fromisoformat(source["manifest"]["as_of"])):
                again = parse_opening_export(export_opening(workspace_id=self.b.pk, actor=self.actor, loan_id=origin.loan_id))
            self.assertEqual(semantic_evidence(again["evidence"]), semantic_evidence(source["evidence"]))
            self.assertNotEqual(origin.loan_id, source["evidence"]["loan"]["id"])
            self.assertNotEqual(set(origin.references["items"].values()), set(source["evidence"]["origin"]["references"]["items"].values()))
            preview = preview_opening_restore(**self.restore_args, content=content)
            replay, _ = commit_opening_restore(**self.restore_args, content=content, expected_sha256=preview["sha256"], confirmed=True)
            self.assertEqual(replay.pk, origin.pk)
            self.assertEqual(m.PawnLoan.objects.count(), 1)
            self.assertEqual(m.PawnLoanEvent.objects.count(), len(source["evidence"]["events"]))
            self.assertFalse(m.PawnLoanDisbursalSnapshot.objects.exists())
            self.assertFalse(AuditLog.objects.filter(company=self.b, action="DATA_EXPORT").exclude(data__loan=origin.loan_id).exists())
            return origin

    def test_active_opening_round_trip_and_live_servicing_after_restore(self):
        origin = self.check_round_trip("opening")
        with self.scoped(self.b), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 3)):
            released = release_pawn_loan_in_full(origin.loan_id, settlement_amount=1010, request_key="after-restore", actor=self.actor)
            self.assertEqual(balance_values(origin.loan, date(2021, 2, 3))["principal"], "0")
            source = origin.references["restore"]["document"]
            content = (dump(source["manifest"]) + "\n" + dump(source["evidence"]) + "\n").encode()
            preview = preview_opening_restore(**self.restore_args, content=content)
            commit_opening_restore(**self.restore_args, content=content, expected_sha256=preview["sha256"], confirmed=True)
            self.assertEqual(balance_values(origin.loan, date(2021, 2, 3))["principal"], "0")
            self.assertEqual(m.PawnLoanRelease.objects.count(), 1)
            reverse_pawn_loan_event(released.loan_event.pk, actor=self.actor, reason="Cancelled new return")
            self.assertEqual(balance_values(origin.loan, date(2021, 2, 3))["principal"], "1000")

    def test_closed_concession_round_trip(self):
        self.check_round_trip("closed")

    def test_covered_first_month_release_does_not_invent_interest(self):
        self.check_round_trip("covered")

    def test_reversed_release_round_trip(self):
        self.check_round_trip("reversed")

    def test_release_reversal_then_release_round_trip(self):
        self.check_round_trip("released_again")

    def test_two_collateral_items_keep_distinct_bindings(self):
        first = self.review["collateral"][0]
        first.update(original_principal="500", remaining_principal="500")
        second = copy.deepcopy(first)
        second.update(id="girvi_loanitem:2", description="Second item", metal="SILVER")
        self.review["collateral"].append(second)
        self.review["source"]["item_ids"].append(second["id"])
        self.check_round_trip("released_again")

    def test_dated_additional_appraisal_is_preserved_and_used_for_release(self):
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 2)):
            origin = self.write()
            item = origin.loan.collateral_items.get()
            m.CollateralAppraisal.objects.create(workspace=self.a, collateral_item=item, version=2,
                effective_at=datetime(2021, 1, 25, tzinfo=dt_timezone.utc), appraised_value=2200,
                method="MIGRATION_REVIEW", evidence_reference="Later appraisal", supersedes=item.appraisals.get(), created_by=self.actor,
                valuation_context={"rate_id": 12345, "buying_price_inr_per_pure_gram": "100"})
            release_pawn_loan_in_full(origin.loan_id, settlement_amount=1010, request_key="later", actor=self.actor)
            content = export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
        with self.scoped(self.b):
            restored, _ = self.restore(content)
            self.assertEqual(restored.loan.collateral_items.get().appraisals.count(), 2)
            self.assertEqual(Decimal(m.PawnLoanReleaseItem.objects.get().valuation_snapshot["valuation_amount"]), 2200)
            context = restored.loan.collateral_items.get().appraisals.get(version=2).valuation_context
            self.assertEqual(context["source_workspace_id"], self.a.pk)
            self.assertEqual(context["rate_id"], 12345)

    def test_old_evidence_only_flag_is_accepted_but_malformed_or_oversized_files_are_rejected(self):
        source = parse_opening_export(self.source())
        source["manifest"]["restore_supported"] = False
        content = (dump(source["manifest"]) + "\n" + dump(source["evidence"]) + "\n").encode()
        with self.scoped(self.b):
            self.restore(content)
        from apps.tenant_apps.loans.services.history_contract import MAX_BYTES
        for invalid in (b"x" * (MAX_BYTES + 1), b'{"profile":"x","profile":"y"}\n{}\n',
                b'{"number":NaN}\n{}\n', content.replace(b'"principal":"1000"', b'"principal":"999"', 1)):
            with self.subTest(content=invalid[:30]), self.assertRaises(HistoryError):
                parse_opening_export(invalid)

    def test_operator_command_defaults_to_preview_and_requires_exact_confirmation(self):
        content = self.source("closed")
        with TemporaryDirectory(dir=".tmp") as directory:
            path = Path(directory) / "opening.jsonl"
            path.write_bytes(content)
            options = dict(workspace_id=self.b.pk, actor_id=self.actor.pk, source=str(path), **self.mapping)
            output = StringIO()
            call_command("restore_loan_opening", **options, stdout=output)
            preview = json.loads(output.getvalue())
            self.assertFalse(preview["committed"])
            with self.scoped(self.b):
                self.assertFalse(m.PawnLoan.objects.exists())
            with self.assertRaises(CommandError):
                call_command("restore_loan_opening", **options, commit=True)
            with self.assertRaises(CommandError):
                call_command("restore_loan_opening", **{**options, "actor_id": self.other_actor.pk, "source": "missing.jsonl"})
            output = StringIO()
            call_command("restore_loan_opening", **options, commit=True, expected_sha256=preview["sha256"], stdout=output)
            self.assertTrue(json.loads(output.getvalue())["committed"])

    def test_tampering_is_rejected_even_with_recomputed_export_checksum(self):
        source = parse_opening_export(self.source("closed"))
        mutations = [lambda e: e["recorded_balance"].update(principal="1"),
            lambda e: e["closing_lines"][0].update(principal_settled="999"),
            lambda e: e["custody_events"].clear(),
            lambda e: e["allocations"][0].update(obligation_id=99999999),
            lambda e: e["release_items"][0]["valuation_snapshot"].update(valuation_amount="1"),
            lambda e: e["schedules"][0].update(contractual_interest="999")]
        with self.scoped(self.b):
            for mutate in mutations:
                value = copy.deepcopy(source)
                mutate(value["evidence"])
                value["manifest"]["sha256"] = digest(value["evidence"])
                content = (dump(value["manifest"]) + "\n" + dump(value["evidence"]) + "\n").encode()
                with self.subTest(mutation=mutate), self.assertRaises(HistoryError):
                    preview_opening_restore(**self.restore_args, content=content)
                self.assertFalse(m.PawnLoan.objects.exists())
                self.assertFalse(m.HistoricalLoanImport.objects.exists())

    def test_confirmation_mapping_access_and_immutable_restore_provenance(self):
        content = self.source()
        with self.scoped(self.b):
            with self.assertRaises(PermissionDenied):
                preview_opening_restore(**{**self.restore_args, "actor": self.other_actor}, content=b"invalid")
            preview = preview_opening_restore(**self.restore_args, content=content)
            for extra in ({"confirmed": False}, {"expected_sha256": "0" * 64}):
                args = dict(self.restore_args, content=content, expected_sha256=preview["sha256"], confirmed=True)
                args.update(extra)
                with self.assertRaises(HistoryError):
                    commit_opening_restore(**args)
            with self.assertRaises(ValueError):
                preview_opening_restore(**{**self.restore_args, "mapping": {**self.mapping, "borrower_id": self.review["mapping"]["borrower_id"]}}, content=content)
            origin, _ = self.restore(content)
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.HistoricalLoanImport.objects.filter(pk=origin.pk).update(references={})
            value = parse_opening_export(content)
            value["manifest"]["restore_supported"] = False
            changed = (dump(value["manifest"]) + "\n" + dump(value["evidence"]) + "\n").encode()
            with self.assertRaisesMessage(ValueError, "different accepted restoration"):
                preview_opening_restore(**self.restore_args, content=changed)

    def test_revoked_permission_and_existing_source_origin_cannot_be_bypassed(self):
        from apps.orgs.models import Membership, WorkspaceRoleGrant
        content = self.source()
        mapping = self.review["mapping"]
        with self.scoped(), self.assertRaisesMessage(ValueError, "different accepted restoration"):
            preview_opening_restore(workspace_id=self.a.pk, actor=self.actor, content=content,
                mapping=dict(borrower_id=mapping["borrower_id"], revision_id=mapping["licence_revision_id"],
                    series_id=mapping["series_id"], product_version_id=mapping["product_version_id"]))
        with self.scoped(self.b):
            preview = preview_opening_restore(**self.restore_args, content=content)
            member = Membership.objects.get(company=self.b, user=self.actor)
            WorkspaceRoleGrant.objects.filter(workspace_id=self.b.pk, workspace_role__role_id=member.role_id,
                permission__codename="loan_release").delete()
            with self.assertRaises(PermissionDenied):
                commit_opening_restore(**self.restore_args, content=content, expected_sha256=preview["sha256"], confirmed=True)
            self.assertFalse(m.PawnLoan.objects.exists())
