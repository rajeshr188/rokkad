"""Cross-Workspace transfer preserves each new evidence boundary."""
from datetime import date, datetime
from unittest.mock import patch

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.archive import accept_evidence
from apps.tenant_apps.loans.services.history_contract import digest
from apps.tenant_apps.loans.services.terminal_admission import preview_terminal_admission, admit_terminal_position
from apps.tenant_apps.loans.services.recorded_history import new_recording_intent
from apps.tenant_apps.loans.services.opening_export import export_loan_data, export_opening
from apps.tenant_apps.loans.services.opening_restore import preview_opening_restore, commit_opening_restore
from apps.tenant_apps.loans.services.servicing_bundle import read_bundle
from .test_bounded_opening_evidence import ExplicitOpeningFixture
from .test_opening_import import OpeningImportFixture
from .test_servicing_bundle import roundtrip, destination
from apps.tenant_apps.data_portability.tests import test_loan_archive as archives


class TerminalPortabilityTests(OpeningImportFixture):
    def test_terminal_archive_and_position_roundtrip_without_fake_settlement(self):
        with self.scoped():
            source = archives.document()
            source["source"].update(loan_id="closed-incomplete-5", system=self.review["mapping"]["borrower_source_system"],
                namespace=self.review["source"]["namespace"])
            source["facts"].update(loan_number="CLOSED-5", opened_on="2021-01-01", closed_on="2021-02-20",
                original_principal="1000", reported_balance="0", borrower_reference=None, payments=None,
                collateral=[dict(description="Ring", quantity=1, gross_weight="10", net_weight="9")])
            evidence = accept_evidence(workspace_id=self.a.pk, actor=self.actor, document=source, expected_sha256=digest(source), confirmed=True)
            data = dict(borrower_id=self.source_party.identity.party_id, series_id=self.series.pk,
                product_version_id=self.review["mapping"]["product_version_id"], license_revision_id=self.review["mapping"]["licence_revision_id"],
                number="CLOSED-5", date="2021-01-01", tenure=3, currency_quantum="0.01", source_reference="Synthetic agreement 5",
                monitoring_method="LATEST_APPRAISAL", monitoring_ltv="0.8", monitoring_reason="No outstanding exposure",
                closed_on="2021-02-20", closure_reference="Verified closure; earlier receipts unavailable", custody="UNKNOWN",
                confirmed_agreement=True, confirmed_closed=True,
                collateral=[dict(description="Ring", quantity=1, metal="GOLD", gross_weight="10", net_weight="9", purity="75", principal="1000", rate="1")])
            args = dict(workspace=self.a, actor=self.actor, data=data, evidence_id=evidence.public_id,
                intent_token=new_recording_intent(workspace=self.a, actor=self.actor))
            _, token = preview_terminal_admission(**args)
            loan, _ = admit_terminal_position(**args, review_token=token, confirmed=True)
            content, name = export_loan_data(workspace_id=self.a.pk, actor=self.actor, loan_id=loan.pk)
            self.assertEqual(name, "loan-servicing.zip")
        result = roundtrip(self, content)
        with self.scoped(self.b):
            rebuilt = m.PawnLoan.objects.get()
            self.assertEqual(rebuilt.state, "CLOSED")
            self.assertFalse(rebuilt.disbursal_snapshot_id)
            self.assertFalse(rebuilt.releases.exists())
            self.assertEqual(rebuilt.loan_events.count(), 1)
            self.assertEqual(rebuilt.historical_import.archive_evidence.document, source)
            self.assertEqual(rebuilt.collateral_items.get().custody_state, "PAPER_CLOSED")
            from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
            position = get_pawn_loan_balance(rebuilt, as_of_date=date(2021, 2, 20))
            self.assertEqual((position.principal_outstanding, position.interest_outstanding, position.fees_outstanding), (0, 0, 0))


class ExplicitOpeningPortabilityTests(ExplicitOpeningFixture):
    def test_item_split_and_fee_evidence_survive_opening_v4_restore(self):
        with self.scoped():
            self.receipt()
            packet = export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=self.loan.pk)
            bundle, _ = export_loan_data(workspace_id=self.a.pk, actor=self.actor, loan_id=self.loan.pk)
        with self.scoped(self.b):
            self.commit(self.ready(self.stage(workspace=self.b, system=self.review["mapping"]["borrower_source_system"]), workspace=self.b), workspace=self.b)
        source, _ = read_bundle(bundle)
        mapping = destination(self, source)[str(self.loan.pk)]
        args = dict(workspace_id=self.b.pk, actor=self.actor, content=packet, mapping=mapping)
        with self.scoped(self.b):
            preview = preview_opening_restore(**args)
            origin, _ = commit_opening_restore(**args, expected_sha256=preview["sha256"], confirmed=True)
            self.assertEqual(origin.loan.loan_events.filter(event_kind="REPAYMENT").count(), 1)
            receipt = origin.loan.loan_events.get(event_kind="REPAYMENT")
            split = receipt.payload["repayment"]["recording"]["item_principal_split"]
            self.assertEqual(set(split), {str(pk) for pk in origin.loan.collateral_items.values_list("pk", flat=True)})
            self.assertEqual(receipt.payload["repayment"]["recording"]["fees_paid"], "10.00")


class PreciseOpeningPortabilityTests(ExplicitOpeningPortabilityTests):
    precise = True

    def test_precise_checkpoint_day_closure_roundtrip(self):
        from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full
        from apps.tenant_apps.loans.services.servicing_bundle import export_servicing_bundle
        on = date(2021, 2, 20)
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=on), patch(
                "django.utils.timezone.now", return_value=datetime.fromisoformat("2021-02-20T11:00:00+05:30")):
            release_pawn_loan_in_full(self.loan.pk, actor=self.actor, settlement_amount="830", request_key="timed-close")
        with self.scoped():
            packet = export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=self.loan.pk)
            bundle = export_servicing_bundle(workspace_id=self.a.pk, actor=self.actor, loan_id=self.loan.pk)
        with self.scoped(self.b):
            self.commit(self.ready(self.stage(workspace=self.b, system=self.review["mapping"]["borrower_source_system"]), workspace=self.b), workspace=self.b)
        source, _ = read_bundle(bundle)
        mapping = destination(self, source)[str(self.loan.pk)]
        args = dict(workspace_id=self.b.pk, actor=self.actor, content=packet, mapping=mapping)
        with self.scoped(self.b):
            preview = preview_opening_restore(**args)
            origin, _ = commit_opening_restore(**args, expected_sha256=preview["sha256"], confirmed=True)
            release = origin.loan.loan_events.get(event_kind="RELEASE_RECEIPT")
            self.assertEqual(release.payload["opening_collection"]["occurred_at"], "2021-02-20T11:00:00+05:30")
            self.assertEqual(origin.loan.state, "CLOSED")
