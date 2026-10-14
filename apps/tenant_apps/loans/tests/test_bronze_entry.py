"""Bronze facts and standing terms use the existing paper loan workflow."""
from decimal import Decimal

from django.test import override_settings
from django.utils import timezone

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.services.paper_entry_terms import paper_entry_terms
from apps.tenant_apps.loans.web.economic_forms import PawnEconomicConfigurationForm
from apps.tenant_apps.loans.web.recorded_history import PaperCollateralForm
from apps.tenant_apps.loans.services.economic_policies import create_pawn_economic_configuration
from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
from apps.tenant_apps.loans.models import LoanMonitoringPolicy
from apps.tenant_apps.rates.models import RateSource, Rate
from . import test_paper_entry_simplification as paper
from . import test_multi_item_paper as mixed


@override_settings(ROOT_URLCONF="django_project.workspace_urls",
    STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class BronzePaperEntryTests(WorkspaceTestCase):
    setup_tenant = classmethod(paper.PaperEntrySimplificationTests.setup_tenant.__func__)
    make_snapshot = paper.PaperEntrySimplificationTests.make_snapshot
    prepare_history = paper.PaperEntrySimplificationTests.prepare_history
    row = paper.PaperEntrySimplificationTests.row
    configure = paper.PaperEntrySimplificationTests.configure
    setUp = paper.PaperEntrySimplificationTests.setUp
    facts = paper.PaperEntrySimplificationTests.facts
    preview = paper.PaperEntrySimplificationTests.preview

    @classmethod
    def get_test_schema_name(cls):
        return "bronze-paper-entry"

    def test_bronze_paper_review_supplies_its_own_dated_rate_and_records_actual_terms(self):
        self.configure(bronze_monthly_interest_rate=Decimal("3"))
        terms = paper_entry_terms(workspace=self.tenant, series=self.series, day=self.day, metal="BRONZE")
        self.assertEqual(terms["values"]["rate"], Decimal("3"))
        self.assertIn("BRONZE", dict(PaperCollateralForm.base_fields["metal"].choices))
        values = self.facts(metal="BRONZE", description="Bronze vessel", purity="100")
        values.update({"collateral-TOTAL_FORMS": "1", "collateral-INITIAL_FORMS": "0",
            "collateral-MIN_NUM_FORMS": "1", "collateral-MAX_NUM_FORMS": "100",
            "collateral-0-description": "Bronze vessel", "collateral-0-metal": "BRONZE",
            "collateral-0-quantity": "1", "collateral-0-gross_weight": "1000",
            "collateral-0-net_weight": "900", "collateral-0-purity_percentage": "100",
            "collateral-0-allocated_principal": "12000"})
        response = self.preview(values)
        self.assertEqual(response.context["formset"].forms[0].cleaned_data["interest_rate_override"], Decimal("3"))
        posted = self.client.post(self.path, dict(values, action="confirm", confirm_review="on", review_token=response.context["review_token"]))
        self.assertEqual(posted.status_code, 302)
        from apps.tenant_apps.loans.models import PawnLoan
        loan = PawnLoan.objects.get(loan_number=values["number"])
        self.assertEqual(loan.collateral_items.get().metal, "BRONZE")
        self.assertEqual(loan.monthly_interest_rate, Decimal("3"))
        self.assertFalse(loan.approval_snapshots.exists())

    def test_bronze_only_configuration_creates_no_gold_or_silver_rate(self):
        from django.forms.models import model_to_dict
        from apps.tenant_apps.loans.models import PawnLoanEconomicPolicy, PawnMetalInterestRatePolicy
        before = PawnMetalInterestRatePolicy.objects.count()
        values = model_to_dict(PawnLoanEconomicPolicy.objects.latest("pk"), fields=tuple(PawnEconomicConfigurationForm.base_fields))
        values.update(license=self.series.license_id, series=self.series.pk, metals_to_configure="BRONZE",
                      bronze_monthly_interest_rate="3.5", effective_from=self.day,
                      gold_monthly_interest_rate="2", silver_monthly_interest_rate="4")
        form = PawnEconomicConfigurationForm(values, workspace=self.tenant)
        self.assertTrue(form.is_valid(), form.errors)
        result = create_pawn_economic_configuration(workspace=self.tenant, actor=self.actor, **form.cleaned_data)
        self.assertIsNone(result.gold_rate_policy)
        self.assertIsNone(result.silver_rate_policy)
        self.assertEqual(result.bronze_rate_policy.monthly_interest_rate, Decimal("3.5"))
        self.assertEqual(PawnMetalInterestRatePolicy.objects.count(), before + 1)


class MixedBronzePaperMonitoringTests(WorkspaceTestCase):
    setup_tenant = classmethod(mixed.MultiItemPaperTests.setup_tenant.__func__)
    make_snapshot = mixed.MultiItemPaperTests.make_snapshot
    prepare_history = mixed.MultiItemPaperTests.prepare_history
    row = mixed.MultiItemPaperTests.row
    setUp = mixed.MultiItemPaperTests.setUp
    admit = mixed.MultiItemPaperTests.admit

    @classmethod
    def get_test_schema_name(cls):
        return "mixed-bronze-paper"

    def test_mixed_paper_bronze_and_silver_receive_current_values_without_origin_approval(self):
        self.data["collateral"][0].update(metal="BRONZE", description="Bronze vessel")
        self.data["metal"] = "BRONZE"
        loan, _ = self.admit()
        LoanMonitoringPolicy.objects.create(workspace=self.tenant, effective_from=self.day, version=1,
            valuation_basis="CALCULATED_METAL_VALUE", compliance_profile="Fictional bronze monitoring",
            ltv_warning_ratio=Decimal("0.7"), ltv_breach_ratio=Decimal("0.8"), ltv_critical_ratio=Decimal("0.9"),
            eligible_custody_states=["IN_VAULT", "WITH_FUNDING_LENDER"], severity_mapping={"strategy": "derived-v1"}, created_by=self.actor)
        source = RateSource.objects.create(name="Fictional mixed source", location="Local")
        for metal, price in (("Bronze", "0.60"), ("Silver", "100")):
            Rate.objects.create(rate_source=source, metal=metal, buying_rate=price, selling_rate=price)
        events = list(loan.loan_events.values())
        value = get_pawn_loan_collateral_valuation(loan.pk, as_of_date=timezone.localdate())
        expected = sum((Decimal(price) * Decimal(row["net_weight"]) * Decimal(row["purity"]) / 100).quantize(Decimal("0.01"))
                       for row, price in zip(self.data["collateral"], ("0.60", "100")))
        self.assertEqual(value.eligible_collateral_value, expected)
        self.assertFalse(loan.approval_snapshots.exists())
        self.assertEqual(list(loan.loan_events.values()), events)
        from apps.tenant_apps.loans.services.servicing_bundle import export_servicing_bundle
        from apps.tenant_apps.loans.services.servicing_bundle_contract import read_bundle
        self.start_active_trial()
        content = export_servicing_bundle(workspace_id=self.tenant.pk, actor=self.actor, loan_id=loan.pk)
        document, _ = read_bundle(content)
        self.assertIn("BRONZE", {item["metal"] for item in document["tables"]["PawnCollateralItem"]})
