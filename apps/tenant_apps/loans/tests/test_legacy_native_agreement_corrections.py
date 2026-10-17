"""Unserviced policy-1 agreements retain their actual calendar and cash review."""

from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.test import override_settings
from django.utils import timezone

from apps.tenant_apps.data_portability.tests.fixtures import PortabilityFixture
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services import (
    approve_pawn_loan,
    disburse_pawn_loan,
    create_pawn_loan_economic_policy,
)
from apps.tenant_apps.loans.services import pawn_lifecycle
from apps.tenant_apps.loans.services.agreement_corrections import (
    preview_agreement_correction,
    record_agreement_correction,
)
from apps.tenant_apps.loans.services.pawn_interest import (
    preview_pawn_loan_accruals,
    finalize_pawn_loan_accrual,
)
from apps.tenant_apps.loans.tests import test_collateral_reappraisal as fixtures


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class LegacyNativeAgreementCorrectionTests(PortabilityFixture):
    make_loan = fixtures.CollateralReappraisalTests.make_loan
    original = date(2026, 1, 31)
    day = date(2026, 3, 1)

    def setUp(self):
        super().setUp()
        self.tenant = self.a
        # Create an authentic version-1 frozen approval before disbursal; never
        # rewrite an immutable policy/snapshot after origination to fake history.
        build = pawn_lifecycle._approval_payload

        def legacy_payload(*args, **kwargs):
            value = build(*args, **kwargs)
            value["collateral_economics"]["policy_version"] = 1
            return value

        with (
            self.scoped(),
            patch("django.utils.timezone.localdate", return_value=self.original),
            patch(
                "django.utils.timezone.now",
                return_value=timezone.make_aware(datetime(2026, 1, 31, 12)),
            ),
        ):
            self.make_loan(
                method="LATEST_APPRAISAL", product_index=2, age_days=0, activate=False
            )
            from apps.tenant_apps.loans.services.license_series import (
                _record_license_revision,
            )

            self.loan.license_revision = _record_license_revision(
                self.loan.license,
                kind=m.LoanLicenseRevision.Kind.INITIAL,
                actor=self.actor,
            )
            self.loan.save(update_fields=["license_revision"])
            create_pawn_loan_economic_policy(
                workspace=self.a,
                license=self.loan.license,
                valuation_method="LATEST_APPRAISAL",
                maximum_ltv_ratio=Decimal(".8"),
                advance_interest_periods=1,
                currency_quantum=Decimal(".01"),
                effective_from=self.original,
                actor=self.actor,
            )
            with patch.object(
                pawn_lifecycle, "_approval_payload", side_effect=legacy_payload
            ):
                approve_pawn_loan(self.loan.pk, actor=self.actor)
            disburse_pawn_loan(
                self.loan.pk, effective_date=self.original, actor=self.actor
            )
            self.loan.refresh_from_db()
            self.assertEqual(self.loan.policy_snapshot.policy_version, 1)

    def facts(self, **changes):
        return (
            dict(
                date=self.original.isoformat(),
                principal="1000",
                rate="1.1",
                cash_paid="989",
                reference="Original paper payout and 1.1% advance verified",
                reason="Wrong inherited interest rate",
                request_key=uuid4().hex,
            )
            | changes
        )

    def correct(self, data=None):
        data = data or self.facts()
        review, token = preview_agreement_correction(
            self.loan.pk, actor=self.actor, data=data
        )
        result = record_agreement_correction(
            self.loan.pk,
            actor=self.actor,
            data=data,
            review_token=token,
            confirmed=True,
        )
        self.loan.refresh_from_db()
        return data, review, token, result

    def test_preserves_legacy_policy_calendar_upfront_and_immutable_source(self):
        with (
            self.scoped(),
            patch("django.utils.timezone.localdate", return_value=self.day),
        ):
            policy = self.loan.policy_snapshot
            fields = {
                f.name: getattr(policy, f.name)
                for f in m.LoanPolicySnapshot._meta.fields
                if f.name not in {"id", "workspace", "loan", "created_at"}
            }
            old = self.loan.disbursal_snapshot
            old_payload = deepcopy(old.loan_event.payload)
            self.correct()
            self.assertEqual(self.loan.policy_snapshot.policy_version, 1)
            self.assertEqual(
                {k: getattr(self.loan.policy_snapshot, k) for k in fields}, fields
            )
            self.assertEqual(self.loan.disbursal_snapshot.advance_interest, 11)
            self.assertEqual(self.loan.disbursal_snapshot.net_disbursed, 989)
            old.loan_event.refresh_from_db()
            self.assertEqual(old.loan_event.payload, old_payload)
            pending = preview_pawn_loan_accruals(self.loan.pk, as_of_date=self.day)
            self.assertEqual(pending[0].period_end, date(2026, 2, 27))
            self.assertEqual(pending[1].period_start, date(2026, 2, 28))
            self.assertEqual(pending[0].advance_interest_applied, 11)
            self.assertEqual(pending[0].recognized_interest, 0)
            self.assertEqual(pending[1].recognized_interest, 11)

    def test_saved_payout_cannot_be_silently_preserved_when_corrected_advance_differs(
        self,
    ):
        with (
            self.scoped(),
            patch("django.utils.timezone.localdate", return_value=self.day),
        ):
            before = list(self.loan.loan_events.values())
            with self.assertRaisesMessage(ValueError, "Corrected proceeds"):
                preview_agreement_correction(
                    self.loan.pk, actor=self.actor, data=self.facts(cash_paid="980")
                )
            self.assertEqual(list(self.loan.loan_events.values()), before)

    def test_later_legacy_charge_prevents_independent_original_agreement_correction(
        self,
    ):
        with (
            self.scoped(),
            patch("django.utils.timezone.localdate", return_value=self.day),
        ):
            finalize_pawn_loan_accrual(self.loan.pk, actor=self.actor, period_number=1)
            with self.assertRaisesMessage(ValueError, "unserviced disbursal"):
                preview_agreement_correction(
                    self.loan.pk, actor=self.actor, data=self.facts()
                )

    def test_corrected_export_uses_version_8_and_cannot_be_downgraded(self):
        from apps.tenant_apps.loans.services.servicing_bundle import (
            export_servicing_bundle,
            restore_servicing_bundle,
        )
        from apps.orgs.models import Company
        from apps.tenancy.context import without_workspace_context
        from apps.tenant_apps.party.models import Party
        from apps.tenant_apps.data_portability.models import (
            PartyIdentity,
            SourceIdentity,
        )
        from apps.tenant_apps.loans.services.license_series import create_license
        from apps.tenant_apps.loans.services.servicing_bundle_contract import (
            read_bundle,
            decode,
        )

        self.actor.is_superuser = True
        self.actor.save(update_fields=["is_superuser"])
        with (
            self.scoped(),
            patch("django.utils.timezone.localdate", return_value=self.day),
        ):
            data, _, token, _ = self.correct()
            self.assertFalse(
                record_agreement_correction(
                    self.loan.pk,
                    actor=self.actor,
                    data=data,
                    review_token=token,
                    confirmed=True,
                )[1]
            )
        with self.scoped():
            content = export_servicing_bundle(
                workspace_id=self.a.pk, actor=self.actor, loan_id=self.loan.pk
            )
            document, _ = read_bundle(content)
            self.assertEqual(document["profile"], "loan-servicing-bundle/8")
            snapshot = next(
                r
                for r in document["tables"]["PawnLoanDisbursalSnapshot"]
                if r["basis"] == "CORRECTED"
            )
            with self.assertRaisesMessage(ValueError, "version 8"):
                decode(
                    "PawnLoanDisbursalSnapshot",
                    snapshot,
                    profile="loan-servicing-bundle/7",
                )
        with without_workspace_context():
            target = Company.objects.create(
                name="Legacy native restore",
                schema_name="legacy_" + uuid4().hex,
                owner=self.actor,
                creator=self.actor,
            )
        with self.scoped(target):
            key = str(self.loan.pk)
            setup = document["setup"][key]
            reference = setup["borrower"]
            party = Party.objects.create(display_name="Synthetic source borrower")
            identity = PartyIdentity.objects.create(workspace=target, party=party)
            SourceIdentity.objects.create(
                workspace=target,
                identity=identity,
                source_system=reference["source_system"],
                external_id=reference["id"],
                accepted_digest="a" * 64,
                local_digest="a" * 64,
            )
            license = create_license(
                workspace=target,
                actor=self.actor,
                name="Original register",
                license_number=setup["licence_number"],
                issued_on=date(2020, 1, 1),
                expires_on=date(2099, 1, 1),
            )
            series = m.LoanSeries.objects.create(
                license=license, name="Original", code="AA"
            )
            product = m.LoanProduct.objects.create(
                workspace=target, name="Legacy native", code="AA"
            )
            version = m.LoanProductVersion.objects.create(
                product=product,
                version=1,
                status="RETIRED",
                maximum_tenor_months=1200,
                **setup["product"],
            )
            args = dict(
                workspace_id=target.pk,
                actor=self.actor,
                content=content,
                mapping={
                    key: dict(
                        borrower_id=party.pk,
                        revision_id=license.revisions.get().pk,
                        series_id=series.pk,
                        product_version_id=version.pk,
                    )
                },
            )
            preview = restore_servicing_bundle(**args)
            self.assertFalse(m.PawnLoan.objects.exists())
            result = restore_servicing_bundle(
                **args, expected_sha256=preview["sha256"], confirmed=True
            )
            restored = m.PawnLoan.objects.get(pk=result["loans"][0])
            self.assertEqual(restored.policy_snapshot.policy_version, 1)
            self.assertEqual(restored.disbursal_snapshot.advance_interest, 11)
            self.assertEqual(restored.disbursal_snapshot.net_disbursed, 989)
            again, _ = read_bundle(
                export_servicing_bundle(
                    workspace_id=target.pk, actor=self.actor, loan_id=restored.pk
                )
            )
            self.assertEqual(
                again["positions"][str(restored.pk)]["recorded"],
                document["positions"][key]["recorded"],
            )
            self.assertTrue(
                restore_servicing_bundle(
                    **args, expected_sha256=preview["sha256"], confirmed=True
                )["already_restored"]
            )
        from apps.tenant_apps.loans.tests.test_pawn_recovery import PawnRecoveryTests

        self.tenant = target
        original = PawnRecoveryTests.export(self)
        PawnRecoveryTests.empty(self)
        self.assertFalse(PawnRecoveryTests.restore(self)["committed"])
        self.assertTrue(PawnRecoveryTests.restore(self, commit=True)["committed"])
        recovered = PawnRecoveryTests.export(self)
        self.assertEqual(original["tables"], recovered["tables"])

    def test_stale_review_and_second_revision_preserve_first_month_payment(self):
        with (
            self.scoped(),
            patch("django.utils.timezone.localdate", return_value=self.day),
        ):
            data = self.facts()
            _, token = preview_agreement_correction(
                self.loan.pk, actor=self.actor, data=data
            )
            self.loan.collateral_items.update(description="Changed evidence")
            with self.assertRaisesMessage(ValueError, "facts changed"):
                record_agreement_correction(
                    self.loan.pk,
                    actor=self.actor,
                    data=data,
                    review_token=token,
                    confirmed=True,
                )
            self.correct(data)
            self.correct(self.facts(rate="1.2", cash_paid="988"))
            self.assertEqual(self.loan.policy_snapshot.policy_version, 1)
            self.assertEqual(self.loan.disbursal_snapshot.advance_interest, 12)
            self.assertEqual(
                self.loan.disbursal_snapshot.evidence["agreement_correction"][
                    "revision"
                ],
                3,
            )
