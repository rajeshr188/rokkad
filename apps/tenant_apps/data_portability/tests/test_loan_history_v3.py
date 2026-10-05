from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.test import override_settings
from django.db import DatabaseError, transaction
from apps.tenant_apps.data_portability.models import LoanHistoryBatch
from apps.tenant_apps.loans.services.history_contract import encode, parse, decimal, HistoryError, SCHEMA_V3
from apps.tenant_apps.loans.services.history_export import export_history
from apps.tenant_apps.loans.services.history_import import balance_values
from apps.tenant_apps.loans.models import PawnLoan
from apps.tenant_apps.data_portability import loan_history
from .fixtures import PortabilityFixture
from .test_loan_history_v2 import LoanHistoryV2Tests, weekly_document


def inclusive_document(method="STARTED_WEEKS", early=False):
    value = weekly_document(method=method, early=early)
    value["manifest"]["profile"] = "loan-history/3"
    loan = value["loan"]
    loan["policy"]["policy_version"] = 2
    first = loan["events"][1]
    first["accrual"].update(period_days=29, chargeable_days=29)
    if not early:
        first["date"] = first["accrual"]["end"] = "2021-03-01"
        first["accrual"]["elapsed_days"] = 29
        loan["events"][2]["date"] = "2021-03-01"
        second = loan["events"][3]
        fraction = Decimal(7)/31 if method in ("STARTED_WEEKS", "ACTUAL_DAYS") else Decimal(".5") if method == "SLAB" else Decimal(1)
        raw = Decimal(9) * fraction
        rounded = raw.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        detail = second["accrual"]
        detail.update(start="2021-03-02", fraction=decimal(fraction), unrounded=decimal(raw),
            recognized=decimal(rounded), calculated=decimal(rounded), elapsed_days=7,
            chargeable_days=7 if method in ("STARTED_WEEKS", "ACTUAL_DAYS") else None)
        detail["lines"][0].update(fraction=decimal(fraction), unrounded=decimal(raw),
            recognized=decimal(rounded), calculated=decimal(rounded))
        second["interest"] = second["balance"]["interest"] = decimal(rounded)
        loan["events"][4]["interest"] = decimal(rounded)
    return value


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                           "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class LoanHistoryV3Tests(LoanHistoryV2Tests):

    def test_published_schema_and_example_match_implemented_contract(self):
        import json
        from pathlib import Path
        from django.conf import settings
        root = Path(settings.BASE_DIR) / "docs/contracts"
        self.assertEqual(json.loads((root / "loan-history-v3.schema.json").read_text()), SCHEMA_V3)
        self.assertEqual(parse((root / "examples/loan-history-weekly-v3.jsonl").read_bytes()), inclusive_document())

    def test_corrected_history_stage_commit_roundtrip_and_retry(self):
        with self.scoped():
            value = inclusive_document()
            batch, token, origin = self.run_import(value)
            self.assertEqual(batch.profile, "loan-history/3")
            self.assertEqual(parse(export_history(**self.args, loan_id=origin.loan_id)), value)
            self.assertEqual(balance_values(origin.loan, date(2021, 3, 8)), value["loan"]["cutover"])
            self.assertEqual(loan_history.commit(**self.args, batch_id=batch.public_id, approval=token, confirmed=True).pk, origin.pk)
            self.assertEqual(origin.loan.interest_accruals.get(period_number=2).recognized_interest, Decimal("2.03"))
            with self.assertRaises(DatabaseError), transaction.atomic():
                LoanHistoryBatch.objects.filter(pk=batch.pk).update(profile="loan-history/2")

    def test_policy_partial_methods_and_upfront_early_closure(self):
        with self.scoped():
            for method, early in (("ACTUAL_DAYS", False), ("FULL_MONTH", False), ("SLAB", False), ("STARTED_WEEKS", True)):
                value = inclusive_document(method, early)
                value["loan"]["id"] += method + str(early)
                value["loan"]["events"][-1]["id"] += method + str(early)
                batch = loan_history.stage(**self.args, content=encode(value))
                before = PawnLoan.objects.count()
                token = loan_history.preview(**self.args, batch_id=batch.public_id, values=self.mapping)
                self.assertEqual(PawnLoan.objects.count(), before)
                origin = loan_history.commit(**self.args, batch_id=batch.public_id, approval=token, confirmed=True)
                self.assertEqual(parse(export_history(**self.args, loan_id=origin.loan_id)), value)

    def test_old_wire_cannot_claim_new_policy_or_early_charge(self):
        value = inclusive_document()
        value["manifest"]["profile"] = "loan-history/2"
        with self.assertRaises(HistoryError):
            encode(value)
        value = inclusive_document()
        value["loan"]["events"][3]["accrual"]["start"] = "2021-03-01"
        with self.scoped():
            batch = loan_history.stage(**self.args, content=encode(value))
            with self.assertRaises(HistoryError):
                loan_history.preview(**self.args, batch_id=batch.public_id, values=self.mapping)
