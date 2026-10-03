from copy import deepcopy
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import DatabaseError, transaction
from django.test import override_settings
from django.urls import reverse

from apps.tenant_apps.loans.models import PawnLoan, LoanProductVersion, LoanSeries, LoanProduct
from apps.tenant_apps.loans.services.history_contract import encode, parse, decimal, HistoryError
from apps.tenant_apps.loans.services.history_export import export_history
from apps.tenant_apps.loans.services.history_import import balance_values
from apps.tenant_apps.loans.services.license_series import create_license
from apps.tenant_apps.data_portability import loan_history
from apps.tenant_apps.data_portability.models import LoanHistoryBatch
from . import test_loan_history as history_tests
from .test_loan_history import document
from .fixtures import PortabilityFixture


def weekly_document(*, method="STARTED_WEEKS", bullet=False, early=False):
    result = document(True)
    loan = result["loan"]
    result["manifest"].update(profile="loan-history/2", as_of="2021-03-08" if not early else "2021-02-08")
    loan["disbursed_on"] = "2021-02-01"
    loan["approval"]["at"] = "2021-02-01T00:00:00+00:00"
    loan["schedule"]["maturity"] = loan["schedule"]["obligations"][0]["due"] = "2021-05-01"
    loan["policy"].update(partial_month_method=method, minimum_first_month=True)
    loan["product"] = dict(repayment_structure="SINGLE_PAYMENT_BULLET" if bullet else "FLEXIBLE_PARTIAL_PAYMENT",
        amortisation_method="NONE", payment_frequency="AT_MATURITY" if bullet else "FLEXIBLE",
        extra_payment_rule="NOT_APPLICABLE" if bullet else "REDUCE_PRINCIPAL")
    loan["disbursal"].update(advance_periods=1, advance_interest="10", net_cash="990")
    events = loan["events"]
    events[0]["date"] = "2021-02-01"
    events[1]["date"] = "2021-02-08" if early else "2021-02-28"
    events[1]["interest"] = events[1]["balance"]["interest"] = "0"
    events[1]["accrual"].update(start="2021-02-01", end=events[1]["date"], recognized="0")
    events[2]["date"] = "2021-02-28"
    events[2]["interest"] = "0"
    base = Decimal(1000 if bullet or early else 900)
    fraction = {"STARTED_WEEKS": Decimal(14)/31, "ACTUAL_DAYS": Decimal(8)/31,
                "SLAB": Decimal(".5"), "FULL_MONTH": Decimal(1)}[method]
    unrounded = base / 100 * fraction
    recognized = unrounded.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
    events[3].update(date="2021-03-08", interest=decimal(recognized))
    events[3]["balance"].update(principal=decimal(base), interest=decimal(recognized))
    events[3]["accrual"].update(start="2021-03-01", end="2021-03-08", base=decimal(base),
        fraction=decimal(fraction), unrounded=decimal(unrounded), recognized=decimal(recognized))
    events[4].update(date=result["manifest"]["as_of"], principal=decimal(base), interest="0" if early else decimal(recognized))
    events[4]["release"]["returned_at"] = result["manifest"]["as_of"] + "T12:00:00+00:00"
    events[4]["allocations"][0].update(before=decimal(base), principal=decimal(base))
    loan["events"] = [events[0], events[1], events[4]] if early else ([events[0], events[1], events[3], events[4]] if bullet else events)
    for entry in loan["events"]:
        entry["event_recorded"] = entry["id"] != "a1"
        accrual = entry["accrual"]
        if not accrual: continue
        first = accrual["period"] == 1
        calculated = "10" if first else decimal(recognized)
        advance = "10" if first else "0"
        accrual.update(calculated=calculated, advance_applied=advance,
            release_catch_up=(not first or early), period_days=28 if first else 31,
            elapsed_days=(8 if early else 28) if first else 8,
            chargeable_days=28 if first else (14 if method=="STARTED_WEEKS" else (8 if method=="ACTUAL_DAYS" else None)),
            lines=[dict(item="item1", base=accrual["base"], rate="1", fraction=accrual["fraction"],
                unrounded=accrual["unrounded"], calculated=calculated, advance_applied=advance, recognized=accrual["recognized"])])
    return result


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                           "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class LoanHistoryV2Tests(PortabilityFixture):
    def setUp(self):
        super().setUp()
        with self.scoped():
            self.commit(self.ready())
            license=create_license(workspace=self.a,actor=self.actor,name="Historical",license_number="OLD-L",issued_on=date(2020,1,1),expires_on=date(2022,1,1))
            series=LoanSeries.objects.create(license=license,name="Historical",code="H")
            product=LoanProduct.objects.create(workspace=self.a,code="H",name="Historical")
            version=LoanProductVersion.objects.create(product=product,version=1,status="RETIRED",repayment_structure="FLEXIBLE_PARTIAL_PAYMENT",
                amortisation_method="NONE",payment_frequency="FLEXIBLE",extra_payment_rule="REDUCE_PRINCIPAL",maximum_tenor_months=12,
                operational_grace_days=3,calculation_contract_version="TEST-V1")
            self.mapping={"revision_id":license.revisions.get().pk,"series_id":series.pk,"product_version_id":version.pk}
        self.args={"workspace_id":self.a.pk,"actor":self.actor}

    run_import = history_tests.LoanHistoryTests.run_import

    def test_weekly_roundtrip_preserves_exact_fraction_advance_and_balances(self):
        with self.scoped():
            value = weekly_document()
            batch, token, result = self.run_import(value)
            self.assertEqual(result.loan.loan_events.count(), 4)
            self.assertEqual(result.loan.interest_accruals.filter(loan_event__isnull=True).count(), 1)
            exact = result.loan.loan_events.get(event_kind="INTEREST_ACCRUAL").payload["accrual"]
            self.assertEqual(exact["period_fraction"], "0.4516129032258064516129032258")
            self.assertEqual(exact["recognized_interest"], "4.06")
            self.assertEqual(parse(export_history(**self.args, loan_id=result.loan_id)), value)
            self.assertEqual(loan_history.commit(**self.args, batch_id=batch.public_id, approval=token, confirmed=True).pk, result.pk)
            self.assertEqual(balance_values(result.loan, date(2021,3,8)), value["loan"]["cutover"])

    def test_all_methods_and_early_closure(self):
        with self.scoped():
            for method, early in (("ACTUAL_DAYS", False), ("SLAB", False), ("FULL_MONTH", False), ("STARTED_WEEKS", True)):
                with self.subTest(method=method, early=early):
                    value = weekly_document(method=method, early=early)
                    value["loan"]["id"] += method + str(early)
                    value["loan"]["events"][-1]["id"] += method + str(early)
                    batch = loan_history.stage(**self.args, content=encode(value))
                    token = loan_history.preview(**self.args, batch_id=batch.public_id, values=self.mapping)
                    result = loan_history.commit(**self.args, batch_id=batch.public_id, approval=token, confirmed=True)
                    self.assertEqual(parse(export_history(**self.args, loan_id=result.loan_id)), value)

    def test_bullet_product_preserved_and_wrong_mapping_rejected(self):
        with self.scoped():
            value = weekly_document(bullet=True)
            batch = loan_history.stage(**self.args, content=encode(value))
            with self.assertRaises(HistoryError):
                loan_history.preview(**self.args, batch_id=batch.public_id, values=self.mapping)
            LoanProductVersion.objects.filter(pk=self.mapping["product_version_id"]).update(**value["loan"]["product"])
            token = loan_history.preview(**self.args, batch_id=batch.public_id, values=self.mapping)
            result = loan_history.commit(**self.args, batch_id=batch.public_id, approval=token, confirmed=True)
            self.assertEqual(parse(export_history(**self.args, loan_id=result.loan_id)), value)

    def test_corrupt_exact_evidence_and_missing_zero_accrual_roll_back(self):
        mutations = [
            lambda v: v["loan"]["events"][3]["accrual"].update(fraction="0.4516"),
            lambda v: v["loan"]["events"][3]["accrual"].update(period_days=30),
            lambda v: v["loan"]["events"][3]["accrual"]["lines"][0].update(advance_applied="1"),
            lambda v: v["loan"]["events"][0].update(event_recorded=False),
            lambda v: v["loan"]["events"].pop(1),
            lambda v: v["loan"]["events"][3]["accrual"].update(unrounded="4.064516129032258064516129033"),
        ]
        with self.scoped():
            for mutate in mutations:
                value = weekly_document(); mutate(value)
                batch = loan_history.stage(**self.args, content=encode(value))
                with self.assertRaises(HistoryError):
                    loan_history.preview(**self.args, batch_id=batch.public_id, values=self.mapping)
                self.assertFalse(PawnLoan.objects.exists())

    def test_v2_profile_immutability_and_workspace_isolation(self):
        with self.scoped():
            batch, _, result = self.run_import(weekly_document())
            with self.assertRaises(DatabaseError), transaction.atomic():
                LoanHistoryBatch.objects.filter(pk=batch.pk).update(profile="loan-history/1")
        with self.scoped(self.b):
            self.assertFalse(PawnLoan.objects.filter(pk=result.loan_id).exists())
            self.assertFalse(LoanHistoryBatch.objects.filter(pk=batch.pk).exists())

    def test_help_is_read_only_and_examples_validate_dates(self):
        from django.test import RequestFactory
        from apps.tenant_apps.loans.web.interest_help import interest_policy_help
        url = reverse("workspace_loans:interest_policy_help", kwargs={"workspace_slug": self.a.slug})
        def get(values=None, method="get"):
            request = getattr(RequestFactory(), method)(url, values or {})
            request.user, request.workspace, request.session = self.actor, self.a, {}
            return interest_policy_help(request)
        with self.scoped():
            self.assertContains(get(), "Try an example")
            values = dict(principal="10000", monthly_rate="3", start="2026-03-01", end="2026-04-08",
                method="STARTED_WEEKS", cutoff=15, lower_fraction="0.5", advance_periods=1)
            response = get(values)
            self.assertContains(response, "440.00")
            self.assertContains(response, "140.00")
            self.assertContains(get(values | {"end":"2026-02-01"}), "Choose a date on or after")
            self.assertEqual(get(method="post").status_code, 405)
            self.assertFalse(PawnLoan.objects.exists())

    def test_native_advance_covered_early_release_exports_and_restores(self):
        from unittest.mock import patch
        from apps.tenant_apps.loans.models import PawnLoanEconomicPolicy
        create = PawnLoanEconomicPolicy.objects.create
        def policy(**values):
            return create(**(values | dict(minimum_first_month=True, advance_interest_periods=1,
                                          partial_month_method="STARTED_WEEKS")))
        with patch.object(PawnLoanEconomicPolicy.objects, "create", side_effect=policy):
            history_tests.LoanHistoryTests.test_native_origination_export_can_preview_as_complete_history(self)

    def test_export_restores_in_another_workspace_with_matching_balances(self):
        with self.scoped():
            _, _, result = self.run_import(weekly_document())
            content = export_history(**self.args, loan_id=result.loan_id)
        with self.scoped(self.b):
            self.commit(self.ready(workspace=self.b), workspace=self.b)
            license = create_license(workspace=self.b, actor=self.actor, name="Destination", license_number="OLD-L",
                issued_on=date(2020,1,1), expires_on=date(2022,1,1))
            series = LoanSeries.objects.create(license=license, code="DEST", name="Destination")
            product = LoanProduct.objects.create(workspace=self.b, code="DEST", name="Destination")
            version = LoanProductVersion.objects.create(product=product, version=1, status="RETIRED",
                **weekly_document()["loan"]["product"], maximum_tenor_months=12, operational_grace_days=3,
                calculation_contract_version="TEST-V1")
            args = dict(workspace_id=self.b.pk, actor=self.actor)
            batch = loan_history.stage(**args, content=content)
            token = loan_history.preview(**args, batch_id=batch.public_id, values=dict(
                revision_id=license.revisions.get().pk, series_id=series.pk, product_version_id=version.pk))
            restored = loan_history.commit(**args, batch_id=batch.public_id, approval=token, confirmed=True)
            self.assertEqual(parse(export_history(**args, loan_id=restored.loan_id)), parse(content))
            self.assertEqual(restored.loan.workspace_id, self.b.pk)
            self.assertNotEqual(restored.loan_id, result.loan_id)

    def test_mixed_item_rates_and_repayment_allocations_roundtrip(self):
        value = weekly_document()
        loan = value["loan"]
        loan["collateral"][0].update(principal="500", monthly_rate="2")
        loan["collateral"].append(loan["collateral"][0] | dict(id="item2", principal="500", monthly_rate="0", metal="SILVER"))
        first, repay, final, release = loan["events"][1:]
        first["accrual"]["lines"][0].update(base="500", rate="2")
        first["accrual"]["lines"].append(dict(item="item2", base="500", rate="0", fraction="1",
            unrounded="0", calculated="0", advance_applied="0", recognized="0"))
        repay["allocations"][0].update(before="500", after="400")
        repay["allocations"].append(dict(item="item2", before="500", principal="0", after="500"))
        exact = decimal(Decimal(8) * (Decimal(14)/31))
        final["accrual"].update(unrounded=exact, calculated="3.61", recognized="3.61")
        final["accrual"]["lines"][0].update(base="400", rate="2", unrounded=exact, calculated="3.61", recognized="3.61")
        final["accrual"]["lines"].append(dict(item="item2", base="500", rate="0", fraction=final["accrual"]["fraction"],
            unrounded="0", calculated="0", advance_applied="0", recognized="0"))
        final["interest"] = final["balance"]["interest"] = release["interest"] = "3.61"
        release["allocations"][0].update(before="400", principal="400")
        release["allocations"].append(dict(item="item2", before="500", principal="500", after="0"))
        release["release"]["valuation"].append(dict(item="item2", value="2000"))
        with self.scoped():
            _, _, result = self.run_import(value)
            self.assertEqual(parse(export_history(**self.args, loan_id=result.loan_id)), value)

    def test_published_v2_schema_and_example(self):
        import json
        from pathlib import Path
        from apps.tenant_apps.loans.services.history_contract import SCHEMA_V2
        self.assertEqual(json.loads(Path("docs/contracts/loan-history-v2.schema.json").read_text()), SCHEMA_V2)
        self.assertEqual(parse(Path("docs/contracts/examples/loan-history-weekly-v2.jsonl").read_bytes()), weekly_document())
