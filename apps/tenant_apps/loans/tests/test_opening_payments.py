from datetime import date
from unittest.mock import patch
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from .test_opening_release import OpeningReleaseFixture
from apps.tenant_apps.loans.services.pawn_repayment import preview_pawn_loan_repayment, record_pawn_loan_repayment
from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
from apps.tenant_apps.loans.selectors import get_pawn_loan_balance, get_pawn_loan_exposure
from apps.tenant_apps.loans.services.pawn_tranches import get_pawn_principal_tranche_balances


class OpeningPaymentTests(OpeningReleaseFixture):
    def pay(self, amount, key="payment"):
        return record_pawn_loan_repayment(self.loan.pk, amount=amount, request_key=key, actor=self.actor)

    def exposure(self, on=None):
        return get_pawn_loan_exposure(self.loan.pk, as_of_date=on or self.day).total_economic_exposure

    def test_interest_only_payment_then_next_charge(self):
        preview = preview_pawn_loan_repayment(self.loan.pk, amount=10)
        self.assertEqual((preview.allocation.interest, preview.allocation.principal), (10, 0))
        result = self.pay(10)
        self.assertEqual(result.allocation.interest, 10)
        self.assertEqual(self.exposure(), 1000)
        self.assertEqual(self.exposure(date(2021, 3, 2)), 1010)
        self.assertEqual(self.loan.loan_events.count(), 3)
        self.assertTrue(self.pay(10).already_recorded)
        with self.assertRaises(ValueError):
            self.pay(11)
        with self.assertRaises(PermissionDenied):
            record_pawn_loan_repayment(self.loan.pk, amount=10, request_key="payment", actor=None)

    def test_partial_principal_changes_next_charge_not_current_month(self):
        result = self.pay(210)
        self.assertEqual((result.allocation.interest, result.allocation.principal), (10, 200))
        self.assertEqual(get_pawn_principal_tranche_balances(self.loan)[0].principal_outstanding, 800)
        self.assertEqual(self.exposure(date(2021, 3, 1)), 800)
        self.assertEqual(self.exposure(date(2021, 3, 2)), 808)
        self.day = date(2021, 3, 2)
        second = self.pay(108, "second")
        self.assertEqual(second.allocation.principal, 100)
        self.assertEqual(self.exposure(date(2021, 4, 2)), 707)
        self.assertEqual(get_pawn_loan_balance(self.loan, as_of_date=self.day).interest_accrued, 18)

    def test_payment_reversal_restores_interest_and_principal_and_as_of_history(self):
        result = self.pay(210)
        self.day = date(2021, 3, 3)
        reversal = reverse_pawn_loan_event(result.loan_event.pk, actor=self.actor, reason="Wrong collection")
        self.assertIsNotNone(reversal.catch_up_reversal_event)
        self.assertEqual(self.exposure(), 1020)
        self.assertEqual(self.exposure(date(2021, 2, 3)), 800)
        self.assertEqual(get_pawn_principal_tranche_balances(self.loan)[0].principal_outstanding, 1000)
        self.assertTrue(reverse_pawn_loan_event(result.loan_event.pk, actor=self.actor, reason="Wrong collection").already_reversed)

    def test_release_after_payment_and_reverse_both_newest_first(self):
        payment = self.pay(210)
        self.day = date(2021, 3, 2)
        release = self.release()
        self.assertEqual(release.release.settlement_amount, 808)
        self.assertEqual(self.exposure(), 0)
        with self.assertRaises(ValueError):
            reverse_pawn_loan_event(payment.loan_event.pk, actor=self.actor, reason="Wrong order")
        reverse_pawn_loan_event(release.loan_event.pk, actor=self.actor, reason="Return cancelled")
        self.assertEqual(self.exposure(), 808)
        reverse_pawn_loan_event(payment.loan_event.pk, actor=self.actor, reason="Payment cancelled")
        self.assertEqual(self.exposure(), 1020)

    def test_payment_after_reversal_of_legacy_full_release(self):
        release = self.release()
        reverse_pawn_loan_event(release.loan_event.pk, actor=self.actor, reason="Return cancelled")
        self.pay(210)
        self.assertEqual(self.exposure(date(2021, 3, 2)), 808)

    def test_tampered_collection_checkpoint_and_principal_allocation_fail_closed(self):
        from copy import deepcopy
        from types import SimpleNamespace
        from apps.tenant_apps.loans.services.opening_continuation import preview_opening_collection
        result = self.pay(210)
        events = [SimpleNamespace(pk=e.pk, event_kind=e.event_kind, effective_date=e.effective_date,
                  payload=deepcopy(e.payload), reversal_of_id=e.reversal_of_id) for e in self.loan.loan_events.all()]
        payment = next(e for e in events if e.pk == result.loan_event.pk)
        payment.payload["opening_collection"]["baseline_as_of"] = "11"
        with self.assertRaises(ValueError):
            preview_opening_collection(self.loan, events=events, as_of_date=self.day)
        payment.payload = deepcopy(result.loan_event.payload)
        payment.payload["repayment"]["item_principal_allocations"][0]["balance_after"] = "799"
        with self.assertRaises(ValueError):
            preview_opening_collection(self.loan, events=events, as_of_date=self.day)

    def test_rollback_includes_catch_up_payment_and_item_lines(self):
        with patch("apps.tenant_apps.loans.services.pawn_repayment.allocate_event_to_obligations", side_effect=RuntimeError("Failure")):
            with self.assertRaises(RuntimeError):
                self.pay(210)
        self.assertEqual(self.loan.loan_events.count(), 1)
        self.assertFalse(self.loan.interest_accruals.exists())
        self.assertEqual(self.exposure(), 1010)

    def test_all_money_paid_keeps_collateral_and_requires_explicit_release(self):
        self.pay(1010)
        self.loan.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(self.loan.state, "ACTIVE")
        self.assertEqual(self.item.custody_state, "IN_VAULT")
        self.assertEqual(self.exposure(date(2021, 3, 2)), 0)
        self.assertEqual(self.release().release.settlement_amount, 0)

    def test_cutover_and_overpayment_rejected_without_events(self):
        with self.assertRaises(ValueError):
            self.pay(1011)
        self.day = date(2021, 1, 20)
        with self.assertRaises(ValueError):
            self.pay(10)
        self.assertEqual(self.loan.loan_events.count(), 1)

    def test_same_day_payments_and_next_month_only_charge_once(self):
        self.pay(210)
        second = self.pay(100, "second")
        self.assertEqual(second.allocation.interest, 0)
        self.assertEqual(self.loan.interest_accruals.count(), 1)
        self.assertEqual(self.exposure(date(2021, 3, 2)), 707)
        reverse_pawn_loan_event(second.loan_event.pk, actor=self.actor, reason="Wrong amount")
        self.assertEqual(self.exposure(date(2021, 3, 2)), 808)

    def test_payment_on_anniversary_uses_next_charge_and_preserves_inclusive_calendar(self):
        self.day = date(2021, 2, 1)
        self.pay(200)
        self.assertEqual(self.exposure(), 800)
        self.assertEqual(self.exposure(date(2021, 2, 2)), 808)
        self.assertEqual(self.exposure(date(2021, 3, 1)), 808)
        self.assertEqual(self.exposure(date(2021, 3, 2)), 816)

    def test_repayment_staff_permissions_and_cross_workspace(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        from apps.orgs.models import Company, Membership, Role
        from apps.tenancy.testing import workspace_role_permissions
        from apps.tenancy.context import without_workspace_context, workspace_context
        user = get_user_model().objects.create_user(username="opening-payment-staff")
        role = Role.objects.create(name="Opening payment staff")
        Membership.objects.create(company=self.tenant, user=user, role=role)
        workspace_role_permissions(role, self.tenant).set(Permission.objects.filter(
            content_type__app_label="orgs", content_type__model="company", codename__in=["data_view", "loan_repay"]))
        result = record_pawn_loan_repayment(self.loan.pk, amount=210, request_key="staff", actor=user)
        self.assertEqual(result.allocation.principal, 200)
        with self.assertRaises(PermissionDenied):
            self.release(actor=user)
        with self.assertRaises(ValueError):
            reverse_pawn_loan_event(result.loan_event.pk, actor=user, reason="Not allowed")
        other = Company.objects.create(name="Other", schema_name="opening-payments-other", owner=self.actor, creator=self.actor)
        with without_workspace_context(), workspace_context(other.pk), self.assertRaises(ValueError):
            self.pay(10, "foreign")

    def test_failed_payment_reversal_rolls_back_both_compensating_events(self):
        payment = self.pay(210)
        with patch("apps.tenant_apps.loans.services.pawn_reversal._reverse_opening_payment_catch_up", side_effect=RuntimeError("Failure")):
            with self.assertRaises(RuntimeError):
                reverse_pawn_loan_event(payment.loan_event.pk, actor=self.actor, reason="Wrong")
        self.assertFalse(self.loan.loan_events.filter(event_kind="REVERSAL").exists())
        self.assertEqual(self.exposure(), 800)

    @override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    })
    def test_payment_form_preview_commit_detail_and_receipt(self):
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        args = {"workspace_slug": self.tenant.slug, "pk": self.loan.pk}
        url = reverse("workspace_loans:pawn_loan_repay", kwargs=args)
        detail = reverse("workspace_loans:pawn_loan_detail", kwargs=args)
        self.assertContains(client.get(detail), url)
        self.assertContains(client.get(url), "1010")
        data = {"amount": "210", "request_key": "http-payment", "action": "preview"}
        self.assertContains(client.post(url, data), "Preview only")
        self.assertEqual(self.loan.loan_events.count(), 1)
        self.assertEqual(client.post(url, {**data, "action": "confirm"}).status_code, 302)
        self.assertContains(client.get(detail), "Monthly interest on the remaining principal")
        event = self.loan.loan_events.get(event_kind="REPAYMENT")
        pdf = client.get(reverse("workspace_loans:pawn_repayment_receipt_pdf", kwargs={**args, "event_pk": event.pk}))
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")


