"""Original financial mistakes through the shared reviewed agreement boundary."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.db import DatabaseError, connection, transaction
from django.test import override_settings
from django.urls import reverse

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.agreement_corrections import (
    preview_agreement_correction, record_agreement_correction, correction_dependencies,
)
from apps.tenant_apps.loans.selectors.servicing_contract import get_servicing_position
from apps.tenant_apps.loans.tests.test_continuation_admissions import AdmissionFixture
from apps.tenant_apps.loans.tests.test_settlement_continuation import on


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class AgreementCorrectionTests(AdmissionFixture):
    day = date(2026, 5, 6)

    def facts(self, loan=None, **changes):
        loan = loan or self.direct
        return dict(date=loan.loan_date.isoformat(), principal="6000", rate="3", cash_paid="5820",
            reference="Checked original agreement", reason="Original principal transcribed incorrectly",
            request_key=uuid4().hex) | changes

    def correct(self, loan, facts=None):
        facts = facts or self.facts(loan)
        review, token = preview_agreement_correction(loan.pk, actor=self.actor, data=facts)
        log, created = record_agreement_correction(loan.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)
        self.assertTrue(created)
        loan.refresh_from_db()
        return review, log, token

    def test_native_replay_preserves_cash_receipts_approval_custody_and_old_rows(self):
        with self.scoped(), on(self.day):
            loan = self.direct
            old_snapshot = loan.disbursal_snapshot
            original_approval = deepcopy(old_snapshot.approval_snapshot.payload)
            old_events = list(loan.loan_events.values())
            old_rows = list(loan.interest_accruals.values())
            custody = list(m.PawnCollateralCustodyEvent.objects.filter(collateral_item__loan=loan).values())
            facts = self.facts()
            review, log, token = self.correct(loan, facts)
            self.assertEqual(loan.state, "ACTIVE")
            self.assertEqual(loan.principal_amount, 6000)
            self.assertEqual(loan.policy_snapshot.basis, "ORIGINATION")
            self.assertEqual(loan.disbursal_snapshot.basis, "CORRECTED")
            self.assertEqual(loan.disbursal_snapshot.approval_snapshot_id, old_snapshot.approval_snapshot_id)
            old_snapshot.approval_snapshot.refresh_from_db()
            self.assertEqual(old_snapshot.approval_snapshot.payload, original_approval)
            self.assertEqual(list(loan.loan_events.filter(pk__in=[e["id"] for e in old_events]).values()), old_events)
            self.assertEqual(list(loan.interest_accruals.filter(pk__in=[r["id"] for r in old_rows]).values()), old_rows)
            self.assertEqual(list(m.PawnCollateralCustodyEvent.objects.filter(collateral_item__loan=loan).values()), custody)
            active = loan.loan_events.filter(event_kind="REPAYMENT", reversed_by_event__isnull=True).get()
            self.assertEqual(Decimal(active.payload["repayment"]["amount_received"]), self.reduction)
            self.assertEqual(Decimal(active.payload["values"]["principal"]), self.reduction)
            self.assertEqual(active.effective_date, self.cutover)
            self.assertEqual(get_servicing_position(loan, as_of_date=self.day).contract.profile, "native-monthly-policy/2")
            self.assertEqual(get_servicing_position(loan, as_of_date=self.day).balance.principal_outstanding, Decimal("6000") - self.reduction)
            self.assertEqual(Decimal(review["after"]["position"]["interest"]), Decimal("176.99"))
            self.assertFalse(record_agreement_correction(loan.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)[1])
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.LoanChangeLog.objects.filter(pk=log.pk).delete()

    def test_native_and_paper_equivalent_correction_results(self):
        with self.scoped(), on(self.day):
            for loan in (self.direct, self.paper):
                self.correct(loan)
            direct = get_servicing_position(self.direct, as_of_date=self.day).balance
            paper = get_servicing_position(self.paper, as_of_date=self.day).balance
            self.assertEqual((direct.principal_outstanding, direct.interest_outstanding, direct.total_due),
                (paper.principal_outstanding, paper.interest_outstanding, paper.total_due))

    def test_accepted_history_uses_saved_agreement_and_retains_original_import(self):
        with self.scoped():
            original = deepcopy(self.imported.historical_import.document)
            self.correct(self.imported)
            self.imported.historical_import.refresh_from_db()
            self.assertEqual(self.imported.historical_import.document, original)
            balance = get_servicing_position(self.imported, as_of_date=self.day).balance
            self.assertEqual(balance.principal_outstanding, Decimal("6000") - self.reduction)
            self.assertEqual(balance.interest_outstanding, Decimal("176.99"))

    def test_recalculated_receipt_discloses_agreement_correction_without_new_collection(self):
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        with self.scoped(), on(self.day):
            self.correct(self.direct)
            receipt = self.direct.loan_events.get(event_kind="REPAYMENT", reversed_by_event__isnull=True)
            payload = PawnLoanDocumentProjectionBuilder.repayment_receipt(receipt)
            fields = {field.key: field.value for field in payload.fields}
            self.assertIn("agreement correction", fields["document.status"])
            self.assertIn("not a new cash collection", fields["document.status"])
            self.assertEqual(Decimal(receipt.payload["repayment"]["amount_received"]), self.reduction)

    def test_failed_replay_and_stale_review_leave_all_evidence_unchanged(self):
        with self.scoped(), on(self.day):
            loan = self.direct
            before = list(loan.loan_events.values())
            with self.assertRaises(ValueError):
                preview_agreement_correction(loan.pk, actor=self.actor, data=self.facts(principal="100", cash_paid="97"))
            self.assertEqual(list(loan.loan_events.values()), before)
            facts = self.facts()
            _, token = preview_agreement_correction(loan.pk, actor=self.actor, data=facts)
            m.PawnCollateralItem.objects.filter(loan=loan).update(description="Reviewed original ring")
            with self.assertRaisesMessage(ValueError, "facts changed"):
                record_agreement_correction(loan.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)
            self.assertEqual(list(loan.loan_events.values()), before)

    def test_second_revision_and_later_monthly_recognition_do_not_duplicate_interest(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        with self.scoped(), on(self.day):
            self.correct(self.direct)
            facts = self.facts(principal="5500", rate="2", cash_paid="5390")
            self.correct(self.direct, facts)
            self.assertEqual(self.direct.disbursal_snapshot.evidence["agreement_correction"]["revision"], 3)
            self.assertEqual(get_servicing_position(self.direct, as_of_date=self.day).balance.interest_outstanding, 108)
            record_pawn_loan_repayment(self.direct.pk, amount="108", request_key="after-correction", actor=self.actor)
            self.assertEqual(get_servicing_position(self.direct, as_of_date=self.day).balance.interest_outstanding, 0)
            self.assertEqual(get_servicing_position(self.direct, as_of_date=date(2026, 6, 6)).balance.interest_outstanding, 108)

    def test_shared_http_review_and_confirmation_for_direct_and_paper(self):
        import os
        from pathlib import Path
        from apps.tenancy.testing import start_workspace_trial
        start_workspace_trial(self.a)
        self.client.force_login(self.actor)
        with self.scoped(), on(self.day):
            for loan in (self.direct, self.paper):
                url = reverse("workspace_loans:pawn_agreement_correct", kwargs=dict(workspace_slug=self.a.slug, pk=loan.pk))
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Correct agreement details")
                if os.environ.get("AGREEMENT_CORRECTION_QA_CAPTURE"):
                    folder = Path(os.environ["AGREEMENT_CORRECTION_QA_CAPTURE"])
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / ("direct-form.html" if loan == self.direct else "paper-form.html")).write_bytes(response.content)
                values = dict(self.facts(loan), action="preview")
                response = self.client.post(url, values)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.context["form"].errors, response.context["form"].errors)
                self.assertIsNotNone(response.context["review"])
                if os.environ.get("AGREEMENT_CORRECTION_QA_CAPTURE"):
                    (folder / ("direct-review.html" if loan == self.direct else "paper-review.html")).write_bytes(response.content)
                values.update(action="confirm", confirmed="on", review_token=response.context["form"].data["review_token"])
                self.assertEqual(self.client.post(url, values).status_code, 302)

    def test_checkpoint_http_uses_typed_review_and_preserves_missing_earlier_history(self):
        import os
        from pathlib import Path
        from apps.tenancy.testing import start_workspace_trial
        from apps.tenant_apps.loans.web.opening_agreement_corrections import CheckpointCorrectionForm
        from apps.tenant_apps.loans.services.opening_evidence import read_opening_evidence
        start_workspace_trial(self.a)
        self.client.force_login(self.actor)
        with self.scoped(), on(self.day):
            url = reverse("workspace_loans:pawn_agreement_correct", args=[self.a.slug, self.opening.pk])
            response = self.client.get(url)
            self.assertContains(response, "Correct agreement and opening balances")
            origin = self.opening.loan_events.get(event_kind="MIGRATION_OPENING")
            opening = read_opening_evidence(self.opening, origin)
            form = CheckpointCorrectionForm(opening=opening | {"review": self.checkpoint_facts()["checkpoint"]})
            values = dict(form.initial, reference="Checked original contract and opening book", reason="Original principal entered wrongly",
                request_key=uuid4().hex, action="preview")
            item = self.opening.collateral_items.get()
            response = self.client.post(url, values)
            self.assertFalse(response.context["form"].errors, response.context["form"].errors)
            self.assertIsNotNone(response.context["review"])
            self.assertContains(response, "Earlier payments remain unavailable")
            if os.environ.get("AGREEMENT_CORRECTION_QA_CAPTURE"):
                folder = Path(os.environ["AGREEMENT_CORRECTION_QA_CAPTURE"])
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "checkpoint-review.html").write_bytes(response.content)
            values.update(action="confirm", confirmed="on", review_token=response.context["form"].data["review_token"])
            self.assertEqual(self.client.post(url, values).status_code, 302)
            self.assertEqual(self.opening.loan_events.filter(event_kind="MIGRATION_OPENING").count(), 1)

    def test_competing_reviews_and_noop_cannot_append_an_extra_financial_revision(self):
        with self.scoped(), on(self.day):
            first = self.facts()
            second = self.facts(principal="7000", rate="3", cash_paid="6790")
            _, first_token = preview_agreement_correction(self.direct.pk, actor=self.actor, data=first)
            _, second_token = preview_agreement_correction(self.direct.pk, actor=self.actor, data=second)
            record_agreement_correction(self.direct.pk, actor=self.actor, data=first, review_token=first_token, confirmed=True)
            with self.assertRaisesMessage(ValueError, "facts changed"):
                record_agreement_correction(self.direct.pk, actor=self.actor, data=second, review_token=second_token, confirmed=True)
            with self.assertRaisesMessage(ValueError, "No agreement facts"):
                preview_agreement_correction(self.direct.pk, actor=self.actor, data=first | {"request_key": uuid4().hex})
            self.assertEqual(self.direct.disbursal_snapshots.filter(basis="CORRECTED").count(), 1)

    def test_unknown_checkpoint_history_does_not_fall_back_to_full_history_replay(self):
        with self.scoped(), on(self.day):
            self.assertTrue(correction_dependencies(self.opening)[2])
            with self.assertRaisesMessage(ValueError, "checkpoint"):
                preview_agreement_correction(self.opening.pk, actor=self.actor, data=self.facts(self.opening))

    def checkpoint_facts(self):
        from apps.tenant_apps.loans.services.opening_evidence import read_opening_evidence
        origin = self.opening.loan_events.get(event_kind="MIGRATION_OPENING")
        opening = read_opening_evidence(self.opening, origin)
        checkpoint = deepcopy(opening["review"])
        item = checkpoint["collateral"][0]
        item.update(original_principal="6000", remaining_principal="5000", monthly_rate="3")
        carry = checkpoint["continuation"]
        carry["bases"][0]["principal_base"] = "6000"
        carry["expected_period_interest"] = "180"
        advance = sum(Decimal(r["interest"]) for r in carry["advance_coverage"] if r["period_number"] == carry["period_number"])
        unpaid = str(Decimal("180") - advance)
        for name in ("recognized_interest", "recognized_unpaid_interest", "current_period_recognized_interest", "current_period_unpaid_interest"):
            carry[name] = unpaid
        checkpoint["balances"].update(principal="5000", interest=unpaid)
        checkpoint["obligations"][0].update(principal="5000", recognized_interest=unpaid)
        return dict(checkpoint=checkpoint, reference="Checked original agreement and cutover balances",
            reason="Principal and cutover debt were entered incorrectly", request_key=uuid4().hex)

    def test_opening_correction_keeps_one_origin_and_distinct_original_and_cutover_principal(self):
        from apps.tenant_apps.loans.services.opening_evidence import read_opening_evidence
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        with self.scoped(), on(self.day):
            loan = self.opening
            origin = loan.loan_events.get(event_kind="MIGRATION_OPENING")
            original_payload = deepcopy(origin.payload)
            facts = self.checkpoint_facts()
            review, log, token = self.correct(loan, facts)
            self.assertEqual(loan.principal_amount, 5000)
            self.assertEqual(review["after"]["original_principal"], "6000")
            self.assertEqual(loan.loan_events.filter(event_kind="MIGRATION_OPENING").count(), 1)
            self.assertFalse(loan.loan_events.filter(event_kind="DISBURSAL").exists())
            origin.refresh_from_db()
            self.assertEqual(origin.payload, original_payload)
            self.assertEqual(read_opening_evidence(loan, origin)["review"], facts["checkpoint"])
            self.assertEqual(get_servicing_position(loan, as_of_date=self.cutover).balance.principal_outstanding, 5000)
            self.assertFalse(record_agreement_correction(loan.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)[1])
            record_pawn_loan_repayment(loan.pk, amount="10", request_key="after-reviewed-checkpoint", actor=self.actor)
            self.assertEqual(loan.loan_events.filter(event_kind="REPAYMENT").count(), 1)
            self.assertEqual(get_servicing_position(loan, as_of_date=self.day).balance.principal_outstanding, 5000)
            with self.assertRaisesMessage(ValueError, "connected reconciliation"):
                preview_agreement_correction(loan.pk, actor=self.actor, data=facts | {"request_key": uuid4().hex})

    def test_opening_mismatched_checkpoint_and_changed_source_are_refused(self):
        with self.scoped(), on(self.day):
            facts = self.checkpoint_facts()
            bad = deepcopy(facts)
            bad["checkpoint"]["balances"]["principal"] = "1"
            with self.assertRaises(ValueError):
                preview_agreement_correction(self.opening.pk, actor=self.actor, data=bad)
            _, token = preview_agreement_correction(self.opening.pk, actor=self.actor, data=facts)
            m.PawnCollateralItem.objects.filter(loan=self.opening).update(description="Changed source")
            with self.assertRaisesMessage(ValueError, "facts changed"):
                record_agreement_correction(self.opening.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)

    def test_corrected_checkpoint_assessment_keeps_cutover_and_source_uncertainty(self):
        from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
        from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
        with self.scoped(), on(self.day):
            before = transaction_completeness(self.opening, self.day)
            self.correct(self.opening, self.checkpoint_facts())
            snapshot = refresh_loan_risk_snapshot(self.opening.pk, as_of_date=self.day)
            self.assertEqual(snapshot.status, "CURRENT")
            balance = get_servicing_position(self.opening, as_of_date=self.day).balance
            self.assertEqual(snapshot.exposure, balance.total_due)
            self.assertEqual(balance.financial_history_from, self.cutover)
            after = transaction_completeness(self.opening, self.day)
            self.assertTrue(after.required)
            self.assertEqual(after.complete, before.complete)

    def test_portable_corrected_native_roundtrip_preserves_revisions_and_current_position(self):
        self._assert_portable_roundtrip(self.direct)

    def test_portable_corrected_checkpoint_roundtrip_preserves_one_origin(self):
        self._assert_portable_roundtrip(self.opening)

    def _assert_portable_roundtrip(self, loan):
        from apps.orgs.models import Company
        from apps.tenancy.context import without_workspace_context
        from apps.tenant_apps.party.models import Party
        from apps.tenant_apps.data_portability.models import PartyIdentity, SourceIdentity
        from apps.tenant_apps.loans.services.license_series import create_license
        from apps.tenant_apps.loans.services.servicing_bundle import export_servicing_bundle, restore_servicing_bundle
        from apps.tenant_apps.loans.services.servicing_bundle_contract import read_bundle, decode
        self.actor.is_superuser = True
        self.actor.save(update_fields=["is_superuser"])
        with self.scoped(), on(self.day):
            if loan == self.opening:
                self.correct(loan, self.checkpoint_facts())
            else:
                self.correct(loan)
                self.correct(loan, self.facts(principal="5500", rate="2", cash_paid="5390"))
        with self.scoped():
            content = export_servicing_bundle(workspace_id=self.a.pk, actor=self.actor, loan_id=loan.pk)
            document, _ = read_bundle(content)
            self.assertEqual(document["profile"], "loan-servicing-bundle/7")
            kind = "PawnLoanEvent" if loan == self.opening else "PawnLoanDisbursalSnapshot"
            corrected = next(r for r in document["tables"][kind] if r.get("basis") == "CORRECTED" or r.get("event_kind") == "OPENING_CORRECTION")
            for profile in range(1, 7):
                with self.assertRaises(ValueError):
                    decode(kind, corrected, profile=f"loan-servicing-bundle/{profile}")
        with without_workspace_context():
            target = Company.objects.create(name="Agreement restore", schema_name="agreement_" + uuid4().hex,
                owner=self.actor, creator=self.actor)
        with self.scoped(target):
            source_key = str(loan.pk)
            reference = document["setup"][source_key]["borrower"]
            party = Party.objects.create(display_name="Exact source borrower")
            identity = PartyIdentity.objects.create(workspace=target, party=party)
            SourceIdentity.objects.create(workspace=target, identity=identity, source_system=reference["source_system"],
                external_id=reference["id"], accepted_digest="a"*64, local_digest="a"*64)
            setup = document["setup"][source_key]
            license = create_license(workspace=target, actor=self.actor, name="Original register",
                license_number=setup["licence_number"], issued_on=date(2020, 1, 1), expires_on=date(2099, 1, 1))
            series = m.LoanSeries.objects.create(license=license, name="Original", code="AA")
            product = m.LoanProduct.objects.create(workspace=target, name="Supported agreement", code="AA")
            version = m.LoanProductVersion.objects.create(product=product, version=1, status="RETIRED",
                maximum_tenor_months=1200, **setup["product"])
            args = dict(workspace_id=target.pk, actor=self.actor, content=content, mapping={source_key: dict(
                borrower_id=party.pk, revision_id=license.revisions.get().pk, series_id=series.pk, product_version_id=version.pk)})
            preview = restore_servicing_bundle(**args)
            self.assertFalse(m.PawnLoan.objects.exists())
            result = restore_servicing_bundle(**args, expected_sha256=preview["sha256"], confirmed=True)
            restored = m.PawnLoan.objects.get(pk=result["loans"][0])
            self.assertEqual(restored.disbursal_snapshots.filter(basis="CORRECTED").count(), 0 if loan == self.opening else 2)
            if loan == self.opening:
                self.assertEqual(restored.loan_events.filter(event_kind="MIGRATION_OPENING").count(), 1)
                self.assertEqual(restored.loan_events.filter(event_kind="OPENING_CORRECTION").count(), 1)
            self.assertEqual(restored.policy_snapshot.basis, "ORIGINATION")
            again, _ = read_bundle(export_servicing_bundle(workspace_id=target.pk, actor=self.actor, loan_id=restored.pk))
            self.assertEqual(again["positions"][str(restored.pk)]["recorded"], document["positions"][source_key]["recorded"])
            self.assertTrue(restore_servicing_bundle(**args, expected_sha256=preview["sha256"], confirmed=True)["already_restored"])
        return target, restored

    def test_exact_recovery_of_corrected_native_retains_original_and_replacement_rows(self):
        from apps.tenant_apps.loans.tests.test_pawn_recovery import PawnRecoveryTests
        target, _ = self._assert_portable_roundtrip(self.direct)
        self.tenant = target
        original = PawnRecoveryTests.export(self)
        PawnRecoveryTests.empty(self)
        self.assertTrue(PawnRecoveryTests.restore(self, commit=True)["committed"])
        restored = PawnRecoveryTests.export(self)
        self.assertEqual(original["tables"], restored["tables"])
        self.assertEqual(original["files"], restored["files"])

    def test_issued_pdf_uses_corrected_terms_and_old_artifact_bytes_remain(self):
        from apps.tenancy.testing import start_workspace_trial
        from apps.tenant_apps.loans.services.document_layouts import LoanDocumentLayoutService
        start_workspace_trial(self.a)
        self.client.force_login(self.actor)
        with self.scoped(), on(self.day):
            url = reverse("workspace_loans:pawn_loan_ticket_pdf", args=[self.a.slug, self.direct.pk])
            original = self.client.get(url)
            self.assertEqual(original.status_code, 200)
            source_issue = original["X-Rokkad-Document-Issue"]
            self.correct(self.direct)
            corrected = self.client.get(url)
            self.assertEqual(corrected.status_code, 200)
            self.assertNotEqual(source_issue, corrected["X-Rokkad-Document-Issue"])
            self.assertNotEqual(original.content, corrected.content)
            self.assertEqual(LoanDocumentLayoutService.read_verified_artifact(m.LoanDocumentIssue.objects.get(pk=source_issue)), original.content)
            self.assertEqual(self.client.get(url).content, corrected.content)

    def test_corrected_equivalent_direct_and_paper_risk_and_alerts_match(self):
        from apps.tenant_apps.loans.services.collateral_reappraisal import record_collateral_reappraisal
        from apps.tenant_apps.loans.services.transaction_reviews import preview_transaction_review, confirm_transaction_review
        from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
        with self.scoped(), on(self.day):
            values, alerts = [], []
            for loan in (self.direct, self.paper):
                self.correct(loan)
                item = loan.collateral_items.get()
                prior = item.appraisals.order_by("-version").first()
                record_collateral_reappraisal(loan_id=loan.pk, item_id=item.pk, actor=self.actor,
                    appraised_value=Decimal("5500"), method="PHYSICAL_INSPECTION", evidence_reference="Same current evidence",
                    review_notes="Same physical assessment", expected_version=prior.version if prior else 0)
                data = dict(through_date=self.day, confirmed_complete=True, source_reference="Actual books checked",
                    request_key=uuid4().hex, future_capture="ROKKAD_ONLY")
                _, token = preview_transaction_review(loan.pk, actor=self.actor, **data)
                confirm_transaction_review(loan.pk, actor=self.actor, review_token=token, acknowledged=True, **data)
                snapshot = refresh_loan_risk_snapshot(loan.pk, as_of_date=self.day)
                self.assertEqual(snapshot.status, "CURRENT")
                values.append(tuple(getattr(snapshot, field) for field in ("exposure", "due", "overdue", "days_past_due",
                    "days_to_maturity", "collateral_value", "ltv_ratio", "performance_class", "severity", "action_hint", "flags", "policy_identity")))
                alerts.append(list(loan.risk_alerts.values_list("alert_kind", "severity", "status").order_by("alert_kind")))
            self.assertEqual(values[0], values[1])
            self.assertEqual(alerts[0], alerts[1])

    def test_closed_native_correction_reconciles_verified_settlement_without_moving_collateral(self):
        from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full
        from apps.tenant_apps.loans.selectors.recorded_settlements import restated_release
        with self.scoped(), on(self.day):
            loan = self.direct
            facts = self.facts()
            expected, _ = preview_agreement_correction(loan.pk, actor=self.actor, data=facts)
            m.LoanNumberSequence.objects.create(series=loan.series, document_kind="PAWN_LOAN_RELEASE",
                prefix="AG-R-", width=5, maximum_number=10000)
            release = release_pawn_loan_in_full(loan.pk, actor=self.actor,
                settlement_amount=get_servicing_position(loan, as_of_date=self.day).balance.total_due, request_key="actual-full-return").release
            loan.refresh_from_db()
            custody = list(m.PawnCollateralCustodyEvent.objects.filter(collateral_item__loan=loan).values())
            facts["settlement"] = dict(cash_received=expected["after"]["balance"], cash_paid="0", interest_offset="0",
                reference="Verified actual original closing receipt", confirmed_unchanged=True)
            review, _, _ = self.correct(loan, facts)
            self.assertEqual(loan.state, "CLOSED")
            self.assertEqual(get_servicing_position(loan, as_of_date=self.day).balance.total_due, 0)
            self.assertEqual(restated_release(release).settlement_amount, Decimal(expected["after"]["balance"]))
            self.assertEqual(list(m.PawnCollateralCustodyEvent.objects.filter(collateral_item__loan=loan).values()), custody)
            self.assertEqual(loan.releases.count(), 1)
            self.assertEqual(review["rows"][-1]["principal"], expected["after"]["position"]["principal"])

    def test_new_document_copy_discloses_correction_and_preserves_original_approval(self):
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        with self.scoped(), on(self.day):
            original = PawnLoanDocumentProjectionBuilder.loan_ticket(self.direct)
            self.correct(self.direct)
            corrected = PawnLoanDocumentProjectionBuilder.loan_ticket(self.direct)
            fields = {f.key: f.value for f in corrected.fields}
            self.assertIn("6,000", fields["loan.principal"])
            self.assertNotEqual(original.verification_id, corrected.verification_id)
            self.assertIn("Corrected agreement", fields["document.status"])

    def test_actor_review_expiry_confirmation_and_workspace_are_enforced(self):
        from unittest.mock import patch
        with self.scoped(), on(self.day):
            facts = self.facts()
            _, token = preview_agreement_correction(self.direct.pk, actor=self.actor, data=facts)
            for value in ("", token + "invalid"):
                with self.assertRaises(ValueError):
                    record_agreement_correction(self.direct.pk, actor=self.actor, data=facts, review_token=value, confirmed=True)
            with self.assertRaisesMessage(ValueError, "Confirm"):
                record_agreement_correction(self.direct.pk, actor=self.actor, data=facts, review_token=token)
            with patch("django.core.signing.time.time", return_value=99999999999):
                with self.assertRaisesMessage(ValueError, "expired"):
                    record_agreement_correction(self.direct.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)
        with self.scoped(self.b), on(self.day):
            with self.assertRaisesMessage(ValueError, "active Workspace"):
                preview_agreement_correction(self.direct.pk, actor=self.actor, data=facts)

    def test_runtime_sql_cannot_rewrite_or_forge_checkpoint_source(self):
        from apps.tenant_apps.loans.services.event_recording import _fingerprint
        with self.scoped(), on(self.day):
            self.correct(self.opening, self.checkpoint_facts())
            event = self.opening.loan_events.get(event_kind="OPENING_CORRECTION")
            wrong = deepcopy(event.payload)
            wrong["agreement_correction"]["source_event_id"] = self.direct.loan_events.get(event_kind="DISBURSAL").pk
            fingerprint = _fingerprint(wrong)
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.PawnLoanEvent.objects.filter(pk=event.pk).update(payload=wrong)
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.PawnLoanEvent.objects.bulk_create([m.PawnLoanEvent(workspace=self.a, loan=self.opening,
                    event_kind="OPENING_CORRECTION", effective_date=event.effective_date, payload=wrong,
                    payload_fingerprint=fingerprint, idempotency_key="loans:forged:" + fingerprint, created_by=self.actor)])

    def test_without_workspace_authority_cannot_correct_an_agreement(self):
        from django.core.exceptions import PermissionDenied
        with self.scoped(), on(self.day):
            with self.assertRaises(PermissionDenied):
                preview_agreement_correction(self.direct.pk, actor=self.other_actor, data=self.facts())

    def test_queued_native_notice_is_held_after_financial_correction(self):
        from unittest.mock import Mock
        from apps.tenant_apps.loans.services.pawn_notices import create_pawn_loan_notice
        from apps.tenant_apps.loans.services.notice_delivery_readiness import dispatch_with_transaction_review
        from apps.tenant_apps.notify_v2.models import NotificationJob
        with self.scoped(), on(self.day):
            borrower = self.direct.borrower
            borrower.primary_email = "synthetic@example.test"
            borrower.save(update_fields=["primary_email"])
            notice = create_pawn_loan_notice(self.direct.pk, notice_kind="REPAYMENT_REMINDER", channel="EMAIL",
                request_key="before-financial-correction", actor=self.actor, dispatch_due=False)
            self.correct(self.direct)
            deliver = Mock()
            job = NotificationJob.objects.get(pk=notice.notification_job_id)
            self.assertFalse(dispatch_with_transaction_review(job, deliver))
            deliver.assert_not_called()
            job.refresh_from_db()
            self.assertEqual(job.status, "FAILED")
            new = create_pawn_loan_notice(self.direct.pk, notice_kind="REPAYMENT_REMINDER", channel="EMAIL",
                request_key="after-financial-correction", actor=self.actor, dispatch_due=False)
            self.assertEqual(new.payload_snapshot["agreement_identity"]["correction_id"],
                self.direct.change_log.filter(metadata__agreement_correction__isnull=False).get().pk)
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.PawnLoanNotice.objects.filter(pk=new.pk).update(payload_snapshot={})
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.PawnLoanNotice.objects.filter(pk=notice.pk).update(payload_snapshot=notice.payload_snapshot | {
                    "agreement_identity": new.payload_snapshot["agreement_identity"]})

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", DEFAULT_FROM_EMAIL="test@example.test")
    def test_native_risk_reminder_can_be_reviewed_once_again_after_agreement_correction(self):
        from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
        from apps.tenant_apps.loans.services.risk_borrower_notices import preview_risk_borrower_notice, create_risk_borrower_notice
        from apps.tenant_apps.notify_v2.models import NotificationEventType, NotificationTemplate
        with self.scoped(), on(date(2027, 4, 1)):
            borrower = self.direct.borrower
            borrower.primary_email = "synthetic@example.test"
            borrower.save(update_fields=["primary_email"])
            m.PawnLoanCommunicationConsent.objects.create(workspace=self.a, party=borrower, channel="EMAIL",
                service_notices_allowed=True, evidence="Actual independent consent", updated_by=self.actor)
            event, _ = NotificationEventType.objects.get_or_create(key="pawn_loan.repayment_reminder", defaults=dict(name="Repayment", domain="LOAN"))
            NotificationTemplate.objects.create(event_type=event, channel="EMAIL", name="Repayment",
                body_template="{{ customer.name }}: {{ loans.0.total_due }}", subject_template="Repayment")
            refresh_loan_risk_snapshot(self.direct.pk, as_of_date=date(2027, 4, 1))
            alert = m.LoanRiskAlert.objects.get(loan=self.direct, alert_kind="MATURITY")
            preview = preview_risk_borrower_notice(alert.pk)
            original = create_risk_borrower_notice(alert.pk, actor=self.actor, expected_fingerprint=preview.fingerprint)
            self.correct(self.direct)
            refresh_loan_risk_snapshot(self.direct.pk, as_of_date=date(2027, 4, 1))
            preview = preview_risk_borrower_notice(alert.pk)
            replacement = create_risk_borrower_notice(alert.pk, actor=self.actor, expected_fingerprint=preview.fingerprint)
            self.assertNotEqual(original.pk, replacement.pk)
            self.assertEqual(original.source_risk_event_id, replacement.source_risk_event_id)
            self.assertNotEqual(original.payload_snapshot["total_amount"], replacement.payload_snapshot["total_amount"])
            with self.assertRaisesMessage(ValueError, "already has"):
                preview_risk_borrower_notice(alert.pk)
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.PawnLoanNotice.objects.create(workspace=self.a, loan=self.direct, notice_kind=replacement.notice_kind,
                    channel="EMAIL", request_key=uuid4().hex, scheduled_for=replacement.scheduled_for,
                    recipient_email=replacement.recipient_email, source_risk_alert=alert, source_risk_event=alert.source_event,
                    notification_template_id=replacement.notification_template_id, notification_template_version=replacement.notification_template_version,
                    payload_snapshot=replacement.payload_snapshot)
            from importlib import import_module
            reverse = import_module("apps.tenant_apps.loans.migrations.0081_agreement_notice_identity").Migration.operations[-1].reverse_sql
            with self.assertRaisesMessage(DatabaseError, "prevents downgrade"), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(reverse)

    def test_corrected_native_supports_ordinary_renewal_and_retains_connected_correction_guard(self):
        from apps.tenant_apps.loans.tests.test_settlement_continuation import SettlementContinuationTests
        from apps.tenant_apps.loans.services.pawn_renewals import preview_pawn_loan_renewal_plan, renew_pawn_loan
        with self.scoped(), on(self.day):
            self.correct(self.direct)
        day = date(2026, 6, 6)
        with self.scoped(), on(day):
            self.remaining = get_servicing_position(self.direct, as_of_date=day).balance.principal_outstanding
            SettlementContinuationTests.successor_setup(self, day)
            values = SettlementContinuationTests.renewal_values(self, self.direct)
            preview = preview_pawn_loan_renewal_plan(self.direct.pk, **values)
            result = renew_pawn_loan(self.direct.pk, **values, renewal_date=day, request_key="after-financial-correction",
                expected_preview_fingerprint=preview.fingerprint, actor=self.actor)
            self.assertEqual(result.successor_loan.principal_amount, self.remaining + 100)
            self.direct.refresh_from_db()
            self.assertEqual(self.direct.state, "CLOSED")
            self.assertEqual(self.direct.disbursal_snapshot.basis, "CORRECTED")
            with self.assertRaises(ValueError):
                preview_agreement_correction(self.direct.pk, actor=self.actor, data=self.facts())


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class MultipleItemAgreementCorrectionTests(AdmissionFixture):
    multiple_items = True
    principal = Decimal("5025.50")
    second_rate = Decimal("4")

    def test_corrected_item_rates_reallocate_native_receipt_under_the_retained_rule(self):
        with self.scoped(), on(date(2026, 5, 6)):
            items = list(self.direct.collateral_items.order_by("pk"))
            data = dict(date=self.original.isoformat(), principal="6000", rate="2", cash_paid="5880",
                reference="Checked itemized agreement", reason="Original per-item terms were entered wrongly", request_key=uuid4().hex,
                items=[dict(item_id=items[0].pk, principal="3000", rate="3"), dict(item_id=items[1].pk, principal="3000", rate="1")])
            _, token = preview_agreement_correction(self.direct.pk, actor=self.actor, data=data)
            record_agreement_correction(self.direct.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
            self.direct.refresh_from_db()
            receipt = self.direct.loan_events.get(event_kind="REPAYMENT", reversed_by_event__isnull=True)
            line = receipt.repayment_allocation_lines.filter(principal_applied__gt=0).get()
            self.assertEqual(line.collateral_item_id, items[0].pk)
            self.assertEqual(line.principal_applied, self.reduction)
            self.assertEqual(Decimal(receipt.payload["repayment"]["amount_received"]), self.reduction)
            self.assertEqual(get_servicing_position(self.direct, as_of_date=date(2026, 5, 6)).balance.interest_outstanding, Decimal("116.99"))
