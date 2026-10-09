"""Batching retains single-loan admission and numbering safeguards."""
from copy import deepcopy
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import TransactionTestCase

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.archive import accept_evidence
from apps.tenant_apps.loans.services.closed_position_batch import review_closed_position_batch, apply_closed_position_batch
from apps.tenant_apps.loans.services.history_contract import digest
from .test_closed_position_admission import ClosedPositionAdmissionTests
from .test_recorded_origination import RecordedOriginationTests


class ClosedPositionBatchTests(RecordedOriginationTests):
    prepare_history = ClosedPositionAdmissionTests.prepare_history
    prepare_position = ClosedPositionAdmissionTests.prepare_position
    retain_source = ClosedPositionAdmissionTests.retain_source

    def setUp(self):
        super().setUp()
        self.prepare_position()
        self.prepare_batch()

    def prepare_batch(self):
        self.retain_source()
        self.second = deepcopy(self.document)
        self.second["source"]["loan_id"] = "loan-11"
        self.second["loan"]["number"] = "P-0011"
        self.second["retained_evidence"]["source"]["loan_id"] = "loan-11"
        self.second["retained_evidence"]["facts"]["loan_number"] = "P-0011"
        evidence = accept_evidence(workspace_id=self.tenant.pk, actor=self.actor,
            document=self.second["retained_evidence"], expected_sha256=digest(self.second["retained_evidence"]), confirmed=True)
        self.candidates = [dict(document=self.document, **{k:v for k,v in self.mapping.items() if k not in ("workspace_id", "actor")}),
            dict(document=self.second, borrower_id=self.data["borrower_id"], series_id=self.series.pk, evidence_id=str(evidence.public_id))]
        self.batch_mapping = dict(workspace_id=self.tenant.pk, actor=self.actor)

    def review_batch(self):
        return review_closed_position_batch(candidates=self.candidates, **self.batch_mapping)

    def apply_batch(self, manifest, token, **kwargs):
        return apply_closed_position_batch(manifest=manifest, review_token=token,
            confirmed=True, **self.batch_mapping, **kwargs)

    def test_review_consumes_nothing_and_interrupted_chunks_resume_idempotently(self):
        before = m.PawnLoan.objects.count()
        manifest, token = self.review_batch()
        self.assertEqual(m.PawnLoan.objects.count(), before)
        self.seq.refresh_from_db(); self.assertEqual(self.seq.next_number, 1)
        first = self.apply_batch(manifest, token, start=0, limit=1)
        self.assertEqual((first["created"], first["next_start"]), (1, 1))
        replay = self.apply_batch(manifest, token, start=0, limit=1)
        self.assertEqual((replay["created"], replay["already_admitted"]), (0, 1))
        last = self.apply_batch(manifest, token, start=1, limit=1)
        self.assertEqual(last["created"], 1)
        self.assertEqual(m.PawnLoan.objects.count(), before + 2)
        self.seq.refresh_from_db(); self.assertEqual(self.seq.next_number, 12)
        self.assertEqual(m.PawnLoanEvent.objects.filter(loan__is_imported_closed_position=True).count(), 2)

    def test_failure_in_second_entry_rolls_back_entire_chunk_and_counters(self):
        manifest, token = self.review_batch()
        from apps.tenant_apps.loans.services import closed_position as admission
        original = admission._write
        def fail_second(workspace, series, actor, accepted, **kwargs):
            if accepted["position"]["loan"]["number"] == "P-0011":
                raise ValueError("Injected final-entry failure")
            return original(workspace, series, actor, accepted, **kwargs)
        before = m.PawnLoan.objects.count()
        with patch.object(admission, "_write", side_effect=fail_second), self.assertRaises(ValueError):
            self.apply_batch(manifest, token)
        self.assertEqual(m.PawnLoan.objects.count(), before)
        self.seq.refresh_from_db(); self.assertEqual(self.seq.next_number, 1)
        self.assertEqual(self.apply_batch(manifest, token)["created"], 2)

    def test_tampered_manifest_and_wrong_actor_are_refused(self):
        manifest, token = self.review_batch()
        changed = deepcopy(manifest); changed["entries"][0]["borrower_id"] += 1
        with self.assertRaises(ValueError): self.apply_batch(changed, token)
        changed = deepcopy(manifest); changed["workspace_id"] += 1
        with self.assertRaises(ValueError): self.apply_batch(changed, token)
        with self.assertRaises(ValueError): self.apply_batch(manifest, token, limit=101)
        with self.assertRaises(ValueError): self.apply_batch(manifest, token, start=-1)

    def test_duplicated_sources_and_number_aliases_are_refused_during_review(self):
        for candidates in ([self.candidates[0], self.candidates[0]],):
            with self.assertRaises(ValueError):
                review_closed_position_batch(candidates=candidates, **self.batch_mapping)
        self.seq.refresh_from_db(); self.assertEqual(self.seq.next_number, 1)

    def test_authority_is_checked_again_for_each_resume(self):
        manifest, token = self.review_batch()
        self.apply_batch(manifest, token, limit=1)
        from apps.tenant_apps.loans.services import closed_position_batch as batch
        with patch.object(batch, "require_history_setup_access", side_effect=PermissionDenied("Owner access changed")), self.assertRaises(PermissionDenied):
            self.apply_batch(manifest, token, start=1, limit=1)
        self.assertEqual(m.PawnLoan.objects.filter(is_imported_closed_position=True).count(), 1)

    def test_new_current_number_conflict_after_review_is_not_bypassed_by_signature(self):
        manifest, token = self.review_batch()
        loan = self.make_snapshot(save=False).loan
        m.PawnLoan.objects.filter(pk=loan.pk).update(loan_number="p-0011")
        with self.assertRaises(ValueError): self.apply_batch(manifest, token)
        self.assertFalse(m.PawnLoan.objects.filter(is_imported_closed_position=True).exists())

    def test_added_source_snapshot_invalidates_previous_review(self):
        manifest, token = self.review_batch()
        changed = deepcopy(self.second["retained_evidence"])
        changed["facts"]["borrower_name"] = "Source corrected display"
        accept_evidence(workspace_id=self.tenant.pk, actor=self.actor, document=changed,
            expected_sha256=digest(changed), confirmed=True)
        with self.assertRaises(ValueError): self.apply_batch(manifest, token)
        self.assertFalse(m.PawnLoan.objects.filter(is_imported_closed_position=True).exists())

    def test_expired_review_can_be_refreshed_without_changing_existing_accepted_positions(self):
        from apps.tenant_apps.loans.management.commands.convert_legacy_closed_positions import unchanged_manifest_candidates
        manifest, token = self.review_batch()
        self.apply_batch(manifest, token, limit=1)
        with patch("django.core.signing.time.time", return_value=9999999999), self.assertRaises(ValueError):
            self.apply_batch(manifest, token, start=1, limit=1)
        renewed, token = review_closed_position_batch(**self.batch_mapping,
            candidates=unchanged_manifest_candidates(self.tenant.pk, self.actor, manifest))
        self.assertEqual([e["accepted_sha256"] for e in manifest["entries"]],
            [e["accepted_sha256"] for e in renewed["entries"]])
        result = self.apply_batch(renewed, token)
        self.assertEqual((result["created"], result["already_admitted"]), (1, 1))


