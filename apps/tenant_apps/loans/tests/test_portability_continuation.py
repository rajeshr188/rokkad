"""Named acceptance checks against ordinary services after a native-loan restore."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.utils import timezone

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.tests import test_servicing_bundle as fixture
from apps.tenant_apps.loans.tests.test_recorded_auctions import on
from apps.tenant_apps.loans.services.servicing_bundle import export_servicing_bundle
from apps.tenant_apps.loans.services.servicing_bundle_contract import read_bundle


class PortabilityContinuationTests(fixture.ApprovedBundleTests):
    def test_fresh_graph_package_requires_local_licence_review_then_creates_next_direct_loan(
        self,
    ):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from uuid import uuid4
        from apps.orgs.models import Company, Membership, Role
        from apps.tenant_apps.data_portability import (
            business_package as package,
            services,
        )
        from apps.tenant_apps.loans.services.storage_operations import (
            create_storage_location,
        )
        from apps.tenant_apps.loans.services.license_series import (
            assert_series_can_issue,
            update_license,
        )
        from apps.tenant_apps.loans.services import (
            CreatePawnDraftCommand,
            CollateralDraftInput,
            create_pawn_draft,
            approve_pawn_loan,
        )
        from apps.tenant_apps.loans.services.pawn_disbursal import disburse_pawn_loan

        self.native_bundle()
        target = Company.objects.create(
            name="Fresh native continuation",
            slug="fresh-native-" + uuid4().hex,
            schema_name="fresh_native_" + uuid4().hex,
            owner=self.actor,
            creator=self.actor,
        )
        Membership.objects.create(
            company=target, user=self.actor, role=Role.objects.get(name="Owner")
        )
        with TemporaryDirectory() as directory:
            with self.scoped():
                create_storage_location(
                    workspace=self.a,
                    actor=self.actor,
                    level="BRANCH",
                    code="SPARE",
                    name="Unused configured branch",
                )
                with patch.object(services, "require_export_snapshot"):
                    exported = package.write_package(
                        workspace_id=self.a.pk,
                        actor=self.actor,
                        directory=Path(directory),
                        _consistent_snapshot=True,
                    )
                self.assertEqual(exported["profile"], package.GRAPH_PROFILE)
            with self.scoped(target):
                args = dict(
                    workspace_id=target.pk,
                    actor=self.actor,
                    directory=directory,
                    expected_sha256=exported["sha256"],
                )
                review = package.preview_package(**args)
                package.restore_package(
                    **args, approval=review["approval"], confirmed=True
                )
                # Provisioning does not transfer commercial access. Activate this
                # fictional destination explicitly before normal new lending.
                from apps.tenancy.testing import WorkspaceTestCase
                from types import SimpleNamespace

                WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=target))
                original = m.PawnLoan.objects.get()
                series = original.series
                license = series.license
                self.assertFalse(license.is_active)
                license.is_active = True
                license.save(update_fields=["is_active"])
                with self.assertRaisesMessage(
                    ValueError, "Review and save the imported licence"
                ):
                    assert_series_can_issue(series)
                update_license(license, actor=self.actor)
                series.refresh_from_db()
                assert_series_can_issue(series)
                # Restore preserves the old market observation; new lending
                # needs a fresh observation rather than redating its evidence.
                from apps.tenant_apps.rates.models import Rate

                earlier_quote = Rate.objects.latest("effective_at")
                earlier_time = earlier_quote.effective_at
                Rate.objects.create(
                    rate_source=earlier_quote.rate_source,
                    metal=earlier_quote.metal,
                    currency=earlier_quote.currency,
                    purity=earlier_quote.purity,
                    buying_rate=earlier_quote.buying_rate,
                    selling_rate=earlier_quote.selling_rate,
                    effective_at=timezone.now(),
                    recorded_by=self.actor,
                )
                earlier_quote.refresh_from_db()
                self.assertEqual(earlier_quote.effective_at, earlier_time)
                loan = create_pawn_draft(
                    CreatePawnDraftCommand(
                        workspace_id=target.pk,
                        borrower_id=original.borrower_id,
                        license_id=license.pk,
                        series_id=series.pk,
                        product_version_id=original.product_version_id,
                        principal_amount=Decimal("1000"),
                        monthly_interest_rate=Decimal("2"),
                        loan_date=timezone.localdate(),
                        tenure_months=3,
                        collateral=(
                            CollateralDraftInput(
                                description="New ring",
                                metal="GOLD",
                                gross_weight=Decimal("3"),
                                net_weight=Decimal("2"),
                                purity_percentage=Decimal("90"),
                                latest_appraised_value=Decimal("12000"),
                                allocated_principal=Decimal("1000"),
                            ),
                        ),
                    ),
                    actor=self.actor,
                )
                self.assertEqual(loan.loan_number, "C-00002")
                approve_pawn_loan(loan.pk, actor=self.actor)
                disburse_pawn_loan(
                    loan.pk, effective_date=timezone.localdate(), actor=self.actor
                )
                loan.refresh_from_db()
                self.assertEqual(loan.state, "ACTIVE")
                self.assertFalse(
                    m.HistoricalLoanImport.objects.filter(loan=loan).exists()
                )
                self.assertEqual(m.PawnLoan.objects.count(), 2)
                self.assertEqual(m.PawnStorageLocation.objects.get().code, "SPARE")

    def test_restored_native_loan_prints_monitors_collects_closes_and_reexports(self):
        from apps.tenant_apps.loans.services.documents import PawnLoanDocumentService
        from apps.tenant_apps.loans.services.transaction_reviews import (
            preview_transaction_review,
            confirm_transaction_review,
        )
        from apps.tenant_apps.loans.selectors.servicing_contract import (
            get_servicing_position,
        )
        from apps.tenant_apps.loans.selectors.collateral_valuation import (
            get_pawn_loan_collateral_valuation,
        )
        from apps.tenant_apps.loans.selectors.risk import get_pawn_loan_risk_assessment
        from apps.tenant_apps.loans.services.pawn_repayment import (
            record_pawn_loan_repayment,
        )
        from apps.tenant_apps.loans.services.pawn_release import (
            preview_pawn_loan_full_release,
            release_pawn_loan_in_full,
        )
        from apps.tenant_apps.loans.services.number_allocation import (
            allocate_pawn_loan_number,
            preview_number,
        )
        from apps.tenant_apps.rates.models import Rate, RateSource

        result = {}
        original = fixture.roundtrip

        def retain(case, content):
            result.update(original(case, content))
            return result

        with patch.object(fixture, "roundtrip", side_effect=retain):
            self.native_bundle()
        with self.scoped(self.b), on(date(2026, 10, 5)):
            loan = m.PawnLoan.objects.get(pk=result["loans"][0])
            agreement = loan.approval_snapshots.get().payload.copy()
            self.assertTrue(
                PawnLoanDocumentService.render_loan_ticket(loan).pdf.startswith(b"%PDF")
            )
            m.LoanMonitoringPolicy.objects.create(
                workspace=self.b,
                version=1,
                effective_from=loan.loan_date,
                compliance_profile="Synthetic continuation acceptance",
                ltv_warning_ratio=Decimal(".7"),
                ltv_breach_ratio=Decimal(".8"),
                ltv_critical_ratio=Decimal(".9"),
                eligible_custody_states=["IN_VAULT", "WITH_FUNDING_LENDER"],
                severity_mapping={
                    "LOW": "LOW",
                    "MEDIUM": "MEDIUM",
                    "HIGH": "HIGH",
                    "CRITICAL": "CRITICAL",
                },
                created_by=self.actor,
            )
            unknown = get_pawn_loan_risk_assessment(loan.pk, as_of_date=loan.loan_date)
            self.assertIn("VALUATION_UNKNOWN", unknown.flags)
            source = RateSource.objects.create(
                name="Destination market", location="Local"
            )
            Rate.objects.create(
                rate_source=source,
                buying_rate=10000,
                selling_rate=10100,
                effective_at=timezone.now(),
                recorded_by=self.actor,
            )
            valuation = get_pawn_loan_collateral_valuation(
                loan.pk, as_of_date=loan.loan_date
            )
            self.assertIsNotNone(valuation.ltv.ltv_ratio)
            self.assertNotIn(
                "VALUATION_UNKNOWN",
                get_pawn_loan_risk_assessment(loan.pk, as_of_date=loan.loan_date).flags,
            )
            loan.approval_snapshots.get().refresh_from_db()
            self.assertEqual(loan.approval_snapshots.get().payload, agreement)
            facts = dict(
                through_date=loan.loan_date,
                confirmed_complete=True,
                source_reference="Synthetic accepted transfer checked locally",
                request_key="local-continuation",
                future_capture="ROKKAD_ONLY",
            )
            _, token = preview_transaction_review(loan.pk, actor=self.actor, **facts)
            confirm_transaction_review(
                loan.pk,
                actor=self.actor,
                review_token=token,
                acknowledged=True,
                **facts,
            )
            before = get_servicing_position(
                loan, as_of_date=loan.loan_date
            ).balance.total_due
            payment = record_pawn_loan_repayment(
                loan.pk,
                amount="200",
                request_key="destination-receipt",
                actor=self.actor,
            )
            self.assertTrue(
                PawnLoanDocumentService.render_repayment_receipt(
                    payment.loan_event
                ).pdf.startswith(b"%PDF")
            )
            loan.refresh_from_db()
            self.assertEqual(
                get_servicing_position(
                    loan, as_of_date=loan.loan_date
                ).balance.total_due,
                before - 200,
            )
            m.LoanNumberSequence.objects.create(
                series=loan.series,
                document_kind="PAWN_LOAN",
                prefix="N-",
                width=5,
                maximum_number=10000,
                next_number=50,
            )
            m.LoanNumberSequence.objects.create(
                series=loan.series,
                document_kind="PAWN_LOAN_RELEASE",
                prefix="NR-",
                width=5,
                maximum_number=10000,
                next_number=25,
            )
            self.assertEqual(
                preview_number(series=loan.series, document_kind="PAWN_LOAN").value,
                "N-00050",
            )
            self.assertEqual(
                allocate_pawn_loan_number(series=loan.series, actor=self.actor).value,
                "N-00050",
            )
            self.assertEqual(
                preview_number(series=loan.series, document_kind="PAWN_LOAN").value,
                "N-00051",
            )
            quote = preview_pawn_loan_full_release(loan.pk)
            released = release_pawn_loan_in_full(
                loan.pk,
                settlement_amount=quote.minimum_settlement,
                request_key="destination-closure",
                actor=self.actor,
            )
            self.assertEqual(released.release.release_number, "NR-00025")
            self.assertTrue(
                PawnLoanDocumentService.render_release_memo(
                    released.release
                ).pdf.startswith(b"%PDF")
            )
            loan.refresh_from_db()
            self.assertEqual(loan.state, "CLOSED")
            self.assertEqual(loan.loan_events.filter(event_kind="DISBURSAL").count(), 1)
            final, _ = read_bundle(
                export_servicing_bundle(
                    workspace_id=self.b.pk, actor=self.actor, loan_id=loan.pk
                )
            )
            self.assertTrue(
                all(
                    Decimal(value) == 0
                    for value in final["positions"][str(loan.pk)]["recorded"].values()
                )
            )
