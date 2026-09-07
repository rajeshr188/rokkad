import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from apps.tenancy.testing import WorkspaceTestCase

from apps.orgs.models import Company, Membership, Role
from apps.tenant_apps.loans.domain import LoanDocumentKind, TransactionKind
from apps.tenant_apps.loans.models import (
    LoanLicense,
    LoanNumberSequence,
    LoanSeries,
    PawnLoan,
    PawnLoanEvent,
    PawnLoanEconomicPolicy,
    PawnLoanInterestAccrual,
    PawnLoanInterestAccrualLine,
    PawnLoanRelease,
    PawnLoanReleaseItem,
    PawnMetalInterestRatePolicy,
)
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.party.widgets import PartyAutocompleteWidget
from apps.tenant_apps.loans.services import (
    record_loan_event,
    seed_default_loan_products,
)
from apps.tenant_apps.loans.services.pawn_draft_split import (
    preview_pawn_draft_split,
    split_pawn_draft,
)


@override_settings(
    ROOT_URLCONF="django_project.workspace_urls",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class PawnDraftUiTests(WorkspaceTestCase):
    test_schema_name = f"loans_draft_ui_{uuid.uuid4().hex[:8]}"
    test_domain = f"loans-draft-ui-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        User = get_user_model()
        owner, _ = User.objects.get_or_create(
            username="pawn-draft-ui-owner",
            defaults={"email": "pawn-draft-ui-owner@example.com"},
        )
        tenant.name = f"Pawn Draft UI {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner
        tenant.save()
        owner_role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.get_or_create(user=owner, company=tenant, defaults={"role": owner_role})

    def setUp(self):
        super().setUp()
        static_url = patch(
            "django.templatetags.static.StaticNode.handle_simple",
            side_effect=lambda path: f"/static/{path}",
        )
        static_url.start()
        self.addCleanup(static_url.stop)
        self.owner = self.tenant.owner
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.owner)
        self.party = Party.objects.create(display_name="Draft Borrower")
        self.product_version = seed_default_loan_products()[0]
        type(self.product_version).objects.filter(pk=self.product_version.pk).update(status="ACTIVE")

    def test_list_filters_workspace_loans_and_preserves_filters_while_paging(self):
        license, series = self._configured_setup()
        for sequence in range(26):
            PawnLoan.objects.create(
                workspace=self.tenant,
                product_version=self.product_version,
                license=license,
                series=series,
                borrower=self.party,
                loan_number=f"PL-LIST-{sequence:03d}",
                state="DRAFT",
                principal_amount=Decimal("1000.00"),
                monthly_interest_rate=Decimal("2.000000"),
                loan_date=date(2026, 7, 18),
                created_by=self.owner,
            )

        special_party = Party.objects.create(display_name="Special Borrower")
        second_license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="Second License",
            license_number=f"PBL-SECOND-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
            created_by=self.owner,
        )
        second_series = LoanSeries.objects.create(
            license=second_license,
            name="Second",
            code="B",
        )
        special_loan = PawnLoan.objects.create(
            workspace=self.tenant,
            product_version=self.product_version,
            license=second_license,
            series=second_series,
            borrower=special_party,
            loan_number="PL-SPECIAL-001",
            state="ACTIVE",
            principal_amount=Decimal("5000.00"),
            monthly_interest_rate=Decimal("2.000000"),
            loan_date=date(2026, 7, 20),
            created_by=self.owner,
        )

        first_page = self.client.get(
            reverse("loans:pawn_loan_list"),
            {"state": "DRAFT"},
        )
        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.context["page_obj"].paginator.count, 26)
        self.assertEqual(len(first_page.context["loans"]), 25)
        self.assertContains(first_page, "?state=DRAFT&amp;page=2")

        second_page = self.client.get(
            reverse("loans:pawn_loan_list"),
            {"state": "DRAFT", "page": 2},
        )
        self.assertEqual(len(second_page.context["loans"]), 1)

        filtered = self.client.get(
            reverse("loans:pawn_loan_list"),
            {
                "q": "Special Borrower",
                "state": "ACTIVE",
                "license": second_license.pk,
                "series": second_series.pk,
                "loan_date_from": "2026-07-20",
                "loan_date_to": "2026-07-20",
            },
        )
        self.assertEqual(list(filtered.context["loans"]), [special_loan])
        self.assertContains(filtered, "PL-SPECIAL-001")
        self.assertNotContains(filtered, "PL-LIST-000")
        self.assertEqual(
            set(
                filtered.context["loan_filter"]
                .form.fields["license"]
                .queryset.values_list("pk", flat=True)
            ),
            {license.pk, second_license.pk},
        )

    def test_detail_navigates_to_adjacent_loans_in_the_same_series(self):
        license, series = self._configured_setup()
        other_series = LoanSeries.objects.create(license=license, name="Other", code="B")
        common = {
            "workspace": self.tenant,
            "product_version": self.product_version,
            "license": license,
            "borrower": self.party,
            "state": "DRAFT",
            "principal_amount": Decimal("1000.00"),
            "monthly_interest_rate": Decimal("2.000000"),
            "created_by": self.owner,
        }
        previous = PawnLoan.objects.create(
            **common, series=series, loan_number="PL-A-00001", loan_date=date(2026, 7, 17)
        )
        current = PawnLoan.objects.create(
            **common, series=series, loan_number="PL-A-00002", loan_date=date(2026, 7, 18)
        )
        following = PawnLoan.objects.create(
            **common, series=series, loan_number="PL-A-00003", loan_date=date(2026, 7, 18)
        )
        PawnLoan.objects.create(
            **common, series=other_series, loan_number="PL-B-00001", loan_date=date(2026, 7, 18)
        )

        detail = self.client.get(reverse("loans:pawn_loan_detail", args=[current.pk]))

        self.assertEqual(detail.context["previous_loan"], previous)
        self.assertEqual(detail.context["next_loan"], following)
        self.assertContains(detail, reverse("loans:pawn_loan_detail", args=[previous.pk]))
        self.assertContains(detail, reverse("loans:pawn_loan_detail", args=[following.pk]))

    def test_detail_disables_series_navigation_at_the_boundaries(self):
        license, series = self._configured_setup()
        only_loan = PawnLoan.objects.create(
            workspace=self.tenant,
            product_version=self.product_version,
            license=license,
            series=series,
            borrower=self.party,
            loan_number="PL-A-00001",
            state="DRAFT",
            principal_amount=Decimal("1000.00"),
            monthly_interest_rate=Decimal("2.000000"),
            loan_date=date(2026, 7, 18),
            created_by=self.owner,
        )

        detail = self.client.get(reverse("loans:pawn_loan_detail", args=[only_loan.pk]))

        self.assertIsNone(detail.context["previous_loan"])
        self.assertIsNone(detail.context["next_loan"])
        self.assertContains(detail, 'aria-disabled="true"', count=2)

    def test_create_is_blocked_with_clear_setup_action(self):
        response = self.client.get(reverse("loans:pawn_loan_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PawnLoan setup required")
        self.assertContains(response, "Open Economic Setup")
        self.assertContains(response, reverse("loans:pawn_economics_setup"))

    def test_create_uses_active_party_autocomplete_and_supports_preselection(self):
        self._configured_setup()
        self.party.primary_phone = "+919876543210"
        self.party.primary_email = "draft@example.com"
        self.party.relation_label = Party.RelationLabel.SON_OF
        self.party.relation_name = "Mohan Lal"
        self.party.save()
        inactive_party = Party.objects.create(
            display_name="Inactive Borrower",
            status=Party.PartyStatus.INACTIVE,
        )

        response = self.client.get(
            reverse("loans:pawn_loan_create"),
            {"party": self.party.pk},
        )

        self.assertEqual(response.status_code, 200)
        field = response.context["form"].fields["borrower"]
        self.assertIsInstance(field.widget, PartyAutocompleteWidget)
        self.assertEqual(
            response.context["form"].initial["borrower"],
            str(self.party.pk),
        )
        self.assertEqual(list(field.queryset), [self.party])
        self.assertEqual(list(field.widget.get_queryset()), [self.party])
        self.assertNotIn(inactive_party, field.widget.get_queryset())
        self.assertContains(response, "django-select2")
        self.assertContains(
            response,
            "Search by name, party code, phone, relation, or email",
        )
        label = field.widget.label_from_instance(self.party)
        self.assertIn("Draft Borrower", label)
        self.assertIn("Mohan Lal", label)
        self.assertIn("+919876543210", label)
        self.assertIn(self.party.party_code, label)

        form = response.context["form"]
        self.assertNotIn("license", form.fields)
        self.assertIn("series", form.fields)
        self.assertContains(response, "Series (license / register)")
        self.assertContains(
            response,
            "The selected series determines the regulatory license",
        )
        self.assertContains(response, "django-select2")

    def test_staff_can_create_view_and_correct_a_draft_only(self):
        license, series = self._configured_setup()
        response = self.client.post(
            reverse("loans:pawn_loan_create"),
            self._payload(license, series),
        )

        loan = PawnLoan.objects.get()
        self.assertRedirects(
            response,
            reverse("loans:pawn_loan_detail", args=[loan.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(loan.state, "DRAFT")
        self.assertEqual(loan.license_id, series.license_id)
        self.assertEqual(loan.series_id, series.pk)
        self.assertEqual(loan.collateral_items.count(), 1)
        original_item = loan.collateral_items.get()
        original_public_id = original_item.public_id
        original_photo = original_item.photos.get()
        photo_url = reverse(
            "loans:pawn_collateral_photo_document",
            args=[loan.pk, original_item.pk, original_photo.pk],
        )

        detail = self.client.get(reverse("loans:pawn_loan_detail", args=[loan.pk]))
        self.assertContains(detail, loan.loan_number)
        self.assertContains(detail, "Recommended next step")
        self.assertContains(detail, "Approve loan")
        self.assertContains(detail, "Capture collateral photograph")
        self.assertContains(detail, 'capture="environment"')
        self.assertContains(detail, f'{photo_url}?inline=1')
        self.assertContains(detail, "Gold chain photograph captured")
        self.assertNotContains(detail, "Loan ticket PDF")
        ticket = self.client.get(reverse("loans:pawn_loan_ticket_pdf", args=[loan.pk]))
        self.assertEqual(ticket.status_code, 409)

        edit = self.client.get(reverse("loans:pawn_loan_update", args=[loan.pk]))
        self.assertContains(edit, "Official loan number")
        self.assertContains(edit, loan.loan_number)
        self.assertContains(edit, "Use camera/webcam")
        self.assertContains(edit, "loans/collateral_camera.js")
        self.assertContains(edit, 'capture="environment"')
        self.assertContains(edit, "Existing photograph evidence")
        self.assertContains(edit, f'{photo_url}?inline=1')
        self.assertContains(edit, "Existing collateral: Gold chain")
        self.assertContains(edit, "+ Add collateral")
        self.assertContains(edit, "New collateral")
        self.assertContains(edit, "Remove collateral")
        self.assertContains(edit, 'id="empty-collateral-form"')
        self.assertContains(edit, "__prefix__")

        inline_photo = self.client.get(f"{photo_url}?inline=1")
        self.assertEqual(inline_photo.status_code, 200)
        self.assertTrue(inline_photo["Content-Disposition"].startswith("inline"))
        download_photo = self.client.get(photo_url)
        self.assertTrue(download_photo["Content-Disposition"].startswith("attachment"))

        payload = self._payload(license, series)
        payload["collateral-0-allocated_principal"] = "12500.00"
        payload["collateral-0-description"] = "Corrected gold chain"
        payload["collateral-0-collateral_item_id"] = str(loan.collateral_items.get().pk)
        response = self.client.post(reverse("loans:pawn_loan_update", args=[loan.pk]), payload)
        self.assertEqual(
            response.status_code,
            302,
            msg=(
                response.context["form"].errors.as_json()
                if response.context
                else response.content.decode(errors="replace")[:1000]
            ),
        )
        loan.refresh_from_db()
        self.assertEqual(str(loan.principal_amount), "12500.00")
        self.assertEqual(loan.collateral_items.get().description, "Corrected gold chain")
        self.assertEqual(loan.collateral_items.get().public_id, original_public_id)
        self.assertEqual(loan.collateral_items.get().photos.count(), 2)
        self.assertEqual(loan.change_log.count(), 2)

    def test_staff_can_add_another_collateral_item_to_a_draft(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()
        existing = loan.collateral_items.get()
        payload = self._payload(license, series)
        payload.update(
            {
                "collateral-TOTAL_FORMS": "2",
                "collateral-0-collateral_item_id": str(existing.pk),
                "collateral-0-allocated_principal": "10000.00",
                "collateral-1-description": "Silver anklet",
                "collateral-1-metal": "SILVER",
                "collateral-1-gross_weight": "25.0000",
                "collateral-1-net_weight": "24.0000",
                "collateral-1-purity_percentage": "80.0000",
                "collateral-1-latest_appraised_value": "15000.00",
                "collateral-1-allocated_principal": "5000.00",
                "collateral-1-photograph": SimpleUploadedFile(
                    "silver-anklet.jpg",
                    b"\xff\xd8\xff\xe0additional-evidence",
                    content_type="image/jpeg",
                ),
            }
        )

        response = self.client.post(
            reverse("loans:pawn_loan_update", args=[loan.pk]), payload
        )

        self.assertRedirects(
            response,
            reverse("loans:pawn_loan_detail", args=[loan.pk]),
            fetch_redirect_response=False,
        )
        loan.refresh_from_db()
        self.assertEqual(loan.collateral_items.count(), 2)
        added = loan.collateral_items.get(description="Silver anklet")
        self.assertEqual(added.photos.count(), 1)
        self.assertEqual(loan.principal_amount, Decimal("15000.00"))

        removed_item_id = added.pk
        removed_photo = added.photos.get()
        removal_payload = self._payload(license, series)
        removal_payload["collateral-0-collateral_item_id"] = str(existing.pk)
        removal = self.client.post(
            reverse("loans:pawn_loan_update", args=[loan.pk]), removal_payload
        )

        self.assertRedirects(
            removal,
            reverse("loans:pawn_loan_detail", args=[loan.pk]),
            fetch_redirect_response=False,
        )
        self.assertFalse(PawnLoan.objects.get(pk=loan.pk).collateral_items.filter(pk=removed_item_id).exists())
        self.assertFalse(type(removed_photo).objects.filter(pk=removed_photo.pk).exists())

    def test_draft_split_moves_selected_identity_and_keeps_source_number(self):
        license, series = self._configured_setup()
        payload = self._payload(license, series)
        payload.update({
            "collateral-TOTAL_FORMS": "2",
            "collateral-0-allocated_principal": "10000.00",
            "collateral-1-description": "Gold ring",
            "collateral-1-metal": "GOLD",
            "collateral-1-gross_weight": "5.0000",
            "collateral-1-net_weight": "4.5000",
            "collateral-1-purity_percentage": "91.6000",
            "collateral-1-latest_appraised_value": "25000.00",
            "collateral-1-allocated_principal": "5000.00",
            "collateral-1-photograph": SimpleUploadedFile("ring.jpg", b"\xff\xd8\xff\xe0ring", content_type="image/jpeg"),
        })
        self.client.post(reverse("loans:pawn_loan_create"), payload)
        source = PawnLoan.objects.get()
        source_number = source.loan_number
        selected = source.collateral_items.get(description="Gold ring")
        selected_public_id = selected.public_id
        selected_photo_id = selected.photos.get().pk
        preview = preview_pawn_draft_split(
            source.pk, collateral_item_ids=(selected.pk,), series=series,
            product_version=self.product_version, loan_date=source.loan_date,
            tenure_months=source.tenure_months,
        )

        new_loan = split_pawn_draft(
            source.pk, collateral_item_ids=(selected.pk,), series=series,
            product_version=self.product_version, loan_date=source.loan_date,
            tenure_months=source.tenure_months,
            expected_fingerprint=preview.fingerprint, actor=self.owner,
        )

        source.refresh_from_db()
        selected.refresh_from_db()
        self.assertEqual(source.loan_number, source_number)
        self.assertEqual(source.collateral_items.count(), 1)
        self.assertEqual(new_loan.collateral_items.count(), 1)
        self.assertEqual(selected.loan_id, new_loan.pk)
        self.assertEqual(selected.public_id, selected_public_id)
        self.assertTrue(selected.photos.filter(pk=selected_photo_id).exists())
        self.assertEqual(new_loan.loan_events.count(), 0)

    def test_invalid_create_rerenders_without_consuming_number(self):
        license, series = self._configured_setup()
        payload = self._payload(license, series)
        payload["collateral-0-net_weight"] = "12.0000"
        response = self.client.post(reverse("loans:pawn_loan_create"), payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The draft was not saved.")
        self.assertEqual(PawnLoan.objects.count(), 0)
        sequence = LoanNumberSequence.objects.get(
            series=series, document_kind=LoanDocumentKind.PAWN_LOAN.value
        )
        self.assertEqual(sequence.next_number, 1)

    def test_save_is_the_default_submit_action(self):
        license, series = self._configured_setup()

        response = self.client.get(reverse("loans:pawn_loan_create"))

        content = response.content.decode()
        self.assertLess(
            content.index('name="action" value="save"'),
            content.index('name="action" value="preview"'),
        )

    def test_economic_preview_does_not_create_or_consume_a_draft(self):
        license, series = self._configured_setup()
        payload = self._payload(license, series)
        payload["action"] = "preview"

        initial = self.client.get(reverse("loans:pawn_loan_create"))
        self.assertContains(initial, "Next expected PawnLoan number")
        self.assertContains(initial, "PL-A-00001")

        response = self.client.post(reverse("loans:pawn_loan_create"), payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Economic preview")
        self.assertContains(response, "10000.00")
        self.assertContains(response, "9800.00")
        self.assertContains(response, "PL-A-00001")
        self.assertFalse(PawnLoan.objects.exists())
        sequence = LoanNumberSequence.objects.get(
            series=series, document_kind=LoanDocumentKind.PAWN_LOAN.value
        )
        self.assertEqual(sequence.next_number, 1)

    def test_mixed_metal_preview_shows_item_rates_limits_and_net_cash(self):
        license, series = self._configured_setup()
        payload = self._mixed_metal_payload(license, series)
        payload["action"] = "preview"

        response = self.client.post(reverse("loans:pawn_loan_create"), payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gold")
        self.assertContains(response, "Silver")
        self.assertContains(response, "2.000000%")
        self.assertContains(response, "4.000000%")
        self.assertContains(response, "Maximum at LTV")
        self.assertContains(response, "260.00")
        self.assertContains(response, "8740.00")
        self.assertFalse(PawnLoan.objects.exists())

    def test_ltv_failure_is_attached_to_offending_item_principal(self):
        license, series = self._configured_setup()
        payload = self._payload(license, series)
        payload["collateral-0-allocated_principal"] = "41000.00"

        response = self.client.post(reverse("loans:pawn_loan_create"), payload)

        self.assertEqual(response.status_code, 200)
        item_errors = response.context["formset"].forms[0].errors
        self.assertIn("allocated_principal", item_errors)
        self.assertIn("exceeds its maximum 40000.00", item_errors["allocated_principal"][0])
        self.assertFalse(response.context["form"].non_field_errors())
        self.assertFalse(PawnLoan.objects.exists())
        sequence = LoanNumberSequence.objects.get(
            series=series, document_kind=LoanDocumentKind.PAWN_LOAN.value
        )
        self.assertEqual(sequence.next_number, 1)

    def test_authorized_primary_navigation_exposes_pawnloans_and_setup(self):
        response = self.client.get(reverse("loans:license_list"))
        self.assertContains(
            response,
            reverse(
                "workspace_slug_loan_list",
                kwargs={"workspace_slug": self.tenant.slug},
            ),
        )
        self.assertContains(response, self.workspace_reverse("loans:license_list"))

    def test_internal_reports_render_all_operational_sections(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))

        response = self.client.get(reverse("loans:pawn_loan_reports"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Operational reports")
        self.assertContains(response, "Actionable integrity findings")
        self.assertContains(response, "Active, due &amp; overdue")
        self.assertContains(response, "Communication")
        self.assertContains(response, "Finalized accruals")
        self.assertContains(response, "Repayments")
        self.assertContains(response, "Releases")
        self.assertContains(response, "Release and renew")
        self.assertContains(response, "Collateral custody")
        self.assertContains(response, "Every format below is rendered from the same")
        for section in (
            "active", "daily", "interest_due", "overdue",
            "releases_renewals", "storage", "license_expiry",
        ):
            for export_format in ("csv", "xlsx", "pdf"):
                self.assertContains(
                    response,
                    reverse(
                        "loans:pawn_loan_report_export",
                        args=[section, export_format],
                    ),
                )
        self.assertContains(response, reverse("loans:license_register_pdf"))

    def test_current_overdue_report_links_directly_to_overdue_notice(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()
        PawnLoan.objects.filter(pk=loan.pk).update(
            state="ACTIVE",
            loan_date=date(2026, 1, 1),
            tenure_months=1,
        )
        PawnLoanEvent.objects.create(
            loan=loan,
            event_kind="DISBURSAL",
            effective_date=date(2026, 1, 1),
            payload={
                "values": {"principal": "10000.00", "interest": "0", "fees": "0"}
            },
            payload_fingerprint="9" * 64,
            idempotency_key="overdue-report-disbursal",
            created_by=self.owner,
        )

        response = self.client.get(reverse("loans:pawn_loan_reports"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Prepare overdue notice")
        self.assertContains(response, "?kind=OVERDUE_NOTICE")

    def test_party_statement_transaction_history_honors_as_of_date(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()
        PawnLoan.objects.filter(pk=loan.pk).update(state="ACTIVE")
        future = PawnLoanEvent.objects.create(
            loan=loan,
            event_kind="REPAYMENT",
            effective_date=date(2026, 8, 5),
            payload={
                "values": {"principal": "777.00", "interest": "0", "fees": "0"},
                "repayment": {"amount_received": "777.00"},
            },
            payload_fingerprint="future-party-statement",
            idempotency_key="future-party-statement",
            created_by=self.owner,
        )
        url = reverse("loans:pawn_party_statement", args=[loan.borrower_id])

        earlier = self.client.get(url, {"as_of": "2026-08-04"})
        included = self.client.get(url, {"as_of": "2026-08-05"})

        self.assertNotContains(earlier, f"Event #{future.pk}")
        self.assertContains(included, f"Event #{future.pk}")
        self.assertContains(included, "CURRENT")

    def test_essential_pdf_routes_use_workspace_scoped_immutable_sources(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()
        self.client.post(reverse("loans:pawn_loan_approve", args=[loan.pk]))
        repayment = PawnLoanEvent.objects.create(
            loan=loan,
            event_kind="REPAYMENT",
            effective_date=date(2026, 8, 3),
            payload={
                "values": {
                    "principal": "450",
                    "interest": "50",
                    "overdue_interest": "20",
                    "current_interest": "30",
                    "fees": "0",
                },
                "repayment": {"amount_received": "500"},
            },
            payload_fingerprint="receipt-fixture",
            idempotency_key="receipt-fixture",
            created_by=self.owner,
        )
        release_event = PawnLoanEvent.objects.create(
            loan=loan,
            event_kind="RELEASE_RECEIPT",
            effective_date=date(2026, 8, 3),
            payload={"values": {"principal": "10000", "interest": "0", "fees": "0"}},
            payload_fingerprint="release-fixture",
            idempotency_key="release-fixture",
            created_by=self.owner,
        )
        release = PawnLoanRelease.objects.create(
            workspace=self.tenant,
            loan=loan,
            release_number="RL-A-00001",
            request_key="release-document-fixture",
            effective_date=date(2026, 8, 3),
            is_full_release=True,
            settlement_amount=Decimal("10000"),
            principal_amount=Decimal("10000"),
            interest_amount=Decimal("0"),
            fee_amount=Decimal("0"),
            loan_event=release_event,
            created_by=self.owner,
        )
        PawnLoanReleaseItem.objects.create(
            release=release,
            collateral_item=loan.collateral_items.get(),
            valuation_snapshot={"valuation_amount": "50000"},
        )

        routes = (
            reverse("loans:pawn_loan_ticket_pdf", args=[loan.pk]),
            reverse("loans:pawn_repayment_receipt_pdf", args=[loan.pk, repayment.pk]),
            reverse("loans:pawn_release_memo_pdf", args=[release.pk]),
        )
        for url in routes:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "application/pdf")
            self.assertTrue(response.content.startswith(b"%PDF"))
            self.assertTrue(response["X-Rokkad-Verification-ID"].startswith("ROKKAD|"))

    def test_workspace_member_can_use_internal_draft_ui_but_not_setup(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()
        User = get_user_model()
        member = User.objects.create_user(
            username=f"pawn-staff-{uuid.uuid4().hex[:8]}",
            email=f"pawn-staff-{uuid.uuid4().hex[:8]}@example.com",
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=member_role)
        self.client.force_login(member)

        response = self.client.get(reverse("loans:pawn_loan_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("loans:pawn_loan_list"))
        self.assertNotContains(response, reverse("loans:license_list"))
        self.assertEqual(self.client.get(reverse("loans:license_list")).status_code, 403)

    def test_unknown_and_cross_workspace_loan_sources_are_not_exposed(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()
        item = loan.collateral_items.get()
        event = PawnLoanEvent.objects.create(
            loan=loan,
            event_kind="REPAYMENT",
            effective_date=date(2026, 8, 2),
            payload={
                "values": {"principal": "1.00", "interest": "0", "fees": "0"},
                "repayment": {"amount_received": "1.00"},
            },
            payload_fingerprint="p12-cross-workspace-event",
            idempotency_key="p12-cross-workspace-event",
            created_by=self.owner,
        )
        other_workspace = Company(
            name=f"P12 Foreign {uuid.uuid4().hex[:8]}",
            schema_name=f"p12_foreign_{uuid.uuid4().hex[:8]}",
            owner=self.owner,
            creator=self.owner,
        )
        other_workspace.save()
        PawnLoan.objects.filter(pk=loan.pk).update(workspace=other_workspace)
        LoanLicense.objects.filter(pk=license.pk).update(workspace=other_workspace)

        scoped_routes = (
            reverse("loans:pawn_loan_detail", args=[loan.pk]),
            reverse("loans:pawn_loan_update", args=[loan.pk]),
            reverse("loans:pawn_loan_ticket_pdf", args=[loan.pk]),
            reverse("loans:pawn_repayment_receipt_pdf", args=[loan.pk, event.pk]),
            reverse("loans:pawn_collateral_photo_document", args=[loan.pk, item.pk, item.photos.get().pk]),
            reverse("loans:pawn_collateral_label_pdf", args=[loan.pk, item.pk]),
            reverse("loans:pawn_collateral_scan", args=[item.public_id]),
            reverse("loans:pawn_party_statement", args=[loan.borrower_id]),
            reverse("loans:license_detail", args=[license.pk]),
        )
        for url in scoped_routes:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

        unknown_routes = (
            reverse("loans:pawn_loan_detail", args=[999999]),
            reverse("loans:pawn_loan_ticket_pdf", args=[999999]),
            reverse("loans:pawn_party_statement", args=[999999]),
            reverse("loans:license_detail", args=[999999]),
        )
        for url in unknown_routes:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_staff_can_approve_reopen_reapprove_and_cancel_through_ui(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()

        response = self.client.post(reverse("loans:pawn_loan_approve", args=[loan.pk]))
        self.assertEqual(response.status_code, 302)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "APPROVED")
        self.assertEqual(loan.approval_snapshots.count(), 1)

        response = self.client.post(
            reverse("loans:pawn_loan_reopen", args=[loan.pk]),
            {"reason": "Correct collateral valuation"},
        )
        self.assertEqual(response.status_code, 302)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "DRAFT")
        self.client.post(reverse("loans:pawn_loan_approve", args=[loan.pk]))
        self.assertEqual(loan.approval_snapshots.count(), 2)

        response = self.client.post(
            reverse("loans:pawn_loan_cancel", args=[loan.pk]),
            {"reason": "Borrower withdrew"},
        )
        self.assertEqual(response.status_code, 302)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "CANCELLED")

    def test_reason_form_does_not_transition_when_reason_is_missing(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()

        response = self.client.post(reverse("loans:pawn_loan_cancel", args=[loan.pk]), {"reason": ""})
        self.assertEqual(response.status_code, 200)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "DRAFT")

    def test_approved_detail_guides_staff_to_disbursal_and_dispatches_command(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()
        self.client.post(reverse("loans:pawn_loan_approve", args=[loan.pk]))

        detail = self.client.get(reverse("loans:pawn_loan_detail", args=[loan.pk]))
        self.assertContains(detail, "Disburse loan")
        self.assertContains(detail, reverse("loans:pawn_loan_disburse", args=[loan.pk]))

        with patch("apps.tenant_apps.loans.web.pawn_financial_actions.disburse_pawn_loan") as command:
            response = self.client.post(
                reverse("loans:pawn_loan_disburse", args=[loan.pk]),
                {"effective_date": "2026-08-03"},
            )

        self.assertRedirects(
            response,
            reverse("loans:pawn_loan_detail", args=[loan.pk]),
            fetch_redirect_response=False,
        )
        command.assert_called_once_with(
            loan.pk,
            effective_date=date(2026, 8, 3),
            actor=self.owner,
        )

    def test_active_detail_exposes_complete_staff_lifecycle_and_repayment_command(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()
        PawnLoan.objects.filter(pk=loan.pk).update(state="ACTIVE")
        balance = SimpleNamespace(
            principal_outstanding=Decimal("10000.00"),
            interest_outstanding=Decimal("200.00"),
            fees_outstanding=Decimal("0.00"),
            total_due=Decimal("10200.00"),
        )
        with (
            patch("apps.tenant_apps.loans.views.get_pawn_loan_balance", return_value=balance),
            patch("apps.tenant_apps.loans.web.pawn_financial_actions.preview_pawn_loan_accruals", return_value=()),
        ):
            detail = self.client.get(reverse("loans:pawn_loan_detail", args=[loan.pk]))

        self.assertContains(detail, "Record repayment")
        self.assertContains(detail, "Accrue interest")
        self.assertNotContains(detail, "Partial release")
        self.assertContains(detail, "Release and renew")
        self.assertContains(detail, "Full release")
        self.assertContains(
            detail,
            reverse("loans:pawn_loan_notice_create", args=[loan.pk]),
        )
        self.assertContains(
            detail,
            reverse("loans:pawn_party_statement", args=[loan.borrower_id]),
        )

        collateral = loan.collateral_items.get()
        accrual_line = SimpleNamespace(
            collateral_item_id=collateral.pk,
            principal_base=Decimal("10000.00"),
            monthly_interest_rate=Decimal("2.000000"),
            calculated_interest=Decimal("200.00"),
            advance_interest_applied=Decimal("0.00"),
            recognized_interest=Decimal("200.00"),
        )
        accrual_preview = SimpleNamespace(
            period_number=1,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
            calculated_interest=Decimal("200.00"),
            advance_interest_applied=Decimal("0.00"),
            recognized_interest=Decimal("200.00"),
            lines=(accrual_line,),
        )
        with patch(
            "apps.tenant_apps.loans.web.pawn_financial_actions.preview_pawn_loan_accruals",
            return_value=(accrual_preview,),
        ):
            accrual_page = self.client.get(
                reverse("loans:pawn_loan_accrue", args=[loan.pk])
            )
        self.assertContains(accrual_page, collateral.description)
        self.assertContains(accrual_page, "Principal base")
        self.assertContains(accrual_page, "Advance applied")
        self.assertContains(accrual_page, "2.000000%")

        finalized = PawnLoanInterestAccrual.objects.create(
            loan=loan,
            period_number=1,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
            period_fraction=Decimal("1.0000"),
            calculation_base=Decimal("10000.00"),
            unrounded_interest=Decimal("200.00"),
            recognized_interest=Decimal("200.00"),
            finalized_by=self.owner,
        )
        PawnLoanInterestAccrualLine.objects.create(
            accrual=finalized,
            collateral_item=collateral,
            principal_base=Decimal("10000.00"),
            monthly_interest_rate=Decimal("2.000000"),
            period_fraction=Decimal("1.0000"),
            unrounded_interest=Decimal("200.00"),
            calculated_interest=Decimal("200.00"),
            advance_interest_applied=Decimal("0.00"),
            recognized_interest=Decimal("200.00"),
        )
        with (
            patch("apps.tenant_apps.loans.views.get_pawn_loan_balance", return_value=balance),
            patch("apps.tenant_apps.loans.web.pawn_financial_actions.preview_pawn_loan_accruals", return_value=()),
        ):
            finalized_detail = self.client.get(
                reverse("loans:pawn_loan_detail", args=[loan.pk])
            )
        self.assertContains(finalized_detail, "Finalized interest accruals")
        self.assertContains(finalized_detail, "Immutable collateral-tranche calculation")

        allocation = SimpleNamespace(
            amount_received=Decimal("500.00"),
            fees=Decimal("0.00"),
            overdue_interest=Decimal("100.00"),
            current_interest=Decimal("50.00"),
            principal=Decimal("350.00"),
        )
        item_allocation = SimpleNamespace(
            collateral_item_id=collateral.pk,
            monthly_interest_rate=Decimal("2.000000"),
            balance_before=Decimal("10000.00"),
            principal_applied=Decimal("350.00"),
            balance_after=Decimal("9650.00"),
        )
        preview = SimpleNamespace(
            allocation=allocation,
            item_allocations=(item_allocation,),
        )
        with (
            patch(
                "apps.tenant_apps.loans.web.pawn_financial_actions.preview_pawn_loan_repayment",
                return_value=preview,
            ) as preview_command,
            patch("apps.tenant_apps.loans.web.pawn_financial_actions.record_pawn_loan_repayment") as record_command,
        ):
            response = self.client.post(
                reverse("loans:pawn_loan_repay", args=[loan.pk]),
                {
                    "amount": "500.00",
                    "request_key": "ui-repayment-1",
                    "action": "preview",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no money recorded yet")
        self.assertContains(response, "Overdue interest")
        self.assertContains(response, "highest monthly rate first")
        preview_command.assert_called_once_with(loan.pk, amount=Decimal("500.00"))
        record_command.assert_not_called()

        result = SimpleNamespace(
            allocation=allocation,
            outbox=SimpleNamespace(get_status_display=lambda: "Pending"),
        )
        with patch(
            "apps.tenant_apps.loans.web.pawn_financial_actions.record_pawn_loan_repayment",
            return_value=result,
        ) as command:
            response = self.client.post(
                reverse("loans:pawn_loan_repay", args=[loan.pk]),
                {"amount": "500.00", "request_key": "ui-repayment-1"},
            )

        self.assertEqual(response.status_code, 302)
        command.assert_called_once_with(
            loan.pk,
            amount=Decimal("500.00"),
            request_key="ui-repayment-1",
            actor=self.owner,
        )

    def test_correction_ui_exposes_only_newest_event_and_requires_confirmation(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()
        PawnLoan.objects.filter(pk=loan.pk).update(state="ACTIVE")
        loan.refresh_from_db()
        disbursal, _ = record_loan_event(
            loan.pk,
            event_kind=TransactionKind.DISBURSAL,
            effective_date=date(2026, 8, 1),
            payload={"values": {"principal": "10000.00"}},
            actor=self.owner,
        )
        repayment, _ = record_loan_event(
            loan.pk,
            event_kind=TransactionKind.REPAYMENT,
            effective_date=date(2026, 8, 2),
            payload={
                "values": {
                    "principal": "1000.00",
                    "interest": "0.00",
                    "fees": "0.00",
                }
            },
            actor=self.owner,
        )
        balance = SimpleNamespace(
            principal_outstanding=Decimal("9000.00"),
            interest_outstanding=Decimal("0.00"),
            fees_outstanding=Decimal("0.00"),
            total_due=Decimal("9000.00"),
        )
        with (
            patch("apps.tenant_apps.loans.views.get_pawn_loan_balance", return_value=balance),
            patch("apps.tenant_apps.loans.web.pawn_financial_actions.preview_pawn_loan_accruals", return_value=()),
        ):
            detail = self.client.get(reverse("loans:pawn_loan_detail", args=[loan.pk]))
            action = self.client.get(
                reverse(
                    "loans:pawn_loan_reverse_event", args=[loan.pk, repayment.pk]
                )
            )

        self.assertContains(detail, "Business events")
        self.assertContains(detail, "Correct newest event", count=1)
        self.assertContains(detail, f"Reverse later event #{repayment.pk} first.")
        self.assertNotContains(
            detail,
            reverse("loans:pawn_loan_reverse_event", args=[loan.pk, disbursal.pk]),
        )
        self.assertContains(action, "Correction preflight")
        self.assertContains(action, "This event is currently the next safe correction target")

        missing_confirmation = self.client.post(
            reverse("loans:pawn_loan_reverse_event", args=[loan.pk, repayment.pk]),
            {"reason": "Duplicate receipt"},
        )
        self.assertContains(missing_confirmation, "This field is required")
        with patch(
            "apps.tenant_apps.loans.views.get_pawn_loan_balance",
            return_value=SimpleNamespace(total_due=Decimal("10000.00")),
        ):
            recorded = self.client.post(
                reverse(
                    "loans:pawn_loan_reverse_event", args=[loan.pk, repayment.pk]
                ),
                {"reason": "Duplicate receipt", "confirm_reversal": "on"},
            )
        self.assertRedirects(
            recorded,
            reverse("loans:pawn_loan_detail", args=[loan.pk]),
            fetch_redirect_response=False,
        )
        reversal = repayment.reversed_by_event
        self.assertEqual(reversal.payload["reversal"]["reason"], "Duplicate receipt")
        self.assertEqual(reversal.reversal_of_id, repayment.pk)

    def test_active_loan_notice_form_dispatches_service_owned_command(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()
        PawnLoan.objects.filter(pk=loan.pk).update(state="ACTIVE")
        notice = SimpleNamespace(
            get_notice_kind_display=lambda: "Repayment Reminder",
        )

        form_page = self.client.get(
            reverse("loans:pawn_loan_notice_create", args=[loan.pk]),
            {"kind": "OVERDUE_NOTICE"},
        )
        self.assertEqual(form_page.status_code, 200)
        self.assertContains(form_page, "immutable notice source")
        self.assertEqual(
            form_page.context["form"].initial["notice_kind"], "OVERDUE_NOTICE"
        )

        unconfirmed_payload = {
            "notice_kind": "REPAYMENT_REMINDER",
            "channel": "EMAIL",
            "scheduled_for": "",
            "request_key": "ui-notice-1",
        }
        with patch("apps.tenant_apps.loans.web.pawn_notice_actions.create_pawn_loan_notice") as command:
            rejected = self.client.post(
                reverse("loans:pawn_loan_notice_create", args=[loan.pk]),
                unconfirmed_payload,
            )
        self.assertEqual(rejected.status_code, 200)
        self.assertContains(rejected, "This field is required")
        command.assert_not_called()

        with patch(
            "apps.tenant_apps.loans.web.pawn_notice_actions.create_pawn_loan_notice",
            return_value=notice,
        ) as command:
            response = self.client.post(
                reverse("loans:pawn_loan_notice_create", args=[loan.pk]),
                {**unconfirmed_payload, "confirm_notice_snapshot": "on"},
            )

        self.assertRedirects(
            response,
            reverse("loans:pawn_loan_detail", args=[loan.pk]),
            fetch_redirect_response=False,
        )
        command.assert_called_once_with(
            loan.pk,
            notice_kind="REPAYMENT_REMINDER",
            channel="EMAIL",
            scheduled_for=None,
            request_key="ui-notice-1",
            actor=self.owner,
        )

    def test_partial_release_route_is_gone_without_dispatch(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()
        PawnLoan.objects.filter(pk=loan.pk).update(state="ACTIVE")
        response = self.client.post(
            reverse("loans:pawn_loan_release_partial", args=[loan.pk]),
        )

        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "release and renew", status_code=410)

    def test_full_release_shows_exact_catch_up_quote_and_requires_handoff_confirmation(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()
        PawnLoan.objects.filter(pk=loan.pk).update(state="ACTIVE")
        collateral = loan.collateral_items.get()
        quote = SimpleNamespace(
            minimum_settlement=Decimal("10550.00"),
            fees_and_interest_settlement=Decimal("550.00"),
            release_day_catch_up_interest=Decimal("50.00"),
            principal_reduction_required=Decimal("10000.00"),
            item_valuations=(
                SimpleNamespace(
                    selected_for_release=True,
                    description=collateral.description,
                    metal="GOLD",
                    net_weight=Decimal("10.0000"),
                    valuation_amount=Decimal("50000.00"),
                ),
            ),
            blockers=(),
        )
        url = reverse("loans:pawn_loan_release_full", args=[loan.pk])
        with patch(
            "apps.tenant_apps.loans.web.pawn_release_actions.preview_pawn_loan_full_release",
            return_value=quote,
        ):
            page = self.client.get(url)

        self.assertContains(page, "Exact settlement")
        self.assertContains(page, "Release-day interest")
        self.assertContains(page, "10550.00")
        self.assertContains(page, collateral.description)
        self.assertContains(page, "physically returned to the customer")

        payload = {
            "settlement_amount": "10550.00",
            "request_key": "full-release-ui-1",
        }
        with (
            patch(
                "apps.tenant_apps.loans.web.pawn_release_actions.preview_pawn_loan_full_release",
                return_value=quote,
            ),
            patch("apps.tenant_apps.loans.web.pawn_release_actions.release_pawn_loan_in_full") as command,
        ):
            rejected = self.client.post(url, payload)
        self.assertEqual(rejected.status_code, 200)
        self.assertContains(rejected, "This field is required")
        command.assert_not_called()

        result = SimpleNamespace(
            release=SimpleNamespace(
                release_number="RL-A-00001",
                settlement_amount=Decimal("10550.00"),
                items=SimpleNamespace(count=lambda: 1),
            ),
            outbox=SimpleNamespace(get_status_display=lambda: "Pending"),
        )
        payload["confirm_collateral_handoff"] = "on"
        with (
            patch(
                "apps.tenant_apps.loans.web.pawn_release_actions.preview_pawn_loan_full_release",
                return_value=quote,
            ),
            patch(
                "apps.tenant_apps.loans.web.pawn_release_actions.release_pawn_loan_in_full",
                return_value=result,
            ) as command,
        ):
            accepted = self.client.post(url, payload)
        self.assertRedirects(
            accepted,
            reverse("loans:pawn_loan_detail", args=[loan.pk]),
            fetch_redirect_response=False,
        )
        command.assert_called_once_with(
            loan.pk,
            settlement_amount=Decimal("10550.00"),
            request_key="full-release-ui-1",
            actor=self.owner,
        )

    def test_release_and_renew_form_submits_explicit_retained_plan(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()
        PawnLoan.objects.filter(pk=loan.pk).update(state="ACTIVE")
        collateral = loan.collateral_items.get()
        result = SimpleNamespace(
            successor_loan=SimpleNamespace(pk=99, loan_number="PL-A-00099"),
            renewal=SimpleNamespace(
                renewal_number="REN-PL-A-00001",
                valuation_snapshot={
                    "returned_source_item_ids": [],
                    "retained_source_item_ids": [collateral.pk],
                    "additional_successor_item_ids": [],
                },
            ),
            settlement_outbox=SimpleNamespace(get_status_display=lambda: "Pending"),
            opening_outbox=SimpleNamespace(get_status_display=lambda: "Completed"),
        )
        quote = SimpleNamespace(
            source_principal=Decimal("10000.00"),
            release_day_interest=Decimal("100.00"),
            interest_settled=Decimal("100.00"),
            fees_settled=Decimal("0.00"),
            base_cash_received=Decimal("100.00"),
            balance=SimpleNamespace(interest_outstanding=Decimal("0.00")),
        )
        exact_plan = SimpleNamespace(
            fingerprint="renewal-preview-fingerprint",
            source=quote,
            successor_principal=Decimal("9000.00"),
            successor_monthly_interest=Decimal("180.00"),
            successor_advance_interest=Decimal("180.00"),
            successor_deducted_fees=Decimal("50.00"),
            principal_paid=Decimal("1000.00"),
            total_cash_received=Decimal("1330.00"),
            top_up_amount=Decimal("0.00"),
            net_cash_amount=Decimal("1330.00"),
            net_cash_direction="COLLECT_FROM_CUSTOMER",
            retained_item_ids=frozenset((collateral.pk,)),
            returned_item_ids=(),
            successor_collateral_count=1,
        )
        payload = {
            "mode": "PAY_AND_RENEW",
            "principal_paid": "1000.00",
            "top_up_amount": "0.00",
            "successor_license": license.pk,
            "successor_series": series.pk,
            "tenure_months": "3",
            "request_key": "release-renew-ui-1",
            "retained-TOTAL_FORMS": "1",
            "retained-INITIAL_FORMS": "1",
            "retained-MIN_NUM_FORMS": "0",
            "retained-MAX_NUM_FORMS": "1000",
            "retained-0-collateral_item_id": collateral.pk,
            "retained-0-retain": "on",
            "retained-0-allocated_principal": "9000.00",
            "additional-TOTAL_FORMS": "1",
            "additional-INITIAL_FORMS": "0",
            "additional-MIN_NUM_FORMS": "0",
            "additional-MAX_NUM_FORMS": "1000",
        }
        with (
            patch(
                "apps.tenant_apps.loans.web.pawn_renewal_actions.preview_pawn_loan_renewal_source",
                return_value=quote,
            ),
            patch("apps.tenant_apps.loans.web.pawn_renewal_actions.renew_pawn_loan") as command,
        ):
            rejected = self.client.post(
                reverse("loans:pawn_loan_renew", args=[loan.pk]),
                payload,
            )
        self.assertEqual(rejected.status_code, 200)
        self.assertContains(rejected, "This field is required")
        command.assert_not_called()

        payload["confirm_renewal_plan"] = "on"
        payload["preview_fingerprint"] = exact_plan.fingerprint
        with (
            patch(
                "apps.tenant_apps.loans.web.pawn_renewal_actions.preview_pawn_loan_renewal_source",
                return_value=quote,
            ),
            patch(
                "apps.tenant_apps.loans.web.pawn_renewal_actions.preview_pawn_loan_renewal_plan",
                return_value=exact_plan,
            ),
            patch(
                "apps.tenant_apps.loans.web.pawn_renewal_actions.renew_pawn_loan",
                return_value=result,
            ) as command,
        ):
            response = self.client.post(
                reverse("loans:pawn_loan_renew", args=[loan.pk]),
                payload,
            )

        self.assertEqual(response.status_code, 302)
        call = command.call_args.kwargs
        self.assertEqual(call["retained_collateral"][0].collateral_item_id, collateral.pk)
        self.assertEqual(
            call["retained_collateral"][0].allocated_principal,
            Decimal("9000.00"),
        )
        self.assertEqual(call["additional_collateral"], ())
        self.assertEqual(
            call["expected_preview_fingerprint"],
            exact_plan.fingerprint,
        )

        preview_payload = dict(payload)
        preview_payload.pop("confirm_renewal_plan")
        preview_payload.pop("preview_fingerprint")
        preview_payload["action"] = "preview"
        with (
            patch(
                "apps.tenant_apps.loans.web.pawn_renewal_actions.preview_pawn_loan_renewal_source",
                return_value=quote,
            ),
            patch(
                "apps.tenant_apps.loans.web.pawn_renewal_actions.preview_pawn_loan_renewal_plan",
                return_value=exact_plan,
            ),
            patch("apps.tenant_apps.loans.web.pawn_renewal_actions.renew_pawn_loan") as command,
        ):
            preview_response = self.client.post(
                reverse("loans:pawn_loan_renew", args=[loan.pk]),
                preview_payload,
            )
        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(
            preview_response.json()["fingerprint"], exact_plan.fingerprint
        )
        self.assertEqual(
            preview_response.json()["successor_advance_interest"], "180.00"
        )
        command.assert_not_called()

        with patch(
            "apps.tenant_apps.loans.web.pawn_renewal_actions.preview_pawn_loan_renewal_source",
            return_value=quote,
        ):
            page = self.client.get(
                reverse("loans:pawn_loan_renew", args=[loan.pk])
            )
        self.assertContains(page, "Exact source settlement")
        self.assertContains(page, "Renewal-day interest")
        self.assertContains(page, "Successor and cash preview")
        self.assertContains(page, "I confirm the source settlement")
        self.assertContains(page, "Use camera/webcam")
        self.assertContains(page, "Capture collateral photograph")

    def _configured_setup(self):
        license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="UI License",
            license_number=f"PBL-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
            created_by=self.owner,
        )
        series = LoanSeries.objects.create(license=license, name="Main", code="A")
        for kind, prefix in (
            (LoanDocumentKind.PAWN_LOAN.value, "PL-A-"),
            (LoanDocumentKind.PAWN_LOAN_RELEASE.value, "RL-A-"),
        ):
            LoanNumberSequence.objects.create(
                series=series,
                document_kind=kind,
                prefix=prefix,
                width=5,
                maximum_number=10000,
            )
        PawnLoanEconomicPolicy.objects.create(
            workspace=self.tenant,
            license=license,
            valuation_method="LATEST_APPRAISAL",
            maximum_ltv_ratio=Decimal("0.80"),
            advance_interest_periods=1,
            effective_from=date(2026, 1, 1),
            created_by=self.owner,
        )
        for metal, rate in (("GOLD", "2"), ("SILVER", "4")):
            PawnMetalInterestRatePolicy.objects.create(
                workspace=self.tenant,
                license=license,
                metal=metal,
                monthly_interest_rate=Decimal(rate),
                effective_from=date(2026, 1, 1),
                created_by=self.owner,
            )
        return license, series

    def _payload(self, license, series):
        return {
            "borrower": self.party.pk,
            "series": series.pk,
            "product_version": self.product_version.pk,
            "loan_date": "2026-07-18",
            "tenure_months": "3",
            "collateral-TOTAL_FORMS": "1",
            "collateral-INITIAL_FORMS": "0",
            "collateral-MIN_NUM_FORMS": "1",
            "collateral-MAX_NUM_FORMS": "1000",
            "collateral-0-description": "Gold chain",
            "collateral-0-metal": "GOLD",
            "collateral-0-gross_weight": "10.0000",
            "collateral-0-net_weight": "9.0000",
            "collateral-0-purity_percentage": "91.6000",
            "collateral-0-latest_appraised_value": "50000.00",
            "collateral-0-allocated_principal": "10000.00",
            "collateral-0-photograph": SimpleUploadedFile(
                "gold-chain.jpg",
                b"\xff\xd8\xff\xe0evidence",
                content_type="image/jpeg",
            ),
        }

    def _mixed_metal_payload(self, license, series):
        payload = self._payload(license, series)
        payload.update(
            {
                "collateral-TOTAL_FORMS": "2",
                "collateral-0-latest_appraised_value": "10000.00",
                "collateral-0-allocated_principal": "5000.00",
                "collateral-1-description": "Silver anklet",
                "collateral-1-metal": "SILVER",
                "collateral-1-gross_weight": "30.0000",
                "collateral-1-net_weight": "25.0000",
                "collateral-1-purity_percentage": "80.0000",
                "collateral-1-latest_appraised_value": "10000.00",
                "collateral-1-allocated_principal": "4000.00",
                "collateral-1-photograph": SimpleUploadedFile(
                    "silver-anklet.png",
                    b"\x89PNG\r\n\x1aevidence",
                    content_type="image/png",
                ),
            }
        )
        return payload
