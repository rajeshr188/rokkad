import copy
from datetime import date
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, transaction

from apps.tenant_apps.data_portability.tests.fixtures import PortabilityFixture
from apps.tenant_apps.data_portability.tests.test_loan_history import document as history_document
from apps.tenant_apps.data_portability.models import SourceIdentity
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.history_import import import_complete_history, balance_values
from apps.tenant_apps.loans.services.history_contract import digest
from apps.tenant_apps.loans.services.license_series import create_license
from apps.tenant_apps.loans.services.opening_import import commit_opening_import, preview_opening_import, PROFILE
from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full
from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
from apps.tenant_apps.loans.tests.test_opening_continuation import collection_review


class OpeningImportFixture(PortabilityFixture):
    def setUp(self):
        super().setUp()
        self.review = collection_review()
        self.review["terms"]["maturity_date"] = "2021-04-01"
        self.review["obligations"][0].update(due="2021-04-01", interest="30")
        self.review["collateral"][0].update(metal="BRONZE", gross_weight=None)
        self.review["source"]["borrower_id"] = "old-1"
        self.review["mapping"]["borrower_external_id"] = "old-1"
        with self.scoped():
            self.commit(self.ready(self.stage(system=self.review["mapping"]["borrower_source_system"])))
            self.source_party = SourceIdentity.objects.get(external_id="old-1")
            licence = create_license(workspace=self.a, actor=self.actor, name="Historical", license_number="OLD-L",
                                     issued_on=date(2020, 1, 1), expires_on=date(2022, 1, 1))
            self.series = m.LoanSeries.objects.create(license=licence, name="Historical", code="H")
            product = m.LoanProduct.objects.create(workspace=self.a, code="H", name="Historical")
            version = m.LoanProductVersion.objects.create(product=product, version=1, status="RETIRED",
                repayment_structure="FLEXIBLE_PARTIAL_PAYMENT", amortisation_method="NONE", payment_frequency="FLEXIBLE",
                extra_payment_rule="REDUCE_PRINCIPAL", maximum_tenor_months=12, operational_grace_days=3,
                calculation_contract_version=self.review["terms"]["rule_id"])
            self.review["mapping"].update(workspace_id=self.a.pk, borrower_id=self.source_party.identity.party_id,
                licence_revision_id=licence.revisions.get().pk, series_id=self.series.pk, product_version_id=version.pk)
            self.sequence = m.LoanNumberSequence.objects.create(series=self.series, document_kind="PAWN_LOAN",
                prefix="H-", width=5, maximum_number=10000)
            m.LoanNumberSequence.objects.create(series=self.series, document_kind="PAWN_LOAN_RELEASE",
                prefix="HR-", width=5, maximum_number=10000)
        self.setup = {"tenure_months": 3, "source_license_number": "OLD-L", "policy": history_document()["loan"]["policy"]}
        self.args = {"workspace_id": self.a.pk, "actor": self.actor, "review": self.review, "setup": self.setup}

    def write(self, **changes):
        args = {**self.args, **changes}
        checksum = digest({"profile": PROFILE, "review": args["review"], "setup": args["setup"]})
        return commit_opening_import(**args, expected_sha256=checksum, confirmed=True)[0]


