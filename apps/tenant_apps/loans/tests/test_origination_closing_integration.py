"""Corrected source agreements continue through the shared closing entry."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from uuid import uuid4

import fitz
from django.test import override_settings
from django.urls import reverse

from apps.tenancy.testing import start_workspace_trial
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.selectors.servicing_contract import get_servicing_position
from apps.tenant_apps.loans.services.agreement_corrections import (
    preview_agreement_correction,
    record_agreement_correction,
)
from apps.tenant_apps.loans.services.borrower_corrections import (
    preview_borrower_correction,
    record_borrower_correction,
)
from apps.tenant_apps.loans.services.collateral_corrections import (
    item_details,
    preview_collateral_correction,
    record_collateral_correction,
)
from apps.tenant_apps.loans.services.documents import PawnLoanDocumentService
from apps.tenant_apps.party.models import Party
from .test_continuation_admissions import AdmissionFixture
from .test_settlement_continuation import on


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class OriginationClosingIntegrationTests(AdmissionFixture):
    actual = date(2026, 5, 6)

    def assert_redirect(self, response):
        if response.status_code != 302:
            context = response.context or {}
            self.fail(
                str(context.get("error"))
                + str(context.get("form").errors if context.get("form") else "")
                + str(
                    context.get("confirmation_form").errors
                    if context.get("confirmation_form")
                    else ""
                )
            )

    def correct(self, loan):
        old_events = list(loan.loan_events.order_by("pk").values())
        old_policy = deepcopy(loan.policy_snapshot)
        old_pdf = PawnLoanDocumentService.render_loan_ticket(loan).pdf
        customer = Party.objects.create(display_name="Journey Borrower " + str(loan.pk))
        facts = dict(
            borrower_id=customer.pk,
            reference="Checked original customer",
            reason="Mistaken selection",
            request_key=uuid4().hex,
        )
        _, token = preview_borrower_correction(loan.pk, actor=self.actor, data=facts)
        record_borrower_correction(
            loan.pk, actor=self.actor, data=facts, review_token=token, confirmed=True
        )
        loan.refresh_from_db()
        item = loan.collateral_items.get()
        facts = dict(
            item_id=item.pk,
            after=item_details(item) | {"description": "Corrected original gold ring"},
            reference="Checked original item",
            reason="Description mistyped",
            request_key=uuid4().hex,
        )
        _, token = preview_collateral_correction(loan.pk, actor=self.actor, data=facts)
        record_collateral_correction(
            loan.pk, actor=self.actor, data=facts, review_token=token, confirmed=True
        )
        facts = dict(
            date=loan.loan_date.isoformat(),
            principal="6000",
            rate="3",
            cash_paid="5820",
            reference="Checked original agreement",
            reason="Original financial entry mistyped",
            request_key=uuid4().hex,
        )
        _, token = preview_agreement_correction(loan.pk, actor=self.actor, data=facts)
        record_agreement_correction(
            loan.pk, actor=self.actor, data=facts, review_token=token, confirmed=True
        )
        loan.refresh_from_db()
        self.assertEqual(loan.borrower_id, customer.pk)
        self.assertEqual(loan.principal_amount, Decimal("6000"))
        self.assertEqual(
            loan.collateral_items.get().description, "Corrected original gold ring"
        )
        self.assertEqual(
            list(
                loan.loan_events.filter(pk__in=[row["id"] for row in old_events])
                .order_by("pk")
                .values()
            ),
            old_events,
        )
        self.assertEqual(
            loan.policy_snapshot.partial_month_method, old_policy.partial_month_method
        )
        self.assertEqual(
            loan.policy_snapshot.valuation_method, old_policy.valuation_method
        )
        pdf = PawnLoanDocumentService.render_loan_ticket(loan).pdf
        self.assertNotEqual(pdf, old_pdf)
        with fitz.open(stream=pdf, filetype="pdf") as document:
            text = " ".join(page.get_text() for page in document)
        self.assertIn(customer.display_name, text)
        self.assertIn("6,000", text)

    def run_journey(self, *, completed, multiple):
        today = date(2026, 5, 7) if completed else self.actual
        selected = (
            (self.direct, self.paper)
            if multiple
            else (self.paper if completed else self.direct,)
        )
        with self.scoped(), on(self.actual):
            policies = list(m.LoanMonitoringPolicy.objects.order_by("pk").values())
            for loan in selected:
                m.LoanNumberSequence.objects.get_or_create(
                    series=loan.series,
                    document_kind="PAWN_LOAN_RELEASE",
                    defaults={"prefix": f"JOURNEY-{loan.series_id}-", "width": 5},
                )
                self.correct(loan)
            self.assertEqual(
                list(m.LoanMonitoringPolicy.objects.order_by("pk").values()), policies
            )
        start_workspace_trial(self.a)
        self.client.force_login(self.actor)
        path = reverse("workspace_loans:loan_closing_create", args=[self.a.slug])
        ids = [loan.pk for loan in selected]
        with self.scoped(), on(today):
            for loan in selected:
                page = self.client.get(
                    reverse(
                        "workspace_loans:pawn_loan_detail", args=[self.a.slug, loan.pk]
                    )
                )
                self.assertContains(page, "data-close-release-action")
            purpose = "PAPER" if completed else "CURRENT"
            page = self.client.get(path, {"purpose": purpose, "loans": ids})
            self.assertEqual(page.status_code, 200)
            if completed:
                payload = dict(
                    purpose=purpose,
                    loans=ids,
                    action="review",
                    request_key=str(uuid4()),
                    closure_date=self.actual.isoformat(),
                    paper_reference="Checked earlier settlement",
                )
                page = self.client.post(path, payload)
                self.assertEqual(len(page.context["rows"]), len(selected))
                payload.update(
                    action="complete",
                    confirmed="on",
                    quote_token=page.context["header"]["quote_token"].value(),
                )
                for row in page.context["rows"]:
                    self.assertNotIn("error", row)
                    pk = row["loan"].pk
                    payload.update(
                        {
                            f"row_{pk}-include": "on",
                            f"row_{pk}-amount": row["form"]["amount"].value(),
                            f"row_{pk}-basis": "RETURNED",
                            f"row_{pk}-collector_is_borrower": "yes",
                            f"row_{pk}-collector_name": row[
                                "loan"
                            ].borrower.display_name,
                            f"row_{pk}-paid_by": row["loan"].borrower.display_name,
                        }
                    )
                response = self.client.post(path, payload)
                self.assertFalse(
                    response.context.get("error"),
                    str(response.context.get("error"))
                    + str([row["form"].errors for row in response.context["rows"]]),
                )
                self.assertIsNotNone(response.context["completed"])
                retry = self.client.post(path, payload)
                self.assertEqual(
                    retry.context["completed"].pk, response.context["completed"].pk
                )
            elif multiple:
                header = page.context["confirmation_form"]
                payload = dict(
                    purpose=purpose,
                    loans=ids,
                    action="complete",
                    request_key=header["request_key"].value(),
                    quote_token=header["quote_token"].value(),
                    paid_by="Actual combined payer",
                    payment_confirmed="on",
                )
                for loan in selected:
                    payload.update(
                        {
                            f"collector_{loan.pk}-loan_id": loan.pk,
                            f"collector_{loan.pk}-collector_type": "borrower",
                            f"collector_{loan.pk}-handover_confirmed": "on",
                        }
                    )
                response = self.client.post(path, payload)
                self.assert_redirect(response)
                response = self.client.post(path, payload)
                self.assert_redirect(response)
            else:
                payload = dict(
                    purpose=purpose,
                    loans=ids,
                    request_key=str(uuid4()),
                    settlement_amount=str(page.context["quote"].minimum_settlement),
                    interest_concession="0",
                    confirm_collateral_handoff="on",
                )
                self.assert_redirect(self.client.post(path, payload))
                self.assert_redirect(self.client.post(path, payload))
            for loan in selected:
                loan.refresh_from_db()
                self.assertEqual(loan.state, "CLOSED")
                release = loan.releases.get()
                self.assertEqual(release.effective_date, self.actual)
                self.assertEqual(
                    loan.collateral_items.get().custody_state, "WITH_CUSTOMER"
                )
                self.assertEqual(
                    get_servicing_position(loan, as_of_date=today).balance.total_due, 0
                )
            self.assertEqual(
                m.PawnLoanRelease.objects.filter(loan_id__in=ids).count(), len(selected)
            )

    def test_corrected_direct_current_single(self):
        self.run_journey(completed=False, multiple=False)

    def test_corrected_paper_earlier_single(self):
        self.run_journey(completed=True, multiple=False)

    def test_corrected_direct_and_paper_current_multiple(self):
        self.run_journey(completed=False, multiple=True)

    def test_corrected_direct_and_paper_earlier_multiple(self):
        self.run_journey(completed=True, multiple=True)
