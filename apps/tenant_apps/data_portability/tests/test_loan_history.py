import copy
import uuid
from datetime import date
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, transaction

from apps.tenant_apps.loans.models import LoanSeries, LoanProduct, LoanProductVersion, PawnLoan, HistoricalLoanImport
from apps.tenant_apps.loans.services.license_series import create_license
from apps.tenant_apps.loans.services.history_contract import encode, parse, HistoryError
from apps.tenant_apps.loans.services.history_import import balance_values
from apps.tenant_apps.data_portability import loan_history
from apps.tenant_apps.data_portability.models import LoanHistoryBatch
from .fixtures import PortabilityFixture


def document(closed=False):
    def event(id, kind, day, p, i, balance, allocations=None, accrual=None, release=None):
        return dict(id=id, kind=kind, date=day, actor="source-operator", principal=str(p), interest=str(i), fees="0",
            balance={"principal":str(balance),"interest":"0","fees":"0"}, allocations=allocations or [], accrual=accrual, release=release)
    first = event("d1","DISBURSAL","2021-01-01",1000,0,1000)
    accrual = event("a1","INTEREST_ACCRUAL","2021-01-31",0,10,1000,
        accrual=dict(period=1,start="2021-01-01",end="2021-01-31",fraction="1",base="1000",unrounded="10",recognized="10"))
    accrual["balance"]["interest"]="10"
    repayment=event("p1","REPAYMENT","2021-01-31",100,10,900,
        allocations=[dict(item="item1",before="1000",principal="100",after="900")])
    result={"manifest":{"profile":"loan-history/1","namespace":"8e6c2138-e413-4f15-83fc-ad28a47f4fb1","as_of":"2021-01-31","coverage":"PARTIAL",
        "exclusions":["binary_files","workspace_configuration","renewals","auctions","opening_positions"]},
        "loan":{"id":"source-loan","number":"00042","state":"ACTIVE","borrower":{"source_system":"paper","id":"old-1"},
        "licence_number":"OLD-L","disbursed_on":"2021-01-01","tenure_months":3,"calculation_contract":"TEST-V1","grace_days":3,
        "approval":{"at":"2021-01-01T00:00:00+00:00","actor":"source-approver","reference":"Signed paper 42"},
        "policy":{"policy_version":1,"interest_method":"SIMPLE","partial_month_method":"FULL_MONTH","partial_month_cutoff_days":15,
            "partial_month_lower_fraction":"0.5","capitalization_interval_periods":12,"valuation_method":"LATEST_APPRAISAL",
            "maximum_ltv_ratio":"0.8","rounding_method":"PER_ACCRUAL_PERIOD","currency_quantum":"0.01"},
        "collateral":[{"id":"item1","description":"Gold ring","metal":"GOLD","gross_weight":"10","net_weight":"10","purity":"100",
            "principal":"1000","monthly_rate":"1","metal_rate":None,"appraised_value":"2000","valuation_reference":"Appraisal 42"}],
        "disbursal":{"advance_periods":0,"fees":[],"principal":"1000","monthly_interest":"10","advance_interest":"0","deducted_fees":"0","net_cash":"1000"},
        "schedule":{"maturity":"2021-04-01","principal":"1000","interest":"30","obligations":[{"sequence":1,"due":"2021-04-01","principal":"1000","interest":"30"}]},
        "events":[first,accrual,repayment],"cutover":{"principal":"900","interest":"0","fees":"0"}}}
    if closed:
        final_accrual=event("a2","INTEREST_ACCRUAL","2021-02-01",0,9,900,
            accrual=dict(period=2,start="2021-02-01",end="2021-02-01",fraction="1",base="900",unrounded="9",recognized="9"))
        final_accrual["balance"]["interest"]="9"
        release=event("r1","RELEASE_RECEIPT","2021-02-01",900,9,0,
            allocations=[dict(item="item1",before="900",principal="900",after="0")],
            release=dict(number="R0042",returned_at="2021-02-01T12:00:00+00:00",collector="Borrower",valuation=[dict(item="item1",value="2000")]))
        result["loan"]["events"] += [final_accrual,release]
        result["loan"]["state"]="CLOSED"
        result["loan"]["cutover"]["principal"]="0"
        result["manifest"]["as_of"]="2021-02-01"
    return result


