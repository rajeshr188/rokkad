import copy
from datetime import date
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.tests.test_opening_import import OpeningImportFixture
from apps.tenant_apps.loans.services.license_series import create_legacy_license_reference, create_license, activate_license, update_license
from apps.tenant_apps.loans.services.history_setup import preview_history_setup
from apps.tenant_apps.loans.services.opening_validation import validate_opening
from apps.tenant_apps.loans.selectors.regulatory import get_loan_license_register
from apps.tenant_apps.loans.selectors.reports import get_pawn_loan_reports
from apps.tenant_apps.loans.services.operational_notices import create_license_expiry_notice


class LegacyEvidenceGapTests(OpeningImportFixture):
    def legacy(self, **changes):
        return create_legacy_license_reference(**dict(workspace=self.a, actor=self.actor,
            name="Historical group", source_label="OLD-GROUP", evidence_reference="Owner: no validity recorded", **changes))

    def test_unknown_validity_requires_inactive_reference_and_isolated_owner(self):
        with self.scoped():
            with self.assertRaises(PermissionDenied):
                create_legacy_license_reference(workspace=self.a, actor=self.other_actor, name="Old",
                    source_label="OLD-GROUP", evidence_reference="Unrecorded")
            legacy = self.legacy()
            self.assertIsNone(legacy.issued_on)
            self.assertIsNone(legacy.expires_on)
            self.assertFalse(legacy.is_active)
            from apps.tenant_apps.loans.services.number_allocation import preview_number
            series = m.LoanSeries.objects.create(license=legacy, name="Old series", code="LG")
            with self.assertRaisesMessage(ValueError, "inactive"):
                preview_number(series=series, document_kind="PAWN_LOAN")
            self.assertEqual(legacy.revisions.get().kind, "LEGACY_REFERENCE")
            for changes in ({"is_active": True}, {"is_legacy_reference": False, "issued_on": date(2020,1,1), "expires_on": date(2030,1,1)}):
                with self.subTest(changes=changes), self.assertRaises(DatabaseError), transaction.atomic():
                    m.LoanLicense.objects.filter(pk=legacy.pk).update(**changes)
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.LoanLicenseRevision.objects.filter(license=legacy).update(notes="changed")
            with self.assertRaises(ValueError):
                activate_license(legacy, actor=self.actor)
            with self.assertRaises(ValueError):
                update_license(legacy, actor=self.actor, name="Verified now")
            with self.assertRaises(ValidationError):
                create_license(workspace=self.a, actor=self.actor, name="Incomplete ordinary licence",
                    license_number="BAD", issued_on=None, expires_on=None)
        with self.scoped(self.b):
            self.assertFalse(m.LoanLicense.objects.filter(pk=legacy.pk).exists())

    def test_reference_register_reports_and_expiry_notice_do_not_claim_validity(self):
        with self.scoped():
            legacy = self.legacy()
            row = next(r for r in get_loan_license_register(self.a.pk) if r.license.pk == legacy.pk)
            self.assertEqual(row.status, "LEGACY_REFERENCE")
            self.assertIsNone(row.days_remaining)
            report = get_pawn_loan_reports(as_of_date=date(2021,1,20))
            self.assertEqual(next(r.status for r in report.license_expiry if r.license.pk == legacy.pk), "LEGACY_REFERENCE")
            with self.assertRaisesMessage(ValueError, "no verified expiry"):
                create_license_expiry_notice(legacy.pk, request_key="never-send", actor=self.actor)

    def test_complete_history_cannot_use_legacy_reference_without_opening_evidence(self):
        with self.scoped():
            legacy = self.legacy()
            series = m.LoanSeries.objects.create(license=legacy, name="Legacy", code="LG")
            with self.assertRaisesMessage(ValueError, "complete history requires"):
                preview_history_setup(workspace_id=self.a.pk, actor=self.actor,
                    revision_id=legacy.revisions.get().pk, series_id=series.pk,
                    product_version_id=self.review["mapping"]["product_version_id"],
                    source_namespace=self.review["source"]["namespace"], source_loan_id="legacy-1",
                    source_loan_number="L1", source_license_number="OLD-GROUP", disbursed_on=date(2021,1,1),
                    tenure_months=3, calculation_contract_version=self.review["terms"]["rule_id"], operational_grace_days=3)

    def test_unverified_valuation_is_explicit_bounded_and_only_v2(self):
        doc = copy.deepcopy(self.review)
        doc["collateral"][0]["valuation"] = dict(status="UNVERIFIED", source_amount="1234", source_date=None, evidence_reference="Old undated source value")
        self.assertTrue(validate_opening(doc)["document_reconciled"])
        for key,value in (("source_amount","-1"),("source_date","2021-02-01"),("evidence_reference",""),("status","APPROVED")):
            bad = copy.deepcopy(doc)
            bad["collateral"][0]["valuation"][key] = value
            self.assertFalse(validate_opening(bad)["document_reconciled"])
        doc["profile"] = "loan-opening-review/1"
        self.assertFalse(validate_opening(doc)["document_reconciled"])

    def test_missing_appraisal_never_allows_partial_collateral_release(self):
        from apps.tenant_apps.loans.selectors.release_readiness import get_pawn_loan_release_readiness
        self.review["collateral"][0]["valuation"] = dict(status="UNVERIFIED", source_amount=None,
            source_date=None, evidence_reference="Source has no usable appraisal")
        second = copy.deepcopy(self.review["collateral"][0])
        second["id"] = "girvi_loanitem:2"
        self.review["collateral"].append(second)
        self.review["source"]["item_ids"].append(second["id"])
        self.review["balances"]["principal"] = self.review["obligations"][0]["principal"] = "2000"
        with self.scoped():
            origin = self.write()
            ids = list(origin.loan.collateral_items.values_list("pk", flat=True))
            partial = get_pawn_loan_release_readiness(origin.loan_id, selected_item_ids=ids[:1], as_of_date=date(2021,1,21))
            self.assertFalse(partial.ready)
            self.assertIn("LATEST_APPRAISAL_REQUIRED", {b.code for b in partial.blockers})
            full = get_pawn_loan_release_readiness(origin.loan_id, selected_item_ids=ids, as_of_date=date(2021,1,21))
            self.assertTrue(full.ready, full.blockers)
            self.assertEqual(full.minimum_settlement, 2000)