class OpeningImportTests(OpeningImportFixture):
    def test_preview_rolls_back_then_commit_replay_preserves_review_and_no_origination(self):
        with self.scoped():
            before = copy.deepcopy(self.review)
            preview = preview_opening_import(**self.args)
            for model in (m.PawnLoan, m.PawnCollateralItem, m.PawnLoanEvent, m.HistoricalLoanImport, m.CollateralAppraisal):
                self.assertFalse(model.objects.exists())
            origin, summary = commit_opening_import(**self.args, expected_sha256=preview["sha256"], confirmed=True)
            self.assertEqual(summary, preview["summary"])
            self.assertEqual(self.write().pk, origin.pk)
            self.assertEqual(m.PawnLoan.objects.count(), 1)
            self.assertEqual(origin.source_id, "tenant_a:girvi_loan:1")
            self.assertEqual(balance_values(origin.loan, date(2021, 1, 20)), {"principal": "1000", "interest": "0", "fees": "0"})
            self.assertEqual(list(origin.loan.loan_events.values_list("event_kind", flat=True)), ["MIGRATION_OPENING"])
            self.assertFalse(m.PawnLoanApprovalSnapshot.objects.exists())
            self.assertFalse(m.PawnLoanDisbursalSnapshot.objects.exists())
            self.assertFalse(m.PawnCollateralCustodyEvent.objects.exists())
            item = origin.loan.collateral_items.get()
            self.assertIsNone(item.gross_weight)
            self.assertEqual(item.metal, "BRONZE")
            self.assertEqual(item.appraisals.get().method, "MIGRATION_REVIEW")
            self.assertEqual(origin.loan.repayment_schedules.get().maturity_date, date(2021, 4, 1))
            self.sequence.refresh_from_db()
            self.assertEqual(self.sequence.next_number, 1)
            self.assertEqual(self.review, before)

    def test_committed_opening_can_release_reverse_and_retry_import_without_duplicate_debt(self):
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 2)):
            origin = self.write()
            released = release_pawn_loan_in_full(origin.loan_id, settlement_amount=1010,
                request_key="import-release", actor=self.actor)
            self.assertEqual(self.write().pk, origin.pk)
            self.assertEqual(balance_values(origin.loan, date(2021, 2, 2))["principal"], "0")
            reverse_pawn_loan_event(released.loan_event.pk, actor=self.actor, reason="Cancelled handoff")
            self.assertEqual(balance_values(origin.loan, date(2021, 2, 2))["principal"], "1000")

    def test_changed_accepted_review_conflicts_and_confirmation_binds_setup(self):
        with self.scoped():
            preview = preview_opening_import(**self.args)
            with self.assertRaises(ValueError):
                commit_opening_import(**self.args, expected_sha256=preview["sha256"])
            changed = copy.deepcopy(self.setup)
            changed["policy"]["maximum_ltv_ratio"] = "0.7"
            with self.assertRaises(ValueError):
                commit_opening_import(**{**self.args, "setup": changed}, expected_sha256=preview["sha256"], confirmed=True)
            self.write()
            changed = copy.deepcopy(self.review)
            changed["review_reference"] = "Different review"
            with self.assertRaisesMessage(ValueError, "different accepted financial origin"):
                self.write(review=changed)

    def test_missing_terms_source_errors_and_wrong_borrower_are_held_without_writes(self):
        with self.scoped():
            for group, field, value in (("terms", "maturity_date", None), ("source", "errors", ["dispute"]),
                                        ("mapping", "borrower_id", 999999), ("mapping", "workspace_id", self.b.pk)):
                changed = copy.deepcopy(self.review)
                changed[group][field] = value
                with self.subTest(field=field), self.assertRaises(ValueError):
                    self.write(review=changed)
                self.assertFalse(m.PawnLoan.objects.exists())
            with self.assertRaisesMessage(ValueError, "tenure"):
                self.write(setup={**self.setup, "tenure_months": 0})

    def test_late_failure_rolls_back_all_business_and_identity_rows(self):
        with self.scoped():
            with patch("apps.tenant_apps.loans.services.opening_import.AuditLog.log", side_effect=RuntimeError("audit unavailable")):
                with self.assertRaises(RuntimeError):
                    self.write()
            for model in (m.PawnLoan, m.PawnCollateralItem, m.PawnLoanEvent, m.HistoricalLoanImport,
                          m.CollateralAppraisal, m.LoanPolicySnapshot, m.RepaymentScheduleVersion, m.RepaymentObligation):
                self.assertFalse(model.objects.exists())

    def test_authorization_precedes_replay_and_foreign_workspace_is_invisible(self):
        with self.assertRaises(PermissionDenied):
            self.write()
        with self.scoped():
            origin = self.write()
            for actor in (None, self.other_actor):
                with self.assertRaises(PermissionDenied):
                    self.write(actor=actor)
        with self.scoped(self.b):
            self.assertFalse(m.HistoricalLoanImport.objects.filter(pk=origin.pk).exists())
            with self.assertRaises(PermissionDenied):
                self.write()

    def test_origin_evidence_is_immutable_under_restricted_role(self):
        with self.scoped():
            origin = self.write()
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.HistoricalLoanImport.objects.filter(pk=origin.pk).update(source_sha256="d" * 64)
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.PawnLoanEvent.objects.filter(loan=origin.loan).delete()

    def test_complete_history_cannot_add_a_second_origin(self):
        with self.scoped():
            self.write()
            doc = history_document()
            doc["manifest"]["namespace"] = self.review["source"]["namespace"]
            doc["loan"].update(id=self.review["source"]["loan_id"],
                borrower={"source_system": self.review["mapping"]["borrower_source_system"], "id": "old-1"})
            mapping = self.review["mapping"]
            with self.assertRaisesMessage(ValueError, "different accepted history"):
                import_complete_history(workspace_id=self.a.pk, actor=self.actor, document=doc,
                    mapping={"revision_id": mapping["licence_revision_id"], "series_id": mapping["series_id"],
                             "product_version_id": mapping["product_version_id"], "borrower_id": mapping["borrower_id"]})
            self.assertEqual(m.PawnLoan.objects.count(), 1)

    def test_opening_cannot_replace_complete_history_and_legacy_export_replays(self):
        from apps.tenant_apps.loans.services.history_export import export_history
        from apps.tenant_apps.loans.services.history_contract import parse
        with self.scoped():
            doc = history_document()
            doc["manifest"]["namespace"] = self.review["source"]["namespace"]
            doc["loan"].update(id=self.review["source"]["loan_id"], calculation_contract=self.review["terms"]["rule_id"],
                borrower={"source_system": self.review["mapping"]["borrower_source_system"], "id": "old-1"})
            mapping = self.review["mapping"]
            args = dict(workspace_id=self.a.pk, actor=self.actor, document=doc,
                mapping={"revision_id": mapping["licence_revision_id"], "series_id": mapping["series_id"],
                         "product_version_id": mapping["product_version_id"], "borrower_id": mapping["borrower_id"]})
            origin, _ = import_complete_history(**args)
            self.assertEqual(origin.source_id, "tenant_a:girvi_loan:1")
            self.assertEqual(import_complete_history(**args)[0].pk, origin.pk)
            with self.assertRaisesMessage(ValueError, "different accepted financial origin"):
                self.write()
            exported = export_history(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
            # Export returns its canonical bytes and retains the original source key.
            self.assertEqual(parse(exported)["loan"]["id"], self.review["source"]["loan_id"])
            self.assertEqual(m.PawnLoan.objects.count(), 1)

    def test_pre_scoping_complete_identity_still_blocks_opening_and_replays(self):
        with self.scoped():
            doc = history_document()
            doc["manifest"]["namespace"] = self.review["source"]["namespace"]
            doc["loan"].update(id=self.review["source"]["loan_id"], calculation_contract=self.review["terms"]["rule_id"],
                borrower={"source_system": self.review["mapping"]["borrower_source_system"], "id": "old-1"})
            mapping = self.review["mapping"]
            args = dict(workspace_id=self.a.pk, actor=self.actor, document=doc,
                mapping={"revision_id": mapping["licence_revision_id"], "series_id": mapping["series_id"],
                         "product_version_id": mapping["product_version_id"], "borrower_id": mapping["borrower_id"]})
            with patch("apps.tenant_apps.loans.services.history_import.source_binding_id", return_value=doc["loan"]["id"]):
                old, _ = import_complete_history(**args)
            self.assertEqual(import_complete_history(**args)[0].pk, old.pk)
            with self.assertRaisesMessage(ValueError, "different accepted financial origin"):
                self.write()
            old.refresh_from_db()
            self.assertEqual(old.source_id, doc["loan"]["id"])
            self.assertEqual(m.HistoricalLoanImport.objects.count(), 1)

    def test_same_source_key_in_another_schema_is_distinct(self):
        with self.scoped():
            first = self.write()
            review = copy.deepcopy(self.review)
            review["source"]["schema"] = "tenant_b"
            review["mapping"]["borrower_source_system"] = review["mapping"]["borrower_source_system"].replace(":tenant_a", ":tenant_b")
            SourceIdentity.objects.create(workspace=self.a, identity=self.source_party.identity,
                source_system=review["mapping"]["borrower_source_system"], external_id="old-1",
                accepted_digest=self.source_party.accepted_digest, local_digest=self.source_party.local_digest)
            second = self.write(review=review)
            self.assertNotEqual(first.source_id, second.source_id)
            self.assertNotEqual(first.loan.loan_number, second.loan.loan_number)

    def test_existing_number_and_valid_but_wrong_party_mapping_are_rejected(self):
        from apps.tenant_apps.party.models import Party
        with self.scoped():
            other = Party.objects.create(display_name="Unrelated borrower")
            changed = copy.deepcopy(self.review)
            changed["mapping"]["borrower_id"] = other.pk
            with self.assertRaisesMessage(ValueError, "exact source Party"):
                self.write(review=changed)
            preview = preview_opening_import(**self.args)
            mapping = self.review["mapping"]
            m.PawnLoan.objects.create(workspace=self.a, license_id=self.series.license_id,
                license_revision_id=mapping["licence_revision_id"], series=self.series,
                product_version_id=mapping["product_version_id"], borrower_id=mapping["borrower_id"],
                loan_number=preview["summary"]["loan_number"], principal_amount=1000, monthly_interest_rate=1,
                loan_date=date(2021, 1, 1), tenure_months=3)
            with self.assertRaisesMessage(ValueError, "number already exists"):
                self.write()
            self.assertFalse(m.HistoricalLoanImport.objects.exists())