class ClosedPositionBatchConcurrencyTests(TransactionTestCase):
    make_snapshot = RecordedOriginationTests.make_snapshot
    prepare_history = ClosedPositionBatchTests.prepare_history
    prepare_position = ClosedPositionBatchTests.prepare_position
    prepare_batch = ClosedPositionBatchTests.prepare_batch
    retain_source = ClosedPositionBatchTests.retain_source

    def start_active_trial(self):
        from apps.tenancy.testing import start_workspace_trial
        return start_workspace_trial(self.tenant)

    def setUp(self):
        from uuid import uuid4
        from django.contrib.auth import get_user_model
        from apps.orgs.models import Company, Membership, Role
        from apps.tenancy.context import workspace_context
        self.actor = get_user_model().objects.create_user(username="closed-batch-race-" + uuid4().hex)
        self.tenant = Company.objects.create(name="Closed batch concurrency", schema_name="closed-" + uuid4().hex,
            owner=self.actor, creator=self.actor)
        Membership.objects.create(user=self.actor, company=self.tenant, role=Role.objects.get_or_create(name="Owner")[0])
        with workspace_context(self.tenant.pk):
            self.prepare_position(); self.prepare_batch()
        self.manifest, self.token = review_closed_position_batch(candidates=self.candidates, **self.batch_mapping)

    def test_concurrent_replay_commits_one_position_per_source(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        from apps.tenancy.context import workspace_context
        ready = Barrier(2)
        def submit(_):
            try:
                ready.wait(timeout=15)
                return apply_closed_position_batch(manifest=self.manifest, review_token=self.token,
                    confirmed=True, **self.batch_mapping)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(submit, range(2)))
        self.assertEqual(sorted(r["created"] for r in results), [0, 2])
        self.assertEqual(sorted(r["already_admitted"] for r in results), [0, 2])
        with workspace_context(self.tenant.pk):
            self.assertEqual(m.PawnLoan.objects.filter(is_imported_closed_position=True).count(), 2)
            self.assertEqual(m.PawnLoanEvent.objects.filter(loan__is_imported_closed_position=True).count(), 2)
            self.seq.refresh_from_db(); self.assertEqual(self.seq.next_number, 12)
