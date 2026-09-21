import copy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core import signing
from django.core.management import call_command
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, transaction
from django.test import override_settings, Client
from django.urls import reverse

from apps.orgs.models import Membership, WorkspaceRoleGrant
from apps.tenant_apps.loans.models import PawnLoan, HistoricalLoanImport, PawnLoanEvent
from apps.tenant_apps.loans.tests.test_opening_import import OpeningImportFixture
from apps.tenant_apps.data_portability import legacy_opening as bridge, loan_history
from apps.tenant_apps.data_portability.legacy_preview import build_preview, propose_collateral_exclusions
from apps.tenant_apps.data_portability.opening_review import prepare_openings
from apps.tenant_apps.data_portability.legacy_owner_rules import NAMESPACE, MATURITY_EVIDENCE
from apps.tenant_apps.data_portability.models import SourceIdentity, LoanHistoryBatch
from apps.tenant_apps.data_portability.tests.test_legacy_dump import source


class LegacyOpeningTests(OpeningImportFixture):
    def setUp(self):
        super().setUp()
        self.extracted = source("jcl")
        self.extracted["tables"]["girvi_loanitem"]["1"]["itemtype"] = "Bronze"
        summary, records = build_preview(self.extracted, schema="jcl", source_namespace=NAMESPACE)
        propose_collateral_exclusions(summary, records)
        candidate = prepare_openings(summary, records, owner_profile="jcl-owner/2")[0]
        self.review["source"] = candidate["source"]
        for key in ("borrower_source_system", "borrower_external_id"):
            self.review["mapping"][key] = candidate["mapping"][key]
        for key in ("metal", "gross_weight", "net_weight", "purity", "weight_reference"):
            self.review["collateral"][0][key] = candidate["collateral"][0][key]
        with self.scoped():
            SourceIdentity.objects.create(workspace=self.a, identity=self.source_party.identity,
                source_system=summary["source_system"], external_id=candidate["source"]["borrower_id"],
                accepted_digest=self.source_party.accepted_digest, local_digest=self.source_party.local_digest)
        self.extract = self.enterContext(patch.object(bridge, "inspect_archive", return_value=self.extracted))

    def stage_opening(self, **changes):
        return bridge.stage(**{**self.args, "archive_path": "synthetic.dump", **changes})

    def test_versioned_profile_staging_preserves_ledger_and_rejects_source_drift(self):
        tables = self.extracted["tables"]
        tables["girvi_loan"]["29887"] = {**tables["girvi_loan"]["1"], "id": "29887",
            "loan_id": "R09911", "loan_date": "2026-12-16 09:47:00+00"}
        tables["girvi_loanitem"]["29887"] = {**tables["girvi_loanitem"]["1"], "id": "29887", "loan_id": "29887"}
        summary, records = build_preview(self.extracted, schema="jcl", source_namespace=NAMESPACE,
                                         source_profile="linode-jcl/1")
        propose_collateral_exclusions(summary, records)
        candidate = prepare_openings(summary, records, owner_profile="linode-owner/1")[0]
        self.review["source"] = candidate["source"]
        self.review["collateral"][0]["weight_reference"] = candidate["collateral"][0]["weight_reference"]
        with self.scoped():
            batch = self.stage_opening(source_profile="linode-jcl/1")
            self.assertEqual(batch.document["source_evidence"]["source_profile"], "linode-jcl/1")
            many = bridge.stage_many(workspace_id=self.a.pk, actor=self.actor, archive_path="synthetic.dump",
                openings=[{"review": self.review, "setup": self.setup}], source_profile="linode-jcl/1")
            self.assertEqual(many[0].document, batch.document)
            tables["girvi_loan"]["29887"]["loan_date"] = "2024-12-16 09:47:00+00"
            with self.assertRaisesMessage(ValueError, "does not match"):
                self.stage_opening(source_profile="linode-jcl/1")
            self.assertEqual(LoanHistoryBatch.objects.count(), 2)
            self.assertFalse(PawnLoan.objects.exists())

    def test_versioned_profile_cannot_cross_source_schema(self):
        with self.scoped(), self.assertRaisesMessage(ValueError, "does not match"):
            self.stage_opening(source_profile="linode-jsk/1")
        with self.scoped():
            self.assertFalse(LoanHistoryBatch.objects.exists())

    def test_confirmed_linode_profiles_stage_commit_and_replay_with_canonical_parties(self):
        from uuid import UUID, uuid5
        self.extracted["tables"]["girvi_loanitem"]["1"]["itemdesc"] = "Ring\nchain\tPendant"
        for schema, profile in (("jsk", "linode-jsk/1"), ("lakshmipawnbroker", "linode-lakshmi/1")):
            self.extracted["source_schema"] = schema
            self.extracted["schemas"] = {schema: list(self.extracted["tables"])}
            summary, records = build_preview(self.extracted, schema=schema, source_namespace=NAMESPACE, source_profile=profile)
            propose_collateral_exclusions(summary, records)
            candidate = prepare_openings(summary, records, owner_profile="linode-owner/1")[0]
            review = copy.deepcopy(self.review)
            review["source"] = candidate["source"]
            for key in ("borrower_source_system", "borrower_external_id"):
                review["mapping"][key] = candidate["mapping"][key]
            review["collateral"][0]["weight_reference"] = candidate["collateral"][0]["weight_reference"]
            review["collateral"][0]["description"] = candidate["collateral"][0]["description"]
            with self.scoped():
                SourceIdentity.objects.create(identity=self.source_party.identity,
                    source_system=summary["source_system"],
                    external_id=str(uuid5(uuid5(UUID(NAMESPACE), schema), "contact_customer:1")),
                    accepted_digest=self.source_party.accepted_digest, local_digest=self.source_party.local_digest)
                batch = self.stage_opening(review=review, source_profile=profile)
                self.assertEqual(batch.document["source_evidence"]["owner_profile"], "linode-owner/1")
                transformation = batch.document["source_evidence"]["transformations"][0]
                self.assertEqual(transformation["before"], "Ring\nchain\tPendant")
                self.assertEqual(transformation["after"], "Ring chain Pendant")
                forged = copy.deepcopy(review)
                forged["collateral"][0]["description"] = "A different item"
                with self.assertRaisesMessage(ValueError, "preserve the verified source facts"):
                    self.stage_opening(review=forged, source_profile=profile)
                approval = bridge.preview(**self.batch_args(batch))
                result = bridge.commit(**self.batch_args(batch), approval=approval, confirmed=True)
                self.assertEqual(bridge.commit(**self.batch_args(batch), approval=approval, confirmed=True), result)
        with self.scoped():
            self.assertEqual(PawnLoan.objects.count(), 2)

    def many_inputs(self):
        tables = self.extracted["tables"]
        tables["girvi_loan"]["2"] = {**tables["girvi_loan"]["1"], "id": "2", "loan_id": "A00002"}
        tables["girvi_loanitem"]["2"] = {**tables["girvi_loanitem"]["1"], "id": "2", "loan_id": "2"}
        summary, records = build_preview(self.extracted, schema="jcl", source_namespace=NAMESPACE)
        propose_collateral_exclusions(summary, records)
        inputs = []
        for candidate in prepare_openings(summary, records, owner_profile="jcl-owner/2"):
            review = copy.deepcopy(self.review)
            review["source"] = candidate["source"]
            review["collateral"][0]["id"] = candidate["collateral"][0]["id"]
            inputs.append({"review": review, "setup": copy.deepcopy(self.setup)})
        return inputs

    def test_bounded_staging_extracts_once_and_preserves_per_loan_approval(self):
        inputs = self.many_inputs()
        with self.scoped():
            batches = bridge.stage_many(workspace_id=self.a.pk, actor=self.actor,
                archive_path="synthetic.dump", openings=inputs)
            self.assertEqual(self.extract.call_count, 1)
            self.assertEqual(len(batches), 2)
            self.assertFalse(PawnLoan.objects.exists())
            for batch, prepared in zip(batches, inputs):
                self.assertEqual(batch.document["source_evidence"], bridge.source_evidence(
                    archive_path="synthetic.dump", **prepared))
                approval = bridge.preview(**self.batch_args(batch))
                result = bridge.commit(**self.batch_args(batch), approval=approval, confirmed=True)
                self.assertEqual(bridge.commit(**self.batch_args(batch), approval=approval, confirmed=True), result)
            self.assertEqual(PawnLoan.objects.count(), 2)

    def test_bounded_staging_late_source_failure_creates_no_batches(self):
        inputs = self.many_inputs()
        inputs[1]["review"]["source"]["archive_sha256"] = "b" * 64
        with self.scoped(), self.assertRaises(ValueError):
            bridge.stage_many(workspace_id=self.a.pk, actor=self.actor,
                archive_path="synthetic.dump", openings=inputs)
        with self.scoped():
            self.assertFalse(LoanHistoryBatch.objects.exists())
            self.assertFalse(PawnLoan.objects.exists())

    def test_bounded_staging_limits_duplicates_and_authorization_before_source_access(self):
        inputs = self.many_inputs()
        with self.scoped():
            for invalid in ([], inputs * 11, [inputs[0], inputs[0]]):
                with self.assertRaises(ValueError):
                    bridge.stage_many(workspace_id=self.a.pk, actor=self.actor,
                        archive_path="synthetic.dump", openings=invalid)
            with self.assertRaises(PermissionDenied):
                bridge.stage_many(workspace_id=self.a.pk, actor=self.other_actor,
                    archive_path="synthetic.dump", openings=inputs)
            self.assertFalse(LoanHistoryBatch.objects.exists())
        self.extract.assert_not_called()

    def test_staging_preserves_legacy_label_and_unverified_source_value_without_promoting_it(self):
        from apps.tenant_apps.loans.services.license_series import create_legacy_license_reference
        from apps.tenant_apps.loans.models import LoanSeries, CollateralAppraisal
        label = self.extracted["tables"]["girvi_license"]["1"]["name"]
        old_value = self.extracted["tables"]["girvi_loan"]["1"]["value"]
        with self.scoped():
            licence = create_legacy_license_reference(workspace=self.a, actor=self.actor, name="Old grouping",
                source_label=label, evidence_reference="Owner confirms unrecorded licence validity")
            series = LoanSeries.objects.create(license=licence, name="Old series", code="LG")
            self.review["mapping"].update(licence_revision_id=licence.revisions.get().pk, series_id=series.pk)
            self.setup.update(source_license_number=label, legacy_license_evidence="Owner confirms unrecorded licence validity")
            self.review["collateral"][0]["valuation"] = dict(status="UNVERIFIED", source_amount=old_value,
                source_date=None, evidence_reference="Owner confirms old undated value")
            for key, value in (("source_amount", "9999"), ("source_date", "2021-01-01")):
                forged = copy.deepcopy(self.review)
                forged["collateral"][0]["valuation"][key] = value
                with self.subTest(key=key), self.assertRaises(ValueError):
                    self.stage_opening(review=forged)
            batch = self.stage_opening()
            approval = bridge.preview(**self.batch_args(batch))
            origin = bridge.commit(**self.batch_args(batch), approval=approval, confirmed=True)
            self.assertFalse(CollateralAppraisal.objects.exists())
            self.assertEqual(origin.document["review"]["collateral"][0]["valuation"]["source_amount"], old_value)

    def batch_args(self, batch):
        return {"workspace_id": self.a.pk, "actor": self.actor, "batch_id": batch.public_id}

    def test_source_staging_preview_commit_retry_and_profile_separation(self):
        with self.scoped():
            batch = self.stage_opening()
            self.extract.assert_called_once_with("synthetic.dump", schema="jcl", pg_restore="pg_restore")
            self.assertEqual(batch.profile, bridge.PROFILE)
            self.assertEqual(len(batch.document["source_evidence"]["records"]), 5)
            self.assertFalse(PawnLoan.objects.exists())
            with self.assertRaises(PermissionDenied):
                loan_history.get_batch(**self.batch_args(batch))
            approval = bridge.preview(**self.batch_args(batch))
            self.assertFalse(PawnLoan.objects.exists())
            origin = bridge.commit(**self.batch_args(batch), approval=approval, confirmed=True)
            self.assertEqual(bridge.commit(**self.batch_args(batch), approval=approval, confirmed=True).pk, origin.pk)
            self.assertEqual(PawnLoan.objects.count(), 1)
            self.assertEqual(list(PawnLoanEvent.objects.values_list("event_kind", flat=True)), ["MIGRATION_OPENING"])
            from apps.tenant_apps.loans.services.opening_export import export_opening
            exported = export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
            evidence = json.loads(exported.splitlines()[1])
            self.assertEqual(evidence["source_verifications"], [{"batch": str(batch.public_id),
                "source_evidence": batch.document["source_evidence"]}])
            self.assertEqual(origin.document["review"], self.review)

    def test_forged_archive_selection_or_source_facts_cannot_stage(self):
        with self.scoped():
            for group, key, value in (("source", "archive_sha256", "b" * 64), ("source", "selection_sha256", "c" * 64),
                                       ("source", "number", "forged"), ("collateral", "net_weight", "11")):
                doc = copy.deepcopy(self.review)
                (doc[group][0] if group == "collateral" else doc[group])[key] = value
                with self.subTest(field=key), self.assertRaises(ValueError):
                    self.stage_opening(review=doc)
                self.assertFalse(LoanHistoryBatch.objects.exists())
                self.assertFalse(PawnLoan.objects.exists())

    def test_approval_requires_confirmation_exact_operator_batch_and_fresh_signature(self):
        with self.scoped():
            batch = self.stage_opening()
            args = self.batch_args(batch)
            approval = bridge.preview(**args)
            with self.assertRaises(ValueError):
                bridge.commit(**args, approval=approval)
            with self.assertRaises(ValueError):
                bridge.commit(**args, approval=approval + "tampered", confirmed=True)
            with patch("django.core.signing.time.time", return_value=10**12), self.assertRaises(ValueError):
                bridge.commit(**args, approval=approval, confirmed=True)
            other = self.stage_opening()
            with self.assertRaises(PermissionDenied):
                bridge.commit(**self.batch_args(other), approval=approval, confirmed=True)
            token = signing.loads(approval, salt=bridge.SALT)
            token["actor"] = self.other_actor.pk
            with self.assertRaises(PermissionDenied):
                bridge.commit(**args, approval=signing.dumps(token, salt=bridge.SALT), confirmed=True)
            self.assertFalse(PawnLoan.objects.exists())

    def test_staged_source_profile_and_completed_records_are_immutable(self):
        with self.scoped():
            batch = self.stage_opening()
            for fields in ({"profile": "loan-history/1"}, {"document": {}}, {"source_sha256": "b" * 64}):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    LoanHistoryBatch.objects.filter(pk=batch.pk).update(**fields)
            approval = bridge.preview(**self.batch_args(batch))
            bridge.commit(**self.batch_args(batch), approval=approval, confirmed=True)
            with self.assertRaises(DatabaseError), transaction.atomic():
                LoanHistoryBatch.objects.filter(pk=batch.pk).update(preview={})
            with self.assertRaises(ValueError):
                bridge.cancel(**self.batch_args(batch), confirmed=True)

    def test_stale_preview_rolls_back_the_financial_commit(self):
        with self.scoped():
            batch = self.stage_opening()
            approval = bridge.preview(**self.batch_args(batch))
            from apps.tenant_apps.party.models import Party
            Party.objects.filter(pk=self.review["mapping"]["borrower_id"]).update(display_name="Changed borrower name")
            with self.assertRaisesMessage(ValueError, "Destination changed"):
                bridge.commit(**self.batch_args(batch), approval=approval, confirmed=True)
            self.assertFalse(PawnLoan.objects.exists())
            self.assertFalse(HistoricalLoanImport.objects.exists())
            batch.refresh_from_db()
            self.assertEqual(batch.state, "READY")

    def test_cancel_erases_staging_only_and_remains_in_correct_profile(self):
        with self.scoped():
            batch = self.stage_opening()
            args = self.batch_args(batch)
            approval = bridge.preview(**args)
            bridge.cancel(**args, confirmed=True)
            bridge.cancel(**args, confirmed=True)
            batch = bridge.get_batch(**args)
            self.assertEqual((batch.state, batch.document, batch.preview), ("CANCELLED", {}, {}))
            with self.assertRaises(ValueError):
                bridge.commit(**args, approval=approval, confirmed=True)
            self.assertFalse(PawnLoan.objects.exists())

    def test_scope_and_revocation_are_rechecked_on_completed_replay(self):
        with self.scoped():
            batch = self.stage_opening()
            approval = bridge.preview(**self.batch_args(batch))
            bridge.commit(**self.batch_args(batch), approval=approval, confirmed=True)
            membership = Membership.objects.get(company=self.a, user=self.actor)
            WorkspaceRoleGrant.objects.filter(workspace_id=self.a.pk, workspace_role__role_id=membership.role_id,
                                               permission__codename="data_import").delete()
            with self.assertRaises(PermissionDenied):
                bridge.commit(**self.batch_args(batch), approval=approval, confirmed=True)
        with self.scoped(self.b):
            self.assertFalse(LoanHistoryBatch.objects.filter(pk=batch.pk).exists())
            with self.assertRaises(PermissionDenied):
                bridge.get_batch(workspace_id=self.b.pk, actor=self.actor, batch_id=batch.public_id)

    def test_unauthorized_staging_never_reads_dump_and_missing_tenure_requires_owner_evidence(self):
        with self.scoped():
            with self.assertRaises(PermissionDenied):
                self.stage_opening(actor=self.other_actor)
            self.extract.assert_not_called()
            self.extracted["tables"]["girvi_loan"]["1"]["tenure"] = "0"
            summary, records = build_preview(self.extracted, schema="jcl", source_namespace=NAMESPACE)
            propose_collateral_exclusions(summary, records)
            self.review["source"] = prepare_openings(summary, records, owner_profile="jcl-owner/2")[0]["source"]
            with self.assertRaisesMessage(ValueError, "explicit owner three-month"):
                self.stage_opening()
            self.assertFalse(LoanHistoryBatch.objects.exists())
            self.assertFalse(PawnLoan.objects.exists())
            self.review["terms"]["evidence_reference"] += "; " + MATURITY_EVIDENCE
            batch = self.stage_opening()
            evidence = batch.document["source_evidence"]["maturity_review"]
            self.assertEqual(evidence["source_tenure"], "0")
            self.assertEqual(evidence["basis"], "OWNER_MISSING_MATURITY_RULE")
            approval = bridge.preview(**self.batch_args(batch))
            origin = bridge.commit(**self.batch_args(batch), approval=approval, confirmed=True)
            self.assertEqual(origin.loan.tenure_months, 3)
            self.assertEqual(origin.loan.repayment_schedules.get().maturity_date.isoformat(), "2021-04-01")
            from apps.tenant_apps.loans.services.opening_export import export_opening
            exported = json.loads(export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id).splitlines()[1])
            self.assertEqual(exported["source_verifications"][0]["source_evidence"]["maturity_review"], evidence)
            self.assertEqual(bridge.commit(**self.batch_args(batch), approval=approval, confirmed=True).pk, origin.pk)

    def test_recorded_longer_tenure_is_not_replaced_by_fallback(self):
        self.extracted["tables"]["girvi_loan"]["1"]["tenure"] = "6"
        summary, records = build_preview(self.extracted, schema="jcl", source_namespace=NAMESPACE)
        propose_collateral_exclusions(summary, records)
        self.review["source"] = prepare_openings(summary, records, owner_profile="jcl-owner/2")[0]["source"]
        self.review["terms"]["evidence_reference"] += "; " + MATURITY_EVIDENCE
        with self.scoped():
            with self.assertRaisesMessage(ValueError, "preserve recorded terms"):
                self.stage_opening()
            self.assertFalse(LoanHistoryBatch.objects.exists())
            self.setup["tenure_months"] = 6
            self.review["terms"]["maturity_date"] = self.review["obligations"][0]["due"] = "2021-07-01"
            batch = self.stage_opening()
            self.assertEqual(batch.document["source_evidence"]["maturity_review"]["basis"], "RECORDED_TENURE")
            self.assertEqual(batch.document["source_evidence"]["maturity_review"]["maturity_date"], "2021-07-01")

    def test_missing_maturity_uses_calendar_months_from_original_date(self):
        raw = self.extracted["tables"]["girvi_loan"]["1"]
        raw.update(tenure="0", loan_date="2021-01-31T00:00:00+00:00")
        summary, records = build_preview(self.extracted, schema="jcl", source_namespace=NAMESPACE)
        propose_collateral_exclusions(summary, records)
        self.review["source"] = prepare_openings(summary, records, owner_profile="jcl-owner/2")[0]["source"]
        self.review["terms"].update(original_date="2021-01-31", billing_anchor="2021-01-31",
            maturity_date="2021-04-30", evidence_reference=MATURITY_EVIDENCE)
        self.review["cutover"]["date"] = "2021-02-10"
        self.review["continuation"]["covered_through"] = "2021-02-10"
        self.review["collateral"][0]["valuation"]["date"] = "2021-02-10"
        self.review["obligations"][0]["due"] = "2021-04-30"
        with self.scoped():
            batch = self.stage_opening()
            approval = bridge.preview(**self.batch_args(batch))
            origin = bridge.commit(**self.batch_args(batch), approval=approval, confirmed=True)
            self.assertEqual(origin.loan.repayment_schedules.get().maturity_date.isoformat(), "2021-04-30")
            self.assertEqual(origin.document["review"]["terms"]["billing_anchor"], "2021-01-31")

    def test_operator_command_stages_one_review_and_prints_browser_route(self):
        with self.scoped(), TemporaryDirectory() as directory:
            path = Path(directory) / "prepared.jsonl"
            path.write_text(json.dumps({"profile": "loan-opening-commit/1", "review": self.review, "setup": self.setup}) + "\n", encoding="utf-8")
            output = io.StringIO()
            call_command("stage_legacy_opening", workspace_id=self.a.pk, actor_id=self.actor.pk,
                dump="synthetic.dump", opening_file=str(path), stdout=output)
            self.assertIn("No loan imported", output.getvalue())
            self.assertIn("/openings/", output.getvalue())
            self.assertEqual(LoanHistoryBatch.objects.count(), 1)
            self.assertFalse(PawnLoan.objects.exists())

    @override_settings(ALLOWED_HOSTS=["testserver"], STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_browser_review_explicit_confirmation_and_csrf(self):
        from types import SimpleNamespace
        from apps.tenancy.testing import WorkspaceTestCase
        WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=self.a))
        with self.scoped():
            batch = self.stage_opening()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        url = reverse("workspace_portability:opening_batch", kwargs={"workspace_slug": self.a.slug, "batch_id": batch.public_id})
        page = client.get(url)
        self.assertContains(page, "A00001")
        self.assertContains(page, "Not recorded")
        self.assertContains(page, "Bronze")
        self.assertContains(page, "Destination licence: OLD-L")
        self.assertIn("no-store", page["Cache-Control"])
        self.assertEqual(client.post(url, {"action": "preview"}).status_code, 403)
        csrf = {"csrfmiddlewaretoken": client.cookies["csrftoken"].value}
        preview = client.post(url, {**csrf, "action": "preview"})
        self.assertContains(preview, "Import reviewed opening")
        token = preview.context["approval"]
        with self.scoped():
            self.assertFalse(PawnLoan.objects.exists())
        self.assertContains(client.post(url, {**csrf, "action": "commit", "approval": token}), "Confirm the selected")
        result = client.post(url, {**csrf, "action": "commit", "approval": token, "confirmed": "yes"})
        self.assertEqual(result.status_code, 302)
        self.assertContains(client.get(url), "Open imported loan")
        self.assertContains(client.get(reverse("workspace_portability:opening_list", kwargs={"workspace_slug": self.a.slug})), "A00001")
