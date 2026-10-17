"""One closing experience preserves current/completed cash and custody meaning."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.urls import reverse

from apps.orgs.models import Membership, Role
from apps.tenant_apps.loans.models import (
    PawnLoan,
    PawnLoanRelease,
    PawnReleaseBatch,
    PawnLoanEvent,
)
from apps.tenant_apps.loans.selectors.servicing_contract import (
    resolve_servicing_contract,
)
from apps.tenant_apps.loans.services import approve_pawn_loan, disburse_pawn_loan
from apps.tenant_apps.loans.services.economic_policies import (
    create_pawn_loan_economic_policy,
)
from apps.tenant_apps.loans.services.servicing_eligibility import servicing_eligibility
from apps.tenant_apps.loans.services.paper_closures import (
    preview_paper_closures,
    complete_paper_closures,
    set_paper_transition,
)
from apps.tenant_apps.loans.services.recorded_closures import (
    preview_recorded_closure,
    record_paper_closure,
)
from apps.tenant_apps.loans.services.pawn_release import preview_pawn_loan_full_release
from apps.tenant_apps.loans.tests import test_release_batches as batch_fixtures


class ClosingWorkflowTests(batch_fixtures.ReleaseBatchTests):
    def url(self, loan=None):
        return reverse(
            "workspace_loans:pawn_loan_close",
            kwargs={
                "workspace_slug": self.tenant.slug,
                "pk": (loan or self.loans[0]).pk,
            },
        )

    def facts(self, loan=None, **overrides):
        loan = loan or self.loans[0]
        quote = preview_pawn_loan_full_release(loan.pk)
        return (
            dict(
                date="2026-07-18",
                amount=str(quote.minimum_settlement),
                number="",
                reference="Book 7",
                basis="PAPER_SETTLEMENT",
                recipient="",
                request_key=str(uuid4()),
                interest_concession="0",
                concession_reason="",
                exception_reason="",
                paid_by="",
                collector_is_borrower=True,
                relationship="",
                authorization_note="",
            )
            | overrides
        )

    def batch(self, **overrides):
        preview = preview_paper_closures(
            workspace=self.tenant,
            actor=self.owner,
            loan_ids=[loan.pk for loan in self.loans],
            closure_date=date(2026, 7, 18),
        )
        return (
            dict(
                workspace=self.tenant,
                actor=self.owner,
                request_key=uuid4(),
                quote_token=preview["token"],
                confirmed=True,
                paper_reference="Book 7",
                rows=[
                    dict(
                        loan_id=row["loan"].pk,
                        amount=str(row["amount"]),
                        basis="PAPER_SETTLEMENT",
                        paid_by="",
                        collector_name="",
                        number="",
                        collector_is_borrower=True,
                    )
                    for row in preview["rows"]
                ],
            )
            | overrides
        )

    def test_one_screen_requires_explicit_purpose_independently_of_native_origin(self):
        response = self.client.get(self.url())
        self.assertContains(response, "Close / release loan")
        self.assertEqual(response.context["closing_purpose"], "")
        self.assertEqual(
            [loan.pk for loan in response.context["closing_selected_loans"]],
            [self.loans[0].pk],
        )
        self.assertContains(response, "Record a settlement already completed")
        response = self.client.get(self.url(), {"purpose": "CURRENT"})
        self.assertEqual(response.context["closure_purpose"], "CURRENT")
        self.assertContains(response, "Confirm collection and full release")
        self.assertEqual(self.client.post(self.url(), {}).status_code, 400)
        self.assertEqual(
            self.client.get(self.url(), {"purpose": "UNKNOWN"}).status_code, 400
        )

    def test_unified_current_confirmation_uses_ordinary_release(self):
        amount = preview_pawn_loan_full_release(self.loans[0].pk).minimum_settlement
        response = self.client.post(
            self.url(),
            dict(
                purpose="CURRENT",
                request_key=str(uuid4()),
                settlement_amount=str(amount),
                confirm_collateral_handoff="on",
            ),
        )
        self.assertEqual(response.status_code, 302)
        release = self.loans[0].releases.get()
        self.assertNotIn("paper_closure", release.loan_event.payload["release"])
        self.assertTrue(
            all(item.returned_at is not None for item in release.items.all())
        )

    def test_unified_completed_review_confirm_and_duplicate_are_not_current_cash(self):
        facts = self.facts()
        web = dict(
            facts, collector_is_borrower="yes", purpose="PAPER", action="preview"
        )
        response = self.client.post(self.url(), web)
        self.assertContains(
            response, "Physical cash and customer handover remain unconfirmed"
        )
        self.assertFalse(PawnLoanRelease.objects.exists())
        web.update(
            action="confirm",
            confirmed="on",
            review_token=response.context["review_token"],
        )
        self.assertEqual(self.client.post(self.url(), web).status_code, 302)
        self.assertEqual(self.client.post(self.url(), web).status_code, 302)
        self.assertEqual(PawnLoanRelease.objects.count(), 1)
        self.assertEqual(
            self.loans[0].collateral_items.get().custody_state, "PAPER_CLOSED"
        )

    def test_mixed_bulk_retains_independent_settlement_and_unknown_custody_and_csv(
        self,
    ):
        command = self.batch()
        returned = command["rows"][1]
        returned.update(
            basis="RETURNED",
            paid_by="Family payer",
            collector_name=self.loans[1].borrower.display_name,
            number="PAPER-CLOSE-2",
        )
        with patch("django.utils.timezone.localdate", return_value=date(2026, 7, 20)):
            batch = complete_paper_closures(**command)
        self.assertEqual(batch.effective_date, date(2026, 7, 18))
        self.assertEqual(
            batch.total_amount, sum(Decimal(row["amount"]) for row in command["rows"])
        )
        self.assertEqual(complete_paper_closures(**command).pk, batch.pk)
        self.assertEqual(
            self.loans[0].collateral_items.get().custody_state, "PAPER_CLOSED"
        )
        self.assertEqual(
            self.loans[1].collateral_items.get().custody_state, "WITH_CUSTOMER"
        )
        self.assertEqual(self.loans[1].releases.get().release_number, "PAPER-CLOSE-2")
        self.assertTrue(
            all(
                item.returned_at is None
                for release in PawnLoanRelease.objects.all()
                for item in release.items.all()
            )
        )
        from apps.tenant_apps.loans.documents.payloads import (
            PawnLoanDocumentProjectionBuilder,
        )

        payload = PawnLoanDocumentProjectionBuilder.release_memo(
            self.loans[0].releases.get()
        )
        self.assertIn(
            ("Collected by", "Not confirmed by paper record"), payload.details
        )
        self.assertNotIn(
            "Borrower receipt attested from paper record", str(payload.details)
        )
        detail = self.client.get(
            reverse(
                "workspace_loans:release_batch_detail",
                kwargs={"workspace_slug": self.tenant.slug, "batch_pk": batch.pk},
            )
        )
        self.assertContains(
            detail, "Physical cash and customer handover were not established"
        )
        csv = self.client.get(
            reverse(
                "workspace_loans:paper_closure_csv",
                kwargs={"workspace_slug": self.tenant.slug, "batch_pk": batch.pk},
            )
        )
        self.assertContains(csv, "Not established")
        self.assertContains(csv, "Settlement amount")

    def test_bad_row_rolls_back_all_extended_settlements_and_original_numbers(self):
        command = self.batch()
        command["rows"][0]["number"] = "SOURCE-CLOSE-1"
        command["rows"][1]["amount"] = str(Decimal(command["rows"][1]["amount"]) + 1)
        before = PawnLoanEvent.objects.count()
        with self.assertRaises(ValueError):
            complete_paper_closures(**command)
        self.assertFalse(PawnLoanRelease.objects.exists())
        self.assertFalse(PawnReleaseBatch.objects.exists())
        self.assertEqual(PawnLoanEvent.objects.count(), before)
        for loan in self.loans:
            loan.refresh_from_db()
            self.assertEqual(loan.state, "ACTIVE")

    def test_optional_restriction_rechecks_single_and_bulk_and_retains_exceptions(self):
        facts = self.facts()
        _, token = preview_recorded_closure(
            loan_id=self.loans[0].pk, actor=self.owner, data=facts
        )
        batch = self.batch()
        set_paper_transition(
            workspace=self.tenant,
            actor=self.owner,
            system_first_date=date(2026, 7, 18),
            retired=True,
            reason="Owner operating commitment",
        )
        with self.assertRaisesMessage(ValueError, "exception reason"):
            record_paper_closure(
                loan_id=self.loans[0].pk,
                actor=self.owner,
                data=facts,
                review_token=token,
                confirmed=True,
            )
        with self.assertRaisesMessage(ValueError, "exception reason"):
            complete_paper_closures(**batch)
        facts["exception_reason"] = "Outage entry"
        _, token = preview_recorded_closure(
            loan_id=self.loans[0].pk, actor=self.owner, data=facts
        )
        release, _ = record_paper_closure(
            loan_id=self.loans[0].pk,
            actor=self.owner,
            data=facts,
            review_token=token,
            confirmed=True,
        )
        self.assertEqual(
            release.loan_event.payload["release"]["paper_closure"]["exception_reason"],
            "Outage entry",
        )
        self.assertEqual(
            self.client.get(self.url(self.loans[1])).context["closing_purpose"], ""
        )

    def test_confirmed_other_recipient_requires_authority_in_both_paths(self):
        facts = self.facts(
            basis="RETURNED",
            recipient="Spouse",
            collector_is_borrower=False,
            paid_by="Borrower",
        )
        with self.assertRaisesMessage(ValueError, "authority"):
            preview_recorded_closure(
                loan_id=self.loans[0].pk, actor=self.owner, data=facts
            )
        command = self.batch()
        command["rows"][0].update(
            basis="RETURNED",
            collector_is_borrower=False,
            paid_by="Borrower",
            collector_name="Spouse",
        )
        with self.assertRaises(ValueError):
            complete_paper_closures(**command)
        facts.update(relationship="Spouse", authorization_note="Signed authority")
        _, token = preview_recorded_closure(
            loan_id=self.loans[0].pk, actor=self.owner, data=facts
        )
        release, _ = record_paper_closure(
            loan_id=self.loans[0].pk,
            actor=self.owner,
            data=facts,
            review_token=token,
            confirmed=True,
        )
        from apps.tenant_apps.loans.documents.payloads import (
            PawnLoanDocumentProjectionBuilder,
        )

        memo = PawnLoanDocumentProjectionBuilder.release_memo(release)
        self.assertIn(("Collected by", "Spouse"), memo.details)
        self.assertIn(("Collection authorization", "Signed authority"), memo.details)

    def test_issued_legacy_bulk_form_retry_retains_original_profile_and_digest(self):
        command = self.batch()
        for loan, row in zip(self.loans, command["rows"]):
            row.pop("basis")
            row.pop("number")
            row.update(paid_by="Borrower", collector_name=loan.borrower.display_name)
        batch = complete_paper_closures(**command)
        data = dict(
            action="complete",
            loans=[str(loan.pk) for loan in self.loans],
            closure_date="2026-07-18",
            paper_reference=command["paper_reference"],
            request_key=str(command["request_key"]),
            quote_token=command["quote_token"],
            confirmed="on",
        )
        for row in command["rows"]:
            prefix = f"row_{row['loan_id']}-"
            data.update(
                {
                    prefix + name: value
                    for name, value in row.items()
                    if name != "loan_id"
                }
            )
            data.update(
                {prefix + "include": "on", prefix + "collector_is_borrower": "yes"}
            )
        url = reverse(
            "workspace_loans:paper_closure_create",
            kwargs={"workspace_slug": self.tenant.slug},
        )
        response = self.client.post(url, data)
        self.assertEqual(response.context["completed"].pk, batch.pk)
        self.assertEqual(PawnReleaseBatch.objects.count(), 1)
        self.assertEqual(PawnLoanRelease.objects.count(), 2)
        for release in PawnLoanRelease.objects.all():
            self.assertEqual(
                release.loan_event.payload["release"]["paper_closure"]["profile"],
                "paper-closure/1",
            )

    def test_owner_can_require_all_recording_exceptions_without_a_cutoff(self):
        url = reverse(
            "workspace_loans:paper_closure_settings",
            kwargs={"workspace_slug": self.tenant.slug},
        )
        response = self.client.post(
            url, dict(retired="on", reason="All actions recorded as they happen")
        )
        self.assertEqual(response.status_code, 302)
        with self.assertRaisesMessage(ValueError, "exception reason"):
            preview_recorded_closure(
                loan_id=self.loans[0].pk, actor=self.owner, data=self.facts()
            )
        self.assertEqual(self.client.get(self.url()).context["closing_purpose"], "")

    def test_extended_unknown_batch_supports_later_handover_without_another_settlement(
        self,
    ):
        batch = complete_paper_closures(**self.batch())
        loan = self.loans[0]
        from apps.tenant_apps.loans.services.paper_handover import (
            preview_paper_handover,
            confirm_paper_handover,
        )

        before = list(loan.loan_events.values_list("pk", "payload_fingerprint"))
        data = dict(
            date="2026-07-18",
            recipient=loan.borrower.display_name,
            reference="Return slip",
            request_key=str(uuid4()),
        )
        _, token = preview_paper_handover(loan.pk, actor=self.owner, data=data)
        confirm_paper_handover(
            loan.pk, actor=self.owner, data=data, review_token=token, confirmed=True
        )
        self.assertEqual(
            before, list(loan.loan_events.values_list("pk", "payload_fingerprint"))
        )
        self.assertEqual(loan.collateral_items.get().custody_state, "WITH_CUSTOMER")
        self.assertEqual(batch.lines.count(), 2)

    def test_restricted_database_guards_require_exact_unknown_evidence(self):
        from apps.tenant_apps.loans.models import PawnReleaseBatchLine

        command = self.batch()
        command["rows"][1].update(
            basis="RETURNED",
            paid_by="Borrower",
            collector_name=self.loans[1].borrower.display_name,
        )
        batch = complete_paper_closures(**command)
        unknown, returned = list(batch.lines.order_by("release__loan_id"))
        role = connection.ops.quote_name("closing_guards_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(
                f"GRANT SELECT ON loans_pawnreleasebatch, loans_pawnloanrelease, loans_pawnloanevent TO {role}"
            )
            cursor.execute(
                f"GRANT SELECT, INSERT, UPDATE ON loans_pawnreleasebatchline TO {role}"
            )
            cursor.execute(
                f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}"
            )
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {role}")
            for source, changes, message in (
                (unknown, dict(paid_by="Invented payer"), "cannot assert payer"),
                (returned, dict(collector_name=""), "Collector confirmation"),
                (returned, dict(paid_by=""), "Paper closure payer required"),
            ):
                values = dict(
                    workspace_id=self.tenant.pk,
                    batch_id=batch.pk,
                    release_id=source.release_id,
                    borrower_name=source.borrower_name,
                    paid_by=source.paid_by,
                    collector_name=source.collector_name,
                    collector_is_borrower=source.collector_is_borrower,
                    relationship=source.relationship,
                    authorization_note=source.authorization_note,
                )
                with (
                    self.subTest(changes=changes),
                    self.assertRaisesMessage(DatabaseError, message),
                    transaction.atomic(),
                ):
                    PawnReleaseBatchLine.objects.create(**(values | changes))
            with (
                self.assertRaisesMessage(DatabaseError, "immutable"),
                transaction.atomic(),
            ):
                batch.lines.update(paid_by="Rewritten")
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    def entry(self):
        return reverse(
            "workspace_loans:loan_closing_create",
            kwargs={"workspace_slug": self.tenant.slug},
        )

    def test_release_navigation_has_one_destination_and_contextual_views(self):
        import re
        from django.utils.html import strip_tags

        routes = (
            "pawn_release_list",
            "release_batch_list",
            "paper_closure_guide",
            "loan_closing_create",
        )
        for route in routes:
            response = self.client.get(
                reverse("workspace_loans:" + route, args=[self.tenant.slug])
            )
            self.assertEqual(response.status_code, 200)
            html = response.content.decode()
            sidebars = re.findall(
                r'<nav[^>]*aria-label="Workspace navigation"[^>]*>(.*?)</nav>',
                html,
                re.S,
            )
            self.assertTrue(sidebars)
            for sidebar in sidebars:
                releases = re.findall(
                    r'<a([^>]*href="[^"]*/loans/releases/[^"]*"[^>]*)>(.*?)</a>',
                    sidebar,
                    re.S,
                )
                self.assertEqual(len(releases), 1)
                self.assertEqual(strip_tags(releases[0][1]).strip(), "Releases")
                self.assertIn("active", releases[0][0])
            self.assertContains(response, 'aria-label="Release views"')
            self.assertContains(response, ">All releases</a>")
            self.assertContains(response, ">Grouped submissions</a>")
            self.assertContains(response, ">Help with closing</a>")
        collateral = self.client.get(
            reverse("workspace_loans:pawn_collateral_list", args=[self.tenant.slug])
        )
        self.assertNotContains(collateral, 'aria-label="Release views"')
        self.assertNotContains(collateral, ">Close / release loans</a>")
        viewer = get_user_model().objects.create_user(username="release-history-viewer")
        role, _ = Role.objects.get_or_create(name="Viewer")
        Membership.objects.create(company=self.tenant, user=viewer, role=role)
        self.client.force_login(viewer)
        for route in routes[:3]:
            response = self.client.get(
                reverse("workspace_loans:" + route, args=[self.tenant.slug])
            )
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(
                response, 'class="btn btn-primary" href="' + self.entry()
            )

    def test_all_releases_includes_standalone_and_completed_group(self):
        self.release_first_for_navigation()
        standalone = self.loans[0].releases.get()
        preview = preview_paper_closures(
            workspace=self.tenant,
            actor=self.owner,
            loan_ids=[self.loans[1].pk],
            closure_date=date(2026, 7, 18),
        )
        command = dict(
            workspace=self.tenant,
            actor=self.owner,
            request_key=uuid4(),
            quote_token=preview["token"],
            confirmed=True,
            paper_reference="Book",
            rows=[
                dict(
                    loan_id=self.loans[1].pk,
                    amount=str(preview["rows"][0]["amount"]),
                    basis="PAPER_SETTLEMENT",
                    paid_by="",
                    number="",
                    interest_concession="0",
                    concession_reason="",
                )
            ],
        )
        batch = complete_paper_closures(**command)
        history = self.client.get(
            reverse("workspace_loans:pawn_release_list", args=[self.tenant.slug])
        )
        self.assertEqual(
            {row.record.pk for row in history.context["table"].rows},
            {standalone.pk, batch.lines.get().release_id},
        )
        grouped = self.client.get(
            reverse("workspace_loans:release_batch_list", args=[self.tenant.slug])
        )
        self.assertEqual([row.pk for row in grouped.context["page"]], [batch.pk])
        self.assertContains(grouped, "Standalone releases are in All releases")

    def test_loan_picker_searches_active_loans_by_number_borrower_code_and_phone(self):
        from apps.tenant_apps.party.models import Party
        from apps.orgs.models import Company
        from apps.tenancy.context import without_workspace_context, workspace_context

        loan = self.loans[0]
        Party.objects.filter(pk=loan.borrower_id).update(primary_phone="+919876543210")
        loan.borrower.refresh_from_db()
        search = reverse(
            "workspace_loans:release_batch_search", args=[self.tenant.slug]
        )
        for term in (
            loan.loan_number,
            loan.borrower.display_name,
            loan.borrower.party_code,
            "987654",
        ):
            response = self.client.get(search, {"q": term})
            self.assertEqual(
                [row["id"] for row in response.json()["results"]], [loan.pk]
            )
        other = Company.objects.create(
            name="Search foreign", owner=self.owner, creator=self.owner
        )
        with without_workspace_context(), workspace_context(other.pk):
            Party.objects.create(display_name="Borrower foreign")
        self.assertEqual(
            self.client.get(search, {"q": "foreign"}).json()["results"], []
        )
        self.release_first_for_navigation()
        remaining = self.client.get(search).json()["results"]
        self.assertEqual([row["id"] for row in remaining], [self.loans[1].pk])

    def release_first_for_navigation(self):
        from apps.tenant_apps.loans.services.pawn_release import (
            release_pawn_loan_in_full,
        )

        loan = self.loans[0]
        quote = preview_pawn_loan_full_release(loan.pk)
        release_pawn_loan_in_full(
            loan.pk,
            settlement_amount=quote.minimum_settlement,
            request_key=str(uuid4()),
            actor=self.owner,
        )

    def weekly_loan(self):
        license, series = self._configured_setup()
        # An ordinary, more-specific configuration before approval freezes it.
        create_pawn_loan_economic_policy(
            workspace=self.tenant,
            license=license,
            series=series,
            valuation_method="LATEST_APPRAISAL",
            maximum_ltv_ratio=Decimal(".8"),
            advance_interest_periods=1,
            partial_month_method="STARTED_WEEKS",
            effective_from=date(2026, 1, 1),
            actor=self.owner,
        )
        self.assertEqual(
            self.client.post(
                reverse("loans:pawn_loan_create"), self._payload(license, series)
            ).status_code,
            302,
        )
        loan = PawnLoan.objects.latest("pk")
        approve_pawn_loan(loan.pk, actor=self.owner)
        disburse_pawn_loan(loan.pk, effective_date=date(2026, 7, 18), actor=self.owner)
        loan.refresh_from_db()
        return loan

    def test_detail_and_list_expose_one_closing_entry_without_recording_anything(self):
        detail = self.client.get(
            reverse(
                "workspace_loans:pawn_loan_detail",
                args=[self.tenant.slug, self.loans[0].pk],
            )
        )
        self.assertContains(detail, "data-close-release-action", count=1)
        page = self.client.get(
            reverse("workspace_loans:pawn_loan_list", args=[self.tenant.slug])
        )
        self.assertContains(page, 'href="' + self.entry() + '"')
        self.assertNotContains(page, "Record paper closures")
        self.assertNotContains(page, "Release multiple loans")
        response = self.client.get(self.entry())
        self.assertEqual(response.context["closing_purpose"], "")
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertFalse(PawnLoanRelease.objects.exists())

    def test_canonical_single_current_preserves_concession_and_retry(self):
        loan = self.loans[0]
        with patch("django.utils.timezone.localdate", return_value=date(2026, 8, 20)):
            review = self.client.get(
                self.entry(), {"purpose": "CURRENT", "loans": [loan.pk]}
            )
            due = review.context["quote"].minimum_settlement
            payload = dict(
                purpose="CURRENT",
                loans=[loan.pk],
                request_key=str(uuid4()),
                settlement_amount=str(due - 1),
                interest_concession="1",
                concession_reason="Agreed discount",
                confirm_collateral_handoff="on",
            )
            self.assertEqual(self.client.post(self.entry(), payload).status_code, 302)
            self.assertEqual(self.client.post(self.entry(), payload).status_code, 302)
        release = loan.releases.get()
        self.assertEqual(release.settlement_amount, due - 1)
        self.assertNotIn("paper_closure", release.loan_event.payload["release"])
        self.assertTrue(
            all(item.returned_at is not None for item in release.items.all())
        )

    def test_canonical_combined_current_review_completion_and_retry(self):
        ids = [loan.pk for loan in self.loans]
        page = self.client.get(self.entry(), {"purpose": "CURRENT", "loans": ids})
        self.assertContains(page, "Total to collect")
        self.assertContains(page, 'action="' + self.entry() + '"')
        header = page.context["confirmation_form"]
        payload = dict(
            purpose="CURRENT",
            loans=ids,
            action="complete",
            request_key=header["request_key"].value(),
            quote_token=header["quote_token"].value(),
            paid_by="One combined payer",
            payment_confirmed="on",
        )
        for loan in self.loans:
            payload.update(
                {
                    f"collector_{loan.pk}-loan_id": loan.pk,
                    f"collector_{loan.pk}-collector_type": "borrower",
                    f"collector_{loan.pk}-handover_confirmed": "on",
                }
            )
        mismatched = dict(payload, loans=[ids[0]])
        self.assertEqual(self.client.post(self.entry(), mismatched).status_code, 400)
        self.assertFalse(PawnLoanRelease.objects.exists())
        self.assertEqual(self.client.post(self.entry(), payload).status_code, 302)
        self.assertEqual(self.client.post(self.entry(), payload).status_code, 302)
        batch = PawnReleaseBatch.objects.get()
        self.assertEqual(
            (batch.mode, batch.paid_by, batch.lines.count()),
            ("COUNTER", "One combined payer", 2),
        )

    def test_weekly_contract_closes_on_actual_date_through_shared_completed_screen(
        self,
    ):
        loan = self.weekly_loan()
        original_policy = {
            field.name: getattr(loan.policy_snapshot, field.name)
            for field in loan.policy_snapshot._meta.concrete_fields
        }
        original_payout = deepcopy(loan.disbursal_snapshot.evidence)
        actual = date(2026, 8, 19)
        ids = [
            self.loans[0].pk,
            loan.pk,
        ]  # monthly and started-week agreements together
        with patch("django.utils.timezone.localdate", return_value=date(2026, 8, 20)):
            contract = resolve_servicing_contract(loan, as_of_date=actual)
            self.assertEqual(contract.partial_month_method, "STARTED_WEEKS")
            self.assertFalse(contract.supports_completed_monthly_servicing)
            for purpose in ("CURRENT", "PAPER"):
                self.assertTrue(
                    servicing_eligibility(
                        loan,
                        operation="FULL_RELEASE",
                        purpose=purpose,
                        effective_date=actual,
                    ).ready
                )
            self.assertIn(
                "PAPER_CONTRACT",
                [
                    row.code
                    for row in servicing_eligibility(
                        loan,
                        operation="REPAYMENT",
                        purpose="PAPER",
                        effective_date=actual,
                    ).blockers
                ],
            )
            with self.assertRaisesMessage(ValueError, "Finalize every completed"):
                preview_pawn_loan_full_release(loan.pk, as_of_date=actual)
            from apps.tenant_apps.loans.services.pawn_interest import (
                finalize_pawn_loan_accrual,
            )

            finalize_pawn_loan_accrual(loan.pk, period_number=1, actor=self.owner)
            initial = self.client.get(self.entry(), {"purpose": "PAPER", "loans": ids})
            self.assertIsNone(initial.context["header"]["closure_date"].value())
            payload = dict(
                purpose="PAPER",
                loans=ids,
                action="review",
                request_key=str(uuid4()),
                closure_date=actual.isoformat(),
                paper_reference="Original book",
            )
            page = self.client.post(self.entry(), payload)
            self.assertEqual(len(page.context["rows"]), 2)
            self.assertFalse(PawnLoanRelease.objects.exists())
            payload.update(
                action="complete",
                confirmed="on",
                quote_token=page.context["header"]["quote_token"].value(),
            )
            amounts = {}
            for row in page.context["rows"]:
                pk = row["loan"].pk
                self.assertNotIn("error", row)
                due = preview_pawn_loan_full_release(
                    pk, as_of_date=actual
                ).minimum_settlement
                self.assertEqual(row["amount"], due)
                amounts[pk] = due
                returned = pk == loan.pk
                payload.update(
                    {
                        f"row_{pk}-include": "on",
                        f"row_{pk}-amount": format(due, ".2f"),
                        f"row_{pk}-basis": (
                            "RETURNED" if returned else "PAPER_SETTLEMENT"
                        ),
                        f"row_{pk}-collector_is_borrower": "yes",
                        f"row_{pk}-paid_by": "Actual payer" if returned else "",
                        f"row_{pk}-collector_name": (
                            row["loan"].borrower.display_name if returned else ""
                        ),
                    }
                )
            response = self.client.post(self.entry(), payload)
            self.assertNotIn("error", response.context)
            self.assertEqual(response.context["completed"].lines.count(), 2)
            self.assertFalse(response.context["closing_selected_loans"].exists())
            retry = self.client.post(self.entry(), payload)
            self.assertEqual(
                retry.context["completed"].pk, response.context["completed"].pk
            )
        self.assertEqual(PawnReleaseBatch.objects.count(), 1)
        for pk, due in amounts.items():
            release = PawnLoanRelease.objects.get(loan_id=pk)
            self.assertEqual(
                (release.effective_date, release.settlement_amount), (actual, due)
            )
            self.assertTrue(
                all(item.returned_at is None for item in release.items.all())
            )
        self.assertEqual(loan.collateral_items.get().custody_state, "WITH_CUSTOMER")
        self.assertEqual(
            self.loans[0].collateral_items.get().custody_state, "PAPER_CLOSED"
        )
        loan.refresh_from_db()
        self.assertEqual(loan.disbursal_snapshot.evidence, original_payout)
        self.assertEqual(
            {
                field.name: getattr(loan.policy_snapshot, field.name)
                for field in loan.policy_snapshot._meta.concrete_fields
            },
            original_policy,
        )

    def test_canonical_rejects_invalid_selection_future_dates_and_missing_confirmation(
        self,
    ):
        for values, status in (
            ({"purpose": "bad"}, 400),
            ({"loans": ["bad"]}, 400),
            ({"loans": [self.loans[0].pk] * 2}, 400),
            ({"loans": [99999999]}, 404),
        ):
            self.assertEqual(self.client.get(self.entry(), values).status_code, status)
        payload = dict(
            purpose="PAPER",
            loans=[self.loans[0].pk],
            action="review",
            request_key=str(uuid4()),
        )
        self.assertContains(
            self.client.post(self.entry(), payload), "This field is required"
        )
        self.assertContains(
            self.client.post(self.entry(), dict(payload, closure_date="2026-07-19")),
            "today or earlier",
        )
        self.assertEqual(self.client.post(self.entry(), {}).status_code, 400)
        self.assertFalse(PawnLoanRelease.objects.exists())

    def test_canonical_permissions_csrf_and_detail_visibility(self):
        self.client.handler.enforce_csrf_checks = True
        self.assertEqual(self.client.post(self.entry(), {}).status_code, 403)
        self.client.handler.enforce_csrf_checks = False
        user = get_user_model().objects.create_user(username="closing-viewer")
        role, _ = Role.objects.get_or_create(name="Viewer")
        Membership.objects.create(company=self.tenant, user=user, role=role)
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.entry()).status_code, 403)
        self.assertEqual(
            self.client.post(
                self.entry(), {"purpose": "CURRENT", "loans": [self.loans[0].pk]}
            ).status_code,
            403,
        )
        response = self.client.get(
            reverse(
                "workspace_loans:pawn_loan_detail",
                args=[self.tenant.slug, self.loans[0].pk],
            )
        )
        self.assertNotContains(response, "data-close-release-action")


from apps.tenant_apps.loans.tests import test_release_concessions as concession_fixtures


class CompletedConcessionTests(concession_fixtures.ReleaseConcessionTests):
    def test_completed_concession_retains_loss_and_unknown_handover(self):
        from apps.tenant_apps.loans.selectors import get_pawn_loan_balance

        facts = dict(
            date=self.today.isoformat(),
            amount=str(self.quote.minimum_settlement - 5),
            number="",
            reference="Closing agreement",
            basis="PAPER_SETTLEMENT",
            recipient="",
            request_key=str(uuid4()),
            interest_concession="5",
            concession_reason="Agreed interest concession",
        )
        review, token = preview_recorded_closure(
            loan_id=self.loan.pk, actor=self.actor, data=facts
        )
        self.assertEqual(review["interest_concession"], "5.00")
        release, created = record_paper_closure(
            loan_id=self.loan.pk,
            actor=self.actor,
            data=facts,
            review_token=token,
            confirmed=True,
        )
        self.assertTrue(created)
        balance = get_pawn_loan_balance(self.loan.pk, as_of_date=self.today)
        self.assertEqual(balance.total_due, 0)
        self.assertEqual(balance.interest_conceded, 5)
        self.assertEqual(
            release.settlement_amount,
            release.principal_amount + release.interest_amount + release.fee_amount,
        )
        self.assertFalse(
            self.loan.collateral_items.exclude(custody_state="PAPER_CLOSED").exists()
        )

    def test_completed_concession_requires_administrator_and_cannot_waive_principal(
        self,
    ):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        from apps.orgs.models import Membership, Role
        from apps.tenancy.testing import workspace_role_permissions

        user = get_user_model().objects.create_user(username="closing-release-only")
        role = Role.objects.create(name="Completed closure without concessions")
        Membership.objects.create(company=self.tenant, user=user, role=role)
        workspace_role_permissions(role, self.tenant).set(
            Permission.objects.filter(
                content_type__app_label="orgs",
                content_type__model="company",
                codename__in=["data_view", "loan_release"],
            )
        )
        facts = dict(
            date=self.today.isoformat(),
            amount=str(self.quote.minimum_settlement - 5),
            number="",
            reference="Closing agreement",
            basis="PAPER_SETTLEMENT",
            recipient="",
            request_key=str(uuid4()),
            interest_concession="5",
            concession_reason="Agreed interest concession",
        )
        with self.assertRaises(PermissionDenied):
            preview_recorded_closure(loan_id=self.loan.pk, actor=user, data=facts)
        facts.update(amount="0", interest_concession=str(self.quote.minimum_settlement))
        with self.assertRaises(ValueError):
            preview_recorded_closure(loan_id=self.loan.pk, actor=self.actor, data=facts)
        self.assertFalse(self.loan.releases.exists())