class LoanHistoryTests(PortabilityFixture):
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

    def run_import(self, value):
        batch=loan_history.stage(**self.args,content=encode(value))
        approval=loan_history.preview(**self.args,batch_id=batch.public_id,values=self.mapping)
        self.assertFalse(PawnLoan.objects.exists())
        result=loan_history.commit(**self.args,batch_id=batch.public_id,approval=approval,confirmed=True)
        return batch,approval,result

    def test_active_history_preview_rollback_commit_and_replay(self):
        with self.scoped():
            batch,approval,result=self.run_import(document())
            self.assertEqual(result.loan.state,"ACTIVE")
            self.assertEqual(balance_values(result.loan,date(2021,1,31)),document()["loan"]["cutover"])
            self.assertEqual(result.loan.loan_events.count(),3)
            self.assertEqual(loan_history.commit(**self.args,batch_id=batch.public_id,approval=approval,confirmed=True).pk,result.pk)
            self.assertEqual(PawnLoan.objects.count(),1)

    def test_closed_history_restores_settlement_custody_and_termination(self):
        with self.scoped():
            _,_,result=self.run_import(document(True))
            self.assertEqual(result.loan.state,"CLOSED")
            self.assertEqual(result.loan.collateral_items.get().custody_state,"WITH_CUSTOMER")
            self.assertEqual(result.loan.releases.count(),1)
            self.assertEqual(balance_values(result.loan,date(2021,2,1)),document(True)["loan"]["cutover"])

    def test_wrong_financial_checkpoint_rolls_back_whole_loan(self):
        with self.scoped():
            value=document(True);value["loan"]["events"][-1]["balance"]["principal"]="1"
            batch=loan_history.stage(**self.args,content=encode(value))
            with self.assertRaises(HistoryError) as raised:
                loan_history.preview(**self.args,batch_id=batch.public_id,values=self.mapping)
            self.assertEqual(raised.exception.issue["category"], "HISTORICAL_INCONSISTENCY")
            self.assertEqual(raised.exception.issue["code"], "CALCULATION_MISMATCH")
            self.assertFalse(PawnLoan.objects.exists())
            self.assertFalse(HistoricalLoanImport.objects.exists())

    def test_cancellation_and_unauthorized_access(self):
        with self.assertRaises(PermissionDenied): loan_history.stage(**self.args,content=encode(document()))
        with self.scoped():
            batch=loan_history.stage(**self.args,content=encode(document()))
            with self.assertRaises(PermissionDenied): loan_history.get_batch(workspace_id=self.a.pk,actor=self.other_actor,batch_id=batch.public_id)
            with self.assertRaises(HistoryError): loan_history.cancel(**self.args,batch_id=batch.public_id)
            loan_history.cancel(**self.args,batch_id=batch.public_id,confirmed=True)
            batch.refresh_from_db();self.assertEqual(batch.document,{})

    def test_missing_history_and_duplicate_json_fail_closed(self):
        with self.assertRaises(HistoryError): parse(b'{"profile":"a","profile":"b"}\n{}\n')
        with self.scoped():
            value=document();value["loan"]["events"].pop(1)
            batch=loan_history.stage(**self.args,content=encode(value))
            with self.assertRaises(HistoryError):loan_history.preview(**self.args,batch_id=batch.public_id,values=self.mapping)

    def test_imported_active_and_closed_export_exact_roundtrip(self):
        from apps.tenant_apps.loans.services.history_export import export_history
        with self.scoped():
            for closed in (False, True):
                value=document(closed)
                value["loan"]["id"] += str(closed)
                batch=loan_history.stage(**self.args,content=encode(value))
                approval=loan_history.preview(**self.args,batch_id=batch.public_id,values=self.mapping)
                result=loan_history.commit(**self.args,batch_id=batch.public_id,approval=approval,confirmed=True)
                exported=parse(export_history(**self.args,loan_id=result.loan_id))
                self.assertEqual(exported,value)

    def test_native_origination_export_can_preview_as_complete_history(self):
        from decimal import Decimal
        from django.utils import timezone
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.tenant_apps.loans.models import LoanNumberSequence
        from apps.tenant_apps.loans.services import CreatePawnDraftCommand, CollateralDraftInput, create_pawn_draft, append_collateral_photo, approve_pawn_loan
        from apps.tenant_apps.loans.services.pawn_disbursal import disburse_pawn_loan
        from apps.tenant_apps.loans.services.product_catalog import _seed_default_loan_products
        from apps.tenant_apps.loans.services.history_export import export_history
        from apps.tenant_apps.party.models import Party
        from apps.tenant_apps.rates.models import Rate, RateSource
        with self.scoped():
            today=timezone.localdate()
            license=create_license(workspace=self.a,actor=self.actor,name="Current",license_number="CURRENT",issued_on=today,expires_on=date(today.year+1,12,31))
            series=LoanSeries.objects.create(license=license,name="Current",code="C")
            LoanNumberSequence.objects.create(series=series,document_kind="PAWN_LOAN",prefix="C-",width=5,maximum_number=10000)
            product=LoanProductVersion.objects.get(pk=self.mapping["product_version_id"])
            LoanProductVersion.objects.filter(pk=product.pk).update(status="ACTIVE")
            Rate.objects.create(rate_source=RateSource.objects.create(name="Local",location="Local"),buying_rate=10000,selling_rate=10100)
            from apps.tenant_apps.loans.models import PawnLoanEconomicPolicy,PawnMetalInterestRatePolicy
            PawnLoanEconomicPolicy.objects.create(workspace=self.a,advance_interest_periods=0)
            PawnMetalInterestRatePolicy.objects.create(workspace=self.a,metal="GOLD",monthly_interest_rate=2)
            loan=create_pawn_draft(CreatePawnDraftCommand(workspace_id=self.a.pk,borrower_id=Party.objects.get().pk,
                license_id=license.pk,series_id=series.pk,product_version_id=product.pk,principal_amount=Decimal("50000"),monthly_interest_rate=Decimal("2"),
                loan_date=today,tenure_months=3,collateral=(CollateralDraftInput(description="Ring",metal="GOLD",gross_weight=Decimal("20"),net_weight=Decimal("18"),purity_percentage=Decimal("91.6"),latest_appraised_value=Decimal("120000"),allocated_principal=Decimal("50000")),)),actor=self.actor)
            append_collateral_photo(loan.collateral_items.get().pk,upload=SimpleUploadedFile("ring.jpg",b"\xff\xd8\xff\xe0evidence",content_type="image/jpeg"),actor=self.actor)
            approve_pawn_loan(loan.pk,actor=self.actor)
            disburse_pawn_loan(loan.pk,effective_date=today,actor=self.actor)
            exported=parse(export_history(**self.args,loan_id=loan.pk))
            batch=loan_history.stage(**self.args,content=encode(exported))
            token=loan_history.preview(**self.args,batch_id=batch.public_id,values=dict(revision_id=license.revisions.get().pk,series_id=series.pk,product_version_id=product.pk))
            imported=loan_history.commit(**self.args,batch_id=batch.public_id,approval=token,confirmed=True)
            self.assertEqual(exported,parse(export_history(**self.args,loan_id=imported.loan_id)))
            from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full,preview_pawn_loan_full_release
            LoanNumberSequence.objects.create(series=series,document_kind="PAWN_LOAN_RELEASE",prefix="R-",width=5,maximum_number=10000)
            quote=preview_pawn_loan_full_release(loan.pk)
            release_pawn_loan_in_full(loan.pk,settlement_amount=quote.minimum_settlement,request_key="native-release",actor=self.actor)
            closed=parse(export_history(**self.args,loan_id=loan.pk))
            self.assertEqual(closed["loan"]["state"],"CLOSED")
            closed["manifest"]["namespace"]=str(uuid.uuid4())
            final_batch=loan_history.stage(**self.args,content=encode(closed))
            token=loan_history.preview(**self.args,batch_id=final_batch.public_id,values=dict(revision_id=license.revisions.get().pk,series_id=series.pk,product_version_id=product.pk))
            restored=loan_history.commit(**self.args,batch_id=final_batch.public_id,approval=token,confirmed=True)
            self.assertEqual(closed,parse(export_history(**self.args,loan_id=restored.loan_id)))

    def test_imported_active_loan_accepts_native_repayment_and_exports_it(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        from apps.tenant_apps.loans.services.history_export import export_history
        with self.scoped():
            _,_,result=self.run_import(document())
            record_pawn_loan_repayment(result.loan_id,amount="100",request_key="after-import",actor=self.actor)
            exported=parse(export_history(**self.args,loan_id=result.loan_id))
            self.assertEqual(len(exported["loan"]["events"]),4)
            self.assertEqual(exported["loan"]["cutover"]["principal"],"800")

    def test_stale_approval_duplicate_source_and_late_commit_failure(self):
        with self.scoped():
            batch=loan_history.stage(**self.args,content=encode(document()))
            approval=loan_history.preview(**self.args,batch_id=batch.public_id,values=self.mapping)
            with self.assertRaises(HistoryError):
                loan_history.commit(**self.args,batch_id=batch.public_id,approval=approval)
            with self.assertRaises(HistoryError):
                loan_history.commit(**self.args,batch_id=batch.public_id,approval=approval+"broken",confirmed=True)
            with patch("apps.tenant_apps.loans.services.history_import.AuditLog.log",side_effect=ValueError("late failure")):
                with self.assertRaises(HistoryError):
                    loan_history.commit(**self.args,batch_id=batch.public_id,approval=approval,confirmed=True)
            self.assertFalse(PawnLoan.objects.exists())
            batch.refresh_from_db();self.assertEqual(batch.state,"READY")
            result=loan_history.commit(**self.args,batch_id=batch.public_id,approval=approval,confirmed=True)
            second=loan_history.stage(**self.args,content=encode(document()))
            second_token=loan_history.preview(**self.args,batch_id=second.public_id,values=self.mapping)
            self.assertEqual(loan_history.commit(**self.args,batch_id=second.public_id,approval=second_token,confirmed=True).pk,result.pk)
            changed=document();changed["loan"]["number"]="changed"
            conflict=loan_history.stage(**self.args,content=encode(changed))
            with self.assertRaises(HistoryError):loan_history.preview(**self.args,batch_id=conflict.public_id,values=self.mapping)
            self.assertEqual(PawnLoan.objects.count(),1)

    def test_rls_and_immutable_provenance_and_finished_batch(self):
        with self.scoped():
            batch,_,result=self.run_import(document())
            for model,pk,changes in ((HistoricalLoanImport,result.pk,{"document":{}}),(LoanHistoryBatch,batch.pk,{"state":"STAGED"})):
                with self.assertRaises(DatabaseError),transaction.atomic(): model.objects.filter(pk=pk).update(**changes)
                with self.assertRaises(DatabaseError),transaction.atomic():
                    from django.db import connection
                    with connection.cursor() as cursor:cursor.execute(f'DELETE FROM "{model._meta.db_table}" WHERE id=%s',[pk])
        with self.scoped(self.b):
            self.assertFalse(HistoricalLoanImport.objects.filter(pk=result.pk).exists())
            self.assertFalse(LoanHistoryBatch.objects.filter(pk=batch.pk).exists())
            with self.assertRaises(PermissionDenied):loan_history.get_batch(workspace_id=self.b.pk,actor=self.actor,batch_id=batch.public_id)
            with self.assertRaises(DatabaseError),transaction.atomic():
                HistoricalLoanImport.objects.create(workspace_id=self.b.pk,loan_id=result.loan_id,source_namespace=uuid.uuid4(),source_id="cross",source_sha256="a"*64,document={},references={},imported_by=self.actor)

    def test_revoked_permission_blocks_commit_and_completed_replay(self):
        from apps.orgs.models import Membership,WorkspaceRoleGrant
        with self.scoped():
            batch,approval,_=self.run_import(document())
            membership=Membership.objects.get(company=self.a,user=self.actor)
            WorkspaceRoleGrant.objects.filter(workspace_id=self.a.pk,workspace_role__role_id=membership.role_id,permission__codename="data_import").delete()
            with self.assertRaises(PermissionDenied):loan_history.commit(**self.args,batch_id=batch.public_id,approval=approval,confirmed=True)

    def test_preview_rejects_missing_borrower_and_incomplete_source(self):
        with self.scoped():
            mutations=[lambda v:v["loan"]["borrower"].update(id="missing"),
                lambda v:v["loan"]["events"][0].update(date="2022-01-01"),
                lambda v:v["loan"]["events"][2]["allocations"][0].update(item="missing"),
                lambda v:v["loan"]["schedule"].update(interest="99")]
            for mutate in mutations:
                value=document();mutate(value)
                batch=loan_history.stage(**self.args,content=encode(value))
                with self.assertRaises(HistoryError):loan_history.preview(**self.args,batch_id=batch.public_id,values=self.mapping)
            self.assertFalse(PawnLoan.objects.exists())

    def test_failure_categories_survive_preview_without_admitting_history(self):
        cases = [({"state": "CLOSED"}, "MISSING_EVIDENCE"),
                 ({"calculation_contract": "UNSUPPORTED"}, "OPERATIONAL_READINESS"),
                 ({"borrower": {"source_system": "paper", "id": "missing"}}, "OPERATIONAL_READINESS")]
        with self.scoped():
            for changes, category in cases:
                value = document()
                value["loan"].update(changes)
                batch = loan_history.stage(**self.args, content=encode(value))
                with self.subTest(changes=changes), self.assertRaises(HistoryError) as raised:
                    loan_history.preview(**self.args, batch_id=batch.public_id, values=self.mapping)
                self.assertEqual(raised.exception.issue["category"], category)
                batch.refresh_from_db()
                self.assertEqual(batch.state, "STAGED")
                self.assertEqual(batch.preview, {})
            self.assertFalse(PawnLoan.objects.exists())
            self.assertFalse(HistoricalLoanImport.objects.exists())

    def test_real_http_upload_preview_confirm_export_and_csrf(self):
        from types import SimpleNamespace
        from django.test import Client,override_settings
        from django.urls import reverse
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.tenancy import testing
        testing.WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=self.a))
        with override_settings(ALLOWED_HOSTS=["testserver"],STORAGES={"default":{"BACKEND":"django.core.files.storage.FileSystemStorage"},"staticfiles":{"BACKEND":"django.contrib.staticfiles.storage.StaticFilesStorage"}}):
            client=Client(enforce_csrf_checks=True);client.force_login(self.actor)
            upload=reverse("workspace_portability:loan_upload",kwargs={"workspace_slug":self.a.slug})
            page=client.get(upload);self.assertContains(page,"Stage loan history")
            self.assertIn("no-store",page["Cache-Control"])
            self.assertEqual(client.post(upload,{}).status_code,403)
            csrf={"csrfmiddlewaretoken":client.cookies["csrftoken"].value}
            rejected=client.post(upload,{**csrf,"source":SimpleUploadedFile("bad.jsonl",b"not json\n{}\n")})
            self.assertContains(rejected,"Malformed data: Invalid bounded UTF-8 JSONL document.")
            staged=client.post(upload,{**csrf,"source":SimpleUploadedFile("loan.jsonl",encode(document()))})
            self.assertEqual(staged.status_code,302)
            url=staged.url
            preview=client.post(url,{**csrf,**self.mapping,"action":"preview"})
            self.assertContains(preview,"Commit complete loan history")
            with self.scoped():self.assertFalse(PawnLoan.objects.exists())
            token=preview.context["approval"]
            self.assertContains(client.post(url,{**csrf,"action":"commit","approval":token}),"Operational readiness: Confirm the entire")
            committed=client.post(url,{**csrf,"action":"commit","approval":token,"confirmed":"yes"})
            self.assertEqual(committed.status_code,302)
            self.assertContains(client.get(url),"complete loan history was imported")
            with self.scoped():result=HistoricalLoanImport.objects.get()
            export=reverse("workspace_portability:loan_export",kwargs={"workspace_slug":self.a.slug,"loan_id":result.loan_id})
            self.assertEqual(client.get(export).status_code,405)
            response=client.post(export,csrf)
            self.assertEqual(response.status_code,200)
            self.assertEqual(parse(response.content),document())

    def test_closed_history_exports_and_imports_into_other_workspace(self):
        from apps.tenant_apps.loans.services.history_export import export_history
        with self.scoped():
            _,_,origin=self.run_import(document(True))
            content=export_history(**self.args,loan_id=origin.loan_id)
        with self.scoped(self.b):
            self.commit(self.ready(workspace=self.b),workspace=self.b)
            license=create_license(workspace=self.b,actor=self.actor,name="Destination",license_number="OLD-L",issued_on=date(2020,1,1),expires_on=date(2022,1,1))
            series=LoanSeries.objects.create(license=license,name="Historical",code="H")
            product=LoanProduct.objects.create(workspace=self.b,code="H",name="Historical")
            version=LoanProductVersion.objects.create(product=product,version=1,status="RETIRED",repayment_structure="FLEXIBLE_PARTIAL_PAYMENT",amortisation_method="NONE",payment_frequency="FLEXIBLE",extra_payment_rule="REDUCE_PRINCIPAL",maximum_tenor_months=12,operational_grace_days=3,calculation_contract_version="TEST-V1")
            args=dict(workspace_id=self.b.pk,actor=self.actor)
            batch=loan_history.stage(**args,content=content)
            token=loan_history.preview(**args,batch_id=batch.public_id,values=dict(revision_id=license.revisions.get().pk,series_id=series.pk,product_version_id=version.pk))
            result=loan_history.commit(**args,batch_id=batch.public_id,approval=token,confirmed=True)
            self.assertNotEqual(result.loan_id,origin.loan_id)
            self.assertEqual(parse(export_history(**args,loan_id=result.loan_id)),parse(content))

    def test_mapping_tamper_and_expired_confirmation_fail(self):
        with self.scoped():
            batch=loan_history.stage(**self.args,content=encode(document()))
            token=loan_history.preview(**self.args,batch_id=batch.public_id,values=self.mapping)
            with patch("django.core.signing.time.time",return_value=9999999999):
                with self.assertRaises(HistoryError):loan_history.commit(**self.args,batch_id=batch.public_id,approval=token,confirmed=True)
            LoanHistoryBatch.objects.filter(pk=batch.pk).update(mapping={**self.mapping,"borrower_id":999999})
            with self.assertRaises(HistoryError):loan_history.commit(**self.args,batch_id=batch.public_id,approval=token,confirmed=True)
            self.assertFalse(PawnLoan.objects.exists())

    def test_parser_bounds_and_published_schema_examples(self):
        import json
        from pathlib import Path
        from apps.tenant_apps.loans.services.history_contract import SCHEMA,MAX_BYTES
        self.assertEqual(json.loads(Path("docs/contracts/loan-history-v1.schema.json").read_text()),SCHEMA)
        for state in ("active","closed"):
            parse(Path(f"docs/contracts/examples/loan-history-{state}.jsonl").read_bytes())
        for content in (b" "*(MAX_BYTES+1),b"{}\n{}\n{}",b"["*1500+b"]"*1500+b"\n{}",b"NaN\n{}"):
            with self.assertRaises(HistoryError):parse(content)
        for mutate in (lambda v:v["loan"].update(extra="unknown"),lambda v:v["loan"].update(tenure_months=True),
            lambda v:v["loan"]["cutover"].update(principal="1.0000001"),lambda v:v["loan"]["events"][0].update(kind="REVERSAL")):
            value=document();mutate(value)
            with self.assertRaises(HistoryError):encode(value)

    def test_decimal_spelling_and_equal_same_day_payments_preserve_identity(self):
        from apps.tenant_apps.loans.services.history_export import export_history
        with self.scoped():
            value=document()
            for index,before in ((2,900),(3,800)):
                event=copy.deepcopy(value["loan"]["events"][-1])
                event.update(id=f"p{index}",interest="0",principal="100.00")
                event["balance"]["principal"]=str(before-100)
                event["allocations"]=[dict(item="item1",before=str(before),principal="100.00",after=str(before-100))]
                value["loan"]["events"].append(event)
            value["loan"]["cutover"]["principal"]="700.00"
            _,_,result=self.run_import(value)
            self.assertEqual(result.loan.loan_events.filter(event_kind="REPAYMENT").count(),3)
            self.assertEqual(parse(export_history(**self.args,loan_id=result.loan_id)),parse(encode(value)))

    def test_offset_custody_timestamp_roundtrip(self):
        from apps.tenant_apps.loans.services.history_export import export_history
        with self.scoped():
            value=document(True)
            value["loan"]["events"][-1]["release"]["returned_at"]="2021-02-01T00:30:00+05:30"
            _,_,result=self.run_import(value)
            self.assertEqual(parse(export_history(**self.args,loan_id=result.loan_id)),value)
