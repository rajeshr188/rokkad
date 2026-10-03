"""Storage/read-model foundation; fixtures are not a public admission workflow."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context, without_workspace_context
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.integrations import disbursal_payload
from apps.tenant_apps.loans.services.event_recording import record_loan_event
from apps.tenant_apps.loans.services.obligations import persist_disbursal_repayment_schedule
from apps.tenant_apps.loans.services.recorded_origination_evidence import CONTRACT_POLICY_FIELDS
from apps.tenant_apps.party.models import Party
from .factories import ensure_test_product_version


class RecordedOriginationTests(WorkspaceTestCase):
    @classmethod
    def get_test_schema_name(cls):
        return "recorded-origination"

    @classmethod
    def setup_tenant(cls, tenant):
        cls.actor = get_user_model().objects.create_user(username="recorded-origin-owner")
        tenant.name = "Recorded origination"
        tenant.owner = tenant.creator = cls.actor
        tenant.save()
        Membership.objects.create(user=cls.actor, company=tenant,
                                  role=Role.objects.get_or_create(name="Owner")[0])

    def make_snapshot(self, *, save=True, advance=0, method="CALCULATED_METAL_VALUE",
                      rate=Decimal("2"), partial="FULL_MONTH"):
        today = timezone.localdate()
        day = today - timedelta(days=8)
        license = m.LoanLicense.objects.create(workspace=self.tenant, name="Main",
            license_number=uuid.uuid4().hex, issued_on=day, expires_on=today + timedelta(days=365))
        series = m.LoanSeries.objects.create(license=license, name="Paper book", code="P")
        loan = m.PawnLoan.objects.create(workspace=self.tenant, license=license, series=series,
            borrower=Party.objects.create(display_name="Borrower"),
            product_version=ensure_test_product_version(self.tenant), loan_number=uuid.uuid4().hex,
            principal_amount=Decimal("10000"), monthly_interest_rate=rate, tenure_months=3, loan_date=day)
        item = m.PawnCollateralItem.objects.create(loan=loan, quantity=1, description="Ring", metal="GOLD",
            gross_weight=Decimal("10"), net_weight=Decimal("9"), purity_percentage=Decimal("90"),
            allocated_principal=Decimal("10000"), monthly_interest_rate=rate)
        policy = m.LoanPolicySnapshot.objects.create(loan=loan, basis="RECORDED_CONTRACT",
            interest_method="SIMPLE", partial_month_method=partial, valuation_method=method,
            maximum_ltv_ratio=Decimal("0.8"), rounding_method="PER_ACCRUAL_PERIOD", currency_quantum=Decimal("0.01"))
        interest_policy = {key: str(getattr(policy, key)) if isinstance(getattr(policy, key), Decimal)
                           else getattr(policy, key) for key in CONTRACT_POLICY_FIELDS}
        monthly = (Decimal("10000") * rate / 100).quantize(Decimal("0.01"))
        tranches = [dict(collateral_item_id=item.pk, allocated_principal="10000",
                         monthly_interest_rate=str(rate), monthly_interest=str(monthly),
                         advance_interest=str(monthly * advance))]
        collateral = dict(item_id=item.pk, description=item.description, metal=item.metal, quantity=item.quantity,
            gross_weight="10", net_weight="9", purity_percentage="90", latest_appraised_value=None,
            monthly_interest_rate=str(rate))
        recording = dict(schema="recorded-origination/1", source_reference="Paper book 1 / page 20",
            payout_already_occurred=True, original_actor=None, date_precision="DAY", occurred_on=day.isoformat(),
            terms=dict(loan_number=loan.loan_number, principal_amount="10000", monthly_interest_rate=str(rate),
                       tenure_months=3, interest_policy=interest_policy, collateral=[collateral]),
            monitoring=dict(selected_on=today.isoformat(), valuation_method=method, maximum_ltv_ratio="0.8",
                            reason="Use the current gold price for ongoing coverage review."))
        payload = disbursal_payload(loan, effective_date=day, principal_amount=10000,
            net_cash_amount=10000-monthly*advance, advance_interest_amount=monthly*advance,
            deducted_fee_amount=0).to_dict()
        payload.update(recording=recording, disbursal=dict(basis="RECORDED", policy_snapshot_id=policy.pk,
            approval_snapshot_id=None, advance_interest_periods=advance, monthly_interest=str(monthly),
            tranches=tranches, fees=[]))
        event, _ = record_loan_event(loan.pk, event_kind="DISBURSAL", effective_date=day, payload=payload, actor=self.actor)
        snapshot = m.PawnLoanDisbursalSnapshot(loan=loan, policy_snapshot=policy, loan_event=event,
            basis="RECORDED", gross_principal=10000, monthly_interest=monthly, advance_interest_periods=advance,
            advance_interest=monthly*advance, deducted_fees=0, net_disbursed=10000-monthly*advance,
            evidence=dict(recording=recording, tranches=tranches, fees=[]), created_by=self.actor)
        if save:
            snapshot.save()
            persist_disbursal_repayment_schedule(loan, source_event=event, disbursed_on=day,
                currency_quantum=policy.currency_quantum, actor=self.actor)
            loan.state = "ACTIVE"
            loan.save(update_fields=["state"])
        return snapshot

    def test_recorded_origin_retains_date_terms_without_quotes_or_approval(self):
        from apps.tenant_apps.rates.models import Rate
        from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
        from apps.tenant_apps.loans.services.pawn_interest import preview_pawn_loan_accruals
        from apps.tenant_apps.loans.services.pawn_tranches import get_pawn_principal_tranche_balances
        snapshot = self.make_snapshot()
        self.assertFalse(Rate.objects.exists())
        self.assertFalse(m.PawnLoanApprovalSnapshot.objects.exists())
        self.assertFalse(m.CollateralAppraisal.objects.exists())
        self.assertLess(snapshot.loan_event.effective_date, timezone.localdate(snapshot.created_at))
        self.assertIsNone(snapshot.evidence["recording"]["original_actor"])
        self.assertEqual(get_pawn_loan_balance(snapshot.loan, as_of_date=timezone.localdate()).principal_outstanding, Decimal("10000"))
        self.assertEqual(get_pawn_loan_balance(snapshot.loan,
            as_of_date=snapshot.loan.loan_date - timedelta(days=1)).principal_outstanding, 0)
        self.assertEqual(get_pawn_principal_tranche_balances(snapshot.loan)[0].initial_principal, 10000)
        periods = preview_pawn_loan_accruals(snapshot.loan_id, as_of_date=timezone.localdate())
        self.assertEqual(sum(p.recognized_interest for p in periods), Decimal("200.00"))

    def test_advance_interest_preserved_and_not_charged_twice(self):
        from apps.tenant_apps.loans.services.pawn_interest import preview_pawn_loan_accruals
        snapshot = self.make_snapshot(advance=1)
        self.assertEqual(snapshot.net_disbursed, 9800)
        preview = preview_pawn_loan_accruals(snapshot.loan_id, as_of_date=timezone.localdate())[0]
        self.assertEqual(preview.advance_interest_applied, Decimal("200.00"))
        self.assertEqual(preview.recognized_interest, 0)

    def test_daily_partial_interest_uses_currency_precision(self):
        from apps.tenant_apps.loans.services.pawn_interest import preview_pawn_loan_accruals
        snapshot = self.make_snapshot(rate=Decimal("1.234567"), partial="ACTUAL_DAYS")
        preview = preview_pawn_loan_accruals(snapshot.loan_id, as_of_date=snapshot.loan.loan_date)[0]
        self.assertEqual(preview.recognized_interest, preview.unrounded_interest.quantize(Decimal("0.01")))
        self.assertEqual(preview.recognized_interest.as_tuple().exponent, -2)

    def test_missing_current_price_is_unknown_then_current_quote_monitors_same_debt(self):
        from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
        from apps.tenant_apps.rates.models import Rate, RateSource
        snapshot = self.make_snapshot()
        today = timezone.localdate()
        m.LoanMonitoringPolicy.objects.create(workspace=self.tenant, effective_from=today,
            version=1, compliance_profile="Current coverage review",
            ltv_warning_ratio=Decimal("0.7"), ltv_breach_ratio=Decimal("0.8"), ltv_critical_ratio=Decimal("0.9"),
            eligible_custody_states=["IN_VAULT", "WITH_FUNDING_LENDER"],
            severity_mapping={"strategy": "derived-v1"}, created_by=self.actor)
        def valuation():
            return get_pawn_loan_collateral_valuation(snapshot.loan_id, as_of_date=today)
        before = valuation()
        self.assertIsNone(before.eligible_collateral_value)
        source = RateSource.objects.create(name="Current market", location="Local")
        Rate.objects.create(rate_source=source, buying_rate=2000, selling_rate=2100)
        after = valuation()
        self.assertEqual(after.eligible_collateral_value, Decimal("16200"))
        self.assertEqual(after.compliance_profile, f"recorded-monitoring-basis:{snapshot.policy_snapshot_id}")
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.gross_principal, 10000)
        self.assertEqual(snapshot.evidence["recording"]["terms"]["principal_amount"], "10000")

    def test_inconsistent_or_unsupported_evidence_is_rejected(self):
        changes = [
            lambda s: s.evidence["recording"]["terms"].update(principal_amount="9000"),
            lambda s: s.evidence["recording"]["terms"]["interest_policy"].update(partial_month_method="SLAB"),
            lambda s: s.evidence["recording"]["monitoring"].update(maximum_ltv_ratio="0.9"),
            lambda s: s.evidence["recording"].update(source_reference=" "),
            lambda s: s.evidence["recording"].update(occurred_on=(timezone.localdate()+timedelta(days=1)).isoformat()),
            lambda s: s.evidence["tranches"][0].update(monthly_interest="NaN"),
            lambda s: s.evidence["tranches"].append(deepcopy(s.evidence["tranches"][0])),
            lambda s: setattr(s, "advance_interest_periods", 2),
            lambda s: setattr(s, "net_disbursed", 9000),
            lambda s: setattr(s, "created_by", None),
            lambda s: setattr(s, "basis", "APPROVED"),
        ]
        for change in changes:
            with self.subTest(change=change):
                snapshot = self.make_snapshot(save=False)
                change(snapshot)
                with self.assertRaises(ValidationError):
                    snapshot.full_clean()

    def test_current_appraisal_is_separate_from_unknown_original_valuation(self):
        from apps.tenant_apps.loans.services.collateral_reappraisal import record_collateral_reappraisal
        from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
        snapshot = self.make_snapshot(method="LATEST_APPRAISAL")
        item = snapshot.loan.collateral_items.get()
        m.LoanMonitoringPolicy.objects.create(workspace=self.tenant, effective_from=timezone.localdate(),
            version=1, compliance_profile="Current coverage review",
            ltv_warning_ratio=Decimal("0.7"), ltv_breach_ratio=Decimal("0.8"), ltv_critical_ratio=Decimal("0.9"),
            eligible_custody_states=["IN_VAULT"], severity_mapping={"strategy": "derived-v1"}, created_by=self.actor)
        appraisal = record_collateral_reappraisal(loan_id=snapshot.loan_id, item_id=item.pk, actor=self.actor,
            appraised_value=Decimal("16000"), method="PHYSICAL_INSPECTION", evidence_reference="Inspection today",
            review_notes="Current monitoring assessment", expected_version=0)
        value = get_pawn_loan_collateral_valuation(snapshot.loan_id, as_of_date=timezone.localdate())
        self.assertEqual(value.eligible_collateral_value, 16000)
        self.assertGreater(timezone.localdate(appraisal.effective_at), snapshot.loan.loan_date)
        snapshot.refresh_from_db()
        self.assertIsNone(snapshot.evidence["recording"]["terms"]["collateral"][0]["latest_appraised_value"])

    def test_ordinary_repayment_retry_and_reversal_use_same_principal(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
        from apps.tenant_apps.loans.services.pawn_tranches import get_pawn_principal_tranche_balances
        snapshot = self.make_snapshot()
        result = record_pawn_loan_repayment(snapshot.loan_id, amount=Decimal("100"),
                                            request_key="current-receipt", actor=self.actor)
        retry = record_pawn_loan_repayment(snapshot.loan_id, amount=Decimal("100"),
                                           request_key="current-receipt", actor=self.actor)
        self.assertEqual(retry.loan_event.pk, result.loan_event.pk)
        self.assertEqual(get_pawn_principal_tranche_balances(snapshot.loan)[0].principal_outstanding, 9900)
        reverse_pawn_loan_event(result.loan_event.pk, reason="Wrong receipt", actor=self.actor)
        self.assertEqual(get_pawn_principal_tranche_balances(snapshot.loan)[0].principal_outstanding, 10000)
        snapshot.loan.refresh_from_db()
        self.assertEqual(snapshot.loan.state, "ACTIVE")

    def test_no_fictional_approval_export_ticket_or_reversal(self):
        from apps.tenant_apps.loans.services.history_export import export_history, HistoryError
        from apps.tenant_apps.loans.services.pawn_reversal import assess_pawn_loan_event_reversal, reverse_pawn_loan_event, PawnReversalError
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder, DocumentProjectionError
        snapshot = self.make_snapshot()
        self.assertFalse(assess_pawn_loan_event_reversal(snapshot.loan_event).can_reverse)
        with self.assertRaisesMessage(PawnReversalError, "history correction"):
            reverse_pawn_loan_event(snapshot.loan_event_id, reason="Correct source", actor=self.actor)
        with self.assertRaisesMessage(HistoryError, "recorded-origination profile"):
            export_history(workspace_id=self.tenant.pk, actor=self.actor, loan_id=snapshot.loan_id)
        with self.assertRaises(DocumentProjectionError):
            PawnLoanDocumentProjectionBuilder.loan_ticket(snapshot.loan)

    def test_pledge_book_uses_frozen_paper_terms_and_unknown_original_valuation(self):
        from apps.tenant_apps.loans.selectors.pledge_book import _entry
        snapshot = self.make_snapshot()
        loan = snapshot.loan
        loan.register_events = [snapshot.loan_event]
        loan.register_disbursals = [snapshot]
        loan.register_releases = []
        row = _entry(loan, {}, start=loan.loan_date, end=timezone.localdate())
        self.assertIn("Recorded paper payout", row["source"])
        self.assertEqual(row["borrower"], "Not recorded")
        self.assertTrue(any("Original article valuation is missing" in w for w in row["warnings"]))

    def test_restricted_role_database_guards_and_workspace_isolation(self):
        snapshot = self.make_snapshot(save=False)
        other_workspace = Company.objects.create(name="Other workspace", schema_name=uuid.uuid4().hex,
                                                owner=self.actor, creator=self.actor)
        other = self.make_snapshot(save=False)
        role = connection.ops.quote_name("recorded_test_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {role}")
            for changes in ({"basis": "APPROVED"}, {"evidence": {}},
                            {"created_by": None}, {"workspace_id": other_workspace.pk},
                            {"policy_snapshot": other.policy_snapshot}, {"loan_event": other.loan_event},
                            {"net_disbursed": 9999}):
                forged = deepcopy(snapshot)
                for key, value in changes.items():
                    setattr(forged, key, value)
                with self.subTest(changes=changes), self.assertRaises(DatabaseError), transaction.atomic():
                    m.PawnLoanDisbursalSnapshot.objects.bulk_create([forged])
            snapshot.save()
            for action in (lambda: m.PawnLoanDisbursalSnapshot.objects.filter(pk=snapshot.pk).update(net_disbursed=1),
                           lambda: m.LoanPolicySnapshot.objects.filter(pk=snapshot.policy_snapshot_id).update(basis="ORIGINATION")):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    action()
            with without_workspace_context(), workspace_context(other_workspace.pk):
                self.assertFalse(m.PawnLoanDisbursalSnapshot.objects.filter(pk=snapshot.pk).exists())
                self.assertEqual(m.PawnLoanDisbursalSnapshot.objects.filter(pk=snapshot.pk).update(net_disbursed=1), 0)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")