class OpeningPaymentRoundingTests(OpeningReleaseFixture):
    pay = OpeningPaymentTests.pay
    exposure = OpeningPaymentTests.exposure
    def review_document(self):
        from .test_opening_continuation import collection_review
        return collection_review(cutover=date(2021, 2, 2), rate="14.82")

    def test_cumulative_rounding_after_reduction(self):
        self.day = date(2021, 3, 2)
        result = self.pay(496)  # 148 opening + 148 new interest, 200 principal.
        self.assertEqual(result.allocation.principal, 200)
        self.assertEqual(self.exposure(date(2021, 4, 2)), 919)  # round(296.4 + 118.56) - 296 = 119.


class OpeningPaymentCoveredTests(OpeningReleaseFixture):
    pay = OpeningPaymentTests.pay
    exposure = OpeningPaymentTests.exposure

    def review_document(self):
        from .test_opening_continuation import collection_review
        review = collection_review(cutover=date(2021, 3, 15), unpaid="15")
        review["balances"]["fees"] = "5"
        return review

    def test_opening_fees_then_interest_and_partial_interest_collection(self):
        self.day = date(2021, 4, 2)
        first = self.pay(8)
        self.assertEqual((first.allocation.fees, first.allocation.interest, first.allocation.principal), (5, 3, 0))
        self.assertEqual(self.exposure(), 1022)
        second = self.pay(222, "second")
        self.assertEqual((second.allocation.interest, second.allocation.principal), (22, 200))
        self.assertEqual(self.exposure(date(2021, 5, 2)), 808)


class OpeningMonthEndPaymentTests(SimpleTestCase):
    def test_february_clamping_does_not_shift_march_anniversary(self):
        from types import SimpleNamespace
        from .test_opening_continuation import collection_review
        from apps.tenant_apps.loans.services.opening_payment_evidence import baseline
        review = collection_review(original=date(2020, 1, 31), cutover=date(2020, 2, 1))
        payment = SimpleNamespace(event_kind="REPAYMENT", effective_date=date(2020, 2, 28),
            payload={"repayment": {"item_principal_allocations": [{"principal_applied": "200", "monthly_interest_rate": "1"}]}})
        actions = [(payment, None)]
        self.assertEqual(baseline(review, actions, date(2020, 2, 29))[0], 0)
        self.assertEqual(baseline(review, actions, date(2020, 3, 1))[0], 8)
        self.assertEqual(baseline(review, actions, date(2020, 3, 31))[0], 8)
        self.assertEqual(baseline(review, actions, date(2020, 4, 1))[0], 16)
