"""Migration evidence must not weaken native origination or invent metal values."""
import copy
from datetime import date
from decimal import Decimal
from unittest.mock import Mock

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from apps.tenant_apps.loans.forms import PawnCollateralDraftForm
from apps.tenant_apps.loans.models import PawnCollateralItem
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from apps.tenant_apps.loans.services.opening_validation import validate_opening
from apps.tenant_apps.loans.services.pawn_release import preview_pawn_loan_full_release
from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
from apps.tenant_apps.loans.tests.test_opening_continuation import collection_review
from apps.tenant_apps.loans.tests.test_opening_release import OpeningReleaseFixture
from apps.tenant_apps.loans.tests.test_opening_validation import reviewed_opening


class LegacyCollateralReviewTests(SimpleTestCase):
    def test_v2_preserves_unknown_gross_and_distinct_bronze(self):
        doc = collection_review()
        doc["collateral"][0].update(gross_weight=None, metal="BRONZE")
        before = copy.deepcopy(doc)
        self.assertTrue(validate_opening(doc)["document_reconciled"])
        self.assertFalse(validate_opening(doc)["import_ready"])
        self.assertEqual(doc, before)
        for field, value in (("gross_weight", "0"), ("gross_weight", "8"),
                             ("gross_weight", "NaN"), ("gross_weight", ""),
                             ("net_weight", None), ("purity", None),
                             ("weight_reference", None), ("metal", "Copper"),
                             ("valuation", None), ("custody_reference", None)):
            changed = copy.deepcopy(doc)
            changed["collateral"][0][field] = value
            with self.subTest(field=field, value=value):
                self.assertFalse(validate_opening(changed)["document_reconciled"])

    def test_v1_stays_strict_and_missing_due_dates_still_hold_v2(self):
        for updates in ({"gross_weight": None}, {"metal": "BRONZE"}):
            doc = reviewed_opening()
            doc["collateral"][0].update(updates)
            self.assertFalse(validate_opening(doc)["document_reconciled"])
        for group, field in (("terms", "maturity_date"), ("obligations", "due")):
            doc = collection_review()
            target = doc[group][0] if group == "obligations" else doc[group]
            target[field] = None
            result = validate_opening(doc)
            self.assertFalse(result["document_reconciled"])
            self.assertIn("DATE_REQUIRED", {i["code"] for i in result["issues"]})


class NetOnlyBronzeServicingTests(OpeningReleaseFixture):
    def review_document(self):
        doc = super().review_document()
        doc["collateral"][0].update(gross_weight=None, metal="BRONZE")
        return doc

    def test_release_and_reversal_keep_net_only_source_evidence(self):
        self.item.refresh_from_db()
        self.assertIsNone(self.item.gross_weight)
        self.assertEqual((self.item.metal, self.item.net_weight, self.item.purity_percentage),
                         ("BRONZE", Decimal("9"), Decimal("90")))
        from apps.tenant_apps.loans.selectors import release_readiness
        lookup = Mock(wraps=release_readiness.get_latest_commodity_valuation_rate)
        readiness = release_readiness.calculate_pawn_loan_release_readiness(
            self.loan, collateral_items=(self.item,),
            balance=get_pawn_loan_balance(self.loan.pk, as_of_date=self.day),
            policy_snapshot=self.loan.policy_snapshot, selected_item_ids=(self.item.pk,),
            as_of_date=self.day, rate_resolver=lookup, appraisal_values={self.item.pk: Decimal("2000")})
        # Bronze's missing commodity quote cannot be replaced with a precious-metal rate.
        self.assertTrue(lookup.called)
        self.assertEqual({c.kwargs["commodity_code"] for c in lookup.call_args_list}, {"BRONZE"})
        self.assertIsNone(readiness.item_valuations[0].calculated_metal_value)
        self.assertEqual(readiness.item_valuations[0].valuation_amount, 2000)
        self.assertEqual(preview_pawn_loan_full_release(self.loan.pk).minimum_settlement, 1010)
        result = self.release()
        self.assertTrue(get_pawn_loan_balance(self.loan.pk, as_of_date=self.day).closure_ready)
        self.day = date(2021, 2, 3)
        reverse_pawn_loan_event(result.loan_event.pk, actor=self.actor, reason="Cancelled return")
        self.item.refresh_from_db()
        self.assertEqual(self.item.custody_state, "IN_VAULT")
        self.assertIsNone(self.item.gross_weight)
        self.origin.refresh_from_db()
        frozen = self.origin.payload["opening"]["review"]["collateral"][0]
        self.assertEqual((frozen["gross_weight"], frozen["net_weight"], frozen["purity"], frozen["metal"]),
                         (None, "9", "90", "BRONZE"))

    def test_native_validation_still_requires_gross_and_db_checks_known_weights(self):
        # The ordinary native form and approval's full_clean boundary remain strict.
        self.assertTrue(PawnCollateralDraftForm().fields["gross_weight"].required)
        with self.assertRaises(ValidationError) as error:
            self.item.full_clean()
        self.assertIn("gross_weight", error.exception.message_dict)
        for bad in (0, -1, 8):
            with self.subTest(gross=bad), self.assertRaises(IntegrityError), transaction.atomic():
                PawnCollateralItem.objects.filter(pk=self.item.pk).update(gross_weight=bad)
        self.item.refresh_from_db()
        self.assertIsNone(self.item.gross_weight)

    @override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                               "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_detail_displays_unknown_gross_and_bronze(self):
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        response = client.get(reverse("workspace_loans:pawn_loan_detail", args=[self.tenant.slug, self.loan.pk]))
        self.assertContains(response, "Gross weight not recorded")
        self.assertContains(response, "Bronze")
        self.assertNotContains(response, "None g")
