"""Effective lending terms and narrow changes preserve financial boundaries."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, DatabaseError, transaction
from django.test import override_settings
from django.urls import reverse

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import without_workspace_context, workspace_context
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.selectors.lending_terms import effective_lending_terms
from apps.tenant_apps.loans.services.economic_policies import (
    create_pawn_economic_configuration,
)
from apps.tenant_apps.loans.services.license_series import create_license
from apps.tenant_apps.loans.services.economic_policy_reviews import (
    preview_economic_change,
    confirm_economic_change,
)
from apps.tenant_apps.loans.services.entry_purpose import (
    new_loan_entry_purpose as default_entry_purpose,
)


@override_settings(
    ROOT_URLCONF="django_project.workspace_urls",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
)
class LendingSetupTests(WorkspaceTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        owner = get_user_model().objects.create_user(username="lending-setup-owner")
        tenant.owner = tenant.creator = owner
        tenant.save()
        Membership.objects.create(
            company=tenant, user=owner, role=Role.objects.get_or_create(name="Owner")[0]
        )

    def setUp(self):
        super().setUp()
        self.enterContext(
            patch("django.utils.timezone.localdate", return_value=date(2026, 10, 17))
        )
        self.start_active_trial()
        self.owner = self.tenant.owner
        self.client = self.make_workspace_client()
        self.client.force_login(self.owner)
        self.license = create_license(
            workspace=self.tenant,
            name="Lending licence",
            license_number="TEST-A",
            issued_on=date(2026, 1, 1),
            expires_on=date(2028, 1, 1),
            actor=self.owner,
        )
        self.series = m.LoanSeries.objects.create(
            workspace=self.tenant, license=self.license, name="Register AA", code="AA"
        )
        self.original = create_pawn_economic_configuration(
            workspace=self.tenant,
            actor=self.owner,
            valuation_method="LATEST_APPRAISAL",
            maximum_ltv_ratio=Decimal(".8"),
            default_tenure_months=12,
            gold_monthly_interest_rate=Decimal("2"),
            silver_monthly_interest_rate=Decimal("4"),
            effective_from=date(2026, 1, 1),
            default_entry_purpose="PAPER",
        )

    def reviewed(self, kind, **changes):
        return dict(
            workspace=self.tenant,
            actor=self.owner,
            kind=kind,
            values=dict(effective_from=date(2026, 10, 17), **changes),
        )

    def save(self, args):
        review, token = preview_economic_change(**args)
        result = confirm_economic_change(**args, token=token, acknowledged=True)
        return review, result, token

    def test_entry_preference_is_independent_and_retains_legacy_scope_inheritance(self):
        from apps.tenant_apps.loans.services.entry_purpose import (
            default_entry_purpose as servicing_default,
        )

        before = {
            model.__name__: list(model.objects.filter(workspace=self.tenant).values())
            for model in (
                m.PawnLoanEconomicPolicy,
                m.PawnMetalInterestRatePolicy,
                m.PawnLoanFeePolicy,
                m.LoanMonitoringPolicy,
                m.LoanNumberSequence,
            )
        }
        self.assertEqual(
            default_entry_purpose(workspace=self.tenant, series_id=self.series.pk),
            "PAPER",
        )
        args = self.reviewed("entry", purpose="DIRECT")
        review, result, token = self.save(args)
        self.assertTrue(review["entry_preference"])
        self.assertEqual(
            default_entry_purpose(workspace=self.tenant, series_id=self.series.pk),
            "DIRECT",
        )
        self.assertTrue(
            confirm_economic_change(**args, token=token, acknowledged=True)[
                "already_saved"
            ]
        )
        self.assertEqual(m.LoanEntryPreference.objects.count(), 1)
        self.assertEqual(
            servicing_default(workspace=self.tenant, series_id=self.series.pk), "PAPER"
        )
        self.save(
            self.reviewed(
                "entry", license=self.license, series=self.series, purpose="PAPER"
            )
        )
        self.assertEqual(
            default_entry_purpose(workspace=self.tenant, series_id=self.series.pk),
            "PAPER",
        )
        self.save(
            self.reviewed(
                "entry", license=self.license, series=self.series, purpose="INHERIT"
            )
        )
        self.assertEqual(
            default_entry_purpose(workspace=self.tenant, series_id=self.series.pk),
            "DIRECT",
        )
        for model in (
            m.PawnLoanEconomicPolicy,
            m.PawnMetalInterestRatePolicy,
            m.PawnLoanFeePolicy,
            m.LoanMonitoringPolicy,
            m.LoanNumberSequence,
        ):
            self.assertEqual(
                list(model.objects.filter(workspace=self.tenant).values()),
                before[model.__name__],
            )

    def test_rate_only_change_does_not_copy_other_metals_or_calculation_policy(self):
        _, result, _ = self.save(
            self.reviewed(
                "rates",
                license=self.license,
                series=self.series,
                gold_monthly_interest_rate=Decimal("1.1"),
            )
        )
        self.assertEqual(len(result["policy_ids"]), 1)
        self.assertEqual(m.PawnLoanEconomicPolicy.objects.count(), 1)
        terms = effective_lending_terms(
            workspace=self.tenant, series=self.series, day=date(2026, 10, 17)
        )
        self.assertEqual(
            {row["metal"]: row["value"] for row in terms["rates"]},
            {"Gold": Decimal("1.1"), "Silver": Decimal("4")},
        )
        self.assertEqual(terms["policy"].pk, self.original.economic_policy.pk)
        self.assertIn("Series", terms["rates"][0]["source"])
        self.assertEqual(
            effective_lending_terms(
                workspace=self.tenant, series=self.series, day=date(2026, 10, 16)
            )["rates"][0]["value"],
            Decimal("2"),
        )

    def test_term_only_change_preserves_other_rules_and_rates(self):
        original = self.original.economic_policy
        before_rates = list(m.PawnMetalInterestRatePolicy.objects.values())
        self.save(
            self.reviewed(
                "terms",
                license=self.license,
                series=self.series,
                default_tenure_months=6,
                advance_interest_periods=None,
            )
        )
        effective = effective_lending_terms(
            workspace=self.tenant, series=self.series, day=date(2026, 10, 17)
        )["policy"]
        self.assertEqual(effective.default_tenure_months, 6)
        original.refresh_from_db()
        self.assertEqual(original.default_tenure_months, 12)
        for field in (
            "interest_method",
            "partial_month_method",
            "rounding_method",
            "advance_interest_periods",
            "currency_quantum",
            "default_entry_purpose",
        ):
            self.assertEqual(getattr(effective, field), getattr(original, field))
        self.assertEqual(
            list(m.PawnMetalInterestRatePolicy.objects.values()), before_rates
        )

    def test_stale_wrong_scope_and_unacknowledged_reviews_do_not_save(self):
        args = self.reviewed("entry", purpose="DIRECT")
        _, token = preview_economic_change(**args)
        self.assertFalse(m.LoanEntryPreference.objects.exists())
        with self.assertRaises(ValueError):
            confirm_economic_change(**args, token=token)
        self.save(self.reviewed("rates", gold_monthly_interest_rate=Decimal("1.5")))
        with self.assertRaisesMessage(ValueError, "Setup changed"):
            confirm_economic_change(**args, token=token, acknowledged=True)
        with self.assertRaises(ValidationError):
            preview_economic_change(**self.reviewed("entry", purpose="UNKNOWN"))
        with self.assertRaises(ValueError):
            preview_economic_change(
                **self.reviewed(
                    "terms", default_tenure_months=None, advance_interest_periods=None
                )
            )

    def test_scope_authority_and_database_guards(self):
        other = Company.objects.create(
            name="Other lending", owner=self.owner, creator=self.owner
        )
        with without_workspace_context(), workspace_context(other.pk):
            foreign = m.LoanLicense.objects.create(
                workspace=other,
                name="Foreign",
                license_number="FOREIGN",
                issued_on=date(2026, 1, 1),
                expires_on=date(2028, 1, 1),
            )
        with self.assertRaises(ValueError):
            preview_economic_change(
                **self.reviewed("entry", license=foreign, purpose="DIRECT")
            )
        viewer = get_user_model().objects.create_user(username="lending-viewer")
        Membership.objects.create(
            company=self.tenant,
            user=viewer,
            role=Role.objects.get_or_create(name="Viewer")[0],
        )
        with self.assertRaises(PermissionDenied):
            preview_economic_change(
                **(self.reviewed("entry", purpose="DIRECT") | {"actor": viewer})
            )
        role = connection.ops.quote_name("lending_rls_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}"
            )
            cursor.execute(
                f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}"
            )
            cursor.execute(f"SET LOCAL ROLE {role}")
        try:
            self.save(self.reviewed("entry", purpose="DIRECT"))
            for workspace, license in ((other, None), (self.tenant, foreign)):
                with (
                    self.assertRaises(DatabaseError),
                    transaction.atomic(),
                    connection.cursor() as cursor,
                ):
                    cursor.execute(
                        "INSERT INTO loans_loanentrypreference (workspace_id, license_id, purpose, updated_at) VALUES (%s,%s,'PAPER',CURRENT_TIMESTAMP)",
                        [workspace.pk, license.pk if license else None],
                    )
            self.assertEqual(
                m.LoanEntryPreference.objects.filter(workspace=other).count(), 0
            )
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    def test_setup_view_shows_effective_terms_and_narrow_changes(self):
        url = reverse("workspace_loans:pawn_economics_setup", args=[self.tenant.slug])
        page = self.client.get(url, {"series": self.series.pk})
        self.assertContains(page, "Business lending terms")
        self.assertContains(page, 'aria-label="Effective business lending terms"')
        self.assertEqual(
            page.context["effective_lending_terms"]["policy"].pk,
            self.original.economic_policy.pk,
        )
        for item in page.context["narrow_forms"]:
            self.assertEqual(item["form"]["series"].value(), self.series.pk)
            self.assertEqual(item["form"]["license"].value(), self.license.pk)
        self.assertEqual(
            page.context["configuration_form"]["series"].value(), self.series.pk
        )
        payload = {
            "action": "entry",
            "entry-purpose": "DIRECT",
            "entry-effective_from": "2026-10-17",
        }
        review = self.client.post(url, payload)
        self.assertContains(review, "This changes only today's initial New loan screen")
        self.assertFalse(m.LoanEntryPreference.objects.exists())
        row = next(
            item for item in review.context["narrow_forms"] if item["kind"] == "entry"
        )
        response = self.client.post(
            url,
            payload
            | {
                "economic_confirm": "1",
                "economic_acknowledged": "on",
                "economic_review_token": row["token"],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(m.LoanEntryPreference.objects.get().purpose, "DIRECT")

    def test_preexisting_review_token_remains_supported_without_new_preferences(self):
        from django.core import signing
        from apps.tenant_apps.loans.services.economic_policy_reviews import SALT, _state

        args = self.reviewed(
            "configuration",
            valuation_method="LATEST_APPRAISAL",
            maximum_ltv_ratio=Decimal(".8"),
            gold_monthly_interest_rate=Decimal("1.5"),
            silver_monthly_interest_rate=Decimal("4"),
        )
        _, token = preview_economic_change(**args)
        signed = signing.loads(token, salt=SALT)
        signed.pop("state_version")
        signed["state"] = _state(self.tenant, include_entry=False)
        old = signing.dumps(signed, salt=SALT, compress=True)
        self.assertFalse(
            confirm_economic_change(**args, token=old, acknowledged=True)[
                "already_saved"
            ]
        )

    def test_native_recovery_retains_entry_preference_identity_and_actor(self):
        import hashlib
        from apps.tenant_apps.loans.services import pawn_recovery as recovery
        from . import test_pawn_recovery as fixtures

        self.save(
            self.reviewed(
                "entry", license=self.license, series=self.series, purpose="DIRECT"
            )
        )
        before = list(m.LoanEntryPreference.objects.values())
        content = recovery.export_archive(workspace=self.tenant, actor=self.owner)
        checksum = hashlib.sha256(content).hexdigest()
        fixtures.PawnRecoveryTests.empty(self)
        self.assertFalse(m.LoanEntryPreference.objects.exists())
        recovery.restore_archive(
            workspace=self.tenant,
            actor=self.owner,
            content=content,
            expected_sha256=checksum,
            commit=True,
        )
        self.assertEqual(list(m.LoanEntryPreference.objects.values()), before)

    def test_new_screen_preference_does_not_change_saved_draft_or_financial_review(
        self,
    ):
        from apps.tenant_apps.party.models import Party
        from apps.tenant_apps.loans.services.pawn_drafts import (
            CreatePawnDraftCommand,
            CollateralDraftInput,
            create_pawn_draft,
        )
        from apps.tenant_apps.loans.services.product_catalog import (
            _seed_default_loan_products,
            activate_product_version,
        )
        from apps.tenant_apps.loans.services.loan_workflow import review_values

        product = _seed_default_loan_products()[0]
        activate_product_version(product.pk, actor=self.owner)
        borrower = Party.objects.create(display_name="Fictional review customer")
        m.LoanNumberSequence.objects.create(
            series=self.series,
            document_kind="PAWN_LOAN",
            prefix="AA",
            width=5,
            maximum_number=10000,
        )
        loan = create_pawn_draft(
            CreatePawnDraftCommand(
                workspace_id=self.tenant.pk,
                borrower_id=borrower.pk,
                license_id=self.license.pk,
                series_id=self.series.pk,
                product_version_id=product.pk,
                principal_amount=Decimal("1000"),
                monthly_interest_rate=Decimal("2"),
                loan_date=date(2026, 10, 17),
                tenure_months=12,
                collateral=(
                    CollateralDraftInput(
                        description="Fictional ring",
                        metal="GOLD",
                        gross_weight=Decimal("10"),
                        net_weight=Decimal("10"),
                        purity_percentage=Decimal("100"),
                        allocated_principal=Decimal("1000"),
                        latest_appraised_value=Decimal("2000"),
                    ),
                ),
            ),
            actor=self.owner,
        )
        original = m.PawnLoan.objects.values().get(pk=loan.pk)
        before = review_values(loan)
        self.save(
            self.reviewed(
                "entry", license=self.license, series=self.series, purpose="DIRECT"
            )
        )
        self.assertEqual(review_values(loan), before)
        self.assertEqual(m.PawnLoan.objects.values().get(pk=loan.pk), original)
        self.assertEqual(
            m.LoanNumberSequence.objects.get(series=self.series).next_number, 1
        )
