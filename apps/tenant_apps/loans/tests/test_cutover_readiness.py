import json
from datetime import date
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from apps.tenant_apps.loans.selectors.cutover_readiness import (
    MANUAL_ACKNOWLEDGEMENTS,
    build_pawn_loan_cutover_readiness,
    get_pawn_loan_cutover_readiness,
)


AS_OF = date(2026, 8, 4)


class PawnLoanCutoverReadinessTests(SimpleTestCase):
    def test_clean_automated_evidence_and_all_acknowledgements_produce_go(self):
        readiness = self._build()

        self.assertTrue(readiness.is_ready)
        self.assertEqual(readiness.blocker_count, 0)
        self.assertEqual(readiness.as_dict()["is_ready"], True)
        self.assertFalse(readiness.feature_enabled)

    def test_every_automated_and_manual_gap_is_fail_closed(self):
        readiness = self._build(
            pending_migrations=("loans.9999_pending",),
            operations=self._operations(
                sequence_rows=(),
                sequence_blocker_count=0,
                failed_count=1,
                stale_processing_events=(object(),),
                accounting_blocker_count=2,
            ),
            reports=SimpleNamespace(issues=(object(),)),
            acknowledgements={},
        )

        self.assertFalse(readiness.is_ready)
        blocked = {check.code for check in readiness.checks if not check.passed}
        self.assertEqual(
            blocked,
            {
                "LOANS_MIGRATIONS",
                "NUMBERING_READY",
                "OUTBOX_HEALTH",
                "ACCOUNTING_READY",
                "LOANS_RECONCILIATION",
                *(code for code, _ in MANUAL_ACKNOWLEDGEMENTS),
            },
        )

    @patch(
        "apps.tenant_apps.loans.selectors.cutover_readiness.current_tenant_workspace_id",
        return_value=None,
    )
    def test_runtime_selector_requires_tenant_schema(self, _workspace_id):
        with self.assertRaisesMessage(ValueError, "active tenant schema"):
            get_pawn_loan_cutover_readiness(as_of_date=AS_OF)

    @patch(
        "apps.tenant_apps.loans.management.commands.check_pawn_loan_cutover_readiness.get_pawn_loan_cutover_readiness"
    )
    def test_command_emits_machine_readable_go_evidence(self, readiness_selector):
        readiness_selector.return_value = self._build()
        stdout = StringIO()

        call_command(
            "check_pawn_loan_cutover_readiness",
            as_of=AS_OF.isoformat(),
            format="json",
            ack_backup=True,
            ack_rollback=True,
            ack_support=True,
            ack_monitoring=True,
            ack_permissions=True,
            ack_pilot_workflow=True,
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["is_ready"])
        acknowledgements = readiness_selector.call_args.kwargs["acknowledgements"]
        self.assertTrue(all(acknowledgements.values()))

    @patch(
        "apps.tenant_apps.loans.management.commands.check_pawn_loan_cutover_readiness.get_pawn_loan_cutover_readiness"
    )
    def test_command_can_fail_deployment_on_any_blocker(self, readiness_selector):
        readiness_selector.return_value = self._build(acknowledgements={})

        with self.assertRaisesMessage(CommandError, "NO-GO"):
            call_command(
                "check_pawn_loan_cutover_readiness",
                as_of=AS_OF.isoformat(),
                fail_on_blocker=True,
            )

    def _build(self, **overrides):
        values = {
            "workspace_id": 42,
            "as_of_date": AS_OF,
            "feature_enabled": False,
            "pending_migrations": (),
            "operations": self._operations(),
            "reports": SimpleNamespace(issues=()),
            "acknowledgements": {
                code: True for code, _ in MANUAL_ACKNOWLEDGEMENTS
            },
        }
        values.update(overrides)
        return build_pawn_loan_cutover_readiness(**values)

    @staticmethod
    def _operations(**overrides):
        values = {
            "sequence_rows": (object(), object()),
            "sequence_blocker_count": 0,
            "failed_count": 0,
            "stale_processing_events": (),
            "accounting_blocker_count": 0,
        }
        values.update(overrides)
        return SimpleNamespace(**values)
