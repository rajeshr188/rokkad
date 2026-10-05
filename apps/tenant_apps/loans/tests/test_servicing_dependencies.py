from datetime import timedelta
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.selectors.servicing_dependencies import servicing_dependencies
from apps.tenant_apps.loans.services.recorded_corrections import preview_correction, record_correction
from . import test_recorded_corrections as corrections


class ServicingDependencyTests(corrections.RecordedCorrectionTests):
    def test_correction_preview_becomes_stale_after_custody_evidence_changes(self):
        _, token = preview_correction(self.loan.pk, actor=self.actor, data=self.correction)
        count = self.loan.loan_events.count()
        item = self.loan.collateral_items.get()
        auction = m.PawnLoanAuction.objects.create(loan=self.loan, workspace=self.tenant, auction_number="AUC-dependency",
            attempt_number=1, request_key="custody-source", notice_date=self.today,
            scheduled_date=self.today+timedelta(days=60), created_by=self.actor)
        movement = m.PawnCollateralCustodyEvent.objects.create(collateral_item=item, actor=self.actor, auction=auction,
            effective_date=self.today, from_state="IN_VAULT", to_state="AUCTION_DISPOSED")
        item.custody_state = "AUCTION_DISPOSED"
        item.save(update_fields=["custody_state"])
        m.PawnCollateralCustodyEvent.objects.create(collateral_item=item, actor=self.actor, auction=auction,
            effective_date=self.today, from_state="AUCTION_DISPOSED", to_state="IN_VAULT")
        item.custody_state = "IN_VAULT"
        item.save(update_fields=["custody_state"])
        inventory = servicing_dependencies(self.loan, effective_date=self.day).evidence()
        self.assertIn(movement.pk, [row["id"] for row in inventory["custody"]])
        with self.assertRaisesMessage(ValueError, "dependencies changed"):
            record_correction(self.loan.pk, actor=self.actor, data=self.correction, review_token=token, confirmed=True)
        self.assertEqual(count, self.loan.loan_events.count())
