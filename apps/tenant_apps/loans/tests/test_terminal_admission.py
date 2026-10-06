"""Verified zero position must not invent disbursal, receipts or handover."""
from copy import deepcopy
from types import SimpleNamespace

from django.db import connection, transaction, DatabaseError
from django.core.exceptions import PermissionDenied
from django.test import override_settings
from django.urls import reverse

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.terminal_admission import preview_terminal_admission, admit_terminal_position
from apps.tenant_apps.loans.services.archive_admission import archive_origin
from apps.tenant_apps.loans.services.archive import export_evidence
from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance, calculate_pawn_loan_balance
from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
from .test_recorded_origination import RecordedOriginationTests
from .test_recorded_history import RecordedHistoryTests
from .test_archive_admission import ArchiveAdmissionTests


class TerminalAdmissionTests(RecordedOriginationTests):
    prepare_history = RecordedHistoryTests.prepare_history
    prepare_archive = ArchiveAdmissionTests.prepare_archive
    accept = ArchiveAdmissionTests.accept
    row = RecordedHistoryTests.row

    def setUp(self):
        super().setUp()
        self.start_active_trial()
        self.prepare_history()
        self.prepare_archive()
        self.terminal = {key: self.data[key] for key in ("borrower_id", "series_id", "product_version_id", "number", "date",
            "tenure", "source_reference", "monitoring_method", "monitoring_ltv", "monitoring_reason")}
        self.terminal.update(currency_quantum="0.01", collateral=[{key: self.data[key] for key in (
            "description", "metal", "quantity", "gross_weight", "net_weight", "purity", "principal", "rate")}],
            closed_on=self.today.isoformat(), closure_reference="Checked closure register and signed agreement; receipts incomplete.",
            custody="UNKNOWN", confirmed_agreement=True, confirmed_closed=True)
        self.terminal_args = dict(self.args, evidence_id=self.evidence.public_id)

    def terminal_admit(self):
        before = m.PawnLoan.objects.count()
        summary, token = preview_terminal_admission(**self.terminal_args, data=self.terminal)
        self.assertEqual(m.PawnLoan.objects.count(), before)
        loan, created = admit_terminal_position(**self.terminal_args, data=self.terminal, review_token=token, confirmed=True)
        self.assertTrue(created)
        return loan, summary, token

    @override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_owner_can_review_closed_position_in_ordinary_interface(self):
        client = self.make_workspace_client()
        client.force_login(self.actor)
        url = reverse("workspace_loans:pawn_loan_record_closed_position", kwargs={"workspace_slug": self.tenant.slug})
        page = client.get(url, {"archive": str(self.evidence.public_id)})
        self.assertEqual(page.status_code, 200)
        values = {k: v for k, v in self.terminal.items() if k != "collateral"}
        values.update(archive_evidence_id=str(self.evidence.public_id), intent_token=page.context["intent_token"], action="preview",
            **{"collateral-TOTAL_FORMS": "1", "collateral-INITIAL_FORMS": "0"})
        aliases = {"purity": "purity_percentage", "principal": "allocated_principal", "rate": "interest_rate_override"}
        values.update({"collateral-0-" + aliases.get(k, k): v for k, v in self.terminal["collateral"][0].items()})
        page = client.post(url, values)
        self.assertEqual(page.context["form"].errors, {})
        self.assertTrue(page.context["review"], page.context["collateral"].errors)
        values.update(action="confirm", confirmed="yes", review_token=page.context["review_token"])
        admitted = client.post(url, values)
        self.assertEqual(admitted.status_code, 302)
        self.assertContains(client.get(admitted.url), "Earlier receipts")

    def test_closed_archive_becomes_ordinary_without_invented_cash_or_receipts(self):
        source = export_evidence(workspace_id=self.tenant.pk, actor=self.actor, evidence_id=self.evidence.public_id)
        loan, summary, token = self.terminal_admit()
        self.assertEqual(loan.state, "CLOSED")
        self.assertEqual(loan.principal_amount, 10000)
        self.assertEqual(loan.loan_date, self.day)
        self.assertFalse(loan.approval_snapshots.exists())
        self.assertFalse(loan.disbursal_snapshot_id)
        self.assertFalse(loan.releases.exists())
        self.assertFalse(loan.repayment_schedules.exists())
        from apps.tenant_apps.loans.selectors.interest_contract_inventory import interest_contract_inventory
        inventory = next(row for row in interest_contract_inventory() if row["loan_id"] == loan.pk)
        self.assertEqual(inventory["status"], "VERIFIED_TERMINAL_POSITION")
        self.assertEqual(transaction_completeness(loan, self.today).evidence()["capture_basis"], "VERIFIED_TERMINAL_POSITION")
        self.assertEqual(list(loan.loan_events.values_list("event_kind", flat=True)), ["MIGRATION_OPENING"])
        balance = get_pawn_loan_balance(loan, as_of_date=self.today)
        self.assertEqual((balance.total_due, balance.principal_disbursed, balance.principal_paid, balance.interest_paid), (0, 0, 0, 0))
        self.assertTrue(balance.financially_settled)
        self.assertFalse(balance.collateral_return_complete)
        self.assertEqual(loan.collateral_items.get().custody_state, "PAPER_CLOSED")
        exposure = get_pawn_loan_exposure(loan.pk, as_of_date=self.today)
        self.assertEqual(exposure.original_principal, 10000)
        self.assertEqual(exposure.total_economic_exposure, 0)
        self.assertEqual(exposure.principal_history_basis, "VERIFIED_TERMINAL_POSITION")
        self.assertEqual(summary["earlier_receipts"], "UNAVAILABLE")
        self.assertFalse(transaction_completeness(loan, self.today).complete)
        self.assertEqual(archive_origin(self.evidence).loan_id, loan.pk)
        self.assertEqual(export_evidence(workspace_id=self.tenant.pk, actor=self.actor, evidence_id=self.evidence.public_id), source)
        self.assertFalse(admit_terminal_position(**self.terminal_args, data=self.terminal, review_token=token, confirmed=True)[1])

    def test_release_inventory_keeps_archive_and_terminal_position_distinct(self):
        from apps.tenant_apps.loans.selectors.release_inventory import loan_release_inventory
        before = loan_release_inventory(as_of_date=self.today)
        self.assertEqual(before["census"]["unadmitted_archive_identities"], 1)
        loan, _, _ = self.terminal_admit()
        after = loan_release_inventory(as_of_date=self.today)
        self.assertEqual(after["census"]["archive_snapshots"], 1)
        self.assertEqual(after["census"]["unadmitted_archive_identities"], 0)
        row = next(r for r in after["loans"] if r["loan_id"] == loan.pk)
        self.assertEqual(row["contract_profile"], "loan-terminal-position/1")
        self.assertEqual(row["recorded_due"], 0)
        self.assertFalse(row["transactions"]["complete"])
        self.assertEqual(row["servicing_prerequisites"], {})

    def test_returned_checkpoint_is_known_position_without_fake_return_event(self):
        self.terminal["custody"] = "RETURNED"
        loan, _, _ = self.terminal_admit()
        balance = get_pawn_loan_balance(loan, as_of_date=self.today)
        self.assertTrue(balance.collateral_return_complete)
        self.assertEqual(loan.collateral_items.get().custody_state, "WITH_CUSTOMER")
        self.assertFalse(m.PawnCollateralCustodyEvent.objects.filter(collateral_item__loan=loan).exists())

    def test_unknown_receipts_do_not_prevent_admission_but_conflicting_agreement_does(self):
        for key, value in (("number", "Different"), ("closed_on", self.day.isoformat()), ("confirmed_closed", False)):
            changed = deepcopy(self.terminal)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                preview_terminal_admission(**self.terminal_args, data=changed)

    def test_no_earlier_balance_repayment_or_reversal_of_nonexistent_settlement(self):
        loan, _, _ = self.terminal_admit()
        with self.assertRaises(ValueError):
            get_pawn_loan_balance(loan, as_of_date=self.day)
        with self.assertRaises(ValueError):
            record_pawn_loan_repayment(loan.pk, amount=1, request_key="impossible", actor=self.actor)
        with self.assertRaises(ValueError):
            reverse_pawn_loan_event(loan.loan_events.get().pk, actor=self.actor, reason="Cannot reverse missing receipt")
        with transaction.atomic(), self.assertRaises(DatabaseError), transaction.atomic():
            m.PawnLoan.objects.filter(pk=loan.pk).update(state="ACTIVE")
        with transaction.atomic(), self.assertRaises(DatabaseError), transaction.atomic():
            event = loan.loan_events.get()
            m.PawnLoanEvent.objects.create(workspace=self.tenant, loan=loan, event_kind="REPAYMENT", effective_date=self.today,
                payload={"values": {"principal": "1"}}, payload_fingerprint="f"*64, idempotency_key="terminal-forged")
        self.assertEqual(loan.loan_events.count(), 1)

    def test_stale_review_and_source_snapshot_changes_roll_back(self):
        _, token = preview_terminal_admission(**self.terminal_args, data=self.terminal)
        changed = deepcopy(self.terminal)
        changed["custody"] = "RETURNED"
        before = m.PawnLoan.objects.count()
        with self.assertRaises(ValueError):
            admit_terminal_position(**self.terminal_args, data=changed, review_token=token, confirmed=True)
        self.assertEqual(m.PawnLoan.objects.count(), before)

    def test_tampered_zero_checkpoint_fails_reads(self):
        loan, _, _ = self.terminal_admit()
        event = loan.loan_events.get()
        payload = deepcopy(event.payload)
        payload["opening"]["review"]["data"]["confirmed_closed"] = False
        fake = SimpleNamespace(pk=event.pk, event_kind=event.event_kind, effective_date=event.effective_date, payload=payload)
        with self.assertRaises(ValueError):
            calculate_pawn_loan_balance(loan, events=[fake], collateral_items=loan.collateral_items.all(),
                policy_snapshot=loan.policy_snapshot, as_of_date=self.today)
