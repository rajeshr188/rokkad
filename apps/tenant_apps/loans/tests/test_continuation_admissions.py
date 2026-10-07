"""Real four-path admission characterization, never fabricated import markers."""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID

from dateutil.relativedelta import relativedelta
from django.test import override_settings
from django.utils import timezone

from apps.tenant_apps.data_portability import loan_history
from apps.tenant_apps.data_portability.models import SourceIdentity
from apps.tenant_apps.data_portability.tests.fixtures import PortabilityFixture
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.domain.monthly_contract import item_monthly_interest, RULE
from apps.tenant_apps.loans.selectors.continuation import resolve_loan_continuation
from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
from apps.tenant_apps.loans.selectors.servicing_contract import get_servicing_position
from apps.tenant_apps.loans.services import (
    approve_pawn_loan, disburse_pawn_loan, update_pawn_draft, UpdatePawnDraftCommand, CollateralDraftInput,
)
from apps.tenant_apps.loans.services.economic_policies import create_pawn_loan_economic_policy
from apps.tenant_apps.loans.services.history_contract import encode, digest
from apps.tenant_apps.loans.services.license_series import _record_license_revision
from apps.tenant_apps.loans.services.opening_import import commit_opening_import, preview_opening_import, PROFILE
from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment, preview_pawn_loan_repayment
from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
from apps.tenant_apps.loans.services.recorded_history import (
    new_recording_intent, preview_recorded_history, admit_recorded_history,
)
from . import test_collateral_reappraisal as native_fixtures, test_opening_checkpoint as opening_fixtures


