"""Fact corrections across real admission paths, without financial or custody replay."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.test import override_settings
from django.urls import reverse

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.selectors.servicing_contract import get_servicing_position
from apps.tenant_apps.loans.services.collateral_corrections import (
    item_details, preview_collateral_correction, record_collateral_correction, validate_correction_chain,
)
from apps.tenant_apps.loans.tests.test_continuation_admissions import AdmissionFixture
from apps.tenant_apps.loans.tests.test_settlement_continuation import on
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.tests import test_recorded_origination as origins, test_recorded_history as histories


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class CollateralCorrectionTests(AdmissionFixture):
    day = date(2026, 5, 6)

    def facts(self, loan=None, **changes):
        loan = loan or self.direct
        item = loan.collateral_items.get()
        return dict(item_id=item.pk, after=dict(item_details(item), **(changes or {"description": "Correct gold ring"})),
            reference="Actual agreement / checked item", reason="Mistyped during entry", request_key=uuid4().hex)

    def correct(self, loan, facts):
        review, token = preview_collateral_correction(loan.pk, actor=self.actor, data=facts)
        log, created = record_collateral_correction(loan.pk, actor=self.actor, data=facts,
            review_token=token, confirmed=True)
        self.assertTrue(created)
        return log, review, token

    def test_all_four_origins_preserve_money_custody_and_original_evidence(self):
        with self.scoped(), on(self.day):
            for loan in self.loans:
                item = loan.collateral_items.get()
                before = get_servicing_position(loan, as_of_date=self.day).balance
                events = list(loan.loan_events.values())
                approvals = list(loan.approval_snapshots.values())
                payouts = list(loan.disbursal_snapshots.values())
                custody = list(item.custody_history.values())
                economics = (item.allocated_principal, item.monthly_interest_rate, item.interest_rate_policy_id)
                facts = self.facts(loan, description="Actual ring", net_weight="0.9000", quantity=2)
                log, review, _ = self.correct(loan, facts)
                item.refresh_from_db()
                self.assertEqual((item.description, item.net_weight, item.quantity), ("Actual ring", Decimal(".9"), 2))
                self.assertEqual((item.allocated_principal, item.monthly_interest_rate, item.interest_rate_policy_id), economics)
                self.assertEqual(get_servicing_position(loan, as_of_date=self.day).balance, before)
                self.assertEqual(list(loan.loan_events.values()), events)
                self.assertEqual(list(loan.approval_snapshots.values()), approvals)
                self.assertEqual(list(loan.disbursal_snapshots.values()), payouts)
                self.assertEqual(list(item.custody_history.values()), custody)
                self.assertTrue(review["valuation_changed"])
                self.assertEqual(log.from_state, log.to_state)
                validate_correction_chain(loan)

    def test_no_change_invalid_input_and_financial_field_injection_are_refused(self):
        with self.scoped(), on(self.day):
            base = self.facts()
            invalid = [dict(base, after=item_details(self.direct.collateral_items.get())),
                dict(base, after=dict(base["after"], net_weight="NaN")),
                dict(base, after=dict(base["after"], net_weight="2")),
                dict(base, after=dict(base["after"], purity_percentage="101")),
                dict(base, after=dict(base["after"], quantity=True)),
                dict(base, after=dict(base["after"], quantity=0)),
                dict(base, after=dict(base["after"], net_weight=".12345")),
                dict(base, after=dict(base["after"], gross_weight=None)),
                dict(base, after=dict(base["after"], allocated_principal="1"))]
            for facts in invalid:
                with self.assertRaises(ValueError):
                    preview_collateral_correction(self.direct.pk, actor=self.actor, data=facts)
            self.assertFalse(self.direct.change_log.filter(event_kind="COLLATERAL_CORRECTED").exists())

    def test_signed_review_changed_facts_actor_expiry_and_retry(self):
        with self.scoped(), on(self.day):
            facts = self.facts()
            _, token = preview_collateral_correction(self.direct.pk, actor=self.actor, data=facts)
            for value in (token + "bad", ""):
                with self.assertRaises(ValueError):
                    record_collateral_correction(self.direct.pk, actor=self.actor, data=facts, review_token=value, confirmed=True)
            changed = dict(facts, after=dict(facts["after"], description="Different item description"))
            with self.assertRaisesMessage(ValueError, "facts changed"):
                record_collateral_correction(self.direct.pk, actor=self.actor, data=changed, review_token=token, confirmed=True)
            with self.assertRaisesMessage(ValueError, "Confirm"):
                record_collateral_correction(self.direct.pk, actor=self.actor, data=facts, review_token=token)
            with patch("django.core.signing.time.time", return_value=99999999999):
                with self.assertRaisesMessage(ValueError, "again"):
                    record_collateral_correction(self.direct.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)
            log, created = record_collateral_correction(self.direct.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)
            again, created = record_collateral_correction(self.direct.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)
            self.assertFalse(created)
            self.assertEqual(again.pk, log.pk)
            with self.assertRaisesMessage(ValueError, "different collateral facts"):
                record_collateral_correction(self.direct.pk, actor=self.actor, data=changed, review_token=token, confirmed=True)

    def test_foreign_item_and_workspace_are_refused(self):
        with self.scoped(), on(self.day):
            facts = self.facts(self.paper)
            with self.assertRaisesMessage(ValueError, "on this loan"):
                preview_collateral_correction(self.direct.pk, actor=self.actor, data=facts)
        with self.scoped(self.b), on(self.day):
            with self.assertRaisesMessage(ValueError, "active Workspace"):
                preview_collateral_correction(self.direct.pk, actor=self.actor, data=facts)

    def test_new_loan_or_appraisal_changes_invalidate_review(self):
        with self.scoped(), on(self.day):
            facts = self.facts()
            _, token = preview_collateral_correction(self.direct.pk, actor=self.actor, data=facts)
            self.direct.updated_at = self.direct.updated_at.replace(year=2025)
            m.PawnLoan.objects.filter(pk=self.direct.pk).update(updated_at=self.direct.updated_at)
            with self.assertRaisesMessage(ValueError, "facts changed"):
                record_collateral_correction(self.direct.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)

    def test_competing_reviews_cannot_both_apply(self):
        with self.scoped(), on(self.day):
            first, second = self.facts(description="First correction"), self.facts(description="Second correction")
            _, first_token = preview_collateral_correction(self.direct.pk, actor=self.actor, data=first)
            _, second_token = preview_collateral_correction(self.direct.pk, actor=self.actor, data=second)
            record_collateral_correction(self.direct.pk, actor=self.actor, data=first, review_token=first_token, confirmed=True)
            with self.assertRaisesMessage(ValueError, "facts changed"):
                record_collateral_correction(self.direct.pk, actor=self.actor, data=second, review_token=second_token, confirmed=True)
            self.assertEqual(self.direct.change_log.filter(event_kind="COLLATERAL_CORRECTED").count(), 1)

    def test_unexplained_projection_drift_is_held_before_confirmation(self):
        with self.scoped(), on(self.day):
            m.PawnCollateralItem.objects.filter(loan=self.direct).update(net_weight=Decimal(".8"))
            with self.assertRaisesMessage(ValueError, "retained source"):
                preview_collateral_correction(self.direct.pk, actor=self.actor, data=self.facts())
            self.assertFalse(self.direct.change_log.filter(event_kind="COLLATERAL_CORRECTED").exists())

    def test_measurement_correction_invalidates_old_appraisal_but_new_appraisal_works(self):
        from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
        from apps.tenant_apps.loans.services.collateral_reappraisal import record_collateral_reappraisal
        from apps.tenant_apps.loans.selectors.portfolio_analysis import _collateral_analysis
        from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
        with self.scoped(), on(self.day):
            item = self.direct.collateral_items.get()
            before = get_pawn_loan_collateral_valuation(self.direct.pk, as_of_date=self.day)
            self.assertIsNotNone(before.items[0].appraisal_value)
            report_before = _collateral_analysis(self.a.pk, self.day)
            snapshot = refresh_loan_risk_snapshot(self.direct.pk, as_of_date=self.day)
            self.assertNotEqual(snapshot.status, "ERROR")
            self.correct(self.direct, self.facts(net_weight=".9"))
            snapshot.refresh_from_db()
            self.assertEqual(snapshot.status, "STALE")
            after = get_pawn_loan_collateral_valuation(self.direct.pk, as_of_date=self.day)
            self.assertIsNone(after.items[0].appraisal_value)
            self.assertEqual(_collateral_analysis(self.a.pk, self.day)["totals"][6], report_before["totals"][6] + 1)
            version = item.appraisals.order_by("-version").get().version
            record_collateral_reappraisal(loan_id=self.direct.pk, item_id=item.pk, actor=self.actor,
                appraised_value=Decimal("9000"), method="PHYSICAL_INSPECTION", evidence_reference="Checked ring",
                review_notes="Corrected weight measured", expected_version=version)
            current = get_pawn_loan_collateral_valuation(self.direct.pk, as_of_date=self.day)
            self.assertEqual(current.items[0].appraisal_value, Decimal("9000"))
            self.assertEqual(_collateral_analysis(self.a.pk, self.day)["totals"][6], report_before["totals"][6])

    def test_description_correction_preserves_appraisal_and_new_ticket_discloses_it(self):
        from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder as Projection
        with self.scoped(), on(self.day):
            before = get_pawn_loan_collateral_valuation(self.direct.pk, as_of_date=self.day)
            old = Projection.loan_ticket(self.direct)
            _, review, _ = self.correct(self.direct, self.facts())
            after = get_pawn_loan_collateral_valuation(self.direct.pk, as_of_date=self.day)
            self.assertEqual(after.items, before.items)
            new = Projection.loan_ticket(self.direct)
            self.assertNotEqual(new.verification_id, old.verification_id)
            self.assertIn("Correct gold ring", str(new))
            self.assertIn("Collateral correction", str(new))
            self.assertFalse(review["valuation_changed"])

    def test_failed_projection_update_rolls_back_audit(self):
        with self.scoped(), on(self.day):
            facts = self.facts()
            _, token = preview_collateral_correction(self.direct.pk, actor=self.actor, data=facts)
            original = m.PawnLoan.save
            def fail(loan, *args, **kwargs):
                if loan.pk == self.direct.pk:
                    raise ValueError("Projection failure")
                return original(loan, *args, **kwargs)
            with patch.object(m.PawnLoan, "save", fail):
                with self.assertRaisesMessage(ValueError, "Projection failure"):
                    record_collateral_correction(self.direct.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)
            self.assertFalse(self.direct.change_log.filter(event_kind="COLLATERAL_CORRECTED").exists())
            self.assertNotEqual(self.direct.collateral_items.get().description, facts["after"]["description"])

    def test_database_guard_preserves_correction_and_item_identity(self):
        with self.scoped(), on(self.day):
            log, _, _ = self.correct(self.direct, self.facts())
            for action in (
                lambda: m.LoanChangeLog.objects.filter(pk=log.pk).update(reason="Rewritten"),
                lambda: m.LoanChangeLog.objects.filter(pk=log.pk).delete(),
                lambda: m.PawnCollateralItem.objects.filter(pk=log.metadata["collateral_correction"]["item_id"]).update(loan_id=self.paper.pk),
            ):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    action()

    def test_restricted_role_can_correct_but_cannot_rewrite_or_cross_workspace(self):
        from apps.tenancy.context import without_workspace_context, workspace_context
        role = connection.ops.quote_name("collateral_correct_" + uuid4().hex)
        connection.check_constraints()
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        with self.scoped(), on(self.day):
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET LOCAL ROLE {role}")
                log, _, _ = self.correct(self.direct, self.facts())
                for action in (
                    lambda: m.LoanChangeLog.objects.filter(pk=log.pk).update(reason="Overwrite"),
                    lambda: m.LoanChangeLog.objects.filter(pk=log.pk).delete(),
                ):
                    with self.assertRaises(DatabaseError), transaction.atomic():
                        action()
                metadata = deepcopy(log.metadata)
                metadata["collateral_correction"]["item_id"] = self.paper.collateral_items.get().pk
                metadata["collateral_correction"]["request_key"] = "Wrong loan item"
                with self.assertRaises(DatabaseError), transaction.atomic():
                    m.LoanChangeLog.objects.create(workspace_id=self.a.pk, loan=self.direct, actor=self.actor,
                        event_kind="COLLATERAL_CORRECTED", from_state="ACTIVE", to_state="ACTIVE", reason=log.reason, metadata=metadata)
                with without_workspace_context(), workspace_context(self.b.pk):
                    self.assertFalse(m.LoanChangeLog.objects.filter(pk=log.pk).exists())
                    self.assertFalse(m.PawnCollateralItem.objects.filter(pk=log.metadata["collateral_correction"]["item_id"]).exists())
            finally:
                with connection.cursor() as cursor:
                    cursor.execute("RESET ROLE")
                    cursor.execute(f"DROP OWNED BY {role}")
                    cursor.execute(f"DROP ROLE {role}")

    def test_metal_correction_keeps_agreed_rates_and_full_release_then_closed_correction_work(self):
        from apps.tenant_apps.loans.services.pawn_release import preview_pawn_loan_full_release, release_pawn_loan_in_full
        with self.scoped(), on(self.day):
            m.LoanNumberSequence.objects.create(series=self.direct.series, document_kind="PAWN_LOAN_RELEASE",
                prefix="COR-R-", width=5, maximum_number=10000)
            for loan in self.loans:
                item = loan.collateral_items.get()
                rate = item.monthly_interest_rate
                self.correct(loan, self.facts(loan, metal="SILVER"))
                item.refresh_from_db()
                item.save(update_fields=["custody_state"])
                amount = preview_pawn_loan_full_release(loan.pk).minimum_settlement
                result = release_pawn_loan_in_full(loan.pk, settlement_amount=amount,
                    request_key="Correct then close " + str(loan.pk), actor=self.actor)
                loan.refresh_from_db()
                self.assertEqual(loan.state, "CLOSED")
                self.correct(loan, self.facts(loan, description="Corrected closed description"))
                loan.refresh_from_db()
                item.refresh_from_db()
                self.assertEqual((loan.state, item.custody_state, item.monthly_interest_rate), ("CLOSED", "WITH_CUSTOMER", rate))
                from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
                self.assertEqual(get_pawn_loan_balance(loan, as_of_date=self.day).total_due, 0)

    def test_missing_authority_and_pre_confirmation_states_are_refused(self):
        with self.scoped(), on(self.day):
            facts = self.facts()
            with self.assertRaises(PermissionDenied):
                preview_collateral_correction(self.direct.pk, actor=None, data=facts)
            for state in ("DRAFT", "APPROVED", "CANCELLED"):
                m.PawnLoan.objects.filter(pk=self.direct.pk).update(state=state)
                with self.assertRaisesMessage(ValueError, "draft"):
                    preview_collateral_correction(self.direct.pk, actor=self.actor, data=facts)

    def test_corrected_loan_can_renew_but_linked_items_require_connected_review(self):
        from apps.tenant_apps.loans.tests.test_settlement_continuation import SettlementContinuationTests
        from apps.tenant_apps.loans.services.pawn_renewals import preview_pawn_loan_renewal_plan, renew_pawn_loan
        day = date(2026, 6, 6)
        with self.scoped(), on(day):
            self.correct(self.direct, self.facts(net_weight=".9"))
            SettlementContinuationTests.successor_setup(self, day)
            values = SettlementContinuationTests.renewal_values(self, self.direct)
            preview = preview_pawn_loan_renewal_plan(self.direct.pk, **values)
            result = renew_pawn_loan(self.direct.pk, **values, renewal_date=day, request_key="Corrected then renewed",
                expected_preview_fingerprint=preview.fingerprint, actor=self.actor)
            self.assertEqual(result.successor_loan.collateral_items.get().net_weight, Decimal(".9"))
            for loan in (self.direct, result.successor_loan):
                with self.assertRaisesMessage(ValueError, "both loans"):
                    preview_collateral_correction(loan.pk, actor=self.actor, data=self.facts(loan))

    def test_migration_preserves_existing_rows_and_retained_corrections_block_downgrade(self):
        from importlib import import_module
        sql = import_module("apps.tenant_apps.loans.migrations.0078_collateral_fact_corrections").Migration.operations[-1]
        before = list(m.PawnLoanEvent.objects.values())
        connection.check_constraints()
        with connection.cursor() as cursor:
            cursor.execute(sql.reverse_sql)
            cursor.execute(sql.sql)
        self.assertEqual(list(m.PawnLoanEvent.objects.values()), before)
        with self.scoped(), on(self.day):
            self.correct(self.direct, self.facts())
        with self.assertRaisesMessage(DatabaseError, "prevents downgrade"), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(sql.reverse_sql)

    def test_existing_correction_route_returns_to_contextual_actions(self):
        from apps.tenancy.testing import start_workspace_trial
        start_workspace_trial(self.a)
        self.client.force_login(self.actor)
        response = self.client.get(reverse("workspace_loans:pawn_loan_correction_review", args=[self.a.slug, self.direct.pk]))
        self.assertRedirects(response, reverse("workspace_loans:pawn_loan_detail", args=[self.a.slug, self.direct.pk]) + "#loan-corrections", fetch_redirect_response=False)

    def test_http_review_confirm_and_detail_history(self):
        import os
        from pathlib import Path
        from apps.tenancy.testing import start_workspace_trial
        start_workspace_trial(self.a)
        self.client.force_login(self.actor)
        for label, loan in (("direct", self.direct), ("paper", self.paper)):
            with self.scoped():
                item = loan.collateral_items.get()
                facts = self.facts(loan)
            url = reverse("workspace_loans:pawn_collateral_correct", args=[self.a.slug, loan.pk, item.pk])
            entry = self.client.get(url)
            self.assertContains(entry, "Correct collateral details")
            data = dict(facts["after"], **{key: facts[key] for key in ("reason", "reference", "request_key")}, action="preview")
            response = self.client.post(url, data)
            self.assertContains(response, "Review before recording")
            if os.environ.get("LOAN_CORRECTION_QA_CAPTURE"):
                output = Path(os.environ["LOAN_CORRECTION_QA_CAPTURE"])
                output.mkdir(parents=True, exist_ok=True)
                (output / f"{label}-form.html").write_bytes(entry.content)
                (output / f"{label}-review.html").write_bytes(response.content)
            data.update(action="confirm", confirmed="on", review_token=response.context["form"]["review_token"].value())
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 302)
            detail = self.client.get(response["Location"])
            self.assertContains(detail, "Collateral correction history")
            self.assertContains(detail, "Correct gold ring")
            self.assertNotContains(detail, "Correct original paper terms")
            if os.environ.get("LOAN_CORRECTION_QA_CAPTURE"):
                (output / f"{label}-detail.html").write_bytes(detail.content)

    def test_portable_version_six_roundtrip_all_origins_and_old_profile_rejection(self):
        from apps.orgs.models import Company
        from apps.tenancy.context import without_workspace_context
        from apps.tenant_apps.party.models import Party
        from apps.tenant_apps.data_portability.models import PartyIdentity, SourceIdentity
        from apps.tenant_apps.loans.services.license_series import create_license
        from apps.tenant_apps.loans.services.servicing_bundle import export_servicing_bundle, restore_servicing_bundle
        from apps.tenant_apps.loans.services.servicing_bundle_contract import read_bundle, decode
        from apps.tenant_apps.loans.services.history_export import export_history
        from apps.tenant_apps.loans.services.opening_export import export_opening
        self.actor.is_superuser = True
        self.actor.save(update_fields=["is_superuser"])
        for loan in self.loans:
            with self.scoped(), on(self.day):
                self.correct(loan, self.facts(loan, description="Reviewed ring", net_weight=".9"))
                self.correct(loan, self.facts(loan, description="Checked ring twice"))
                if loan == self.paper:
                    from apps.tenant_apps.loans.services.recorded_contract_corrections import preview_contract_correction, record_contract_correction
                    terms = dict(date=self.original.isoformat(), principal="6000", rate="3", cash_paid="5820",
                        reference="Correct original financial terms", reason="Principal and rate were transcribed wrongly", request_key=uuid4().hex)
                    _, token = preview_contract_correction(loan.pk, actor=self.actor, data=terms)
                    record_contract_correction(loan.pk, actor=self.actor, data=terms, review_token=token, confirmed=True)
                    loan.refresh_from_db()
                    self.assertEqual(loan.principal_amount, Decimal("6000"))
                expected = item_details(loan.collateral_items.get())
                with self.assertRaisesMessage(ValueError, "version 6"):
                    (export_opening if loan == self.opening else export_history)(workspace_id=self.a.pk, actor=self.actor, loan_id=loan.pk)
            with self.scoped():
                content = export_servicing_bundle(workspace_id=self.a.pk, actor=self.actor, loan_id=loan.pk)
                document, _ = read_bundle(content)
                self.assertEqual(document["profile"], "loan-servicing-bundle/6")
                row = next(row for row in document["tables"]["LoanChangeLog"] if row["event_kind"] == "COLLATERAL_CORRECTED")
                for profile in range(1, 6):
                    with self.assertRaises(ValueError):
                        decode("LoanChangeLog", row, profile=f"loan-servicing-bundle/{profile}")
                from apps.tenant_apps.loans.services.servicing_collateral import validate_corrections
                tampered = deepcopy(document)
                last = [row for row in tampered["tables"]["LoanChangeLog"] if row["event_kind"] == "COLLATERAL_CORRECTED"][-1]
                last["metadata"]["collateral_correction"]["after"]["net_weight"] = ".1000"
                with self.assertRaises(ValueError):
                    validate_corrections(tampered)
            with without_workspace_context():
                target = Company.objects.create(name="Correction restore " + str(loan.pk), schema_name="correct_" + uuid4().hex,
                    owner=self.actor, creator=self.actor)
            with self.scoped(target):
                source_key = str(loan.pk)
                reference = document["setup"][source_key]["borrower"]
                party = Party.objects.create(display_name="Exact source customer")
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
                self.assertEqual(item_details(restored.collateral_items.get()), expected)
                self.assertEqual(len(validate_correction_chain(restored)[restored.collateral_items.get().pk]), 2)
                again, _ = read_bundle(export_servicing_bundle(workspace_id=target.pk, actor=self.actor, loan_id=restored.pk))
                self.assertEqual(again["positions"][str(restored.pk)]["recorded"], document["positions"][source_key]["recorded"])
                self.assertTrue(restore_servicing_bundle(**args, expected_sha256=preview["sha256"], confirmed=True)["already_restored"])


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class CollateralRecoveryTests(WorkspaceTestCase):
    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history
    row = histories.RecordedHistoryTests.row
    admit = histories.RecordedHistoryTests.admit

    @classmethod
    def get_test_schema_name(cls):
        return "collateral-correction-recovery"

    def setUp(self):
        self.prepare_history()

    def test_exact_workspace_recovery_retains_corrections_and_original_rows(self):
        from apps.tenant_apps.loans.tests.test_pawn_recovery import PawnRecoveryTests
        self.data["events"] = [self.row(amount="2000")]
        loan, _, _ = self.admit()
        item = loan.collateral_items.get()
        facts = dict(item_id=item.pk, after=dict(item_details(item), description="Recovery corrected ring"),
            reference="Actual signed agreement", reason="Description transcribed incorrectly", request_key=uuid4().hex)
        _, token = preview_collateral_correction(loan.pk, actor=self.actor, data=facts)
        record_collateral_correction(loan.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)
        original = PawnRecoveryTests.export(self)
        PawnRecoveryTests.empty(self)
        self.assertTrue(PawnRecoveryTests.restore(self, commit=True)["committed"])
        restored = PawnRecoveryTests.export(self)
        self.assertEqual(original["tables"], restored["tables"])
        validate_correction_chain(loan)
        self.assertEqual(loan.collateral_items.get().description, "Recovery corrected ring")

    def test_new_ticket_copy_uses_corrected_facts_and_original_issue_bytes_remain(self):
        from apps.tenant_apps.loans.services.document_layouts import LoanDocumentLayoutService
        self.start_active_trial()
        loan, _, _ = self.admit()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        url = reverse("workspace_loans:pawn_loan_ticket_pdf", args=[self.tenant.slug, loan.pk])
        original = client.get(url)
        self.assertEqual(original.status_code, 200)
        issue_id = original["X-Rokkad-Document-Issue"]
        item = loan.collateral_items.get()
        facts = dict(item_id=item.pk, after=dict(item_details(item), description="Checked collateral description"),
            reference="Original ticket", reason="Description transcribed wrongly", request_key=uuid4().hex)
        _, token = preview_collateral_correction(loan.pk, actor=self.actor, data=facts)
        record_collateral_correction(loan.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)
        corrected = client.get(url)
        self.assertEqual(corrected.status_code, 200)
        self.assertNotEqual(corrected["X-Rokkad-Document-Issue"], issue_id)
        self.assertNotEqual(corrected.content, original.content)
        self.assertEqual(LoanDocumentLayoutService.read_verified_artifact(m.LoanDocumentIssue.objects.get(pk=issue_id)), original.content)
        self.assertEqual(client.get(url).content, corrected.content)
