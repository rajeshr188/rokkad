"""Retained aggregate openings share the ordinary audited correction boundary."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.test import SimpleTestCase
from django.urls import reverse

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.selectors.servicing_contract import get_servicing_position
from apps.tenant_apps.loans.services.agreement_corrections import (
    preview_agreement_correction,
    record_agreement_correction,
)
from apps.tenant_apps.loans.services.legacy_interest import (
    aggregate_collection_interest,
)
from apps.tenant_apps.loans.services.opening_continuation import (
    opening_interest_breakdown,
)
from apps.tenant_apps.loans.services.opening_corrections import _validate_change
from apps.tenant_apps.loans.services.opening_evidence import read_opening_evidence
from apps.tenant_apps.loans.services.opening_rate_review import (
    prepare_unpaid_collection_rate_review,
)
from apps.tenant_apps.loans.tests.test_opening_continuation import collection_review
from apps.tenant_apps.loans.tests.test_opening_import import OpeningImportFixture


def aggregate_review(
    original=date(2021, 1, 1), cutover=date(2021, 3, 2), principal="1013"
):
    review = collection_review(original, cutover, rate="2")
    item = review["collateral"][0]
    item.update(original_principal=principal, remaining_principal=principal)
    calculated = aggregate_collection_interest(
        original, cutover, Decimal(principal) * Decimal(".02")
    )
    interest = calculated["additional_interest"]
    review["balances"].update(principal=principal, interest=interest)
    review["continuation"].update(
        recognized_interest=interest, recognized_unpaid_interest=interest
    )
    review["obligations"][0].update(
        principal=principal, interest=interest, recognized_interest=interest
    )
    return review


def corrected(review, rate="1.1"):
    return prepare_unpaid_collection_rate_review(
        review,
        monthly_rate=rate,
        reference="Owner-confirmed original paper terms and upfront payment",
    )


class AggregateRateReviewTests(SimpleTestCase):
    def test_separate_principal_obligation_keeps_identity_date_and_amount(self):
        before = aggregate_review()
        principal = deepcopy(before["obligations"][0])
        principal.update(
            id="principal-only", due="2021-04-29", interest="0", recognized_interest="0"
        )
        before["obligations"][0].update(principal="0", due="2021-03-02")
        before["obligations"].append(principal)
        after = corrected(before)
        self.assertEqual(after["obligations"][1], principal)
        self.assertEqual(after["obligations"][0]["due"], "2021-03-02")
        self.assertEqual(after["obligations"][0]["interest"], "22")

    def test_round_original_amounts_once_instead_of_scaling_rounded_interest(self):
        before = aggregate_review()
        retained = deepcopy(before)
        after = corrected(before)
        self.assertEqual(before, retained)
        self.assertEqual(before["balances"]["interest"], "41")
        self.assertEqual(after["balances"]["interest"], "22")
        self.assertNotEqual(
            Decimal(after["balances"]["interest"]),
            (Decimal("41") * Decimal(".55")).quantize(Decimal("1")),
        )
        self.assertEqual(after["profile"], before["profile"])
        self.assertEqual(after["terms"], before["terms"])
        self.assertTrue(after["continuation"]["first_month_paid"])
        _validate_change(before, after)

    def test_short_month_anniversary_and_first_month_stay_covered(self):
        for original, anniversary, next_day in (
            (date(2021, 1, 31), date(2021, 2, 28), date(2021, 3, 1)),
            (date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 1)),
        ):
            before = aggregate_review(original, anniversary)
            after = corrected(before)
            self.assertEqual(after["balances"]["interest"], "0")
            self.assertEqual(
                opening_interest_breakdown(after, as_of_date=anniversary)[
                    "total_interest"
                ],
                0,
            )
            self.assertEqual(
                opening_interest_breakdown(after, as_of_date=next_day)[
                    "total_interest"
                ],
                11,
            )

    def test_partial_payments_future_charges_and_multiple_obligations_need_explicit_review(
        self,
    ):
        before = aggregate_review()
        partial = deepcopy(before)
        partial["balances"]["interest"] = partial["continuation"][
            "recognized_unpaid_interest"
        ] = "31"
        partial["obligations"][0].update(interest="31", recognized_interest="31")
        with self.assertRaisesMessage(ValueError, "Earlier paid or waived"):
            corrected(partial)
        future = deepcopy(before)
        future["obligations"][0]["interest"] = "50"
        with self.assertRaisesMessage(ValueError, "Future or differently allocated"):
            corrected(future)
        multiple = deepcopy(before)
        row = deepcopy(multiple["obligations"][0])
        multiple["obligations"][0].update(interest="20", recognized_interest="20")
        row.update(id="second", principal="0", interest="21", recognized_interest="21")
        multiple["obligations"].append(row)
        with self.assertRaisesMessage(ValueError, "Multiple interest"):
            corrected(multiple)

    def test_profile_economic_rule_source_and_upfront_cannot_be_changed(self):
        before = aggregate_review()
        for group, key, value in (
            (None, "profile", "loan-opening-review/3"),
            ("terms", "rounding_mode", "HALF_UP"),
            ("source", "loan_id", "different-source"),
            ("continuation", "first_month_paid", False),
            ("continuation", "covered_through", "2021-03-01"),
        ):
            after = corrected(before)
            (after if group is None else after[group])[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                _validate_change(before, after)

    def test_invalid_rates_are_rejected_without_arithmetic_or_mutation(self):
        before = aggregate_review()
        for rate in ("NaN", "Infinity", "-1", "1000", "1.1234567", "", 1.1):
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                corrected(before, rate)


class AggregateCheckpointCorrectionTests(OpeningImportFixture):
    day = date(2021, 3, 3)

    def setUp(self):
        super().setUp()
        review = aggregate_review()
        review["terms"]["maturity_date"] = "2021-04-01"
        review["obligations"][0]["due"] = "2021-04-01"
        review["mapping"] = self.review["mapping"]
        review["source"]["borrower_id"] = self.review["source"]["borrower_id"]
        review["collateral"][0].update(metal="BRONZE", gross_weight=None)
        self.review = review
        self.args["review"] = review
        with self.scoped():
            self.origin = self.write()
            self.loan = self.origin.loan

    def facts(self, **changes):
        origin = self.loan.loan_events.get(event_kind="MIGRATION_OPENING")
        opening = read_opening_evidence(self.loan, origin)
        return (
            dict(
                checkpoint=corrected(opening["review"]),
                reference="Confirmed original paper rate and paid first month",
                reason="Wrong default rate inherited at migration",
                request_key=uuid4().hex,
            )
            | changes
        )

    def apply(self, data=None):
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

    def test_preview_rollback_apply_retry_and_source_immutability(self):
        with (
            self.scoped(),
            patch("django.utils.timezone.localdate", return_value=self.day),
        ):
            old_events = list(self.loan.loan_events.values())
            old_document = deepcopy(self.origin.document)
            old_policy = self.loan.policy_snapshot_id
            data = self.facts()
            review, token = preview_agreement_correction(
                self.loan.pk, actor=self.actor, data=data
            )
            self.assertEqual(list(self.loan.loan_events.values()), old_events)
            self.loan.refresh_from_db()
            self.assertEqual(self.loan.monthly_interest_rate, 2)
            log, created = record_agreement_correction(
                self.loan.pk,
                actor=self.actor,
                data=data,
                review_token=token,
                confirmed=True,
            )
            self.assertTrue(created)
            self.loan.refresh_from_db()
            self.assertEqual(
                (self.loan.principal_amount, self.loan.monthly_interest_rate),
                (1013, Decimal("1.1")),
            )
            self.assertEqual(self.loan.policy_snapshot_id, old_policy)
            self.assertEqual(Decimal(review["before"]["position"]["interest"]), 41)
            self.assertEqual(Decimal(review["after"]["position"]["interest"]), 22)
            self.assertEqual(
                self.loan.loan_events.filter(event_kind="MIGRATION_OPENING").count(), 1
            )
            self.assertEqual(
                list(self.loan.loan_events.filter(pk=old_events[0]["id"]).values()),
                old_events,
            )
            self.origin.refresh_from_db()
            self.assertEqual(self.origin.document, old_document)
            self.assertEqual(self.loan.repayment_schedules.count(), 2)
            self.assertFalse(
                record_agreement_correction(
                    self.loan.pk,
                    actor=self.actor,
                    data=data,
                    review_token=token,
                    confirmed=True,
                )[1]
            )
            with self.assertRaises(DatabaseError), transaction.atomic():
                self.loan.loan_events.filter(event_kind="OPENING_CORRECTION").delete()
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.LoanChangeLog.objects.filter(pk=log.pk).delete()

    def test_servicing_continues_from_corrected_checkpoint_without_double_charging(
        self,
    ):
        from apps.tenant_apps.loans.services.pawn_repayment import (
            record_pawn_loan_repayment,
        )

        with (
            self.scoped(),
            patch("django.utils.timezone.localdate", return_value=self.day),
        ):
            self.apply()
            self.assertEqual(
                get_servicing_position(
                    self.loan, as_of_date=date(2021, 4, 2)
                ).balance.interest_outstanding,
                33,
            )
            record_pawn_loan_repayment(
                self.loan.pk,
                amount="5",
                request_key="after-correction",
                actor=self.actor,
            )
            self.assertEqual(
                get_servicing_position(
                    self.loan, as_of_date=self.day
                ).balance.interest_outstanding,
                17,
            )
            with self.assertRaisesMessage(ValueError, "connected reconciliation"):
                preview_agreement_correction(
                    self.loan.pk, actor=self.actor, data=self.facts()
                )

    def test_stale_source_competing_review_unconfirmed_and_changed_retry_are_refused(
        self,
    ):
        with (
            self.scoped(),
            patch("django.utils.timezone.localdate", return_value=self.day),
        ):
            first = self.facts()
            second = self.facts(checkpoint=corrected(self.review, "1.2"))
            _, token = preview_agreement_correction(
                self.loan.pk, actor=self.actor, data=first
            )
            _, other = preview_agreement_correction(
                self.loan.pk, actor=self.actor, data=second
            )
            with self.assertRaisesMessage(ValueError, "Confirm"):
                record_agreement_correction(
                    self.loan.pk, actor=self.actor, data=first, review_token=token
                )
            record_agreement_correction(
                self.loan.pk,
                actor=self.actor,
                data=first,
                review_token=token,
                confirmed=True,
            )
            with self.assertRaisesMessage(ValueError, "facts changed"):
                record_agreement_correction(
                    self.loan.pk,
                    actor=self.actor,
                    data=second,
                    review_token=other,
                    confirmed=True,
                )
            with self.assertRaisesMessage(ValueError, "different checkpoint facts"):
                record_agreement_correction(
                    self.loan.pk,
                    actor=self.actor,
                    data=first | {"reason": "Different"},
                    review_token=token,
                    confirmed=True,
                )

    def test_workspace_scope_and_authority_precede_preview(self):
        with self.scoped():
            data = self.facts()
        with self.assertRaises((ValueError, PermissionDenied)):
            preview_agreement_correction(self.loan.pk, actor=self.actor, data=data)
        with self.scoped(self.b), self.assertRaisesMessage(ValueError, "not found"):
            preview_agreement_correction(self.loan.pk, actor=self.actor, data=data)
        with self.scoped(), self.assertRaises(PermissionDenied):
            preview_agreement_correction(
                self.loan.pk, actor=self.other_actor, data=data
            )

    def test_risk_refresh_uses_corrected_position_without_changing_monitoring_policy(
        self,
    ):
        from apps.tenant_apps.loans.services.risk_snapshots import (
            refresh_loan_risk_snapshot,
        )

        with (
            self.scoped(),
            patch("django.utils.timezone.localdate", return_value=self.day),
        ):
            m.LoanMonitoringPolicy.objects.create(
                workspace=self.a,
                version=1,
                effective_from=date(2021, 1, 1),
                compliance_profile="Synthetic monitoring",
                ltv_warning_ratio=".7",
                ltv_breach_ratio=".8",
                ltv_critical_ratio=".9",
                eligible_custody_states=["IN_VAULT"],
                severity_mapping={"strategy": "derived-v1"},
                created_by=self.actor,
            )
            prior = refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.day)
            policy = list(m.LoanMonitoringPolicy.objects.values())
            self.apply()
            prior.refresh_from_db()
            self.assertEqual(prior.status, "STALE")
            current = refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.day)
            self.assertEqual(current.exposure, Decimal("1035"))
            self.assertEqual(
                get_servicing_position(
                    self.loan, as_of_date=self.day
                ).balance.financial_history_from,
                self.day.replace(day=2),
            )
            self.assertEqual(list(m.LoanMonitoringPolicy.objects.values()), policy)

    def test_mutable_collateral_and_retained_history_reject_stale_preview(self):
        with (
            self.scoped(),
            patch("django.utils.timezone.localdate", return_value=self.day),
        ):
            data = self.facts()
            _, token = preview_agreement_correction(
                self.loan.pk, actor=self.actor, data=data
            )
            self.loan.collateral_items.update(description="New physical description")
            with self.assertRaisesMessage(ValueError, "facts changed"):
                record_agreement_correction(
                    self.loan.pk,
                    actor=self.actor,
                    data=data,
                    review_token=token,
                    confirmed=True,
                )
            self.assertEqual(self.loan.loan_events.count(), 1)

    def test_downgrade_guard_refuses_retained_aggregate_correction(self):
        from importlib import import_module

        with (
            self.scoped(),
            patch("django.utils.timezone.localdate", return_value=self.day),
        ):
            self.apply()
            reverse_sql = (
                import_module(
                    "apps.tenant_apps.loans.migrations.0092_aggregate_checkpoint_corrections"
                )
                .Migration.operations[0]
                .reverse_sql
            )
            with (
                self.assertRaisesMessage(
                    DatabaseError, "Retained aggregate or legacy corrections"
                ),
                transaction.atomic(),
            ):
                with connection.cursor() as cursor:
                    cursor.execute(reverse_sql)

    def test_runtime_cannot_forge_a_checkpoint_predecessor(self):
        from apps.tenant_apps.loans.services.event_recording import _fingerprint

        with (
            self.scoped(),
            patch("django.utils.timezone.localdate", return_value=self.day),
        ):
            self.apply()
            event = self.loan.loan_events.get(event_kind="OPENING_CORRECTION")
            wrong = deepcopy(event.payload)
            wrong["agreement_correction"]["source_event_id"] = 999999999
            fingerprint = _fingerprint(wrong)
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.PawnLoanEvent.objects.bulk_create(
                    [
                        m.PawnLoanEvent(
                            workspace=self.a,
                            loan=self.loan,
                            event_kind="OPENING_CORRECTION",
                            effective_date=event.effective_date,
                            payload=wrong,
                            payload_fingerprint=fingerprint,
                            idempotency_key="loans:forged:" + fingerprint,
                            created_by=self.actor,
                        )
                    ]
                )

    def test_failed_schedule_persistence_rolls_back_all_financial_changes(self):
        with (
            self.scoped(),
            patch("django.utils.timezone.localdate", return_value=self.day),
        ):
            data = self.facts()
            _, token = preview_agreement_correction(
                self.loan.pk, actor=self.actor, data=data
            )
            before = list(self.loan.loan_events.values())
            with patch(
                "apps.tenant_apps.loans.services.opening_obligations.persist_opening_repayment_schedule",
                side_effect=ValueError("Schedule unavailable"),
            ):
                with self.assertRaisesMessage(ValueError, "Schedule unavailable"):
                    record_agreement_correction(
                        self.loan.pk,
                        actor=self.actor,
                        data=data,
                        review_token=token,
                        confirmed=True,
                    )
            self.loan.refresh_from_db()
            self.assertEqual(self.loan.monthly_interest_rate, 2)
            self.assertEqual(list(self.loan.loan_events.values()), before)
            self.assertEqual(self.loan.repayment_schedules.count(), 1)

    def test_portable_roundtrip_requires_version_8_and_preserves_one_opening(self):
        from apps.orgs.models import Company
        from apps.tenancy.context import without_workspace_context
        from apps.tenant_apps.party.models import Party
        from apps.tenant_apps.data_portability.models import (
            PartyIdentity,
            SourceIdentity,
        )
        from apps.tenant_apps.loans.services.license_series import create_license
        from apps.tenant_apps.loans.services.servicing_bundle import (
            export_servicing_bundle,
            restore_servicing_bundle,
        )
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
            self.apply()
        with self.scoped():
            content = export_servicing_bundle(
                workspace_id=self.a.pk, actor=self.actor, loan_id=self.loan.pk
            )
            document, _ = read_bundle(content)
            self.assertEqual(document["profile"], "loan-servicing-bundle/8")
            event = next(
                r
                for r in document["tables"]["PawnLoanEvent"]
                if r["event_kind"] == "OPENING_CORRECTION"
            )
            for version in range(1, 8):
                with self.assertRaisesMessage(ValueError, "version 8"):
                    decode(
                        "PawnLoanEvent",
                        event,
                        profile=f"loan-servicing-bundle/{version}",
                    )
        with without_workspace_context():
            target = Company.objects.create(
                name="Aggregate restore",
                schema_name="aggregate_" + uuid4().hex,
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
                workspace=target, name="Aggregate", code="AA"
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
            self.assertEqual(
                restored.loan_events.filter(event_kind="MIGRATION_OPENING").count(), 1
            )
            self.assertEqual(
                restored.loan_events.filter(event_kind="OPENING_CORRECTION").count(), 1
            )
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
        # Exact recovery must retain the original and corrected rows byte-for-byte.
        from apps.tenant_apps.loans.tests.test_pawn_recovery import PawnRecoveryTests

        self.tenant = target
        original = PawnRecoveryTests.export(self)
        PawnRecoveryTests.empty(self)
        self.assertFalse(PawnRecoveryTests.restore(self)["committed"])
        self.assertTrue(PawnRecoveryTests.restore(self, commit=True)["committed"])
        recovered = PawnRecoveryTests.export(self)
        self.assertEqual(original["tables"], recovered["tables"])
        self.assertEqual(original["files"], recovered["files"])

    def test_typed_http_review_uses_existing_screen_without_period_base_fields(self):
        from apps.tenancy.testing import start_workspace_trial
        from apps.tenant_apps.loans.web.opening_agreement_corrections import (
            CheckpointCorrectionForm,
        )

        start_workspace_trial(self.a)
        self.client.force_login(self.actor)
        with (
            self.scoped(),
            patch("django.utils.timezone.localdate", return_value=self.day),
        ):
            origin = self.loan.loan_events.get(event_kind="MIGRATION_OPENING")
            opening = read_opening_evidence(self.loan, origin)
            form = CheckpointCorrectionForm(
                opening=opening | {"review": corrected(opening["review"])}
            )
            self.assertFalse(
                any(
                    k.endswith("_base") or k.startswith("advance_") for k in form.fields
                )
            )
            data = dict(
                form.initial,
                reference="Confirmed original paper terms",
                reason="Incorrect migrated rate",
                request_key=uuid4().hex,
                action="preview",
            )
            url = reverse(
                "workspace_loans:pawn_agreement_correct",
                args=[self.a.slug, self.loan.pk],
            )
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(
                response.context["form"].errors, response.context["form"].errors
            )
            self.assertIsNotNone(response.context["review"])
            data.update(
                action="confirm",
                confirmed="on",
                review_token=response.context["form"].data["review_token"],
            )
            self.assertEqual(self.client.post(url, data).status_code, 302)