class AdmissionFixture(PortabilityFixture):
    make_loan = native_fixtures.CollateralReappraisalTests.make_loan
    quantum = Decimal(".01")
    original = date(2026, 4, 5)
    cutover = date(2026, 4, 20)
    principal = Decimal("5025.25")
    reduction = Decimal("100.25")
    multiple_items = False
    second_rate = Decimal("2")

    def setUp(self):
        super().setUp()
        self.tenant = self.a
        self.remaining = self.principal - self.reduction
        self.advance = item_monthly_interest(self.principal, "2", self.quantum)
        self.monthly = item_monthly_interest(self.remaining, "2", self.quantum)
        if self.multiple_items:
            self.item_principals = (Decimal("2512.75"), Decimal("2512.75"))
            self.item_rates = (Decimal("2"), self.second_rate)
            self.reduced_index = 1 if self.second_rate > 2 else 0
            self.item_remaining = tuple(value - (self.reduction if i == self.reduced_index else 0)
                for i, value in enumerate(self.item_principals))
            self.advance = sum(item_monthly_interest(p, r, self.quantum)
                for p, r in zip(self.item_principals, self.item_rates))
            self.monthly = sum(item_monthly_interest(p, r, self.quantum)
                for p, r in zip(self.item_remaining, self.item_rates))
        with self.scoped():
            system = opening_fixtures.checkpoint()["mapping"]["borrower_source_system"]
            self.commit(self.ready(self.stage(system=system)))
            self.identity = SourceIdentity.objects.get(external_id="old-1")
            with patch("django.utils.timezone.localdate", return_value=date(2026, 10, 5)), patch(
                    "django.utils.timezone.now", return_value=timezone.make_aware(datetime(2026, 10, 5, 12))):
                self.make_loan(method="LATEST_APPRAISAL", product_index=2, age_days=183, activate=False)
            self.loan.license_revision = _record_license_revision(self.loan.license,
                kind=m.LoanLicenseRevision.Kind.INITIAL, actor=self.actor)
            self.loan.principal_amount = self.principal
            self.loan.monthly_interest_rate = (self.advance / self.principal * 100).quantize(Decimal(".000001"))
            self.loan.save(update_fields=["license_revision", "principal_amount", "monthly_interest_rate"])
            self.item.allocated_principal = self.principal
            self.item.latest_appraised_value = Decimal("10000")
            self.item.save(update_fields=["allocated_principal", "latest_appraised_value"])
            create_pawn_loan_economic_policy(workspace=self.a, license=self.loan.license,
                valuation_method="LATEST_APPRAISAL", maximum_ltv_ratio=Decimal(".8"), advance_interest_periods=1,
                currency_quantum=self.quantum, effective_from=self.original, actor=self.actor)
            items = [CollateralDraftInput(description="Gold ring", metal="GOLD", gross_weight=Decimal(1),
                net_weight=Decimal(1), purity_percentage=Decimal(100), latest_appraised_value=Decimal(10000),
                allocated_principal=Decimal("2512.75") if self.multiple_items else self.principal,
                collateral_item_id=self.item.pk)]
            if self.multiple_items:
                from apps.tenant_apps.loans.services.economic_policies import create_pawn_metal_interest_rate_policy
                create_pawn_metal_interest_rate_policy(workspace=self.a, license=self.loan.license,
                    metal="SILVER", monthly_interest_rate=self.second_rate, effective_from=self.original, actor=self.actor)
                items.append(CollateralDraftInput(description="Silver ring", metal="SILVER", gross_weight=Decimal(1),
                    net_weight=Decimal(1), purity_percentage=Decimal(100), latest_appraised_value=Decimal(10000),
                    allocated_principal=Decimal("2512.75")))
            update_pawn_draft(self.loan.pk, UpdatePawnDraftCommand(borrower_id=self.loan.borrower_id,
                principal_amount=self.principal, monthly_interest_rate=self.loan.monthly_interest_rate,
                loan_date=self.original, tenure_months=12, collateral=tuple(items)), actor=self.actor)
            if self.multiple_items:
                from django.core.files.uploadedfile import SimpleUploadedFile
                from apps.tenant_apps.loans.services import append_collateral_photo
                second = self.loan.collateral_items.exclude(pk=self.item.pk).get()
                append_collateral_photo(second.pk, upload=SimpleUploadedFile("second.jpg", b"\xff\xd8\xff\xe0evidence",
                    content_type="image/jpeg"), actor=self.actor)
            with patch("django.utils.timezone.now", return_value=self.quote.effective_at):
                approve_pawn_loan(self.loan.pk, actor=self.actor)
                disburse_pawn_loan(self.loan.pk, effective_date=self.original, actor=self.actor)
            self.loan.refresh_from_db()
            with patch("django.utils.timezone.localdate", return_value=self.cutover):
                record_pawn_loan_repayment(self.loan.pk, amount=self.reduction, request_key="actual-direct-reduction", actor=self.actor)
            self.direct = self.loan
            with patch("django.utils.timezone.localdate", return_value=date(2026, 5, 5)):
                self.paper = self.admit_paper()
            self.imported = self.admit_history()
            self.opening = self.admit_opening()
            self.loans = (self.direct, self.paper, self.imported, self.opening)

    def admit_paper(self):
        values = dict(borrower_id=self.direct.borrower_id, series_id=self.direct.series_id,
            product_version_id=self.direct.product_version_id, number="PAPER-42", date=self.original.isoformat(),
            principal=str(self.principal), rate="2", tenure=12, advance_months=1,
            cash_paid=str(self.principal-self.advance), document_charge="0", payout_basis="PROCEEDS",
            source_reference="Synthetic book page 42", description="Gold ring", metal="GOLD", quantity=1,
            gross_weight="1", net_weight="1", purity="100", monitoring_method="LATEST_APPRAISAL",
            monitoring_ltv=".8", monitoring_reason="Current appraisal assessed separately",
            complete_through="2026-05-05", final_state="ACTIVE", confirmed_history=True, confirmed_rule=True,
            currency_quantum=str(self.quantum), events=[dict(kind="PAYMENT", amount=str(self.reduction),
                date=self.cutover.isoformat(), reference="Synthetic principal receipt", number="", rate=None,
                tenure=None, recipient="")])
        args = dict(workspace=self.a, actor=self.actor,
            intent_token=new_recording_intent(workspace=self.a, actor=self.actor))
        if self.multiple_items:
            values["rate"] = str(sum(p*r for p, r in zip(self.item_principals, self.item_rates))/self.principal)
            values["collateral"] = [dict(description=f"{metal} ring", metal=metal, quantity=1, gross_weight="1", net_weight="1",
                purity="100", principal=str(principal), rate=str(rate))
                for metal, principal, rate in zip(("GOLD", "SILVER"), self.item_principals, self.item_rates)]
            values["events"][0]["item_principal_split"] = {
                str(i+1): str(self.reduction if i == self.reduced_index else 0) for i in range(2)}
        _, token = preview_recorded_history(**args, data=values)
        loan, created = admit_recorded_history(**args, data=values, review_token=token, confirmed=True)
        self.assertTrue(created)
        return loan

    def admit_history(self):
        args = dict(workspace_id=self.a.pk, actor=self.actor)
        from apps.tenant_apps.data_portability.tests import test_loan_history_v4 as history_fixtures
        value = history_fixtures.document()
        value["manifest"]["namespace"] = str(UUID(self.identity.source_system.split(":")[1]))
        value["manifest"]["as_of"] = "2026-05-05"
        value["loan"].update(id="Import book:99", number="IMPORT-99", book_reference="Import book",
            source_reference="Synthetic imported loan 99", borrower=dict(source_system=self.identity.source_system, id="old-1"),
            licence_number=self.direct.license.license_number, disbursed_on=self.original.isoformat(),
            calculation_contract=self.direct.product_version.calculation_contract_version,
            grace_days=self.direct.product_version.operational_grace_days, currency_quantum=str(self.quantum),
            collateral=[dict(id="ring", description="Gold ring", metal="GOLD", quantity=1, gross_weight="1",
                net_weight="1", purity="100", principal=str(self.principal), monthly_rate="2")],
            payout=dict(advance_months=1, document_charge="0", proceeds=str(self.principal-self.advance), basis="PROCEEDS"),
            cutover=dict(principal=str(self.remaining), interest="0", fees="0"))
        receipt = value["loan"]["events"][0]
        receipt.update(date=self.cutover.isoformat(), amount=str(self.reduction), principal=str(self.reduction),
            allocations=[dict(item="ring", before=str(self.principal), principal=str(self.reduction), after=str(self.remaining))])
        if self.multiple_items:
            first = value["loan"]["collateral"][0]
            first["principal"] = "2512.75"
            value["loan"]["collateral"].append(dict(first, id="ring-2", description="Silver ring", metal="SILVER",
                monthly_rate=str(self.second_rate)))
            receipt["allocations"] = [dict(item=item_id, before=str(principal),
                principal=str(principal-remaining), after=str(remaining))
                for item_id, principal, remaining in zip(("ring", "ring-2"), self.item_principals, self.item_remaining)]
        mapping = dict(revision_id=self.direct.license_revision_id, series_id=self.direct.series_id,
                       product_version_id=self.direct.product_version_id)
        batch = loan_history.stage(**args, content=encode(value))
        count = m.PawnLoan.objects.count()
        token = loan_history.preview(**args, batch_id=batch.public_id, values=mapping)
        self.assertEqual(m.PawnLoan.objects.count(), count)
        origin = loan_history.commit(**args, batch_id=batch.public_id, approval=token, confirmed=True)
        self.assertTrue(m.HistoricalLoanImport.objects.filter(loan=origin.loan).exists())
        self.assertEqual(loan_history.commit(**args, batch_id=batch.public_id, approval=token, confirmed=True).pk, origin.pk)
        return origin.loan

    def admit_opening(self):
        review = opening_fixtures.checkpoint(original=self.original, cutover=self.cutover,
            original_principal=str(self.principal), remaining=str(self.remaining), current_base=str(self.principal),
            rate="2", quantum=str(self.quantum), recognized="0", unpaid="0", current_recognized="0",
            current_unpaid="0", advances=[(1, str(self.advance))])
        review["source"].update(borrower_id="old-1", loan_id="Opening:43", number="OPENING-43")
        review["terms"]["maturity_date"] = (self.original+relativedelta(months=12)).isoformat()
        review["terms"]["grace_days"] = self.direct.product_version.operational_grace_days
        review["obligations"][0].update(due=review["terms"]["maturity_date"], interest=str(self.monthly*11))
        if self.multiple_items:
            first = review["collateral"][0]
            first.update(original_principal="2512.75", remaining_principal=str(self.item_remaining[0]))
            second = deepcopy(first)
            second.update(id="girvi_loanitem:2", description="Silver ring", metal="SILVER",
                monthly_rate=str(self.second_rate), remaining_principal=str(self.item_remaining[1]))
            review["collateral"].append(second)
            review["source"]["item_ids"].append(second["id"])
            review["continuation"].update(bases=[dict(item_id=item["id"], principal_base="2512.75")
                for item in review["collateral"]], expected_period_interest=str(self.advance))
        system = review["mapping"]["borrower_source_system"]
        identity = SourceIdentity.objects.get(external_id="old-1", source_system=system)
        product = m.LoanProduct.objects.create(workspace=self.a, code="CHECKPOINT", name="Checkpoint")
        version = m.LoanProductVersion.objects.create(product=product, version=1, status="RETIRED",
            repayment_structure="FLEXIBLE_PARTIAL_PAYMENT", amortisation_method="NONE", payment_frequency="FLEXIBLE",
            extra_payment_rule="REDUCE_PRINCIPAL", maximum_tenor_months=12,
            operational_grace_days=self.direct.product_version.operational_grace_days, calculation_contract_version=RULE)
        review["mapping"].update(workspace_id=self.a.pk, borrower_id=identity.identity.party_id,
            borrower_external_id="old-1", licence_revision_id=self.direct.license_revision_id,
            series_id=self.direct.series_id, product_version_id=version.pk)
        from apps.tenant_apps.data_portability.tests import test_loan_history as history_fixtures
        setup = dict(tenure_months=12, source_license_number=self.direct.license.license_number,
            policy=deepcopy(history_fixtures.document()["loan"]["policy"]))
        setup["policy"].update(policy_version=2, minimum_first_month=False, currency_quantum=str(self.quantum))
        args = dict(workspace_id=self.a.pk, actor=self.actor, review=review, setup=setup)
        preview_opening_import(**args)
        checksum = digest(dict(profile=PROFILE, review=review, setup=setup))
        origin, _ = commit_opening_import(**args, expected_sha256=checksum, confirmed=True)
        self.assertEqual(list(origin.loan.loan_events.values_list("event_kind", flat=True)), ["MIGRATION_OPENING"])
        return origin.loan


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class ContinuationAdmissionTests(AdmissionFixture):
    def test_maturity_forecast_reduces_next_period_and_caps_transaction_knowledge(self):
        before_payment, paid_on = date(2026, 5, 5), date(2026, 5, 20)
        with self.scoped():
            old_payoffs = [get_pawn_loan_exposure(loan.pk, as_of_date=before_payment).maturity_payoff
                for loan in self.loans]
            self.assertEqual(old_payoffs, [old_payoffs[0]] * 4)
            for loan in self.loans:
                with patch("django.utils.timezone.localdate", return_value=paid_on):
                    record_pawn_loan_repayment(loan.pk, amount=self.monthly + Decimal("100"),
                        request_key="forecast-reduction-" + str(loan.pk), actor=self.actor)
            before_events = list(m.PawnLoanEvent.objects.values_list("pk", "payload_fingerprint"))
            payoffs = []
            for loan, old in zip(self.loans, old_payoffs):
                with self.subTest(loan=loan.loan_number):
                    self.assertEqual(get_pawn_loan_exposure(loan.pk, as_of_date=before_payment).maturity_payoff, old)
                    exposure = get_pawn_loan_exposure(loan.pk, as_of_date=paid_on)
                    self.assertEqual(exposure.principal_outstanding, self.remaining - 100)
                    self.assertEqual(exposure.projected_interest, 0)
                    from apps.tenant_apps.loans.services.pawn_tranches import get_pawn_principal_tranche_balances
                    tranches = get_pawn_principal_tranche_balances(loan, as_of_date=paid_on)
                    following = sum((item_monthly_interest(row.principal_outstanding,
                        row.monthly_interest_rate, self.quantum) for row in tranches), Decimal(0))
                    self.assertEqual(exposure.maturity_payoff, self.remaining - 100 + following * 10)
                    forecast = resolve_loan_continuation(loan, as_of_date=paid_on,
                        forecast_through=self.original + relativedelta(months=12))
                    self.assertEqual(forecast.recognition.additional_interest, following * 10)
                    with self.assertRaisesMessage(ValueError, "not a current collection balance"):
                        _ = forecast.collection_balance
                    payoffs.append(exposure.maturity_payoff)
            self.assertEqual(payoffs, [payoffs[0]] * 4)
            self.assertEqual(list(m.PawnLoanEvent.objects.values_list("pk", "payload_fingerprint")), before_events)

    def test_future_forecast_rejects_invalid_horizon_and_preserves_checkpoint_basis(self):
        with self.scoped():
            with self.assertRaisesMessage(ValueError, "on or after"):
                resolve_loan_continuation(self.direct, as_of_date=self.cutover,
                    forecast_through=self.original)
            exposure = get_pawn_loan_exposure(self.opening.pk, as_of_date=self.cutover)
            self.assertEqual(exposure.principal_history_basis, "OPENING_CHECKPOINT")
            self.assertEqual(exposure.financial_history_from, self.cutover)
            self.assertEqual(exposure.original_principal, self.remaining)

    def test_actual_origins_checkpoint_and_advance_evidence_are_distinct(self):
        with self.scoped():
            self.assertTrue(self.direct.approval_snapshots.exists())
            self.assertFalse(self.paper.approval_snapshots.exists())
            self.assertFalse(self.imported.approval_snapshots.exists())
            self.assertFalse(self.opening.disbursal_snapshot_id)
            for loan in self.loans:
                with self.subTest(loan=loan.loan_number):
                    position = resolve_loan_continuation(loan, as_of_date=self.cutover)
                    self.assertEqual(position.contract.original_date, self.original)
                    self.assertEqual(position.contract.currency_quantum.normalize(), self.quantum.normalize())
                    self.assertEqual(position.recorded_balance.principal_outstanding, self.remaining)
                    self.assertEqual(position.recognition.additional_interest, 0)
                    self.assertEqual(position.collection_balance.total_due, self.remaining)
            checkpoint = resolve_loan_continuation(self.opening, as_of_date=self.cutover).contract
            self.assertEqual(checkpoint.financial_history_from, self.cutover)
            self.assertEqual(checkpoint.checkpoint_advance_coverage, ((1, self.advance),))
            self.assertEqual(sum(amount for _, amount in checkpoint.checkpoint_item_bases), self.principal)

    def test_anniversary_collection_and_risk_inputs_agree_without_writes(self):
        with self.scoped():
            before = list(m.PawnLoanEvent.objects.order_by("pk").values_list("pk", "payload_fingerprint"))
            accruals = m.PawnLoanInterestAccrual.objects.count()
            for on, interest in ((date(2026, 5, 5), Decimal(0)), (date(2026, 5, 6), self.monthly)):
                economic = []
                for loan in self.loans:
                    with self.subTest(on=on, loan=loan.loan_number):
                        position = get_servicing_position(loan, as_of_date=on, include_coverage=True)
                        exposure = get_pawn_loan_exposure(loan.pk, as_of_date=on)
                        self.assertEqual(position.balance.interest_outstanding, interest)
                        self.assertEqual(position.balance.total_due, self.remaining + interest)
                        self.assertEqual(exposure.recorded_total_due, self.remaining)
                        self.assertEqual(exposure.projected_interest, interest)
                        self.assertEqual(exposure.total_economic_exposure, position.balance.total_due)
                        with patch("django.utils.timezone.localdate", return_value=on):
                            quote = preview_pawn_loan_repayment(loan.pk, amount=interest+1)
                        self.assertEqual((quote.allocation.interest, quote.allocation.principal), (interest, Decimal(1)))
                        economic.append((exposure.principal_outstanding, exposure.cash_receivable_basis,
                            exposure.total_economic_exposure, exposure.maturity_payoff, exposure.ltv_exposure_basis))
                        if loan != self.direct and on == date(2026, 5, 6):
                            self.assertFalse(position.transaction_coverage.complete)
                self.assertEqual(economic, [economic[0]]*4)
            self.assertEqual(list(m.PawnLoanEvent.objects.order_by("pk").values_list("pk", "payload_fingerprint")), before)
            self.assertEqual(m.PawnLoanInterestAccrual.objects.count(), accruals)

    def test_interest_recognized_once_by_real_writers_and_retry(self):
        on = date(2026, 5, 6)
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=on):
            for loan in self.loans:
                with self.subTest(loan=loan.loan_number):
                    args = dict(amount=self.monthly, request_key="once-"+str(loan.pk), actor=self.actor)
                    paid = record_pawn_loan_repayment(loan.pk, **args)
                    retry = record_pawn_loan_repayment(loan.pk, **args)
                    self.assertEqual(retry.loan_event.pk, paid.loan_event.pk)
                    position = resolve_loan_continuation(loan, as_of_date=on)
                    self.assertEqual(position.recognition.additional_interest, 0)
                    self.assertEqual(position.collection_balance.total_due, self.remaining)
                    self.assertEqual(position.recorded_balance.interest_outstanding, 0)
                    self.assertEqual(get_pawn_loan_exposure(loan.pk, as_of_date=on).projected_interest, 0)

    def test_writer_reversals_restore_collection_without_replaying_before_cutover(self):
        with self.scoped():
            for loan in self.loans:
                with self.subTest(loan=loan.loan_number):
                    with patch("django.utils.timezone.localdate", return_value=date(2026, 5, 6)):
                        paid = record_pawn_loan_repayment(loan.pk, amount=self.monthly,
                            request_key="reverse-"+str(loan.pk), actor=self.actor)
                    with patch("django.utils.timezone.localdate", return_value=date(2026, 5, 7)):
                        if loan in (self.paper, self.imported):
                            # Their cumulative recognition requires the reviewed
                            # correction command; a generic reversal must not bypass it.
                            with self.assertRaisesMessage(ValueError, "Review paper history correction"):
                                reverse_pawn_loan_event(paid.loan_event.pk, actor=self.actor, reason="Synthetic cancelled receipt")
                            continue
                        reverse_pawn_loan_event(paid.loan_event.pk, actor=self.actor, reason="Synthetic cancelled receipt")
                    position = resolve_loan_continuation(loan, as_of_date=date(2026, 5, 7))
                    exposure = get_pawn_loan_exposure(loan.pk, as_of_date=date(2026, 5, 7))
                    self.assertEqual(position.collection_balance.total_due, self.remaining+self.monthly)
                    self.assertEqual(exposure.total_economic_exposure, position.collection_balance.total_due)
                    earlier = resolve_loan_continuation(loan, as_of_date=date(2026, 5, 5))
                    self.assertEqual(earlier.collection_balance.total_due, self.remaining)

    def test_cutover_unknown_history_and_foreign_workspace_fail_explicitly(self):
        with self.scoped():
            with self.assertRaisesMessage(ValueError, "before the migration cutover"):
                resolve_loan_continuation(self.opening, as_of_date=date(2026, 4, 19))
            # Shared facts can be read on cutover; writer chronology stays stricter.
            with patch("django.utils.timezone.localdate", return_value=self.cutover):
                with self.assertRaisesMessage(ValueError, "strictly after cutover"):
                    record_pawn_loan_repayment(self.opening.pk, amount=1, request_key="bad-cutover", actor=self.actor)
        with self.scoped(self.b):
            with self.assertRaisesMessage(ValueError, "active Workspace"):
                resolve_loan_continuation(self.direct, as_of_date=date(2026, 5, 6))
            with self.assertRaisesMessage(ValueError, "not found"):
                get_pawn_loan_exposure(self.direct.pk, as_of_date=date(2026, 5, 6))


class ContinuationWholeRupeeAdmissionTests(ContinuationAdmissionTests):
    quantum = Decimal("1")


class ContinuationMultiItemAdmissionTests(ContinuationAdmissionTests):
    multiple_items = True
    principal = Decimal("5025.50")
    reduction = Decimal("100.50")


class ContinuationMultiItemWholeRupeeTests(ContinuationMultiItemAdmissionTests):
    quantum = Decimal("1")
