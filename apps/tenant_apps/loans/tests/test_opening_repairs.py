from datetime import date
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from apps.orgs.audit import AuditLog
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.opening_repairs import restore_opening_quantities
from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full
from apps.tenant_apps.loans.services.history_import import balance_values
from apps.tenant_apps.loans.tests.test_opening_import import OpeningImportFixture


class OpeningQuantityRepairTests(OpeningImportFixture):
    def repair(self, origin, **changes):
        return restore_opening_quantities(**dict(workspace_id=self.a.pk, actor=self.actor,
            origin_id=origin.pk, expected_sha256=origin.source_sha256, **changes))

    def test_new_import_preserves_quantity_and_old_projection_repairs_once(self):
        with self.scoped():
            origin = self.write()
            item = origin.loan.collateral_items.get()
            self.assertEqual(item.quantity, self.review['collateral'][0]['quantity'])
            m.PawnCollateralItem.objects.filter(pk=item.pk).update(quantity=None)
            frozen = (origin.document, list(origin.loan.loan_events.values('pk','payload','payload_fingerprint')))
            self.assertEqual(self.repair(origin), 1)
            self.assertEqual(self.repair(origin), 0)
            item.refresh_from_db(); origin.refresh_from_db()
            self.assertEqual(item.quantity, self.review['collateral'][0]['quantity'])
            self.assertEqual(frozen, (origin.document, list(origin.loan.loan_events.values('pk','payload','payload_fingerprint'))))
            self.assertEqual(AuditLog.objects.filter(data__operation='RESTORE_OPENING_QUANTITIES').count(), 1)

    def test_closed_loan_money_custody_and_release_evidence_preserved(self):
        with self.scoped(), patch('django.utils.timezone.localdate', return_value=date(2021, 2, 2)):
            origin = self.write()
            release_pawn_loan_in_full(origin.loan_id, settlement_amount=1010, request_key='repair-release', actor=self.actor)
            m.PawnCollateralItem.objects.filter(loan=origin.loan).update(quantity=None)
            before = (balance_values(origin.loan, date(2021,2,2)), list(origin.loan.loan_events.values()),
                      list(origin.loan.collateral_items.values_list('custody_state',flat=True)))
            self.assertEqual(self.repair(origin), 1)
            origin.loan.refresh_from_db()
            self.assertEqual(origin.loan.state, 'CLOSED')
            self.assertEqual(before, (balance_values(origin.loan, date(2021,2,2)), list(origin.loan.loan_events.values()),
                      list(origin.loan.collateral_items.values_list('custody_state',flat=True))))

    def test_conflicts_and_audit_failure_never_overwrite(self):
        with self.scoped():
            origin = self.write(); item = origin.loan.collateral_items.get()
            m.PawnCollateralItem.objects.filter(pk=item.pk).update(quantity=item.quantity+1)
            with self.assertRaisesMessage(ValueError, 'contradicts'):
                self.repair(origin)
            m.PawnCollateralItem.objects.filter(pk=item.pk).update(quantity=None)
            with patch('apps.tenant_apps.loans.services.opening_repairs.AuditLog.log',side_effect=RuntimeError('audit failed')):
                with self.assertRaises(RuntimeError):self.repair(origin)
            item.refresh_from_db();self.assertIsNone(item.quantity)
            with self.assertRaisesMessage(ValueError, 'fingerprint'):
                restore_opening_quantities(workspace_id=self.a.pk,actor=self.actor,origin_id=origin.pk,expected_sha256='0'*64)

    def test_wrong_actor_and_workspace_denied_under_restricted_role(self):
        with self.scoped():
            origin=self.write()
            with self.assertRaises(PermissionDenied):
                restore_opening_quantities(workspace_id=self.a.pk,actor=self.other_actor,origin_id=origin.pk,expected_sha256=origin.source_sha256)
        with self.scoped(self.b), self.assertRaises(PermissionDenied):self.repair(origin)
